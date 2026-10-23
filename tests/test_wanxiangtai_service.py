import unittest
import os
import tempfile
from app import create_app

from services.wanxiangtai_service import WanxiangtaiService


class WanxiangtaiServiceTests(unittest.TestCase):
    def test_charge_sum_single_day_is_daily(self):
        payload = {'data': {'searchCharge': '12.5', 'contentSceneCharge': 0}}
        rows = WanxiangtaiService.parse_charge_sum_response(
            payload, '2026-09-17', '2026-09-17'
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['date'], '2026-09-17')
        self.assertEqual(rows[0]['granularity'], 'day')
        self.assertEqual(rows[0]['ad_spend'], 12.5)

    def test_charge_sum_multi_day_is_summary_not_last_day(self):
        payload = {'data': {'searchCharge': 42, 'shopCharge': 8}}
        rows = WanxiangtaiService.parse_charge_sum_response(
            payload, '2026-09-10', '2026-09-16'
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['date'] is None for row in rows))
        self.assertTrue(all(row['granularity'] == 'summary' for row in rows))
        self.assertTrue(all(row['period_start'] == '2026-09-10' for row in rows))
        self.assertTrue(all(row['period_end'] == '2026-09-16' for row in rows))

    def test_query_maps_direct_payment_amount_only_from_amount_field(self):
        payload = {
            'data': {'list': [{
                'date': '2026-09-17',
                'charge': 10,
                'alipayInshopAmt': 20,
                'alipayInshopNum': 2,
                'alipayDirAmt': 3,
                'alipayDirNum': 99,
            }]}
        }
        rows = WanxiangtaiService.parse_query_response(payload)
        self.assertEqual(rows[0]['direct_payment_amount'], 3.0)
        self.assertNotEqual(rows[0]['direct_payment_amount'], 99)

    def test_import_persists_multi_day_charge_sum_as_summary(self):
        temp_dir = tempfile.TemporaryDirectory(prefix='wanxiangtai-api-')
        try:
            app = create_app({
                'TESTING': True,
                'DATABASE_PATH': os.path.join(temp_dir.name, 'dashboard.db'),
            })
            response = app.test_client().post('/api/wanxiangtai/import', json={
                'payload': {'data': {'searchCharge': 42}},
                'start_date': '2026-09-10',
                'end_date': '2026-09-16',
            })
            self.assertEqual(response.status_code, 201)
            body = response.get_json()
            self.assertEqual(body['data']['target'], 'promotion_period_summary')
            with app.app_context():
                from db import get_db
                with get_db() as conn:
                    row = conn.execute(
                        'SELECT period_start, period_end, ad_spend FROM promotion_period_summary'
                    ).fetchone()
                    staging = conn.execute(
                        "SELECT status, source_key FROM collector_data_staging WHERE batch_id = ?",
                        (body['data']['batch_id'],),
                    ).fetchone()
            self.assertEqual(dict(row), {
                'period_start': '2026-09-10', 'period_end': '2026-09-16', 'ad_spend': 42.0,
            })
            self.assertEqual(dict(staging), {'status': 'published', 'source_key': 'wanxiangtai'})
        finally:
            temp_dir.cleanup()

    def test_import_rejects_report_when_requested_impressions_are_absent_everywhere(self):
        temp_dir = tempfile.TemporaryDirectory(prefix='wanxiangtai-missing-impressions-')
        try:
            app = create_app({
                'TESTING': True,
                'DATABASE_PATH': os.path.join(temp_dir.name, 'dashboard.db'),
            })
            response = app.test_client().post('/api/wanxiangtai/import', json={
                'payload': {'data': {'list': [{
                    'date': '2026-09-26', 'promotionId': 'product-1',
                    'charge': 0, 'click': 0, 'alipayInshopAmt': 25,
                }]}},
                'report_type': 'item_promotion', 'split_type': 'day',
                'start_date': '2026-09-26', 'end_date': '2026-09-26',
            })
            self.assertEqual(response.status_code, 422)
            self.assertIn('缺少已请求的展现字段', response.get_json()['message'])
            with app.app_context():
                from db import get_db
                with get_db() as conn:
                    self.assertEqual(conn.execute(
                        'SELECT COUNT(*) FROM promotion_daily_facts'
                    ).fetchone()[0], 0)
        finally:
            temp_dir.cleanup()

    def test_import_rejects_active_rows_missing_impressions_even_when_other_rows_have_them(self):
        temp_dir = tempfile.TemporaryDirectory(prefix='wanxiangtai-partial-impressions-')
        try:
            app = create_app({
                'TESTING': True,
                'DATABASE_PATH': os.path.join(temp_dir.name, 'dashboard.db'),
            })
            response = app.test_client().post('/api/wanxiangtai/import', json={
                'payload': {'data': {'list': [
                    {'date': '2026-09-30', 'promotionId': 'known', 'charge': 4,
                     'click': 2, 'adPv': 100},
                    {'date': '2026-09-30', 'promotionId': 'broken', 'charge': 2,
                     'click': 1},
                ]}},
                'report_type': 'item_promotion', 'split_type': 'day',
                'start_date': '2026-09-30', 'end_date': '2026-09-30',
            })
            self.assertEqual(response.status_code, 422)
            self.assertIn('投放行缺失', response.get_json()['message'])
            with app.app_context():
                from db import get_db
                with get_db() as conn:
                    self.assertEqual(conn.execute(
                        'SELECT COUNT(*) FROM promotion_daily_facts'
                    ).fetchone()[0], 0)
        finally:
            temp_dir.cleanup()

    def test_period_summary_endpoint_reads_interval_rows(self):
        temp_dir = tempfile.TemporaryDirectory(prefix='wanxiangtai-summary-')
        try:
            app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(temp_dir.name, 'dashboard.db')})
            client = app.test_client()
            imported = client.post('/api/wanxiangtai/import', json={
                'payload': {'data': {'searchCharge': 42}},
                'start_date': '2026-09-10', 'end_date': '2026-09-16',
            })
            self.assertEqual(imported.status_code, 201)
            response = client.get('/api/wanxiangtai/period-summary?start_date=2026-09-10&end_date=2026-09-16')
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertEqual(body['data']['row_count'], 1)
            self.assertEqual(body['data']['rows'][0]['period_end'], '2026-09-16')
        finally:
            temp_dir.cleanup()

    def test_import_links_staging_to_collector_run(self):
        temp_dir = tempfile.TemporaryDirectory(prefix='wanxiangtai-run-link-')
        try:
            app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(temp_dir.name, 'dashboard.db')})
            client = app.test_client()
            run_id = 'collector-run-123'
            from services.collector_run_service import create_run
            run_id = create_run('wanxiangtai', 'default', db_path=app.config['DATABASE_PATH'])
            imported = client.post('/api/wanxiangtai/import', json={
                'payload': {'data': {'searchCharge': 9}},
                'start_date': '2026-09-17', 'end_date': '2026-09-17',
                'source_run_id': run_id,
            })
            self.assertEqual(imported.status_code, 201)
            response = client.get(f'/api/collect/runs/{run_id}/staging')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['data']['row_count'], 1)
        finally:
            temp_dir.cleanup()


if __name__ == '__main__':
    unittest.main()
