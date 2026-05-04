#!/usr/bin/env python3
"""
数据导入脚本 - 从原始数据源自动匹配并导入数据到新架构数据库
数据源目录：F:\bi\海贝海\原始数据

支持的文件类型：
  1. 智能选款文件 (智能选款_*.xlsx)
  2. TOP N文件 (TOP10单品_*, TOP50-整体_*, topN-*.xlsx)
  3. 流量来源文件 (4月X-来源_*, topN-来源_*, 店铺-来源_*)
  4. 搜索排行/关键词文件 (搜索排行_*.xlsx, 关键词洞察_*.xlsx)
  5. 品类文件 (品类-*.xls)
  6. 市场排行文件 (市场排行_*.xlsx)
  7. 店铺/日数据文件 (店铺4月_日_*.xlsx)
  8. 生意参谋商品文件 (【生意参谋平台】商品_*.xls)
  9. 全店单品列表文件 (全店单品列表_*.xlsx)
"""

import sys
import os
import re
import glob
import zipfile
import tempfile
import shutil
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

# 确保我们能找到app模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))

from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.models.product import (
    Product, MonthlyData, WeeklyData, DailyData, ProductRanking, ProductHealth
)
from app.models.dashboard_models import (
    DailyMetrics, KeywordMetrics, TrafficStructure, FunnelMetrics,
    MarketAnalysis, MarketKeywordOpportunity, ProductProfit
)
from app.models.command_tower import DmpCrowd, WxtCampaign


# ==========================================
# 数据类型清理函数
# ==========================================
def clean_number(val):
    if pd.isna(val) or val is None:
        return None
    try:
        val_str = str(val).replace(',', '').replace('%', '').strip()
        return float(val_str) if val_str else None
    except:
        return None


def clean_int(val):
    n = clean_number(val)
    return int(n) if n is not None else None


def clean_pct(val):
    n = clean_number(val)
    if n is None:
        return None
    if n > 1:
        return n / 100.0
    return n


def clean_str(val):
    if pd.isna(val) or val is None:
        return ''
    return str(val).strip()


# ==========================================
# 日期解析函数
# ==========================================
def extract_date_from_filename(filename):
    """从文件名提取日期范围"""
    # 匹配 YYYY-MM-DD~YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})[~至](\d{4})-(\d{2})-(\d{2})', os.path.basename(filename))
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    
    # 匹配单个日期 YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', os.path.basename(filename))
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    
    # 匹配 4月X-* 这种格式
    m = re.search(r'(\d+)月(\d+)[- ]', os.path.basename(filename))
    if m:
        year = 2026  # 默认年份
        month = int(m.group(1))
        day = int(m.group(2))
        return f"{year}-{month:02d}-{day:02d}"
    
    # 匹配 20260503 这种时间戳
    m = re.search(r'_(\d{8})_', os.path.basename(filename))
    if m:
        ts = m.group(1)
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
    
    return None


# ==========================================
# Excel文件处理工具
# ==========================================
def find_header_row(df, header_keywords):
    """查找表头行"""
    for i, row in df.iterrows():
        for j, val in enumerate(row):
            val_str = str(val).strip()
            if any(keyword in val_str for keyword in header_keywords):
                return i, j
    return None, None


def load_excel_file(filepath):
    """加载Excel文件"""
    try:
        if filepath.endswith('.xls'):
            return pd.ExcelFile(filepath, engine='xlrd')
        else:
            return pd.ExcelFile(filepath, engine='openpyxl')
    except Exception as e:
        print(f"  ❌ 文件打开失败: {e}")
        return None


# ==========================================
# 文件类型分类
# ==========================================
def classify_file(filename):
    """根据文件名分类文件类型"""
    filename_lower = filename.lower()
    
    if '智能选款' in filename:
        return 'smart_selection'
    
    elif 'top' in filename_lower and ('单品' in filename or '整体' in filename):
        return 'topn_items'
    
    elif '来源' in filename or 'traffic' in filename_lower:
        return 'traffic_source'
    
    elif '搜索排行' in filename or '关键词' in filename:
        return 'search_ranking'
    
    elif '品类' in filename:
        return 'category'
    
    elif '市场排行' in filename:
        return 'market_ranking'
    
    elif '店铺' in filename and ('日' in filename):
        return 'shop_daily'
    
    elif '【生意参谋平台】商品' in filename:
        return 'sycm_products'
    
    elif '全店单品列表' in filename:
        return 'all_items_list'
    
    elif 'dmp' in filename_lower or '达摩盘' in filename:
        return 'dmp_crowd'
    
    elif 'wxt' in filename_lower or '万相台' in filename:
        return 'wxt_campaign'
    
    elif 'sku销售' in filename:
        return 'sku_sales'
    
    elif '绩效明细' in filename:
        return 'performance'
    
    else:
        return 'unknown'


# ==========================================
# 1. 智能选款文件导入
# ==========================================
def import_smart_selection(filepath, session):
    """导入智能选款Excel到MonthlyData和Products"""
    month = extract_date_from_filename(filepath)
    if not month:
        print(f"  ⚠️ 无法从文件名提取月份")
        month = datetime.now().strftime("%Y-%m")

    xls = load_excel_file(filepath)
    if not xls:
        return 0

    total = 0

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        except Exception as e:
            print(f"  跳过工作表 {sheet_name}: {e}")
            continue

        # 查找表头
        header_row, id_col = find_header_row(df, ['商品ID', '宝贝ID', '主体ID'])
        if header_row is None:
            print(f"  ⚠️ {sheet_name} 未找到表头")
            continue

        df.columns = df.iloc[header_row].astype(str).tolist()
        df = df.iloc[header_row + 1:].reset_index(drop=True)

        # 构建列名 -> 索引映射
        col_map = {str(col).strip(): i for i, col in enumerate(df.columns)}

        rows_imported = 0
        for _, row in df.iterrows():
            pid = clean_str(row.iloc[id_col]) if id_col < len(row) else None
            if not pid or pid.lower() in ['nan', 'none', '']:
                continue

            def g(col_name):
                """获取列值的快捷函数"""
                if col_name in col_map and col_map[col_name] < len(row):
                    return row.iloc[col_map[col_name]]
                return None

            payment_amount = clean_number(g('支付金额'))
            if payment_amount is None:
                continue

            # 1. 处理Product表
            title = clean_str(g('商品标题'))
            category = clean_str(g('商品类目'))
            image_url = clean_str(g('图片链接'))
            list_date = clean_str(g('上架时间'))
            
            if title and title.lower() != 'nan':
                existing_product = session.query(Product).filter(Product.product_id == pid).first()
                if existing_product:
                    existing_product.title = title
                    existing_product.category = category
                    existing_product.image_url = image_url
                    existing_product.list_date = list_date
                    existing_product.updated_at = datetime.now()
                else:
                    new_product = Product(
                        product_id=pid,
                        title=title,
                        category=category,
                        image_url=image_url,
                        list_date=list_date,
                        status='active'
                    )
                    session.add(new_product)
                session.flush()

            # 2. 处理MonthlyData表
            existing_monthly = session.query(MonthlyData).filter(
                MonthlyData.product_id == pid,
                MonthlyData.month == month
            ).first()

            data_source = 'smart_selection'
            imported_at = datetime.now()

            monthly_fields = {
                'payment_amount': payment_amount,
                'refund_amount': clean_number(g('退款金额')),
                'net_sales': clean_number(g('退款后销售额')),
                'visitors': clean_int(g('访客数')),
                'page_views': clean_int(g('浏览量')),
                'uv_value': clean_number(g('UV价值')),
                'search_visitors': clean_int(g('搜索人数')),
                'search_ratio': clean_pct(g('搜索占比')),
                'payment_conversion': clean_pct(g('支付转化率')),
                'search_conversion': clean_pct(g('搜索支付转化率')),
                'cart_rate': clean_pct(g('加购率')),
                'fav_rate': clean_pct(g('访客收藏率')),
                'bounce_rate': clean_pct(g('跳失率')),
                'avg_stay_duration': clean_number(g('平均停留时长')),
                'ad_spend': clean_number(g('总推广花费')),
                'ad_roi': clean_number(g('推广直接ROI')),
                'overall_roi': clean_number(g('总投产')),
                'paid_ratio': clean_pct(g('付费占比')),
                'refund_paid_ratio': clean_pct(g('退款付费占比')),
                'keyword_spend': clean_number(g('关键词推广花费')),
                'keyword_sales': clean_number(g('关键词推广销售额')),
                'keyword_roi': clean_number(g('关键词推广投产')),
                'keyword_visitors': clean_int(g('关键词推广访客数')),
                'keyword_ppc': clean_number(g('关键词推广PPC')),
                'crowd_spend': clean_number(g('人群推广花费')),
                'crowd_sales': clean_number(g('人群推广销售额')),
                'crowd_roi': clean_number(g('人群推广投产')),
                'crowd_visitors': clean_int(g('人群推广访客数')),
                'crowd_ppc': clean_number(g('人群推广PPC')),
                'site_spend': clean_number(g('货品全站推广花费')),
                'site_sales': clean_number(g('货品全站推广销售额')),
                'site_roi': clean_number(g('货品全站推广投产')),
                'site_visitors': clean_int(g('货品全站推广访客数')),
                'site_ppc': clean_number(g('货品全站推广PPC')),
                'refund_rate': clean_pct(g('退款率')),
                'repurchase_rate': clean_pct(g('复购率')),
                'cross_sell_rate': clean_pct(g('连带率')),
                'buyers': clean_int(g('支付人数')),
                'avg_order_value': clean_number(g('客单价')),
                'payment_qty': clean_int(g('支付件数')),
                'cart_qty': clean_int(g('加购件数')),
                'fav_users': clean_int(g('收藏人数')),
                'click_rate': clean_pct(g('总点击率')),
                'score': clean_int(g('评分')),
                'data_source': data_source,
                'imported_at': imported_at
            }

            if existing_monthly:
                for key, value in monthly_fields.items():
                    if value is not None:
                        setattr(existing_monthly, key, value)
            else:
                new_monthly = MonthlyData(product_id=pid, month=month, **monthly_fields)
                session.add(new_monthly)

            rows_imported += 1
            total += 1

        print(f"  ✅ {sheet_name}: {rows_imported} 条 (月份: {month})")
        session.commit()

    return total


# ==========================================
# 2. 流量来源文件导入
# ==========================================
def import_traffic_source(filepath, session):
    """导入流量来源文件到TrafficStructure和DailyMetrics"""
    date = extract_date_from_filename(filepath)
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    xls = load_excel_file(filepath)
    if not xls:
        return 0

    total = 0

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
        except Exception as e:
            print(f"  跳过工作表 {sheet_name}: {e}")
            continue

        # 尝试找可能的表头
        header_row, _ = find_header_row(df, ['来源', '来源名称', '流量来源', '访客数', 'UV', '浏览量'])
        
        if header_row is not None and header_row > 0:
            df.columns = df.iloc[header_row].astype(str).tolist()
            df = df.iloc[header_row + 1:].reset_index(drop=True)

        col_map = {str(col).strip(): i for i, col in enumerate(df.columns)}

        rows_imported = 0
        for _, row in df.iterrows():
            def g(col_pattern):
                for col_name, idx in col_map.items():
                    if col_pattern in col_name:
                        return row.iloc[idx] if idx < len(row) else None
                return None

            total_uv = clean_int(g('访客数')) or clean_int(g('UV'))
            search_uv = clean_int(g('搜索')) or clean_int(g('搜索访客'))
            recommend_uv = clean_int(g('推荐'))
            ztc_uv = clean_int(g('直通车')) or clean_int(g('ZTC'))
            wxt_uv = clean_int(g('万相台')) or clean_int(g('WXT'))

            if total_uv is not None or search_uv is not None:
                existing_ts = session.query(TrafficStructure).filter(TrafficStructure.date == date).first()
                if existing_ts:
                    if total_uv is not None: existing_ts.total_uv = total_uv
                    if search_uv is not None: existing_ts.search_uv = search_uv
                    if recommend_uv is not None: existing_ts.recommend_uv = recommend_uv
                    if ztc_uv is not None: existing_ts.ztc_uv = ztc_uv
                    if wxt_uv is not None: existing_ts.wxt_uv = wxt_uv
                else:
                    new_ts = TrafficStructure(
                        date=date,
                        total_uv=total_uv,
                        search_uv=search_uv,
                        recommend_uv=recommend_uv,
                        ztc_uv=ztc_uv,
                        wxt_uv=wxt_uv
                    )
                    session.add(new_ts)
                
                rows_imported += 1
                total += 1

    if rows_imported > 0:
        print(f"  ✅ 流量数据: {rows_imported} 条 (日期: {date})")
        session.commit()

    return total


# ==========================================
# 3. 搜索排行/关键词文件导入
# ==========================================
def import_search_ranking(filepath, session):
    """导入搜索排行/关键词文件到KeywordMetrics"""
    date = extract_date_from_filename(filepath)
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    xls = load_excel_file(filepath)
    if not xls:
        return 0

    total = 0

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
        except Exception as e:
            print(f"  跳过工作表 {sheet_name}: {e}")
            continue

        # 查找表头
        header_row, _ = find_header_row(df, ['关键词', '搜索词', '搜索人气', '搜索热度', '点击率', '转化率'])
        if header_row is not None and header_row > 0:
            df.columns = df.iloc[header_row].astype(str).tolist()
            df = df.iloc[header_row + 1:].reset_index(drop=True)

        col_map = {str(col).strip(): i for i, col in enumerate(df.columns)}

        rows_imported = 0
        for _, row in df.iterrows():
            def g(col_pattern):
                for col_name, idx in col_map.items():
                    if col_pattern in col_name:
                        return row.iloc[idx] if idx < len(row) else None
                return None

            keyword = clean_str(g('关键词')) or clean_str(g('搜索词'))
            if not keyword or keyword.lower() in ['nan', '']:
                continue

            popularity = clean_int(g('搜索人气')) or clean_int(g('热度'))
            impressions = clean_int(g('曝光')) or clean_int(g('展现'))
            clicks = clean_int(g('点击')) or clean_int(g('点击量'))
            ctr = clean_pct(g('点击率'))
            cvr = clean_pct(g('转化率'))
            gmv = clean_number(g('GMV')) or clean_number(g('交易金额'))
            cost = clean_number(g('花费')) or clean_number(g('消耗'))
            roi = clean_number(g('ROI')) or clean_number(g('投产'))

            # 查找是否已存在
            existing_kw = session.query(KeywordMetrics).filter(
                KeywordMetrics.date == date,
                KeywordMetrics.keyword == keyword
            ).first()

            if existing_kw:
                if popularity is not None: existing_kw.popularity = popularity
                if impressions is not None: existing_kw.impressions = impressions
                if clicks is not None: existing_kw.clicks = clicks
                if ctr is not None: existing_kw.ctr = ctr
                if cvr is not None: existing_kw.cvr = cvr
                if gmv is not None: existing_kw.gmv = gmv
                if cost is not None: existing_kw.cost = cost
                if roi is not None: existing_kw.roi = roi
            else:
                new_kw = KeywordMetrics(
                    date=date,
                    keyword=keyword,
                    popularity=popularity,
                    impressions=impressions,
                    clicks=clicks,
                    ctr=ctr,
                    cvr=cvr,
                    gmv=gmv,
                    cost=cost,
                    roi=roi,
                    category='流量词'
                )
                session.add(new_kw)
            
            rows_imported += 1
            total += 1

    if rows_imported > 0:
        print(f"  ✅ 关键词数据: {rows_imported} 条 (日期: {date})")
        session.commit()

    return total


# ==========================================
# 4. 店铺/日数据导入
# ==========================================
def import_shop_daily(filepath, session):
    """导入店铺日数据到DailyMetrics"""
    date = extract_date_from_filename(filepath)
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    xls = load_excel_file(filepath)
    if not xls:
        return 0

    total = 0

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
        except Exception as e:
            print(f"  跳过工作表 {sheet_name}: {e}")
            continue

        col_map = {str(col).strip(): i for i, col in enumerate(df.columns)}

        for _, row in df.iterrows():
            def g(col_pattern):
                for col_name, idx in col_map.items():
                    if col_pattern in col_name:
                        return row.iloc[idx] if idx < len(row) else None
                return None

            gmv = clean_number(g('GMV')) or clean_number(g('支付金额')) or clean_number(g('交易金额'))
            total_uv = clean_int(g('访客数')) or clean_int(g('UV'))
            buyers = clean_int(g('支付人数')) or clean_int(g('买家数'))
            conversion_rate = clean_pct(g('支付转化率'))
            ad_spend = clean_number(g('推广花费')) or clean_number(g('花费'))
            ad_roi = clean_number(g('ROI')) or clean_number(g('投产'))

            if gmv is not None or total_uv is not None:
                existing_dm = session.query(DailyMetrics).filter(DailyMetrics.date == date).first()
                if existing_dm:
                    if gmv is not None: existing_dm.gmv = gmv
                    if total_uv is not None: existing_dm.total_uv = total_uv
                    if buyers is not None: existing_dm.buyers = buyers
                    if conversion_rate is not None: existing_dm.conversion_rate = conversion_rate
                    if ad_spend is not None: existing_dm.ad_spend = ad_spend
                    if ad_roi is not None: existing_dm.ad_roi = ad_roi
                    existing_dm.updated_at = datetime.now()
                else:
                    new_dm = DailyMetrics(
                        date=date,
                        gmv=gmv,
                        total_uv=total_uv,
                        buyers=buyers,
                        conversion_rate=conversion_rate,
                        ad_spend=ad_spend,
                        ad_roi=ad_roi
                    )
                    session.add(new_dm)
                
                total += 1

    if total > 0:
        print(f"  ✅ 店铺日数据: {total} 条 (日期: {date})")
        session.commit()

    return total


# ==========================================
# 5. TOP N 商品导入
# ==========================================
def import_topn_items(filepath, session):
    """导入TOP N商品到ProductRanking和MonthlyData"""
    month = extract_date_from_filename(filepath)
    if not month:
        month = datetime.now().strftime("%Y-%m")

    xls = load_excel_file(filepath)
    if not xls:
        return 0

    total = 0

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        except Exception as e:
            print(f"  跳过工作表 {sheet_name}: {e}")
            continue

        header_row, id_col = find_header_row(df, ['商品ID', '宝贝ID', '货号', '排名'])
        if header_row is None:
            continue

        df.columns = df.iloc[header_row].astype(str).tolist()
        df = df.iloc[header_row + 1:].reset_index(drop=True)
        col_map = {str(col).strip(): i for i, col in enumerate(df.columns)}

        rows_imported = 0
        current_rank = 0
        for _, row in df.iterrows():
            current_rank += 1
            pid = clean_str(row.iloc[id_col]) if id_col < len(row) else None
            
            if not pid or pid.lower() in ['nan', '']:
                continue

            def g(col_pattern):
                for col_name, idx in col_map.items():
                    if col_pattern in col_name:
                        return row.iloc[idx] if idx < len(row) else None
                return None

            title = clean_str(g('商品标题')) or clean_str(g('标题'))
            sales_30d = clean_int(g('交易金额')) or clean_int(g('支付金额')) or clean_int(g('GMV'))
            
            # ProductRanking表
            existing_rank = session.query(ProductRanking).filter(ProductRanking.product_id == pid).first()
            if existing_rank:
                existing_rank.title = title or existing_rank.title
                existing_rank.sales_30d = sales_30d or existing_rank.sales_30d
                existing_rank.sales_rank = current_rank
                existing_rank.updated_at = datetime.now()
            else:
                new_rank = ProductRanking(
                    product_id=pid,
                    title=title,
                    sales_30d=sales_30d,
                    sales_rank=current_rank
                )
                session.add(new_rank)

            # 同时也更新Products表
            if title:
                existing_product = session.query(Product).filter(Product.product_id == pid).first()
                if existing_product:
                    if title: existing_product.title = title
                else:
                    session.add(Product(product_id=pid, title=title, status='active'))

            rows_imported += 1
            total += 1

        if rows_imported > 0:
            print(f"  ✅ {sheet_name}: {rows_imported} 条TOP商品")
            session.commit()

    return total


# ==========================================
# 6. ZIP压缩包处理
# ==========================================
def extract_and_import_zip(zip_filepath, session):
    """解压ZIP文件并导入其中的Excel文件"""
    grand_total = 0
    stats = {
        'smart_selection': 0,
        'traffic_source': 0,
        'search_ranking': 0,
        'shop_daily': 0,
        'topn_items': 0,
        'unknown': 0
    }
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix='haibeihai_import_')
    
    try:
        print(f"📦 解压ZIP文件: {os.path.basename(zip_filepath)}")
        
        with zipfile.ZipFile(zip_filepath, 'r') as zf:
            # 提取所有文件
            zf.extractall(temp_dir)
            
            # 查找解压后的Excel文件
            excel_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.xlsx', '.xls')):
                        excel_files.append(os.path.join(root, file))
            
            print(f"   在压缩包中找到 {len(excel_files)} 个Excel文件\n")
            
            # 导入每个Excel文件
            for filepath in sorted(excel_files):
                filename = os.path.basename(filepath)
                file_type = classify_file(filename)
                
                print(f"▶️  处理 (压缩包内): {filename}")
                print(f"   类型: {file_type}")
                
                try:
                    imported = 0
                    
                    if file_type == 'smart_selection':
                        imported = import_smart_selection(filepath, session)
                    
                    elif file_type in ['traffic_source']:
                        imported = import_traffic_source(filepath, session)
                    
                    elif file_type in ['search_ranking']:
                        imported = import_search_ranking(filepath, session)
                    
                    elif file_type in ['shop_daily']:
                        imported = import_shop_daily(filepath, session)
                    
                    elif file_type in ['topn_items']:
                        imported = import_topn_items(filepath, session)
                    
                    else:
                        try:
                            imported = import_smart_selection(filepath, session)
                            if imported == 0:
                                imported = import_traffic_source(filepath, session)
                        except Exception:
                            pass
                    
                    if file_type in stats:
                        stats[file_type] += imported
                    else:
                        stats['unknown'] += imported
                    
                    grand_total += imported
                    
                except Exception as e:
                    print(f"  ❌ 处理失败: {e}")
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return grand_total, stats


# ==========================================
# 主导入函数
# ==========================================
def import_directory(source_dir, session):
    """导入整个目录的所有数据"""
    print(f"\n📂 扫描目录: {source_dir}")

    # 查找所有Excel文件
    excel_files = []
    for ext in ['*.xlsx', '*.xls']:
        excel_files.extend(glob.glob(os.path.join(source_dir, ext)))

    # 查找所有ZIP文件
    zip_files = []
    for ext in ['*.zip']:
        zip_files.extend(glob.glob(os.path.join(source_dir, ext)))

    print(f"🔍 找到 {len(excel_files)} 个Excel文件, {len(zip_files)} 个ZIP文件\n")

    grand_total = 0
    stats = {
        'smart_selection': 0,
        'traffic_source': 0,
        'search_ranking': 0,
        'shop_daily': 0,
        'topn_items': 0,
        'zip': 0,
        'unknown': 0
    }

    for filepath in sorted(excel_files):
        filename = os.path.basename(filepath)
        file_type = classify_file(filename)
        
        print(f"▶️  处理: {filename}")
        print(f"   类型: {file_type}")
        
        try:
            imported = 0
            
            if file_type == 'smart_selection':
                imported = import_smart_selection(filepath, session)
            
            elif file_type in ['traffic_source']:
                imported = import_traffic_source(filepath, session)
            
            elif file_type in ['search_ranking']:
                imported = import_search_ranking(filepath, session)
            
            elif file_type in ['shop_daily']:
                imported = import_shop_daily(filepath, session)
            
            elif file_type in ['topn_items']:
                imported = import_topn_items(filepath, session)
            
            else:
                # 未知类型，尝试通用导入（先用智能选款的方式）
                try:
                    imported = import_smart_selection(filepath, session)
                    if imported == 0:
                        imported = import_traffic_source(filepath, session)
                except Exception:
                    pass
            
            if file_type in stats:
                stats[file_type] += imported
            else:
                stats['unknown'] += imported
            
            grand_total += imported
            
        except Exception as e:
            print(f"  ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 处理ZIP文件
    for filepath in sorted(zip_files):
        filename = os.path.basename(filepath)
        
        print(f"\n📦 处理压缩包: {filename}")
        
        try:
            zip_total, zip_stats = extract_and_import_zip(filepath, session)
            
            # 合并统计
            for k, v in zip_stats.items():
                if k in stats:
                    stats[k] += v
                else:
                    stats[k] = v
            
            if zip_total > 0:
                stats['zip'] += 1
            
            grand_total += zip_total
            
        except Exception as e:
            print(f"  ❌ 处理压缩包失败: {e}")
            import traceback
            traceback.print_exc()

    return grand_total, stats


def print_summary(stats, grand_total):
    """打印统计信息"""
    print("\n" + "="*60)
    print("📊 导入统计")
    print("="*60)
    type_names = {
        'smart_selection': '智能选款',
        'traffic_source': '流量来源',
        'search_ranking': '搜索排行',
        'shop_daily': '店铺日数据',
        'topn_items': 'TOP商品',
        'zip': '压缩包',
        'unknown': '其他'
    }
    for k, v in stats.items():
        if v > 0:
            if k == 'zip':
                print(f"  {type_names.get(k, k)}: {v} 个压缩包处理成功")
            else:
                print(f"  {type_names.get(k, k)}: {v} 条")
    print(f"\n✨ 总计: {grand_total} 条数据导入成功")
    print("="*60)


# ==========================================
# 入口
# ==========================================
if __name__ == '__main__':
    print("="*60)
    print("海贝海数据导入脚本 - 新架构")
    print("="*60)

    # 确保数据目录存在
    os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'data', 'db'), exist_ok=True)

    # 创建所有表（如果不存在）
    print("\n🔧 初始化数据库...")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建/验证成功")

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        source_dir = r"F:\bi\海贝海\原始数据"

        # 命令行参数支持自定义源目录
        if len(sys.argv) > 1:
            source_dir = sys.argv[1]

        if os.path.exists(source_dir):
            grand_total, stats = import_directory(source_dir, session)
            print_summary(stats, grand_total)
        else:
            print(f"\n❌ 源目录不存在: {source_dir}")
            print("\n使用示例:")
            print("  python import_raw_data.py")
            print("  python import_raw_data.py \"C:\\Path\\To\\Data\"")

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断操作")
        session.rollback()
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()
        print("\n✅ 导入过程结束")
