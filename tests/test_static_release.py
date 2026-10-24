"""Filesystem-only release transactions. Never imports app or business DB."""
import json
from pathlib import Path
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from utils import static_release as releases


class StaticReleaseTests(unittest.TestCase):
    def setUp(self):
        # 受限环境下 TMPDIR 会回退到仓库根，Windows 上会让目录 rename 撞上
        # 权限/占用问题；显式放到仓库的父目录。
        self.temp = tempfile.TemporaryDirectory(
            dir=str(pathlib.Path(__file__).resolve().parents[1].parent))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.store = self.root / 'store'
        for name, content in {'pages/overview.html': '<head><script src="../assets/a.js?v=old"></script></head>',
                              'assets/a.js': 'A', 'assets/runtime/lazy.js': 'LAZY_A',
                              'assets/theme.css': 'body{}'}.items():
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')

    def test_every_managed_file_change_changes_version_and_preserves_old_bytes(self):
        first = releases.publish_release(self.source, self.store)
        for path in sorted(self.source.rglob('*')):
            if not path.is_file():
                continue
            original = path.read_bytes()
            path.write_bytes(original + b' changed')
            changed = releases.build_release(self.source, self.store)
            self.assertNotEqual(first, changed, path)
            self.assertEqual(releases.read_current(self.store), first)
            self.assertEqual(releases.read_release_file(self.store, first, path.relative_to(self.source).as_posix()), original)
            path.write_bytes(original)
        self.assertEqual(releases.build_release(self.source, self.store), first)

    def test_stage_activate_rollback_and_missing_old_resource_never_use_new_bytes(self):
        first = releases.publish_release(self.source, self.store)
        (self.source / 'assets/runtime/lazy.js').write_text('LAZY_B')
        second = releases.build_release(self.source, self.store)
        self.assertEqual(releases.read_current(self.store), first)
        releases.activate_release(self.store, second)
        self.assertEqual(releases.read_current(self.store), second)
        self.assertEqual(releases.read_release_file(self.store, first, 'assets/runtime/lazy.js'), b'LAZY_A')
        releases.activate_release(self.store, first)
        self.assertEqual(releases.read_current(self.store), first)
        self.assertEqual(releases.read_release_file(self.store, second, 'assets/runtime/lazy.js'), b'LAZY_B')
        (self.store / 'releases' / first / 'assets/runtime/lazy.js').unlink()
        with self.assertRaises(releases.ReleaseUnavailable):
            releases.read_release_file(self.store, first, 'assets/runtime/lazy.js')
        with self.assertRaises(releases.ReleaseUnavailable):
            releases.activate_release(self.store, first)

    def test_source_changes_during_build_cannot_replace_current(self):
        first = releases.publish_release(self.source, self.store)
        reader = releases._source_files
        reads = 0
        def concurrent_edit(source):
            nonlocal reads
            reads += 1
            if reads == 2:
                (self.source / 'assets/a.js').write_text('EDITED_DURING_BUILD')
            return reader(source)
        with patch.object(releases, '_source_files', side_effect=concurrent_edit):
            with self.assertRaisesRegex(releases.ReleaseUnavailable, 'source changed'):
                releases.publish_release(self.source, self.store)
        self.assertEqual(releases.read_current(self.store), first)
        self.assertFalse(list((self.store / 'releases').glob('.building-*')))

    def test_corruption_and_traversal_are_rejected_not_repaired(self):
        version = releases.publish_release(self.source, self.store)
        for name in ('../active.json', '/active.json', 'assets/../../active.json', 'assets\\a.js'):
            with self.subTest(path=name), self.assertRaises(releases.ReleaseUnavailable):
                releases.read_release_file(self.store, version, name)
        (self.store / 'releases' / version / 'assets/a.js').write_text('TAMPERED')
        with self.assertRaises(releases.ReleaseUnavailable):
            releases.read_release_file(self.store, version, 'assets/a.js')
        with self.assertRaises(releases.ReleaseUnavailable):
            releases.build_release(self.source, self.store)
        self.assertEqual((self.store / 'releases' / version / 'assets/a.js').read_text(), 'TAMPERED')

    def test_malformed_active_pointer_does_not_auto_publish_current_sources(self):
        version = releases.publish_release(self.source, self.store)
        for value in ('{broken', '[]', 'null'):
            (self.store / 'active.json').write_text(value)
            with self.subTest(value=value), self.assertRaises(releases.ReleaseUnavailable):
                releases.ensure_initial_release(self.source, self.store)
        self.assertTrue((self.store / 'releases' / version).is_dir())

    def test_reader_sees_old_until_atomic_pointer_replacement(self):
        first = releases.publish_release(self.source, self.store)
        (self.source / 'assets/a.js').write_text('B')
        second = releases.build_release(self.source, self.store)
        replace = releases.os.replace
        observations = []
        def commit(source, target):
            observations.append(releases.read_current(self.store))
            replace(source, target)
            observations.append(releases.read_current(self.store))
        with patch.object(releases.os, 'replace', side_effect=commit):
            releases.activate_release(self.store, second)
        self.assertEqual(observations, [first, second])

    def test_publisher_failure_preserves_active_and_retained_release(self):
        first = releases.publish_release(self.source, self.store)
        (self.source / 'assets/a.js').write_text('B')
        second = releases.build_release(self.source, self.store)
        with patch.object(releases.os, 'replace', side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):
                releases.activate_release(self.store, second)
        self.assertEqual(releases.read_current(self.store), first)
        self.assertEqual(releases.read_release_file(self.store, second, 'assets/a.js'), b'B')
        self.assertFalse((self.store / '.publish.lock').exists())


if __name__ == '__main__':
    unittest.main()
