#!/usr/bin/env python3
import argparse
import json
import re
import ssl
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from zoneinfo import ZoneInfo


SOURCE_URL = "https://www.wind.com.cn"
INDEXES = {
    "上证指数": ("1.000001", "sh000001"),
    "沪深300": ("1.000300", "sh000300"),
    "创业板指": ("0.399006", "sz399006"),
}


def request_text(url, referer):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="ignore")
    except URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            return response.read().decode("utf-8", errors="ignore")


@lru_cache(maxsize=None)
def fund_rows(code, start_date="", end_date="", page_size=30):
    url = (
        "https://api.fund.eastmoney.com/f10/lsjz"
        f"?fundCode={code}&pageIndex=1&pageSize={page_size}"
        f"&startDate={start_date}&endDate={end_date}"
    )
    text = request_text(url, f"https://fundf10.eastmoney.com/jjjz_{code}.html")
    return json.loads(text).get("Data", {}).get("LSJZList", [])


def load_templates(root):
    path = root / "data" / "bank_templates.json"
    return json.loads(path.read_text(encoding="utf-8"))


def all_fund_codes(templates):
    return sorted({row["fund_code"] for row in templates["fundRows"] if row.get("fund_code")})


def choose_latest_available_date(templates):
    latest_dates = []
    for code in all_fund_codes(templates):
        rows = fund_rows(code, page_size=8)
        if rows:
            latest_dates.append(max(row["FSRQ"] for row in rows))
    if not latest_dates:
        raise RuntimeError("No fund net-value date found.")
    return max(latest_dates)


def fund_row_on_or_before(code, target_date):
    target = datetime.strptime(target_date, "%Y-%m-%d")
    for days in (18, 45, 120, 420):
        start = (target - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = fund_rows(code, start, target_date, page_size=100)
        eligible = [row for row in rows if row.get("FSRQ", "") <= target_date]
        if eligible:
            return max(eligible, key=lambda row: row["FSRQ"])
    raise RuntimeError(f"No fund data found for {code} on or before {target_date}.")


@lru_cache(maxsize=None)
def period_return(code, target_date, target_nav, label):
    target = datetime.strptime(target_date, "%Y-%m-%d")
    if label == "今年以来":
        base_end = f"{target.year - 1}-12-31"
        base_start = f"{target.year - 1}-12-15"
    elif label == "近1年":
        base = target - timedelta(days=365)
        base_end = base.strftime("%Y-%m-%d")
        base_start = (base - timedelta(days=18)).strftime("%Y-%m-%d")
    else:
        return None

    rows = fund_rows(code, base_start, base_end, page_size=30)
    eligible = [row for row in rows if row.get("FSRQ", "") <= base_end]
    if not eligible:
        return None
    base_row = max(eligible, key=lambda row: row["FSRQ"])
    base_nav = float(base_row["DWJZ"])
    return round((target_nav / base_nav - 1) * 100, 2)


@lru_cache(maxsize=None)
def eastmoney_index_return(secid, target_date):
    date_compact = target_date.replace("-", "")
    start = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=12)).strftime("%Y%m%d")
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt=101&fqt=1&beg={start}&end={date_compact}"
    )
    text = request_text(url, "https://quote.eastmoney.com/")
    data = json.loads(text).get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        raise RuntimeError(f"No index data found for {secid} on or before {target_date}.")
    latest = max((line.split(",") for line in klines), key=lambda parts: parts[0])
    return round(float(latest[8]), 2)


@lru_cache(maxsize=None)
def tencent_index_return(symbol, target_date):
    start = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=12)).strftime("%Y-%m-%d")
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={symbol},day,{start},{target_date},20,qfq"
    )
    text = request_text(url, "https://gu.qq.com/")
    data = json.loads(text).get("data") or {}
    rows = (data.get(symbol) or {}).get("day") or []
    rows = [row for row in rows if row[0] <= target_date]
    if len(rows) < 2:
        raise RuntimeError(f"No fallback index data found for {symbol} on or before {target_date}.")
    rows.sort(key=lambda row: row[0])
    return round((float(rows[-1][2]) / float(rows[-2][2]) - 1) * 100, 2)


def index_return(name, target_date):
    secid, fallback_symbol = INDEXES[name]
    try:
        return eastmoney_index_return(secid, target_date)
    except Exception:
        return tencent_index_return(fallback_symbol, target_date)


def display_date(date_text):
    date = datetime.strptime(date_text, "%Y-%m-%d")
    return f"{date.year}.{date.month}.{date.day}"


def signed_percent(value):
    if value is None:
        return "--"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def period_percent(value):
    if value is None:
        return "--"
    number = float(value)
    return f"{number:.2f}%" if number >= 0 else f"-{abs(number):.2f}%"


def note_suffix(note):
    match = re.search(r"原文备注[:：](.+)$", note or "")
    if not match:
        return ""
    return f"（{match.group(1).strip()}）"


def is_hong_kong_fund(fund):
    name = fund.get("fund_name", "")
    return "港股" in name or "恒生" in name


def stale_data_suffix(value, target_date, fund):
    if is_hong_kong_fund(fund):
        return ""
    if value.get("date") and value.get("date") != target_date:
        return "（数据未更新）"
    return ""


def template_indexes(templates):
    fund_by_bank_group = defaultdict(deque)
    for row in sorted(templates["fundRows"], key=lambda item: item["fund_order"]):
        fund_by_bank_group[(row["bank_id"], row["group_name"])].append(row)

    lines_by_bank = defaultdict(list)
    for row in sorted(templates["templateRows"], key=lambda item: item["line_order"]):
        lines_by_bank[row["bank_id"]].append(row)

    return fund_by_bank_group, lines_by_bank


def build_fund_values(templates, target_date):
    values = {}
    unique_rows = {}
    for row in templates["fundRows"]:
        code = row.get("fund_code")
        if code and row.get("metric_type") == "daily_return":
            unique_rows[code] = row

    for code in sorted(unique_rows):
        row = fund_row_on_or_before(code, target_date)
        nav = float(row["DWJZ"])
        values[code] = {
            "daily": round(float(row.get("JZZZL") or 0), 2),
            "nav": nav,
            "date": row["FSRQ"],
        }
    return values


def render_bank(bank, templates, fund_values, index_values, target_date, now):
    fund_queues, lines_by_bank = template_indexes(templates)
    display_lines = []
    wechat_lines = []
    footer_text = ""
    last_fund = None

    for line in lines_by_bank[bank["bank_id"]]:
        line_type = line["line_type"]
        text = line["template_text"]

        if line_type in {"fund_item", "featured_item"}:
            fund = fund_queues[(bank["bank_id"], line["group_name"])].popleft()
            value = fund_values.get(fund.get("fund_code"), {})
            text = text.replace("{daily_return}", signed_percent(value.get("daily")))
            if not is_hong_kong_fund(fund):
                text += note_suffix(fund.get("note", ""))
            text += stale_data_suffix(value, target_date, fund)
            last_fund = {**fund, **value}
        elif line_type == "featured_ytd":
            period = None
            if last_fund and last_fund.get("fund_code"):
                period = period_return(
                    last_fund["fund_code"],
                    target_date,
                    last_fund["nav"],
                    last_fund.get("period_label") or "今年以来",
                )
            text = text.replace("{period_return}", period_percent(period))
        elif line_type == "index":
            name = next((item for item in INDEXES if item in text), "")
            text = text.replace("{index_return}", signed_percent(index_values.get(name)))
        elif line_type == "footer":
            text = text.replace("{date}", display_date(target_date))
            footer_text = text

        if line_type == "title":
            wechat_lines.append(text)
            wechat_lines.append("")
            continue
        if line_type == "stars":
            wechat_lines.append(text)
            continue

        wechat_lines.append(text)
        if line_type != "footer":
            display_lines.append({"type": line_type, "text": text})

    return {
        "id": bank["bank_id"],
        "name": bank["bank_name"],
        "title": bank["title"],
        "asOf": display_date(target_date),
        "source": bank.get("source") or "wind",
        "sourceUrl": SOURCE_URL,
        "updatedAt": now,
        "lines": display_lines,
        "footer": footer_text,
        "wechatText": "\n".join(wechat_lines),
    }


def build_payload(root, target_date):
    templates = load_templates(root)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    fund_values = build_fund_values(templates, target_date)
    index_values = {name: index_return(name, target_date) for name in INDEXES}
    banks = [
        render_bank(bank, templates, fund_values, index_values, target_date, now)
        for bank in templates["banks"]
    ]
    return {
        "version": 3,
        "defaultBank": "cmb_1",
        "banks": banks,
    }


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Update website data from public fund and index endpoints.")
    parser.add_argument("--date", help="Target data date, e.g. 2026-07-06. Defaults to latest available fund date.")
    parser.add_argument("--out", default=str(root / "data" / "performance.json"))
    args = parser.parse_args()

    templates = load_templates(root)
    target_date = args.date or choose_latest_available_date(templates)
    payload = build_payload(root, target_date)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {out_path} with data as of {display_date(target_date)}")


if __name__ == "__main__":
    main()
