import sqlite3

conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db')
cursor = conn.cursor()

# Check table schema
print('=== weekly_data 表结构 ===')
cursor.execute('PRAGMA table_info(weekly_data)')
columns = cursor.fetchall()
for col in columns:
    print(f'  {col[1]} ({col[2]})')

# Find the date column name
date_col = None
for col in columns:
    if 'date' in col[1].lower() or 'period' in col[1].lower() or 'week' in col[1].lower():
        date_col = col[1]
        break

if date_col:
    print(f'\n=== 使用日期列: {date_col} ===')
    
    # Check for negative values in calculations
    print('\n=== 检查负数计算结果 ===')
    cursor.execute(f'''
    SELECT product_id, {date_col}, payment_amount, visitors, ad_spend, payment_conversion 
    FROM weekly_data 
    ORDER BY {date_col} DESC
    LIMIT 10
    ''')
    for row in cursor.fetchall():
        print(row)
    
    # Get latest period
    cursor.execute(f'SELECT DISTINCT {date_col} FROM weekly_data ORDER BY {date_col} DESC LIMIT 5')
    periods = cursor.fetchall()
    print(f'\n=== 最近5个周期 ===')
    for p in periods:
        print(p[0])
    
    if len(periods) >= 2:
        curr_period = periods[0][0]
        prev_period = periods[1][0]
        
        print(f'\n=== {curr_period} 汇总 ===')
        cursor.execute(f'''
        SELECT SUM(payment_amount), SUM(visitors), SUM(ad_spend), AVG(payment_conversion)
        FROM weekly_data WHERE {date_col} = '{curr_period}'
        ''')
        curr = cursor.fetchone()
        print(f'payment={curr[0]}, visitors={curr[1]}, ad_spend={curr[2]}, conversion={curr[3]}')
        
        print(f'\n=== {prev_period} 汇总 ===')
        cursor.execute(f'''
        SELECT SUM(payment_amount), SUM(visitors), SUM(ad_spend), AVG(payment_conversion)
        FROM weekly_data WHERE {date_col} = '{prev_period}'
        ''')
        prev = cursor.fetchone()
        print(f'payment={prev[0]}, visitors={prev[1]}, ad_spend={prev[2]}, conversion={prev[3]}')

conn.close()
