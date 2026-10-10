# -*- coding: utf-8 -*-
"""一键导出（生意参谋市场）快照导入器 —— tmall-dashboard 导入链路的一部分。

与 ``import_market_snapshot_exports.py`` 同源同表，但适配 2026-10 起的
「一键导出-市场-…」文件名与列结构：

  一键导出-市场-市场排行-商品-月-…    → market_snapshot_items   (类型 item_month)
  一键导出-市场-市场排行-店铺-上月-…  → market_snapshot_shop_rank(类型 shop_month)
  一键导出-市场-搜索排行-…-周-…       → market_snapshot_searches(类型 search_words)
  一键导出-市场-竞争监控-竞品列表      → market_snapshot_rival_items  (类型 rival_item)
  一键导出-市场-竞争监控-竞店列表      → market_snapshot_rival_shops  (类型 rival_shop)

设计约束（与主库质量体系一致）：
* **幂等**：按文件 sha256 去重，重复导入只报 already_imported。
* **区间值保留原文 + 同时落中位值**：生意参谋是区间脱敏（"10万 ~ 25万"），
  中位值仅用于横向比较，原始区间一并存表，禁止据此推算精确 GMV/客单价。
* **不造数**：搜索周榜的搜索人数/点击率/支付转化率在导出中为空 → 落 NULL，
  不填 0；空导出的竞争监控文件整表跳过并记入报告，不生成空批次。

用法：
  python scripts/import_market_oneclick_exports.py --directory <解压目录> \
      --db data/dashboard.db [--dry-run] [--report data/market_import_report.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def period_bounds(value):
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", str(value or ""))
    if len(dates) == 1:
        return dates[0], dates[0]
    if len(dates) == 2:
        return dates[0], dates[1]
    raise ValueError(f"invalid period: {value}")


def midpoint(value, percentage=False):
    """区间 → 中位值。如 "7500 ~ 1万" = (7500+10000)/2。端点各自带单位。"""
    text = str(value or "").strip().replace(",", "")
    if not text or text in {"-", "--", "None"}:
        return None
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


# 判定"这行到底有没有数据"的载荷列：占位行的元信息列（栏目/菜单/维度/导出时间）非空，
# 但载荷列全空 —— 生意参谋空导出就是这个形态，不能当数据行。
PAYLOAD_COLS = ("商品ID", "商品名称", "店铺名称", "店铺ID", "搜索词")


def _blank(v):
    return v in (None, "", "None", "nan")


def read_xlsx(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    headers = [str(v).strip() if v is not None else "" for v in rows[0]]
    records = []
    for row in rows[1:]:
        rec = dict(zip(headers, row))
        payload = [rec.get(c) for c in PAYLOAD_COLS if c in headers]
        if payload and all(_blank(v) for v in payload):
            continue                      # 占位行
        if all(_blank(v) for v in rec.values()):
            continue                      # 全空行
        records.append(rec)
    return headers, records


def classify(name):
    """文件名 → 快照类型。顺序敏感：商品/店铺必须早于 搜索/竞争监控 判断。"""
    if "市场排行-商品" in name:
        return "item_month"
    if "市场排行-店铺" in name:
        return "shop_month"
    if "搜索排行" in name:
        return "search_words"
    if "竞品列表" in name:
        return "rival_item"
    if "竞店列表" in name:
        return "rival_shop"
    return None


def period_of(records, headers):
    for col in ("日期范围", "日期", "维度"):
        if col in headers and records and records[0].get(col):
            try:
                return period_bounds(records[0][col])
            except ValueError:
                continue
    raise ValueError("no period column found")


SHOP_RANK_DDL = """
CREATE TABLE IF NOT EXISTS market_snapshot_shop_rank (
  batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
  cate_name TEXT, shop_name TEXT NOT NULL, shop_url TEXT, shop_type TEXT,
  uv_value REAL, uv_range TEXT, pay_buyer_value REAL, pay_buyer_range TEXT,
  on_sale_count INTEGER, rank INTEGER, trend TEXT,
  UNIQUE(batch_id, shop_name)
);
CREATE INDEX IF NOT EXISTS idx_market_snapshot_shop_rank_period
  ON market_snapshot_shop_rank(period_start, period_end, shop_name);
"""


def ensure_schema(conn):
    from scripts.import_market_snapshot_exports import schema as base_schema
    base_schema(conn)
    conn.executescript(SHOP_RANK_DDL)
    # 主图列：基础表结构没有「商品图片链接」列，导致商品主图一直丢（看板硬要求带主图）。
    # 加列是追加式的，不动既有列，历史批次的 pic_url 为 NULL（重导可补）。
    cols = [c[1] for c in conn.execute("PRAGMA table_info(market_snapshot_items)")]
    if "pic_url" not in cols:
        conn.execute("ALTER TABLE market_snapshot_items ADD COLUMN pic_url TEXT")


CHILD_TABLES = ("market_snapshot_items", "market_snapshot_searches",
                "market_snapshot_shop_rank", "market_snapshot_rival_items",
                "market_snapshot_rival_shops")


def drop_batch(conn, digest):
    row = conn.execute("SELECT id FROM market_snapshot_batches WHERE source_hash=?",
                       (digest,)).fetchone()
    if not row:
        return False
    bid = row[0]
    for t in CHILD_TABLES:
        conn.execute(f"DELETE FROM {t} WHERE batch_id=?", (bid,))
    conn.execute("DELETE FROM market_snapshot_batches WHERE id=?", (bid,))
    return True


def import_file(conn, path, dry_run=False, force=False):
    kind = classify(path.name)
    if not kind:
        return {"file": path.name, "status": "ignored_unknown_type", "rows": 0}
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if conn.execute("SELECT 1 FROM market_snapshot_batches WHERE source_hash=?", (digest,)).fetchone():
        if not force:
            return {"file": path.name, "status": "already_imported", "rows": 0}
        if not dry_run:
            drop_batch(conn, digest)
    headers, records = read_xlsx(path)
    if not records:
        return {"file": path.name, "status": "skipped_empty_export", "rows": 0,
                "note": "导出文件只有表头/占位行（生意参谋未带数据），不生成空批次"}
    start, end = period_of(records, headers)
    if dry_run:
        return {"file": path.name, "status": "dry_run", "rows": len(records),
                "snapshot_type": kind, "period": f"{start}~{end}"}

    cur = conn.execute(
        "INSERT INTO market_snapshot_batches(snapshot_type,source_filename,source_hash,"
        "period_start,period_end,row_count) VALUES(?,?,?,?,?,?)",
        (kind, path.name, digest, start, end, len(records)))
    bid = cur.lastrowid

    if kind == "item_month":
        for r in records:
            conn.execute(
                "INSERT OR REPLACE INTO market_snapshot_items"
                "(batch_id,period_start,period_end,cate_name,item_id,title,product_url,"
                " core_keyword,shop_name,shop_type,uv_value,uv_range,pay_buyer_value,"
                " pay_buyer_range,rank,trend,pic_url)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    bid, start, end, r.get("类目名称"), str(r.get("商品ID") or ""),
                    r.get("商品名称"), r.get("商品链接"), r.get("商品关键词"),
                    r.get("店铺名称"), r.get("店铺类型"),
                    midpoint(r.get("访客数")), r.get("访客数"),
                    midpoint(r.get("支付买家数")), r.get("支付买家数"),
                    int(midpoint(r.get("行业排名")) or 0), r.get("趋势"),
                    r.get("商品图片链接")))
    elif kind == "shop_month":
        for r in records:
            conn.execute("INSERT OR REPLACE INTO market_snapshot_shop_rank VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                bid, start, end, r.get("类目名称"), str(r.get("店铺名称") or ""), r.get("店铺链接"),
                r.get("店铺类型"), midpoint(r.get("访客数")), r.get("访客数"),
                midpoint(r.get("支付买家数")), r.get("支付买家数"),
                int(midpoint(r.get("在售商品数量")) or 0) or None,
                int(midpoint(r.get("行业排名")) or 0), r.get("趋势")))
    elif kind == "search_words":
        for r in records:
            # 搜索人数/点击率/支付转化率/排名 在周榜导出中为空 → 落 NULL（不填 0）
            conn.execute("INSERT OR REPLACE INTO market_snapshot_searches VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                bid, start, end, r.get("分类名称") or r.get("类目"), str(r.get("搜索词") or ""),
                midpoint(r.get("搜索人数")), r.get("搜索人数"),
                midpoint(r.get("支付转化率"), True), r.get("支付转化率"),
                midpoint(r.get("点击率"), True), r.get("点击率"),
                int(midpoint(r.get("排名")) or 0)))
    elif kind == "rival_item":
        for r in records:
            conn.execute("INSERT OR REPLACE INTO market_snapshot_rival_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                bid, start, end, str(r.get("商品ID") or ""), r.get("商品名称"), r.get("店铺名称"),
                r.get("标签"), midpoint(r.get("支付买家数")), r.get("支付买家数"),
                r.get("交易增速"), midpoint(r.get("访客数")), r.get("访客数"),
                r.get("流量增速"), r.get("预计支付金额")))
    else:  # rival_shop
        for r in records:
            conn.execute("INSERT OR REPLACE INTO market_snapshot_rival_shops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                bid, start, end, str(r.get("店铺ID") or r.get("店铺名称") or ""), r.get("店铺名称"),
                r.get("所在地"), r.get("标签"), midpoint(r.get("支付买家数")), r.get("支付买家数"),
                r.get("交易增速"), midpoint(r.get("访客数")), r.get("访客数"), r.get("流量增速")))
    return {"file": path.name, "status": "imported", "rows": len(records),
            "snapshot_type": kind, "batch_id": bid, "period": f"{start}~{end}"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    default_db = str(Path(__file__).resolve().parent.parent / "data" / "dashboard.db")
    parser.add_argument("--db", default=os.environ.get("TMALL_DB_PATH", default_db))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="已导入过的文件也重导（先删旧批次，用于补列/纠错）")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    files = sorted(Path(args.directory).glob("*.xlsx"))
    conn = sqlite3.connect(args.db)
    try:
        ensure_schema(conn)
        results = [import_file(conn, p, args.dry_run, args.force) for p in files]
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    summary = {}
    for r in results:
        summary.setdefault(r["status"], []).append(r)
    print(json.dumps({
        "directory": args.directory, "files": len(files), "dry_run": args.dry_run,
        "by_status": {k: len(v) for k, v in summary.items()},
        "imported_rows": sum(r.get("rows", 0) for r in summary.get("imported", [])),
        "empty_exports": [r["file"] for r in summary.get("skipped_empty_export", [])],
    }, ensure_ascii=False, indent=1))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump({"ran_at": datetime.now().isoformat(timespec="seconds"),
                       "database": args.db, "results": results}, fh, ensure_ascii=False, indent=1)
        print("report:", args.report)


if __name__ == "__main__":
    main()
