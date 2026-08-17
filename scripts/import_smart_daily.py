#!/usr/bin/env python3
"""导入智能选款Excel文件到daily_data表（单日数据）"""
import sys, os, re
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import init_db, get_connection

def clean_number(val):
    if pd.isna(val) or val is None: return None
    try: return float(str(val).replace(',', '').replace('%', '').strip())
    except: return None

def clean_int(val):
    n = clean_number(val)
    return int(n) if n is not None else None

def clean_pct(val):
    n = clean_number(val)
    if n is None: return None
    if n > 1: return n / 100.0
    return n

def extract_date_from_filename(filename):
    """从文件名提取日期，如 智能选款_2026-04-22~2026-04-22.xlsx -> 2026-04-22"""
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', os.path.basename(filename))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None

def import_smart_selection_daily(filepath, conn):
    """导入智能选款Excel到daily_data"""
    date_str = extract_date_from_filename(filepath)
    if not date_str:
        print(f"  SKIP: 无法从文件名提取日期: {filepath}")
        return 0

    xls = pd.ExcelFile(filepath)
    total = 0

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, header=None)

        # 查找表头行
        header_row = None
        id_col = None
        for i, row in df.iterrows():
            for j, val in enumerate(row):
                if str(val).strip() in ('商品ID', '宝贝ID', '主体ID'):
                    header_row = i
                    id_col = j
                    break
            if header_row is not None:
                break

        if header_row is None:
            print(f"  Sheet '{sheet}': 未找到表头行，跳过")
            continue

        df.columns = df.iloc[header_row].astype(str).tolist()
        df = df.iloc[header_row + 1:].reset_index(drop=True)

        # 构建列名映射
        col_map = {}
        for i, col in enumerate(df.columns):
            col_map[str(col).strip()] = i

        rows = 0
        for _, row in df.iterrows():
            pid = str(row.iloc[id_col]).strip() if id_col < len(row) else None
            if not pid or pid == 'nan' or pid == 'None':
                continue

            # 更新商品信息
            title = str(row.get('商品标题', '')).strip() if '商品标题' in col_map else ''
            category = str(row.get('商品类目', '')).strip() if '商品类目' in col_map else ''
            image_url = str(row.get('图片链接', '')).strip() if '图片链接' in col_map else ''
            list_date = str(row.get('上架时间', '')).strip() if '上架时间' in col_map else ''

            if title and title != 'nan':
                conn.execute('''INSERT OR IGNORE INTO products (product_id, title, category, image_url, list_date, status)
                    VALUES (?,?,?,?,?,'active')''', (pid, title, category, image_url, list_date))
                conn.execute('''UPDATE products SET title=?, category=?, image_url=?, list_date=?, updated_at=datetime('now')
                    WHERE product_id=?''', (title, category, image_url, list_date, pid))

            # 导入日度数据
            g = lambda name: row.iloc[col_map[name]] if name in col_map and col_map[name] < len(row) else None

            payment_amount = clean_number(g('支付金额'))
            if payment_amount is None:
                continue

            conn.execute('''
                INSERT INTO daily_data (shop_id, product_id, date, payment_amount, refund_amount, net_sales,
                    ipv, pv, payment_conversion, cart_rate, fav_rate, bounce_rate, avg_stay_duration,
                    ad_spend, ad_roi, avg_order_value, buyers, payment_qty, cart_qty, fav_users,
                    search_visitors, uv_value, data_source, imported_at)
                VALUES ('default',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                ON CONFLICT(shop_id, product_id, date) DO UPDATE SET
                    payment_amount=excluded.payment_amount, refund_amount=excluded.refund_amount,
                    net_sales=excluded.net_sales, ipv=excluded.ipv, pv=excluded.pv,
                    payment_conversion=excluded.payment_conversion, cart_rate=excluded.cart_rate,
                    fav_rate=excluded.fav_rate, bounce_rate=excluded.bounce_rate,
                    avg_stay_duration=excluded.avg_stay_duration,
                    ad_spend=excluded.ad_spend, ad_roi=excluded.ad_roi,
                    avg_order_value=excluded.avg_order_value, buyers=excluded.buyers,
                    payment_qty=excluded.payment_qty, cart_qty=excluded.cart_qty,
                    fav_users=excluded.fav_users,
                    search_visitors=excluded.search_visitors, uv_value=excluded.uv_value,
                    data_source=excluded.data_source, imported_at=datetime('now')
            ''', (
                pid, date_str,
                payment_amount,
                clean_number(g('退款金额')),
                clean_number(g('退款后销售额')),
                clean_int(g('访客数')),
                clean_int(g('浏览量')),
                clean_pct(g('支付转化率')),
                clean_pct(g('加购率')),
                clean_pct(g('访客收藏率')),
                clean_pct(g('跳失率')),
                clean_number(g('平均停留时长')),
                clean_number(g('总推广花费')),
                clean_number(g('推广直接ROI')),
                clean_number(g('客单价')),
                clean_int(g('支付人数')),
                clean_int(g('支付件数')),
                clean_int(g('加购件数')),
                clean_int(g('收藏人数')),
                clean_int(g('搜索人数')),
                clean_number(g('UV价值')),
                'smart_selection'
            ))
            rows += 1

        print(f"  Sheet '{sheet}': {rows} rows imported (date={date_str})")
        total += rows

    return total


if __name__ == '__main__':
    init_db()
    conn = get_connection()

    files = sys.argv[1:]
    if not files:
        print("Usage: python import_smart_daily.py <file1.xlsx> [file2.xlsx ...]")
        sys.exit(1)

    grand_total = 0
    for f in files:
        if not os.path.exists(f):
            print(f"SKIP: {f} not found")
            continue
        print(f"\nImporting: {os.path.basename(f)}")
        n = import_smart_selection_daily(f, conn)
        grand_total += n
        conn.commit()
        print(f"  Total: {n} rows")

    conn.close()
    print(f"\n=== Grand total: {grand_total} rows imported ===")
