#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接检查数据库 - 不需要任何依赖
"""
import sqlite3
from pathlib import Path

print("="*60)
print("海贝海数据仪表盘 - 新架构数据库检查")
print("="*60)

# 检查多个可能的数据库位置
possible_paths = [
    Path(__file__).parent / "data" / "db" / "dashboard.db",
    Path(__file__).parent / "data" / "dashboard.db",
    Path(__file__).parent.parent / "legacy" / "data" / "dashboard.db",
    Path(__file__).parent.parent / "dashboard.db",
]

db_found = None
for path in possible_paths:
    if path.exists():
        print(f"\n✅ 找到数据库: {path}")
        print(f"   大小: {path.stat().st_size:,} 字节")
        db_found = path
        break

if not db_found:
    print("\n❌ 找不到数据库！")
    print("\n可能的位置:")
    for path in possible_paths:
        print(f"   {path}")
    exit(1)

print("\n" + "="*60)
print("连接数据库...")
conn = sqlite3.connect(str(db_found))
cursor = conn.cursor()
print("✅ 连接成功！")

print("\n📋 数据库中的表:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

if not tables:
    print("   ⚠️ 数据库为空！")
else:
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {table_name}: {count} 条记录")
        except Exception as e:
            print(f"   ⚠️ {table_name}: 无法查询 ({e})")

print("\n" + "="*60)
print("关键数据检查:")
print("="*60)

# 检查商品数据
if any("product" in t[0] for t in tables):
    product_table = None
    if "products" in [t[0] for t in tables]:
        product_table = "products"
    elif "products" in [t[0] for t in tables]:
        product_table = "products"
    
    if product_table:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {product_table}")
            count = cursor.fetchone()[0]
            print(f"\n🛒 {product_table}: {count} 件商品")
            
            if count > 0:
                cursor.execute(f"SELECT * FROM {product_table} LIMIT 2")
                rows = cursor.fetchall()
                print(f"\n   示例商品:")
                for row in rows:
                    row_str = [str(x)[:30] for x in row]
                    print(f"      {row_str}")
        except Exception as e:
            print(f"\n⚠️ {product_table}: 无法查询 ({e})")

# 检查月度数据
if "monthly_data" in [t[0] for t in tables]:
    try:
        cursor.execute("SELECT COUNT(*) FROM monthly_data")
        count = cursor.fetchone()[0]
        print(f"\n📈 monthly_data: {count} 条")
        
        if count > 0:
            cursor.execute("SELECT DISTINCT month FROM monthly_data LIMIT 5")
            months = cursor.fetchall()
            print(f"   包含月份: {[m[0] for m in months]}")
            
            cursor.execute("SELECT * FROM monthly_data LIMIT 1")
            sample = cursor.fetchone()
            print(f"   示例数据: {[str(x)[:20] for x in sample]}")
    except Exception as e:
        print(f"\n⚠️ monthly_data: 无法查询 ({e})")

conn.close()
print("\n" + "="*60)
print("✅ 检查完成！")
print("="*60)
print("\n🚀 下一步:")
print("在你的Python环境中运行:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\backend")
print("   pip install -r requirements.txt")
print("   python run.py")
print("\n访问: http://localhost:8000")
print("="*60)
