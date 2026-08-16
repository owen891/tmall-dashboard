import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app


if __name__ == '__main__':
    database_path = os.environ.get('TMALL_DB_PATH') or os.path.abspath('data/dashboard.db')
    app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.abspath(database_path)})
    app.run(host='127.0.0.1', port=int(os.environ.get('TMALL_PORT', '8770')), debug=False)
