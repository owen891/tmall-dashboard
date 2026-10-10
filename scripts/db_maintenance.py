"""Read-only database growth report with explicit, safe retention previews.

The command never deletes rows and never runs VACUUM.  It reports the rows
that *would* be eligible for a future archive, plus integrity and index-plan
signals, so an operator can review a manifest before any destructive change.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta, timezone, datetime
from pathlib import Path


DEFAULT_TABLES = {
    "collector_data_staging": ("published_at", 14),
    "collector_artifacts": ("created_at", 30),
    "collector_checkpoints": ("updated_at", 30),
    "monthly_source_payload": ("month", 180),
    "bi_product_daily_raw": ("date", 180),
}

# 与执行器 enforce_retention.TABLE_SPECS 的 extra_where 保持**逐字一致**：
# 预览器若漏掉该过滤，会把不该被清理的行（如未发布的 staging）也算进
# eligible_count，于是预览数字大于执行器实际会删的行数——运维据此误判。
# 2026-10-08：当前库里 collector_data_staging 全部是 published，差异被掩盖；
# 一旦出现非 published 的超期行就会暴露。这里显式对齐，避免再次漂移。
ROW_FILTERS = {
    "collector_data_staging": "status = 'published'",
}

# 执行器**能真正处置**的 mode（见 enforce_retention 的 mode 分支）。
# `compact` 在 enforce_retention 中明确未实现（模块 docstring：
# 「compact / retain not implemented here」），dry-run 会报
# `unsupported_mode:compact`。预览器若仍照常报 eligible_count，读者会误以为
# 「0 行超期 = 已被妥善管理」，而实际是**策略声明了却无人执行**。
# 这里显式标注可执行性，把「悬空策略」暴露出来而非掩盖。
ENFORCEABLE_MODES = frozenset({"archive", "purge_after_archive"})


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _column_has_time(conn, table: str, column: str) -> bool:
    """True when the column stores timestamps rather than pure dates.

    2026-10-08：cutoff 格式必须匹配列的存储格式，否则字符串比较错一天：
    时间戳列用纯日期 cutoff 会漏掉截止日当天（永不清理）；纯日期列用时间戳
    cutoff 会把边界当天的行**提前**判为超期。两个方向相反，故按实际取值探测。

    取 ``MAX(LENGTH(...))`` 而非单行 ``LIMIT 1``：单行取样对混合格式列依赖
    扫描顺序（先命中纯日期即误判），结果不确定；最大值只要列中出现过时间戳
    就判定为时间戳列，与行序无关。
    """
    try:
        row = conn.execute(
            f'SELECT MAX(LENGTH("{column}")) FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL'
        ).fetchone()
    except sqlite3.Error:
        return False
    if not row or row[0] is None:
        return False
    try:
        return int(row[0]) > 10
    except (TypeError, ValueError):
        return False


def _cutoff(column: str, days: int, *, has_time: bool = True) -> str:
    """Retention cutoff used by the read-only preview.

    2026-10-08 修复：日期列此前一律返回纯日期 ``YYYY-MM-DD``，而 eligible 判定是
    SQL 字符串比较 ``"<column>" < ?``。带时分秒的真实数据（如
    ``'2026-09-24 01:30:28'``）与纯日期截止值 ``'2026-09-24'`` 比较时被判为
    **不小于**，于是**截止日当天全部行被漏报**——本预览器与执行器
    ``enforce_retention`` 因此对同一张表给出相反结论（实测 0 vs 8316）。

    ``has_time`` 由调用方按列的真实取值探测传入：时间戳列用带时分秒的 cutoff，
    纯日期列（如 ``bi_product_daily_raw.date``）保持纯日期，避免把边界当天的行
    提前判为超期。``month`` 列仍是月份粒度，保持 ``YYYY-MM``。
    """
    if column == "month":
        return (date.today().replace(day=1) - timedelta(days=days)).isoformat()[:7]
    if has_time:
        return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    return (date.today() - timedelta(days=days)).isoformat()


def build_report(database: str | Path, retention_days: dict[str, int] | None = None) -> dict:
    path = Path(database).resolve()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {}
        retention_days = retention_days or {}
        configured = {}
        if _table_exists(conn, "retention_policies"):
            for row in conn.execute(
                "SELECT source_table, retention_days, mode, protected "
                "FROM retention_policies"
            ):
                configured[row[0]] = {
                    "retention_days": int(row[1]),
                    "mode": row[2],
                    "protected": bool(row[3]),
                }
        table_specs = {}
        for table, (column, default_days) in DEFAULT_TABLES.items():
            policy = configured.get(table, {})
            table_specs[table] = (
                column,
                int(retention_days.get(
                    table, policy.get("retention_days", default_days)
                )),
                policy,
            )
        for table, (column, default_days, policy) in table_specs.items():
            mode = policy.get("mode", "archive")
            item = {"exists": _table_exists(conn, table), "table": table,
                    "column": column, "retention_days": default_days,
                    "mode": mode,
                    "protected": policy.get("protected", False),
                    "policy_source": "database" if table in configured else "default",
                    # 该策略能否被 enforce_retention 真正执行；False 表示
                    # 「声明了但无执行器」（如 compact），eligible_count 仅供参考。
                    "enforceable": mode in ENFORCEABLE_MODES}
            if not item["exists"]:
                tables[table] = item
                continue
            cutoff = _cutoff(
                column, item["retention_days"],
                has_time=_column_has_time(conn, table, column),
            )
            item["cutoff"] = cutoff
            item["row_count"] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            # 与执行器同款行过滤（见 ROW_FILTERS 注释）：漏掉会把不该清理的行
            # 也算进 eligible_count，导致预览数字大于执行器实际删除数。
            row_filter = ROW_FILTERS.get(table)
            where = f'"{column}" < ?'
            if row_filter:
                where += f' AND {row_filter}'
            item["eligible_count"] = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE {where}', (cutoff,)
            ).fetchone()[0]
            if row_filter:
                item["row_filter"] = row_filter
            item["min_value"], item["max_value"] = conn.execute(
                f'SELECT MIN("{column}"), MAX("{column}") FROM "{table}"'
            ).fetchone()
            tables[table] = item

        archive_catalog = {"exists": _table_exists(conn, "archive_catalog")}
        if archive_catalog["exists"]:
            archive_catalog["row_count"] = conn.execute(
                "SELECT COUNT(*) FROM archive_catalog"
            ).fetchone()[0]
            archive_catalog["verified_count"] = conn.execute(
                "SELECT COUNT(*) FROM archive_catalog WHERE status = 'verified'"
            ).fetchone()[0]

        plans = {
            "daily_observation_latest": conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM daily_data_observations "
                "WHERE shop_id=? AND product_id=? AND date=? "
                "ORDER BY observed_at DESC, id DESC LIMIT 1",
                ("default", "__probe__", "1970-01-01"),
            ).fetchall() if _table_exists(conn, "daily_data_observations") else [],
            "daily_scope_date": conn.execute(
                "EXPLAIN QUERY PLAN SELECT product_id FROM daily_data "
                "WHERE shop_id=? AND date BETWEEN ? AND ?",
                ("default", "1970-01-01", "1970-01-02"),
            ).fetchall() if _table_exists(conn, "daily_data") else [],
        }
        return {
            "manifest_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": str(path),
            "dry_run": True,
            "integrity_check": conn.execute("PRAGMA quick_check").fetchone()[0],
            "tables": tables,
            "archive_catalog": archive_catalog,
            "query_plans": {
                key: [row[3] for row in rows] for key, rows in plans.items()
            },
            "policy": {
                "mutations_performed": False,
                "protected_tables": ["daily_data_observations", "fact_field_lineage"],
                "vacuum_performed": False,
                "delete_performed": False,
            },
        }
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a read-only SQLite growth report")
    parser.add_argument("--database", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = build_report(args.database)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
