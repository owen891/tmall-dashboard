import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class DesktopRuntimeTests(unittest.TestCase):
    def test_desktop_paths_use_user_profile_and_never_bundle_directory(self):
        from desktop_runtime import desktop_data_paths

        with tempfile.TemporaryDirectory() as appdata, tempfile.TemporaryDirectory() as local:
            paths = desktop_data_paths({'APPDATA': appdata, 'LOCALAPPDATA': local})

        self.assertEqual(
            paths.database,
            os.path.join(appdata, 'TmallDashboard', 'data', 'dashboard.db'),
        )
        self.assertEqual(
            paths.uploads,
            os.path.join(appdata, 'TmallDashboard', 'data', 'uploads'),
        )
        self.assertEqual(
            paths.import_inbox,
            os.path.join(appdata, 'TmallDashboard', 'data', 'import-inbox'),
        )
        self.assertEqual(paths.logs, os.path.join(local, 'TmallDashboard', 'logs'))
        self.assertFalse(os.path.abspath(paths.database).startswith(PROJECT_ROOT))

    def test_ensure_desktop_directories_creates_only_parent_directories(self):
        from desktop_runtime import DesktopPaths, ensure_desktop_directories

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = DesktopPaths(
                database=os.path.join(temp_dir, 'data', 'dashboard.db'),
                uploads=os.path.join(temp_dir, 'data', 'uploads'),
                import_inbox=os.path.join(temp_dir, 'data', 'import-inbox'),
                logs=os.path.join(temp_dir, 'logs'),
            )
            ensure_desktop_directories(paths)

            self.assertTrue(os.path.isdir(os.path.dirname(paths.database)))
            self.assertTrue(os.path.isdir(paths.uploads))
            self.assertTrue(os.path.isdir(paths.import_inbox))
            self.assertTrue(os.path.isdir(paths.logs))
            self.assertFalse(os.path.exists(paths.database))

    def test_desktop_environment_points_flask_and_sqlalchemy_to_same_database(self):
        from desktop_runtime import DesktopPaths, desktop_environment

        paths = DesktopPaths('C:/data/dashboard.db', 'C:/data/uploads', 'C:/data/import-inbox', 'C:/logs')
        # The default contract must not depend on unrelated host environment variables.
        with patch.dict(os.environ, {'IMPORT_SCAN_ALLOWED_ROOTS': ''}):
            environment = desktop_environment(paths)

        self.assertEqual(environment['TMALL_DB_PATH'], 'C:/data/dashboard.db')
        self.assertEqual(environment['DATABASE_URL'], 'sqlite:///C:/data/dashboard.db')
        self.assertEqual(environment['TMALL_UPLOAD_FOLDER'], 'C:/data/uploads')
        self.assertEqual(environment['IMPORT_SCAN_ALLOWED_ROOTS'], 'C:/data/import-inbox')
        self.assertEqual(environment['TMALL_DESKTOP_MODE'], '1')

    def test_desktop_environment_formats_windows_backslash_database_url(self):
        from desktop_runtime import DesktopPaths, desktop_environment

        paths = DesktopPaths(r'C:\data\dashboard.db', r'C:\data\uploads', r'C:\data\import-inbox', r'C:\logs')
        environment = desktop_environment(paths)

        self.assertEqual(environment['DATABASE_URL'], 'sqlite:///C:/data/dashboard.db')

    def test_desktop_environment_keeps_operator_scan_roots(self):
        from desktop_runtime import DesktopPaths, desktop_environment

        paths = DesktopPaths('C:/data/dashboard.db', 'C:/data/uploads', 'C:/data/import-inbox', 'C:/logs')
        environment = desktop_environment(paths, {
            'IMPORT_SCAN_ALLOWED_ROOTS': 'D:/data/source;E:/bi/source',
        })

        self.assertEqual(
            environment['IMPORT_SCAN_ALLOWED_ROOTS'],
            'C:/data/import-inbox;D:/data/source;E:/bi/source',
        )

    def test_resource_root_defaults_to_source_root(self):
        from desktop_runtime import resource_root

        self.assertEqual(resource_root(), PROJECT_ROOT)

    def test_config_supports_upload_folder_override_without_changing_web_default(self):
        original = os.environ.get('TMALL_UPLOAD_FOLDER')
        try:
            os.environ.pop('TMALL_UPLOAD_FOLDER', None)
            import config
            importlib.reload(config)
            self.assertEqual(
                config.Config.UPLOAD_FOLDER,
                os.path.join(PROJECT_ROOT, 'data', 'uploads'),
            )

            os.environ['TMALL_UPLOAD_FOLDER'] = 'D:/tmall/uploads'
            importlib.reload(config)
            self.assertEqual(config.Config.UPLOAD_FOLDER, 'D:/tmall/uploads')
        finally:
            if original is None:
                os.environ.pop('TMALL_UPLOAD_FOLDER', None)
            else:
                os.environ['TMALL_UPLOAD_FOLDER'] = original
            import config
            importlib.reload(config)

    def test_missing_version_fails_fast_in_desktop_mode(self):
        from config import _read_app_version

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {'TMALL_DESKTOP_MODE': '1'}, clear=False):
            with self.assertRaisesRegex(RuntimeError, 'VERSION'):
                _read_app_version(os.path.join(temp_dir, 'VERSION'))

    def test_config_defaults_scan_allowlist_to_project_inbox_only(self):
        original = os.environ.get('IMPORT_SCAN_ALLOWED_ROOTS')
        try:
            os.environ.pop('IMPORT_SCAN_ALLOWED_ROOTS', None)
            import config
            importlib.reload(config)
            self.assertEqual(
                config.Config.IMPORT_SCAN_ALLOWED_ROOTS,
                [os.path.join(PROJECT_ROOT, 'data', 'import-inbox')],
            )
        finally:
            if original is None:
                os.environ.pop('IMPORT_SCAN_ALLOWED_ROOTS', None)
            else:
                os.environ['IMPORT_SCAN_ALLOWED_ROOTS'] = original
            import config
            importlib.reload(config)

    def test_app_factory_database_override_keeps_sqlalchemy_on_same_file(self):
        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'desktop.db')
            app = create_app({
                'TESTING': True,
                'DATABASE_PATH': database_path,
                'IMPORT_SCAN_ALLOWED_ROOTS': [],
            })

        self.assertEqual(app.config['DATABASE_PATH'], database_path)
        self.assertEqual(
            app.config['SQLALCHEMY_DATABASE_URI'],
            'sqlite:///' + database_path.replace('\\', '/'),
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
