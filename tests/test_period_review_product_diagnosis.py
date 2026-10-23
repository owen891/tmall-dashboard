import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class PeriodReviewProductDiagnosisTests(unittest.TestCase):
    endpoint = '/api/period-reviews/week/2026-W38/context'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-dashboard-product-diagnosis-')
        from app import create_app

        self.database_path = os.path.join(self.temp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def _context(self, query='category_mode=all&compare=previous'):
        response = self.client.get(f'{self.endpoint}?{query}')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        response.close()
        return payload['data']['context']

    def _insert_products(self, rows):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO products
                   (product_id, title, image_url, product_tags, shop_label)
                   VALUES (?, ?, ?, ?, ?)''',
                rows,
            )
            connection.commit()

    def _insert_daily(self, rows):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO daily_data
                   (product_id, date, payment_amount, refund_amount, net_sales,
                    ipv, buyers, ad_spend)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                rows,
            )
            connection.commit()

    def test_product_diagnosis_contains_metrics_anomaly_tags_and_unknowns(self):
        self._insert_products([
            ('diag-a', '诊断商品 A', 'a.jpg', '爆款', '默认品类'),
        ])
        self._insert_daily([
            ('diag-a', '2026-09-14', 300, 30, 270, 100, 10, 20),
            ('diag-a', '2026-09-07', 200, 10, 180, 80, 8, 10),
        ])

        context = self._context()
        item = context['products']['top'][0]
        expected_fields = {
            'product_id', 'title', 'image_url', 'tags', 'gsv', 'net_sales',
            'prev_gsv', 'delta', 'change_rate', 'share_of_gsv', 'buyers',
            'prev_buyers', 'visitors', 'prev_visitors', 'conversion',
            'prev_conversion', 'aov', 'prev_aov', 'ad_spend', 'prev_ad_spend',
            'refund_rate', 'prev_refund_rate', 'anomaly_tags', 'system_facts',
            'unknowns',
        }
        self.assertTrue(expected_fields.issubset(item))
        self.assertEqual(item['product_id'], 'diag-a')
        self.assertEqual(item['title'], '诊断商品 A')
        self.assertEqual(item['tags'], '爆款')
        self.assertEqual(item['gsv'], 300.0)
        self.assertEqual(item['net_sales'], 270.0)
        self.assertEqual(item['prev_gsv'], 200.0)
        self.assertEqual(item['delta'], 100.0)
        self.assertEqual(item['change_rate'], 0.5)
        self.assertEqual(item['share_of_gsv'], 1.0)
        self.assertEqual(item['buyers'], 10.0)
        self.assertEqual(item['prev_buyers'], 8.0)
        self.assertEqual(item['visitors'], 100.0)
        self.assertEqual(item['prev_visitors'], 80.0)
        self.assertEqual(item['conversion'], 0.1)
        self.assertEqual(item['prev_conversion'], 0.1)
        self.assertEqual(item['aov'], 30.0)
        self.assertEqual(item['prev_aov'], 25.0)
        self.assertEqual(item['ad_spend'], 20.0)
        self.assertEqual(item['prev_ad_spend'], 10.0)
        self.assertEqual(item['refund_rate'], 0.1)
        self.assertEqual(item['prev_refund_rate'], 0.05)
        self.assertIn('投放效率下降', item['anomaly_tags'])
        self.assertIn('退款率上升', item['anomaly_tags'])
        self.assertTrue(item['system_facts'])
        self.assertIsInstance(item['unknowns'], list)

    def test_decline_sorting_follows_previous_and_custom_comparison_periods(self):
        self._insert_products([
            ('sort-a', '排序商品 A', '', '', '默认品类'),
            ('sort-b', '排序商品 B', '', '', '默认品类'),
        ])
        self._insert_daily([
            ('sort-a', '2026-09-14', 100, 0, 90, 100, 10, 10),
            ('sort-b', '2026-09-14', 80, 0, 70, 100, 8, 10),
            ('sort-a', '2026-09-07', 50, 0, 45, 100, 5, 10),
            ('sort-b', '2026-09-07', 300, 0, 270, 100, 30, 10),
            ('sort-a', '2026-08-24', 400, 0, 360, 100, 40, 10),
            ('sort-b', '2026-08-24', 70, 0, 63, 100, 7, 10),
        ])

        previous = self._context()
        self.assertEqual(
            [item['product_id'] for item in previous['products']['top']],
            ['sort-a', 'sort-b'],
        )
        self.assertEqual(
            [item['product_id'] for item in previous['products']['decline']],
            ['sort-b'],
        )
        self.assertEqual(previous['products']['decline'][0]['prev_gsv'], 300.0)
        self.assertEqual(previous['products']['decline'][0]['delta'], -220.0)

        custom = self._context(
            'category_mode=all&compare=custom&compare_period=2026-W35'
        )
        self.assertEqual(custom['compare']['period_key'], '2026-W35')
        self.assertEqual(
            [item['product_id'] for item in custom['products']['decline']],
            ['sort-a'],
        )
        self.assertEqual(custom['products']['decline'][0]['prev_gsv'], 400.0)
        self.assertEqual(custom['products']['decline'][0]['delta'], -300.0)

    def test_missing_metrics_and_missing_baseline_remain_none_and_are_explained(self):
        self._insert_products([
            ('missing-a', '缺失指标商品', '', '', '默认品类'),
            ('missing-b', '缺失对比商品', '', '', '默认品类'),
        ])
        self._insert_daily([
            ('missing-a', '2026-09-14', 120, None, None, None, None, None),
            ('missing-a', '2026-09-07', 100, None, None, None, None, None),
            ('missing-b', '2026-09-07', 90, None, None, None, None, None),
        ])

        context = self._context()
        rows = {item['product_id']: item for item in context['products']['top']}

        metric_missing = rows['missing-a']
        self.assertIsNone(metric_missing['net_sales'])
        self.assertIsNone(metric_missing['buyers'])
        self.assertIsNone(metric_missing['prev_buyers'])
        self.assertIsNone(metric_missing['visitors'])
        self.assertIsNone(metric_missing['prev_visitors'])
        self.assertIsNone(metric_missing['conversion'])
        self.assertIsNone(metric_missing['aov'])
        self.assertIsNone(metric_missing['ad_spend'])
        self.assertIsNone(metric_missing['refund_rate'])
        self.assertTrue(metric_missing['unknowns'])
        self.assertNotIn(0, metric_missing['unknowns'])

        missing_current = next(
            item for item in context['products']['decline']
            if item['product_id'] == 'missing-b'
        )
        self.assertIsNone(missing_current['gsv'])
        self.assertEqual(missing_current['prev_gsv'], 90.0)
        self.assertEqual(missing_current['delta'], -90.0)
        self.assertFalse(missing_current['current_record_exists'])
        self.assertEqual(missing_current['current_data_status'], 'no-record')

    def test_category_filter_applies_to_top_decline_and_share_metrics(self):
        self._insert_products([
            ('scope-sock', '标品商品', '', '', '默认品类'),
            ('scope-multi', '多标签商品', '', '', '默认品类,平销商品'),
            ('scope-other', '其他商品', '', '', '内裤'),
        ])
        self._insert_daily([
            ('scope-sock', '2026-09-14', 100, 0, 90, 100, 10, 10),
            ('scope-multi', '2026-09-14', 50, 0, 45, 50, 5, 5),
            ('scope-other', '2026-09-14', 900, 0, 810, 900, 90, 90),
            ('scope-sock', '2026-09-07', 200, 0, 180, 100, 20, 10),
            ('scope-multi', '2026-09-07', 100, 0, 90, 50, 10, 5),
            ('scope-other', '2026-09-07', 1000, 0, 900, 900, 100, 90),
        ])

        filtered = self._context('category_mode=sock&compare=previous')
        self.assertEqual(filtered['category']['label'], '默认品类')
        self.assertTrue(filtered['category']['filtered'])
        self.assertEqual(
            [item['product_id'] for item in filtered['products']['top']],
            ['scope-sock', 'scope-multi'],
        )
        self.assertNotIn(
            'scope-other',
            [item['product_id'] for item in filtered['products']['top']]
            + [item['product_id'] for item in filtered['products']['decline']],
        )
        self.assertEqual(
            sum(item['share_of_gsv'] for item in filtered['products']['top']),
            1.0,
        )

        unfiltered = self._context('category_mode=all&compare=previous')
        self.assertIsNone(unfiltered['category']['label'])
        self.assertIn(
            'scope-other',
            [item['product_id'] for item in unfiltered['products']['top']],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
