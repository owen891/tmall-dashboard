"""查 source_batch_id 对应导入来源 + collector_data_staging 最近记录。"""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== collector_data_staging 表结构 ===")
for c in conn.execute("PRAGMA table_info(collector_data_staging)").fetchall():
    print(f"  {c['name']:30s} {c['type']}")

print()
print("=== 9-19 product 级记录的 source_batch_id 分布 ===")
rows = conn.execute(
    """
    SELECT source_batch_id, COUNT(*) cnt
    FROM promotion_daily_facts
    WHERE date='2026-09-19'
    GROUP BY source_batch_id
    """
).fetchall()
for r in rows:
    print(f"  batch={r['source_batch_id']}  rows={r['cnt']}")

print()
print("=== 最近的 collector_data_staging 记录（按 rowid desc 10条）===")
try:
    rows = conn.execute(
        "SELECT * FROM collector_data_staging ORDER BY rowid DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 100:
                d[k] = v[:100] + '...'
        print(d)
        print('---')
except Exception as e:
    print("err:", e)

print()
print("=== 最近的 import_staging_rows 记录（看导入来源）===")
try:
    rows = conn.execute(
        "SELECT * FROM import_staging_rows ORDER BY rowid DESC LIMIT 5"
    ).fetchall()
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 100:
                d[k] = v[:100] + '...'
        print(d)
        print('---')
except Exception as e:
    print("err:", e)
