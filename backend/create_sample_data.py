#!/usr/bin/env python3
"""
创建示例数据
"""
import sys
import os
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import SessionLocal
from app.models import Product, WeeklyData

def create_sample_data():
    print("创建示例数据...")
    db = SessionLocal()
    
    # 检查是否已有数据
    existing_count = db.query(Product).count()
    if existing_count > 0:
        print(f"数据库中已有 {existing_count} 个商品，跳过创建。")
        db.close()
        return
    
    # 创建示例商品
    sample_products = [
        Product(
            product_id="1001",
            title="轻奢风格家居装饰摆件",
            category="家居饰品/摆件类/装饰摆件",
            tier="主推款",
            style="轻奢",
            scene="客厅",
            list_date=date(2024, 1, 15),
            status="active",
            manager="张三",
            starred=True,
            image_url="https://img.alicdn.com/bao/uploaded/i1/123456789/O1CN01Test123.jpg"
        ),
        Product(
            product_id="1002",
            title="中古风玄关钥匙收纳",
            category="家居饰品/摆件类/装饰摆件",
            tier="新品",
            style="中古风",
            scene="玄关",
            list_date=date(2024, 3, 20),
            status="active",
            manager="李四",
            image_url="https://img.alicdn.com/bao/uploaded/i2/123456789/O1CN01Test456.jpg"
        ),
        Product(
            product_id="1003",
            title="北欧风格小夜灯床头灯",
            category="家居饰品/摆件类/桌面摆件",
            tier="常规款",
            style="北欧",
            scene="卧室",
            list_date=date(2024, 2, 10),
            status="active",
            manager="王五",
            image_url="https://img.alicdn.com/bao/uploaded/i3/123456789/O1CN01Test789.jpg"
        )
    ]
    
    for product in sample_products:
        db.add(product)
    
    db.commit()
    print(f"✅ 创建了 {len(sample_products)} 个示例商品！")
    
    # 创建示例周数据
    base_date = date(2024, 5, 1)
    sample_data = [
        WeeklyData(
            product_id="1001",
            week_start=base_date,
            payment_amount=50000,
            ad_spend=5000,
            total_roi=10,
            direct_roi=8,
            visitors=1000,
            uv_value=50,
            payment_conversion=0.03,
            refund_rate=0.02
        ),
        WeeklyData(
            product_id="1001",
            week_start=date(2024, 5, 8),
            payment_amount=60000,
            ad_spend=5500,
            total_roi=10.9,
            direct_roi=9,
            visitors=1100,
            uv_value=54.5,
            payment_conversion=0.032,
            refund_rate=0.018
        ),
        WeeklyData(
            product_id="1002",
            week_start=base_date,
            payment_amount=35000,
            ad_spend=4000,
            total_roi=8.75,
            direct_roi=7,
            visitors=800,
            uv_value=43.75,
            payment_conversion=0.028,
            refund_rate=0.022
        ),
        WeeklyData(
            product_id="1003",
            week_start=base_date,
            payment_amount=25000,
            ad_spend=2500,
            total_roi=10,
            direct_roi=8.5,
            visitors=600,
            uv_value=41.67,
            payment_conversion=0.025,
            refund_rate=0.015
        )
    ]
    
    for data in sample_data:
        db.add(data)
    
    db.commit()
    print(f"✅ 创建了 {len(sample_data)} 条示例周数据！")
    
    db.close()
    print("\n🎉 示例数据创建完成！")
    print("可以启动服务查看效果了！")

if __name__ == "__main__":
    create_sample_data()
