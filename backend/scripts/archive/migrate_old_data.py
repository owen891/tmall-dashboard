#!/usr/bin/env python3
"""
Migrate data from old system to new database
"""
import sqlite3
import os
from datetime import datetime
from app.core.database import engine, Base, SessionLocal
from app.models import Product, WeeklyData

def get_row_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError):
        return default

def migrate_from_old_db():
    old_db_path = "../legacy/data/dashboard.db"
    
    if not os.path.exists(old_db_path):
        print(f"旧数据库不存在: {old_db_path}")
        return
    
    print("创建数据库表...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        print("连接旧数据库...")
        old_conn = sqlite3.connect(old_db_path)
        old_conn.row_factory = sqlite3.Row
        old_cursor = old_conn.cursor()
        
        print("开始迁移商品数据...")
        old_cursor.execute("SELECT * FROM products")
        old_products = old_cursor.fetchall()
        
        product_count = 0
        for row in old_products:
            product_id = row['product_id']
            existing = db.query(Product).filter(Product.product_id == product_id).first()
            
            if not existing:
                product = Product(
                    product_id=product_id,
                    title=row['title'],
                    category=row['category'],
                    tier=row['tier'],
                    style=row['style'],
                    scene=row['scene'],
                    list_date=row['list_date'],
                    status=get_row_value(row, 'status', 'active'),
                    remark=get_row_value(row, 'remark'),
                    image_url=get_row_value(row, 'image_url'),
                    manager=get_row_value(row, 'manager'),
                    starred=bool(get_row_value(row, 'starred', False)),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(product)
                product_count += 1
                if product_count % 100 == 0:
                    print(f"已迁移 {product_count} 个商品...")
        
        db.commit()
        print(f"✅ 成功迁移 {product_count} 个商品！")
        
        print("开始迁移历史数据...")
        data_count = 0
        
        for table_name in ['weekly_data', 'monthly_data', 'daily_data']:
            try:
                old_cursor.execute(f"SELECT * FROM {table_name}")
                old_data = old_cursor.fetchall()
                
                for row in old_data:
                    product_id = get_row_value(row, 'product_id')
                    
                    if not product_id:
                        continue
                    
                    week_start = get_row_value(row, 'week_start') or get_row_value(row, 'date')
                    if not week_start:
                        week_start = datetime.now().date()
                    
                    existing = db.query(WeeklyData).filter(
                        WeeklyData.product_id == product_id,
                        WeeklyData.week_start == week_start
                    ).first()
                    
                    if not existing:
                        week_data = WeeklyData(
                            product_id=product_id,
                            week_start=week_start,
                            payment_amount=get_row_value(row, 'payment_amount', 0) or 0,
                            refund_amount=get_row_value(row, 'refund_amount', 0) or 0,
                            net_sales=get_row_value(row, 'net_sales', 0) or 0,
                            gsv_change=get_row_value(row, 'gsv_change', 0) or 0,
                            ad_spend=get_row_value(row, 'ad_spend', 0) or 0,
                            ad_spend_change=get_row_value(row, 'ad_spend_change', 0) or 0,
                            total_roi=get_row_value(row, 'total_roi', 0) or 0,
                            direct_roi=get_row_value(row, 'direct_roi', 0) or 0,
                            direct_roi_change=get_row_value(row, 'direct_roi_change', 0) or 0,
                            refund_ad_ratio=get_row_value(row, 'refund_ad_ratio', 0) or 0,
                            visitors=get_row_value(row, 'visitors', 0) or 0,
                            uv_value=get_row_value(row, 'uv_value', 0) or 0,
                            payment_conversion=get_row_value(row, 'payment_conversion', 0) or 0,
                            refund_rate=get_row_value(row, 'refund_rate', 0) or 0,
                            cart_rate=get_row_value(row, 'cart_rate', 0) or 0,
                            cart_qty=get_row_value(row, 'cart_qty', 0) or 0,
                            payment_users=get_row_value(row, 'payment_users', 0) or 0,
                            avg_order_value=get_row_value(row, 'avg_order_value', 0) or 0,
                            lead_potential_ratio=get_row_value(row, 'lead_potential_ratio', 0) or 0,
                            new_customer_cost=get_row_value(row, 'new_customer_cost', 0) or 0,
                            direct_cart_cost=get_row_value(row, 'direct_cart_cost', 0) or 0,
                            total_cart_cost=get_row_value(row, 'total_cart_cost', 0) or 0,
                            repurchase_rate=get_row_value(row, 'repurchase_rate', 0) or 0,
                            cross_sell_rate=get_row_value(row, 'cross_sell_rate', 0) or 0,
                            category_width=get_row_value(row, 'category_width', 0) or 0,
                            click_rate=get_row_value(row, 'click_rate', 0) or 0,
                            data_source=table_name,
                            imported_at=datetime.now()
                        )
                        db.add(week_data)
                        data_count += 1
                        if data_count % 100 == 0:
                            print(f"已迁移 {data_count} 条历史数据...")
                
                db.commit()
            except Exception as e:
                print(f"跳过表 {table_name}: {e}")
                continue
        
        print(f"✅ 成功迁移 {data_count} 条历史数据！")
        print("\n🎉 数据迁移全部完成！")
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        old_conn.close()
        db.close()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    migrate_from_old_db()
