import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class BackupRetentionEnforcementTests(unittest.TestCase):
    """改进路线 2026-10-01 P1.3：轮转必须在 backup_database() 函数级生效。

    此前裁剪只挂在 CLI 的「默认落点」分支上，aggregate_store_daily 等显式
    指定目的地的调用方从不裁剪，data/backups 堆到 7 份 24GB。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-backup-prune-')
        self.root = Path(self.temp.name)
        source = self.root / 'dashboard.db'
        connection = sqlite3.connect(source)
        try:
            connection.execute('CREATE TABLE t (x INTEGER)')
            connection.commit()
        finally:
            connection.close()
        self.source = source
        self.backup_dir = self.root / 'backups'
        self.backup_dir.mkdir()
        for index in range(3):
            stale = self.backup_dir / f'dashboard-{index}.db'
            stale.write_bytes(b'stale-backup' * 8)
            # mtime 全程确定性：快速循环里创建的文件可能共享时间戳，裁剪按 mtime 排序
            os.utime(stale, (1_000_000 + index * 100, 1_000_000 + index * 100))

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_destination_still_prunes(self):
        from scripts import backup_retention
        from scripts.backup_database import backup_database

        # 收紧保留数让裁剪可观测：3 份陈旧备份里只留最新 1 份（新的这份受 protected 保护）
        with mock.patch.object(backup_retention, 'retention_settings', return_value=(1, 1024 ** 3)):
            report = backup_database(self.source, self.backup_dir / 'dashboard-new.db')

        self.assertTrue(report['ok'])
        pruned = {Path(item).name for item in report['pruned']}
        self.assertEqual(pruned, {'dashboard-0.db', 'dashboard-1.db'})
        self.assertFalse((self.backup_dir / 'dashboard-0.db').exists())
        self.assertFalse((self.backup_dir / 'dashboard-1.db').exists())
        # 最新陈旧备份与本次备份必须还在
        self.assertTrue((self.backup_dir / 'dashboard-2.db').exists())
        self.assertTrue((self.backup_dir / 'dashboard-new.db').exists())

    def test_prune_failure_does_not_break_backup(self):
        from scripts import backup_retention
        from scripts.backup_database import backup_database

        with mock.patch.object(backup_retention, 'prune_backups', side_effect=OSError('disk busy')):
            report = backup_database(self.source, self.backup_dir / 'dashboard-new.db')

        self.assertTrue(report['ok'])
        self.assertIsNone(report['pruned'])
        self.assertIn('prune_warning', report)
        self.assertTrue((self.backup_dir / 'dashboard-new.db').exists())


if __name__ == '__main__':
    unittest.main()
