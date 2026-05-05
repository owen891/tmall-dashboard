"""
修复数据库：恢复备份并添加所有缺失的列，然后导入数据
"""
import sqlite3
import shutil
import os
import pandas as pd
import re
from datetime import datetime

# Paths
DATA_DIR = r"F:\bi\海贝海\原始数据"
DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
BACKUP_DIR = r"F:\ai\.accelerate\tmall-dashboard\backend\data\backups"

def restore_backup():
    """恢复最新的备份"""
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
    if backups:
        latest_backup = os.path.join(BACKUP_DIR, backups[-1])
        shutil.copy2(latest_backup, DB_PATH)
        print(f"✓ 已恢复备份: {backups[-1]}")
        return True
    return False

def add_missing_columns():
    """添加所有缺失的列"""
    conn = sqlite3.connect(DB_PATH)
    
    # Get current columns
    cursor = conn.execute("PRAGMA table_info(weekly_data)")
    existing_cols = set([row[1] for row in cursor.fetchall()])
    
    # All columns we need
    cols_to_add = [
        ("search_visitors", "INTEGER", "0"),
    ]
    
    added = 0
    for col_name, col_type, default in cols_to_add:
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE weekly_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                print(f"✓ 添加列: {col_name}")
                added += 1
            except Exception as e:
                print(f"✗ 添加列失败 {col_name}: {e}")
    
    conn.commit()
    conn.close()
    print(f"\n共添加 {added} 个列")

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

def extract_product_id(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    match = re.search(r'\d{10,}', val_str)
    return match.group() if match else val_str

def clear_and_import():
    """清空并导入数据"""
    print("\n" + "=" * 70)
    print("开始导入数据")
    print("=" * 70)
    
    # Clear old data
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM weekly_data")
    conn.commit()
    
    files = [f for f in os.listdir(DATA_DIR) if '智能选款' in f and f.endswith('.xlsx')]
    print(f"\n发现 {len(files)} 个智能选款文件\n")
    
    total_inserted = 0
    total_errors = 0
    
    for filename in sorted(files):
        filepath = os.path.join(DATA_DIR, filename)
        print(f"处理: {filename}")
        
        try:
            df = pd.read_excel(filepath, sheet_name=0)
            file_inserted = 0
            
            # Extract week_start from filename
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
            week_start = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
            
            for _, row in df.iterrows():
                product_id = extract_product_id(row.get('商品ID'))
                if not product_id:
                    continue
                
                payment_amount = safe_float(row.get('支付金额'))
                refund_amount = safe_float(row.get('退款金额'))
                ad_spend = safe_float(row.get('总推广花费'))
                direct_roi = safe_float(row.get('推广直接ROI'))
                visitors = safe_int(row.get('访客数'))
                uv_value = safe_float(row.get('UV价值'))
                payment_conversion = safe_float(row.get('支付转化率'))
                refund_rate = safe_float(row.get('退款率'))
                cart_rate = safe_float(row.get('加购率'))
                cart_qty = safe_int(row.get('加购件数'))
                avg_order_value = safe_float(row.get('客单价'))
                page_views = safe_int(row.get('浏览量'))
                search_visitors = safe_int(row.get('搜索人数'))
                search_ratio = safe_float(row.get('搜索占比'))
                click_rate = safe_float(row.get('总点击率'))
                impressions = safe_int(row.get('总展现量'))
                clicks = safe_int(row.get('总点击量'))
                fav_users = safe_int(row.get('收藏人数'))
                payment_users = safe_int(row.get('支付人数'))
                
                net_sales = max(0, payment_amount - refund_amount)
                total_roi = (payment_amount / ad_spend) if ad_spend > 0 else 0
                
                try:
                    conn.execute("""
                        INSERT INTO weekly_data (
                            product_id, week_start, payment_amount, refund_amount, net_sales,
                            ad_spend, total_roi, direct_roi, 
                            visitors, uv_value, payment_conversion, refund_rate,
                            cart_rate, cart_qty, avg_order_value, 
                            page_views, search_visitors, search_ratio,
                            click_rate, impressions, clicks, fav_users,
                            payment_users, data_source, imported_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        product_id, week_start, payment_amount, refund_amount, net_sales,
                        ad_spend, total_roi, direct_roi,
                        visitors, uv_value, payment_conversion, refund_rate,
                        cart_rate, cart_qty, avg_order_value,
                        page_views, search_visitors, search_ratio,
                        click_rate, impressions, clicks, fav_users,
                        payment_users, 'sycm_import', datetime.now().isoformat()
                    ))
                    file_inserted += 1
                except Exception as e:
                    total_errors += 1
                    if total_errors <= 3:
                        print(f"    ✗ 插入失败 (product_id={product_id}): {e}")
            
            conn.commit()
            total_inserted += file_inserted
            print(f"  ✓ 插入 {file_inserted} 条记录\n")
            
        except Exception as e:
            print(f"  ✗ 文件处理失败: {e}\n")
            total_errors += 1
    
    conn.close()
    print(f"\n智能选款数据导入完成:")
    print(f"  总插入: {total_inserted} 条")
    print(f"  错误数: {total_errors} 条")

def verify():
    """验证数据"""
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
    print(f"\nweekly_data: {count} 条记录")
    
    neg_count = conn.execute(
        "SELECT COUNT(*) FROM weekly_data WHERE payment_amount < 0 OR visitors < 0"
    ).fetchone()[0]
    print(f"  负数记录: {neg_count} 条")
    
    if count > 0:
        sample = conn.execute(
            "SELECT product_id, week_start, payment_amount, visitors, ad_spend FROM weekly_data LIMIT 5"
        ).fetchall()
        print("\n  示例数据:")
        for row in sample:
            print(f"    商品ID: {row[0]}, 日期: {row[1]}, 支付金额: {row[2]}, 访客数: {row[3]}, 广告花费: {row[4]}")
    
    conn.close()

if __name__ == "__main__":
    print("=" * 70)
    print("数据修复工具 v3.0")
    print("=" * 70)
    
    # Step 1: Restore backup
    print("\n步骤 1: 恢复备份")
    restore_backup()
    
    # Step 2: Add missing columns
    print("\n步骤 2: 添加缺失的列")
    add_missing_columns()
    
    # Step 3: Clear and import
    clear_and_import()
    
    # Step 4: Verify
    print("\n步骤 3: 验证数据")
    verify()
    
    print("\n" + "=" * 70)
    print("数据修复完成！")
    print("=" * 70)
