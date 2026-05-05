import sqlite3

conn = sqlite3.connect('f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db')
cursor = conn.cursor()

# Check all distinct week_start dates
print('=== 所有 period 数据量 ===')
cursor.execute('''
SELECT week_start, COUNT(*) as cnt, SUM(payment_amount) as total_payment
FROM weekly_data
GROUP BY week_start
ORDER BY week_start DESC
''')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} rows, payment={row[2]}')

# Check if 2026-04-27 exists
print('\n=== 检查 2026-04-27 ===')
cursor.execute("SELECT COUNT(*) FROM weekly_data WHERE week_start = '2026-04-27'")
print(f'2026-04-27 记录数: {cursor.fetchone()[0]}')

cursor.execute("SELECT SUM(payment_amount), SUM(visitors), SUM(ad_spend) FROM weekly_data WHERE week_start = '2026-04-27'")
row = cursor.fetchone()
print(f'2026-04-27 汇总: payment={row[0]}, visitors={row[1]}, ad_spend={row[2]}')

# Check if 2026-05-03 exists
print('\n=== 检查 2026-05-03 ===')
cursor.execute("SELECT SUM(payment_amount), SUM(visitors), SUM(ad_spend) FROM weekly_data WHERE week_start = '2026-05-03'")
row = cursor.fetchone()
print(f'2026-05-03 汇总: payment={row[0]}, visitors={row[1]}, ad_spend={row[2]}')

conn.close()
