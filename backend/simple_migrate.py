#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单直接的数据库迁移 - 复制老架构数据库到新架构
"""
import shutil
import os
from pathlib import Path

print("="*60)
print("新架构数据库迁移")
print("="*60)

# 源数据库（老架构）
legacy_db = Path(__file__).parent.parent / "legacy" / "data" / "dashboard.db"
# 目标数据库（新架构）
target_db = Path(__file__).parent / "data" / "db" / "dashboard.db"

print(f"\n📁 源数据库: {legacy_db}")
print(f"📁 目标数据库: {target_db}")

if not legacy_db.exists():
    print(f"\n❌ 找不到源数据库！")
    exit(1)

print(f"\n✅ 源数据库存在: {legacy_db.stat().st_size:,} 字节")

# 创建目标目录
target_db.parent.mkdir(parents=True, exist_ok=True)

# 复制数据库
print(f"\n📋 正在复制数据库...")
try:
    shutil.copy2(legacy_db, target_db)
    print(f"✅ 数据库已复制！")
    print(f"   目标: {target_db}")
    print(f"   大小: {target_db.stat().st_size:,} 字节")
except Exception as e:
    print(f"❌ 复制失败: {e}")
    exit(1)

print("\n" + "="*60)
print("✅ 新架构数据库准备就绪！")
print("="*60)
print("\n📋 接下来:")
print("1. 在你的Python环境中运行:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\backend")
print("   pip install -r requirements.txt")
print("   python run.py")
print("\n2. 访问:")
print("   后端API: http://localhost:8000")
print("   API文档: http://localhost:8000/docs")
print("\n3. 前端启动:")
print("   cd f:\\ai\\.accelerate\\tmall-dashboard\\frontend")
print("   npm install")
print("   npm run dev")
print("="*60)
