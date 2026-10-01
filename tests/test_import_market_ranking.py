import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.import_market_ranking import main


class ImportMarketRankingTests(unittest.TestCase):
    def test_preview_does_not_create_or_mutate_database(self):
        with tempfile.TemporaryDirectory(prefix='tmall-market-ranking-') as directory:
            root = Path(directory)
            database = root / 'dashboard.db'
            source = root / 'analysis.json'
            source.write_text(json.dumps({'mid': {}, 'long': {}, 'overlap_shops': []}), encoding='utf-8')

            self.assertEqual(main(['--db', str(database), '--json', str(source)]), 0)
            self.assertFalse(database.exists())

    def test_apply_uses_json_period_and_imports_panty(self):
        with tempfile.TemporaryDirectory(prefix='tmall-market-ranking-') as directory:
            root = Path(directory)
            database = root / 'dashboard.db'
            backup = root / 'dashboard-backup.db'
            source = root / 'analysis.json'
            sqlite3.connect(database).close()
            payload = {
                'analysis_date': '2026-09-27',
                'period_start': '2026-09-21',
                'period_end': '2026-09-27',
                'categories': {'mid': '中筒袜', 'long': '长筒袜', 'panty': '连裤袜'},
                'mid': {
                    'rising': [[253, '上升商品A', '店铺A', 30, 12, 1]],
                    'falling': [[167, '下降商品B', '店铺B', 223, 8, None]],
                },
                'long': {}, 'panty': {}, 'overlap_shops': [],
            }
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

            self.assertEqual(main([
                '--db', str(database), '--json', str(source), '--apply',
                '--backup-destination', str(backup),
            ]), 0)
            connection = sqlite3.connect(database)
            try:
                run = connection.execute(
                    'SELECT analysis_date, period_start, period_end FROM market_analysis_runs'
                ).fetchone()
                categories = connection.execute(
                    'SELECT category FROM market_category_stats ORDER BY category'
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual(run, ('2026-09-27', '2026-09-21', '2026-09-27'))
            self.assertEqual(categories, [('中筒袜',), ('连裤袜',), ('长筒袜',)])

    def test_apply_rising_falling_store_rank_and_change_separately(self):
        """上升/下降榜：rank=当前排名、rank_change=变化幅度，buyers 不再存排名。"""
        with tempfile.TemporaryDirectory(prefix='tmall-market-ranking-') as directory:
            root = Path(directory)
            database = root / 'dashboard.db'
            backup = root / 'dashboard-backup.db'
            source = root / 'analysis.json'
            sqlite3.connect(database).close()
            payload = {
                'analysis_date': '2026-09-27',
                'period_start': '2026-09-21', 'period_end': '2026-09-27',
                'mid': {
                    'rising': [[253, '上升商品A', '店铺A', 30, 12, 1]],
                    'falling': [[167, '下降商品B', '店铺B', 223, 8, None]],
                },
                'overlap_shops': [],
            }
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

            self.assertEqual(main([
                '--db', str(database), '--json', str(source), '--apply',
                '--backup-destination', str(backup),
            ]), 0)
            connection = sqlite3.connect(database)
            try:
                rows = connection.execute(
                    '''SELECT list_type, rank, rank_change, buyers, title
                       FROM market_products WHERE list_type IN ('上升榜','下降榜')
                       ORDER BY list_type'''
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual(rows, [
                ('上升榜', 30, 253, None, '上升商品A'),
                ('下降榜', 223, 167, None, '下降商品B'),
            ])


if __name__ == '__main__':
    unittest.main()
