from datetime import datetime
from re import fullmatch

from flask import Blueprint, request

from api.api_response import failure, json_object, success
from db import get_db
from repos.audit_repo import AuditRepo
from services.shop_scope_service import audit_identity, require_admin_write


overview_events_bp = Blueprint('overview_events', __name__)

ALLOWED_CHART_TYPES = {'sales', 'refund', 'traffic', 'promotion'}
HEX_COLOR = r'^#[0-9A-Fa-f]{6}$'


def _payload():
    return json_object(request)


def _operator_reason(data, default_reason):
    return audit_identity(data, default_reason)


def _validate_event_fields(event_date, title, description, color, chart_type):
    try:
        parsed = datetime.strptime(event_date, '%Y-%m-%d')
    except (TypeError, ValueError):
        return 'event_date 必须使用 YYYY-MM-DD 格式'
    if parsed.strftime('%Y-%m-%d') != event_date:
        return 'event_date 必须使用 YYYY-MM-DD 格式'
    if not 1 <= len(title) <= 120:
        return 'title 长度必须为 1-120 个字符'
    if len(description) > 1000:
        return 'description 长度不能超过 1000 个字符'
    if not fullmatch(HEX_COLOR, color):
        return 'color 必须是六位十六进制颜色'
    if chart_type not in ALLOWED_CHART_TYPES:
        return 'chart_type 不受支持'
    return None


def _success(data, *, action, row_count=1, status=200):
    return success(
        data,
        status=status,
        availability='available' if row_count else 'no-data',
        evidence_level='full' if row_count else 'insufficient',
        evidence=[{'source': 'chart_events', 'action': action, 'row_count': row_count}],
    )


@overview_events_bp.route('/api/overview/events', methods=['GET'])
def list_overview_events():
    chart_type = request.args.get('chart_type', 'sales')
    if chart_type not in ALLOWED_CHART_TYPES:
        return failure('VALIDATION_ERROR', 'chart_type 不受支持', status=422)
    with get_db() as connection:
        rows = connection.execute(
            '''SELECT id, event_date, title, description, color, chart_type, created_at
               FROM chart_events WHERE chart_type = ? ORDER BY event_date''',
            (chart_type,),
        ).fetchall()
    return _success([dict(row) for row in rows], action='list', row_count=len(rows))


@overview_events_bp.route('/api/overview/events', methods=['POST'])
def create_overview_event():
    if (denied := require_admin_write()):
        return denied
    data = _payload()
    event_date = str(data.get('event_date') or '').strip()
    title = str(data.get('title') or '').strip()
    if not event_date or not title:
        return failure('VALIDATION_ERROR', '日期和标题不能为空', status=422)
    description = str(data.get('description') or '').strip()
    color = str(data.get('color') or '#EF4444').strip()
    chart_type = str(data.get('chart_type') or 'sales').strip()
    error = _validate_event_fields(event_date, title, description, color, chart_type)
    if error:
        return failure('VALIDATION_ERROR', error, status=422)
    operator, reason = _operator_reason(data, '记录经营事件')
    with get_db() as connection:
        cursor = connection.execute(
            '''INSERT INTO chart_events (event_date, title, description, color, chart_type)
               VALUES (?, ?, ?, ?, ?)''',
            (event_date, title, description, color, chart_type),
        )
        event_id = cursor.lastrowid
        AuditRepo.record(
            'chart_event', event_id, 'create', operator, reason,
            {}, {'event_date': event_date, 'title': title, 'description': description, 'color': color, 'chart_type': chart_type},
            connection=connection,
        )
        row = connection.execute(
            '''SELECT id, event_date, title, description, color, chart_type, created_at
               FROM chart_events WHERE id = ?''', (event_id,)
        ).fetchone()
        connection.commit()
    return _success(dict(row), action='create', status=201)


@overview_events_bp.route('/api/overview/events/<int:event_id>', methods=['DELETE'])
def delete_overview_event(event_id):
    if (denied := require_admin_write()):
        return denied
    data = _payload()
    operator, reason = _operator_reason(data, '删除经营事件')
    with get_db() as connection:
        row = connection.execute(
            '''SELECT id, event_date, title, description, color, chart_type
               FROM chart_events WHERE id = ?''', (event_id,)
        ).fetchone()
        if row is None:
            return failure('NOT_FOUND', '经营事件不存在', status=404)
        connection.execute('DELETE FROM chart_events WHERE id = ?', (event_id,))
        AuditRepo.record(
            'chart_event', event_id, 'delete', operator, reason,
            dict(row), {}, connection=connection,
        )
        connection.commit()
    return _success({'event_id': event_id, 'deleted_count': 1}, action='delete')
