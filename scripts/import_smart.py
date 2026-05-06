#!/usr/bin/env python3
"""导入智能选款Excel文件到monthly_data表"""
import sys, os, re, glob
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
    """从文件名提取日期，如 智能选款_2026-04-22~2026-04-22.xlsx -> 2026-04"""
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', os.path.basename(filename))
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None

def import_smart_selection(filepath, conn):
    """导入智能选款Excel到monthly_data"""
    month = extract_date_from_filename(filepath)
    if not month:
        print(f"  SKIP: 无法从文件名提取月份: {filepath}")
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

            # 导入月度数据
            g = lambda name: row.iloc[col_map[name]] if name in col_map and col_map[name] < len(row) else None

            payment_amount = clean_number(g('支付金额'))
            if payment_amount is None:
                continue  # 没有支付金额的行跳过

            conn.execute('''
                INSERT INTO monthly_data (product_id, month, payment_amount, refund_amount, net_sales,
                    visitors, page_views, uv_value, search_visitors, search_ratio,
                    payment_conversion, search_conversion, cart_rate, fav_rate, bounce_rate, avg_stay_duration,
                    ad_spend, ad_roi, overall_roi, paid_ratio, refund_paid_ratio,
                    keyword_spend, keyword_sales, keyword_roi, keyword_visitors, keyword_ppc,
                    crowd_spend, crowd_sales, crowd_roi, crowd_visitors, crowd_ppc,
                    site_spend, site_sales, site_roi, site_visitors, site_ppc,
                    refund_rate, repurchase_rate, cross_sell_rate,
                    buyers, avg_order_value, payment_qty, cart_qty, fav_users, click_rate, score,
                    data_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(product_id, month) DO UPDATE SET
                    payment_amount=excluded.payment_amount, refund_amount=excluded.refund_amount,
                    net_sales=excluded.net_sales, visitors=excluded.visitors, page_views=excluded.page_views,
                    uv_value=excluded.uv_value, search_visitors=excluded.search_visitors,
                    search_ratio=excluded.search_ratio,
                    payment_conversion=excluded.payment_conversion, search_conversion=excluded.search_conversion,
                    cart_rate=excluded.cart_rate, fav_rate=excluded.fav_rate,
                    bounce_rate=excluded.bounce_rate, avg_stay_duration=excluded.avg_stay_duration,
                    ad_spend=excluded.ad_spend, ad_roi=excluded.ad_roi,
                    overall_roi=excluded.overall_roi, paid_ratio=excluded.paid_ratio,
                    refund_paid_ratio=excluded.refund_paid_ratio,
                    keyword_spend=excluded.keyword_spend, keyword_sales=excluded.keyword_sales,
                    keyword_roi=excluded.keyword_roi, keyword_visitors=excluded.keyword_visitors,
                    keyword_ppc=excluded.keyword_ppc,
                    crowd_spend=excluded.crowd_spend, crowd_sales=excluded.crowd_sales,
                    crowd_roi=excluded.crowd_roi, crowd_visitors=excluded.crowd_visitors,
                    crowd_ppc=excluded.crowd_ppc,
                    site_spend=excluded.site_spend, site_sales=excluded.site_sales,
                    site_roi=excluded.site_roi, site_visitors=excluded.site_visitors,
                    site_ppc=excluded.site_ppc,
                    refund_rate=excluded.refund_rate, repurchase_rate=excluded.repurchase_rate,
                    cross_sell_rate=excluded.cross_sell_rate,
                    buyers=excluded.buyers, avg_order_value=excluded.avg_order_value,
                    payment_qty=excluded.payment_qty, cart_qty=excluded.cart_qty,
                    fav_users=excluded.fav_users, click_rate=excluded.click_rate, score=excluded.score,
                    imported_at=datetime('now')
            ''', (
                pid, month,
                payment_amount,
                clean_number(g('退款金额')),
                clean_number(g('退款后销售额')),
                clean_int(g('访客数')),
                clean_int(g('浏览量')),
                clean_number(g('UV价值')),
                clean_int(g('搜索人数')),
                clean_pct(g('搜索占比')),
                clean_pct(g('支付转化率')),
                clean_pct(g('搜索支付转化率')),
                clean_pct(g('加购率')),
                clean_pct(g('访客收藏率')),
                clean_pct(g('跳失率')),
                clean_number(g('平均停留时长')),
                clean_number(g('总推广花费')),
                clean_number(g('推广直接ROI')),
                clean_number(g('总投产')),
                clean_pct(g('付费占比')),
                clean_pct(g('退款付费占比')),
                clean_number(g('关键词推广花费')),
                clean_number(g('关键词推广销售额')),
                clean_number(g('关键词推广投产')),
                clean_int(g('关键词推广访客数')),
                clean_number(g('关键词推广PPC')),
                clean_number(g('人群推广花费')),
                clean_number(g('人群推广销售额')),
                clean_number(g('人群推广投产')),
                clean_int(g('人群推广访客数')),
                clean_number(g('人群推广PPC')),
                clean_number(g('货品全站推广花费')),
                clean_number(g('货品全站推广销售额')),
                clean_number(g('货品全站推广投产')),
                clean_int(g('货品全站推广访客数')),
                clean_number(g('货品全站推广PPC')),
                clean_pct(g('退款率')),
                clean_pct(g('复购率')),
                clean_pct(g('连带率')),
                clean_int(g('支付人数')),
                clean_number(g('客单价')),
                clean_int(g('支付件数')),
                clean_int(g('加购件数')),
                clean_int(g('收藏人数')),
                clean_pct(g('总点击率')),
                clean_int(g('评分')),
                'smart_selection'
            ))
            rows += 1

        print(f"  Sheet '{sheet}': {rows} rows imported (month={month})")
        total += rows

    return total


if __name__ == '__main__':
    init_db()
    conn = get_connection()

    files = sys.argv[1:]
    if not files:
        print("Usage: python import_smart.py <file1.xlsx> [file2.xlsx ...]")
        sys.exit(1)

    grand_total = 0
    for f in files:
        if not os.path.exists(f):
            print(f"SKIP: {f} not found")
            continue
        print(f"\nImporting: {os.path.basename(f)}")
        n = import_smart_selection(f, conn)
        grand_total += n
        conn.commit()
        print(f"  Total: {n} rows")

    conn.close()
    print(f"\n=== Grand total: {grand_total} rows imported ===")
