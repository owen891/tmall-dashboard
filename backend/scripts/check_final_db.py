import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
conn = sqlite3.connect(db_path)

print("weekly_data表结构 (data/db/dashboard.db):")
cursor = conn.execute("PRAGMA table_info(weekly_data)")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

count = conn.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
print(f"\n数据记录: {count} 条")

# Check if ipv column exists
has_ipv = any(row[1] == 'ipv' for row in conn.execute("PRAGMA table_info(weekly_data)").fetchall())
print(f"\n有ipv列: {has_ipv}")

if has_ipv:
    ipv_count = conn.execute("SELECT COUNT(*) FROM weekly_data WHERE ipv > 0").fetchone()[0]
    print(f"ipv>0的记录: {ipv_count} 条")

conn.close()
