import sqlite3
import os

# Use absolute path
db_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db'

if not os.path.exists(db_path):
    print(f"数据库文件不存在: {db_path}")
    # Try alternative path
    alt_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\dashboard.db'
    if os.path.exists(alt_path):
        db_path = alt_path
        print(f"使用备用路径: {db_path}")
    else:
        print("数据库文件不存在，尝试创建...")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f"\n数据库路径: {db_path}")
print(f"\n数据库表 ({len(tables)} 个):")
for t in sorted(tables):
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count} 条")
    except:
        print(f"  {t}: (无法查询)")
conn.close()
