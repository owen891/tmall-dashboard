import sqlite3
import os

db_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db'
conn = sqlite3.connect(db_path)

# Check weekly_data structure
print("weekly_data表结构:")
cursor = conn.execute("PRAGMA table_info(weekly_data)")
for col in cursor.fetchall():
    print(f"  {col}")

# Check sample data
print("\nweekly_data前5条数据:")
cursor = conn.execute("SELECT * FROM weekly_data LIMIT 3")
cols = [desc[0] for desc in cursor.description]
print(f"列名: {cols}")
for row in cursor.fetchall():
    print(row)

# Check products table structure
print("\nproducts表结构:")
cursor = conn.execute("PRAGMA table_info(products)")
for col in cursor.fetchall():
    print(f"  {col}")

conn.close()
