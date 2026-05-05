import sqlite3

db_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db'
conn = sqlite3.connect(db_path)

print("weekly_data表结构:")
cursor = conn.execute("PRAGMA table_info(weekly_data)")
cols = cursor.fetchall()
for col in cols:
    print(f"  {col[1]} ({col[2]})")

conn.close()
