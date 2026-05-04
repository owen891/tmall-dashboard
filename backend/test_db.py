#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最简单的数据库测试 - 不需要依赖
"""
import sqlite3
import os
from pathlib import Path

print("="*60)
print("海贝海数据仪表盘 - 新架构数据库检查")
print("="*60)

db_path = Path(__file__).parent / "data" / "db" / "dashboard.db"
print(f"\n📁 数据库路径: {db_path}")

if not db_path.exists():
    print(f"❌ 数据库不存在！")
    exit(1)

print(f"✅ 数据库存在: {db_path.stat().st_size:,} 字节")

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("\n📋 数据库中的表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    if not tables:
        print("   ⚠️ 数据库为空！")
    else:
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   ✅ {table_name}: {count} 条")
            except Exception as e:
                print(f"   ⚠️ {table_name}: 无法查询 ({e})")

    # 检查关键表
    print("\n📊 关键数据检查:")

    if "products" in [t[0] for t in tables]:
        cursor.execute("SELECT COUNT(*) FROM products")
        print(f"   🛒 商品: {cursor.fetchone()[0]} 个")

        cursor.execute("SELECT product_id, title, category FROM products LIMIT 3")
        samples = cursor.fetchall()
        for sample in samples:
            print(f"      - {sample[0]}: {sample[1][:30]}")

    if "monthly_data" in [t[0] for t in tables]:
        cursor.execute("SELECT COUNT(*) FROM monthly_data")
        print(f"   📈 月度数据: {cursor.fetchone()[0]} 条")

        cursor.execute("SELECT DISTINCT month FROM monthly_data LIMIT 3")
        months = cursor.fetchall()
        print(f"      月份: {', '.join([m[0] for m in months])}")

    if "daily_data" in [t[0] for t in tables]:
        cursor.execute("SELECT COUNT(*) FROM daily_data")
        print(f"   📅 日数据: {cursor.fetchone()[0]} 条")

    conn.close()
    print("\n✅ 数据库检查完成！")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("🚀 接下来:")
print("="*60)
print("1. 在你的Python环境中运行:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\backend")
print("   pip install -r requirements.txt")
print("   python run.py")
print("\n2. 访问:")
print("   http://localhost:8000")
print("   http://localhost:8000/docs")
print("="*60)
