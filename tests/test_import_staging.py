import json
import os
import tempfile
import unittest
from uuid import uuid4


class ImportStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-staging-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_publish_keeps_staging_rows_as_audit_evidence(self):
        from db import get_db
        from repos.import_repo import ImportRepo

        batch_id = uuid4().hex
        batch = {
            'id': batch_id,
            'shop_id': 'default',
            'source_type': 'store_day',
            'source_filename': 'store.csv',
            'source_hash': 'hash',
            'total_rows': 1,
            'valid_rows': 1,
            'invalid_rows': 0,
            'quality_summary': json.dumps({'total_rows': 1}),
        }
        rows = [{
            'shop_id': 'default',
            'date': '2026-09-17',
            'payment_amount': 100.0,
            'successful_refund_amount': 2.0,
            'product_visitors': 10,
            'payment_buyers': 3,
            'source_batch_id': batch_id,
        }]
        with self.app.app_context():
            ImportRepo.complete_generic_batch(batch, 'store_daily_facts', ('shop_id', 'date'), rows)
            with get_db() as conn:
                staged = conn.execute(
                    'SELECT status, payload_json, published_at FROM import_staging_rows WHERE batch_id = ?',
                    (batch_id,),
                ).fetchone()
                fact = conn.execute(
                    'SELECT payment_amount FROM store_daily_facts WHERE shop_id = ? AND date = ?',
                    ('default', '2026-09-17'),
                ).fetchone()
        self.assertIsNotNone(staged)
        self.assertEqual(staged['status'], 'published')
        self.assertIsNotNone(staged['published_at'])
        self.assertEqual(json.loads(staged['payload_json'])['payment_amount'], 100.0)
        self.assertEqual(fact['payment_amount'], 100.0)

        response = self.app.test_client().get(f'/api/imports/{batch_id}/staging')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['data'])


if __name__ == '__main__':
    unittest.main()
