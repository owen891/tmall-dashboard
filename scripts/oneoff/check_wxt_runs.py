"""查 collector_runs 表结构和最近万相台运行记录。"""
import sqlite3
from pathlib import Path

DB = Path(r"E:\www\tmall-dashboard\data\dashboard.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== collector_runs 表结构 ===")
cols = conn.execute("PRAGMA table_info(collector_runs)").fetchall()
for c in cols:
    print(c['name'], c['type'])

print()
print("=== 最近 10 次 wanxiangtai 运行 ===")
rows = conn.execute(
    """
    SELECT * FROM collector_runs
    WHERE source_key = 'wanxiangtai'
    ORDER BY started_at DESC LIMIT 10
    """
).fetchall()
for r in rows:
    d = dict(r)
    # 截断长字段
    for k, v in list(d.items()):
        if isinstance(v, str) and len(v) > 150:
            d[k] = v[:150] + '...'
    print(d)
    print('---')
