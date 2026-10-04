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

    【2026-10-04 契约修正】断言按 docs/BACKUP_RETENTION_PLAN_20261004.md 第 2 节
    C1/C2 重写：``keep_newest`` 是「裁剪后目录内匹配文件的总数上限」，protected
    项**占用**该配额（``len(protected) >= keep_newest`` 时非 protected 全裁，
    C1.1）。旧实现「先剔除 protected、再对剩余应用 keep_newest」会让稳态份数
    变成 ``keep_newest + len(protected)``，与本文件的断言不相容——这正是本次要
    修掉的语义漂移。
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

    def _matching_names(self):
        """目录内匹配 ``*.db`` 的文件名（C1 下这就是受 keep_newest 约束的总数）。"""
        return sorted(item.name for item in self.backup_dir.glob('*.db'))

    def test_explicit_destination_still_prunes(self):
        """显式目的地也必须裁剪；keep_newest=1 时总数上限就是 1（protected 占配额）。"""
        from scripts import backup_retention
        from scripts.backup_database import backup_database

        # 收紧保留数让裁剪可观测：目录内匹配文件总数上限 = 1，
        # 而本次新备份（protected）本身就占满这 1 个配额 ⇒ 3 份陈旧备份全裁（C1.1）
        with mock.patch.object(backup_retention, 'retention_settings', return_value=(1, 1024 ** 3)):
            report = backup_database(self.source, self.backup_dir / 'dashboard-new.db')

        self.assertTrue(report['ok'])
        pruned = {Path(item).name for item in report['pruned']}
        # C1.1：len(protected)=1 >= keep_newest=1，非 protected 全部裁掉
        self.assertEqual(pruned, {'dashboard-0.db', 'dashboard-1.db', 'dashboard-2.db'})
        self.assertFalse((self.backup_dir / 'dashboard-0.db').exists())
        self.assertFalse((self.backup_dir / 'dashboard-1.db').exists())
        self.assertFalse((self.backup_dir / 'dashboard-2.db').exists())
        # 本次备份受 protected 保护，必然还在
        self.assertTrue((self.backup_dir / 'dashboard-new.db').exists())
        # C1 的核心：keep_newest 是目录内匹配文件总数上限，protected 计入其中
        self.assertEqual(self._matching_names(), ['dashboard-new.db'])

    def test_keep_newest_counts_protected_towards_the_cap(self):
        """C2：非 protected 保留数 = max(0, keep_newest - len(protected))。

        keep_newest=2、protected=[本次新备份] ⇒ 只再留 1 份最新的陈旧备份，
        目录内总数 = 2；旧实现会在剔除 protected 后仍保留 2 份陈旧备份，总数 3。
        """
        from scripts import backup_retention
        from scripts.backup_database import backup_database

        with mock.patch.object(backup_retention, 'retention_settings', return_value=(2, 1024 ** 3)):
            report = backup_database(self.source, self.backup_dir / 'dashboard-new.db')

        self.assertTrue(report['ok'])
        pruned = {Path(item).name for item in report['pruned']}
        self.assertEqual(pruned, {'dashboard-0.db', 'dashboard-1.db'})
        self.assertFalse((self.backup_dir / 'dashboard-0.db').exists())
        self.assertFalse((self.backup_dir / 'dashboard-1.db').exists())
        # 保留最新的陈旧备份（dashboard-2.db，mtime 最大）与本次受保护的新备份
        self.assertTrue((self.backup_dir / 'dashboard-2.db').exists())
        self.assertTrue((self.backup_dir / 'dashboard-new.db').exists())
        self.assertEqual(self._matching_names(), ['dashboard-2.db', 'dashboard-new.db'])

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
