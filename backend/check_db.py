#!/usr/bin/env python3
"""
检查新架构数据库
"""
import os
import sqlite3
from pathlib import Path

print("="*60)
print("新架构数据库检查")
print("="*60)

db_path = Path(__file__).parent / "data" / "db" / "dashboard.db"
print(f"\n📁 数据库路径: {db_path}")

if db_path.exists():
    print(f"✅ 数据库文件存在: {db_path.stat().st_size:,} bytes")
else:
    print(f"❌ 数据库文件不存在！")
    exit(1)

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("\n📋 数据库表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"   - {table_name}: {count} 条记录")

    print("\n📊 检查部分表的详细数据:")

    # 检查 products
    if 'products' in [t[0] for t in tables]:
        cursor.execute("SELECT COUNT(*) FROM products;")
        product_count = cursor.fetchone()[0]
        print(f"   ✅ products: {product_count} 个商品")
        if product_count > 0:
            cursor.execute("SELECT id, product_id, title, category FROM products LIMIT 3;")
            sample = cursor.fetchall()
            for item in sample:
                print(f"      - {item[1]}: {item[2]}")

    # 检查 monthly_data
    if 'monthly_data' in [t[0] for t in tables]:
        cursor.execute("SELECT COUNT(*) FROM monthly_data;")
        monthly_count = cursor.fetchone()[0]
        print(f"   ✅ monthly_data: {monthly_count} 条月度数据")
        if monthly_count > 0:
            cursor.execute("SELECT DISTINCT month FROM monthly_data LIMIT 3;")
            months = cursor.fetchall()
            print(f"      月份: {', '.join([m[0] for m in months])}")

    conn.close()
    print("\n✅ 数据库检查完成！")

except Exception as e:
    print(f"❌ 数据库错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("新架构准备就绪！")
print("="*60)
