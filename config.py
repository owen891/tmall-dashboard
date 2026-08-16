import os


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_VERSION = '1.0.0'


class Config:
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    DASHBOARD_USERNAME = os.environ.get('DASHBOARD_USERNAME')
    DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'uploads')
    IMPORT_SCAN_ALLOWED_ROOTS = [
        item for item in os.environ.get(
            'IMPORT_SCAN_ALLOWED_ROOTS',
            os.pathsep.join([
                os.path.join(PROJECT_ROOT, 'data', 'import-inbox'),
                r'D:\桌面\0805\数据源',
                r'E:\bi\bi\取数源',
            ]),
        ).split(os.pathsep) if item.strip()
    ]
