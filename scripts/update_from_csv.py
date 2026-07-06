#!/usr/bin/env python3
import argparse
import csv
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


def to_float(value):
    value = (value or "").strip().replace("%", "")
    return None if value == "" else round(float(value), 4)


def main():
    parser = argparse.ArgumentParser(description="Build website data from a Wind-exported CSV.")
    parser.add_argument("csv_file", help="CSV with section, group, name, daily_return, year_to_date, headline columns")
    parser.add_argument("--out", default="wind_daily_site/data/performance.json")
    parser.add_argument("--as-of", required=True, help="Display date, e.g. 2026.6.29")
    parser.add_argument("--title", default="大成·招行重点持营业绩速览")
    parser.add_argument("--source", default="wind / 同花顺公开页检测")
    parser.add_argument("--source-url", default="https://www.10jqka.com.cn")
    args = parser.parse_args()

    groups = OrderedDict()
    featured = []
    indexes = []

    with open(args.csv_file, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            section = (row.get("section") or "").strip().lower()
            group_name = (row.get("group") or "").strip()
            name = (row.get("name") or "").strip()
            if not section or not name:
                continue

            item = {
                "name": name,
                "dailyReturn": to_float(row.get("daily_return")),
            }
            ytd = to_float(row.get("year_to_date"))
            if ytd is not None:
                item["yearToDate"] = ytd
            if (row.get("headline") or "").strip().lower() in {"1", "true", "yes", "y"}:
                item["headline"] = True

            if section == "group":
                groups.setdefault(group_name, []).append(item)
            elif section == "featured":
                featured.append(item)
            elif section == "index":
                indexes.append(item)

    payload = {
        "title": args.title,
        "asOf": args.as_of,
        "source": args.source,
        "sourceUrl": args.source_url,
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "groups": [{"label": label, "items": items} for label, items in groups.items()],
        "featured": featured,
        "indexes": indexes,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {out_path}")


if __name__ == "__main__":
    main()
