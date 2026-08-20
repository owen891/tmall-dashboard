import hmac
from urllib.parse import unquote, urlsplit

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from werkzeug.local import LocalProxy
from werkzeug.exceptions import RequestEntityTooLarge
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
from api.alert_rules_api import alert_rules_bp
from api.data_capabilities_api import data_capabilities_bp
from api.page_capabilities_api import page_capabilities_bp
from api.catalog_mutations_api import catalog_mutations_bp
from api.overview_events_api import overview_events_bp
from api.schedules_api import schedules_bp
from api.import_scans_api import import_scans_bp
from api.manage_api import manage_bp
from config import APP_VERSION, Config, _sqlite_url
from desktop_runtime import resource_root
from models import db as orm_db

# 获取项目根目录的绝对路径
project_root = resource_root()
demo_root = os.path.join(project_root, 'frontend', 'ui_demo')


def _database_path_from_uri(uri):
    parsed = urlsplit(str(uri or ''))
    if parsed.scheme != 'sqlite':
        raise ValueError('SQLALCHEMY_DATABASE_URI must use sqlite so raw database access stays consistent')
    path = unquote(parsed.path or '')
    if path in {'', '/:memory:', ':memory:'}:
        raise ValueError('SQLALCHEMY_DATABASE_URI must reference a file-backed sqlite database')
    # urlsplit keeps a leading slash before Windows drive letters.
    if len(path) >= 3 and path[0] == '/' and path[2] == ':':
        path = path[1:]
    elif path.startswith('/') and not path.startswith('//'):
        # sqlite:///relative.db is relative to the process working directory;
        # four slashes are required for an absolute/UNC-style path.
        path = path[1:]
    return os.path.abspath(path)

def create_app(config=None):
    explicit_sqlalchemy_uri = bool(config and 'SQLALCHEMY_DATABASE_URI' in config)
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, 'templates'),
        static_folder=os.path.join(project_root, 'static'),
    )
    app.config.from_object(Config)
    app.config.setdefault('MAX_CONTENT_LENGTH', 25 * 1024 * 1024)
    if config:
        app.config.from_mapping(config)

    if explicit_sqlalchemy_uri:
        app.config['DATABASE_PATH'] = _database_path_from_uri(
            app.config['SQLALCHEMY_DATABASE_URI']
        )
    else:
        app.config['DATABASE_PATH'] = os.path.abspath(
            app.config.get('DATABASE_PATH') or get_db_path()
        )
        app.config['SQLALCHEMY_DATABASE_URI'] = _sqlite_url(app.config['DATABASE_PATH'])
    scan_roots = app.config.get('IMPORT_SCAN_ALLOWED_ROOTS') or []
    if isinstance(scan_roots, str):
        scan_roots = [scan_roots]
    for scan_root in scan_roots:
        os.makedirs(os.path.abspath(scan_root), exist_ok=True)

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
    app.register_blueprint(alert_rules_bp)
    app.register_blueprint(data_capabilities_bp)
    app.register_blueprint(page_capabilities_bp)
    app.register_blueprint(catalog_mutations_bp)
    app.register_blueprint(overview_events_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(import_scans_bp)
    app.register_blueprint(manage_bp)
    init_db(app.config['DATABASE_PATH'])

    @app.before_request
    def require_lan_authentication():
        remote_addr = request.remote_addr or ''
        # A reverse proxy commonly makes every request appear loopback. Treat
        # forwarded client headers as an external request so the local bypass
        # cannot accidentally become a production authentication bypass.
        forwarded_client = request.headers.get('X-Forwarded-For') or request.headers.get('X-Real-IP')
        loopback = remote_addr in {'127.0.0.1', '::1'} or remote_addr.startswith('127.')
        if loopback and not forwarded_client:
            return None
        username = app.config.get('DASHBOARD_USERNAME')
        password = app.config.get('DASHBOARD_PASSWORD')
        if not username or not password:
            return jsonify({
                'ok': False,
                'code': 'AUTH_CONFIGURATION_REQUIRED',
                'message': '局域网访问需要配置 DASHBOARD_USERNAME 和 DASHBOARD_PASSWORD',
            }), 503
        credentials = request.authorization
        if credentials and hmac.compare_digest(credentials.username or '', username) and hmac.compare_digest(credentials.password or '', password):
            return None
        return jsonify({'ok': False, 'code': 'AUTH_REQUIRED', 'message': '需要认证'}), 401, {
            'WWW-Authenticate': 'Basic realm="tmall-dashboard"',
        }

    @app.after_request
    def prevent_dashboard_frontend_staleness(response):
        if request.path == '/' or request.path == '/api/version' or request.path in {
            '/products', '/promotion', '/lifecycle', '/reviews',
            '/data-center', '/settings', '/goals',
        } or request.path.startswith('/assets/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def payload_too_large(_error):
        from api.api_response import failure
        return failure('PAYLOAD_TOO_LARGE', '上传文件超过 25 MB 限制', status=413)

    @app.route('/')
    def index():
        return send_from_directory(os.path.join(demo_root, 'pages'), 'overview.html', max_age=0)

    @app.route('/<page>')
    def application_page(page):
        if page == 'compare':
            return redirect('/reviews')
        if page == 'manage':
            return redirect('/settings')
        if page not in {'products', 'promotion', 'lifecycle', 'reviews', 'data-center', 'settings', 'goals'}:
            return jsonify({'error': 'page not found'}), 404
        return send_from_directory(os.path.join(demo_root, 'pages'), f'{page}.html', max_age=0)

    @app.route('/products/<product_id>')
    def product_detail_page(product_id):
        return send_from_directory(os.path.join(demo_root, 'pages'), 'product-detail.html', max_age=0)

    @app.route('/legacy/')
    def legacy_index():
        return render_template('dashboard.html')

    @app.route('/static/<path:path>')
    def static_files(path):
        return send_from_directory(os.path.join(project_root, 'static'), path)

    @app.route('/demo/')
    def demo_index():
        return send_from_directory(demo_root, 'index.html', max_age=0)

    @app.route('/demo/<path:path>')
    def demo_files(path):
        return send_from_directory(demo_root, path, max_age=0)

    @app.route('/pages/<path:path>')
    def product_pages(path):
        return send_from_directory(os.path.join(demo_root, 'pages'), path, max_age=0)

    # The catalog is also served at `/`, so relative asset URLs resolve here.
    @app.route('/assets/<path:path>')
    def demo_assets(path):
        return send_from_directory(os.path.join(demo_root, 'assets'), path, max_age=0)

    @app.route('/api/demo/manifest')
    def demo_manifest():
        return jsonify({
            'name': 'tmall-dashboard',
            'version': APP_VERSION,
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

    @app.route('/api/version')
    def app_version():
        return jsonify({
            'ok': True,
            'data': {
                'name': 'tmall-dashboard',
                'version': APP_VERSION,
                'channel': 'stable',
            },
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

    if app.config.get('TESTING'):
        @app.route('/api/test/availability/<state>')
        def availability_fixture(state):
            from api.api_response import success
            return success({'state': state}, availability=state)

    return app


_app_instance = None


def get_app():
    """Create the compatibility application only when it is actually used."""
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    return _app_instance


# Preserve ``from app import app`` compatibility without initializing SQLite
# merely because a script imported ``create_app``.
app = LocalProxy(get_app)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('TMALL_PORT', '5000')), debug=False)
