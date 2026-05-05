"""
导入日维度和月维度数据
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
    
    # 日维度文件
    daily_file = os.path.join(DATA_DIR, "店铺4月_日_20260503_5e79ed5891d064e4161b68a065551ae9.xlsx")
    
    if not os.path.exists(daily_file):
        print("✗ 日维度文件不存在")
        return
    
    print(f"读取文件: {os.path.basename(daily_file)}")
    df = pd.read_excel(daily_file)
    print(f"  数据行数: {len(df)}")
    print(f"  数据列数: {len(df.columns)}")
    
    conn = sqlite3.connect(DB_PATH)
    
    # Create daily_data table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            payment_amount FLOAT DEFAULT 0,
            refund_amount FLOAT DEFAULT 0,
            net_sales FLOAT DEFAULT 0,
            ad_spend FLOAT DEFAULT 0,
            total_roi FLOAT DEFAULT 0,
            direct_roi FLOAT DEFAULT 0,
            visitors INTEGER DEFAULT 0,
            ipv INTEGER DEFAULT 0,
            uv_value FLOAT DEFAULT 0,
            payment_conversion FLOAT DEFAULT 0,
            refund_rate FLOAT DEFAULT 0,
            cart_rate FLOAT DEFAULT 0,
            cart_qty INTEGER DEFAULT 0,
            avg_order_value FLOAT DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            search_visitors INTEGER DEFAULT 0,
            search_ratio FLOAT DEFAULT 0,
            click_rate FLOAT DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            fav_users INTEGER DEFAULT 0,
            payment_users INTEGER DEFAULT 0,
            presale_amount FLOAT DEFAULT 0,
            presale_qty INTEGER DEFAULT 0,
            pv INTEGER DEFAULT 0,
            search_ipv INTEGER DEFAULT 0,
            recommend_ipv INTEGER DEFAULT 0,
            paid_ipv INTEGER DEFAULT 0,
            organic_ipv INTEGER DEFAULT 0,
            fav_rate FLOAT DEFAULT 0,
            search_click_rate FLOAT DEFAULT 0,
            bounce_rate FLOAT DEFAULT 0,
            avg_stay_duration FLOAT DEFAULT 0,
            ad_roi FLOAT DEFAULT 0,
            repurchase_rate FLOAT DEFAULT 0,
            repurchase_users INTEGER DEFAULT 0,
            cross_sell_qty INTEGER DEFAULT 0,
            cross_sell_rate FLOAT DEFAULT 0,
            category_width INTEGER DEFAULT 0,
            data_source TEXT DEFAULT 'store_daily',
            imported_at TEXT,
            action_1 TEXT,
            action_2 TEXT,
            industry_ctr FLOAT DEFAULT 0
        )
    """)
    
    # Clear old data
    conn.execute("DELETE FROM daily_data")
    
    inserted = 0
    for _, row in df.iterrows():
        date = str(row.get('统计日期', ''))
        if not date or date == 'nan':
            continue
        
        # 确保日期格式正确
        try:
            dt = pd.to_datetime(date)
            date_str = dt.strftime('%Y-%m-%d')
        except:
            date_str = date
        
        # 映射列名
        payment_amount = safe_float(row.get('支付金额'))
        visitors = safe_int(row.get('访客数'))
        page_views = safe_int(row.get('浏览量'))
        payment_users = safe_int(row.get('支付买家数'))
        payment_conversion = safe_float(row.get('支付转化率')) / 100 if safe_float(row.get('支付转化率')) > 1 else safe_float(row.get('支付转化率'))
        ad_spend = safe_float(row.get('全站推广花费')) + safe_float(row.get('关键词推广花费')) + safe_float(row.get('精准人群推广花费'))
        refund_amount = safe_float(row.get('成功退款金额'))
        
        # 计算指标
        net_sales = max(0, payment_amount - refund_amount)
        avg_order_value = (payment_amount / payment_users) if payment_users > 0 else 0
        total_roi = (payment_amount / ad_spend) if ad_spend > 0 else 0
        bounce_rate = safe_float(row.get('跳失率')) / 100 if safe_float(row.get('跳失率')) > 1 else safe_float(row.get('跳失率'))
        
        conn.execute("""
        INSERT INTO daily_data (
            date, product_id, payment_amount, refund_amount, net_sales, ad_spend, total_roi, direct_roi,
            visitors, ipv, uv_value, payment_conversion, refund_rate, cart_rate, cart_qty,
            avg_order_value, page_views, search_visitors, search_ratio, click_rate,
            impressions, clicks, fav_users, payment_users, bounce_rate, avg_stay_duration,
            data_source, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date_str, 'store', payment_amount, refund_amount, net_sales, ad_spend, total_roi, 0,
        visitors, visitors, 0, payment_conversion, 0, 0, 0,
        avg_order_value, page_views, 0, 0, 0, 0, 0, 0, payment_users, bounce_rate,
        safe_float(row.get('平均停留时长')), 'store_daily', datetime.now().isoformat()
    ))
        inserted += 1
    
    conn.commit()
    conn.close()
    print(f"✓ 日维度数据导入完成: {inserted} 条记录\n")


def import_monthly_data():
    """导入月维度数据"""
    print("=" * 70)
    print("导入月维度数据")
    print("=" * 70)
    
    # 月维度文件
    monthly_files = [
        "月汇总.xlsx",
        "智能选款_2026-04-01~2026-04-30.xlsx"
    ]
    
    conn = sqlite3.connect(DB_PATH)
    total_inserted = 0
    
    # Create monthly_data table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monthly_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT,
            payment_amount FLOAT DEFAULT 0,
            refund_amount FLOAT DEFAULT 0,
            net_sales FLOAT DEFAULT 0,
            ad_spend FLOAT DEFAULT 0,
            total_roi FLOAT DEFAULT 0,
            direct_roi FLOAT DEFAULT 0,
            visitors INTEGER DEFAULT 0,
            ipv INTEGER DEFAULT 0,
            uv_value FLOAT DEFAULT 0,
            payment_conversion FLOAT DEFAULT 0,
            refund_rate FLOAT DEFAULT 0,
            cart_rate FLOAT DEFAULT 0,
            cart_qty INTEGER DEFAULT 0,
            avg_order_value FLOAT DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            search_visitors INTEGER DEFAULT 0,
            search_ratio FLOAT DEFAULT 0,
            click_rate FLOAT DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            fav_users INTEGER DEFAULT 0,
            payment_users INTEGER DEFAULT 0,
            presale_amount FLOAT DEFAULT 0,
            presale_qty INTEGER DEFAULT 0,
            pv INTEGER DEFAULT 0,
            search_ipv INTEGER DEFAULT 0,
            recommend_ipv INTEGER DEFAULT 0,
            paid_ipv INTEGER DEFAULT 0,
            organic_ipv INTEGER DEFAULT 0,
            fav_rate FLOAT DEFAULT 0,
            search_click_rate FLOAT DEFAULT 0,
            bounce_rate FLOAT DEFAULT 0,
            avg_stay_duration FLOAT DEFAULT 0,
            ad_roi FLOAT DEFAULT 0,
            repurchase_rate FLOAT DEFAULT 0,
            repurchase_users INTEGER DEFAULT 0,
            cross_sell_qty INTEGER DEFAULT 0,
            cross_sell_rate FLOAT DEFAULT 0,
            category_width INTEGER DEFAULT 0,
            data_source TEXT DEFAULT 'monthly_import',
            imported_at TEXT,
            action_1 TEXT,
            action_2 TEXT,
            industry_ctr FLOAT DEFAULT 0
        )
    """)
    
    # Clear old data
    conn.execute("DELETE FROM monthly_data")
    
    for filename in monthly_files:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"✗ 文件不存在: {filename}")
            continue
        
        print(f"处理: {filename}")
        df = pd.read_excel(filepath)
        file_inserted = 0
        
        # 提取月份
        for _, row in df.iterrows():
            month = str(row.get('月份', ''))
            if not month or month == 'nan':
                # 尝试从文件名提取
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})', filename)
                if date_match:
                    month = date_match.group(1)[:7]  # YYYY-MM
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
            payment_conversion = safe_float(row.get('支付转化率')) / 100 if safe_float(row.get('支付转化率')) > 1 else safe_float(row.get('支付转化率'))
            ad_spend = safe_float(row.get('总推广花费'))
            refund_amount = safe_float(row.get('退款金额'))
            
            net_sales = max(0, payment_amount - refund_amount)
            avg_order_value = (payment_amount / payment_users) if payment_users > 0 else 0
            total_roi = (payment_amount / ad_spend) if ad_spend > 0 else 0
            bounce_rate = safe_float(row.get('跳失率')) / 100 if safe_float(row.get('跳失率')) > 1 else safe_float(row.get('跳失率'))
            
            conn.execute("""
                INSERT INTO monthly_data (
                    month, payment_amount, refund_amount, net_sales, ad_spend, total_roi, direct_roi,
                    visitors, ipv, uv_value, payment_conversion, refund_rate, cart_rate, cart_qty,
                    avg_order_value, page_views, search_visitors, search_ratio, click_rate,
                    impressions, clicks, fav_users, payment_users, bounce_rate, avg_stay_duration,
                    data_source, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                month_str, payment_amount, refund_amount, net_sales, ad_spend, total_roi, 0,
                visitors, visitors, 0, payment_conversion, 0, 0, 0,
                avg_order_value, page_views, 0, 0, 0, 0, 0, 0, payment_users, bounce_rate,
                safe_float(row.get('平均停留时长')), 'monthly_import', datetime.now().isoformat()
            ))
            file_inserted += 1
        
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
