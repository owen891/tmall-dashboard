#!/usr/bin/env python3
"""
从老版本数据库完整迁移所有数据到新系统
"""

import sys
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal, engine, Base
from app.models import (
    Product, DailyData, WeeklyData, MonthlyData,
    ProductTag, OperationAction, ProductNote, ProductHealth,
    PaidDetail, ShopTarget, ProductTarget, Alert, AlertRule,
    Review, ReviewSummary, MarketAnalysis, MarketKeywordOpportunity
)

OLD_DB_PATH = str(Path(__file__).parent / "../legacy/data/dashboard.db")


def parse_json_field(value):
    """解析JSON字段，处理可能的错误"""
    if not value:
        return [] if value in (None, "", "[]") else value
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except Exception:
        return []


def parse_date(value):
    """解析日期，处理各种格式"""
    if not value or value in ("-", "", "None", "null"):
        return None
    try:
        if isinstance(value, str) and len(value) >= 10:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        return None
    except Exception:
        return None


def parse_datetime(value):
    """解析日期时间，处理各种格式"""
    if not value or value in ("-", "", "None", "null"):
        return None
    try:
        if isinstance(value, str):
            if len(value) >= 19:
                return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
            elif len(value) >= 10:
                return datetime.strptime(value[:10], "%Y-%m-%d")
        return None
    except Exception:
        return None


def migrate_products(old_conn, new_db):
    """迁移产品表"""
    print("正在迁移 products...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM products")
    
    count = 0
    seen_product_ids = set()
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        product_id = row_dict["product_id"]
        if product_id in seen_product_ids:
            continue  # 跳过重复的 product_id
        seen_product_ids.add(product_id)
        product = Product(
            product_id=product_id,
            title=row_dict.get("title"),
            category=row_dict.get("category"),
            tier=row_dict.get("tier"),
            style=row_dict.get("style"),
            scene=row_dict.get("scene"),
            list_date=parse_date(row_dict.get("list_date")),
            status=row_dict.get("status", "active"),
            remark=row_dict.get("remark"),
            image_url=row_dict.get("image_url"),
            created_at=parse_datetime(row_dict.get("created_at")),
            updated_at=parse_datetime(row_dict.get("updated_at"))
        )
        new_db.add(product)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 个 products")
    return count


def migrate_daily_data(old_conn, new_db):
    """迁移每日数据"""
    print("正在迁移 daily_data...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM daily_data")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        data = DailyData(
            product_id=row_dict["product_id"],
            date=parse_date(row_dict.get("date")),
            payment_amount=row_dict.get("payment_amount", 0),
            refund_amount=row_dict.get("refund_amount", 0),
            net_sales=row_dict.get("net_sales", 0),
            payment_qty=row_dict.get("payment_qty", 0),
            ipv=row_dict.get("ipv", 0),
            pv=row_dict.get("pv", 0),
            search_ipv=row_dict.get("search_ipv", 0),
            recommend_ipv=row_dict.get("recommend_ipv", 0),
            paid_ipv=row_dict.get("paid_ipv", 0),
            organic_ipv=row_dict.get("organic_ipv", 0),
            payment_conversion=row_dict.get("payment_conversion", 0),
            cart_rate=row_dict.get("cart_rate", 0),
            fav_rate=row_dict.get("fav_rate", 0),
            bounce_rate=row_dict.get("bounce_rate", 0),
            avg_stay_duration=row_dict.get("avg_stay_duration", 0),
            ad_spend=row_dict.get("ad_spend", 0),
            ad_roi=row_dict.get("ad_roi", 0),
            buyers=row_dict.get("buyers", 0),
            avg_order_value=row_dict.get("avg_order_value", 0),
            data_source=row_dict.get("data_source"),
            imported_at=parse_datetime(row_dict.get("imported_at"))
        )
        new_db.add(data)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 daily_data")
    return count


def migrate_weekly_data(old_conn, new_db):
    """迁移每周数据"""
    print("正在迁移 weekly_data...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM weekly_data")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        data = WeeklyData(
            product_id=row_dict["product_id"],
            week_start=parse_date(row_dict.get("week_start")),
            payment_amount=row_dict.get("payment_amount", 0),
            refund_amount=row_dict.get("refund_amount", 0),
            net_sales=row_dict.get("net_sales", 0),
            presale_amount=row_dict.get("presale_amount", 0),
            presale_qty=row_dict.get("presale_qty", 0),
            ipv=row_dict.get("ipv", 0),
            pv=row_dict.get("pv", 0),
            search_ipv=row_dict.get("search_ipv", 0),
            recommend_ipv=row_dict.get("recommend_ipv", 0),
            paid_ipv=row_dict.get("paid_ipv", 0),
            organic_ipv=row_dict.get("organic_ipv", 0),
            payment_conversion=row_dict.get("payment_conversion", 0),
            cart_rate=row_dict.get("cart_rate", 0),
            fav_rate=row_dict.get("fav_rate", 0),
            search_click_rate=row_dict.get("search_click_rate", 0),
            bounce_rate=row_dict.get("bounce_rate", 0),
            avg_stay_duration=row_dict.get("avg_stay_duration", 0),
            ad_spend=row_dict.get("ad_spend", 0),
            ad_roi=row_dict.get("ad_roi", 0),
            repurchase_rate=row_dict.get("repurchase_rate", 0),
            repurchase_users=row_dict.get("repurchase_users", 0),
            cross_sell_qty=row_dict.get("cross_sell_qty", 0),
            cross_sell_rate=row_dict.get("cross_sell_rate", 0),
            avg_order_value=row_dict.get("avg_order_value", 0),
            category_width=row_dict.get("category_width", 0),
            action_1=row_dict.get("action_1"),
            action_2=row_dict.get("action_2"),
            data_source=row_dict.get("data_source"),
            imported_at=parse_datetime(row_dict.get("imported_at"))
        )
        new_db.add(data)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 weekly_data")
    return count


def migrate_monthly_data(old_conn, new_db):
    """迁移每月数据"""
    print("正在迁移 monthly_data...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM monthly_data")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        data = MonthlyData(
            product_id=row_dict["product_id"],
            month=row_dict["month"],
            payment_amount=row_dict.get("payment_amount", 0),
            refund_amount=row_dict.get("refund_amount", 0),
            net_sales=row_dict.get("net_sales", 0),
            visitors=row_dict.get("visitors", 0),
            page_views=row_dict.get("page_views", 0),
            uv_value=row_dict.get("uv_value", 0),
            search_visitors=row_dict.get("search_visitors", 0),
            search_ratio=row_dict.get("search_ratio", 0),
            payment_conversion=row_dict.get("payment_conversion", 0),
            search_conversion=row_dict.get("search_conversion", 0),
            cart_rate=row_dict.get("cart_rate", 0),
            fav_rate=row_dict.get("fav_rate", 0),
            bounce_rate=row_dict.get("bounce_rate", 0),
            avg_stay_duration=row_dict.get("avg_stay_duration", 0),
            ad_spend=row_dict.get("ad_spend", 0),
            ad_roi=row_dict.get("ad_roi", 0),
            overall_roi=row_dict.get("overall_roi", 0),
            paid_ratio=row_dict.get("paid_ratio", 0),
            refund_paid_ratio=row_dict.get("refund_paid_ratio", 0),
            keyword_spend=row_dict.get("keyword_spend", 0),
            keyword_sales=row_dict.get("keyword_sales", 0),
            keyword_roi=row_dict.get("keyword_roi", 0),
            keyword_visitors=row_dict.get("keyword_visitors", 0),
            keyword_ppc=row_dict.get("keyword_ppc", 0),
            crowd_spend=row_dict.get("crowd_spend", 0),
            crowd_sales=row_dict.get("crowd_sales", 0),
            crowd_roi=row_dict.get("crowd_roi", 0),
            crowd_visitors=row_dict.get("crowd_visitors", 0),
            crowd_ppc=row_dict.get("crowd_ppc", 0),
            site_spend=row_dict.get("site_spend", 0),
            site_sales=row_dict.get("site_sales", 0),
            site_roi=row_dict.get("site_roi", 0),
            site_visitors=row_dict.get("site_visitors", 0),
            site_ppc=row_dict.get("site_ppc", 0),
            refund_rate=row_dict.get("refund_rate", 0),
            repurchase_rate=row_dict.get("repurchase_rate", 0),
            cross_sell_rate=row_dict.get("cross_sell_rate", 0),
            buyers=row_dict.get("buyers", 0),
            avg_order_value=row_dict.get("avg_order_value", 0),
            payment_qty=row_dict.get("payment_qty", 0),
            cart_qty=row_dict.get("cart_qty", 0),
            fav_users=row_dict.get("fav_users", 0),
            click_rate=row_dict.get("click_rate", 0),
            score=row_dict.get("score", 0),
            data_source=row_dict.get("data_source"),
            imported_at=parse_datetime(row_dict.get("imported_at"))
        )
        new_db.add(data)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 monthly_data")
    return count


def migrate_paid_detail(old_conn, new_db):
    """迁移广告详情"""
    print("正在迁移 paid_detail...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM paid_detail")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        data = PaidDetail(
            product_id=row_dict["product_id"],
            date_range=row_dict["date_range"],
            impressions=row_dict.get("impressions", 0),
            clicks=row_dict.get("clicks", 0),
            cost=row_dict.get("cost", 0),
            ctr=row_dict.get("ctr", 0),
            cpc=row_dict.get("cpc", 0),
            cpm=row_dict.get("cpm", 0),
            total_gmv=row_dict.get("total_gmv", 0),
            total_orders=row_dict.get("total_orders", 0),
            direct_gmv=row_dict.get("direct_gmv", 0),
            indirect_gmv=row_dict.get("indirect_gmv", 0),
            roi=row_dict.get("roi", 0),
            cart_adds=row_dict.get("cart_adds", 0),
            cart_rate=row_dict.get("cart_rate", 0),
            favs=row_dict.get("favs", 0),
            new_buyers=row_dict.get("new_buyers", 0),
            members_gmv=row_dict.get("members_gmv", 0),
            imported_at=parse_datetime(row_dict.get("imported_at"))
        )
        new_db.add(data)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 paid_detail")
    return count


def migrate_operation_actions(old_conn, new_db):
    """迁移操作记录"""
    print("正在迁移 operation_actions...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM operation_actions")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        action = OperationAction(
            product_id=row_dict["product_id"],
            action_date=parse_date(row_dict.get("action_date")),
            action_type=row_dict.get("action_type"),
            action_detail=row_dict.get("action_detail"),
            before_payment=row_dict.get("before_payment", 0),
            before_visitors=row_dict.get("before_visitors", 0),
            before_conversion=row_dict.get("before_conversion", 0),
            before_roi=row_dict.get("before_roi", 0),
            after_payment=row_dict.get("after_payment", 0),
            after_visitors=row_dict.get("after_visitors", 0),
            after_conversion=row_dict.get("after_conversion", 0),
            after_roi=row_dict.get("after_roi", 0),
            effectiveness_score=row_dict.get("effectiveness_score", 0),
            created_at=parse_datetime(row_dict.get("imported_at"))
        )
        new_db.add(action)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 operation_actions")
    return count


def migrate_product_notes(old_conn, new_db):
    """迁移商品笔记"""
    print("正在迁移 product_notes...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM product_notes")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        note = ProductNote(
            product_id=row_dict["product_id"],
            note=row_dict["note"],
            created_by=row_dict.get("created_by", "admin"),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(note)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 product_notes")
    return count


def migrate_product_health(old_conn, new_db):
    """迁移健康度"""
    print("正在迁移 product_health...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM product_health")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        health = ProductHealth(
            product_id=row_dict["product_id"],
            period=row_dict["period"],
            sales_score=row_dict.get("sales_score", 0),
            conversion_score=row_dict.get("conversion_score", 0),
            roi_score=row_dict.get("roi_score", 0),
            refund_score=row_dict.get("refund_score", 0),
            growth_score=row_dict.get("growth_score", 0),
            review_score=row_dict.get("review_score", 0),
            gmv_change_score=row_dict.get("gmv_change_score", 0),
            ad_spend_change_score=row_dict.get("ad_spend_change_score", 0),
            roi_change_score=row_dict.get("roi_change_score", 0),
            refund_rate_score=row_dict.get("refund_rate_score", 0),
            cart_rate_score=row_dict.get("cart_rate_score", 0),
            search_ratio_score=row_dict.get("search_ratio_score", 0),
            new_customer_cost_score=row_dict.get("new_customer_cost_score", 0),
            direct_cart_cost_score=row_dict.get("direct_cart_cost_score", 0),
            total_cart_cost_score=row_dict.get("total_cart_cost_score", 0),
            repurchase_rate_score=row_dict.get("repurchase_rate_score", 0),
            cross_sell_rate_score=row_dict.get("cross_sell_rate_score", 0),
            search_ctr_vs_industry_score=row_dict.get("search_ctr_vs_industry_score", 0),
            health_score=row_dict.get("health_score", 0),
            health_level=row_dict.get("health_level"),
            alert_dimensions=parse_json_field(row_dict.get("alert_dimensions")),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(health)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 product_health")
    return count


def migrate_shop_targets(old_conn, new_db):
    """迁移店铺目标"""
    print("正在迁移 shop_targets...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM shop_targets")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        target = ShopTarget(
            period=row_dict["period"],
            target_gsv=row_dict.get("target_gsv", 0),
            target_ad_spend=row_dict.get("target_ad_spend", 0),
            target_ad_ratio=row_dict.get("target_ad_ratio", 0),
            target_conversion=row_dict.get("target_conversion", 0),
            target_refund_rate=row_dict.get("target_refund_rate", 0),
            remark=row_dict.get("remark"),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(target)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 shop_targets")
    return count


def migrate_product_targets(old_conn, new_db):
    """迁移商品目标"""
    print("正在迁移 product_targets...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM product_targets")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        target = ProductTarget(
            product_id=row_dict.get("product_id"),
            tier=row_dict.get("tier"),
            period=row_dict["period"],
            target_gsv=row_dict.get("target_gsv", 0),
            target_ad_spend=row_dict.get("target_ad_spend", 0),
            target_ad_ratio=row_dict.get("target_ad_ratio", 0),
            remark=row_dict.get("remark"),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(target)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 product_targets")
    return count


def migrate_alerts(old_conn, new_db):
    """迁移告警"""
    print("正在迁移 alerts...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM alerts")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        alert = Alert(
            alert_date=parse_date(row_dict.get("alert_date")),
            alert_type=row_dict["alert_type"],
            severity=row_dict.get("severity", "warning"),
            title=row_dict.get("title"),
            detail=row_dict.get("detail"),
            metric_name=row_dict.get("metric_name"),
            current_value=row_dict.get("current_value", 0),
            target_value=row_dict.get("target_value", 0),
            period=row_dict.get("period"),
            dismissed=bool(row_dict.get("dismissed", False)),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(alert)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 alerts")
    return count


def migrate_alert_rules(old_conn, new_db):
    """迁移告警规则"""
    print("正在迁移 alert_rules...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM alert_rules")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        rule = AlertRule(
            metric=row_dict["metric"],
            operator=row_dict["operator"],
            threshold=row_dict["threshold"],
            level=row_dict.get("level", "warning"),
            enabled=bool(row_dict.get("enabled", True)),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(rule)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 alert_rules")
    return count


def migrate_reviews(old_conn, new_db):
    """迁移评价"""
    print("正在迁移 reviews...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM reviews")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        review = Review(
            product_id=row_dict["product_id"],
            review_date=row_dict.get("review_date"),
            content=row_dict["content"],
            rating=row_dict.get("rating", 5),
            reviewer=row_dict.get("reviewer", ""),
            is_effective=bool(row_dict.get("is_effective", True)),
            sentiment=row_dict.get("sentiment", "neutral"),
            positive_dims=parse_json_field(row_dict.get("positive_dims")),
            negative_dims=parse_json_field(row_dict.get("negative_dims")),
            scenes=parse_json_field(row_dict.get("scenes")),
            has_image=bool(row_dict.get("has_image", False)),
            source=row_dict.get("source"),
            imported_at=parse_datetime(row_dict.get("imported_at"))
        )
        new_db.add(review)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 reviews")
    return count


def migrate_review_summaries(old_conn, new_db):
    """迁移评价摘要"""
    print("正在迁移 review_summary...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM review_summary")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        summary = ReviewSummary(
            product_id=row_dict["product_id"],
            analysis_date=row_dict.get("analysis_date"),
            total_reviews=row_dict.get("total_reviews", 0),
            positive_rate=row_dict.get("positive_rate", 0),
            negative_rate=row_dict.get("negative_rate", 0),
            effective_rate=row_dict.get("effective_rate", 0),
            top_positive_dims=parse_json_field(row_dict.get("top_positive_dims")),
            top_negative_dims=parse_json_field(row_dict.get("top_negative_dims")),
            top_scenes=parse_json_field(row_dict.get("top_scenes")),
            updated_at=parse_datetime(row_dict.get("updated_at"))
        )
        new_db.add(summary)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 review_summary")
    return count


def migrate_market_analysis(old_conn, new_db):
    """迁移市场分析"""
    print("正在迁移 market_analysis...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM market_analysis")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        analysis = MarketAnalysis(
            analysis_date=row_dict["analysis_date"],
            category_path=row_dict.get("category_path"),
            category_short=row_dict.get("category_short"),
            period_30d=row_dict.get("period_30d"),
            period_7d=row_dict.get("period_7d"),
            period_trend=row_dict.get("period_trend"),
            total_keywords=row_dict.get("total_keywords", 0),
            avg_ctr_7d=row_dict.get("avg_ctr_7d"),
            avg_cvr_30d=row_dict.get("avg_cvr_30d"),
            top5_keywords=parse_json_field(row_dict.get("top5_keywords")),
            summary_data=parse_json_field(row_dict.get("summary_data")),
            keywords_data=parse_json_field(row_dict.get("keywords_data")),
            need_stats_data=parse_json_field(row_dict.get("need_stats_data")),
            dimension_details=parse_json_field(row_dict.get("dimension_details")),
            histograms_data=parse_json_field(row_dict.get("histograms_data")),
            rankings_data=parse_json_field(row_dict.get("rankings_data")),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(analysis)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 market_analysis")
    return count


def migrate_market_keyword_opportunities(old_conn, new_db):
    """迁移市场关键词机会"""
    print("正在迁移 market_keyword_opportunities...")
    old_cursor = old_conn.cursor()
    old_cursor.execute("SELECT * FROM market_keyword_opportunities")
    
    count = 0
    for row in old_cursor.fetchall():
        row_dict = dict(row)
        opportunity = MarketKeywordOpportunity(
            analysis_date=row_dict["analysis_date"],
            keyword=row_dict["keyword"],
            pop_30d=row_dict.get("pop_30d"),
            ctr_7d=row_dict.get("ctr_7d"),
            cvr_30d=row_dict.get("cvr_30d"),
            opportunity_category=row_dict.get("opportunity_category"),
            opportunity_score=row_dict.get("opportunity_score"),
            need_tags=parse_json_field(row_dict.get("need_tags")),
            created_at=parse_datetime(row_dict.get("created_at"))
        )
        new_db.add(opportunity)
        count += 1
    
    new_db.commit()
    print(f"已迁移 {count} 条 market_keyword_opportunities")
    return count


def main():
    """主函数"""
    print("=" * 60)
    print("开始完整迁移老版本数据库")
    print("=" * 60)
    
    # 检查旧数据库是否存在
    if not os.path.exists(OLD_DB_PATH):
        print(f"错误：找不到老版本数据库 {OLD_DB_PATH}")
        return False
    
    # 删除现有数据库（重新创建）
    db_file = Path(__file__).parent / "data" / "dashboard.db"
    if db_file.exists():
        print(f"删除现有数据库 {db_file}")
        os.remove(db_file)
    
    # 重新创建所有表
    print("正在创建新数据库表...")
    Base.metadata.create_all(bind=engine)
    print("表创建完成")
    
    # 创建新数据库会话
    new_db = SessionLocal()
    
    try:
        # 连接旧数据库
        old_conn = sqlite3.connect(OLD_DB_PATH)
        old_conn.row_factory = sqlite3.Row
        
        total_count = 0
        
        # 迁移所有数据
        total_count += migrate_products(old_conn, new_db)
        total_count += migrate_daily_data(old_conn, new_db)
        total_count += migrate_weekly_data(old_conn, new_db)
        total_count += migrate_monthly_data(old_conn, new_db)
        total_count += migrate_paid_detail(old_conn, new_db)
        total_count += migrate_operation_actions(old_conn, new_db)
        total_count += migrate_product_notes(old_conn, new_db)
        total_count += migrate_product_health(old_conn, new_db)
        total_count += migrate_shop_targets(old_conn, new_db)
        total_count += migrate_product_targets(old_conn, new_db)
        total_count += migrate_alerts(old_conn, new_db)
        total_count += migrate_alert_rules(old_conn, new_db)
        total_count += migrate_reviews(old_conn, new_db)
        total_count += migrate_review_summaries(old_conn, new_db)
        total_count += migrate_market_analysis(old_conn, new_db)
        total_count += migrate_market_keyword_opportunities(old_conn, new_db)
        
        print("=" * 60)
        print(f"✅ 迁移完成！共迁移 {total_count} 条记录")
        print("=" * 60)
        
        old_conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败：{e}")
        import traceback
        traceback.print_exc()
        new_db.rollback()
        return False
        
    finally:
        new_db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
