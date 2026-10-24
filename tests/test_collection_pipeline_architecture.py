"""Isolated regression tests for the 2026-10-23 collection-pipeline fixes.

Every test here is filesystem/SQLite only. The production database
(`data/dashboard.db`, ~22 GB) is never opened: each test builds its own
fixture database in a temporary directory. No network, no child processes,
no scheduled task is triggered, and no live collection is re-run.

Covered defects (see scripts/check_collect_gaps.py and
scripts/aggregate_store_daily.py for the implementation notes):

1. 汇总口径保护 — the aggregation window used to be anchored on the wall
   clock (`date('now')`), so a business date that slid out of the lookback
   window could never be back-filled and `--skip-if-current` then reported
   "already current" while `store_daily_facts` stayed missing.
2. 分区完整性检查 — every source except the market rank table was accepted
   as "collected" on `COUNT(*) >= 1`, so a partial pull (239 of ~912
   promotion rows on 2026-10-22) passed.
3. 补采日期传播 — `catchup_collect.ps1` accepted `-Date` but did not pass it
   down, so the child re-collected its own "yesterday".
4. 完成验收 — a zero process exit code was indistinguishable from a real
   complete collection, and aggregate failures were not propagated.
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import aggregate_store_daily as aggregate  # noqa: E402
from scripts import check_collect_gaps as gaps  # noqa: E402


def _make_fixture_db(path, *, days, per_day):
    """Create the minimal daily_data/store_daily_facts pair used by aggregation."""
    conn = sqlite3.connect(path)
    try:
        conn.execute('''
            CREATE TABLE daily_data (
                shop_id TEXT, date TEXT, product_id TEXT,
                payment_amount REAL, refund_amount REAL,
                ipv INTEGER, buyers INTEGER, returning_payment_buyers INTEGER,
                ad_spend REAL
            )''')
        conn.execute('''
            CREATE TABLE store_daily_facts (
                shop_id TEXT, date TEXT, payment_amount REAL,
                successful_refund_amount REAL, product_visitors INTEGER,
                payment_buyers INTEGER, returning_payment_buyers INTEGER,
                ad_spend REAL, source_batch_id TEXT,
                PRIMARY KEY (shop_id, date)
            )''')
        rows = []
        for day in days:
            for index in range(per_day):
                rows.append(('shop-1', day, f'p{index}', 10.0, 1.0, 20, 2, 1, 5.0))
        conn.executemany(
            'INSERT INTO daily_data VALUES (?,?,?,?,?,?,?,?,?)', rows)
        conn.commit()
    finally:
        conn.close()


class AggregateAnchorTests(unittest.TestCase):
    """Defect 1: the aggregation window must follow the data, not the clock."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aggregate-anchor-')
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / 'fixture.db')

    def _rows(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute(
                'SELECT date, payment_amount FROM store_daily_facts ORDER BY date'
            ).fetchall()
        finally:
            conn.close()

    def test_anchor_is_latest_source_date_not_wall_clock(self):
        # A deliberately old business date: with a wall-clock anchor this is
        # outside any reasonable lookback window and nothing would be written.
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=3)
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(aggregate.resolve_anchor(conn), '2026-09-20')
        finally:
            conn.close()

    def test_explicit_as_of_overrides_the_anchor(self):
        _make_fixture_db(self.db_path, days=['2026-09-20', '2026-09-21'], per_day=2)
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(aggregate.resolve_anchor(conn, '2026-09-20'), '2026-09-20')
        finally:
            conn.close()

    def test_empty_source_has_no_anchor(self):
        _make_fixture_db(self.db_path, days=[], per_day=0)
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertIsNone(aggregate.resolve_anchor(conn))
            # No anchor means no window: the filter must match nothing rather
            # than silently falling back to a wall-clock range.
            self.assertEqual(aggregate._date_filter(14, anchor=None), ('0', []))
        finally:
            conn.close()

    def test_apply_writes_historical_date_that_clock_window_would_miss(self):
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=3)
        backup = str(Path(self.temp.name) / 'backup.db')
        code = aggregate.main(['--db', self.db_path, '--apply',
                               '--lookback-days', '14',
                               '--backup-destination', backup])
        self.assertEqual(code, 0)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], '2026-09-20')
        self.assertAlmostEqual(rows[0][1], 30.0)

    def test_dates_backfill_is_repeatable_and_idempotent(self):
        _make_fixture_db(self.db_path, days=['2026-09-20', '2026-09-21'], per_day=2)
        # A snapshot destination is write-once by design (sqlite_snapshot uses
        # open('xb')), so each run needs its own path.
        first = aggregate.main(['--db', self.db_path, '--apply',
                                '--dates', '2026-09-20',
                                '--backup-destination',
                                str(Path(self.temp.name) / 'backup-1.db')])
        self.assertEqual(first, 0)
        self.assertEqual([row[0] for row in self._rows()], ['2026-09-20'])
        # Second run only targets the remaining day; the first is untouched.
        second = aggregate.main(['--db', self.db_path, '--apply',
                                 '--dates', '2026-09-21',
                                 '--backup-destination',
                                 str(Path(self.temp.name) / 'backup-2.db')])
        self.assertEqual(second, 0)
        self.assertEqual([row[0] for row in self._rows()],
                         ['2026-09-20', '2026-09-21'])

    def test_requested_date_absent_from_source_fails_instead_of_silently_doing_nothing(self):
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=2)
        backup = str(Path(self.temp.name) / 'backup.db')
        # 2026-09-22 was never collected: this must be a hard failure, because
        # "wrote zero rows" is exactly what hid the 2026-10-22 gap.
        code = aggregate.main(['--db', self.db_path, '--apply',
                               '--dates', '2026-09-22',
                               '--backup-destination', backup])
        self.assertEqual(code, 3)
        self.assertEqual(self._rows(), [])
        self.assertFalse(Path(backup).exists(),
                         'a rejected date list must not create a backup')

    def test_missing_date_can_be_allowed_explicitly(self):
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=2)
        backup = str(Path(self.temp.name) / 'backup.db')
        code = aggregate.main(['--db', self.db_path, '--apply',
                               '--dates', '2026-09-22',
                               '--allow-missing-dates',
                               '--backup-destination', backup])
        self.assertEqual(code, 0)
        self.assertEqual(self._rows(), [])

    def test_skip_if_current_detects_missing_partition(self):
        # daily_data has the day but store_daily_facts does not: --skip-if-current
        # must not report "current".
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=2)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            self.assertFalse(aggregate.is_current(conn, 14, anchor='2026-09-20'))
        finally:
            conn.close()

    def test_dates_and_as_of_are_mutually_exclusive(self):
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=1)
        with self.assertRaises(SystemExit):
            aggregate.main(['--db', self.db_path,
                            '--dates', '2026-09-20', '--as-of', '2026-09-20'])

    def test_missing_database_returns_two(self):
        missing = str(Path(self.temp.name) / 'nope.db')
        self.assertEqual(aggregate.main(['--db', missing]), 2)

    def test_preview_does_not_write_to_the_database(self):
        """A --dry-run preview must not checkpoint or otherwise mutate the file.

        Regression: the probe connection used to be opened read-write, so a
        preview run still rewrote the production main file on close (WAL
        checkpoint) even though no rows changed.
        """
        _make_fixture_db(self.db_path, days=['2026-09-20'], per_day=1)
        before = os.stat(self.db_path)
        code = aggregate.main(['--db', self.db_path, '--lookback-days', '30'])
        after = os.stat(self.db_path)
        self.assertEqual(code, 0)
        self.assertEqual(
            (before.st_size, before.st_mtime_ns),
            (after.st_size, after.st_mtime_ns),
            '预览模式改动了数据库文件',
        )


class PartitionAcceptanceTests(unittest.TestCase):
    """Defect 2: a partition needs presence + population + fields."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gap-acceptance-')
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / 'fixture.db')

    # Three baseline days: baseline_median() needs >= 3 samples, otherwise it
    # returns None and the ratio check is skipped entirely (a real hazard the
    # fixture must not hide).
    BASELINE_DAYS = ('2026-10-19', '2026-10-20', '2026-10-21')
    TARGET_DAY = '2026-10-22'

    def _build(self, promotion_rows, other_rows=4, daily_rows=None):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('CREATE TABLE daily_data '
                         '(shop_id TEXT, product_id TEXT, date TEXT, payment_amount REAL)')
            conn.execute('CREATE TABLE sycm_flow_source_daily '
                         '(stat_date TEXT, channel_name TEXT, uv INTEGER, pay_amount REAL)')
            conn.execute('CREATE TABLE sycm_item_flow_source_daily '
                         '(stat_date TEXT, item_id TEXT, channel_name TEXT, uv INTEGER)')
            conn.execute('CREATE TABLE sycm_market_item_rank '
                         '(stat_date TEXT, cate_id TEXT, item_id TEXT, rank INTEGER)')
            conn.execute('CREATE TABLE promotion_daily_facts '
                         '(shop_id TEXT, date TEXT, channel TEXT, ad_spend REAL, clicks INTEGER)')
            conn.execute('CREATE TABLE store_daily_facts '
                         '(shop_id TEXT, date TEXT, payment_amount REAL)')
            for day in self.BASELINE_DAYS:
                conn.executemany(
                    'INSERT INTO daily_data VALUES (?,?,?,?)',
                    [('shop-1', f'p{i}', day, 1.0) for i in range(other_rows)])
                conn.executemany(
                    'INSERT INTO sycm_flow_source_daily VALUES (?,?,?,?)',
                    [(day, f'ch{i}', 1, 1.0) for i in range(other_rows)])
                conn.executemany(
                    'INSERT INTO sycm_item_flow_source_daily VALUES (?,?,?,?)',
                    [(day, f'i{i}', f'ch{i}', 1) for i in range(other_rows)])
                conn.executemany(
                    'INSERT INTO sycm_market_item_rank VALUES (?,?,?,?)',
                    [(day, 'c1', f'i{i}', i) for i in range(1500)])
                conn.executemany(
                    'INSERT INTO promotion_daily_facts VALUES (?,?,?,?,?)',
                    [('shop-1', day, f'c{i}', 1.0, 1) for i in range(900)])
            # The source rows for the target day: without these the derived
            # store_daily_facts gap could never be attributed to aggregation.
            target_rows = other_rows if daily_rows is None else daily_rows
            conn.executemany(
                'INSERT INTO daily_data VALUES (?,?,?,?)',
                [('shop-1', f'p{i}', self.TARGET_DAY, 1.0) for i in range(target_rows)])
            conn.executemany(
                'INSERT INTO promotion_daily_facts VALUES (?,?,?,?,?)',
                [('shop-1', self.TARGET_DAY, f'c{i}', 1.0, 1)
                 for i in range(promotion_rows)])
            conn.commit()
        finally:
            conn.close()

    def _inspect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return gaps.inspect_dates(conn, [self.TARGET_DAY])
        finally:
            conn.close()

    def test_partial_promotion_pull_is_rejected(self):
        # 239 of ~900 rows is the real 2026-10-22 shape; COUNT>=1 accepted it.
        self._build(promotion_rows=239)
        result = self._inspect()
        promotion = result['tables']['promotion_daily_facts']
        self.assertEqual(promotion['status'], 'partial')
        self.assertIn('below_baseline_ratio', promotion['reasons'])
        self.assertIn('wanxiangtai', result['missing_sources'])

    def test_complete_promotion_pull_is_accepted(self):
        self._build(promotion_rows=900)
        result = self._inspect()
        self.assertEqual(result['tables']['promotion_daily_facts']['status'], 'verified')
        self.assertNotIn('wanxiangtai', result['missing_sources'])

    def test_null_required_field_rejects_partition(self):
        # A row exists but the metric was never collected: 2026-10-20/21 really
        # had SQL NULL payment_amount on some rows.
        self._build(promotion_rows=900)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE daily_data SET payment_amount=NULL "
                         "WHERE rowid=(SELECT MIN(rowid) FROM daily_data "
                         f"WHERE date='{self.TARGET_DAY}')")
            conn.commit()
        finally:
            conn.close()
        result = self._inspect()
        daily = result['tables']['daily_data']
        self.assertEqual(daily['status'], 'partial')
        self.assertIn('required_fields_incomplete', daily['reasons'])

    def test_zero_is_accepted_as_a_real_metric(self):
        # Zero sales are legitimate and must not be mistaken for "not collected".
        self._build(promotion_rows=900)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE daily_data SET payment_amount=0 WHERE date='2026-10-22'")
            conn.commit()
        finally:
            conn.close()
        result = self._inspect()
        self.assertEqual(result['tables']['daily_data']['status'], 'verified')

    def test_empty_derived_partition_requires_aggregation(self):
        self._build(promotion_rows=900)
        result = self._inspect()
        self.assertEqual(result['tables']['store_daily_facts']['status'], 'empty')
        self.assertTrue(result['aggregate_needed'])
        self.assertEqual(result['aggregate_dates'], ['2026-10-22'])

    def test_missing_table_is_treated_as_a_gap_not_a_crash(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('CREATE TABLE daily_data (shop_id TEXT, product_id TEXT, '
                         'date TEXT, payment_amount REAL)')
            conn.execute("INSERT INTO daily_data VALUES ('s','p','2026-10-22',1.0)")
            conn.commit()
        finally:
            conn.close()
        result = self._inspect()
        # A table that does not exist is "unknown", not "empty": we cannot tell
        # an uncollected day from a schema that was never created. Either way it
        # must be reported as a gap rather than raising.
        promotion = result['tables']['promotion_daily_facts']
        self.assertIn(promotion['status'], ('unknown', 'empty'))
        self.assertIn('wanxiangtai', result['missing_sources'])

    def test_gap_inspection_is_read_only(self):
        self._build(promotion_rows=239)
        before = Path(self.db_path).read_bytes()
        self._inspect()
        self.assertEqual(Path(self.db_path).read_bytes(), before)

    def test_readonly_connection_cannot_write(self):
        # The CLI opens mode=ro + PRAGMA query_only; assert that posture holds.
        self._build(promotion_rows=239)
        uri = 'file:' + Path(self.db_path).as_posix() + '?mode=ro'
        conn = sqlite3.connect(uri, uri=True)
        try:
            conn.execute('PRAGMA query_only=ON')
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM promotion_daily_facts")
        finally:
            conn.close()

    def test_required_fields_cannot_drift_from_the_collector_catalog(self):
        # The inspector must agree with the API's authoritative field list;
        # otherwise a source can pass one gate and fail the other.
        from api import collect_api
        specs = {entry[2]: entry for entry in gaps.TABLE_SPECS}
        for source_key, spec in specs.items():
            catalog = collect_api.COLLECTOR_CATALOG.get(source_key)
            self.assertIsNotNone(catalog, f'{source_key} missing from COLLECTOR_CATALOG')
            self.assertEqual(
                tuple(spec[3]), tuple(catalog['fields']),
                f'{source_key} required_fields drifted from COLLECTOR_CATALOG')


@unittest.skipUnless(os.name == 'nt' and (
    Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32' /
    'WindowsPowerShell' / 'v1.0' / 'powershell.exe').exists(), 'Windows PowerShell')
class LauncherDatePropagationTests(unittest.TestCase):
    """Defect 3: the target date must reach the collectors, not be re-derived."""

    def _script(self, name):
        return PROJECT_ROOT / 'scripts' / name

    def test_catchup_passes_target_date_to_collector(self):
        text = self._script('catchup_collect.ps1').read_text(encoding='utf-8-sig')
        self.assertIn("-Start $Date -End $Date", text,
                      'catchup must pass the requested date down to the collector')

    def test_catchup_propagates_aggregate_failure(self):
        text = self._script('catchup_collect.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('$aggExit', text)
        self.assertIn('if ($aggExit -ne 0) { exit $aggExit }', text)

    def test_catchup_verifies_the_target_partition_afterwards(self):
        text = self._script('catchup_collect.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('$remaining', text)
        self.assertIn('$afterAggregateNeeded', text)

    def test_daily_all_passes_target_date_and_reads_structured_result(self):
        text = self._script('daily_collect_all.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('-Start $Date -End $Date -ResultFile $childResult', text)
        self.assertIn('ConvertFrom-Json', text)
        # The fragile log-scraping fallback must be gone.
        self.assertNotIn('成功:\\s*\\d+,\\s*失败:\\s*\\d+', text)

    def test_aggregate_task_accepts_and_forwards_dates(self):
        text = self._script('aggregate_store_daily_task.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('[string[]]$Dates', text)
        self.assertIn("'--dates'", text)

    def test_aggregate_task_joins_multiple_dates_into_one_argument(self):
        """`--dates` is a single-value flag, not append/nargs.

        `@('--dates') + $targets` sends the 2nd..nth dates as stray positionals,
        so argparse dies with "unrecognized arguments" and any multi-date
        backfill fails while a single-date run looks fine. The dates must be
        joined into one comma-separated value.
        """
        text = self._script('aggregate_store_daily_task.ps1').read_text(encoding='utf-8-sig')
        self.assertNotIn("$dateArgs = @('--dates') + $targets", text)
        self.assertIn("($targets -join ',')", text)

    def test_run_daily_collect_dispatches_month_argument_as_year_month(self):
        text = self._script('run_daily_collect.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('DateStyle', text)
        self.assertIn("Substring(0, 7)", text,
                      'aggregate_monthly needs YYYY-MM, not YYYY-MM-DD')
        self.assertIn("'--start'", text,
                      'collect_wanxiangtai_dims_v4.py parses flags, not positionals')
        # `exit $failCount` wraps to 0 past 255, turning mass failure into success.
        # Match statement lines only: the string also appears in an explanatory
        # comment describing what the fix replaced.
        statements = [line.strip() for line in text.splitlines()
                      if line.strip().startswith('exit ')]
        self.assertNotIn('exit $failCount', statements)

    def test_collect_result_contract_is_used_by_both_primary_chains(self):
        for name in ('run_daily_collect.ps1', 'auto-collect.ps1'):
            text = self._script(name).read_text(encoding='utf-8-sig')
            self.assertIn('collect_result.ps1', text)
            self.assertIn('Set-CollectRunOutcome', text)


@unittest.skipUnless(os.name == 'nt', 'PowerShell encoding is a Windows-only failure mode')
class PowerShellEncodingTests(unittest.TestCase):
    """Defect 4: a non-ASCII script without a BOM fails to parse under 5.1."""

    BOM = b'\xef\xbb\xbf'

    def test_every_non_ascii_script_has_a_bom(self):
        offenders = []
        for path in sorted((PROJECT_ROOT / 'scripts').glob('*.ps1')):
            raw = path.read_bytes()
            if raw.startswith(self.BOM):
                continue
            if all(byte < 0x80 for byte in raw):
                continue  # pure ASCII parses correctly either way
            offenders.append(path.name)
        self.assertEqual(offenders, [],
                         'Windows PowerShell 5.1 decodes these as ANSI and exits 0 '
                         'after a parse error, silently collecting nothing')


class UnifiedRuntimeResolutionTests(unittest.TestCase):
    """Defect 5: one collection chain must not run on two different interpreters.

    Before the fix, five entry points hard-coded `.venv\\Scripts\\python.exe`
    while the rest went through `scripts/resolve_runtime.ps1` (which reads
    `data/runtime.json`). The two interpreters have different site-packages
    and different process identities, so their availability can diverge.

    Measured on 2026-10-23: the venv interpreter was denied writes to F:
    (`PermissionError: [Errno 13]`) while the runtime interpreter, system
    Python, cmd.exe and PowerShell all wrote the same directory fine. Because
    `aggregate_store_daily_task.ps1` used the venv interpreter, the nightly
    aggregation failed from 2026-10-22 16:11 onward and `store_daily_facts`
    silently stopped updating.

    These assertions are static on purpose: they are cheap, need no process
    spawn, and pin the invariant that matters — every chain entry point
    resolves its interpreter through the single resolver.
    """

    # Every scheduled-task entry point that runs Python.
    CHAIN_SCRIPTS = (
        'run_daily_collect.ps1',
        'aggregate_store_daily_task.ps1',
        'run_daily_backup.ps1',
        'run_collector_observability.ps1',
        'backfill-tasks.ps1',
        'auto-collect.ps1',
        'catchup_collect.ps1',
        'daily_collect_all.ps1',
    )

    def _script(self, name):
        return PROJECT_ROOT / 'scripts' / name

    def test_no_chain_script_hardcodes_the_venv_interpreter(self):
        offenders = {}
        for name in self.CHAIN_SCRIPTS:
            text = self._script(name).read_text(encoding='utf-8-sig')
            # Only executable lines count: the fix notes deliberately mention
            # the old hard-coded path to explain what was wrong.
            code_lines = [line for line in text.splitlines()
                          if '.venv' in line and not line.strip().startswith('#')]
            if code_lines:
                offenders[name] = [line.strip() for line in code_lines]
        self.assertEqual(offenders, {},
                         'these scripts resolve their own interpreter instead of '
                         'going through resolve_runtime.ps1, so the chain can end up '
                         'running on two different Pythons')

    def test_every_chain_script_uses_the_shared_resolver(self):
        missing = []
        for name in self.CHAIN_SCRIPTS:
            text = self._script(name).read_text(encoding='utf-8-sig')
            if 'Resolve-CollectorPython' not in text:
                missing.append(name)
        self.assertEqual(missing, [],
                         'every chain entry point must call Resolve-CollectorPython '
                         'so TMALL_COLLECT_PYTHON and data/runtime.json are honoured')

    def test_resolver_is_dot_sourced_before_first_use(self):
        # Dot-sourcing must precede the Resolve-CollectorPython call, otherwise
        # the function is undefined and the script dies at parse/runtime.
        for name in self.CHAIN_SCRIPTS:
            text = self._script(name).read_text(encoding='utf-8-sig')
            source_at = text.find('resolve_runtime.ps1')
            use_at = text.find('Resolve-CollectorPython')
            self.assertNotEqual(source_at, -1, f'{name} never dot-sources the resolver')
            self.assertNotEqual(use_at, -1, f'{name} never calls the resolver')
            self.assertLess(source_at, use_at,
                            f'{name} calls Resolve-CollectorPython before dot-sourcing it')

    def test_runtime_failure_maps_to_the_shared_config_error_code(self):
        # 20 == RUNTIME_CONFIG_INVALID, the code auto-collect.ps1 already uses.
        # Without it a broken runtime.json surfaces as an empty path or a raw
        # Python traceback, which is exactly the kind of silent failure this
        # task exists to remove.
        for name in self.CHAIN_SCRIPTS:
            text = self._script(name).read_text(encoding='utf-8-sig')
            self.assertIn('exit 20', text,
                          f'{name} must exit 20 (RUNTIME_CONFIG_INVALID) when the '
                          'runtime cannot be resolved')

    def test_resolver_reads_the_runtime_record_and_keeps_the_env_override(self):
        text = self._script('resolve_runtime.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('TMALL_COLLECT_PYTHON', text,
                      'the explicit override must win over the runtime record')
        self.assertIn('data/runtime.json', text,
                      'the runtime record is the single source of truth for the interpreter')
        # The venv path may only appear as the last-resort fallback, once.
        self.assertEqual(text.count('.venv'), 1,
                         'the venv path belongs in exactly one place: the resolver fallback')


class BackupDestinationResilienceTests(unittest.TestCase):
    """An unwritable backup volume must not silently stop the daily aggregation.

    Measured 2026-10-23: F: denied Python writes intermittently
    (`PermissionError: [Errno 13]`) while cmd.exe / PowerShell / system Python
    wrote the same directory fine, and the block could flip *mid-write* — a
    0-byte destination was created at 16:49:33 and then the process sat at zero
    CPU for 12 minutes. Because the aggregate had no preflight and no fallback,
    `store_daily_facts` stopped updating from 2026-10-22 onward.

    The invariant pinned here: the aggregation entry point must (a) probe the
    destination with the *same interpreter* that will perform the backup, and
    (b) fall back to a writable in-project directory instead of failing without
    a backup. A .NET/PowerShell probe would be a false positive — that is
    exactly why the probe has to shell out to `$PythonPath`.
    """

    def test_aggregate_probes_destination_with_the_backup_interpreter(self):
        text = (PROJECT_ROOT / 'scripts' / 'aggregate_store_daily_task.ps1').read_text(
            encoding='utf-8-sig')
        self.assertIn('Test-BackupDestinationWritable', text)
        # The probe must invoke the resolved interpreter, not .NET file APIs.
        probe_body = text[text.index('function Test-BackupDestinationWritable'):
                          text.index('$EffectiveBackupDir')]
        self.assertIn('& $Python', probe_body,
                      'the probe must use the interpreter that will run the backup')
        self.assertNotIn('[System.IO.File]', probe_body,
                         '.NET write permission differs from Python and yields a false positive')

    def test_aggregate_falls_back_instead_of_failing_without_a_backup(self):
        text = (PROJECT_ROOT / 'scripts' / 'aggregate_store_daily_task.ps1').read_text(
            encoding='utf-8-sig')
        self.assertIn('$EffectiveBackupDir', text)
        self.assertIn('data\\backups', text,
                      'the fallback destination must be inside the project')
        # Refusing to write without a backup is the correct failure mode when
        # even the fallback is unwritable.
        self.assertIn('exit 24', text,
                      '24 = BACKUP_DESTINATION_UNWRITABLE must be a distinct code')
        self.assertIn('不做无备份', text,
                      'the refusal must be explicit in the log, not silent')

    def test_aggregate_backup_path_uses_the_effective_directory(self):
        text = (PROJECT_ROOT / 'scripts' / 'aggregate_store_daily_task.ps1').read_text(
            encoding='utf-8-sig')
        # The actual backup file must be built from the resolved directory,
        # otherwise the fallback would be computed and then ignored.
        self.assertIn('Join-Path $EffectiveBackupDir', text,
                      'the backup file must be created under the effective directory')


class CollectResultContractTests(unittest.TestCase):
    """The run-result contract must record outcomes without throwing.

    Measured 2026-10-23 on a real catch-up run (`logs/collect-20261023-170220.log`):
    the collector exited 2, and the log showed

        ✗ 万相台推广 采集失败，退出码: 2
        ✗ 万相台推广 采集异常: 不能对值为 Null 的表达式调用方法。

    Two symptoms, one cause. `Add-CollectSourceResult` declared
    `[Nullable[datetime]]$StartedAt`, but PowerShell unwraps `Nullable<T]` during
    parameter binding, so the parameter arrives as a plain `[datetime]` and
    `$StartedAt.Value` is always `$null`. Every call that passed `-StartedAt`
    therefore threw — including the *success* path in `run_daily_collect.ps1`.
    The throw landed in the collector's `catch`, which incremented the failure
    counter a second time (`失败: 2` for a single failed source) and rewrote a
    successful source as `reason='exception'`. Net effect: a catch-up could never
    report success, and the failure count was inflated.

    Invariants pinned here:
      1. the contract must not reach for `.Value` on a `Nullable` parameter;
      2. recording a result must be isolated from the "did the collector work"
         try/catch, so a reporting bug can never masquerade as a collection bug;
      3. the emitted file must use one schema (`collect_run` + contract rows),
         not legacy counters mixed with contract fields.
    """

    CONTRACT = PROJECT_ROOT / 'scripts' / 'collect_result.ps1'
    RUNNER = PROJECT_ROOT / 'scripts' / 'run_daily_collect.ps1'

    def test_contract_does_not_dereference_nullable_value(self):
        text = self.CONTRACT.read_text(encoding='utf-8-sig')
        # Comment lines are allowed to quote the bug being described; only
        # executable statements matter here.
        offenders = [line.strip() for line in text.splitlines()
                     if not line.strip().startswith('#')
                     and ('StartedAt.Value' in line or 'DurationSeconds.Value' in line)]
        self.assertEqual(offenders, [],
                         'PowerShell unwraps Nullable<T> in parameter binding, so '
                         '.Value is always $null and calling a method on it throws')

    def test_started_at_is_recorded_through_a_plain_datetime(self):
        text = self.CONTRACT.read_text(encoding='utf-8-sig')
        self.assertIn("([datetime]$StartedAt).ToString('o')", text)

    def test_contract_round_trip_does_not_throw(self):
        """Execute the real function: a passing text check is not proof."""
        script = (
            "$ErrorActionPreference = 'Stop'\n"
            f". '{self.CONTRACT}'\n"
            "$r = New-CollectRunResult -RunId 't' -Sources @('wanxiangtai') "
            "-Start '2026-10-22' -End '2026-10-22'\n"
            "$startedAt = Get-Date\n"
            "Add-CollectSourceResult -Result $r -Source 'wanxiangtai' -Outcome 'succeeded' "
            "-ExitCode 0 -StartedAt $startedAt -DurationSeconds 1.5\n"
            "Add-CollectSourceResult -Result $r -Source 'sycm_flow' -Outcome 'skipped' "
            "-Reason 'not_requested'\n"
            "Set-CollectRunOutcome -Result $r\n"
            "Write-Output ($r['results'].Count)\n"
            "Write-Output $r['outcome']\n"
            "Write-Output $r['results'][0]['started_at']\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'probe.ps1'
            path.write_text(script, encoding='utf-8-sig')
            completed = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(path)],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=120)
        self.assertEqual(completed.returncode, 0,
                         f'contract probe failed: {completed.stderr or completed.stdout}')
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(lines[0], '2', 'both results must be recorded')
        self.assertEqual(lines[1], 'succeeded')
        self.assertNotIn('0001-01-01', lines[2],
                         'a null StartedAt would serialize as the default DateTime')

    def test_recording_is_isolated_from_the_collection_catch(self):
        text = self.RUNNER.read_text(encoding='utf-8-sig')
        body = text[text.index('$sourceSucceeded = '):text.index('Write-Log "=== 采集完成 ==="')]
        self.assertIn('结果记录失败（不影响采集结论）', body,
                      'a reporting failure must degrade to WARN, not re-enter the '
                      'collection catch and double-count the failure')
        # The recording call must sit in its own try block, after the outcome is decided.
        self.assertGreater(body.index('结果记录失败'), body.index('$sourceSucceeded'),
                           'outcome must be decided before the recording is attempted')

    def test_result_file_uses_one_schema(self):
        text = self.RUNNER.read_text(encoding='utf-8-sig')
        self.assertIn("event = 'collect_run'", text)
        self.assertNotIn("event = 'batch_result'", text,
                         'mixing legacy counters with contract rows lets the two '
                         'counts drift apart in the same file')
        self.assertIn("results = @($runResult['results'])", text)
        self.assertIn("failed = $runResult['failed']", text)


if __name__ == '__main__':
    unittest.main()
