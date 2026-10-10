import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts.db_maintenance import build_report, main


class DatabaseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-maintenance-")
        self.database = Path(self.temp_dir.name) / "dashboard.db"
        conn = sqlite3.connect(self.database)
        conn.executescript(
            """
            CREATE TABLE daily_data_observations (
              id INTEGER PRIMARY KEY, shop_id TEXT, product_id TEXT, date TEXT,
              observed_at TEXT
            );
            CREATE INDEX idx_obs ON daily_data_observations(shop_id, product_id, date, observed_at DESC, id DESC);
            CREATE TABLE daily_data (shop_id TEXT, product_id TEXT, date TEXT);
            CREATE INDEX idx_daily ON daily_data(shop_id, date);
            CREATE TABLE collector_data_staging (published_at TEXT, status TEXT);
            INSERT INTO collector_data_staging VALUES ('2020-01-01', 'published');
            CREATE TABLE monthly_source_payload (month TEXT);
            INSERT INTO monthly_source_payload VALUES ('2020-01');
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_is_read_only_and_has_candidates(self):
        before = self.database.read_bytes()
        report = build_report(self.database, {"collector_data_staging": 1})
        self.assertEqual(report["integrity_check"], "ok")
        self.assertEqual(report["tables"]["collector_data_staging"]["eligible_count"], 1)
        self.assertFalse(report["policy"]["mutations_performed"])
        self.assertEqual(self.database.read_bytes(), before)

    def test_cli_writes_json(self):
        output = Path(self.temp_dir.name) / "report.json"
        self.assertEqual(main(["--database", str(self.database), "--output", str(output)]), 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["manifest_version"], 1)


class CutoffConsistencyTests(unittest.TestCase):
    """预览器与执行器必须对「超期」给出一致结论。

    2026-10-08 缺陷：``db_maintenance._cutoff``（只读预览）与
    ``enforce_retention._date_cutoff``（执行器）**各自独立实现**，且都返回纯日期
    ``YYYY-MM-DD``。而 eligible 判定是 SQL 字符串比较 ``"<col>" < ?``，带时分秒
    的真实数据 ``'2026-09-24 01:30:28'`` 与 ``'2026-09-24'`` 比较时被判为不小于
    ⇒ 截止日当天全部行被漏报。

    两个工具因此对同一张表给出相反结论：生产库实测预览器 0、执行器 8316，
    运维会据此误判「无待清理数据」。

    既有夹具用纯日期落库，**碰不到**这个边界；本组测试刻意写入带时分秒的
    时间戳，并直接断言两个工具的数字相等——把「口径一致」本身钉成契约，
    这样任何一方再退回纯日期都会被抓住。
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-cutoff-consistency-")
        self.database = Path(self.temp_dir.name) / "dashboard.db"
        conn = sqlite3.connect(self.database)
        conn.executescript(
            """
            CREATE TABLE retention_policies (
              policy_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
              source_table TEXT NOT NULL, retention_days INTEGER NOT NULL,
              mode TEXT NOT NULL DEFAULT 'archive',
              protected INTEGER NOT NULL DEFAULT 0, updated_at TEXT
            );
            CREATE TABLE collector_data_staging (
              id INTEGER PRIMARY KEY, payload_json TEXT, status TEXT,
              created_at TEXT, published_at TEXT
            );
            """
        )
        # 关键：带时分秒的时间戳，且落在「截止日当天但时钟更早」的窗口内
        cutoff_probe = datetime.now() - timedelta(days=14)
        same_day_earlier = cutoff_probe.replace(
            hour=0, minute=30, second=28, microsecond=0
        ).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO collector_data_staging "
            "(payload_json, status, created_at, published_at) VALUES (?,?,?,?)",
            ('{"a":1}', "published", same_day_earlier, same_day_earlier),
        )
        conn.execute(
            "INSERT INTO retention_policies "
            "(policy_key, source_kind, source_table, retention_days, mode, protected) "
            "VALUES ('staging','runtime','collector_data_staging',14,"
            "'purge_after_archive',0)",
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preview_and_enforcer_agree_on_same_day_boundary_rows(self):
        from scripts.db_maintenance import build_report
        from scripts.enforce_retention import enforce

        preview = build_report(self.database)["tables"]["collector_data_staging"]
        enforcement = next(
            p for p in enforce(self.database, apply_changes=False)["policies"]
            if p["source_table"] == "collector_data_staging"
        )

        # 该行必须被两个工具同时判为超期——纯日期 cutoff 下预览器会漏报成 0
        self.assertEqual(
            preview["eligible_count"], 1,
            "preview must count same-day-but-earlier rows as eligible",
        )
        self.assertEqual(
            enforcement["eligible_count"], 1,
            "enforcer must count same-day-but-earlier rows as eligible",
        )
        self.assertEqual(
            preview["eligible_count"], enforcement["eligible_count"],
            "preview and enforcer must agree on the eligible count",
        )

    def test_cutoff_format_matches_column_storage_format(self):
        """cutoff 格式必须匹配列的存储格式，两个方向都不能错。

        - 时间戳列 + 纯日期 cutoff ⇒ 截止日当天漏报（永不清理）
        - 纯日期列 + 时间戳 cutoff ⇒ 边界当天被**提前**判为超期

        ``bi_product_daily_raw.date`` 是纯日期列，必须得到纯日期 cutoff；
        ``collector_data_staging.published_at`` 是时间戳列，必须得到带时分秒的。
        """
        from scripts.db_maintenance import _cutoff, _column_has_time
        from scripts.enforce_retention import _cutoff_for

        conn = sqlite3.connect(self.database)
        try:
            conn.execute("CREATE TABLE bi_product_daily_raw (date TEXT)")
            conn.execute("INSERT INTO bi_product_daily_raw VALUES ('2025-01-01')")
            conn.commit()

            # 纯日期列：两个工具都必须给纯日期 cutoff（长度 10）
            self.assertFalse(_column_has_time(conn, "bi_product_daily_raw", "date"))
            self.assertEqual(len(_cutoff("date", 180, has_time=False)), 10)
            self.assertEqual(len(_cutoff_for(conn, "bi_product_daily_raw", "date", 180)), 10)

            # 时间戳列：必须给带时分秒的 cutoff（长度 19）
            self.assertTrue(_column_has_time(conn, "collector_data_staging", "published_at"))
            self.assertEqual(len(_cutoff("published_at", 14, has_time=True)), 19)
            self.assertEqual(
                len(_cutoff_for(conn, "collector_data_staging", "published_at", 14)), 19
            )
        finally:
            conn.close()

    def test_pure_date_boundary_row_is_not_archived_early(self):
        """纯日期列的边界当天行不得被判为超期（时间戳 cutoff 会造成此错）。"""
        from scripts.db_maintenance import _cutoff
        from scripts.enforce_retention import _pure_date_cutoff

        cutoff = _pure_date_cutoff(180)          # 例如 '2026-04-11'
        conn = sqlite3.connect(self.database)
        try:
            conn.execute("CREATE TABLE bi_product_daily_raw (date TEXT)")
            # 恰在边界当天：纯日期语义下应**保留**
            conn.execute("INSERT INTO bi_product_daily_raw VALUES (?)", (cutoff,))
            conn.commit()
            eligible = conn.execute(
                'SELECT COUNT(*) FROM bi_product_daily_raw WHERE date < ?', (cutoff,)
            ).fetchone()[0]
            self.assertEqual(eligible, 0, "boundary-day row must be kept")

            # 反证：若误用带时分秒的 cutoff，同一行会被提前归档
            timestamp_cutoff = f"{cutoff} 12:00:00"
            premature = conn.execute(
                'SELECT COUNT(*) FROM bi_product_daily_raw WHERE date < ?',
                (timestamp_cutoff,),
            ).fetchone()[0]
            self.assertEqual(
                premature, 1,
                "timestamp cutoff on a pure-date column wrongly archives the boundary day",
            )
        finally:
            conn.close()
            # 清理：避免影响同一 tempdir 内其他用例
            conn = sqlite3.connect(self.database)
            conn.execute("DROP TABLE IF EXISTS bi_product_daily_raw")
            conn.commit()
            conn.close()


    def test_preview_applies_the_same_row_filter_as_enforcer(self):
        """预览器必须套用与执行器**逐字一致**的行过滤。

        ``enforce_retention.TABLE_SPECS`` 对 ``collector_data_staging`` 带
        ``status = 'published'`` 过滤，而 ``db_maintenance`` 曾无此过滤 ⇒
        未发布的超期行会被预览器算进 ``eligible_count``，数字大于执行器真正
        会删的行数。当前库里该表全是 published，差异被掩盖；本用例插入一条
        **非 published 的超期行**把差异逼出来。
        """
        from scripts.db_maintenance import build_report
        from scripts.enforce_retention import enforce

        old_ts = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.database)
        try:
            conn.execute(
                "INSERT INTO collector_data_staging "
                "(payload_json, status, created_at, published_at) VALUES (?,?,?,?)",
                ('{"staged":1}', "staged", old_ts, old_ts),
            )
            conn.commit()
        finally:
            conn.close()

        preview = build_report(self.database)["tables"]["collector_data_staging"]
        enforcement = next(
            p for p in enforce(self.database, apply_changes=False)["policies"]
            if p["source_table"] == "collector_data_staging"
        )

        # 未发布的超期行不该被任何一方计入
        self.assertEqual(
            enforcement["eligible_count"], 1,
            "enforcer counts only published rows",
        )
        self.assertEqual(
            preview["eligible_count"], enforcement["eligible_count"],
            "preview must not over-report by ignoring the published filter",
        )


    def test_preview_flags_policies_the_executor_cannot_enforce(self):
        """声明了但无执行器的策略必须被标注，而不是伪装成「已管理」。

        ``collector_checkpoints`` 的 mode 是 ``compact``，而 ``enforce_retention``
        未实现该模式（dry-run 报 ``unsupported_mode:compact``）。若预览器只报
        ``eligible_count``，读者会误以为「0 行超期 = 已被妥善管理」。
        """
        from scripts.db_maintenance import build_report

        conn = sqlite3.connect(self.database)
        try:
            conn.execute("CREATE TABLE collector_checkpoints (updated_at TEXT)")
            conn.execute(
                "INSERT INTO retention_policies "
                "(policy_key, source_kind, source_table, retention_days, mode, protected) "
                "VALUES ('cp','runtime','collector_checkpoints',30,'compact',0)"
            )
            conn.commit()
        finally:
            conn.close()

        report = build_report(self.database)
        cp = report["tables"]["collector_checkpoints"]
        self.assertEqual(cp["mode"], "compact")
        self.assertFalse(
            cp["enforceable"],
            "compact has no executor and must be flagged unenforceable",
        )
        # 有执行器的策略保持 True
        self.assertTrue(
            report["tables"]["collector_data_staging"]["enforceable"],
            "purge_after_archive is implemented and must stay enforceable",
        )


    def test_format_detection_is_order_independent_for_mixed_columns(self):
        """混合格式列的探测必须与行序无关。

        早先实现用 ``LIMIT 1`` 单行取样：若先扫到纯日期行就误判为纯日期列，
        结果**依赖扫描顺序**、不确定。改为 ``MAX(LENGTH(...))`` 后，只要列中
        出现过时间戳就判为时间戳列，与行序无关。
        """
        from scripts.db_maintenance import _column_has_time as maint_detect
        from scripts.enforce_retention import _column_has_time as enforce_detect

        conn = sqlite3.connect(self.database)
        try:
            conn.execute("CREATE TABLE mixed_fmt (ts TEXT)")
            # 纯日期在前——旧实现会误判为 False
            conn.execute("INSERT INTO mixed_fmt VALUES ('2026-01-01')")
            conn.execute("INSERT INTO mixed_fmt VALUES ('2026-01-01 10:00:00')")
            conn.commit()
            for detect in (maint_detect, enforce_detect):
                self.assertTrue(
                    detect(conn, "mixed_fmt", "ts"),
                    "mixed column with any timestamp must be detected as timestamp",
                )

            # 纯日期列仍须判为 False（不能反向误判）
            conn.execute("CREATE TABLE pure_fmt (d TEXT)")
            conn.execute("INSERT INTO pure_fmt VALUES ('2025-01-01')")
            conn.execute("INSERT INTO pure_fmt VALUES ('2025-06-30')")
            conn.commit()
            for detect in (maint_detect, enforce_detect):
                self.assertFalse(detect(conn, "pure_fmt", "d"))

            # 空表不得抛异常
            conn.execute("CREATE TABLE empty_fmt (x TEXT)")
            conn.commit()
            for detect in (maint_detect, enforce_detect):
                self.assertFalse(detect(conn, "empty_fmt", "x"))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
