"""检查最近所有数据源的采集运行记录和数据新鲜度。"""
import sqlite3
import os
import sys
from pathlib import Path
from datetime import date, timedelta

DB = Path(os.environ.get('TMALL_DB_PATH') or (Path(__file__).resolve().parents[2] / 'data' / 'dashboard.db'))
if len(sys.argv) > 1:
    DB = Path(sys.argv[1])
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== 最近 3 天各 source 的采集运行 ===")
rows = conn.execute(
    """
    SELECT id, source_key, status, started_at, finished_at,
           error_code,
           substr(error_message,1,120) err,
           stats_json
    FROM collector_runs
    WHERE started_at >= datetime('now', '-3 days')
    ORDER BY started_at DESC
    """
).fetchall()
for r in rows:
    d = dict(r)
    print(f"  {d['started_at'][:19]}  {d['source_key']:16s}  {d['status']:10s}  err={d['err'] or ''}")

print()
print("=== 各数据源最新数据日期（freshness）===")
queries = [
    ("sycm_flow", "sycm_flow_source_daily", "stat_date"),
    ("sycm_item_flow", "sycm_item_flow_source_daily", "stat_date"),
    ("sycm_market_kw", "sycm_market_search_rank", "stat_date"),
    ("promotion", "promotion_daily_facts", "date"),
    ("daily_data(BI)", "daily_data", "date"),
]
for label, table, col in queries:
    try:
        r = conn.execute(f"SELECT MAX({col}) latest, COUNT(*) cnt FROM {table}").fetchone()
        print(f"  {label:20s}  latest={r['latest']}  total_rows={r['cnt']}")
    except Exception as e:
        print(f"  {label:20s}  ERR: {e}")

print()
print("=== collector_checkpoints 最近失败的 unit（24h内）===")
rows = conn.execute(
    """
    SELECT run_id, unit_type, unit_key, status, last_error_message, updated_at
    FROM collector_checkpoints
    WHERE status IN ('failed','blocked')
      AND julianday(updated_at) >= julianday('now', '-1 day')
    ORDER BY julianday(updated_at) DESC LIMIT 20
    """
).fetchall()
for r in rows:
    print(f"  {r['updated_at'][:19]}  {r['unit_type']}:{r['unit_key']}  {r['status']}  err={r['last_error_message']}")
if not rows:
    print("  (无)")
