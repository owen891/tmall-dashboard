import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


COLLECTOR_PATH = Path(
    os.environ.get(
        'TMALL_SYCM_ITEM_FLOW_COLLECTOR',
        r'E:\www\BI采集\collectors\collect_sycm_item_flow_v6.py',
    )
)


@unittest.skipUnless(COLLECTOR_PATH.is_file(), 'external sycm item-flow collector is unavailable')
class SycmItemFlowCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('sycm_item_flow_collector_test_target', COLLECTOR_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    class _Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.body

    def _success_response(self):
        return self._Response(json.dumps({'code': 0, 'content': {}}).encode('utf-8'))

    def test_call_api_retries_transient_http_failure(self):
        module = self.module
        module.API_RETRIES = 2
        module.API_RETRY_DELAY = 0
        error = HTTPError('https://example.test', 502, 'bad gateway', {}, None)
        with patch.object(module.urllib.request, 'urlopen', side_effect=[error, self._success_response()]) as request:
            result = module.call_api('', 'https://example.test', 'https://example.test/ref')
        self.assertEqual(result['code'], 0)
        self.assertEqual(request.call_count, 2)

    def test_call_api_retries_empty_response(self):
        module = self.module
        module.API_RETRIES = 2
        module.API_RETRY_DELAY = 0
        with patch.object(module.urllib.request, 'urlopen', side_effect=[self._Response(b''), self._success_response()]) as request:
            result = module.call_api('', 'https://example.test', 'https://example.test/ref')
        self.assertEqual(result['code'], 0)
        self.assertEqual(request.call_count, 2)

    def test_save_to_db_creates_a_schema_compatible_with_the_insert(self):
        import sqlite3

        conn = sqlite3.connect(':memory:')
        try:
            self.module.save_to_db(conn, [{
                'item_id': 'item-1',
                'channel_name': '搜索',
                'parent_channel': '站内',
                'level': 1,
                'page_level': 1,
                'channel_type': 'search',
                'uv': 1,
                'pv': 2,
                'pay_amount': 3,
                'pay_buyer_count': 1,
                'pay_rate': 0.5,
                'cart_buyer_count': 1,
                'collect_count': 1,
                'deal_buyer_count': 1,
                'pay_item_count': 1,
                'new_uv': 1,
                'page_id': 'page-1',
            }], '2026-09-21')
            columns = {row[1] for row in conn.execute(
                'PRAGMA table_info(sycm_item_flow_source_daily)'
            )}
            self.assertTrue({'parent_channel', 'level', 'page_level', 'collect_item_count', 'collect_count'} <= columns)
            row = conn.execute(
                'SELECT item_id, parent_channel, level, page_level, collect_item_count, collect_count '
                'FROM sycm_item_flow_source_daily'
            ).fetchone()
            self.assertEqual(row, ('item-1', '站内', 1, 1, 1, 1))
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
