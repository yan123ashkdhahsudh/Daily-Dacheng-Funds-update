#!/usr/bin/env python3
import argparse
import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from zoneinfo import ZoneInfo


TITLE = "大成·招行重点持营业绩速览"
SOURCE = "东方财富公开数据 / 同花顺公开页检测"
SOURCE_URL = "https://www.10jqka.com.cn"

GROUPS = [
    {
        "label": "重点持营固收加",
        "items": [
            ("大成丰享回报", "009653"),
            ("大成优享6个月", "026037"),
            ("大成安享得利", "010940"),
        ],
    },
    {
        "label": "启明星权益",
        "items": [
            ("大成洞察优势", "024406"),
        ],
    },
    {
        "label": "徐彦权益系列",
        "items": [
            ("大成卓远视野", "017669"),
        ],
    },
    {
        "label": "重点固收+",
        "items": [
            ("大成元辰招利", "020676"),
            ("大成元丰多利", "019372"),
        ],
    },
    {
        "label": "刘旭权益系列",
        "items": [
            ("大成高鑫股票", "000628"),
            ("大成优势企业", "008271"),
        ],
    },
]

FEATURED = [
    {"name": "大成绩优科技基", "headline": True},
    {"name": "大成科技创新", "code": "008988"},
    {"name": "大成至臻回报", "code": "024469"},
]

INDEXES = [
    ("上证指数", "1.000001", "sh000001"),
    ("沪深300", "1.000300", "sh000300"),
    ("创业板指", "0.399006", "sz399006"),
]


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


def fund_rows(code, start_date="", end_date="", page_size=30):
    url = (
        "https://api.fund.eastmoney.com/f10/lsjz"
        f"?fundCode={code}&pageIndex=1&pageSize={page_size}"
        f"&startDate={start_date}&endDate={end_date}"
    )
    text = request_text(url, f"https://fundf10.eastmoney.com/jjjz_{code}.html")
    data = json.loads(text)
    return data.get("Data", {}).get("LSJZList", [])


def all_fund_codes():
    codes = []
    for group in GROUPS:
        codes.extend(code for _, code in group["items"])
    codes.extend(item["code"] for item in FEATURED if "code" in item)
    return codes


def choose_latest_common_date():
    date_sets = []
    for code in all_fund_codes():
        dates = {row["FSRQ"] for row in fund_rows(code)}
        if dates:
            date_sets.append(dates)
    common_dates = set.intersection(*date_sets) if date_sets else set()
    if not common_dates:
        raise RuntimeError("No common net-value date found across funds.")
    return max(common_dates)


def fund_row_on_or_before(code, target_date):
    start = (
        datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=12)
    ).strftime("%Y-%m-%d")
    rows = fund_rows(code, start, target_date, page_size=20)
    eligible = [row for row in rows if row.get("FSRQ", "") <= target_date]
    if not eligible:
        raise RuntimeError(f"No fund data found for {code} on or before {target_date}.")
    return max(eligible, key=lambda row: row["FSRQ"])


def ytd_return(code, target_date, target_nav):
    year = int(target_date[:4])
    base_end = f"{year - 1}-12-31"
    base_start = f"{year - 1}-12-15"
    rows = fund_rows(code, base_start, base_end, page_size=30)
    eligible = [row for row in rows if row.get("FSRQ", "") <= base_end]
    if not eligible:
        return None
    base_row = max(eligible, key=lambda row: row["FSRQ"])
    base_nav = float(base_row["DWJZ"])
    return round((target_nav / base_nav - 1) * 100, 2)


def eastmoney_index_return(secid, target_date):
    date_compact = target_date.replace("-", "")
    start = (
        datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=12)
    ).strftime("%Y%m%d")
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


def tencent_index_return(symbol, target_date):
    start = (
        datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=12)
    ).strftime("%Y-%m-%d")
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
    today = rows[-1]
    previous = rows[-2]
    return round((float(today[2]) / float(previous[2]) - 1) * 100, 2)


def index_return(secid, fallback_symbol, target_date):
    try:
        return eastmoney_index_return(secid, target_date)
    except Exception:
        return tencent_index_return(fallback_symbol, target_date)


def display_date(date_text):
    date = datetime.strptime(date_text, "%Y-%m-%d")
    return f"{date.year}.{date.month}.{date.day}"


def build_payload(target_date):
    payload_groups = []
    for group in GROUPS:
        items = []
        for name, code in group["items"]:
            row = fund_row_on_or_before(code, target_date)
            items.append({"name": name, "dailyReturn": round(float(row["JZZZL"]), 2)})
        payload_groups.append({"label": group["label"], "items": items})

    featured = []
    for item in FEATURED:
        if item.get("headline"):
            featured.append({"name": item["name"], "dailyReturn": None, "headline": True})
            continue
        row = fund_row_on_or_before(item["code"], target_date)
        nav = float(row["DWJZ"])
        payload = {
            "name": item["name"],
            "dailyReturn": round(float(row["JZZZL"]), 2),
        }
        ytd = ytd_return(item["code"], target_date, nav)
        if ytd is not None:
            payload["yearToDate"] = ytd
        featured.append(payload)

    indexes = [
        {"name": name, "dailyReturn": index_return(secid, fallback_symbol, target_date)}
        for name, secid, fallback_symbol in INDEXES
    ]

    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    return {
        "title": TITLE,
        "asOf": display_date(target_date),
        "source": SOURCE,
        "sourceUrl": SOURCE_URL,
        "updatedAt": now,
        "groups": payload_groups,
        "featured": featured,
        "indexes": indexes,
    }


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Update website data from public fund and index endpoints.")
    parser.add_argument("--date", help="Target data date, e.g. 2026-06-30. Defaults to latest common fund date.")
    parser.add_argument("--out", default=str(root / "data" / "performance.json"))
    args = parser.parse_args()

    target_date = args.date or choose_latest_common_date()
    payload = build_payload(target_date)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {out_path} with data as of {payload['asOf']}")


if __name__ == "__main__":
    main()
