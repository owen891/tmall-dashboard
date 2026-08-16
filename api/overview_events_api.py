from flask import Blueprint, request

from api.api_response import failure, success
from db import get_db
from repos.audit_repo import AuditRepo


overview_events_bp = Blueprint('overview_events', __name__)


def _payload():
    return request.get_json(silent=True) or {}


def _operator_reason(data, default_reason):
    return data.get('operator') or data.get('actor') or 'admin', data.get('reason') or default_reason


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
    with get_db() as connection:
        rows = connection.execute(
            '''SELECT id, event_date, title, description, color, chart_type, created_at
               FROM chart_events WHERE chart_type = ? ORDER BY event_date''',
            (chart_type,),
        ).fetchall()
    return _success([dict(row) for row in rows], action='list', row_count=len(rows))


@overview_events_bp.route('/api/overview/events', methods=['POST'])
def create_overview_event():
    data = _payload()
    event_date = str(data.get('event_date') or '').strip()
    title = str(data.get('title') or '').strip()
    if not event_date or not title:
        return failure('VALIDATION_ERROR', '日期和标题不能为空', status=422)
    description = str(data.get('description') or '').strip()
    color = str(data.get('color') or '#EF4444').strip()
    chart_type = str(data.get('chart_type') or 'sales').strip()
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
