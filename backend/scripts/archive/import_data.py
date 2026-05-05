#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据导入脚本 - 从原始数据文件导入到数据库
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models import Product, DailyData, WeeklyData, MonthlyData


DATA_DIR = r'F:\bi\海贝海\原始数据'


def clean_str(val):
    if pd.isna(val) or val in ['', 'None', 'nan', 'NaN', '-']:
        return None
    try:
        if isinstance(val, (int, float)):
            return str(int(val))
        return str(val).strip()
    except:
        return str(val).strip()


def clean_int(val):
    if pd.isna(val) or val in ['', 'None', 'nan', 'NaN', '-', '--']:
        return 0
    try:
        return int(float(str(val).replace(',', '').replace('%', '')))
    except:
        return 0


def clean_float(val):
    if pd.isna(val) or val in ['', 'None', 'nan', 'NaN', '-', '--']:
        return 0.0
    try:
        s = str(val).replace(',', '').replace('¥', '').replace('%', '').strip()
        return float(s)
    except:
        return 0.0


def excel_date_to_str(val):
    """Excel序列号转日期字符串"""
    if pd.isna(val):
        return None
    try:
        if isinstance(val, (int, float)):
            base = datetime(1899, 12, 30)
            d = base + timedelta(days=int(val))
            return d.strftime('%Y-%m-%d')
        elif isinstance(val, datetime):
            return val.strftime('%Y-%m-%d')
        elif isinstance(val, str):
            if len(val) == 10 and '-' in val:
                return val
            elif len(val) == 8:
                return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
        return None
    except:
        return None


def get_week_start(date_str):
    """获取日期所在周的周一"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        monday = d - timedelta(days=d.weekday())
        return monday.strftime('%Y-%m-%d')
    except:
        return None


def get_month(date_str):
    """获取日期所在月份"""
    try:
        return date_str[:7]
    except:
        return None


def import_sycm_products(filepath, db):
    """导入生意参谋商品数据"""
    print(f"  处理: {os.path.basename(filepath)}")
    
    try:
        df = pd.read_excel(filepath, header=4)
    except Exception as e:
        print(f"  ❌ 打开文件失败: {e}")
        return 0
    
    total = 0
    debug_count = 0
    
    for _, row in df.iterrows():
        try:
            pid = clean_str(row.get('商品ID'))
            if not pid:
                continue
            
            date_val = clean_str(row.get('统计日期'))
            if not date_val:
                continue
            
            if len(date_val) == 10 and '-' in date_val:
                pass
            elif len(date_val) == 8:
                date_val = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
            else:
                continue
            
            gmv = clean_float(row.get('支付金额'))
            refund = clean_float(row.get('成功退款金额'))
            visitors = clean_int(row.get('商品访客数'))
            pv = clean_int(row.get('商品浏览量'))
            conv = clean_float(row.get('商品支付转化率'))
            cart = clean_int(row.get('商品加购件数'))
            fav = clean_int(row.get('商品收藏人数'))
            title = clean_str(row.get('商品名称'))
            
            if debug_count < 3:
                print(f"    调试: pid={pid}, date={date_val}, gmv={gmv}")
                debug_count += 1
            
            product = db.query(Product).filter(Product.product_id == pid).first()
            if not product:
                product = Product(product_id=pid, title=title, status='active')
                db.add(product)
            elif title and not product.title:
                product.title = title
            
            week_start = get_week_start(date_val)
            month = get_month(date_val)
            
            daily = db.query(DailyData).filter(
                DailyData.product_id == pid,
                DailyData.date == date_val
            ).first()
            
            if not daily:
                daily = DailyData(
                    product_id=pid,
                    date=date_val,
                    payment_amount=gmv,
                    refund_amount=refund,
                    ipv=visitors,
                    pv=pv,
                    payment_conversion=conv / 100 if conv > 1 else conv,
                    cart_count=cart,
                    fav_count=fav
                )
                db.add(daily)
                total += 1
            
            if week_start:
                weekly = db.query(WeeklyData).filter(
                    WeeklyData.product_id == pid,
                    WeeklyData.week_start == week_start
                ).first()
                
                if not weekly:
                    weekly = WeeklyData(
                        product_id=pid,
                        week_start=week_start,
                        payment_amount=gmv,
                        refund_amount=refund,
                        ipv=visitors,
                        pv=pv,
                        payment_conversion=conv / 100 if conv > 1 else conv,
                        cart_count=cart,
                        fav_count=fav
                    )
                    db.add(weekly)
            
            if month:
                monthly = db.query(MonthlyData).filter(
                    MonthlyData.product_id == pid,
                    MonthlyData.month == month
                ).first()
                
                if not monthly:
                    monthly = MonthlyData(
                        product_id=pid,
                        month=month,
                        payment_amount=gmv,
                        refund_amount=refund,
                        ipv=visitors,
                        pv=pv,
                        payment_conversion=conv / 100 if conv > 1 else conv,
                        cart_count=cart,
                        fav_count=fav
                    )
                    db.add(monthly)
            
        except Exception as e:
            print(f"    错误: {e}")
            continue
    
    db.commit()
    print(f"  ✅ 导入 {total} 条记录")
    return total


def import_smart_selection(filepath, db):
    """导入智能选款数据"""
    print(f"  处理: {os.path.basename(filepath)}")
    
    try:
        df = pd.read_excel(filepath, header=0)
    except Exception as e:
        print(f"  ❌ 打开文件失败: {e}")
        return 0
    
    total = 0
    
    for _, row in df.iterrows():
        try:
            pid = clean_str(row.get('商品ID'))
            if not pid:
                continue
            
            date_val = excel_date_to_str(row.get('日期'))
            if not date_val:
                continue
            
            gmv = clean_float(row.get('支付金额'))
            refund = clean_float(row.get('退款金额'))
            visitors = clean_int(row.get('访客数'))
            conv = clean_float(row.get('支付转化率'))
            cart = clean_int(row.get('加购件数'))
            fav = clean_int(row.get('收藏人数'))
            title = clean_str(row.get('商品标题'))
            ad_spend = clean_float(row.get('总推广花费'))
            roi = clean_float(row.get('推广直接ROI'))
            
            product = db.query(Product).filter(Product.product_id == pid).first()
            if not product:
                product = Product(product_id=pid, title=title, status='active')
                db.add(product)
            elif title and not product.title:
                product.title = title
            
            week_start = get_week_start(date_val)
            month = get_month(date_val)
            
            daily = db.query(DailyData).filter(
                DailyData.product_id == pid,
                DailyData.date == date_val
            ).first()
            
            if not daily:
                daily = DailyData(
                    product_id=pid,
                    date=date_val,
                    payment_amount=gmv,
                    refund_amount=refund,
                    ipv=visitors,
                    payment_conversion=conv / 100 if conv > 1 else conv,
                    cart_count=cart,
                    fav_count=fav,
                    ad_spend=ad_spend,
                    ad_roi=roi
                )
                db.add(daily)
                total += 1
            
            if week_start:
                weekly = db.query(WeeklyData).filter(
                    WeeklyData.product_id == pid,
                    WeeklyData.week_start == week_start
                ).first()
                
                if not weekly:
                    weekly = WeeklyData(
                        product_id=pid,
                        week_start=week_start,
                        payment_amount=gmv,
                        refund_amount=refund,
                        ipv=visitors,
                        payment_conversion=conv / 100 if conv > 1 else conv,
                        cart_count=cart,
                        fav_count=fav,
                        ad_spend=ad_spend,
                        ad_roi=roi
                    )
                    db.add(weekly)
            
            if month:
                monthly = db.query(MonthlyData).filter(
                    MonthlyData.product_id == pid,
                    MonthlyData.month == month
                ).first()
                
                if not monthly:
                    monthly = MonthlyData(
                        product_id=pid,
                        month=month,
                        payment_amount=gmv,
                        refund_amount=refund,
                        ipv=visitors,
                        payment_conversion=conv / 100 if conv > 1 else conv,
                        cart_count=cart,
                        fav_count=fav,
                        ad_spend=ad_spend,
                        ad_roi=roi
                    )
                    db.add(monthly)
            
        except Exception as e:
            continue
    
    db.commit()
    print(f"  ✅ 导入 {total} 条记录")
    return total


def main():
    print("=" * 60)
    print("数据导入脚本")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        files = os.listdir(DATA_DIR)
        
        sycm_files = [f for f in files if '生意参谋' in f and '商品' in f and f.endswith('.xls')]
        smart_files = [f for f in files if '智能选款' in f and f.endswith('.xlsx') and not f.startswith('~$')]
        
        print(f"\n找到 {len(sycm_files)} 个生意参谋商品文件")
        print(f"找到 {len(smart_files)} 个智能选款文件")
        
        total_imported = 0
        
        print("\n" + "=" * 60)
        print("导入生意参谋商品数据")
        print("=" * 60)
        
        for f in sorted(sycm_files):
            filepath = os.path.join(DATA_DIR, f)
            try:
                imported = import_sycm_products(filepath, db)
                total_imported += imported
            except Exception as e:
                print(f"  处理失败: {e}")
                db.rollback()
        
        print("\n" + "=" * 60)
        print("导入智能选款数据")
        print("=" * 60)
        
        for f in sorted(smart_files):
            filepath = os.path.join(DATA_DIR, f)
            try:
                imported = import_smart_selection(filepath, db)
                total_imported += imported
            except Exception as e:
                print(f"  处理失败: {e}")
                db.rollback()
        
        print("\n" + "=" * 60)
        print("导入统计")
        print("=" * 60)
        
        product_count = db.query(Product).count()
        daily_count = db.query(DailyData).count()
        weekly_count = db.query(WeeklyData).count()
        monthly_count = db.query(MonthlyData).count()
        
        print(f"  Products: {product_count}")
        print(f"  DailyData: {daily_count}")
        print(f"  WeeklyData: {weekly_count}")
        print(f"  MonthlyData: {monthly_count}")
        print(f"\n总计导入: {total_imported} 条记录")
        
    finally:
        db.close()
    
    print("\n导入完成")


if __name__ == '__main__':
    main()
