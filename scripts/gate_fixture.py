"""Small deterministic facts for isolated gates; never copies a user database."""
from contextlib import closing
import sqlite3

SHOP_ID = 'legacy-shop'

# 品类标签必须与运行时解析的 category_mode=sock 标签一致，否则 gate 服务上
# 所有带 category_mode 的请求都会 422（sock 模式解析不到任何商品）。
# 直接复用服务模块的常量，避免两处各自读 env 产生漂移。
def category_label():
    from services.category_mode_service import SOCK_LABEL
    return SOCK_LABEL
PRODUCT_ID = 'gate-product-001'


def seed_database(database, shop_id=None):
    # The caller creates the current schema in a fresh temporary database first.
    shop_scope = shop_id or SHOP_ID
    with closing(sqlite3.connect(database)) as connection:
        with connection:
            # Collector-owned schema from collect_sycm_item_flow_v6.py; empty by design.
            # Gates must not require running a real collector or invent flow evidence.
            connection.execute("CREATE TABLE IF NOT EXISTS sycm_item_flow_source_daily (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            stat_date TEXT NOT NULL,\n            item_id TEXT NOT NULL,\n            channel_name TEXT NOT NULL,\n            parent_channel TEXT,\n            level INTEGER,\n            channel_type TEXT,\n            page_level INTEGER,\n            uv INTEGER,\n            pv INTEGER,\n            pay_amount REAL,\n            pay_buyer_count INTEGER,\n            pay_rate REAL,\n            cart_buyer_count INTEGER,\n            collect_item_count INTEGER,\n            collect_count INTEGER,\n            deal_buyer_count INTEGER,\n            deal_rate REAL,\n            direct_pay_buyer_count INTEGER,\n            pay_item_count INTEGER,\n            new_uv INTEGER,\n            fans_pay_buyer_count INTEGER,\n            order_item_pay_buyer_count INTEGER,\n            collect_item_pay_buyer_count INTEGER,\n            page_id TEXT,\n            belong TEXT DEFAULT 'farthest',\n            raw_data TEXT,\n            created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n            UNIQUE(stat_date, item_id, channel_name, belong)\n        )")
            connection.execute(
                'INSERT OR REPLACE INTO products '
                '(product_id, title, tier, style, status, shop_label) VALUES (?, ?, ?, ?, ?, ?)',
                (PRODUCT_ID, '隔离测试商品', '测试层级', '测试款式', 'active', category_label()),
            )
            # Batch copy needs two distinct catalogue rows; the second product
            # intentionally has no fabricated sales or lifecycle evidence.
            connection.execute(
                'INSERT OR REPLACE INTO products '
                '(product_id, title, tier, style, status, shop_label) VALUES (?, ?, ?, ?, ?, ?)',
                ('gate-product-002', '隔离无销量商品', '测试层级', '测试款式', 'active', category_label()),
            )
            for day in range(10, 18):
                connection.execute(
                    'INSERT OR REPLACE INTO daily_data '
                    '(product_id, date, ipv, pv, payment_amount, buyers, '
                    'net_sales, shop_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (PRODUCT_ID, f'2026-09-{day:02}', 100, 200, 200.0, 10, 200.0, shop_scope),
                )
            # The lifecycle cards consume monthly_data, not daily_data. Derive
            # this fixture month from the same eight seeded days; it is still
            # partial coverage, never a fabricated complete month/60-day history.
            connection.execute(
                "INSERT OR REPLACE INTO monthly_data "
                "(product_id, month, payment_amount, net_sales, visitors, buyers) "
                "SELECT product_id, substr(date, 1, 7), SUM(payment_amount), "
                "SUM(net_sales), SUM(ipv), SUM(buyers) FROM daily_data "
                "WHERE product_id = ? AND shop_id = ? "
                "AND date BETWEEN '2026-09-10' AND '2026-09-17' "
                "GROUP BY product_id, substr(date, 1, 7)",
                (PRODUCT_ID, shop_scope),
            )
