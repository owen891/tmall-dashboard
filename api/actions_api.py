from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from services.actions_service import ActionConflictError, ActionValidationError, actions_service
from db import get_db
from services.shop_scope_service import reject_legacy_shop_scope


def _authorize_product_action(payload, *, capability='product-detail.create_action'):
    """Validate the formal action boundary before touching product_actions.

    There is no user/session identity in the demo runtime, so capability is an
    explicit contract marker. Legacy callers may omit it for compatibility;
    when supplied it must match the formal capability and the product must
    exist. This keeps authorization at the server boundary rather than relying
    solely on button state in the browser.
    """
    requested = payload.get('capability_key')
    if requested is not None and requested != capability:
        return failure('FORBIDDEN', '当前接口不允许该能力标识', {'capability': requested}, status=403)
    product_ids = payload.get('product_ids') if isinstance(payload.get('product_ids'), list) else [payload.get('product_id')]
    product_ids = [str(item) for item in product_ids if item]
    if not product_ids:
        return None
    with get_db() as connection:
        placeholders = ','.join('?' for _ in product_ids)
        rows = connection.execute(
            f'SELECT product_id FROM products WHERE product_id IN ({placeholders})', product_ids
        ).fetchall()
    existing = {row['product_id'] for row in rows}
    missing = sorted(set(product_ids) - existing)
    if missing:
        return failure('NOT_FOUND', '商品不存在，无法创建运营动作', {'product_ids': missing}, status=404)
    return None


def _authorize_capability(payload, expected):
    requested = payload.get('capability_key')
    if requested is not None and requested != expected:
        return failure('FORBIDDEN', 'capability mismatch', {'capability': requested}, status=403)
    return None


actions_bp = Blueprint('actions', __name__)


def _legacy_scope_denied():
    return reject_legacy_shop_scope('经营动作')


def _handle(error):
    return failure('CONFLICT' if isinstance(error, ActionConflictError) else 'VALIDATION_ERROR', str(error), status=409 if isinstance(error, ActionConflictError) else 422)


def _write_success(result, *, action, status=200, availability='available', unknowns=None):
    rows = result.get('actions') if isinstance(result, dict) else None
    if not isinstance(rows, list):
        rows = [result] if isinstance(result, dict) and result.get('id') else []
    ids = [row.get('id') for row in rows if row.get('id')]
    evidence = {
        'source': 'product_actions', 'action': action,
        'row_count': len(rows), 'action_ids': ids,
    }
    if isinstance(result, dict) and result.get('action_group_id'):
        evidence['action_group_id'] = result['action_group_id']
    return success(
        result,
        status=status,
        availability=availability,
        evidence_level='full' if availability == 'available' else 'partial',
        freshness={'latest_update': max((row.get('updated_at') or '' for row in rows), default=None)},
        evidence=[evidence],
        unknowns=list(unknowns or []),
    )


@actions_bp.route('/api/actions', methods=['POST'])
def create_action():
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    denied = _authorize_product_action(payload)
    if denied:
        return denied
    try:
        return _write_success(actions_service.create(payload), action='create', status=201)
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions/batch', methods=['POST'])
def create_actions_batch():
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    denied = _authorize_product_action(payload)
    if denied:
        return denied
    try:
        return _write_success(actions_service.create_batch(payload), action='create_batch', status=201)
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions', methods=['GET'])
def list_actions():
    if (denied := _legacy_scope_denied()):
        return denied
    from repos.actions_repo import ActionsRepo
    try:
        limit = min(max(int(request.args.get('limit', 500)), 1), 1000)
    except ValueError:
        return failure('VALIDATION_ERROR', 'limit 必须是整数', status=422)
    rows = ActionsRepo.list_actions(
        request.args.get('product_id'), limit, request.args.get('status')
    )
    availability = 'available' if rows else 'no-data'
    missing_inputs = [] if rows else ['actions']
    return success(
        rows,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'product_actions', 'row_count': len(rows)}],
    )


@actions_bp.route('/api/actions/<action_id>/transition', methods=['POST'])
def transition_action(action_id):
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    denied = _authorize_capability(payload, 'product-detail.review_action')
    if denied:
        return denied
    try:
        return _write_success(actions_service.transition(action_id, payload.get('status'), payload), action='transition')
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions/<int:action_id>', methods=['PUT'])
def update_legacy_action(action_id):
    """Legacy numeric writes are frozen; use the formal product action API."""
    return failure('LEGACY_READ_ONLY', '旧动作接口已冻结，请使用正式动作接口', {'id': action_id}, status=409)


@actions_bp.route('/api/actions/<int:action_id>', methods=['DELETE'])
def delete_legacy_action(action_id):
    """Legacy numeric writes are frozen; use the formal product action API."""
    return failure('LEGACY_READ_ONLY', '旧动作接口已冻结，请使用正式动作接口', {'id': action_id}, status=409)


@actions_bp.route('/api/actions/recalculate', methods=['POST'])
def recalculate_actions():
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    denied = _authorize_capability(payload, 'product-detail.review_action')
    if denied:
        return denied
    result = actions_service.recalculate()
    updated = int(result.get('updated_count') or 0)
    return _write_success(
        result,
        action='recalculate',
        availability='available' if updated else 'partial',
        unknowns=[] if updated else ['没有动作满足完整观察窗口，未产生新的回算结果'],
    )


@actions_bp.route('/api/actions/<action_id>/review', methods=['POST'])
def review_action(action_id):
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    denied = _authorize_capability(payload, 'product-detail.review_action')
    if denied:
        return denied
    try:
        return _write_success(actions_service.review(action_id, payload), action='review')
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions/pending-review', methods=['GET'])
def pending_review_actions():
    if (denied := _legacy_scope_denied()):
        return denied
    from repos.actions_repo import ActionsRepo
    rows = ActionsRepo.list_pending_review()
    availability = 'available' if rows else 'no-data'
    missing_inputs = [] if rows else ['actions.pending_review']
    return success(
        rows,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'product_actions', 'row_count': len(rows), 'status': 'pending_review'}],
    )


@actions_bp.route('/api/actions/<action_id>/history', methods=['GET'])
def action_history(action_id):
    if (denied := _legacy_scope_denied()):
        return denied
    try:
        return success(actions_service.history(action_id))
    except ActionValidationError as error:
        return _handle(error)
