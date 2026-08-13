import os


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


class Config:
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'uploads')
