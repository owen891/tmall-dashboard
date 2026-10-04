"""``scripts/backfill_promo_detail_from_bi.py`` 的 --apply / --backup-destination 契约测试（F-03）。

审核发现该脚本的备份契约**零测试**（``git grep promo_detail_from_bi -- tests`` 无匹配）。
本文件只覆盖命令行契约本身，不做字段映射逻辑测试：

* **T-B1**：同一 ``--backup-destination`` 二次 ``--apply`` ⇒ ``SystemExit``；
  备份目标文件未被改写（size + sha256 前后一致）；数据库未被写入（文件 sha256 与行值均不变）。
* **T-B2**：``--apply`` 未给 ``--backup-destination`` ⇒ ``SystemExit``（现有 :137 行为），
  且不产生任何备份产物。

全部 fixture 用 ``tempfile``：自建库（``init_db`` + 一行 daily_data）、自建日度 xlsx、
自建备份目的地。**绝不**指向真实 ``data/dashboard.db`` 或 ``data/backups/``。
"""

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_shop_id, init_db  # noqa: E402
from scripts.backfill_promo_detail_from_bi import main as backfill_main  # noqa: E402

STAT_DATE = '2026-04-19'
PRODUCT_ID = '1001'
PROMO_VALUE = 12.5


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(path):
    path = Path(path)
    return (path.stat().st_size, sha256_of(path))


class BackfillPromoBackupContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-backfill-backup-')
        self.root = Path(self.temp.name)
        self.db_path = self.root / 'dashboard.db'
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        self.backup_dir = self.root / 'backups'
        self.backup_dir.mkdir()
        self.destination = self.backup_dir / 'run-2026-04-19.db'
        self._build_database()
        self._build_source_workbook()

    def tearDown(self):
        self.temp.cleanup()

    # --- fixture ---------------------------------------------------------
    def _build_database(self):
        init_db(str(self.db_path))
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                'INSERT INTO daily_data (shop_id, date, product_id) VALUES (?, ?, ?)',
                (get_shop_id(), STAT_DATE, PRODUCT_ID),
            )
            connection.commit()
        finally:
            connection.close()

    def _build_source_workbook(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = '商品总览'
        headers = ['商品id', '货品全站推花费', '全站推广成交金额', '首单礼金', '品牌新享营销托管软件服务费']
        sheet.append(headers)  # 第 1 行表头
        sheet.append(headers)  # 第 2 行子表头
        sheet.append([PRODUCT_ID, PROMO_VALUE, 20.0, 1.0, 3.0])
        workbook.save(self.sources / f'商品总览-{STAT_DATE}.xlsx')

    def _run(self, *extra):
        """以真实 ``main()`` 执行一次命令行（sys.argv 被替换）。"""
        argv = ['backfill_promo_detail_from_bi.py',
                '--db', str(self.db_path),
                '--sources', str(self.sources),
                *extra]
        with mock.patch.object(sys, 'argv', argv):
            return backfill_main()

    def _promo_value(self):
        connection = sqlite3.connect(self.db_path)
        try:
            row = connection.execute(
                'SELECT product_sitewide_spend FROM daily_data '
                'WHERE shop_id = ? AND date = ? AND product_id = ?',
                (get_shop_id(), STAT_DATE, PRODUCT_ID),
            ).fetchone()
            return row[0] if row else None
        finally:
            connection.close()

    # --- T-B1 ------------------------------------------------------------
    def test_tb1_second_apply_same_destination_exits_without_rewriting(self):
        # 第一次 --apply：正常完成，生成备份并落库
        self.assertEqual(self._run('--apply', '--backup-destination', str(self.destination)), 0)
        self.assertTrue(self.destination.is_file(), '首次 --apply 必须生成备份目标')
        self.assertEqual(self._promo_value(), PROMO_VALUE, '首次 --apply 应把明细写进 daily_data')

        destination_before = fingerprint(self.destination)
        database_before = fingerprint(self.db_path)

        # 第二次 --apply：同一 --backup-destination ⇒ FileExistsError → SystemExit
        with self.assertRaises(SystemExit) as caught:
            self._run('--apply', '--backup-destination', str(self.destination))

        self.assertIn('已存在', str(caught.exception))
        self.assertIn('backup-destination', str(caught.exception))
        # 目标文件未被改写
        self.assertEqual(fingerprint(self.destination), destination_before)
        # 数据库未被写入
        self.assertEqual(fingerprint(self.db_path), database_before)
        self.assertEqual(self._promo_value(), PROMO_VALUE)

    # --- T-B2 ------------------------------------------------------------
    def test_tb2_apply_without_backup_destination_exits(self):
        with self.assertRaises(SystemExit) as caught:
            self._run('--apply')

        self.assertIn('需要同时提供', str(caught.exception))
        self.assertIn('backup-destination', str(caught.exception))
        # 未生成任何备份产物
        self.assertEqual(list(self.backup_dir.iterdir()), [])
        # 未落库：明细列仍为 NULL
        self.assertIsNone(self._promo_value())


if __name__ == '__main__':
    unittest.main()
