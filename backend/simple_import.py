#!/usr/bin/env python3
"""
简单导入真实数据
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date, datetime
from app.core import SessionLocal
from app.models import Product, WeeklyData

def safe_float(val, default=0.0):
    if pd.isna(val):
        return default
    if val == '-':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    if pd.isna(val):
        return default
    if val == '-':
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def main():
    print("简单导入真实数据...")
    file_path = "/workspace/legacy/data/raw/828e389b-d3e5-416c-9b24-5235f39417b0_海贝海-数据分析表-周.xlsx"
    
    print(f"读取 Excel: {file_path}")
    df = pd.read_excel(file_path, sheet_name="单品-新", header=0)
    
    db = SessionLocal()
    
    product_count = 0
    data_count =0
    
    for _, row in df.iterrows():
        product_id_val = row.get("商品ID")
        if pd.isna(product_id_val):
            continue
        
        product_id = str(product_id_val)
        
        # 1. 处理商品
        existing_product = db.query(Product).filter(Product.product_id == product_id).first()
        
        product_data = {
            "product_id": product_id,
            "title": str(row.get("商品标题", "")),
            "category": str(row.get("商品类目", "")),
            "tier": str(row.get("分层", "")),
            "style": str(row.get("风格", "")),
            "scene": str(row.get("场景", "")),
            "image_url": str(row.get("图片链接", "")),
        }
        
        list_date = row.get("上架时间")
        if pd.notna(list_date):
            try:
                if isinstance(list_date, datetime):
                    product_data["list_date"] = list_date.date()
                else:
                    product_data["list_date"] = pd.to_datetime(list_date).date()
            except Exception:
                pass
        
        if existing_product:
            # 更新
            for key, value in product_data.items():
                if key != "product_id" and value is not None:
                    setattr(existing_product, key, value)
            existing_product.updated_at = datetime.now()
        else:
            # 新建
            new_product = Product(**product_data)
            db.add(new_product)
        
        product_count += 1
        
        # 2. 处理周数据
        week_start_date = date(2026, 4, 20)
        
        existing_week = db.query(WeeklyData).filter(
            WeeklyData.product_id == product_id,
            WeeklyData.week_start == week_start_date
        ).first()
        
        week_data_dict = {
            "product_id": product_id,
            "week_start": week_start_date,
            "payment_amount": safe_float(row.get("支付金额")),
            "refund_amount": safe_float(row.get("退款金额")),
            "net_sales": safe_float(row.get("净销售/GSV")),
            "gsv_change": safe_float(row.get("GSV环比")),
            "ad_spend": safe_float(row.get("总推广花费")),
            "total_roi": safe_float(row.get("总投产")),
            "direct_roi": safe_float(row.get("推广直接ROI")),
            "refund_ad_ratio": safe_float(row.get("退款付费占比")),
            "visitors": safe_int(row.get("访客数")),
            "uv_value": safe_float(row.get("UV价值")),
            "payment_conversion": safe_float(row.get("支付转化率")),
            "refund_rate": safe_float(row.get("退款率")),
            "cart_rate": safe_float(row.get("加购率")),
            "cart_qty": safe_int(row.get("加购件数")),
            "payment_users": safe_int(row.get("支付人数")),
            "avg_order_value": safe_float(row.get("客单价")),
            "lead_potential_ratio": safe_float(row.get("引潜比")),
            "new_customer_cost": safe_float(row.get("拉新成本")),
            "direct_cart_cost": safe_float(row.get("直接加购成本")),
            "total_cart_cost": safe_float(row.get("总加购成本")),
            "repurchase_rate": safe_float(row.get("复购率")),
            "cross_sell_rate": safe_float(row.get("连带率")),
            "category_width": safe_int(row.get("叶子类目宽度")),
            "click_rate": safe_float(row.get("点击率")),
            "data_source": "excel_import",
        }
        
        if existing_week:
            for key, value in week_data_dict.items():
                if key not in ["product_id", "week_start"]:
                    setattr(existing_week, key, value)
        else:
            new_week_data = WeeklyData(**week_data_dict)
            db.add(new_week_data)
        
        data_count +=1
        
        if product_count % 100 == 0:
            print(f"已处理 {product_count} 个商品...")
            db.commit()
    
    db.commit()
    db.close()
    
    print("=" * 40)
    print(f"✅ 导入完成!")
    print(f"总商品: {product_count}")
    print(f"总数据: {data_count}")
    print("=" *40)

if __name__ == "__main__":
    main()
