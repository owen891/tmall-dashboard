import sqlite3

conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(weekly_data)")
cols = {row[1]: row[2] for row in cursor.fetchall()}

needed_cols = ['cart_count', 'search_visitors', 'new_customers', 'new_customer_cost', 
               'direct_cart_cost', 'total_cart_cost', 'repurchase_rate', 'cross_sell_rate', 'search_ctr']

missing = [c for c in needed_cols if c not in cols]
print(f"缺失的健康度字段: {missing}")

if missing:
    for col in missing:
        col_type = 'FLOAT'
        if 'count' in col or 'visitors' in col or 'customers' in col:
            col_type = 'INTEGER'
        sql = f"ALTER TABLE weekly_data ADD COLUMN {col} {col_type}"
        cursor.execute(sql)
        print(f"✓ 添加 {col} {col_type}")
    conn.commit()
    print("字段添加完成!")

conn.close()
