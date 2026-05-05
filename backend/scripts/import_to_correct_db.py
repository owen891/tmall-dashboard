"""
更新正确的数据库文件
"""
import sqlite3
import shutil
import os
import pandas as pd
import re
from datetime import datetime

DATA_DIR = r"F:\bi\海贝海\原始数据"
# Backend uses this path
DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\dashboard.db"
BACKUP_DIR = r"F:\ai\.accelerate\tmall-dashboard\backend\data\backups"


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


def backup_and_import():
    """备份并导入数据到正确的数据库文件"""
    print("=" * 70)
    print("数据修复 - 导入到正确的数据库文件")
    print("=" * 70)
    print(f"数据库路径: {DB_PATH}")
    
    # Backup if exists
    if os.path.exists(DB_PATH):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f'dashboard_backup_{timestamp}.db')
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ 已备份到: {backup_path}")
    
    # Connect and clear old data
    conn = sqlite3.connect(DB_PATH)
    
    print("\n步骤 1: 清空旧数据")
    try:
        conn.execute("DELETE FROM weekly_data")
        print("  ✓ 已清空 weekly_data")
    except Exception as e:
        print(f"  - weekly_data 表不存在: {e}")
    
    conn.commit()
    
    # Check/add columns
    print("\n步骤 2: 检查表结构")
    cursor = conn.execute("PRAGMA table_info(weekly_data)")
    existing_cols = set([row[1] for row in cursor.fetchall()])
    
    cols_to_add = [
        ("total_roi", "FLOAT", "0"),
        ("direct_roi", "FLOAT", "0"),
        ("uv_value", "FLOAT", "0"),
        ("refund_rate", "FLOAT", "0"),
        ("cart_qty", "INTEGER", "0"),
        ("visitors", "INTEGER", "0"),
        ("page_views", "INTEGER", "0"),
        ("search_visitors", "INTEGER", "0"),
        ("search_ratio", "FLOAT", "0"),
        ("impressions", "INTEGER", "0"),
        ("clicks", "INTEGER", "0"),
        ("fav_users", "INTEGER", "0"),
        ("payment_users", "INTEGER", "0"),
    ]
    
    for col_name, col_type, default in cols_to_add:
        if col_name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE weekly_data ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                print(f"  ✓ 添加列: {col_name}")
            except Exception as e:
                print(f"  ✗ 添加列失败 {col_name}: {e}")
    
    conn.commit()
    
    # Import data
    print("\n步骤 3: 导入原始数据")
    files = [f for f in os.listdir(DATA_DIR) if '智能选款' in f and f.endswith('.xlsx')]
    print(f"发现 {len(files)} 个智能选款文件\n")
    
    total_inserted = 0
    
    for filename in sorted(files):
        filepath = os.path.join(DATA_DIR, filename)
        print(f"处理: {filename}")
        
        try:
            df = pd.read_excel(filepath, sheet_name=0)
            file_inserted = 0
            
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
            
            conn.commit()
            total_inserted += file_inserted
            print(f"  ✓ 插入 {file_inserted} 条记录\n")
            
        except Exception as e:
            print(f"  ✗ 文件处理失败: {e}\n")
    
    conn.close()
    print(f"\n智能选款数据导入完成: 总插入 {total_inserted} 条")
    
    # Verify
    print("\n步骤 4: 验证数据")
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
    print(f"\nweekly_data: {count} 条记录")
    
    neg_count = conn.execute(
        "SELECT COUNT(*) FROM weekly_data WHERE payment_amount < 0 OR visitors < 0"
    ).fetchone()[0]
    print(f"  负数记录: {neg_count} 条")
    
    if count > 0:
        sample = conn.execute(
            "SELECT product_id, week_start, payment_amount, visitors, ad_spend FROM weekly_data ORDER BY week_start DESC LIMIT 5"
        ).fetchall()
        print("\n  最新数据示例:")
        for row in sample:
            print(f"    商品ID: {row[0]}, 日期: {row[1]}, 支付金额: {row[2]}, 访客数: {row[3]}, 广告花费: {row[4]}")
    
    conn.close()
    print("\n" + "=" * 70)
    print("数据修复完成！")
    print("=" * 70)


if __name__ == "__main__":
    backup_and_import()
