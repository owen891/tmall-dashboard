"""深挖 bi_daily 凌晨失败原因 + 任务计划配置 + 数据新鲜度。"""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== collector_runs 表结构（找时间列名）===")
for c in conn.execute("PRAGMA table_info(collector_checkpoints)").fetchall():
    print(" ", c['name'], c['type'])

print()
print("=== 最近 24h 失败的 checkpoints ===")
rows = conn.execute(
    """
    SELECT run_id, unit_type, unit_key, status, last_error_message
    FROM collector_checkpoints
    WHERE status IN ('failed','blocked')
      AND rowid > (SELECT MAX(rowid)-500 FROM collector_checkpoints)
    ORDER BY rowid DESC LIMIT 20
    """
).fetchall()
for r in rows:
    print(f"  {r['unit_type']}:{r['unit_key']}  {r['status']}  err={(r['last_error_message'] or '')[:100]}")

print()
print("=== bi_daily 最近 5 次运行详情 ===")
rows = conn.execute(
    """
    SELECT id, status, started_at, finished_at, error_code,
           substr(error_message,1,200) err, stats_json
    FROM collector_runs
    WHERE source_key='bi_daily'
    ORDER BY started_at DESC LIMIT 5
    """
).fetchall()
for r in rows:
    print(f"  {r['started_at'][:19]}  {r['status']}  err={r['err'] or ''}")
    if r['stats_json']:
        print(f"    stats: {r['stats_json'][:200]}")

print()
print("=== daily_data 最近 5 天 ===")
rows = conn.execute(
    """
    SELECT date, COUNT(*) cnt FROM daily_data
    WHERE date >= '2026-09-15'
    GROUP BY date ORDER BY date DESC
    """
).fetchall()
for r in rows:
    print(f"  {r['date']}  rows={r['cnt']}")

print()
print("=== bi_monthly 最新 ===")
r = conn.execute("SELECT MAX(month) latest FROM monthly_data").fetchone()
print("  monthly_data latest month:", r['latest'])
