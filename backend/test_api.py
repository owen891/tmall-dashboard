#!/usr/bin/env python3
"""
简单的API测试脚本
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import SessionLocal
from app.models import Product
from app.services import ProductService
from datetime import datetime

def test_database():
    print("1. 测试数据库连接...")
    db = SessionLocal()
    
    # 查询商品数量
    count = db.query(Product).count()
    print(f"   当前数据库有 {count} 个商品")
    
    db.close()
    print("   ✅ 数据库连接正常！\n")
    return True

def test_product_service():
    print("2. 测试 ProductService...")
    db = SessionLocal()
    service = ProductService(db)
    
    # 获取过滤器选项
    options = {
        "categories": service.get_categories(),
        "tiers": service.get_tiers(),
        "styles": service.get_styles(),
        "scenes": service.get_scenes()
    }
    print(f"   分类数量: {len(options['categories'])}")
    print(f"   层级数量: {len(options['tiers'])}")
    print(f"   风格数量: {len(options['styles'])}")
    print(f"   场景数量: {len(options['scenes'])}")
    
    db.close()
    print("   ✅ ProductService 正常！\n")
    return True

if __name__ == "__main__":
    print("=" * 40)
    print("系统测试")
    print("=" * 40)
    try:
        test_database()
        test_product_service()
        print("🎉 所有测试通过！")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
