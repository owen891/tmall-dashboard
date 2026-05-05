"""
生意参谋数据导入脚本
支持导入以下数据格式：
1. TOP单品/整体/智能选款 - 商品流量+广告详细数据
2. 来源明细 (top10来源/top20-来源/店铺-来源) - 流量来源数据
3. 品类数据 (品类-整体/品类-来源) - 品类销售+流量数据
4. 店铺日数据 - 店铺每日指标
5. DMP人群数据 - 人群资产数据

使用方法：
  python scripts/import_sycm_data.py [数据目录路径]
"""

import pandas as pd
import sqlite3
import os
import sys
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = r"F:\bi\海贝海\原始数据"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'dashboard.db')


class SycmImporter:
    def __init__(self, data_dir=None, db_path=None):
        self.data_dir = data_dir or DATA_DIR
        self.db_path = db_path or DB_PATH
        self.stats = {
            "traffic_sources": 0,
            "product_traffic_detail": 0,
            "category_data": 0,
            "store_daily_data": 0,
            "keyword_data": 0,
            "dmp_audience": 0,
            "errors": 0,
            "files_processed": 0
        }

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def safe_float(self, val, default=0.0):
        try:
            if pd.isna(val) or val == '' or val == '-':
                return default
            val_str = str(val).replace(',', '')
            return float(val_str)
        except (ValueError, TypeError):
            return default

    def safe_int(self, val, default=0):
        try:
            if pd.isna(val) or val == '' or val == '-':
                return default
            val_str = str(val).replace(',', '')
            return int(float(val_str))
        except (ValueError, TypeError):
            return default

    def normalize_date(self, date_str):
        if pd.isna(date_str):
            return str(datetime.now().date())
        date_str = str(date_str).strip()
        
        if '~' in date_str:
            parts = date_str.split('~')
            return parts[0].strip()
        
        try:
            dt = pd.to_datetime(date_str)
            return dt.strftime('%Y-%m-%d')
        except:
            return date_str

    def extract_product_id(self, val):
        if pd.isna(val):
            return None
        val_str = str(val).strip()
        match = re.search(r'\d{10,}', val_str)
        return match.group() if match else val_str

    def import_top_products(self, filepath):
        print(f"  导入 TOP单品/智能选款: {os.path.basename(filepath)}")
        try:
            xl = pd.ExcelFile(filepath)
            sheet_name = xl.sheet_names[0] if xl.sheet_names else None
            if not sheet_name:
                return
            
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
            
            conn = self.get_connection()
            inserted = 0
            
            for _, row in df.iterrows():
                product_id = self.extract_product_id(row.get('商品ID'))
                if not product_id:
                    continue
                
                date = self.normalize_date(row.get('统计日期'))
                
                conn.execute("""
                    INSERT INTO product_traffic_detail (
                        date, product_id, store_name, traffic_period,
                        platform_traffic, platform_traffic_ratio, ad_traffic, ad_traffic_ratio,
                        search_visitors, search_cart_users, search_payment_amount,
                        search_payment_items, search_payment_buyers,
                        recommend_visitors, recommend_cart_users, recommend_payment_amount,
                        recommend_payment_items, recommend_payment_buyers,
                        payment_amount, payment_items, payment_buyers, refund_amount,
                        cart_items, cart_users, visitors, page_views,
                        conversion_rate, aov, favorite_users, uv_value,
                        ad_spend, ad_ratio, ad_roi, impressions, clicks, ctr, cpc, cpm,
                        total_cart_users, total_favorite_users, favorite_cart_cost,
                        ad_total_sales, ad_orders, ad_cvr,
                        keyword_ad_spend, keyword_ad_roi, keyword_ad_visitors,
                        keyword_ad_cart_users, keyword_ad_sales, keyword_ad_orders, keyword_ad_cvr,
                        audience_ad_spend, audience_ad_roi, audience_ad_visitors,
                        audience_ad_cart_users, audience_ad_sales, audience_ad_orders, audience_ad_cvr,
                        scene_ad_spend, scene_ad_roi, scene_ad_visitors,
                        scene_ad_cart_users, scene_ad_sales, scene_ad_orders, scene_ad_cvr,
                        full_site_ad_spend, full_site_ad_roi, full_site_ad_visitors,
                        full_site_ad_cart_users, full_site_ad_sales, full_site_ad_orders, full_site_ad_cvr,
                        data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date, product_id,
                    str(row.get('店铺名称', '')),
                    str(row.get('流量时期', '')),
                    self.safe_int(row.get('平台流量')),
                    self.safe_float(row.get('平台流量占比')),
                    self.safe_int(row.get('广告流量')),
                    self.safe_float(row.get('广告流量占比')),
                    self.safe_int(row.get('搜索访客数')),
                    self.safe_int(row.get('搜索加购人数')),
                    self.safe_float(row.get('搜索支付金额')),
                    self.safe_int(row.get('搜索支付件数')),
                    self.safe_int(row.get('搜索支付人数')),
                    self.safe_int(row.get('推荐访客数')),
                    self.safe_int(row.get('推荐加购人数')),
                    self.safe_float(row.get('推荐支付金额')),
                    self.safe_int(row.get('推荐支付件数')),
                    self.safe_int(row.get('推荐支付人数')),
                    self.safe_float(row.get('支付金额')),
                    self.safe_int(row.get('支付件数')),
                    self.safe_int(row.get('支付人数')),
                    self.safe_float(row.get('成功退款金额')),
                    self.safe_int(row.get('加购件数')),
                    self.safe_int(row.get('加购人数')),
                    self.safe_int(row.get('商品访客数')),
                    self.safe_int(row.get('商品浏览量')),
                    self.safe_float(row.get('支付转化率')),
                    self.safe_float(row.get('客单价')),
                    self.safe_int(row.get('商品收藏人数')),
                    self.safe_float(row.get('UV价值')),
                    self.safe_float(row.get('推广消耗金额')),
                    self.safe_float(row.get('推广费比')),
                    self.safe_float(row.get('推广ROI')),
                    self.safe_int(row.get('展现量')),
                    self.safe_int(row.get('点击量')),
                    self.safe_float(row.get('点击率')),
                    self.safe_float(row.get('平均点击花费')),
                    self.safe_float(row.get('无界推广CPM')),
                    self.safe_int(row.get('推广总加购数')),
                    self.safe_int(row.get('无界推广收藏数')),
                    self.safe_float(row.get('无界收藏加购成本')),
                    self.safe_float(row.get('推广引导总成交金额')),
                    self.safe_int(row.get('总成交笔数')),
                    self.safe_float(row.get('无界推广CVR')),
                    self.safe_float(row.get('关键词推广花费')),
                    self.safe_float(row.get('关键词推广ROI')),
                    self.safe_int(row.get('关键词推广访客数')),
                    self.safe_int(row.get('关键词推广加购人数')),
                    self.safe_float(row.get('关键词推广支付金额')),
                    self.safe_int(row.get('关键词推广支付件数')),
                    self.safe_float(row.get('关键词推广CVR')),
                    self.safe_float(row.get('人群推广花费')),
                    self.safe_float(row.get('人群推广ROI')),
                    self.safe_int(row.get('人群推广访客数')),
                    self.safe_int(row.get('人群推广加购人数')),
                    self.safe_float(row.get('人群推广支付金额')),
                    self.safe_int(row.get('人群推广支付件数')),
                    self.safe_float(row.get('人群推广CVR')),
                    self.safe_float(row.get('场景推广花费')),
                    self.safe_float(row.get('场景推广ROI')),
                    self.safe_int(row.get('场景推广访客数')),
                    self.safe_int(row.get('场景推广加购人数')),
                    self.safe_float(row.get('场景推广支付金额')),
                    self.safe_int(row.get('场景推广支付件数')),
                    self.safe_float(row.get('场景推广CVR')),
                    self.safe_float(row.get('全站推广花费')),
                    self.safe_float(row.get('全站推广ROI')),
                    self.safe_int(row.get('全站推广访客数')),
                    self.safe_int(row.get('全站推广加购数')),
                    self.safe_float(row.get('全站推广支付金额')),
                    self.safe_int(row.get('全站推广支付件数')),
                    self.safe_float(row.get('全站推广CVR')),
                    'sycm_import'
                ))
                inserted += 1
            
            conn.commit()
            conn.close()
            self.stats["product_traffic_detail"] += inserted
            print(f"    ✓ 插入 {inserted} 条商品流量明细数据")
            
        except Exception as e:
            print(f"    ✗ 导入失败: {e}")
            self.stats["errors"] += 1

    def import_traffic_source(self, filepath):
        print(f"  导入流量来源: {os.path.basename(filepath)}")
        try:
            xl = pd.ExcelFile(filepath)
            sheet_name = xl.sheet_names[0] if xl.sheet_names else None
            if not sheet_name:
                return
            
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
            
            conn = self.get_connection()
            inserted = 0
            
            for _, row in df.iterrows():
                product_id = self.extract_product_id(row.get('商品ID'))
                date = self.normalize_date(row.get('统计日期'))
                
                conn.execute("""
                    INSERT INTO traffic_sources (
                        date, product_id, store_name, traffic_period, source_type,
                        parent_source, source_name, source_level,
                        visitors, new_visitors, page_views, avg_stay_duration,
                        visitors_3s_view, product_click_users, payment_buyers,
                        payment_amount, followers, favorite_users, cart_users,
                        cart_items, conversion_rate, uv_value, aov, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    product_id,
                    str(row.get('店铺名称', '')),
                    str(row.get('流量时期', '')),
                    str(row.get('来源类型', '')),
                    str(row.get('上级来源名称', '')),
                    str(row.get('来源名称', '')),
                    self.safe_int(row.get('来源层级')),
                    self.safe_int(row.get('访客数')),
                    self.safe_int(row.get('新访客数')),
                    self.safe_int(row.get('浏览量')),
                    self.safe_float(row.get('平均停留时长')),
                    self.safe_int(row.get('3秒查看人数')),
                    self.safe_int(row.get('商品点击人数')),
                    self.safe_int(row.get('支付买家数')),
                    self.safe_float(row.get('支付金额')),
                    self.safe_int(row.get('关注店铺人数')),
                    self.safe_int(row.get('商品收藏人数')),
                    self.safe_int(row.get('加购人数')),
                    self.safe_int(row.get('加购件数')),
                    self.safe_float(row.get('支付转化率')),
                    self.safe_float(row.get('UV价值')),
                    self.safe_float(row.get('客单价')),
                    'sycm_import'
                ))
                inserted += 1
            
            conn.commit()
            conn.close()
            self.stats["traffic_sources"] += inserted
            print(f"    ✓ 插入 {inserted} 条流量来源数据")
            
        except Exception as e:
            print(f"    ✗ 导入失败: {e}")
            self.stats["errors"] += 1

    def import_category_data(self, filepath):
        print(f"  导入品类数据: {os.path.basename(filepath)}")
        try:
            xl = pd.ExcelFile(filepath)
            sheet_name = xl.sheet_names[0] if xl.sheet_names else None
            if not sheet_name:
                return
            
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
            
            conn = self.get_connection()
            inserted = 0
            
            for _, row in df.iterrows():
                date = self.normalize_date(row.get('统计日期'))
                
                conn.execute("""
                    INSERT INTO category_data (
                        date, store_name, category_name, category_level,
                        parent_category, level1_category, level2_category,
                        source_name, parent_source, source_level,
                        favorite_users, cart_users, payment_buyers, payment_amount,
                        visitors, favorite_conversion, cart_conversion,
                        payment_conversion, uv_value, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    str(row.get('店铺名称', '')),
                    str(row.get('类目名称', '')),
                    self.safe_int(row.get('类目层级')),
                    str(row.get('父类目名称', '')),
                    str(row.get('一级类目名称', '')),
                    str(row.get('二级类目名称', '')),
                    str(row.get('来源名称', '')),
                    str(row.get('上级来源名称', '')),
                    self.safe_int(row.get('来源层级')),
                    self.safe_int(row.get('收藏人数')),
                    self.safe_int(row.get('加购人数')),
                    self.safe_int(row.get('支付人数')),
                    self.safe_float(row.get('支付金额')),
                    self.safe_int(row.get('访客数')),
                    self.safe_float(row.get('访问收藏转化率')),
                    self.safe_float(row.get('访问加购转化率')),
                    self.safe_float(row.get('支付转化率')),
                    self.safe_float(row.get('UV价值')),
                    'sycm_import'
                ))
                inserted += 1
            
            conn.commit()
            conn.close()
            self.stats["category_data"] += inserted
            print(f"    ✓ 插入 {inserted} 条品类数据")
            
        except Exception as e:
            print(f"    ✗ 导入失败: {e}")
            self.stats["errors"] += 1

    def import_store_daily(self, filepath):
        print(f"  导入店铺日数据: {os.path.basename(filepath)}")
        try:
            xl = pd.ExcelFile(filepath)
            sheet_name = xl.sheet_names[0] if xl.sheet_names else None
            if not sheet_name:
                return
            
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
            
            conn = self.get_connection()
            inserted = 0
            
            for _, row in df.iterrows():
                date = self.normalize_date(row.get('统计日期'))
                
                conn.execute("""
                    INSERT INTO store_daily_data (
                        date, store_name, visitors, new_visitors, page_views,
                        avg_stay_duration, visitors_3s, product_click_users,
                        payment_buyers, payment_amount, followers, favorite_users,
                        cart_users, cart_items, conversion_rate, uv_value, aov,
                        data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    str(row.get('店铺名称', '')),
                    self.safe_int(row.get('访客数')),
                    self.safe_int(row.get('新访客数')),
                    self.safe_int(row.get('浏览量')),
                    self.safe_float(row.get('平均停留时长')),
                    self.safe_int(row.get('3秒查看人数')),
                    self.safe_int(row.get('商品点击人数')),
                    self.safe_int(row.get('支付买家数')),
                    self.safe_float(row.get('支付金额')),
                    self.safe_int(row.get('关注店铺人数')),
                    self.safe_int(row.get('商品收藏人数')),
                    self.safe_int(row.get('加购人数')),
                    self.safe_int(row.get('加购件数')),
                    self.safe_float(row.get('支付转化率')),
                    self.safe_float(row.get('UV价值')),
                    self.safe_float(row.get('客单价')),
                    'sycm_import'
                ))
                inserted += 1
            
            conn.commit()
            conn.close()
            self.stats["store_daily_data"] += inserted
            print(f"    ✓ 插入 {inserted} 条店铺日数据")
            
        except Exception as e:
            print(f"    ✗ 导入失败: {e}")
            self.stats["errors"] += 1

    def run(self):
        print("=" * 70)
        print("生意参谋数据导入工具")
        print("=" * 70)
        print(f"数据目录: {self.data_dir}\n")
        
        files = os.listdir(self.data_dir)
        
        top_files = [f for f in files if any(k in f for k in ['TOP10', 'TOP50', 'top', '智能选款']) and f.endswith('.xlsx')]
        source_files = [f for f in files if '来源' in f and f.endswith('.xlsx')]
        category_files = [f for f in files if '品类' in f and f.endswith('.xlsx')]
        store_files = [f for f in files if '店铺' in f and '日' in f and f.endswith('.xlsx')]
        
        print(f"发现文件:")
        print(f"  - TOP单品/智能选款: {len(top_files)} 个")
        print(f"  - 来源明细: {len(source_files)} 个")
        print(f"  - 品类数据: {len(category_files)} 个")
        print(f"  - 店铺日数据: {len(store_files)} 个")
        print()
        
        for f in top_files:
            try:
                self.import_top_products(os.path.join(self.data_dir, f))
                self.stats["files_processed"] += 1
            except Exception as e:
                print(f"  ✗ 处理失败 {f}: {e}")
                self.stats["errors"] += 1
        
        for f in source_files:
            try:
                self.import_traffic_source(os.path.join(self.data_dir, f))
                self.stats["files_processed"] += 1
            except Exception as e:
                print(f"  ✗ 处理失败 {f}: {e}")
                self.stats["errors"] += 1
        
        for f in category_files:
            try:
                self.import_category_data(os.path.join(self.data_dir, f))
                self.stats["files_processed"] += 1
            except Exception as e:
                print(f"  ✗ 处理失败 {f}: {e}")
                self.stats["errors"] += 1
        
        for f in store_files:
            try:
                self.import_store_daily(os.path.join(self.data_dir, f))
                self.stats["files_processed"] += 1
            except Exception as e:
                print(f"  ✗ 处理失败 {f}: {e}")
                self.stats["errors"] += 1
        
        print("\n" + "=" * 70)
        print("导入统计:")
        print("=" * 70)
        print(f"  处理文件数: {self.stats['files_processed']}")
        print(f"  流量来源数据: {self.stats['traffic_sources']} 条")
        print(f"  商品流量明细: {self.stats['product_traffic_detail']} 条")
        print(f"  品类数据: {self.stats['category_data']} 条")
        print(f"  店铺日数据: {self.stats['store_daily_data']} 条")
        print(f"  错误数: {self.stats['errors']}")
        print("=" * 70)


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else DATA_DIR
    importer = SycmImporter(data_dir=data_dir)
    importer.run()
