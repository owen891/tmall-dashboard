"""
导入生意参谋商品数据 - 修复版
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


def extract_product_id(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    match = re.search(r'\d{10,}', val_str)
    return match.group() if match else val_str


def import_sycm_products():
    """导入生意参谋商品数据"""
    print("=" * 70)
    print("导入生意参谋商品数据")
    print("=" * 70)
    
    xls_files = [f for f in os.listdir(DATA_DIR) if '生意参谋' in f and '商品' in f and f.endswith('.xls')]
    print(f"发现 {len(xls_files)} 个文件\n")
    
    conn = sqlite3.connect(DB_PATH)
    total_inserted = 0
    
    for filename in sorted(xls_files):
        filepath = os.path.join(DATA_DIR, filename)
        print(f"处理: {filename}")
        
        try:
            df = pd.read_excel(filepath, header=None)
            
            # 查找表头行（包含"统计日期"的行）
            header_row = None
            for i in range(len(df)):
                row_str = ' '.join([str(v) for v in df.iloc[i] if pd.notna(v)])
                if '统计日期' in row_str and '商品ID' in row_str:
                    header_row = i
                    break
            
            if header_row is None:
                print(f"  ✗ 未找到表头行")
                continue
            
            # 从表头下一行开始读取数据
            data_df = df.iloc[header_row + 1:]
            header = df.iloc[header_row]
            data_df.columns = header
            data_df = data_df.reset_index(drop=True)
            
            print(f"  数据行数: {len(data_df)}")
            
            # 从文件名提取日期
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
            week_start = date_match.group(1) if date_match else '2026-04-01'
            
            file_inserted = 0
            for _, row in data_df.iterrows():
                date_col = row.get('统计日期')
                if pd.isna(date_col):
                    continue
                
                product_id = extract_product_id(row.get('商品ID'))
                if not product_id:
                    continue
                
                # 提取数据（使用正确的列名）
                payment_amount = safe_float(row.get('支付金额', 0))
                visitors = safe_int(row.get('商品访客数', 0))
                payment_conversion = safe_float(row.get('商品支付转化率', 0)) / 100
                page_views = safe_int(row.get('商品浏览量', 0))
                payment_users = safe_int(row.get('支付买家数', 0))
                refund_amount = safe_float(row.get('成功退款金额', 0))
                cart_users = safe_int(row.get('商品加购人数', 0))
                fav_users = safe_int(row.get('商品收藏人数', 0))
                
                try:
                    conn.execute("""
                        INSERT INTO weekly_data (
                            product_id, week_start, payment_amount, visitors, payment_conversion,
                            page_views, payment_users, refund_amount, cart_qty, fav_users,
                            data_source, imported_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        product_id, week_start, payment_amount, visitors, payment_conversion,
                        page_views, payment_users, refund_amount, cart_users, fav_users,
                        'sycm_product', datetime.now().isoformat()
                    ))
                    file_inserted += 1
                except Exception as e:
                    if file_inserted == 1:
                        print(f"    插入失败: {e}")
            
            conn.commit()
            total_inserted += file_inserted
            print(f"  ✓ 插入 {file_inserted} 条记录\n")
            
        except Exception as e:
            print(f"  ✗ 处理失败: {e}\n")
    
    conn.close()
    print(f"\n生意参谋商品数据导入完成: 总插入 {total_inserted} 条记录")


if __name__ == "__main__":
    import_sycm_products()
