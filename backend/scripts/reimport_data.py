"""
数据修复脚本：备份数据库、清空错误数据、重新导入原始数据
"""
import pandas as pd
import sqlite3
import shutil
import os
import re
from datetime import datetime

# Paths
DATA_DIR = r"F:\bi\海贝海\原始数据"
DB_PATH = r"F:\ai\.accelerate\tmall-dashboard\backend\data\db\dashboard.db"
BACKUP_DIR = r"F:\ai\.accelerate\tmall-dashboard\backend\data\backups"


def safe_float(val, default=0.0):
    """安全转换为浮点数"""
    try:
        if pd.isna(val) or val == '' or val == '-':
            return default
        val_str = str(val).replace(',', '').replace('%', '')
        return float(val_str)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    """安全转换为整数"""
    try:
        if pd.isna(val) or val == '' or val == '-':
            return default
        val_str = str(val).replace(',', '')
        return int(float(val_str))
    except (ValueError, TypeError):
        return default


def extract_product_id(val):
    """提取商品ID"""
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    match = re.search(r'\d{10,}', val_str)
    return match.group() if match else val_str


def backup_database():
    """备份数据库"""
    print("=" * 70)
    print("步骤 1: 备份数据库")
    print("=" * 70)
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'dashboard_backup_{timestamp}.db')
    
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ 数据库已备份到: {backup_path}")
        return backup_path
    else:
        print("✗ 数据库文件不存在，跳过备份")
        return None


def clear_old_data():
    """清空旧数据"""
    print("\n" + "=" * 70)
    print("步骤 2: 清空旧数据")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    
    tables_to_clear = ['weekly_data', 'daily_data', 'monthly_data']
    
    for table in tables_to_clear:
        try:
            conn.execute(f"DELETE FROM {table}")
            print(f"  ✓ 清空 {table}")
        except Exception as e:
            print(f"  - {table} 不存在或清空失败: {e}")
    
    conn.commit()
    conn.close()
    print("✓ 旧数据已清空")


def import_smart_selection_data():
    """导入智能选款数据到weekly_data表"""
    print("\n" + "=" * 70)
    print("步骤 3: 导入智能选款数据")
    print("=" * 70)
    
    files = [f for f in os.listdir(DATA_DIR) if '智能选款' in f and f.endswith('.xlsx')]
    print(f"发现 {len(files)} 个智能选款文件\n")
    
    conn = sqlite3.connect(DB_PATH)
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
                
                # Parse values - 确保数据正确性
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
                payment_qty = safe_int(row.get('支付件数'))
                
                # Calculate derived values
                net_sales = max(0, payment_amount - refund_amount)
                total_roi = (payment_amount / ad_spend) if ad_spend > 0 else 0
                
                try:
                    # Use actual table columns from weekly_data
                    conn.execute("""
                        INSERT INTO weekly_data (
                            product_id, week_start, payment_amount, refund_amount, net_sales,
                            ad_spend, total_roi, direct_roi, 
                            visitors, uv_value, payment_conversion, refund_rate,
                            cart_rate, cart_qty, avg_order_value, 
                            page_views, search_visitors, search_ratio,
                            click_rate, impressions, clicks, fav_users,
                            payment_users, data_source, imported_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?
                        )
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


def update_products_table():
    """更新products表的商品信息"""
    print("\n" + "=" * 70)
    print("步骤 4: 更新商品信息")
    print("=" * 70)
    
    files = [f for f in os.listdir(DATA_DIR) if '智能选款' in f and f.endswith('.xlsx')]
    if not files:
        print("✗ 未找到智能选款文件")
        return
    
    latest_file = sorted(files)[-1]
    filepath = os.path.join(DATA_DIR, latest_file)
    print(f"使用文件: {latest_file}")
    
    df = pd.read_excel(filepath, sheet_name=0)
    
    conn = sqlite3.connect(DB_PATH)
    updated = 0
    inserted = 0
    
    for _, row in df.iterrows():
        product_id = extract_product_id(row.get('商品ID'))
        if not product_id:
            continue
        
        title = str(row.get('商品标题', ''))
        image_url = str(row.get('图片链接', ''))
        category = str(row.get('商品类目', ''))
        list_date = str(row.get('上架时间', ''))
        
        existing = conn.execute(
            "SELECT id FROM products WHERE product_id = ?", 
            (product_id,)
        ).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE products 
                SET title = ?, image_url = ?, category = ?, list_date = ?
                WHERE product_id = ?
            """, (title, image_url, category, list_date, product_id))
            updated += 1
        else:
            conn.execute("""
                INSERT INTO products (product_id, title, image_url, category, list_date, status, starred, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', 0, ?, ?)
            """, (product_id, title, image_url, category, list_date, 
                  datetime.now().isoformat(), datetime.now().isoformat()))
            inserted += 1
    
    conn.commit()
    conn.close()
    
    print(f"  ✓ 更新: {updated} 条")
    print(f"  ✓ 新增: {inserted} 条")


def verify_data():
    """验证数据导入结果"""
    print("\n" + "=" * 70)
    print("步骤 5: 验证数据")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    
    count = conn.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
    print(f"\nweekly_data: {count} 条记录")
    
    neg_count = conn.execute(
        "SELECT COUNT(*) FROM weekly_data WHERE payment_amount < 0 OR visitors < 0"
    ).fetchone()[0]
    print(f"  负数记录: {neg_count} 条")
    
    if count > 0:
        sample = conn.execute(
            "SELECT product_id, week_start, payment_amount, visitors, ad_spend FROM weekly_data LIMIT 3"
        ).fetchall()
        print("\n  示例数据:")
        for row in sample:
            print(f"    商品ID: {row[0]}, 日期: {row[1]}, 支付金额: {row[2]}, 访客数: {row[3]}, 广告花费: {row[4]}")
    
    prod_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    print(f"\nproducts: {prod_count} 条记录")
    
    conn.close()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("数据修复工具 v2.0")
    print("=" * 70)
    print(f"数据目录: {DATA_DIR}")
    print(f"数据库路径: {DB_PATH}\n")
    
    backup_path = backup_database()
    clear_old_data()
    import_smart_selection_data()
    update_products_table()
    verify_data()
    
    print("\n" + "=" * 70)
    print("数据修复完成！")
    print("=" * 70)
    print(f"\n备份文件: {backup_path}")
    print("如果数据有问题，可以恢复备份文件")
