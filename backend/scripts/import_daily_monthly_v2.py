"""
导入日维度和月维度数据 - 店铺级别聚合数据
"""
import pandas as pd
import sqlite3
import re
import os
from datetime import datetime

DATA_DIR = r"F:\bi\海贝海\原始数据"
DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"


def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val == '' or val == '-':
            return default
        val_str = str(val).replace(',', '').replace('%', '')
        return float(val_str)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        if pd.isna(val) or val == '' or val == '-':
            return default
        val_str = str(val).replace(',', '')
        return int(float(val_str))
    except (ValueError, TypeError):
        return default


def import_daily_data():
    """导入日维度数据"""
    print("=" * 70)
    print("导入日维度数据")
    print("=" * 70)
    
    daily_file = os.path.join(DATA_DIR, "店铺4月_日_20260503_5e79ed5891d064e4161b68a065551ae9.xlsx")
    
    if not os.path.exists(daily_file):
        print("✗ 日维度文件不存在")
        return
    
    print(f"读取文件: {os.path.basename(daily_file)}")
    df = pd.read_excel(daily_file)
    print(f"  数据行数: {len(df)}")
    
    conn = sqlite3.connect(DB_PATH)
    
    # Clear old data
    conn.execute("DELETE FROM daily_data")
    
    inserted = 0
    for _, row in df.iterrows():
        date = str(row.get('统计日期', ''))
        if not date or date == 'nan':
            continue
        
        try:
            dt = pd.to_datetime(date)
            date_str = dt.strftime('%Y-%m-%d')
        except:
            date_str = date
        
        payment_amount = safe_float(row.get('支付金额'))
        visitors = safe_int(row.get('访客数'))
        page_views = safe_int(row.get('浏览量'))
        payment_users = safe_int(row.get('支付买家数'))
        payment_conversion_raw = safe_float(row.get('支付转化率'))
        payment_conversion = payment_conversion_raw / 100 if payment_conversion_raw > 1 else payment_conversion_raw
        ad_spend = safe_float(row.get('全站推广花费')) + safe_float(row.get('关键词推广花费')) + safe_float(row.get('精准人群推广花费'))
        refund_amount = safe_float(row.get('成功退款金额'))
        bounce_rate_raw = safe_float(row.get('跳失率'))
        bounce_rate = bounce_rate_raw / 100 if bounce_rate_raw > 1 else bounce_rate_raw
        
        net_sales = max(0, payment_amount - refund_amount)
        avg_order_value = (payment_amount / payment_users) if payment_users > 0 else 0
        total_roi = (payment_amount / ad_spend) if ad_spend > 0 else 0
        
        # 插入数据 - 使用product_id='store_all'表示店铺级别数据
        try:
            conn.execute("""
                INSERT INTO daily_data (
                    product_id, date, payment_amount, refund_amount, net_sales, ad_spend, 
                    total_roi, visitors, ipv, payment_conversion, page_views, 
                    payment_users, bounce_rate, avg_order_value, avg_stay_duration,
                    data_source, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'store_all', date_str, payment_amount, refund_amount, net_sales, ad_spend,
                total_roi, visitors, visitors, payment_conversion, page_views,
                payment_users, bounce_rate, avg_order_value, safe_float(row.get('平均停留时长')),
                'store_daily', datetime.now().isoformat()
            ))
            inserted += 1
        except Exception as e:
            if inserted < 3:
                print(f"  ✗ 插入失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"✓ 日维度数据导入完成: {inserted} 条记录\n")


def import_monthly_data():
    """导入月维度数据"""
    print("=" * 70)
    print("导入月维度数据")
    print("=" * 70)
    
    monthly_files = [
        ("月汇总.xlsx", None),
        ("智能选款_2026-04-01~2026-04-30.xlsx", "2026-04")
    ]
    
    conn = sqlite3.connect(DB_PATH)
    total_inserted = 0
    
    # Clear old data
    conn.execute("DELETE FROM monthly_data")
    
    for filename, default_month in monthly_files:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"✗ 文件不存在: {filename}")
            continue
        
        print(f"处理: {filename}")
        df = pd.read_excel(filepath)
        file_inserted = 0
        
        for _, row in df.iterrows():
            month = str(row.get('月份', ''))
            if not month or month == 'nan':
                if default_month:
                    month = default_month
                else:
                    continue
            
            # 标准化月份格式
            if '-' in month:
                parts = month.split('-')
                if len(parts) >= 2:
                    month_str = f"{parts[0]}-{parts[1]}"
                else:
                    month_str = month
            else:
                month_str = month
            
            payment_amount = safe_float(row.get('支付金额'))
            visitors = safe_int(row.get('访客数'))
            page_views = safe_int(row.get('浏览量'))
            payment_users = safe_int(row.get('支付人数'))
            payment_conversion_raw = safe_float(row.get('支付转化率'))
            payment_conversion = payment_conversion_raw / 100 if payment_conversion_raw > 1 else payment_conversion_raw
            ad_spend = safe_float(row.get('总推广花费'))
            refund_amount = safe_float(row.get('退款金额'))
            bounce_rate_raw = safe_float(row.get('跳失率'))
            bounce_rate = bounce_rate_raw / 100 if bounce_rate_raw > 1 else bounce_rate_raw
            
            net_sales = max(0, payment_amount - refund_amount)
            avg_order_value = (payment_amount / payment_users) if payment_users > 0 else 0
            total_roi = (payment_amount / ad_spend) if ad_spend > 0 else 0
            
            try:
                conn.execute("""
                    INSERT INTO monthly_data (
                        product_id, month, payment_amount, refund_amount, net_sales, ad_spend,
                        total_roi, visitors, ipv, payment_conversion, page_views,
                        payment_users, bounce_rate, avg_order_value, avg_stay_duration,
                        data_source, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'monthly_all', month_str, payment_amount, refund_amount, net_sales, ad_spend,
                    total_roi, visitors, visitors, payment_conversion, page_views,
                    payment_users, bounce_rate, avg_order_value, safe_float(row.get('平均停留时长')),
                    'monthly_import', datetime.now().isoformat()
                ))
                file_inserted += 1
            except Exception as e:
                if file_inserted < 3:
                    print(f"  ✗ 插入失败: {e}")
        
        conn.commit()
        total_inserted += file_inserted
        print(f"  ✓ 插入 {file_inserted} 条记录\n")
    
    conn.close()
    print(f"✓ 月维度数据导入完成: 总插入 {total_inserted} 条记录\n")


def verify():
    """验证数据"""
    print("=" * 70)
    print("验证数据")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    
    # daily_data
    daily_count = conn.execute("SELECT COUNT(*) FROM daily_data").fetchone()[0]
    print(f"\ndaily_data: {daily_count} 条记录")
    if daily_count > 0:
        sample = conn.execute("SELECT date, payment_amount, visitors, page_views FROM daily_data ORDER BY date DESC LIMIT 3").fetchall()
        for row in sample:
            print(f"  日期: {row[0]}, 支付金额: {row[1]}, 访客数: {row[2]}, 浏览量: {row[3]}")
    
    # monthly_data
    monthly_count = conn.execute("SELECT COUNT(*) FROM monthly_data").fetchone()[0]
    print(f"\nmonthly_data: {monthly_count} 条记录")
    if monthly_count > 0:
        sample = conn.execute("SELECT month, payment_amount, visitors FROM monthly_data ORDER BY month DESC LIMIT 3").fetchall()
        for row in sample:
            print(f"  月份: {row[0]}, 支付金额: {row[1]}, 访客数: {row[2]}")
    
    conn.close()


if __name__ == "__main__":
    print("\n开始导入日/月维度数据\n")
    import_daily_data()
    import_monthly_data()
    verify()
    print("\n" + "=" * 70)
    print("导入完成！")
    print("=" * 70)
