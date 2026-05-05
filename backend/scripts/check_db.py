import sqlite3

conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db')
cursor = conn.cursor()

# Check weekly_data for negative values
print('=== weekly_data 负数数据检查 ===')
cursor.execute('SELECT COUNT(*) FROM weekly_data WHERE payment_amount < 0')
print(f'payment_amount < 0: {cursor.fetchone()[0]} 条')

cursor.execute('SELECT COUNT(*) FROM weekly_data WHERE visitors < 0')
print(f'visitors < 0: {cursor.fetchone()[0]} 条')

cursor.execute('SELECT COUNT(*) FROM weekly_data WHERE ad_spend < 0')
print(f'ad_spend < 0: {cursor.fetchone()[0]} 条')

cursor.execute('SELECT COUNT(*) FROM weekly_data WHERE payment_conversion < 0')
print(f'payment_conversion < 0: {cursor.fetchone()[0]} 条')

# Check the latest period data
print('\n=== 2026-05-04 周期数据 ===')
cursor.execute('''
SELECT product_id, payment_amount, visitors, ad_spend, payment_conversion 
FROM weekly_data 
WHERE period = '2026-05-04' 
ORDER BY payment_amount 
LIMIT 5
''')
for row in cursor.fetchall():
    print(row)

# Check previous period
print('\n=== 2026-04-27 周期数据 ===')
cursor.execute('''
SELECT product_id, payment_amount, visitors, ad_spend, payment_conversion 
FROM weekly_data 
WHERE period = '2026-04-27' 
ORDER BY payment_amount 
LIMIT 5
''')
for row in cursor.fetchall():
    print(row)

# Sum comparison
print('\n=== 汇总对比 ===')
cursor.execute("SELECT SUM(payment_amount), SUM(visitors), SUM(ad_spend), AVG(payment_conversion) FROM weekly_data WHERE period = '2026-05-04'")
curr = cursor.fetchone()
print(f'2026-05-04: payment={curr[0]}, visitors={curr[1]}, ad_spend={curr[2]}, conversion={curr[3]}')

cursor.execute("SELECT SUM(payment_amount), SUM(visitors), SUM(ad_spend), AVG(payment_conversion) FROM weekly_data WHERE period = '2026-04-27'")
prev = cursor.fetchone()
print(f'2026-04-27: payment={prev[0]}, visitors={prev[1]}, ad_spend={prev[2]}, conversion={prev[3]}')

# Check if there are duplicate periods causing negative calculations
print('\n=== 检查重复period数据 ===')
cursor.execute('''
SELECT period, COUNT(*) as cnt 
FROM weekly_data 
GROUP BY period 
ORDER BY cnt DESC 
LIMIT 10
''')
for row in cursor.fetchall():
    print(f'period: {row[0]}, count: {row[1]}')

conn.close()
