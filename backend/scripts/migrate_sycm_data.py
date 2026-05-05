"""
生意参谋数据扩展迁移脚本 - 2026-05-04
创建6个新表来支持生意参谋的丰富数据：
1. traffic_sources - 流量来源数据
2. product_traffic_detail - 商品流量+广告详细数据
3. category_data - 品类数据
4. store_daily_data - 店铺日级数据
5. keyword_data - 关键词数据
6. dmp_audience - DMP人群资产数据
"""

import sqlite3
import os
import sys

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'dashboard.db')


def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def table_exists(conn, table_name):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def create_traffic_sources_table(conn):
    if table_exists(conn, 'traffic_sources'):
        print("[SKIP] traffic_sources 表已存在")
        return

    conn.execute("""
        CREATE TABLE traffic_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date VARCHAR NOT NULL,
            product_id VARCHAR,
            store_name VARCHAR,
            traffic_period VARCHAR,
            source_type VARCHAR,
            parent_source VARCHAR,
            source_name VARCHAR NOT NULL,
            source_level INTEGER,
            visitors INTEGER DEFAULT 0,
            new_visitors INTEGER DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            avg_stay_duration FLOAT DEFAULT 0,
            visitors_3s_view INTEGER DEFAULT 0,
            product_click_users INTEGER DEFAULT 0,
            payment_buyers INTEGER DEFAULT 0,
            payment_amount FLOAT DEFAULT 0,
            followers INTEGER DEFAULT 0,
            favorite_users INTEGER DEFAULT 0,
            cart_users INTEGER DEFAULT 0,
            cart_items INTEGER DEFAULT 0,
            conversion_rate FLOAT DEFAULT 0,
            uv_value FLOAT DEFAULT 0,
            aov FLOAT DEFAULT 0,
            data_source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_traffic_date ON traffic_sources(date)")
    conn.execute("CREATE INDEX idx_traffic_product ON traffic_sources(product_id)")
    conn.execute("CREATE INDEX idx_traffic_source ON traffic_sources(source_name)")
    print("[OK] 创建 traffic_sources 表")


def create_product_traffic_detail_table(conn):
    if table_exists(conn, 'product_traffic_detail'):
        print("[SKIP] product_traffic_detail 表已存在")
        return

    conn.execute("""
        CREATE TABLE product_traffic_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date VARCHAR NOT NULL,
            product_id VARCHAR NOT NULL,
            store_name VARCHAR,
            traffic_period VARCHAR,
            platform_traffic INTEGER DEFAULT 0,
            platform_traffic_ratio FLOAT DEFAULT 0,
            ad_traffic INTEGER DEFAULT 0,
            ad_traffic_ratio FLOAT DEFAULT 0,
            search_visitors INTEGER DEFAULT 0,
            search_cart_users INTEGER DEFAULT 0,
            search_payment_amount FLOAT DEFAULT 0,
            search_payment_items INTEGER DEFAULT 0,
            search_payment_buyers INTEGER DEFAULT 0,
            recommend_visitors INTEGER DEFAULT 0,
            recommend_cart_users INTEGER DEFAULT 0,
            recommend_payment_amount FLOAT DEFAULT 0,
            recommend_payment_items INTEGER DEFAULT 0,
            recommend_payment_buyers INTEGER DEFAULT 0,
            payment_amount FLOAT DEFAULT 0,
            payment_items INTEGER DEFAULT 0,
            payment_buyers INTEGER DEFAULT 0,
            refund_amount FLOAT DEFAULT 0,
            cart_items INTEGER DEFAULT 0,
            cart_users INTEGER DEFAULT 0,
            visitors INTEGER DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            conversion_rate FLOAT DEFAULT 0,
            aov FLOAT DEFAULT 0,
            favorite_users INTEGER DEFAULT 0,
            uv_value FLOAT DEFAULT 0,
            ad_spend FLOAT DEFAULT 0,
            ad_ratio FLOAT DEFAULT 0,
            ad_roi FLOAT DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            ctr FLOAT DEFAULT 0,
            cpc FLOAT DEFAULT 0,
            cpm FLOAT DEFAULT 0,
            total_cart_users INTEGER DEFAULT 0,
            total_favorite_users INTEGER DEFAULT 0,
            favorite_cart_cost FLOAT DEFAULT 0,
            ad_total_sales FLOAT DEFAULT 0,
            ad_orders INTEGER DEFAULT 0,
            ad_cvr FLOAT DEFAULT 0,
            keyword_ad_spend FLOAT DEFAULT 0,
            keyword_ad_roi FLOAT DEFAULT 0,
            keyword_ad_visitors INTEGER DEFAULT 0,
            keyword_ad_cart_users INTEGER DEFAULT 0,
            keyword_ad_sales FLOAT DEFAULT 0,
            keyword_ad_orders INTEGER DEFAULT 0,
            keyword_ad_cvr FLOAT DEFAULT 0,
            audience_ad_spend FLOAT DEFAULT 0,
            audience_ad_roi FLOAT DEFAULT 0,
            audience_ad_visitors INTEGER DEFAULT 0,
            audience_ad_cart_users INTEGER DEFAULT 0,
            audience_ad_sales FLOAT DEFAULT 0,
            audience_ad_orders INTEGER DEFAULT 0,
            audience_ad_cvr FLOAT DEFAULT 0,
            scene_ad_spend FLOAT DEFAULT 0,
            scene_ad_roi FLOAT DEFAULT 0,
            scene_ad_visitors INTEGER DEFAULT 0,
            scene_ad_cart_users INTEGER DEFAULT 0,
            scene_ad_sales FLOAT DEFAULT 0,
            scene_ad_orders INTEGER DEFAULT 0,
            scene_ad_cvr FLOAT DEFAULT 0,
            full_site_ad_spend FLOAT DEFAULT 0,
            full_site_ad_roi FLOAT DEFAULT 0,
            full_site_ad_visitors INTEGER DEFAULT 0,
            full_site_ad_cart_users INTEGER DEFAULT 0,
            full_site_ad_sales FLOAT DEFAULT 0,
            full_site_ad_orders INTEGER DEFAULT 0,
            full_site_ad_cvr FLOAT DEFAULT 0,
            data_source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_ptd_date ON product_traffic_detail(date)")
    conn.execute("CREATE INDEX idx_ptd_product ON product_traffic_detail(product_id)")
    print("[OK] 创建 product_traffic_detail 表")


def create_category_data_table(conn):
    if table_exists(conn, 'category_data'):
        print("[SKIP] category_data 表已存在")
        return

    conn.execute("""
        CREATE TABLE category_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date VARCHAR NOT NULL,
            store_name VARCHAR,
            category_name VARCHAR NOT NULL,
            category_level INTEGER DEFAULT 0,
            parent_category VARCHAR,
            level1_category VARCHAR,
            level2_category VARCHAR,
            source_name VARCHAR,
            parent_source VARCHAR,
            source_level INTEGER,
            favorite_users INTEGER DEFAULT 0,
            cart_users INTEGER DEFAULT 0,
            payment_buyers INTEGER DEFAULT 0,
            payment_amount FLOAT DEFAULT 0,
            visitors INTEGER DEFAULT 0,
            favorite_conversion FLOAT DEFAULT 0,
            cart_conversion FLOAT DEFAULT 0,
            payment_conversion FLOAT DEFAULT 0,
            uv_value FLOAT DEFAULT 0,
            data_source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_cat_date ON category_data(date)")
    conn.execute("CREATE INDEX idx_cat_name ON category_data(category_name)")
    print("[OK] 创建 category_data 表")


def create_store_daily_data_table(conn):
    if table_exists(conn, 'store_daily_data'):
        print("[SKIP] store_daily_data 表已存在")
        return

    conn.execute("""
        CREATE TABLE store_daily_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date VARCHAR NOT NULL,
            store_name VARCHAR,
            visitors INTEGER DEFAULT 0,
            new_visitors INTEGER DEFAULT 0,
            page_views INTEGER DEFAULT 0,
            avg_stay_duration FLOAT DEFAULT 0,
            visitors_3s INTEGER DEFAULT 0,
            product_click_users INTEGER DEFAULT 0,
            payment_buyers INTEGER DEFAULT 0,
            payment_amount FLOAT DEFAULT 0,
            followers INTEGER DEFAULT 0,
            favorite_users INTEGER DEFAULT 0,
            cart_users INTEGER DEFAULT 0,
            cart_items INTEGER DEFAULT 0,
            conversion_rate FLOAT DEFAULT 0,
            uv_value FLOAT DEFAULT 0,
            aov FLOAT DEFAULT 0,
            data_source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_sdd_date ON store_daily_data(date)")
    print("[OK] 创建 store_daily_data 表")


def create_keyword_data_table(conn):
    if table_exists(conn, 'keyword_data'):
        print("[SKIP] keyword_data 表已存在")
        return

    conn.execute("""
        CREATE TABLE keyword_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date VARCHAR NOT NULL,
            keyword VARCHAR NOT NULL,
            search_volume INTEGER DEFAULT 0,
            click_volume INTEGER DEFAULT 0,
            ctr FLOAT DEFAULT 0,
            conversion_rate FLOAT DEFAULT 0,
            payment_amount FLOAT DEFAULT 0,
            payment_buyers INTEGER DEFAULT 0,
            online_products INTEGER DEFAULT 0,
            competition_level INTEGER DEFAULT 0,
            market_rank INTEGER DEFAULT 0,
            trend TEXT,
            category VARCHAR,
            data_source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_kw_date ON keyword_data(date)")
    conn.execute("CREATE INDEX idx_kw_keyword ON keyword_data(keyword)")
    print("[OK] 创建 keyword_data 表")


def create_dmp_audience_table(conn):
    if table_exists(conn, 'dmp_audience'):
        print("[SKIP] dmp_audience 表已存在")
        return

    conn.execute("""
        CREATE TABLE dmp_audience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date VARCHAR NOT NULL,
            audience_type VARCHAR NOT NULL,
            audience_count INTEGER DEFAULT 0,
            audience_ratio FLOAT DEFAULT 0,
            change_count INTEGER DEFAULT 0,
            change_ratio FLOAT DEFAULT 0,
            category VARCHAR,
            sub_type VARCHAR,
            data_source VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_dmp_date ON dmp_audience(date)")
    conn.execute("CREATE INDEX idx_dmp_type ON dmp_audience(audience_type)")
    print("[OK] 创建 dmp_audience 表")


def main():
    print("=" * 70)
    print("生意参谋数据扩展迁移脚本 - 2026-05-04")
    print("=" * 70)
    print(f"数据库路径: {DB_PATH}\n")

    conn = get_connection()

    try:
        create_traffic_sources_table(conn)
        create_product_traffic_detail_table(conn)
        create_category_data_table(conn)
        create_store_daily_data_table(conn)
        create_keyword_data_table(conn)
        create_dmp_audience_table(conn)

        conn.commit()
        print("\n" + "=" * 70)
        print("[SUCCESS] 数据库扩展迁移完成!")
        print("=" * 70)
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] 数据库迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
