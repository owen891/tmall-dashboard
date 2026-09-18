from flask import current_app, g, has_request_context, request
from api.api_response import failure
from db import get_shop_id


def _requested_shop_id():
    requested = (request.args.get('shop_id') or '').strip() if has_request_context() else ''
    configured = str(current_app.config.get('SHOP_ID') or '').strip() if has_request_context() else ''
    if not configured and has_request_context():
        configured = str(current_app.config.get('TMALL_SHOP_ID') or '').strip()
    return requested or configured or get_shop_id()


def _external_request():
    if not has_request_context():
        return False
    remote_addr = request.remote_addr or ''
    forwarded = request.headers.get('X-Forwarded-For') or request.headers.get('X-Real-IP')
    return not (remote_addr in {'127.0.0.1', '::1'} or remote_addr.startswith('127.')) or bool(forwarded)


def _credentials_match_configured_auth():
    if not has_request_context():
        return False
    username = current_app.config.get('DASHBOARD_USERNAME')
    password = current_app.config.get('DASHBOARD_PASSWORD')
    credentials = request.authorization
    if not username or not password or credentials is None:
        return False
    import hmac
    return hmac.compare_digest(credentials.username or '', str(username)) and hmac.compare_digest(credentials.password or '', str(password))


def authorize_request_shop():
    """Resolve the request shop and enforce configured user/shop authorization."""
    shop_id = _requested_shop_id()
    authorization = current_app.config.get('SHOP_AUTHORIZATION') or {}
    allowlist = set(current_app.config.get('SHOP_ALLOWLIST') or set())

    # An unauthenticated external request is handled by the Basic Auth guard so
    # it keeps the stable AUTH_REQUIRED response instead of leaking scope policy.
    if _external_request() and not _credentials_match_configured_auth():
        return None

    if authorization or allowlist:
        credentials = request.authorization if has_request_context() else None
        username = (credentials.username or '').strip() if credentials else ''
        allowed_shops = set(authorization.get(username) or ())
        if shop_id not in allowlist and shop_id not in allowed_shops:
            return failure(
                'SHOP_FORBIDDEN',
                '当前身份无权访问所请求店铺',
                {'shop_id': shop_id},
                status=403,
            )
    elif _external_request() and _credentials_match_configured_auth():
        configured_scope = str(
            current_app.config.get('SHOP_ID')
            or current_app.config.get('TMALL_SHOP_ID')
            or get_shop_id()
        ).strip()
        if shop_id != configured_scope:
            return failure(
                'SHOP_FORBIDDEN',
                '当前身份无权访问所请求店铺',
                {'shop_id': shop_id},
                status=403,
            )
    return None


def current_request_shop_id():
    if has_request_context():
        requested = (request.args.get('shop_id') or '').strip()
        if requested:
            return requested
        scoped = getattr(g, 'shop_id', None)
        if scoped:
            return scoped
        return _requested_shop_id()
    return get_shop_id()


def authenticated_username():
    credentials = request.authorization if has_request_context() else None
    if credentials and credentials.username:
        return credentials.username.strip()
    return ''


def require_import_scan_capability(capability):
    """Enforce optional scan access lists without changing local defaults."""
    if not has_request_context():
        return None
    if not _external_request():
        return None
    configured = set(current_app.config.get(
        'IMPORT_SCAN_MANAGE_USERS' if capability == 'manage' else 'IMPORT_SCAN_VIEW_USERS',
    ) or ())
    if not configured:
        return None
    username = authenticated_username()
    if username not in configured:
        return failure(
            'FORBIDDEN',
            '当前身份无权执行本地扫描操作',
            {'capability': f'import_scan_{capability}'},
            status=403,
        )
    return None


def audit_identity(data, default_reason):
    """Use authenticated identity for external writes; keep local fixture compatibility."""
    data = data or {}
    credentials = request.authorization if has_request_context() else None
    username = (credentials.username or '').strip() if credentials else ''
    if _external_request() and username and _credentials_match_configured_auth():
        return username, str(data.get('reason') or default_reason).strip() or default_reason
    return (
        str(data.get('operator') or data.get('actor') or 'admin').strip() or 'admin',
        str(data.get('reason') or default_reason).strip() or default_reason,
    )


def require_admin_write():
    if not _external_request():
        return None
    if not _credentials_match_configured_auth():
        return failure('AUTH_REQUIRED', '管理写操作需要认证', status=401)
    configured_admins = set(current_app.config.get('DASHBOARD_ADMIN_USERS') or ())
    if configured_admins and authenticated_username() not in configured_admins:
        return failure('FORBIDDEN', '当前身份没有管理写权限', status=403)
    return None

LEGACY_SINGLE_SHOP_PATHS = {
    '/api/refund_alert', '/api/ad_performance', '/api/ad_alerts', '/api/ad_trend',
    '/api/traffic_structure', '/api/action_stats', '/api/anomalies',
    '/api/health', '/api/reviews/summary', '/api/reviews/list', '/api/reviews/products',
    '/api/review', '/api/funnel', '/api/industry_benchmark',
    '/api/report', '/api/legacy/actions', '/api/star', '/api/batch_update', '/api/batch_tags',
    '/api/market/summary', '/api/market/keywords', '/api/market/need_stats',
    '/api/market/rankings', '/api/market/histograms', '/api/market/opportunities',
    '/api/market/reports', '/api/upload/reviews', '/api/upload/data',
    '/api/keywords', '/api/alert_checks', '/api/chart_events',
    '/api/notes', '/api/logs', '/api/product_tags',
}


def reject_legacy_shop_scope(domain):
    """Reject resources whose legacy tables cannot isolate named shops."""
    shop_id = current_request_shop_id()
    if not shop_id or shop_id in ('default', '3828498662'):
        return None
    return failure(
        'UNSUPPORTED_SCOPE',
        f'{domain} 当前仅支持 default 店铺 scope，不允许访问 shop_id={shop_id}',
        {'shop_id': shop_id},
        status=422,
    )


def reject_legacy_single_shop_request():
    """Apply the legacy single-shop guard to every migrated compatibility blueprint."""
    if not has_request_context():
        return None
    legacy_field_update = request.path.startswith('/api/products/') and request.path.endswith('/field')
    legacy_prefixes = ('/api/notes', '/api/chart_events', '/api/product_tags', '/api/logs')
    legacy_path = request.path in LEGACY_SINGLE_SHOP_PATHS or request.path.startswith(legacy_prefixes)
    if not legacy_path and not legacy_field_update:
        return None
    return reject_legacy_shop_scope('历史兼容数据')
