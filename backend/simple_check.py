#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单检查数据库 - 仅依赖sqlite3标准库
"""
import sqlite3
import os
from pathlib import Path

print("="*60)
print("新架构数据库检查")
print("="*60)

db_path = Path(__file__).parent / "data" / "db" / "dashboard.db"
print(f"\n📁 数据库路径: {db_path}")

if not db_path.exists():
    print(f"❌ 数据库文件不存在！")
    print(f"   尝试从 legacy 数据库复制...")
    legacy_db = Path(__file__).parent.parent / "legacy" / "data" / "dashboard.db"
    if legacy_db.exists():
        import shutil
        print(f"✅ 找到 legacy 数据库！正在复制...")
        os.makedirs(db_path.parent, exist_ok=True)
        shutil.copy2(legacy_db, db_path)
        print(f"✅ 数据库已复制到新架构！")
    else:
        print(f"❌ 找不到任何数据库！")
        exit(1)

print(f"✅ 数据库文件: {db_path.stat().st_size:,} 字节")

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("\n📋 数据库中的表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("   ⚠️ 数据库是空的！")
    else:
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"   - {table_name}: {count} 条记录")

    conn.close()

    print("\n" + "="*60)
    print("✅ 新架构准备就绪！")
    print("="*60)
    print("\n📋 在你的Python环境中运行:")
    print("1. 后端启动:")
    print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\backend")
    print("   pip install -r requirements.txt")
    print("   python run.py")
    print("\n2. 前端启动:")
    print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\frontend")
    print("   npm install")
    print("   npm run dev")
    print("\n3. 访问:")
    print("   后端: http://localhost:8000")
    print("   前端: http://localhost:5173")
    print("="*60)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
