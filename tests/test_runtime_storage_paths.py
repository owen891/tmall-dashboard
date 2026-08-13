import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RuntimeStoragePathsTests(unittest.TestCase):
    def test_runtime_database_keeps_backups_and_import_log_outside_code_tree(self):
        from scripts import import_data

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'data', 'dashboard.db')
            expected_data_dir = os.path.dirname(database_path)
            with patch.object(import_data, 'get_db_path', return_value=database_path):
                self.assertEqual(import_data.runtime_data_dir(), expected_data_dir)
                self.assertEqual(
                    import_data.runtime_backup_dir(),
                    os.path.join(expected_data_dir, 'backups'),
                )
                self.assertEqual(
                    import_data.runtime_import_log_path(),
                    os.path.join(expected_data_dir, 'import_log.json'),
                )

    def test_backup_is_created_beside_the_runtime_database(self):
        from scripts import import_data

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'data', 'dashboard.db')
            os.makedirs(os.path.dirname(database_path))
            connection = sqlite3.connect(database_path)
            try:
                connection.execute('CREATE TABLE facts (id INTEGER PRIMARY KEY)')
                connection.commit()
            finally:
                connection.close()

            with patch.object(import_data, 'get_db_path', return_value=database_path):
                self.assertTrue(import_data.backup_database())

            backup_dir = os.path.join(temp_dir, 'data', 'backups')
            backups = os.listdir(backup_dir)
            self.assertEqual(len(backups), 1)
            connection = sqlite3.connect(os.path.join(backup_dir, backups[0]))
            try:
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            finally:
                connection.close()

    def test_backups_created_in_the_same_second_use_distinct_paths(self):
        from scripts import import_data

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'data', 'dashboard.db')
            os.makedirs(os.path.dirname(database_path))
            connection = sqlite3.connect(database_path)
            try:
                connection.execute('CREATE TABLE facts (id INTEGER PRIMARY KEY)')
                connection.commit()
            finally:
                connection.close()

            fixed_time = datetime(2026, 8, 13, 2, 30, 0)

            class FixedDatetime(datetime):
                @classmethod
                def now(cls):
                    return fixed_time

            with patch.object(import_data, 'get_db_path', return_value=database_path), patch.object(
                import_data,
                'datetime',
                FixedDatetime,
            ):
                self.assertTrue(import_data.backup_database())
                self.assertTrue(import_data.backup_database())

            backups = os.listdir(os.path.join(temp_dir, 'data', 'backups'))
            self.assertEqual(len(backups), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
