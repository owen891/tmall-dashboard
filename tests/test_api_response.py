import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class ApiResponseTests(unittest.TestCase):
    def test_unknown_availability_is_normalized(self):
        from flask import Flask
        from api.api_response import success
        app = Flask(__name__)
        with app.test_request_context('/'):
            response, status = success({}, availability='not-real')
            self.assertEqual(status, 200)
            self.assertEqual(response.get_json()['availability'], 'calculation-failed')

    def test_success_includes_empty_context_defaults(self):
        from flask import Flask
        from api.api_response import success

        app = Flask(__name__)
        with app.test_request_context('/'):
            response, status = success({'rows': []}, availability='no-data')
            payload = response.get_json()

        self.assertEqual(status, 200)
        self.assertEqual(payload['capabilities'], {})
        self.assertEqual(payload['filters'], {})
        self.assertEqual(payload['missing_fields'], [])
        self.assertEqual(payload['missing_ranges'], [])
        self.assertEqual(payload['source_batches'], [])

    def test_success_preserves_declared_context(self):
        from flask import Flask
        from api.api_response import success

        app = Flask(__name__)
        with app.test_request_context('/'):
            response, _ = success(
                {},
                capabilities={'can_export': True},
                filters={'product_id': 'P-1'},
                missing_fields=['payment_buyers'],
                missing_ranges=[{'start': '2026-08-01', 'end': '2026-08-02'}],
                source_batches=[{'id': 'batch-1'}],
            )
            payload = response.get_json()

        self.assertTrue(payload['capabilities']['can_export'])
        self.assertEqual(payload['filters']['product_id'], 'P-1')
        self.assertEqual(payload['missing_fields'], ['payment_buyers'])

    def test_success_includes_evidence_context_defaults(self):
        from flask import Flask
        from api.api_response import success

        app = Flask(__name__)
        with app.test_request_context('/'):
            response, _ = success({'rows': []})
            payload = response.get_json()

        self.assertEqual(payload['evidence_level'], 'full')
        self.assertEqual(payload['missing_inputs'], [])
        self.assertEqual(payload['limitations'], [])
        self.assertEqual(payload['freshness'], {})
        self.assertEqual(payload['evidence'], [])
        self.assertEqual(payload['assumptions'], [])
        self.assertEqual(payload['unknowns'], [])

    def test_success_preserves_evidence_context(self):
        from flask import Flask
        from api.api_response import success

        app = Flask(__name__)
        with app.test_request_context('/'):
            response, _ = success(
                {},
                availability='partial',
                evidence_level='partial',
                missing_inputs=['product_visitors'],
                limitations=['商品转化率不可计算'],
                freshness={'as_of': '2026-08-13'},
                evidence=[{'source': 'batch-1'}],
                assumptions=['按自然日聚合'],
                unknowns=['缺少渠道归因'],
            )
            payload = response.get_json()

        self.assertEqual(payload['evidence_level'], 'partial')
        self.assertEqual(payload['missing_inputs'], ['product_visitors'])
        self.assertEqual(payload['limitations'], ['商品转化率不可计算'])
        self.assertEqual(payload['freshness']['as_of'], '2026-08-13')
        self.assertEqual(payload['evidence'][0]['source'], 'batch-1')
        self.assertEqual(payload['assumptions'], ['按自然日聚合'])
        self.assertEqual(payload['unknowns'], ['缺少渠道归因'])


if __name__ == '__main__':
    unittest.main()
