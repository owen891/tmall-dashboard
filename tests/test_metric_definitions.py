import unittest

from services.metric_definitions import derive_metrics


class MetricDefinitionTests(unittest.TestCase):
    def test_derives_sum_then_ratio_metrics(self):
        result = derive_metrics({
            'payment_amount': 1000,
            'successful_refund_amount': 100,
            'product_visitors': 200,
            'payment_buyers': 20,
            'returning_payment_buyers': 5,
            'ad_spend': 80,
            'attributed_payment_amount': 240,
        })

        self.assertEqual(result['values']['net_sales'], 900.0)
        self.assertEqual(result['values']['refund_rate'], 0.1)
        self.assertEqual(result['values']['payment_conversion_rate'], 0.1)
        self.assertEqual(result['values']['average_order_value'], 50.0)
        self.assertEqual(result['values']['expense_ratio'], 0.08)
        self.assertEqual(result['values']['ad_roi'], 3.0)
        self.assertEqual(result['values']['returning_buyer_ratio'], 0.25)
        self.assertEqual(result['missing_fields'], [])

    def test_marks_missing_dependencies_without_fabricating_zero(self):
        result = derive_metrics({'payment_amount': 1000})

        self.assertIsNone(result['values']['payment_conversion_rate'])
        self.assertIn('payment_buyers', result['missing_fields'])
        self.assertIn('product_visitors', result['missing_fields'])

    def test_zero_denominator_is_not_a_metric_value(self):
        result = derive_metrics({
            'payment_amount': 0,
            'successful_refund_amount': 0,
            'ad_spend': 0,
        })

        self.assertIsNone(result['values']['refund_rate'])
        self.assertIsNone(result['values']['expense_ratio'])

    def test_overview_consumes_registry_values_and_availability(self):
        from services.metrics_service import build_overview

        result = build_overview({
            'fact_count': 1,
            'data_end_date': '2026-08-02',
            'payment_amount': 1000,
            'successful_refund_amount': 100,
            'product_visitors': 200,
            'payment_buyers': 20,
            'returning_payment_buyers': 5,
            'ad_spend': 80,
            'attributed_payment_amount': 240,
        }, '2026-08-01', '2026-08-02')

        self.assertEqual(result['data']['ad_roi'], 3.0)
        self.assertEqual(result['data']['metric_availability']['refund_rate'], 'available')

    def test_overview_keeps_missing_refund_and_spend_unavailable(self):
        from services.metrics_service import build_overview

        result = build_overview({
            'fact_count': 1,
            'data_end_date': '2026-08-02',
            'payment_amount': 100,
            'successful_refund_amount': None,
            'product_visitors': 10,
            'payment_buyers': 2,
            'returning_payment_buyers': None,
            'ad_spend': None,
        }, '2026-08-01', '2026-08-02')

        self.assertEqual(result['availability'], 'insufficient-data')
        self.assertIsNone(result['data']['successful_refund_amount'])
        self.assertIsNone(result['data']['refund_rate'])
        self.assertIsNone(result['data']['ad_spend'])
        self.assertIsNone(result['data']['expense_ratio'])


if __name__ == '__main__':
    unittest.main()
