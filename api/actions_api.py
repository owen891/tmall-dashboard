from flask import Blueprint, request

from api.api_response import failure, success
from services.actions_service import ActionConflictError, ActionValidationError, actions_service


actions_bp = Blueprint('actions', __name__)


def _handle(error):
    return failure('CONFLICT' if isinstance(error, ActionConflictError) else 'VALIDATION_ERROR', str(error), status=409 if isinstance(error, ActionConflictError) else 422)


@actions_bp.route('/api/actions', methods=['POST'])
def create_action():
    try:
        return success(actions_service.create(request.get_json(silent=True) or {}), status=201)
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions/batch', methods=['POST'])
def create_actions_batch():
    try:
        return success(actions_service.create_batch(request.get_json(silent=True) or {}), status=201)
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions', methods=['GET'])
def list_actions():
    from repos.actions_repo import ActionsRepo
    try:
        limit = min(max(int(request.args.get('limit', 500)), 1), 1000)
    except ValueError:
        return failure('VALIDATION_ERROR', 'limit 必须是整数', status=422)
    return success(ActionsRepo.list_actions(request.args.get('product_id'), limit))


@actions_bp.route('/api/actions/<action_id>/transition', methods=['POST'])
def transition_action(action_id):
    payload = request.get_json(silent=True) or {}
    try:
        return success(actions_service.transition(action_id, payload.get('status'), payload))
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions/<int:action_id>', methods=['PUT'])
def update_legacy_action(action_id):
    """Keep the pre-1.0 numeric action endpoint available during migration."""
    payload = request.get_json(silent=True) or {}
    from db import get_db
    with get_db() as connection:
        cursor = connection.execute(
            '''UPDATE operation_actions SET action_type = ?, action_detail = ? WHERE id = ?''',
            (payload.get('action_type'), payload.get('action_detail'), action_id),
        )
        connection.commit()
    if cursor.rowcount == 0:
        return failure('NOT_FOUND', '旧动作不存在', status=404)
    return success({'id': action_id, 'compatibility': 'legacy-operation-action'})


@actions_bp.route('/api/actions/<int:action_id>', methods=['DELETE'])
def delete_legacy_action(action_id):
    """Keep the pre-1.0 numeric action delete endpoint available during migration."""
    from db import get_db
    with get_db() as connection:
        cursor = connection.execute('DELETE FROM operation_actions WHERE id = ?', (action_id,))
        connection.commit()
    if cursor.rowcount == 0:
        return failure('NOT_FOUND', '旧动作不存在', status=404)
    return success({'id': action_id, 'deleted': True, 'compatibility': 'legacy-operation-action'})


@actions_bp.route('/api/actions/recalculate', methods=['POST'])
def recalculate_actions():
    return success(actions_service.recalculate())


@actions_bp.route('/api/actions/<action_id>/review', methods=['POST'])
def review_action(action_id):
    try:
        return success(actions_service.review(action_id, request.get_json(silent=True) or {}))
    except (ActionValidationError, ActionConflictError) as error:
        return _handle(error)


@actions_bp.route('/api/actions/pending-review', methods=['GET'])
def pending_review_actions():
    from repos.actions_repo import ActionsRepo
    return success(ActionsRepo.list_pending_review())


@actions_bp.route('/api/actions/<action_id>/history', methods=['GET'])
def action_history(action_id):
    try:
        return success(actions_service.history(action_id))
    except ActionValidationError as error:
        return _handle(error)
