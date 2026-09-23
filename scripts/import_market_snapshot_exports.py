"""Import browser-exported market period snapshots without touching daily SYCM facts.

The exports contain ranges (for example ``1万 ~ 2.5万``), so both the raw
range and a midpoint estimate are stored.  The script is idempotent by file
hash and keeps the original period boundaries for weekly/monthly comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import openpyxl


def period_bounds(value):
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", str(value or ""))
    if len(dates) == 1:
        return dates[0], dates[0]
    if len(dates) == 2:
        return dates[0], dates[1]
    raise ValueError(f"invalid period: {value}")


def midpoint(value, percentage=False):
    text = str(value or "").strip().replace(",", "")
    if not text or text in {"-", "--"}:
        return None
    # Apply the unit to each endpoint independently.  For example, ``7500 ~ 1万``
    # means 7,500 to 10,000, not (7,500 + 1) * 10,000.
    matches = list(re.finditer(r"(-?\d+(?:\.\d+)?)(万|亿)?", text))
    values = []
    for match in matches:
        number = float(match.group(1))
        unit = match.group(2)
        values.append(number * (10000 if unit == "万" else 100000000 if unit == "亿" else 1))
    if not values:
        return None
    result = sum(values) / len(values)
    if percentage and ("%" in text or abs(result) > 1):
        result /= 100
    return result


def read_xlsx(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(v).strip() if v is not None else "" for v in rows[0]]
    return headers, [dict(zip(headers, row)) for row in rows[1:]]


def classify(name):
    if name.startswith("市场排行"):
        return "item"
    if name.startswith("搜索排行"):
        return "search"
    if "竞品列表" in name:
        return "rival_item"
    if "竞店列表" in name:
        return "rival_shop"
    return None


def schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS market_snapshot_batches (
      id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_type TEXT NOT NULL,
      source_filename TEXT NOT NULL, source_hash TEXT NOT NULL UNIQUE,
      period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      row_count INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_items (
      batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      cate_name TEXT, item_id TEXT NOT NULL, title TEXT, product_url TEXT,
      core_keyword TEXT, shop_name TEXT, shop_type TEXT, uv_value REAL, uv_range TEXT,
      pay_buyer_value REAL, pay_buyer_range TEXT, rank INTEGER, trend TEXT,
      UNIQUE(batch_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_searches (
      batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      cate_name TEXT, keyword TEXT NOT NULL, search_heat_value REAL, search_heat_range TEXT,
      pay_rate_value REAL, pay_rate_range TEXT, click_rate_value REAL, click_rate_range TEXT,
      rank INTEGER, UNIQUE(batch_id, cate_name, keyword)
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_rival_items (
      batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      item_id TEXT NOT NULL, title TEXT, shop_name TEXT, tag TEXT,
      pay_buyer_value REAL, pay_buyer_range TEXT, transaction_growth TEXT,
      uv_value REAL, uv_range TEXT, traffic_growth TEXT, estimated_payment_amount TEXT,
      UNIQUE(batch_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_rival_shops (
      batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      shop_id TEXT NOT NULL, shop_name TEXT, address TEXT, tag TEXT,
      pay_buyer_value REAL, pay_buyer_range TEXT, transaction_growth TEXT,
      uv_value REAL, uv_range TEXT, traffic_growth TEXT,
      UNIQUE(batch_id, shop_id)
    );
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_item_period ON market_snapshot_items(period_start, period_end, item_id);
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_search_period ON market_snapshot_searches(period_start, period_end, keyword);
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_rival_item_period ON market_snapshot_rival_items(period_start, period_end, item_id);
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_rival_shop_period ON market_snapshot_rival_shops(period_start, period_end, shop_id);
    """)


def import_file(conn, path):
    kind = classify(path.name)
    if not kind:
        return {"file": path.name, "status": "ignored", "rows": 0}
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if conn.execute("SELECT 1 FROM market_snapshot_batches WHERE source_hash=?", (digest,)).fetchone():
        return {"file": path.name, "status": "already_imported", "rows": 0}
    headers, records = read_xlsx(path)
    period_col = "日期"
    start, end = period_bounds(records[0].get(period_col))
    cur = conn.execute(
        "INSERT INTO market_snapshot_batches(snapshot_type,source_filename,source_hash,period_start,period_end,row_count) VALUES(?,?,?,?,?,?)",
        (kind, path.name, digest, start, end, len(records)),
    )
    batch_id = cur.lastrowid
    for row in records:
        if kind == "item":
            conn.execute("INSERT INTO market_snapshot_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                batch_id, start, end, row.get("类目名称"), str(row.get("商品ID") or ""), row.get("商品名称"), row.get("商品链接"),
                row.get("商品关键词"), row.get("店铺名称"), row.get("店铺类型"), midpoint(row.get("访客数")), row.get("访客数"),
                midpoint(row.get("支付买家数")), row.get("支付买家数"), int(midpoint(row.get("行业排名")) or 0), row.get("趋势")))
        elif kind == "search":
            conn.execute("INSERT INTO market_snapshot_searches VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                batch_id, start, end, row.get("分类名称"), str(row.get("搜索词") or ""), midpoint(row.get("搜索人气")), row.get("搜索人气"),
                midpoint(row.get("支付转化率"), True), row.get("支付转化率"), midpoint(row.get("点击率"), True), row.get("点击率"), int(midpoint(row.get("排名")) or 0)))
        elif kind == "rival_item":
            conn.execute("INSERT INTO market_snapshot_rival_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                batch_id, start, end, str(row.get("商品ID") or ""), row.get("商品名称"), row.get("店铺名称"), row.get("标签"),
                midpoint(row.get("支付买家数")), row.get("支付买家数"), row.get("交易增速"), midpoint(row.get("访客数")), row.get("访客数"), row.get("流量增速"), row.get("预计支付金额")))
        else:
            conn.execute("INSERT INTO market_snapshot_rival_shops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                batch_id, start, end, str(row.get("店铺ID") or ""), row.get("店铺名称"), row.get("地址"), row.get("标签"),
                midpoint(row.get("支付买家数")), row.get("支付买家数"), row.get("交易增速"), midpoint(row.get("访客数")), row.get("访客数"), row.get("流量增速")))
    return {"file": path.name, "status": "imported", "rows": len(records), "period_start": start, "period_end": end, "snapshot_type": kind}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--db", default="data/dashboard.db")
    args = parser.parse_args()
    directory = Path(args.directory)
    files = sorted(directory.glob("*.xlsx"))
    conn = sqlite3.connect(args.db)
    try:
        schema(conn)
        result = [import_file(conn, path) for path in files]
        conn.commit()
    finally:
        conn.close()
    print(result)


if __name__ == "__main__":
    main()
