import os
import sys
from pathlib import Path


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _read_app_version(version_path=None):
    override = os.environ.get('TMALL_APP_VERSION')
    if override:
        return override.strip()
    version_path = Path(version_path) if version_path else Path(
        getattr(sys, '_MEIPASS', PROJECT_ROOT),
    ) / 'VERSION'
    try:
        value = version_path.read_text(encoding='utf-8').strip()
    except OSError as error:
        if os.environ.get('TMALL_DESKTOP_MODE') == '1' or os.environ.get('TMALL_RELEASE_BUILD') == '1':
            raise RuntimeError(f'Application VERSION file is unavailable: {version_path}') from error
        value = ''
    if not value and (os.environ.get('TMALL_DESKTOP_MODE') == '1' or os.environ.get('TMALL_RELEASE_BUILD') == '1'):
        raise RuntimeError(f'Application VERSION file is empty: {version_path}')
    return value or '0.0.0'


APP_VERSION = _read_app_version()
DEFAULT_DATABASE_PATH = os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')
DEFAULT_UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'uploads')


def _sqlite_url(path):
    return 'sqlite:///' + os.fspath(path).replace('\\', '/')


class Config:
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    DASHBOARD_USERNAME = os.environ.get('DASHBOARD_USERNAME')
    DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        _sqlite_url(os.environ.get('TMALL_DB_PATH', DEFAULT_DATABASE_PATH)),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('TMALL_UPLOAD_FOLDER', DEFAULT_UPLOAD_FOLDER)
    IMPORT_SCAN_ALLOWED_ROOTS = [
        item for item in os.environ.get(
            'IMPORT_SCAN_ALLOWED_ROOTS',
            os.path.join(PROJECT_ROOT, 'data', 'import-inbox'),
        ).split(os.pathsep) if item.strip()
    ]
