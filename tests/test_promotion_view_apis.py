"""推广分析 4 视图新端点的契约测试。

钉住维度报表上线后的关键行为：
- grain 过滤：商品粒度行（channel='全部'）不进渠道对比，月度汇总行
  （grain='campaign_month'）不进任何日粒度视图；
- /api/promotion/plan-types 按计划名解析投放方式并聚合；
- /api/promotion/creatives 聚合创意日事实并带缩略图；
- /api/promotion/product-detail 与 /api/promotion/campaign-detail 走
  promotion_campaign_items 映射。
"""
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class PromotionViewApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-promotion-views-')
        from app import create_app
        from db import get_db
        self.path = os.path.join(self.temp_dir.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        with get_db(self.path) as conn:
            conn.executescript('''
                INSERT INTO products (product_id, title, image_url) VALUES
                    ('p1', '演示凉感四件套', 'https://cdn.example.com/p1.jpg'),
                    ('p2', '演示纯棉袜子', '');
                INSERT INTO monthly_data (product_id, month, guide_visitors, guide_potential)
                VALUES ('p1', '2026-04', 100, 12);
                UPDATE products SET shop_label = '标品袜子' WHERE product_id = 'p1';
                -- 计划粒度行（维度报表回填形态：channel=场景，带计划名与行为指标）
                INSERT INTO promotion_daily_facts
                    (date, channel, campaign_id, campaign_name, grain, cart_adds, cart_cost, new_buyers,
                     ad_spend, attributed_payment_amount, impressions, clicks, payment_buyers)
                VALUES
                    ('2026-04-01', '关键词推广', 'c1', '标品_A_控点击', 'campaign', 4, 2.5, 2, 100, 300, 1000, 100, 10),
                    ('2026-04-02', '关键词推广', 'c1', '标品_A_控点击', 'campaign', 2, NULL, 1, 50, 100, 500, 40, 5),
                    ('2026-04-01', '人群推广',   'c2', '标品_B_控成本', 'campaign', 1, 9.0, 0, 200, 200, 800, 60, 3);
                -- 商品粒度行（channel='全部'，不得进入渠道对比）
                INSERT INTO promotion_daily_facts
                    (date, channel, product_id, grain, ad_spend, attributed_payment_amount, impressions, clicks)
                VALUES ('2026-04-01', '全部', 'p1', 'product', 999, 999, 9999, 999);
                -- 月度汇总行（不得进入日粒度视图）
                INSERT INTO promotion_daily_facts
                    (date, channel, campaign_id, campaign_name, grain, ad_spend)
                VALUES ('2026-03-31', '关键词推广', 'c1', '标品_A_控点击', 'campaign_month', 5000);
                -- 创意维度与日事实
                INSERT INTO promotion_creatives
                    (shop_id, creative_id, creative_name, image_url, product_id, product_name, channel)
                VALUES
                    ('default', 'cr1', '创意甲', 'https://img.example.com/cr1.jpg', 'p1', '演示凉感四件套', '关键词推广'),
                    ('default', 'cr2', '创意乙', '', 'p1', '演示凉感四件套', '人群推广'),
                    ('default', 'cr3', '商品p1_智能创意_20260821_134418', '', 'p1', '演示凉感四件套', '关键词推广'),
                    ('default', 'cr4', '创意_20260821000000_p1', '', 'p1', '演示凉感四件套', '关键词推广'),
                    ('default', 'cr5', '黑盒创意测试', '', 'p1', '演示凉感四件套', '关键词推广'),
                    ('default', 'cr6', '未关联素材', '', '', '', '关键词推广');
                INSERT INTO promotion_creative_daily
                    (shop_id, date, channel, creative_id, product_id, ad_spend,
                     attributed_payment_amount, impressions, clicks, payment_buyers, cart_adds, new_buyers)
                VALUES
                    ('default', '2026-04-01', '关键词推广', 'cr1', 'p1', 20, 80, 500, 50, 5, 3, 1),
                    ('default', '2026-04-02', '关键词推广', 'cr1', 'p1', 10, 20, 300, 10, 1, 1, 0),
                    ('default', '2026-04-01', '人群推广',   'cr2', 'p1', 5, 0, 100, 2, 0, 0, 0),
                    ('default', '2026-04-01', '关键词推广', 'cr3', 'p1', 99, 0, 100, 2, 0, 0, 0),
                    ('default', '2026-04-01', '关键词推广', 'cr4', 'p1', 99, 0, 100, 2, 0, 0, 0),
                    ('default', '2026-04-01', '关键词推广', 'cr5', 'p1', 99, 0, 100, 2, 0, 0, 0),
                    ('default', '2025-01-01', '关键词推广', 'cr6', '', 999, 999, 100, 99, 0, 0, 0);
                -- 计划×商品映射
                INSERT INTO promotion_campaign_items
                    (shop_id, campaign_id, product_id, campaign_name, product_name, image_url, channel)
                VALUES
                    ('default', 'c1', 'p1', '标品_A_控点击', '演示凉感四件套', 'https://cdn.example.com/p1.jpg', '关键词推广'),
                    ('default', 'c2', 'p1', '标品_B_控成本', '演示凉感四件套', '', '人群推广');
            ''')
            conn.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_channel_view_excludes_product_and_month_rows(self):
        response = self.client.get('/api/promotion?start=2026-03-01&end=2026-04-30&group_by=channel')
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()['data']['rows']
        channels = {row['channel']: row for row in rows}
        # 商品粒度行(¥999)与月度汇总行(¥5000)都必须被排除
        self.assertNotIn('全部', channels)
        self.assertAlmostEqual(channels['关键词推广']['ad_spend'], 150.0, places=6)
        self.assertAlmostEqual(channels['人群推广']['ad_spend'], 200.0, places=6)

    def test_channel_view_sums_behavior_metrics(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-02&group_by=channel')
        rows = response.get_json()['data']['rows']
        keyword = next(row for row in rows if row['channel'] == '关键词推广')
        self.assertEqual(keyword['cart_adds'], 6)
        self.assertEqual(keyword['new_buyers'], 3)
        # cart_cost = 150 / 6
        self.assertAlmostEqual(keyword['cart_cost'], 25.0, places=6)

    def test_campaign_view_carries_names_and_plan_type(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-02&group_by=campaign')
        rows = response.get_json()['data']['rows']
        first = next(row for row in rows if row['campaign_id'] == 'c1')
        self.assertEqual(first['campaign_name'], '标品_A_控点击')
        self.assertEqual(first['plan_type'], '控点击')
        self.assertEqual(first['ad_spend'], 150.0)

    def test_plan_types_aggregates_by_parsed_type(self):
        response = self.client.get('/api/promotion/plan-types?start=2026-04-01&end=2026-04-02')
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()['data']['rows']
        by_type = {row['plan_type']: row for row in rows}
        self.assertEqual(by_type['控点击']['plan_count'], 1)
        self.assertAlmostEqual(by_type['控点击']['ad_spend'], 150.0, places=6)
        self.assertEqual(by_type['控成本']['plan_count'], 1)
        self.assertEqual(by_type['控成本']['cart_cost'], 200.0)

    def test_product_detail_returns_complete_campaign_and_channel_metrics(self):
        response = self.client.get('/api/promotion/product-detail?start=2026-04-01&end=2026-04-02&product_id=p1')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()['data']
        campaign = next(row for row in payload['campaigns'] if row['campaign_id'] == 'c1')
        channel = next(row for row in payload['channel_mix'] if row['channel'] == '关键词推广')
        for row in (campaign, channel):
            for key in ('impressions', 'clicks', 'ctr', 'cpm', 'payment_buyers', 'cvr', 'cpc', 'cart_adds', 'cart_rate', 'cart_cost', 'new_buyers', 'new_buyer_ratio', 'new_customer_cost', 'direct_payment_amount', 'indirect_payment_amount', 'paid_share'):
                self.assertIn(key, row)
        self.assertEqual(campaign['cart_adds'], 6)
        self.assertAlmostEqual(campaign['cpc'], 150 / 140, places=6)
        self.assertAlmostEqual(channel['cart_cost'], 150 / 6, places=6)


        response = self.client.get('/api/promotion/creatives?start=2026-04-01&end=2026-04-02&sort=clicks')
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()['data']['rows']
        self.assertEqual(len(rows), 2)
        top = rows[0]
        self.assertEqual(top['creative_id'], 'cr1')
        self.assertEqual(top['image_url'], 'https://img.example.com/cr1.jpg')
        self.assertAlmostEqual(top['ad_spend'], 30.0, places=6)
        self.assertAlmostEqual(top['ctr'], 60 / 800, places=6)

    def test_creatives_endpoint_excludes_system_creatives(self):
        response = self.client.get('/api/promotion/creatives?start=2026-04-01&end=2026-04-02&sort=clicks')
        rows = response.get_json()['data']['rows']
        ids = {row['creative_id'] for row in rows}
        # 智能创意 / 黑盒 / 创意_时间戳 系统自动命名都不展示
        self.assertNotIn('cr3', ids)
        self.assertNotIn('cr4', ids)
        self.assertNotIn('cr5', ids)
        self.assertIn('cr1', ids)

    def test_creatives_endpoint_filters_by_product(self):
        self.client.get('/api/promotion/creatives?start=2026-04-01&end=2026-04-02')
        response = self.client.get('/api/promotion/creatives?start=2026-04-01&end=2026-04-02&product_id=p2')
        rows = response.get_json()['data']['rows']
        self.assertEqual(rows, [])

    def test_creative_board_aggregates_all_history_by_product(self):
        response = self.client.get('/api/creative-board')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['totals']['product_count'], 1)
        self.assertEqual(data['totals']['creative_count'], 2)
        self.assertAlmostEqual(data['totals']['ad_spend'], 35.0, places=6)
        self.assertEqual(data['totals']['clicks'], 62)
        self.assertEqual(len(data['products']), 1)
        product = data['products'][0]
        self.assertEqual(product['product_id'], 'p1')
        self.assertEqual(product['shop_label'], '标品袜子')
        creatives = {row['creative_id']: row for row in product['creatives']}
        self.assertEqual(set(creatives), {'cr1', 'cr2'})
        self.assertAlmostEqual(creatives['cr1']['ad_spend'], 30.0, places=6)
        self.assertEqual(creatives['cr1']['clicks'], 60)
        self.assertEqual(creatives['cr1']['first_date'], '2026-04-01')
        self.assertEqual(creatives['cr1']['last_date'], '2026-04-02')

    def test_creative_board_ignores_time_params_and_filters_category(self):
        all_time = self.client.get('/api/creative-board?start=1900-01-01&end=1900-01-02').get_json()['data']
        category = self.client.get('/api/creative-board?category=%E6%A0%87%E5%93%81%E8%A2%9C%E5%AD%90').get_json()['data']
        empty = self.client.get('/api/creative-board?category=%E9%9D%9E%E6%A0%87%E5%93%81%E8%A2%9C%E5%AD%90').get_json()['data']
        self.assertEqual(all_time['totals'], category['totals'])
        self.assertEqual([row['product_id'] for row in category['products']], ['p1'])
        self.assertEqual(empty['products'], [])

    def test_creative_board_excludes_unlinked_and_system_creatives(self):
        response = self.client.get('/api/creative-board')
        data = response.get_json()['data']
        names = [creative['creative_name'] for product in data['products'] for creative in product['creatives']]
        self.assertEqual(names, ['创意甲', '创意乙'])
        self.assertNotIn('未关联素材', names)
        self.assertFalse(any(product['product_id'] in ('', '_') for product in data['products']))

        response = self.client.get('/api/promotion/product-detail?start=2026-04-01&end=2026-04-02&product_id=p1')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        mix = {row['channel']: row for row in data['channel_mix']}
        self.assertAlmostEqual(mix['关键词推广']['ad_spend'], 150.0, places=6)
        self.assertAlmostEqual(mix['人群推广']['ad_spend'], 200.0, places=6)
        self.assertAlmostEqual(mix['关键词推广']['spend_share'], 150.0 / 350.0, places=6)
        self.assertAlmostEqual(data['summary']['ad_spend'], 350.0, places=6)
        self.assertAlmostEqual(data['summary']['attributed_payment_amount'], 600.0, places=6)
        self.assertAlmostEqual(data['summary']['roi'], 600.0 / 350.0, places=6)
        self.assertAlmostEqual(data['summary']['ctr'], 200 / 2300, places=6)
        self.assertAlmostEqual(data['summary']['cvr'], 18 / 200, places=6)
        self.assertEqual(data['summary']['cart_adds'], 7)
        self.assertAlmostEqual(data['summary']['cart_cost'], 350 / 7, places=6)
        self.assertAlmostEqual(data['summary']['new_customer_cost'], 350 / 3, places=6)
        self.assertAlmostEqual(data['summary']['guide_potential_ratio'], 12 / 100, places=6)
        self.assertEqual(len(data['campaigns']), 2)
        plans = {row['campaign_id']: row for row in data['campaigns']}
        self.assertEqual(plans['c1']['plan_type'], '控点击')
        self.assertAlmostEqual(plans['c1']['cart_cost'], 150 / 6, places=6)
        self.assertAlmostEqual(plans['c1']['new_customer_cost'], 150 / 3, places=6)

    def test_product_detail_falls_back_to_product_fact_when_plan_fact_is_missing(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                "INSERT INTO promotion_daily_facts (date, channel, product_id, grain, ad_spend, attributed_payment_amount, impressions, clicks, payment_buyers, cart_adds, new_buyers) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ('2026-04-01', '全部', 'p2', 'product', 80, 200, 1000, 50, 4, 8, 2),
            )
            conn.commit()
        response = self.client.get('/api/promotion/product-detail?start=2026-04-01&end=2026-04-02&product_id=p2')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(len(data['campaigns']), 1)
        self.assertEqual(data['campaigns'][0]['campaign_id'], 'product:p2')
        self.assertEqual(data['channel_mix'][0]['channel'], '全部')
        self.assertEqual(data['summary']['cart_adds'], 8)
        self.assertAlmostEqual(data['summary']['new_customer_cost'], 40.0, places=6)

    def test_campaign_detail_returns_products_from_edges(self):
        response = self.client.get('/api/promotion/campaign-detail?start=2026-04-01&end=2026-04-02&campaign_id=c1')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['summary']['campaign_name'], '标品_A_控点击')
        self.assertEqual(data['summary']['plan_type'], '控点击')
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['products'][0]['product_id'], 'p1')
        # 该商品有两个创意映射
        self.assertEqual(data['products'][0]['creative_count'], 2)

    def test_campaign_detail_requires_campaign_id(self):
        response = self.client.get('/api/promotion/campaign-detail?start=2026-04-01&end=2026-04-02')
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
