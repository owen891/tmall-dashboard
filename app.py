from flask import Flask, jsonify, redirect, render_template, send_from_directory
import os
from db import get_db, get_db_path, init_db
from api.data_api import data_bp
from api.imports_api import imports_bp
from api.overview_api import overview_bp
from api.goals_api import goals_bp
from api.actions_api import actions_bp
from api.settings_api import settings_bp
from api.lifecycle_api import lifecycle_bp
from api.promotion_api import promotion_bp
from api.period_reviews_api import period_reviews_bp
from api.product_detail_api import product_detail_bp
from api.status_api import status_bp
from api.tool_api import tool_bp
from config import Config
from models import db as orm_db

# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.abspath(__file__))
demo_root = os.path.join(project_root, 'frontend', 'ui_demo')

def create_app(config=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, 'templates'),
        static_folder=os.path.join(project_root, 'static'),
    )
    app.config.from_object(Config)
    if config:
        app.config.from_mapping(config)

    app.config['DATABASE_PATH'] = os.path.abspath(
        app.config.get('DATABASE_PATH') or get_db_path()
    )

    orm_db.init_app(app)
    app.register_blueprint(status_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(actions_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(lifecycle_bp)
    app.register_blueprint(promotion_bp)
    app.register_blueprint(period_reviews_bp)
    app.register_blueprint(product_detail_bp)
    app.register_blueprint(tool_bp)
    init_db(app.config['DATABASE_PATH'])

    @app.route('/')
    def index():
        return send_from_directory(os.path.join(demo_root, 'pages'), 'overview.html')

    @app.route('/<page>')
    def application_page(page):
        if page == 'compare':
            return redirect('/reviews')
        if page == 'manage':
            return redirect('/settings')
        if page not in {'products', 'promotion', 'lifecycle', 'reviews', 'data-center', 'settings', 'goals'}:
            return jsonify({'error': 'page not found'}), 404
        return send_from_directory(os.path.join(demo_root, 'pages'), f'{page}.html')

    @app.route('/products/<product_id>')
    def product_detail_page(product_id):
        return send_from_directory(os.path.join(demo_root, 'pages'), 'product-detail.html')

    @app.route('/legacy/')
    def legacy_index():
        return render_template('dashboard.html')

    @app.route('/static/<path:path>')
    def static_files(path):
        return send_from_directory(os.path.join(project_root, 'static'), path)

    @app.route('/demo/')
    def demo_index():
        return send_from_directory(demo_root, 'index.html')

    @app.route('/demo/<path:path>')
    def demo_files(path):
        return send_from_directory(demo_root, path)

    @app.route('/pages/<path:path>')
    def product_pages(path):
        return send_from_directory(os.path.join(demo_root, 'pages'), path)

    # The catalog is also served at `/`, so relative asset URLs resolve here.
    @app.route('/assets/<path:path>')
    def demo_assets(path):
        return send_from_directory(os.path.join(demo_root, 'assets'), path)

    @app.route('/api/demo/manifest')
    def demo_manifest():
        return jsonify({
            'name': 'tmall-dashboard',
            'version': '0.1.0',
            'data_mode': 'api',
            'pages': [
                {'id': 'overview', 'path': '/', 'data': 'api', 'endpoint': '/api/overview'},
                {'id': 'products', 'path': '/products', 'data': 'api', 'endpoint': '/api/products'},
                {'id': 'promotion', 'path': '/promotion', 'data': 'api', 'endpoint': '/api/ad_trend'},
                {'id': 'lifecycle', 'path': '/lifecycle', 'data': 'api', 'endpoint': '/api/lifecycle'},
                {'id': 'reviews', 'path': '/reviews', 'data': 'api', 'endpoint': '/api/actions/pending-review'},
                {'id': 'data-center', 'path': '/data-center', 'data': 'api', 'endpoint': '/api/imports/preview'},
                {'id': 'settings', 'path': '/settings', 'data': 'api', 'endpoint': '/api/settings'},
            ],
        })

    @app.route('/healthz')
    def health_check():
        try:
            with get_db() as connection:
                connection.execute('SELECT 1').fetchone()
        except Exception:
            return jsonify({
                'ok': False,
                'data': {'service': 'tmall-dashboard', 'database': 'unavailable'},
            }), 503
        return jsonify({
            'ok': True,
            'data': {'service': 'tmall-dashboard', 'database': 'ok'},
        })

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('TMALL_PORT', '5000')), debug=False)
