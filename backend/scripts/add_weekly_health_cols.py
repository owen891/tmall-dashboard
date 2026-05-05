import sqlite3

conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db')
cursor = conn.cursor()

cols_to_add = [
    ('weekly_data', 'visitors', 'INTEGER'),
    ('weekly_data', 'cart_count', 'INTEGER'),
    ('weekly_data', 'new_customers', 'INTEGER'),
    ('weekly_data', 'new_customer_cost', 'FLOAT'),
    ('weekly_data', 'direct_cart_cost', 'FLOAT'),
    ('weekly_data', 'total_cart_cost', 'FLOAT'),
    ('weekly_data', 'search_ctr', 'FLOAT'),
]

for table, col, col_type in cols_to_add:
    try:
        sql = f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
        cursor.execute(sql)
        print(f"✓ {table}.{col}")
    except Exception as e:
        print(f"  - {table}.{col} 已存在或错误: {e}")

conn.commit()
print("\n完成!")
conn.close()
