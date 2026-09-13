import gzip
import hmac
from urllib.parse import unquote, urlsplit

from flask import Flask, g, jsonify, redirect, request, send_from_directory
from werkzeug.local import LocalProxy
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
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
from api.api_response import JsonObjectError
from config import APP_VERSION, Config, DEFAULT_IMPORT_SCAN_INBOX, _sqlite_url, normalize_import_scan_roots
from desktop_runtime import resource_root
from services.shop_scope_service import authorize_request_shop, current_request_shop_id
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
    # An environment DATABASE_URL must be treated exactly like an explicit
    # factory URI; otherwise the later DATABASE_PATH normalization silently
    # replaces it with the default SQLite file.
    explicit_sqlalchemy_uri = bool(
        (config and 'SQLALCHEMY_DATABASE_URI' in config)
        or os.environ.get('DATABASE_URL')
    )
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config.setdefault('MAX_CONTENT_LENGTH', 25 * 1024 * 1024)
    if config:
        app.config.from_mapping(config)

    if explicit_sqlalchemy_uri:
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        if not (config and 'SQLALCHEMY_DATABASE_URI' in config):
            uri = os.environ.get('DATABASE_URL', uri)
        app.config['SQLALCHEMY_DATABASE_URI'] = uri
        app.config['DATABASE_PATH'] = _database_path_from_uri(uri)
    else:
        configured_path = (config or {}).get('DATABASE_PATH') or os.environ.get('TMALL_DB_PATH') or app.config.get('DATABASE_PATH') or get_db_path()
        app.config['DATABASE_PATH'] = os.path.abspath(configured_path)
        app.config['SQLALCHEMY_DATABASE_URI'] = _sqlite_url(app.config['DATABASE_PATH'])
    scan_roots = normalize_import_scan_roots(app.config.get('IMPORT_SCAN_ALLOWED_ROOTS'))
    app.config['IMPORT_SCAN_ALLOWED_ROOTS'] = scan_roots
    own_inbox = os.path.normcase(os.path.realpath(os.path.abspath(DEFAULT_IMPORT_SCAN_INBOX)))
    for scan_root in scan_roots:
        normalized_root = os.path.abspath(scan_root)
        if os.path.normcase(os.path.realpath(normalized_root)) == own_inbox:
            os.makedirs(normalized_root, exist_ok=True)
        elif not os.path.isdir(normalized_root):
            app.logger.warning('Configured external import scan root is unavailable: %s', normalized_root)

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
    def reject_malformed_json():
        if (request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
                and request.mimetype == 'application/json'
                and request.get_data(cache=True)):
            from werkzeug.exceptions import BadRequest
            try:
                request.get_json(silent=False)
            except BadRequest:
                from api.api_response import failure
                return failure('VALIDATION_ERROR', '请求体不是合法 JSON', status=422)

    @app.before_request
    def bind_and_authorize_shop_scope():
        denied = authorize_request_shop()
        if denied is not None:
            return denied
        g.shop_id = current_request_shop_id()

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
        accepts_gzip = False
        for encoding in (request.headers.get('Accept-Encoding') or '').split(','):
            parts = [part.strip() for part in encoding.lower().split(';')]
            if not parts or parts[0] != 'gzip':
                continue
            quality = next((part[2:].strip() for part in parts[1:] if part.startswith('q=')), None)
            try:
                accepts_gzip = quality is None or float(quality) > 0
            except ValueError:
                accepts_gzip = False
            break
        compressible = response.status_code == 200 and response.content_type.startswith('application/json')
        if accepts_gzip and compressible and response.content_length and response.content_length >= 1024 and not response.headers.get('Content-Encoding'):
            response.set_data(gzip.compress(response.get_data(), mtime=0))
            response.headers['Content-Encoding'] = 'gzip'
            response.headers.add('Vary', 'Accept-Encoding')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def payload_too_large(_error):
        from api.api_response import failure
        return failure('PAYLOAD_TOO_LARGE', '上传文件超过 25 MB 限制', status=413)

    @app.errorhandler(HTTPException)
    def api_http_error(error):
        if not request.path.startswith('/api/'):
            return error
        code = {
            404: 'NOT_FOUND',
            405: 'METHOD_NOT_ALLOWED',
        }.get(error.code, 'HTTP_ERROR')
        message = {
            404: '接口不存在',
            405: '请求方法不被支持',
        }.get(error.code, '请求无法处理')
        from api.api_response import failure
        return failure(code, message, status=error.code or 500)

    @app.errorhandler(JsonObjectError)
    def invalid_json_object(error):
        from api.api_response import failure
        return failure('VALIDATION_ERROR', str(error), status=422)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        if app.testing:
            raise error
        # Keep unexpected service failures on the JSON contract. The detailed
        # exception stays in server logs; ordinary users only need a stable
        # retryable response and request id.
        from api.api_response import failure
        app.logger.exception('Unhandled request failure: %s %s', request.method, request.path)
        return failure('INTERNAL_ERROR', '服务暂时不可用，请稍后重试', status=500)

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

    @app.route('/pages/<path:path>')
    def product_pages(path):
        return send_from_directory(os.path.join(demo_root, 'pages'), path, max_age=0)

    # The catalog is also served at `/`, so relative asset URLs resolve here.
    @app.route('/assets/<path:path>')
    def demo_assets(path):
        return send_from_directory(os.path.join(demo_root, 'assets'), path, max_age=0)

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
