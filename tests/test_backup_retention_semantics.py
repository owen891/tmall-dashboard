"""冻结契约 v2（docs/BACKUP_RETENTION_PLAN_20261004.md 第 2 节 C1–C7）的契约测试。

本文件**只依赖契约文本**，不读真实 ``config.yaml`` 的当前数值、不触碰
``data/`` 下任何文件：所有 fixture 都在 ``tempfile.TemporaryDirectory`` 内构造。

覆盖：T-A2 / T-A3（修正版 C1.1）/ T-A4（C3）/ T-A7（C4）/ T-A8（C1.1×C3）/
T-A9（C6）/ T-A5（C5）+ C5 unlink 容错 + **回归护栏**（复刻旧实现，证明新用例
真的能抓到旧行为：稳态份数 = keep_newest + len(protected)）。
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.backup_retention import prune_backups, retention_settings


class _Fixture(unittest.TestCase):
    """公共 fixture：一个干净的临时备份目录 + 确定性 mtime 的假备份文件。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-retention-sem-')
        self.root = Path(self.temp.name)
        self.backup_dir = self.root / 'backups'
        self.backup_dir.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def make(self, name, size=100, rank=1):
        """造一份假备份；``rank`` 越大 mtime 越新（裁剪按「新的在前」）。"""
        path = self.backup_dir / name
        path.write_bytes(b'x' * size)
        stamp = 1_000_000 + rank * 100
        os.utime(path, (stamp, stamp))
        return path

    def names(self):
        return sorted(item.name for item in self.backup_dir.glob('*.db'))

    def kept_bytes(self):
        return sum(item.stat().st_size for item in self.backup_dir.glob('*.db'))

    def removed_names(self, removed):
        return sorted(Path(item).name for item in removed)


class ContractSemanticsTests(_Fixture):
    BIG = 1024 ** 3  # 容量不设约束时的「足够大」

    # --- T-A2 / C1：protected 占用 keep_newest 配额 -------------------------
    def test_ta2_keep_newest_is_total_cap_including_protected(self):
        for index in range(1, 6):
            self.make(f'b{index}.db', size=100, rank=index)
        protected = self.backup_dir / 'b5.db'

        removed = prune_backups(
            self.backup_dir, keep_newest=4, max_total_bytes=self.BIG,
            protected=[protected],
        )

        self.assertEqual(self.names(), ['b2.db', 'b3.db', 'b4.db', 'b5.db'])
        self.assertEqual(self.removed_names(removed), ['b1.db'])
        self.assertTrue(protected.exists())

    # --- T-A3（修正版）/ C1.1：len(protected) >= keep_newest ----------------
    def test_ta3_protected_saturating_the_quota_prunes_all_others(self):
        for index in range(1, 5):
            self.make(f'b{index}.db', size=100, rank=index)
        protected = [self.backup_dir / 'b4.db', self.backup_dir / 'b3.db']

        removed = prune_backups(
            self.backup_dir, keep_newest=2, max_total_bytes=self.BIG,
            protected=protected,
        )

        self.assertEqual(self.names(), ['b3.db', 'b4.db'])
        self.assertEqual(self.removed_names(removed), ['b1.db', 'b2.db'])
        for item in protected:
            self.assertTrue(item.exists())

    # --- T-A4 / C3：容量超限的项被裁 ---------------------------------------
    def test_ta4_over_capacity_item_is_pruned_while_count_slots_remain(self):
        self.make('s1.db', size=100, rank=5)
        self.make('s2.db', size=100, rank=4)
        self.make('s3.db', size=100, rank=3)
        self.make('big.db', size=900, rank=2)
        self.make('s5.db', size=100, rank=1)

        removed = prune_backups(
            self.backup_dir, keep_newest=4, max_total_bytes=1000,
        )

        self.assertEqual(self.names(), ['s1.db', 's2.db', 's3.db', 's5.db'])
        self.assertEqual(self.removed_names(removed), ['big.db'])
        self.assertLessEqual(self.kept_bytes(), 1000)

    # --- T-A7 / C4：单体 protected 超 cap → 保留 + over_capacity，不抛异常 ---
    def test_ta7_protected_over_capacity_is_kept_and_reported(self):
        self.make('big-protected.db', size=5000, rank=2)
        self.make('small.db', size=100, rank=1)
        report = {}

        removed = prune_backups(
            self.backup_dir, keep_newest=1, max_total_bytes=1000,
            protected=[self.backup_dir / 'big-protected.db'], report=report,
        )

        self.assertTrue((self.backup_dir / 'big-protected.db').exists())
        self.assertFalse((self.backup_dir / 'small.db').exists())
        self.assertEqual(self.removed_names(removed), ['small.db'])
        self.assertIs(report.get('over_capacity'), True)
        # C5：返回值类型不变，仍是「被删除路径列表」
        self.assertIsInstance(removed, list)

    # --- T-A8 / C1.1 × C3 组合 ---------------------------------------------
    def test_ta8_protected_saturation_combined_with_capacity_overflow(self):
        self.make('p1.db', size=200, rank=3)
        self.make('p2.db', size=200, rank=2)
        self.make('s1.db', size=100, rank=1)
        report = {}

        removed = prune_backups(
            self.backup_dir, keep_newest=2, max_total_bytes=300,
            protected=[self.backup_dir / 'p1.db', self.backup_dir / 'p2.db'],
            report=report,
        )

        # C1.1 优先：protected 全留、非 protected 全裁，总数 = len(protected) = 2
        self.assertEqual(self.names(), ['p1.db', 'p2.db'])
        self.assertEqual(self.removed_names(removed), ['s1.db'])
        # C4：protected 自身 400B > 300B，不抛异常但必须暴露超限
        self.assertIs(report.get('over_capacity'), True)

    # --- T-A10 / C1.1 × C4：len(protected) > keep_newest 且 protected 自身超 cap ---
    def test_ta10_protected_beyond_quota_still_counts_towards_capacity(self):
        """F-01 回归：protected 多于配额时，**全部** protected 的字节都必须计入 cap。

        构造：3 份 protected（rank 11/12/13，各 400B，合计 1200B > cap 1000）+ 2 份非 protected。
        契约：protected 全留（C1.1，3 份）、非 protected 全裁（slots = max(0, 2-3) = 0）、
        全部 protected 合计超 cap ⇒ C4：over_capacity=True 且记录 warning。
        未修复实现把 protected 截断成 [:keep] 再统计字节（只算 800B）⇒ 漏报 over_capacity 与 warning。
        """
        for index in range(1, 4):
            self.make(f'p{index}.db', size=400, rank=10 + index)
        self.make('s1.db', size=100, rank=2)
        self.make('s2.db', size=100, rank=1)
        report = {}

        with self.assertLogs('scripts.backup_retention', level='WARNING') as captured:
            removed = prune_backups(
                self.backup_dir, keep_newest=2, max_total_bytes=1000,
                protected=[self.backup_dir / f'p{index}.db' for index in range(1, 4)],
                report=report,
            )

        self.assertEqual(self.names(), ['p1.db', 'p2.db', 'p3.db'])
        self.assertEqual(self.removed_names(removed), ['s1.db', 's2.db'])
        self.assertIs(report.get('over_capacity'), True)
        self.assertTrue(captured.output, 'C4 超限必须记录 warning')

    # --- T-A11 / C4 反向：protected 多于配额但未超 cap → 不得过度告警 ---------
    def test_ta11_protected_beyond_quota_within_capacity_is_not_over_capacity(self):
        """len(protected)=3 > keep=2，但 protected 合计 300B <= cap 1000 ⇒ 不应报超限。"""
        for index in range(1, 4):
            self.make(f'p{index}.db', size=100, rank=10 + index)
        self.make('s1.db', size=100, rank=2)
        self.make('s2.db', size=100, rank=1)
        report = {}

        with self.assertNoLogs('scripts.backup_retention', level='WARNING'):
            removed = prune_backups(
                self.backup_dir, keep_newest=2, max_total_bytes=1000,
                protected=[self.backup_dir / f'p{index}.db' for index in range(1, 4)],
                report=report,
            )

        self.assertFalse(report.get('over_capacity'))
        self.assertEqual(self.names(), ['p1.db', 'p2.db', 'p3.db'])
        self.assertEqual(self.removed_names(removed), ['s1.db', 's2.db'])

    # --- T-A9 / C6：keep_newest 夹取到 >= 1 --------------------------------
    def test_ta9_zero_or_negative_keep_newest_is_clamped_to_at_least_one(self):
        for keep_newest in (0, -5):
            with self.subTest(keep_newest=keep_newest):
                self.temp.cleanup()
                self.setUp()
                for index in range(1, 4):
                    self.make(f'b{index}.db', size=100, rank=index)

                removed = prune_backups(
                    self.backup_dir, keep_newest=keep_newest, max_total_bytes=self.BIG,
                    protected=[self.backup_dir / 'b3.db'],
                )

                # 夹取到 1 ⇒ C1.1：protected 占满配额，非 protected 全裁
                self.assertEqual(self.names(), ['b3.db'])
                self.assertEqual(self.removed_names(removed), ['b1.db', 'b2.db'])

    def test_ta9_retention_settings_clamps_with_temp_config(self):
        """C6 在 settings 层：不依赖真实 config.yaml，用临时配置构造 max_backups=0/-7。"""
        for raw in ('0', '-7'):
            with self.subTest(max_backups=raw):
                config = self.root / 'config.yaml'
                config.write_text(
                    f'data:\n  max_backups: {raw}\n  max_backup_total_gb: 1\n',
                    encoding='utf-8',
                )
                keep_newest, _cap = retention_settings(config)
                self.assertGreaterEqual(keep_newest, 1)

    # --- T-A5 / C5：目录不存在返回 [] --------------------------------------
    def test_ta5_missing_directory_returns_empty_list(self):
        missing = self.root / 'does-not-exist'
        self.assertEqual(prune_backups(missing, keep_newest=1), [])
        self.assertFalse(missing.exists())

    # --- C5：单个 unlink 失败继续处理其余项 --------------------------------
    def test_c5_unlink_failure_is_skipped_and_processing_continues(self):
        self.make('b3.db', size=100, rank=3)  # 最新的留下来
        self.make('b2.db', size=100, rank=2)  # 删除失败
        self.make('b1.db', size=100, rank=1)  # 正常删除

        real_unlink = Path.unlink

        def flaky_unlink(self, *args, **kwargs):  # noqa: N805 - 复刻 Path.method
            if self.name == 'b2.db':
                raise OSError('device busy')
            return real_unlink(self, *args, **kwargs)

        with mock.patch.object(Path, 'unlink', flaky_unlink):
            removed = prune_backups(self.backup_dir, keep_newest=1, max_total_bytes=self.BIG)

        self.assertEqual(self.removed_names(removed), ['b1.db'])
        self.assertTrue((self.backup_dir / 'b2.db').exists())  # 失败项仍在
        self.assertTrue((self.backup_dir / 'b3.db').exists())


def legacy_prune_backups(backup_dir, keep_newest, max_total_bytes, pattern='*.db', protected=()):
    """复刻**旧实现**（2026-10-04 修正前）：先剔除 protected，再对剩余应用 keep_newest。

    仅用于回归护栏——证明本文件的契约断言真的能抓到旧行为。
    """
    directory = Path(backup_dir)
    if not directory.is_dir():
        return []
    protected_names = {Path(item).name for item in protected}
    candidates = [item for item in directory.glob(pattern)
                  if item.is_file() and item.name not in protected_names]
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    removed = []
    kept_bytes = 0
    for index, path in enumerate(candidates):
        size = path.stat().st_size
        if index < keep_newest and kept_bytes + size <= max_total_bytes:
            kept_bytes += size
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
    return removed


class LegacyRegressionGuardTests(_Fixture):
    """回归护栏：同一 fixture 下旧实现留下 5 份，冻结契约要求 4 份。"""

    def _run(self, prune):
        self.temp.cleanup()
        self.setUp()
        for index in range(1, 6):
            self.make(f'b{index}.db', size=100, rank=index)
        keep_newest, cap = 4, 1024 ** 3
        prune(
            self.backup_dir, keep_newest=keep_newest, max_total_bytes=cap,
            protected=[self.backup_dir / 'b5.db'],
        )
        return len(self.names())

    def test_guard_legacy_leaves_five_while_contract_leaves_four(self):
        legacy_remaining = self._run(legacy_prune_backups)
        contract_remaining = self._run(
            lambda directory, **kwargs: prune_backups(directory, **kwargs)
        )

        # 旧实现：剔除 protected 后仍有 4 个名额，全部陈旧备份都活着 ⇒ 5 份
        self.assertEqual(legacy_remaining, 5)
        # 冻结契约 C1：protected 占用配额 ⇒ 4 份
        self.assertEqual(contract_remaining, 4)
        # 两者必须可区分，否则本文件的断言抓不到旧实现
        self.assertNotEqual(legacy_remaining, contract_remaining)


if __name__ == '__main__':
    unittest.main()
