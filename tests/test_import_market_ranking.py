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

    def test_apply_requires_backup(self):
        with tempfile.TemporaryDirectory(prefix='tmall-market-ranking-') as directory:
            root = Path(directory)
            database = root / 'dashboard.db'
            source = root / 'analysis.json'
            source.write_text(json.dumps({'mid': {}, 'long': {}, 'overlap_shops': []}), encoding='utf-8')
            sqlite3.connect(database).close()

            with self.assertRaises(SystemExit):
                main(['--db', str(database), '--json', str(source), '--apply'])


if __name__ == '__main__':
    unittest.main()
