"""查 promotion_daily_facts 表结构 + 数据来源线索。"""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== promotion_daily_facts 表结构 ===")
for c in conn.execute("PRAGMA table_info(promotion_daily_facts)").fetchall():
    print(f"  {c['name']:30s} {c['type']}")

print()
print("=== 9-19 这一天的记录，看是否有来源字段线索 ===")
row = conn.execute(
    "SELECT * FROM promotion_daily_facts WHERE date='2026-09-19' AND grain='product' LIMIT 3"
).fetchone()
if row:
    for k in row.keys():
        print(f"  {k}: {row[k]}")

print()
print("=== 有没有其他推广相关表 ===")
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%promot%' OR name LIKE '%wxt%' OR name LIKE '%wanxiang%'"
).fetchall()
for t in tables:
    print(" ", t['name'])

print()
print("=== 看 lineage / provenance 表 ===")
for t in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%lineage%' OR name LIKE '%provenance%' OR name LIKE '%staging%')"
).fetchall():
    print(" ", t['name'])
