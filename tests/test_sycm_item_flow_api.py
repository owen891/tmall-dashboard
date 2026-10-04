import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class ItemFlowSummaryNoDataTests(unittest.TestCase):
    """范围内无数据必须回 200 + availability=no-data，而不是 400。

    前端以「data.channels 为空」渲染空态/回退口径；400 会被浏览器审计记为
    browserError（products 页预存基线失败项），也会让 domainRequest 直接 throw。
    """

    def setUp(self):
        import sqlite3

        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        database_path = os.path.join(self._tmp.name, 'item-flow.db')
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': database_path,
            'IMPORT_SCAN_ALLOWED_ROOTS': [],
        })
        # init_db 只建核心表；端点无数据分支会查询 sycm_item_flow_source_daily
        #（get_latest_date / item_flow_source_dates 只用到 stat_date + belong 列）。
        connection = sqlite3.connect(database_path)
        try:
            connection.execute('''CREATE TABLE sycm_item_flow_source_daily (
                id INTEGER PRIMARY KEY, stat_date TEXT, belong TEXT DEFAULT 'farthest'
            )''')
            connection.commit()
        finally:
            connection.close()
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def test_range_query_without_data_returns_no_data_envelope(self):
        response = self.client.get(
            '/api/sycm/item-flow/summary?item_id=977760995875&belong=all'
            '&start=2026-09-26&end=2026-10-02'
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['evidence_level'], 'insufficient')
        data = payload['data']
        self.assertEqual(data['channels'], [])
        self.assertEqual(data['levels'], [])
        self.assertEqual(data['data_dates'], [])
        self.assertEqual(data['data_days'], 0)
        self.assertEqual(data['requested_start'], '2026-09-26')
        self.assertEqual(data['requested_end'], '2026-10-02')
        self.assertEqual(data['channel_totals']['uv'], 0)
        self.assertTrue(payload['limitations'])

    def test_empty_table_without_date_args_returns_no_data_envelope(self):
        response = self.client.get('/api/sycm/item-flow/summary?belong=farthest')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'no-data')
        self.assertIsNone(payload['data']['requested_start'])
        self.assertEqual(payload['data']['channels'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
