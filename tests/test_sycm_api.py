import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class SycmTrendApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-dashboard-sycm-tests-')
        from app import create_app
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.temp.name, 'dashboard.db')})
        self.client = self.app.test_client()
        from db import get_db
        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute('''CREATE TABLE sycm_market_rival_shop (
                stat_date TEXT, shop_id TEXT, shop_name TEXT, uv REAL,
                pay_buyer_count REAL, pay_rate REAL, cart_buyer_count REAL,
                collect_buyer_count REAL)''')
            connection.executemany(
                "INSERT INTO sycm_market_rival_shop VALUES (?, 'shop-1', '核心竞店', 100, 10, 0.1, 4, 2)",
                [('2026-09-16',), ('2026-09-17',), ('2026-09-18',), ('2026-09-19',), ('2026-09-22',)],
            )
            connection.execute('''CREATE TABLE sycm_market_item_rank (
                stat_date TEXT, item_id TEXT, uv REAL, pay_buyer_count REAL,
                is_self INTEGER DEFAULT 0, title TEXT, pic_url TEXT, shop_name TEXT,
                shop_id TEXT, cate_id TEXT, cate_name TEXT, core_keyword TEXT,
                rank INTEGER, created_at TEXT)''')
            connection.execute('''CREATE TABLE sycm_market_search_rank (
                stat_date TEXT, keyword TEXT, search_heat REAL, pay_rate REAL, click_rate REAL)''')
            connection.execute('''CREATE TABLE sycm_market_rival_item (
                stat_date TEXT, item_id TEXT, title TEXT, uv REAL,
                pay_buyer_count REAL, pic_url TEXT, detail_url TEXT)''')
            connection.execute('''CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY, title TEXT)''')
            connection.execute("INSERT INTO products (product_id, title) VALUES ('own-1', '同款标题')")
            connection.execute("INSERT INTO products (product_id, title) VALUES ('owned-rank', '自家上榜商品')")
            connection.executemany(
                'INSERT INTO sycm_market_rival_item VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    ('2026-09-22', 'own-1', '同款标题', 900, 90, '', ''),
                    ('2026-09-22', 'rival-1', '同款标题', 100, 10, '', ''),
                ],
            )
            connection.executemany(
                "INSERT INTO sycm_market_item_rank (stat_date, item_id, uv, pay_buyer_count, is_self, title, pic_url, shop_name, shop_id, cate_id, cate_name, core_keyword, rank) VALUES (?, 'item-1', 100, 10, 0, '外部商品', '', '外部店铺', 'shop-ext', 'cat', '袜子', '', 1)",
                [('2026-09-16',), ('2026-09-17',), ('2026-09-18',), ('2026-09-19',), ('2026-09-22',)],
            )
            connection.execute("INSERT INTO sycm_market_item_rank (stat_date, item_id, uv, pay_buyer_count, is_self, title) VALUES ('2026-09-22', 'owned-rank', 900, 90, 0, '自家上榜商品')")
            connection.execute("INSERT INTO sycm_market_item_rank (stat_date, item_id, uv, pay_buyer_count, is_self, title) VALUES ('2026-09-22', 'rival-1', 500, 50, 0, '外部竞品')")
            connection.execute("INSERT INTO sycm_market_item_rank (stat_date, item_id, uv, pay_buyer_count, is_self, title, shop_name, shop_id, cate_id) VALUES ('2026-09-22', 'item-1', 100, 10, 0, '外部商品', '外部店铺', 'shop-ext', 'cat-duplicate')")
            connection.executemany(
                "INSERT INTO sycm_market_search_rank VALUES (?, '词', 100, 0.1, 0.2)",
                [('2026-09-16',), ('2026-09-17',), ('2026-09-18',), ('2026-09-19',), ('2026-09-22',)],
            )
            connection.commit()

    def tearDown(self):
        self.temp.cleanup()

    def test_trend_returns_coverage_and_daily_average(self):
        response = self.client.get('/api/sycm/rival-shops/trend?start=2026-09-16&end=2026-09-22')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()['data']
        self.assertEqual(payload['expected_days'], 7)
        self.assertEqual(payload['observed_days'], 5)
        self.assertEqual(payload['coverage_status'], 'partial')
        self.assertFalse(payload['trend_comparable'])
        self.assertEqual(payload['totals']['avg_uv_per_day'], 100)

    def test_market_trend_returns_daily_sample_series_and_coverage(self):
        response = self.client.get('/api/sycm/market/trend?start=2026-09-16&end=2026-09-22')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()['data']
        self.assertEqual(payload['observed_days'], 5)
        self.assertEqual(payload['expected_days'], 7)
        self.assertFalse(payload['trend_comparable'])
        self.assertEqual(payload['daily'][0]['item_count'], 1)
        self.assertEqual(payload['daily'][0]['keyword_count'], 1)
        self.assertEqual(len(payload['daily']), 7)
        self.assertIsNone(payload['daily'][4]['item_count'])
        self.assertEqual(payload['item_observed_days'], 5)
        self.assertEqual(payload['search_observed_days'], 5)
        self.assertEqual(payload['daily'][-1]['avg_item_buyers'], 30)

    def test_entity_trend_returns_one_shop_and_explicit_missing_days(self):
        response = self.client.get('/api/sycm/rival-shops/entity-trend?shop_id=shop-1&start=2026-09-16&end=2026-09-22')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()['data']
        self.assertEqual(payload['entity_name'], '核心竞店')
        self.assertEqual(payload['observed_days'], 5)
        self.assertEqual(payload['expected_days'], 7)
        self.assertFalse(payload['trend_comparable'])
        self.assertEqual(payload['daily'][0]['pay_rate'], 0.1)

    def test_rival_items_use_external_market_products_and_exclude_owned_ids(self):
        listed = self.client.get('/api/sycm/rival-items/list?date=2026-09-22').get_json()['data']
        listed_ids = [item['item_id'] for item in listed['items']]
        self.assertIn('rival-1', listed_ids)
        self.assertIn('item-1', listed_ids)
        self.assertNotIn('owned-rank', listed_ids)
        self.assertNotIn('own-1', listed_ids)
        self.assertEqual(listed['excluded_own_count'], 1)

        entities = self.client.get('/api/sycm/rival-items/entities?start=2026-09-22&end=2026-09-22').get_json()['data']['entities']
        entity_ids = [item['entity_id'] for item in entities]
        self.assertIn('rival-1', entity_ids)
        self.assertNotIn('owned-rank', entity_ids)

        trend = self.client.get('/api/sycm/rival-items/trend?start=2026-09-22&end=2026-09-22').get_json()['data']
        self.assertEqual(trend['daily'][0]['entity_count'], 2)

    def test_owned_item_has_no_rival_entity_trend(self):
        response = self.client.get('/api/sycm/rival-items/entity-trend?item_id=own-1&start=2026-09-22&end=2026-09-22')
        self.assertEqual(response.get_json()['code'], 'NO_DATA')

    def test_market_entity_trends_list_external_shops_and_items(self):
        shops = self.client.get('/api/sycm/market/shops/entities?start=2026-09-16&end=2026-09-22').get_json()['data']['entities']
        shop_ids = [entity['entity_id'] for entity in shops]
        self.assertIn('shop-ext', shop_ids)
        self.assertNotIn('own-1', shop_ids)
        shop = next(entity for entity in shops if entity['entity_id'] == 'shop-ext')
        self.assertEqual(shop['latest_uv'], 100)
        self.assertEqual(shop['latest_pay_buyer_count'], 10)
        self.assertEqual(shop['daily'][-1]['item_count'], 1)

        shop_trend = self.client.get('/api/sycm/market/shops/entity-trend?shop_id=shop-ext&start=2026-09-16&end=2026-09-22').get_json()['data']
        self.assertEqual(shop_trend['observed_days'], 5)
        self.assertEqual(shop_trend['daily'][0]['item_count'], 1)
        self.assertEqual(shop_trend['daily'][0]['uv'], 100)
        self.assertEqual(len(shop_trend['items']), 1)
        self.assertEqual(shop_trend['items'][0]['item_id'], 'item-1')
        self.assertEqual(shop_trend['items'][0]['uv'], 100)

        items = self.client.get('/api/sycm/market/items/entities?start=2026-09-16&end=2026-09-22').get_json()['data']['entities']
        item_ids = [entity['entity_id'] for entity in items]
        self.assertIn('item-1', item_ids)
        self.assertIn('rival-1', item_ids)
        self.assertNotIn('owned-rank', item_ids)

        item_trend = self.client.get('/api/sycm/market/items/entity-trend?item_id=item-1&start=2026-09-16&end=2026-09-22').get_json()['data']
        self.assertEqual(item_trend['observed_days'], 5)
        self.assertEqual(item_trend['daily'][0]['pay_rate'], 0.1)
        self.assertEqual(item_trend['daily'][-1]['rank'], 1)


if __name__ == '__main__':
    unittest.main()
