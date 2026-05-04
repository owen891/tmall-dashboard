#!/usr/bin/env python3
"""
新架构 - 快速启动指南
"""
import sys
import os

print("="*60)
print("海贝海数据仪表盘 2.0 - 快速开始")
print("="*60)

print("\n📁 当前目录:", os.getcwd())

# 检查依赖
try:
    import fastapi
    print("✅ FastAPI 已安装")
except ImportError:
    print("❌ FastAPI 未安装，请运行: pip install -r requirements.txt")

try:
    import pandas
    print("✅ pandas 已安装")
except ImportError:
    print("❌ pandas 未安装，请运行: pip install -r requirements.txt")

# 检查数据库
db_path = os.path.join(os.path.dirname(__file__), "data", "db", "dashboard.db")
if os.path.exists(db_path):
    print(f"✅ 数据库已存在: {db_path}")
else:
    print(f"⚠️ 数据库不存在，会自动创建: {db_path}")

print("\n" + "="*60)
print("🚀 启动方式:")
print("="*60)
print("1. 后端启动:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\backend")
print("   python run.py")
print()
print("2. 前端启动:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\frontend")
print("   npm install")
print("   npm run dev")
print()
print("3. 导入数据:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\backend")
print("   python import_raw_data.py")
print("="*60)

print("\n📋 数据库表预览:")
try:
    from app.core.database import Base, engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    for table in sorted(tables):
        print(f"   - {table}")
except Exception as e:
    print(f"   ⚠️ 无法连接数据库: {e}")

print("\n✅ 检查完成！按回车键退出...")
input()
