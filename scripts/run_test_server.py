import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app


if __name__ == '__main__':
    database_path = os.environ.get('TMALL_DB_PATH') or os.path.abspath('data/dashboard.db')
    config = {'TESTING': True, 'DATABASE_PATH': os.path.abspath(database_path)}
    # TESTING 默认锁到隔离的 default 店铺范围；TMALL_SHOP_ID 可显式指向真实采集店铺，
    # 让 smoke/audit 跑在真实数据上（当前部署为 3828498662）。
    shop_id = os.environ.get('TMALL_SHOP_ID')
    if shop_id:
        config['SHOP_ID'] = shop_id
    app = create_app(config)
    app.run(host='127.0.0.1', port=int(os.environ.get('TMALL_PORT', '8770')), debug=False)
