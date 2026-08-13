import io
import os
import sys
import tempfile
import unittest

from openpyxl import Workbook


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class ImportWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-import-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app
        from db import get_db

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()
        self.get_db = get_db

    def tearDown(self):
        self.temp_dir.cleanup()

    def preview(self, headers, rows):
        response = self.client.post(
            '/api/imports/preview',
            data={'file': (workbook_bytes(headers, rows), 'product-daily.xlsx')},
            content_type='multipart/form-data',
        )
        payload = response.get_json()
        response.close()
        return response.status_code, payload

    def test_preview_does_not_write_and_identifies_unmapped_required_field(self):
        status, payload = self.preview(
            ['日期', '商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['2026-04-01', 'import-a', 100, 10, 20, 3]],
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['source_type'], 'product_day')
        self.assertEqual(payload['data']['required_unmapped'], ['ad_spend'])
        with self.get_db(self.database_path) as connection:
            facts = connection.execute('SELECT COUNT(*) FROM daily_data').fetchone()[0]
            batches = connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0]
        self.assertEqual(facts, 0)
        self.assertEqual(batches, 0)

    def test_confirm_requires_mapping_and_is_idempotent_by_business_key(self):
        headers = ['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数', '推广花费']
        rows = [['2026-04-01', 'import-a', '导入商品', 100, 10, 20, 3, 20]]
        status, preview = self.preview(headers, rows)
        self.assertEqual(status, 200)
        preview_id = preview['data']['id']

        missing_mapping = self.client.post('/api/imports', json={'preview_id': preview_id, 'mapping': {}})
        self.assertEqual(missing_mapping.status_code, 422)
        missing_mapping.close()

        first = self.client.post('/api/imports', json={
            'preview_id': preview_id,
            'mapping': preview['data']['mapping'],
        })
        first_payload = first.get_json()
        first.close()
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first_payload['ok'])
        self.assertEqual(first_payload['data']['inserted_count'], 1)

        _, second_preview = self.preview(headers, [['2026-04-01', 'import-a', '导入商品', 120, 10, 20, 3, 30]])
        second = self.client.post('/api/imports', json={
            'preview_id': second_preview['data']['id'],
            'mapping': second_preview['data']['mapping'],
        })
        second_payload = second.get_json()
        second.close()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second_payload['data']['updated_count'], 1)

        with self.get_db(self.database_path) as connection:
            facts = connection.execute('SELECT COUNT(*) FROM daily_data').fetchone()[0]
            payment_amount = connection.execute(
                'SELECT payment_amount FROM daily_data WHERE product_id = ? AND date = ?',
                ('import-a', '2026-04-01'),
            ).fetchone()[0]
            batches = connection.execute("SELECT COUNT(*) FROM import_batches WHERE status = 'completed'").fetchone()[0]
        self.assertEqual(facts, 1)
        self.assertEqual(payment_amount, 120.0)
        self.assertEqual(batches, 2)

    def test_preview_accepts_explicit_mapping_and_batch_can_be_reverted(self):
        headers = ['统计日', '商品编号', '成交额', '退款额', '访客', '买家', '消耗']
        rows = [['2026-04-02', 'import-revert', 300, 30, 100, 10, 50]]
        response = self.client.post(
            '/api/imports/preview?source_type=product_day',
            data={'file': (workbook_bytes(headers, rows), 'custom.xlsx')},
            content_type='multipart/form-data',
        )
        preview = response.get_json()['data']
        response.close()
        mapping = {
            'date': '统计日', 'product_id': '商品编号', 'payment_amount': '成交额',
            'successful_refund_amount': '退款额', 'product_visitors': '访客',
            'payment_buyers': '买家', 'ad_spend': '消耗',
        }
        confirmed = self.client.post('/api/imports', json={'preview_id': preview['id'], 'mapping': mapping})
        batch_id = confirmed.get_json()['data']['id']
        confirmed.close()

        history = self.client.get('/api/imports')
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()['data'][0]['id'], batch_id)
        history.close()

        reverted = self.client.post(f'/api/imports/{batch_id}/revert')
        self.assertEqual(reverted.status_code, 200)
        self.assertTrue(reverted.get_json()['data']['reverted'])
        reverted.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM daily_data WHERE product_id = 'import-revert'").fetchone()[0], 0)

    def test_store_daily_source_is_imported_by_business_key(self):
        status, preview = self.preview(['日期', '支付金额', '退款金额', '商品访客数', '支付买家数'], [['2026-04-03', 500, 50, 100, 20]])
        self.assertEqual(status, 200)
        response = self.client.post('/api/imports/preview?source_type=store_day', data={'file': (workbook_bytes(['日期', '支付金额', '退款金额', '商品访客数', '支付买家数'], [['2026-04-03', 500, 50, 100, 20]]), 'store.xlsx')}, content_type='multipart/form-data')
        preview = response.get_json()['data']; response.close()
        confirmed = self.client.post('/api/imports', json={'preview_id': preview['id'], 'mapping': preview['mapping']})
        self.assertEqual(confirmed.status_code, 201); confirmed.close()
        with self.get_db(self.database_path) as connection:
            row = connection.execute("SELECT payment_amount, payment_buyers FROM store_daily_facts WHERE date = '2026-04-03'").fetchone()
        self.assertEqual(tuple(row), (500.0, 20))

    def test_promotion_and_customer_sources_use_their_own_required_fields_and_quality_keys(self):
        promotion = self.client.post(
            '/api/imports/preview?source_type=promotion_campaign_day',
            data={'file': (workbook_bytes(
                ['date', 'channel', 'campaign_id', 'ad_spend', 'attributed_payment_amount'],
                [['2026-04-05', 'search', 'campaign-a', 12, 60]],
            ), 'promotion.xlsx')}, content_type='multipart/form-data',
        )
        payload = promotion.get_json()['data']; promotion.close()
        self.assertEqual(payload['valid_rows'], 1)
        self.assertEqual(payload['invalid_rows'], 0)
        self.assertEqual(payload['required_unmapped'], [])
        self.assertIn('campaign_id', payload['mapping_schema']['required'])
        self.assertNotIn('product_id', payload['mapping_schema']['required'])

        confirmed = self.client.post('/api/imports', json={'preview_id': payload['id'], 'mapping': payload['mapping']})
        self.assertEqual(confirmed.status_code, 201); confirmed.close()
        with self.get_db(self.database_path) as connection:
            row = connection.execute(
                "SELECT channel, campaign_id, attributed_payment_amount FROM promotion_daily_facts"
            ).fetchone()
        self.assertEqual(tuple(row), ('search', 'campaign-a', 60.0))

    def test_invalid_generic_rows_are_reported_and_rejected_before_a_batch_is_written(self):
        response = self.client.post(
            '/api/imports/preview?source_type=customer_day',
            data={'file': (workbook_bytes(
                ['date', 'payment_buyers', 'returning_payment_buyers'],
                [['not-a-date', 10, 4]],
            ), 'customers.xlsx')}, content_type='multipart/form-data',
        )
        preview = response.get_json()['data']; response.close()
        self.assertEqual(preview['valid_rows'], 0)
        self.assertEqual(preview['invalid_rows'], 1)
        self.assertTrue(preview['invalid_details'])
        confirmed = self.client.post('/api/imports', json={'preview_id': preview['id'], 'mapping': preview['mapping']})
        self.assertEqual(confirmed.status_code, 422); confirmed.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0], 0)

    def test_reverting_older_batch_rejects_when_newer_batch_owns_same_fact(self):
        headers = ['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数', '推广花费']
        def import_one(payment):
            _, preview = self.preview(headers, [['2026-04-04', 'import-order', '顺序商品', payment, 0, 10, 2, 1]])
            response = self.client.post('/api/imports', json={'preview_id': preview['data']['id'], 'mapping': preview['data']['mapping']})
            payload = response.get_json(); response.close(); return payload['data']['id']
        older = import_one(100)
        import_one(200)
        response = self.client.post(f'/api/imports/{older}/revert')
        self.assertEqual(response.status_code, 409)
        response.close()
        with self.get_db(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT payment_amount FROM daily_data WHERE product_id='import-order' AND date='2026-04-04'").fetchone()[0], 200.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
