#!/usr/bin/env python3
"""
海贝海数据导入脚本 - 完整版
支持从原始Excel文件导入所有数据到数据库

使用方法:
    python import_complete.py                          # 导入所有数据
    python import_complete.py --smart                  # 仅导入智能选款数据
    python import_complete.py --dmp                    # 仅导入DMP数据
    python import_complete.py --paid                  # 仅导入付费推广数据
    python import_complete.py --weekly                 # 仅导入周报数据
    python import_complete.py --monthly                # 仅导入月度历史数据
    python import_complete.py --data-dir /path/to/dir  # 指定数据目录
"""

import pandas as pd
import sys
import os
import re
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine, Base
from app.models import (
    Product, ProductMonthlySummary, DailyData, WeeklyData, MonthlyData,
    DMPProductData, AdData, KeywordAdData, AudienceAdData, SmartAdData,
    AIPLStats
)


def safe_float(val, default=0.0):
    """安全转换为浮点数，处理百分比和千分位"""
    if pd.isna(val) or val == '' or val == '-':
        return default
    val_str = str(val).strip()
    val_str = val_str.replace(',', '').replace('%', '').replace(' ', '')
    if val_str == '' or val_str == '-' or val_str == 'N/A':
        return default
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    """安全转换为整数，处理千分位"""
    if pd.isna(val) or val == '' or val == '-':
        return default
    val_str = str(val).strip().replace(',', '').replace(' ', '')
    if val_str == '' or val_str == '-':
        return default
    try:
        return int(float(val_str))
    except (ValueError, TypeError):
        return default


def safe_str(val, default=''):
    """安全转换为字符串"""
    if pd.isna(val) or val is None:
        return default
    return str(val).strip()


def parse_percentage(val):
    """解析百分比字符串为浮点数"""
    if pd.isna(val) or val == '' or val == '-':
        return 0.0
    val_str = str(val).strip().replace('%', '').replace(' ', '')
    if val_str == '' or val_str == 'N/A':
        return 0.0
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def extract_product_id(val):
    """从各种格式中提取商品ID"""
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    match = re.search(r'\d{10,}', val_str)
    return match.group() if match else None


def calculate_roi(sales, cost):
    """计算ROI，处理空值情况"""
    if cost <= 0 or pd.isna(cost):
        return None
    if sales <= 0 or pd.isna(sales):
        return 0.0
    return round(sales / cost, 2)


def calculate_score(payment_amount, visitors, conversion, ad_spend):
    """综合计算商品评分"""
    score = 0
    if payment_amount > 10000:
        score += 25
    elif payment_amount > 5000:
        score += 20
    elif payment_amount > 1000:
        score += 15
    else:
        score += 10

    if visitors > 1000:
        score += 20
    elif visitors > 500:
        score += 15
    elif visitors > 100:
        score += 10
    else:
        score += 5

    if conversion > 5:
        score += 25
    elif conversion > 3:
        score += 20
    elif conversion > 1:
        score += 15
    else:
        score += 10

    if ad_spend > 0:
        roi = payment_amount / ad_spend if ad_spend > 0 else 0
        if roi > 5:
            score += 30
        elif roi > 3:
            score += 25
        elif roi > 1:
            score += 20
        else:
            score += 15
    else:
        score += 25

    return min(score, 100)


class DataImporter:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent.parent / 'legacy' / 'data' / 'raw'
        self.stats = {
            'products': 0,
            'daily_data': 0,
            'weekly_data': 0,
            'monthly_data': 0,
            'dmp_data': 0,
            'ad_data': 0
        }
        self.db = SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def import_all(self):
        """导入所有数据"""
        print("=" * 80)
        print("海贝海数据导入工具 - 完整版")
        print(f"数据目录: {self.data_dir}")
        print("=" * 80)

        self.import_smart_selection()
        self.import_weekly_report()
        self.import_monthly_history()
        self.import_dmp_data()
        self.import_paid_data()

        self.print_stats()

    def import_smart_selection(self):
        """导入智能选款日报数据"""
        print("\n[1/5] 导入智能选款数据...")

        smart_files = list(self.data_dir.glob('*_智能选款_*.xlsx'))
        if not smart_files:
            print("  未找到智能选款文件，跳过")
            return

        for filepath in sorted(smart_files):
            try:
                df = pd.read_excel(filepath)
                if len(df) == 0:
                    continue

                date_range = filepath.stem.split('_智能选款_')[-1] if '_智能选款_' in filepath.stem else ''
                batch_count = 0

                for _, row in df.iterrows():
                    product_id = extract_product_id(row.get('商品ID') or row.iloc[0])
                    if not product_id:
                        continue

                    payment_amount = safe_float(row.get('支付金额', 0))
                    refund_amount = safe_float(row.get('退款金额', 0))
                    ad_spend = safe_float(row.get('总推广花费', 0))
                    visitors = safe_int(row.get('访客数', 0))
                    conversion = parse_percentage(row.get('支付转化率', 0))
                    ad_roi = safe_float(row.get('推广直接ROI'))

                    if ad_roi == 0 and ad_spend > 0:
                        ad_roi = calculate_roi(payment_amount, ad_spend)

                    existing_product = self.db.query(Product).filter_by(product_id=product_id).first()
                    if not existing_product:
                        product = Product(
                            product_id=product_id,
                            title=safe_str(row.get('商品标题', '')),
                            category=safe_str(row.get('商品类目', '')),
                            list_date=safe_str(row.get('上架时间', '')),
                            tier=safe_str(row.get('分层', '')),
                            image_url=safe_str(row.get('图片链接', '')),
                            score=calculate_score(payment_amount, visitors, conversion, ad_spend),
                            repurchase_rate=parse_percentage(row.get('复购率', 0)),
                            cross_sell_rate=parse_percentage(row.get('连带率', 0)),
                            new_customer_cost=safe_float(row.get('拉新成本', 0)),
                            direct_cart_cost=safe_float(row.get('直接加购成本', 0)),
                            total_cart_cost=safe_float(row.get('总加购成本', 0)),
                        )
                        self.db.add(product)
                        self.stats['products'] += 1

                    daily = DailyData(
                        product_id=product_id,
                        date=date_range.split('~')[0] if '~' in date_range else date_range,
                        payment_amount=payment_amount,
                        refund_amount=refund_amount,
                        net_sales=payment_amount - refund_amount,
                        ad_spend=ad_spend,
                        ad_roi=ad_roi if ad_roi else 0,
                        direct_roi=ad_roi if ad_roi else 0,
                        total_roi=calculate_roi(payment_amount, ad_spend) or 0,
                        visitors=visitors,
                        ipv=visitors,
                        pv=safe_int(row.get('浏览量', 0)),
                        payment_conversion=conversion,
                        cart_rate=parse_percentage(row.get('加购率', 0)),
                        fav_rate=parse_percentage(row.get('访客收藏率', 0)),
                        bounce_rate=parse_percentage(row.get('跳失率', 0)),
                        avg_stay_duration=safe_float(row.get('平均停留时长', 0)),
                        buyers=safe_int(row.get('支付人数', 0)),
                        avg_order_value=safe_float(row.get('客单价', 0)),
                        payment_qty=safe_int(row.get('支付件数', 0)),
                        cart_qty=safe_int(row.get('加购件数', 0)),
                        fav_users=safe_int(row.get('收藏人数', 0)),
                        search_visitors=safe_int(row.get('搜索人数', 0)),
                        search_ratio=parse_percentage(row.get('搜索占比', 0)),
                        search_conversion=parse_percentage(row.get('搜索支付转化率', 0)),
                        uv_value=safe_float(row.get('UV价值', 0)),
                        search_uv_value=safe_float(row.get('搜索UV价值', 0)),
                        impressions=safe_int(row.get('总展现量', 0)),
                        clicks=safe_int(row.get('总点击量', 0)),
                        ctr=parse_percentage(row.get('总点击率', 0)),
                        cart_users=safe_int(row.get('总购物车宝贝数', 0)),
                        store_favs=safe_int(row.get('总收藏店铺数', 0)),
                        total_favs=safe_int(row.get('总收藏数', 0)),
                        fav_cost=safe_float(row.get('总宝贝收藏成本', 0)),
                        data_source='smart_selection',
                    )
                    self.db.add(daily)
                    self.stats['daily_data'] += 1
                    batch_count += 1

                    if batch_count % 100 == 0:
                        self.db.commit()

                self.db.commit()
                print(f"  ✓ {filepath.name}: {batch_count} 条")

            except Exception as e:
                self.db.rollback()
                print(f"  ✗ {filepath.name}: {e}")

    def import_weekly_report(self):
        """导入海贝海周报数据"""
        print("\n[2/5] 导入周报数据...")

        weekly_files = list(self.data_dir.glob('*数据分析表*周*.xlsx'))
        if not weekly_files:
            print("  未找到周报文件，跳过")
            return

        for filepath in weekly_files:
            try:
                df = pd.read_excel(filepath, sheet_name='单品-新')
                if len(df) == 0:
                    continue

                week_date = datetime.now().strftime('%Y-%m-%d')
                batch_count = 0

                for _, row in df.iterrows():
                    product_id = extract_product_id(row.get('商品ID') or row.iloc[2])
                    if not product_id:
                        continue

                    payment_amount = safe_float(row.get('净销售/GSV', 0))

                    weekly = WeeklyData(
                        product_id=product_id,
                        week_start=week_date,
                        payment_amount=payment_amount,
                        refund_amount=safe_float(row.get('退款金额', 0)),
                        net_sales=payment_amount,
                        ad_spend=safe_float(row.get('总推广花费', 0)),
                        ad_roi=safe_float(row.get('推广直接ROI', 0)),
                        total_roi=safe_float(row.get('总投产', 0)),
                        visitors=safe_int(row.get('访客数', 0)),
                        ipv=safe_int(row.get('访客数', 0)),
                        payment_conversion=parse_percentage(row.get('支付转化率', 0)),
                        cart_rate=parse_percentage(row.get('加购率', 0)),
                        uv_value=safe_float(row.get('UV价值', 0)),
                        buyers=safe_int(row.get('支付人数', 0)),
                        avg_order_value=safe_float(row.get('客单价', 0)),
                        action_1=safe_str(row.get('4.17动作', '')),
                        action_2=safe_str(row.get('4.21动作', '')),
                        repurchase_rate=parse_percentage(row.get('复购率', 0)),
                        cross_sell_rate=parse_percentage(row.get('连带率', 0)),
                        new_customer_cost=safe_float(row.get('拉新成本', 0)),
                        direct_cart_cost=safe_float(row.get('直接加购成本', 0)),
                        total_cart_cost=safe_float(row.get('总加购成本', 0)),
                        data_source='weekly_report',
                    )
                    self.db.add(weekly)
                    self.stats['weekly_data'] += 1
                    batch_count += 1

                    if batch_count % 100 == 0:
                        self.db.commit()

                self.db.commit()
                print(f"  ✓ {filepath.name}: {batch_count} 条")

            except Exception as e:
                self.db.rollback()
                print(f"  ✗ {filepath.name}: {e}")

    def import_monthly_history(self):
        """导入月度历史数据"""
        print("\n[3/5] 导入月度历史数据...")

        weekly_files = list(self.data_dir.glob('*数据分析表*周*.xlsx'))
        if not weekly_files:
            print("  未找到月度历史数据文件，跳过")
            return

        for filepath in weekly_files:
            try:
                df = pd.read_excel(filepath, sheet_name='单品-新')
                if len(df) == 0:
                    continue

                month_columns = [col for col in df.columns if re.match(r'\d{2}年-\d{1,2}月', str(col))]
                batch_count = 0

                for _, row in df.iterrows():
                    product_id = extract_product_id(row.get('商品ID') or row.iloc[2])
                    if not product_id:
                        continue

                    for col in month_columns:
                        payment_amount = safe_float(row.get(col, 0))
                        if payment_amount <= 0:
                            continue

                        match = re.match(r'(\d{2})年-(\d{1,2})月', str(col))
                        if match:
                            year = '20' + match.group(1)
                            month = match.group(2).zfill(2)
                            month_str = f"{year}-{month}"

                            monthly = MonthlyData(
                                product_id=product_id,
                                month=month_str,
                                payment_amount=payment_amount,
                                visitors=safe_int(row.get('访客数', 0)),
                                ad_spend=safe_float(row.get('总推广花费', 0)),
                                ad_roi=safe_float(row.get('推广直接ROI', 0)),
                                uv_value=safe_float(row.get('UV价值', 0)),
                                payment_conversion=parse_percentage(row.get('支付转化率', 0)),
                                repurchase_rate=parse_percentage(row.get('复购率', 0)),
                                cross_sell_rate=parse_percentage(row.get('连带率', 0)),
                                data_source='monthly_history',
                            )
                            self.db.add(monthly)
                            self.stats['monthly_data'] += 1
                            batch_count += 1

                            if batch_count % 100 == 0:
                                self.db.commit()

                self.db.commit()
                print(f"  ✓ 月度历史数据: {batch_count} 条")

            except Exception as e:
                self.db.rollback()
                print(f"  ✗ {filepath.name}: {e}")

    def import_dmp_data(self):
        """导入DMP数据"""
        print("\n[4/5] 导入DMP人群数据...")

        weekly_files = list(self.data_dir.glob('*数据分析表*周*.xlsx'))
        for filepath in weekly_files:
            try:
                df = pd.read_excel(filepath, sheet_name='DMP-源')
                if len(df) == 0 or '宝贝ID' not in str(df.columns):
                    continue

                batch_count = 0

                for _, row in df.iterrows():
                    product_id = extract_product_id(row.get('宝贝ID'))
                    if not product_id:
                        continue

                    dmp = DMPProductData(
                        product_id=product_id,
                        product_title=safe_str(row.get('宝贝名称', '')),
                        growth_stage=safe_str(row.get('货品成长阶段', '')),
                        payment_amount=safe_float(row.get('支付金额', 0)),
                        ipv=safe_int(row.get('IPV', 0)),
                        ad_ipv=safe_int(row.get('营销推广IPV', 0)),
                        ad_cost=safe_float(row.get('营销推广消耗', 0)),
                        ad_roi=safe_float(row.get('营销推广ROI', 0)),
                        cart_fav_rate=parse_percentage(row.get('收加率', 0)),
                        payment_conversion=parse_percentage(row.get('支付转化率', 0)),
                        repurchase_rate=parse_percentage(row.get('复购率', 0)),
                        presale_amount=safe_float(row.get('预售支付金额', 0)),
                        presale_qty=safe_int(row.get('预售销量', 0)),
                        organic_ipv=safe_int(row.get('非推广IPV', 0)),
                        search_ipv=safe_int(row.get('搜索IPV', 0)),
                        recommend_ipv=safe_int(row.get('推荐IPV', 0)),
                        search_ctr=parse_percentage(row.get('免费搜索点击率', 0)),
                        unit_price=safe_float(row.get('笔单价', 0)),
                        cross_sell_qty=safe_int(row.get('连带购买量', 0)),
                        cross_sell_rate=parse_percentage(row.get('连带购买率', 0)),
                        cross_sell_categories=safe_int(row.get('连带购买叶子类目宽度', 0)),
                        repurchase_users=safe_int(row.get('复购用户数', 0)),
                        date=datetime.now().strftime('%Y-%m-%d'),
                    )
                    self.db.add(dmp)
                    self.stats['dmp_data'] += 1
                    batch_count += 1

                    if batch_count % 100 == 0:
                        self.db.commit()

                self.db.commit()
                print(f"  ✓ DMP-源: {batch_count} 条")

            except Exception as e:
                self.db.rollback()
                print(f"  ✗ {filepath.name} (DMP-源): {e}")

    def import_paid_data(self):
        """导入付费推广数据"""
        print("\n[5/5] 导入付费推广数据...")

        weekly_files = list(self.data_dir.glob('*数据分析表*周*.xlsx'))
        for filepath in weekly_files:
            try:
                df = pd.read_excel(filepath, sheet_name='付费-源')
                if len(df) == 0:
                    continue

                batch_count = 0

                for _, row in df.iterrows():
                    product_id = extract_product_id(row.iloc[0] if len(row) > 0 else None)
                    if not product_id:
                        continue

                    ad = AdData(
                        product_id=product_id,
                        date_range=datetime.now().strftime('%Y-%m-%d'),
                        impressions=safe_int(row.get('展现量', 0)),
                        clicks=safe_int(row.get('点击量', 0)),
                        cost=safe_float(row.get('花费', 0)),
                        ctr=parse_percentage(row.get('点击率', 0)),
                        cpc=safe_float(row.get('PPC', 0)),
                        total_gmv=safe_float(row.get('成交金额', 0)),
                        total_orders=safe_int(row.get('成交笔数', 0)),
                        roi=safe_float(row.get('ROI', 0)),
                        click_conversion=parse_percentage(row.get('转化率', 0)),
                        cart_adds=safe_int(row.get('加购件数', 0)),
                        favs=safe_int(row.get('收藏数', 0)),
                        store_favs=safe_int(row.get('收藏店铺数', 0)),
                    )
                    self.db.add(ad)
                    self.stats['ad_data'] += 1
                    batch_count += 1

                    if batch_count % 100 == 0:
                        self.db.commit()

                self.db.commit()
                print(f"  ✓ 付费-源: {batch_count} 条")

            except Exception as e:
                self.db.rollback()
                print(f"  ✗ {filepath.name} (付费-源): {e}")

    def print_stats(self):
        """打印导入统计"""
        print("\n" + "=" * 80)
        print("导入完成!")
        print(f"  商品基础信息: {self.stats['products']} 条")
        print(f"  日度销售数据: {self.stats['daily_data']} 条")
        print(f"  周度汇总数据: {self.stats['weekly_data']} 条")
        print(f"  月度历史数据: {self.stats['monthly_data']} 条")
        print(f"  DMP人群数据: {self.stats['dmp_data']} 条")
        print(f"  付费推广数据: {self.stats['ad_data']} 条")
        print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='海贝海数据导入工具')
    parser.add_argument('--data-dir', type=str, default=None, help='数据目录路径')
    parser.add_argument('--smart', action='store_true', help='仅导入智能选款数据')
    parser.add_argument('--dmp', action='store_true', help='仅导入DMP数据')
    parser.add_argument('--paid', action='store_true', help='仅导入付费推广数据')
    parser.add_argument('--weekly', action='store_true', help='仅导入周报数据')
    parser.add_argument('--monthly', action='store_true', help='仅导入月度历史数据')

    args = parser.parse_args()

    with DataImporter(args.data_dir) as importer:
        if args.smart:
            importer.import_smart_selection()
        elif args.dmp:
            importer.import_dmp_data()
        elif args.paid:
            importer.import_paid_data()
        elif args.weekly:
            importer.import_weekly_report()
        elif args.monthly:
            importer.import_monthly_history()
        else:
            importer.import_all()

        importer.print_stats()
