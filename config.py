import os
import sys
from pathlib import Path

import yaml


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
DEFAULT_IMPORT_SCAN_INBOX = os.path.join(PROJECT_ROOT, 'data', 'import-inbox')


def _split_scan_roots(value):
    raw = str(value or '').strip()
    if not raw:
        return []
    separator = ';' if ';' in raw else os.pathsep
    return [item.strip() for item in raw.split(separator) if item.strip()]


def _legacy_watch_folder(config_path=None):
    path = Path(config_path or Path(PROJECT_ROOT) / 'config.yaml')
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError):
        return ''
    return str((data.get('data') or {}).get('watch_folder') or '').strip()


def normalize_import_scan_roots(values=None):
    if isinstance(values, str):
        values = _split_scan_roots(values)
    values = values or []
    roots = [DEFAULT_IMPORT_SCAN_INBOX, *values]
    normalized = []
    seen = set()
    for value in roots:
        expanded = os.path.expanduser(str(value).strip())
        if not expanded:
            continue
        path = os.path.abspath(expanded)
        key = os.path.normcase(os.path.realpath(path))
        if key not in seen:
            seen.add(key)
            normalized.append(path)
    return normalized


def resolve_import_scan_allowed_roots(environment=None, config_path=None):
    environment = os.environ if environment is None else environment
    configured = str(environment.get('IMPORT_SCAN_ALLOWED_ROOTS') or '').strip()
    values = _split_scan_roots(configured) if configured else _split_scan_roots(
        _legacy_watch_folder(config_path),
    )
    return normalize_import_scan_roots(values)


def _sqlite_url(path):
    return 'sqlite:///' + os.fspath(path).replace('\\', '/')
def _shop_authorization_map(environment=None):
    environment = os.environ if environment is None else environment
    raw = str(environment.get('TMALL_SHOP_AUTHORIZATION') or '').strip()
    if not raw:
        return {}
    try:
        value = yaml.safe_load(raw) or {}
    except yaml.YAMLError as error:
        raise ValueError('TMALL_SHOP_AUTHORIZATION must be valid YAML/JSON') from error
    if not isinstance(value, dict):
        raise ValueError('TMALL_SHOP_AUTHORIZATION must map usernames to shop ids')
    return {
        str(user): ({str(shop) for shop in shops} if isinstance(shops, (list, tuple, set)) else {str(shops)})
        for user, shops in value.items()
    }


def _user_allowlist(environment, name):
    raw = str(environment.get(name) or '').strip()
    return {item.strip() for item in raw.replace(';', ',').split(',') if item.strip()}


def _shop_allowlist(environment=None):
    environment = os.environ if environment is None else environment
    raw = str(environment.get('TMALL_SHOP_ALLOWLIST') or '').strip()
    return {item.strip() for item in raw.replace(';', ',').split(',') if item.strip()}


class Config:
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    DASHBOARD_USERNAME = os.environ.get('DASHBOARD_USERNAME')
    DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        _sqlite_url(os.environ.get('TMALL_DB_PATH', DEFAULT_DATABASE_PATH)),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Keep the raw SQLite connection and Flask-SQLAlchemy on one database.
    # An explicit TMALL_DB_PATH still takes precedence for tests and desktop runs.
    DATABASE_PATH = os.environ.get('TMALL_DB_PATH', DEFAULT_DATABASE_PATH)
    UPLOAD_FOLDER = os.environ.get('TMALL_UPLOAD_FOLDER', DEFAULT_UPLOAD_FOLDER)
    IMPORT_SCAN_ALLOWED_ROOTS = resolve_import_scan_allowed_roots()
    SHOP_AUTHORIZATION = _shop_authorization_map()
    SHOP_ALLOWLIST = _shop_allowlist()
    IMPORT_SCAN_VIEW_USERS = _user_allowlist(os.environ, 'IMPORT_SCAN_VIEW_USERS')
    IMPORT_SCAN_MANAGE_USERS = _user_allowlist(os.environ, 'IMPORT_SCAN_MANAGE_USERS')
