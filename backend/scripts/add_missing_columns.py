"""
添加缺失的列到weekly_data表
"""
import sqlite3

db_path = r'F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db'
conn = sqlite3.connect(db_path)

# Get current columns
cursor = conn.execute("PRAGMA table_info(weekly_data)")
existing_cols = set([row[1] for row in cursor.fetchall()])
print("现有列:", existing_cols)

# Columns to add
cols_to_add = [
    ("page_views", "INTEGER", "0"),
    ("search_ratio", "FLOAT", "0"),
    ("impressions", "INTEGER", "0"),
    ("clicks", "INTEGER", "0"),
    ("fav_users", "INTEGER", "0"),
    ("payment_users", "INTEGER", "0"),
]

for col_name, col_type, default in cols_to_add:
    if col_name not in existing_cols:
        try:
            conn.execute(f"ALTER TABLE weekly_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
            print(f"✓ 添加列: {col_name}")
        except Exception as e:
            print(f"✗ 添加列失败 {col_name}: {e}")
    else:
        print(f"- 列已存在: {col_name}")

conn.commit()
conn.close()
print("\n完成！")
