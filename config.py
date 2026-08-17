import os


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = '1.0.0'
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
