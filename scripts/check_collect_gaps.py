#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读检查采集分区（业务日期）是否完整，输出缺口清单（JSON）。

用途：供 scripts/catchup_collect.ps1 判断「该补哪些源、补哪个日期」。

严格只读：sqlite 以 mode=ro 打开，只做 SELECT / PRAGMA。

分区完整性口径（2026-10-23 修订）
--------------------------------
旧实现除 sycm_market_item_rank 外一律「当天 ≥1 行即视为已采」，于是一次部分失败
也能通过验收。生产实例：2026-10-22 的 promotion_daily_facts 只有 239 行（该源
正常区间 872~1123），旧检查器判为「已采」，缺口被隐藏。现在一个分区要通过三层：

1. presence      该日期有行（旧行为）。
2. population    行数不低于**绝对下限**，且不低于该源自身近期基线的容忍比例。
                 相对基线而非写死阈值：各源行数本身在 872~1123 间正常波动。
3. fields        required_fields 全部非空 —— 直接复用 API 侧权威实现
                 ``services.collector_run_service.verify_fact_dates``，避免两套口径。

任一层不通过即记为该源缺口，并在输出里写明是哪一层、实际值与判据。

退出码：
  0  检查完成（无论有没有缺口）
  2  数据库打不开 / 查询异常
  3  检出未完整分区（仅在 --fail-on-gap 时）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 脚本从 scripts/ 目录被调用时，项目根不在 sys.path，services.* 无法导入。
# 字段级验收要复用 services.collector_run_service，这里显式补上。
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 表 -> (日期列, 采集来源, 必需字段, 绝对行数下限)
#
# 必需字段与 api/collect_api.py 的 COLLECTOR_CATALOG[key]['fields'] 一致；
# tests/test_collection_pipeline_architecture.py 会断言两边不漂移。
# 绝对下限只用于「基本没采到」的兜底，判断「采了但只采了一半」靠基线比例。
TABLE_SPECS = [
    ("daily_data", "date", "bi_daily",
     ("product_id", "date", "payment_amount"), 1),
    ("sycm_flow_source_daily", "stat_date", "sycm_flow",
     ("stat_date", "channel_name", "uv", "pay_amount"), 1),
    ("sycm_item_flow_source_daily", "stat_date", "sycm_item_flow",
     ("stat_date", "item_id", "channel_name", "uv"), 1),
    ("sycm_market_item_rank", "stat_date", "sycm_market",
     ("stat_date", "cate_id", "item_id", "rank"), 1500),
    ("promotion_daily_facts", "date", "wanxiangtai",
     ("date", "channel", "ad_spend", "clicks"), 1),
]

# 派生表：依赖 daily_data，单独判断是否需要重跑汇总
DERIVED_SPECS = [
    ("store_daily_facts", "date", "aggregate", ("date", "payment_amount"), 1),
]

# 基线回看天数：取该日期之前 N 天的中位数作为「正常产量」参照。
BASELINE_DAYS = 14
# 相对基线的最低容忍比例。0.5 能抓住 10-22 那次 239/900≈0.27 的部分失败，
# 又不会因为某天少采几十行而误报。
DEFAULT_MIN_BASELINE_RATIO = 0.5


def default_db_path(project_root: str) -> str:
    env = os.environ.get("TMALL_DB_PATH")
    if env:
        return env
    return os.path.join(project_root, "data", "dashboard.db")


def _table_columns(conn: sqlite3.Connection, table: str) -> set:
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    except sqlite3.Error:
        return set()


def count_rows(conn: sqlite3.Connection, table: str, date_col: str, day: str) -> int:
    sql = f'SELECT COUNT(*) FROM "{table}" WHERE "{date_col}" = ?'
    try:
        return int(conn.execute(sql, (day,)).fetchone()[0])
    except sqlite3.Error:
        # 表不存在 / 列名不符：按 0 处理，交由上层报缺口
        return 0


def baseline_median(conn: sqlite3.Connection, table: str, date_col: str,
                    day: str, lookback_days: int = BASELINE_DAYS):
    """该日期**之前** lookback_days 天内每日行数的中位数；样本不足返回 None。

    用中位数而不是均值：个别天的异常高峰不应该抬高「正常产量」的门槛。
    """
    try:
        rows = conn.execute(
            f'''SELECT "{date_col}" AS d, COUNT(*) AS n FROM "{table}"
                WHERE "{date_col}" >= date(?, '-{int(lookback_days)} days')
                  AND "{date_col}" < ?
                GROUP BY "{date_col}"''',
            (day, day),
        ).fetchall()
    except sqlite3.Error:
        return None
    counts = sorted(int(row[1]) for row in rows)
    if len(counts) < 3:
        # 样本太少（新源 / 刚断档很久）→ 不做比例判断，避免误报
        return None
    middle = len(counts) // 2
    if len(counts) % 2:
        return counts[middle]
    return (counts[middle - 1] + counts[middle]) / 2.0


def check_partition(conn: sqlite3.Connection, table: str, date_col: str, day: str,
                    required_fields, min_rows: int,
                    min_baseline_ratio: float = DEFAULT_MIN_BASELINE_RATIO):
    """检查单个 (表, 日期) 分区，返回 (完整? , 明细 dict)。"""
    detail = {
        "date": day,
        "rows": 0,
        "min_rows": min_rows,
        "baseline": None,
        "baseline_ratio": None,
        "status": "unknown",
        "reasons": [],
    }

    columns = _table_columns(conn, table)
    if not columns:
        detail["status"] = "unknown"
        detail["reasons"].append("table_missing")
        return False, detail
    if date_col not in columns:
        detail["status"] = "unknown"
        detail["reasons"].append("date_column_missing")
        return False, detail

    rows = count_rows(conn, table, date_col, day)
    detail["rows"] = rows
    if rows == 0:
        detail["status"] = "empty"
        detail["reasons"].append("no_rows")
        return False, detail

    complete = True
    if rows < min_rows:
        complete = False
        detail["reasons"].append("below_absolute_minimum")

    baseline = baseline_median(conn, table, date_col, day)
    if baseline:
        detail["baseline"] = baseline
        detail["baseline_ratio"] = round(rows / baseline, 4)
        if rows < baseline * min_baseline_ratio:
            complete = False
            detail["reasons"].append("below_baseline_ratio")

    # 字段级验收：复用 API 侧权威实现，禁止在这里另写一套。
    try:
        from services.collector_run_service import verify_fact_dates
    except Exception as exc:  # noqa: BLE001 - 导入失败也不能让检查器崩掉
        detail["reasons"].append(f"field_check_unavailable:{exc}")
        detail["status"] = "unknown"
        return False, detail

    acceptance = verify_fact_dates(conn, table, date_col, list(required_fields), [day])
    detail["fields"] = {
        "status": acceptance.get("status"),
        "verified_dates": acceptance.get("verified_dates", []),
        "rejected_dates": acceptance.get("rejected_dates", []),
        "scope": acceptance.get("scope"),
    }
    if acceptance.get("status") != "verified":
        complete = False
        detail["reasons"].append("required_fields_incomplete")

    detail["status"] = "verified" if complete else "partial"
    return complete, detail


def inspect_dates(conn: sqlite3.Connection, dates, min_baseline_ratio: float = DEFAULT_MIN_BASELINE_RATIO):
    """检查这些日期的所有分区，返回结果 dict（不含 db/ok/error 等外层字段）。

    把这段逻辑从 main() 里提出来，是为了让它可以被隔离单测直接调用——
    之前它埋在 CLI 里，只能靠起子进程跑整个 main() 才能验证。
    """
    missing = []
    incomplete = []
    aggregate_dates = []
    tables = {}

    for day in dates:
        for table, date_col, source, required_fields, min_rows in TABLE_SPECS:
            complete, detail = check_partition(
                conn, table, date_col, day, required_fields, min_rows,
                min_baseline_ratio)
            # 多日期模式下按 (表, 日期) 记录；单日期时保持旧结构
            if len(dates) == 1:
                tables[table] = {
                    "rows": detail["rows"],
                    "expected": min_rows,
                    "source": source,
                    **{key: value for key, value in detail.items()
                       if key not in ("rows", "min_rows")},
                }
            else:
                tables.setdefault(table, {
                    "expected": min_rows, "source": source, "partitions": {}})
                tables[table]["partitions"][day] = detail
            if not complete:
                if source not in missing:
                    missing.append(source)
                incomplete.append({
                    "date": day, "source": source, "table": table,
                    "status": detail["status"], "rows": detail["rows"],
                    "baseline": detail["baseline"],
                    "reasons": detail["reasons"],
                })

        for table, date_col, source, required_fields, min_rows in DERIVED_SPECS:
            complete, detail = check_partition(
                conn, table, date_col, day, required_fields, min_rows,
                min_baseline_ratio)
            if len(dates) == 1:
                tables[table] = {
                    "rows": detail["rows"],
                    "expected": min_rows,
                    "source": source,
                    **{key: value for key, value in detail.items()
                       if key not in ("rows", "min_rows")},
                }
            else:
                tables.setdefault(table, {
                    "expected": min_rows, "source": source, "partitions": {}})
                tables[table]["partitions"][day] = detail
            if not complete:
                # 派生表缺这一天 / 值不完整 → 需要（重新）聚合这一天。
                # 但源侧 daily_data 当天没数据时聚合无从下手，交给采集缺口处理，
                # 不要把「BI 没采到」误报成「汇总没跑」。
                source_rows = count_rows(conn, "daily_data", "date", day)
                if source_rows > 0:
                    aggregate_dates.append(day)

    return {
        "tables": tables,
        "missing_sources": missing,
        "incomplete_partitions": incomplete,
        "aggregate_needed": bool(aggregate_dates),
        "aggregate_dates": sorted(set(aggregate_dates)),
    }


def _expand_dates(args) -> list:
    if args.days and args.date:
        raise SystemExit("--days 与 --date 不能同时使用")
    if args.days:
        if args.days < 1:
            raise SystemExit("--days 必须 >= 1")
        anchor = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
        return [(anchor - dt.timedelta(days=offset)).isoformat()
                for offset in range(args.days, 0, -1)]
    dates = []
    for value in args.date:
        for part in str(value).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                dates.append(dt.date.fromisoformat(part).isoformat())
            except ValueError:
                raise SystemExit(f"无效日期（需 YYYY-MM-DD）: {part}")
    seen, ordered = set(), []
    for day in dates:
        if day not in seen:
            seen.add(day)
            ordered.append(day)
    return ordered


def main() -> int:
    parser = argparse.ArgumentParser(description="只读检查采集分区完整性")
    parser.add_argument("--date", action="append", default=None,
                        help="检查的日期 YYYY-MM-DD，可重复或逗号分隔")
    parser.add_argument("--days", type=int, default=None,
                        help="检查截至 --as-of（默认今天）的最近 N 天")
    parser.add_argument("--as-of", default=None, help="--days 的锚点日期，默认今天")
    parser.add_argument("--db", default="", help="数据库路径，默认 data/dashboard.db")
    parser.add_argument("--min-baseline-ratio", type=float,
                        default=DEFAULT_MIN_BASELINE_RATIO,
                        help="行数相对近期基线的最低比例，默认 0.5")
    parser.add_argument("--fail-on-gap", action="store_true",
                        help="检出未完整分区时以退出码 3 结束")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        dates = _expand_dates(args)
    except SystemExit:
        raise
    if not dates:
        parser.error("必须提供 --date 或 --days")

    project_root = PROJECT_ROOT
    db_path = args.db or default_db_path(project_root)

    result = {
        "ok": False,
        "date": dates[0],
        "dates": dates,
        "db": db_path,
        "tables": {},
        "missing_sources": [],
        "aggregate_needed": False,
        "aggregate_dates": [],
        "incomplete_partitions": [],
        "error": None,
    }

    if not os.path.exists(db_path):
        result["error"] = f"数据库不存在: {db_path}"
        print(json.dumps(result, ensure_ascii=False) if args.json else result["error"])
        return 2

    try:
        uri = "file:" + db_path.replace("\\", "/") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=30)
        # verify_fact_dates 按列名取值（row['total']），必须是 Row。
        # 之前这里设成 None，字段验收会静默降级为 unknown 而全部判缺口。
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
    except sqlite3.Error as exc:
        result["error"] = f"打开数据库失败: {exc}"
        print(json.dumps(result, ensure_ascii=False) if args.json else result["error"])
        return 2

    try:
        result.update(inspect_dates(conn, dates, args.min_baseline_ratio))
        result["ok"] = True
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"分区完整性检查（{db_path}）")
        for day in dates:
            print(f"  日期 {day}")
            for table, info in result["tables"].items():
                if "partitions" in info:
                    detail = info["partitions"].get(day, {})
                else:
                    detail = info
                rows = detail.get("rows", 0)
                flag = "OK " if detail.get("status") == "verified" else "缺口"
                ratio = detail.get("baseline_ratio")
                ratio_text = f" 基线比={ratio}" if ratio is not None else ""
                print(f"    [{flag}] {table:<32} rows={rows:<6} 期望>={info['expected']}"
                      f"{ratio_text} 来源={info['source']}"
                      f"{' 原因=' + ','.join(detail.get('reasons', [])) if detail.get('reasons') else ''}")
        if result["missing_sources"]:
            print("需补采来源: " + ", ".join(result["missing_sources"]))
        else:
            print("需补采来源: 无")
        print("需重跑汇总: " + ("是 " + ", ".join(result["aggregate_dates"])
                                if result["aggregate_needed"] else "否"))

    if args.fail_on_gap and (result["missing_sources"] or result["aggregate_needed"]):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
