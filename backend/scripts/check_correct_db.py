import sqlite3

db_path = r"F:\ai\.accelerate\tmall-dashboard\backend\data\dashboard.db"
conn = sqlite3.connect(db_path)

print("weekly_data表结构:")
cursor = conn.execute("PRAGMA table_info(weekly_data)")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

conn.close()
