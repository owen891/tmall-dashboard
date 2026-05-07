#!/usr/bin/env python3
"""
Generate sample data for preview
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.core.database import SessionLocal, engine, Base
from app.models import Product, DailyData, WeeklyData, MonthlyData
import random

def generate_sample_data():
    session = SessionLocal()
    
    try:
        # Create sample products
        categories = ['家居饰品/摆件类/装饰摆件', '收纳整理/家庭收纳用具/收纳箱', '家居装饰/装饰画/现代简约']
        tiers = ['引流款', '利润款', '普通款']
        styles = ['现代简约', '中式古典', '欧式风格']
        
        products = []
        for i in range(10):
            product = Product(
                product_id=f"P{i:05d}",
                title=f"精品商品{i+1}",
                category=random.choice(categories),
                tier=random.choice(tiers),
                style=random.choice(styles),
                list_date="2026-01-01",
                status="active",
                score=random.randint(60, 100),
                repurchase_rate=random.uniform(0.05, 0.25),
                cross_sell_rate=random.uniform(0.1, 0.4)
            )
            products.append(product)
            session.add(product)
        
        # Create sample daily data for last 30 days
        base_date = datetime.now() - timedelta(days=30)
        for i in range(30):
            current_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            
            for product in products:
                visitors = random.randint(100, 1000)
                payment_amount = random.uniform(500, 5000)
                ad_spend = random.uniform(50, 300) if random.random() > 0.3 else 0
                
                daily = DailyData(
                    product_id=product.product_id,
                    date=current_date,
                    payment_amount=payment_amount,
                    refund_amount=payment_amount * random.uniform(0, 0.1),
                    net_sales=payment_amount * (1 - random.uniform(0, 0.1)),
                    ad_spend=ad_spend,
                    ad_roi=payment_amount / ad_spend if ad_spend > 0 else 0,
                    direct_roi=payment_amount / ad_spend * 0.8 if ad_spend > 0 else 0,
                    total_roi=payment_amount / ad_spend * 1.2 if ad_spend > 0 else 0,
                    visitors=visitors,
                    ipv=visitors,
                    pv=visitors * random.randint(2, 5),
                    payment_conversion=random.uniform(0.01, 0.05),
                    cart_rate=random.uniform(0.05, 0.15),
                    fav_rate=random.uniform(0.03, 0.1),
                    bounce_rate=random.uniform(0.4, 0.7),
                    avg_stay_duration=random.uniform(60, 180),
                    buyers=int(visitors * random.uniform(0.01, 0.05)),
                    avg_order_value=random.uniform(50, 200),
                    payment_qty=random.randint(10, 50),
                    cart_qty=random.randint(20, 100),
                    fav_users=random.randint(5, 50),
                    impressions=random.randint(1000, 10000),
                    clicks=random.randint(50, 500),
                    ctr=random.uniform(0.02, 0.08),
                    data_source="sample"
                )
                session.add(daily)
        
        session.commit()
        print(f"✅ Generated sample data:")
        print(f"   - Products: {len(products)}")
        print(f"   - Daily records: {len(products) * 30}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    generate_sample_data()
