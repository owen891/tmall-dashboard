"""Import/explicit cleanup entry contracts; only tiny temporary SQLite files."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from scripts import backup_retention, cleanup_backups, import_data
from scripts.backup_database import backup_database as verified_backup
from scripts.sqlite_snapshot import sidecar_path, verify_manifest

# The 商品总览 workbook importers are private-deployment scripts; the public
# checkout ships without them, so the entrypoints exercise only the legacy
# importer there instead of failing collection.
try:
    from scripts import import_snapshot_bi_daily as daily, import_snapshot_bi_overview as monthly
    SNAPSHOT_ENTRYPOINTS_AVAILABLE = True
except ImportError:
    daily = monthly = None
    SNAPSHOT_ENTRYPOINTS_AVAILABLE = False


class ImportBackupRetentionContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='import-retention-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.db'
        self.dest = self.root / 'data' / 'backups'
        self.dest.mkdir(parents=True)
        self.make_source(self.source)

    def make_source(self, path):
        connection = sqlite3.connect(path)
        try:
            connection.execute('CREATE TABLE facts(id INTEGER PRIMARY KEY, value TEXT)')
            connection.execute("INSERT INTO facts VALUES(1, 'fixture')")
            connection.commit()
        finally:
            connection.close()

    def seed(self, count=3, source=None, prefix='verified'):
        result = []
        for index in range(count):
            target = self.dest / f'{prefix}-{index}.db'
            verified_backup(source or self.source, target, prune=False)
            os.utime(target, (1000000 + index, 1000000 + index))
            result.append(target)
        return result

    def verified(self, source=None):
        paths = []
        for sidecar in self.dest.glob('*.db.manifest.json'):
            data = json.loads(sidecar.read_text(encoding='utf-8'))
            path = Path(data['destination'])
            if not path.exists() or Path(data['source']).resolve() != (source or self.source).resolve():
                continue
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), data['destination_sha256'])
            verify_manifest(path, data['manifest'])
            paths.append(path)
        return paths

    @contextlib.contextmanager
    def entry(self, kind):
        patches = [
            mock.patch.object(import_data, 'PROJECT_ROOT', str(self.root)),
            mock.patch.object(import_data, 'get_db_path', return_value=str(self.source)),
            mock.patch.object(backup_retention, 'retention_settings', return_value=(3, 20 * 1024 ** 3)),
        ]
        if SNAPSHOT_ENTRYPOINTS_AVAILABLE:
            patches.append(mock.patch.object(daily, 'ROOT', self.root))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            yield lambda: daily.backup_database(self.source) if kind == 'daily' else (
                monthly.backup_database(self.source, self.dest) if kind == 'monthly' else import_data.backup_database())

    def entrypoint_kinds(self):
        """Entrypoints to exercise: snapshot importers only ship in a private
        deployment, so the public checkout covers the legacy importer alone."""
        return ('daily', 'monthly', 'legacy') if SNAPSHOT_ENTRYPOINTS_AVAILABLE else ('legacy',)

    def cleanup(self, apply=True, cap=20 * 1024 ** 3):
        # ROOT/BACKUPS_DIR are existing public module constants, including old baseline.
        with mock.patch.object(cleanup_backups, 'ROOT', self.root), mock.patch.object(cleanup_backups, 'BACKUPS_DIR', self.dest), \
                mock.patch.object(cleanup_backups, 'get_db_path', return_value=str(self.source), create=True), \
                mock.patch.object(cleanup_backups, 'retention_settings', return_value=(3, cap), create=True), \
                mock.patch('sys.argv', ['cleanup_backups.py'] + (['--apply'] if apply else [])):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cleanup_backups.main()
            self.assertEqual(result, 0)
            return output.getvalue()

    def test_three_entrypoints_create_verified_generation_and_keep_three(self):
        for kind in self.entrypoint_kinds():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.root) as isolated:
                old_root, old_dest = self.root, self.dest
                self.root = Path(isolated); self.dest = self.root / 'data' / 'backups'; self.dest.mkdir(parents=True)
                try:
                    self.seed()
                    before = set(self.dest.glob('*.db'))
                    with self.entry(kind) as call:
                        result = call()
                    self.assertIsInstance(result, bool if kind == 'legacy' else Path)
                    if kind == 'legacy': self.assertTrue(result)
                    new = set(self.dest.glob('*.db')) - before
                    self.assertEqual(len(new), 1)
                    self.assertTrue(sidecar_path(next(iter(new))).exists())
                    self.assertEqual(len(self.verified()), 3)
                finally:
                    self.root, self.dest = old_root, old_dest

    def test_wal_uncheckpointed_rows_survive_each_entry(self):
        connection = sqlite3.connect(self.source)
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('PRAGMA wal_autocheckpoint=0')
            connection.execute("INSERT INTO facts VALUES(2, 'wal')"); connection.commit()
            self.assertGreater(Path(str(self.source) + '-wal').stat().st_size, 0)
            for kind in self.entrypoint_kinds():
                with self.subTest(kind=kind), self.entry(kind) as call:
                    before = set(self.dest.glob('*.db')); call()
                    target = next(iter(set(self.dest.glob('*.db')) - before))
                    restored = sqlite3.connect(target)
                    try: self.assertEqual(restored.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 2)
                    finally: restored.close()
        finally:
            connection.close()

    def test_same_target_collision_never_overwrites(self):
        for kind in self.entrypoint_kinds():
            with self.subTest(kind=kind), self.entry(kind) as call:
                module = daily if kind == 'daily' else monthly if kind == 'monthly' else import_data
                with mock.patch.object(module, 'datetime', wraps=module.datetime) as clock:
                    clock.now.return_value = __import__('datetime').datetime(2026, 10, 18, 1, 2, 3)
                    call(); before = {p.name: p.read_bytes() for p in self.dest.iterdir() if p.is_file()}
                    with self.assertRaises(FileExistsError): call()
                    self.assertEqual(before, {p.name: p.read_bytes() for p in self.dest.iterdir() if p.is_file()})

    def test_snapshot_or_manifest_failure_never_prunes(self):
        self.seed()
        for failure in ('create_snapshot', 'write_verified_sidecar'):
            for kind in self.entrypoint_kinds():
                with self.subTest(failure=failure, kind=kind), self.entry(kind) as call, \
                        mock.patch('scripts.sqlite_snapshot.' + failure, side_effect=RuntimeError('injected verification failure')), \
                        mock.patch.object(backup_retention, 'prune_verified_backups') as prune:
                    before = {p.name: p.read_bytes() for p in self.seed_paths()}
                    with self.assertRaisesRegex(RuntimeError, 'verification failure'): call()
                    prune.assert_not_called()
                    self.assertEqual(before, {p.name: p.read_bytes() for p in self.seed_paths()})
                # Remove ONLY a newly failed local test artifact so another failure injection may use the same second.
                for p in self.dest.glob('dashboard*'):
                    p.unlink()

    def seed_paths(self):
        return sorted(self.dest.glob('verified*'))

    def test_cleanup_three_generation_minimum_and_unknown_protection(self):
        original = self.seed()
        unknown = self.dest / 'unknown.db'; unknown.write_bytes(b'not managed')
        bak = self.root / 'data' / 'dashboard.db.bak_unknown'; bak.write_bytes(b'protected unknown')
        output = self.cleanup()
        self.assertEqual(len(self.verified()), 3)
        self.assertTrue(all(p.exists() for p in original))
        self.assertEqual(unknown.read_bytes(), b'not managed')
        self.assertEqual(bak.read_bytes(), b'protected unknown')
        self.assertIn('未验证', output)

    def test_cleanup_only_selected_source_and_capacity_warning(self):
        selected = self.seed(4)
        other = self.root / 'other.db'; self.make_source(other)
        foreign = self.seed(3, other, 'foreign')
        # The selected source itself may live inside the cleanup directory.
        source_bytes = self.source.read_bytes()
        with self.assertLogs('scripts.backup_retention', level='WARNING'):
            output = self.cleanup(cap=1)
        self.assertEqual(len(self.verified()), 3)
        self.assertEqual(len(self.verified(other)), 3)
        self.assertFalse(selected[0].exists()); self.assertTrue(all(p.exists() for p in foreign))
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertIn('BACKUP_CAPACITY_CONFLICT', output)

    def test_cleanup_dryrun_and_source_inside_directory(self):
        self.source = self.dest / 'source.db'; self.make_source(self.source)
        self.seed(4)
        before = {p.name: p.read_bytes() for p in self.dest.iterdir()}
        self.cleanup(apply=False)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.dest.iterdir()})
        self.cleanup()
        self.assertEqual(self.source.read_bytes(), before['source.db'])
        self.assertEqual(len(self.verified()), 3)

    def test_cleanup_rejects_forged_and_changed_content_as_generations(self):
        originals = self.seed()
        for index in range(3):
            path = self.dest / f'forged-{index}.db'
            path.write_bytes(b'not sqlite')
            data = json.loads(sidecar_path(originals[0]).read_text(encoding='utf-8'))
            data['destination'] = str(path.resolve())
            data['destination_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            sidecar_path(path).write_text(json.dumps(data), encoding='utf-8')
        changed = self.dest / 'changed.db'
        verified_backup(self.source, changed, prune=False)
        connection = sqlite3.connect(changed)
        try:
            connection.execute("UPDATE facts SET value='tampered'"); connection.commit()
        finally:
            connection.close()
        data = json.loads(sidecar_path(changed).read_text(encoding='utf-8'))
        data['destination_sha256'] = hashlib.sha256(changed.read_bytes()).hexdigest()
        sidecar_path(changed).write_text(json.dumps(data), encoding='utf-8')
        before = {p.name: p.read_bytes() for p in self.dest.iterdir()}
        with self.assertLogs('scripts.backup_retention', level='WARNING'):
            output = self.cleanup()
        self.assertIn('UNVERIFIED_BACKUP_RETAINED', output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.dest.iterdir()})

    @unittest.skipUnless(SNAPSHOT_ENTRYPOINTS_AVAILABLE,
                         '商品总览 importers are private-deployment scripts')
    def test_daily_monthly_main_backup_failure_does_not_start_import(self):
        folder = self.root / 'inputs'; folder.mkdir()
        (folder / '商品总览_2026-10-18.xlsx').write_bytes(b'not read before backup')
        before = self.source.read_bytes()
        for module in (daily, monthly):
            with self.subTest(module=module.__name__), mock.patch.object(module, 'init_db'), \
                    mock.patch.object(module, 'get_db_path', return_value=str(self.source)), \
                    mock.patch.object(module, 'backup_database', side_effect=RuntimeError('backup unavailable')), \
                    mock.patch.object(module, 'import_file') as import_file, \
                    mock.patch('sys.argv', ['import.py', '--source', str(folder), '--db', str(self.source)]):
                with self.assertRaisesRegex(RuntimeError, 'backup unavailable'): module.main()
                import_file.assert_not_called()
                self.assertEqual(self.source.read_bytes(), before)

    def test_entrypoint_capacity_warning_and_foreign_unknown_protection(self):
        originals = self.seed()
        other = self.root / 'other.db'; self.make_source(other)
        foreign = self.seed(3, other, 'foreign')
        unknown = self.dest / 'unknown.db'; unknown.write_bytes(b'unknown')
        for kind in self.entrypoint_kinds():
            with self.subTest(kind=kind), self.entry(kind) as call, \
                    mock.patch.object(backup_retention, 'retention_settings', return_value=(2, 1)), \
                    contextlib.redirect_stderr(io.StringIO()) as output:
                call()
                self.assertIn('BACKUP_CAPACITY_CONFLICT', output.getvalue())
                self.assertEqual(len(self.verified()), 3)
                self.assertTrue(all(p.exists() for p in foreign))
                self.assertEqual(unknown.read_bytes(), b'unknown')

    def test_cli_backup_failure_precedes_any_import_work(self):
        for name in ('import_single_file', '_legacy_import_excel_file'):
            with self.subTest(entry=name), mock.patch.object(import_data, 'init_db'), \
                    mock.patch.object(import_data, 'backup_database', side_effect=RuntimeError('backup unavailable')), \
                    mock.patch.object(import_data, 'get_connection') as connection, \
                    mock.patch.object(import_data, 'read_workbook_sheets', return_value=[]) as read, \
                    mock.patch.object(import_data, '_open_excel_for_metadata', return_value=None), \
                    mock.patch.object(import_data, 'log_import'), mock.patch.object(import_data, 'recalc_action_effects'):
                with self.assertRaisesRegex(RuntimeError, 'backup unavailable'):
                    getattr(import_data, name)('fixture.xlsx')
                connection.assert_not_called(); read.assert_not_called()

    def test_cli_success_return_and_once_before_connection(self):
        for name in ('import_single_file', '_legacy_import_excel_file'):
            events = []
            connection = mock.MagicMock()
            with self.subTest(entry=name), mock.patch.object(import_data, 'init_db'), \
                    mock.patch.object(import_data, 'backup_database', side_effect=lambda: events.append('backup') or True) as backup, \
                    mock.patch.object(import_data, 'get_connection', side_effect=lambda: events.append('connection') or connection), \
                    mock.patch.object(import_data, 'read_workbook_sheets', return_value=[]), \
                    mock.patch.object(import_data, '_open_excel_for_metadata', return_value=None), \
                    mock.patch.object(import_data, 'log_import'), mock.patch.object(import_data, 'recalc_action_effects'):
                result = getattr(import_data, name)('fixture.xlsx')
                self.assertEqual(events, ['backup', 'connection']); backup.assert_called_once()
                connection.commit.assert_called_once(); connection.close.assert_called_once()
                if name == 'import_single_file': self.assertIsNone(result)
                else: self.assertEqual(result, {'success': True, 'total_rows': 0, 'details': []})


if __name__ == '__main__':
    unittest.main()
