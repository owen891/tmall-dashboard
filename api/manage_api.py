from flask import Blueprint, request

from api.api_response import failure, success
from db import get_db
from repos.audit_repo import AuditRepo


manage_bp = Blueprint('manage', __name__)


def _payload():
    return request.get_json(silent=True) or {}


def _operator_reason(data, default_reason):
    return data.get('operator') or data.get('actor') or 'admin', data.get('reason') or default_reason


def _success(data, *, source, action, row_count=1, status=200, unknowns=None):
    return success(
        data,
        status=status,
        availability='available' if row_count else 'no-data',
        evidence_level='full' if row_count else 'insufficient',
        evidence=[{'source': source, 'action': action, 'row_count': row_count}],
        unknowns=list(unknowns or []),
    )


def _row(connection, table, item_id):
    return connection.execute(f'SELECT * FROM {table} WHERE id = ?', (item_id,)).fetchone()


@manage_bp.route('/api/manage/tasks', methods=['GET'])
def list_tasks():
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    clauses, params = ['1=1'], []
    if status:
        clauses.append('status = ?')
        params.append(status)
    if priority:
        clauses.append('priority = ?')
        params.append(priority)
    with get_db() as connection:
        rows = connection.execute(
            f'''SELECT * FROM task_items WHERE {' AND '.join(clauses)}
                ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                         due_date IS NULL, due_date ASC, created_at DESC''',
            params,
        ).fetchall()
    values = [dict(row) for row in rows]
    return _success(values, source='task_items', action='list', row_count=len(values))


@manage_bp.route('/api/manage/tasks', methods=['POST'])
def create_task():
    data = _payload()
    title = str(data.get('title') or '').strip()
    if not title:
        return failure('VALIDATION_ERROR', '任务标题不能为空', status=422)
    fields = {
        'description': str(data.get('description') or ''),
        'status': str(data.get('status') or 'todo'),
        'priority': str(data.get('priority') or 'P2'),
        'assignee': str(data.get('assignee') or ''),
        'due_date': str(data.get('due_date') or ''),
    }
    operator, reason = _operator_reason(data, '创建管理任务')
    with get_db() as connection:
        cursor = connection.execute(
            '''INSERT INTO task_items (title, description, status, priority, assignee, due_date)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (title, fields['description'], fields['status'], fields['priority'], fields['assignee'], fields['due_date']),
        )
        item_id = cursor.lastrowid
        row = _row(connection, 'task_items', item_id)
        AuditRepo.record('task', item_id, 'create', operator, reason, {}, dict(row), connection=connection)
        connection.commit()
    return _success(dict(row), source='task_items', action='create', status=201)


@manage_bp.route('/api/manage/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = _payload()
    operator, reason = _operator_reason(data, '更新管理任务')
    allowed = ('title', 'description', 'status', 'priority', 'assignee', 'due_date')
    assignments = [f'{field} = ?' for field in allowed if field in data]
    values = [data[field] for field in allowed if field in data]
    if not assignments:
        return failure('VALIDATION_ERROR', '没有可更新的任务字段', status=422)
    with get_db() as connection:
        before_row = _row(connection, 'task_items', task_id)
        if before_row is None:
            return failure('NOT_FOUND', '任务不存在', status=404)
        connection.execute(
            f'''UPDATE task_items SET {', '.join(assignments)}, updated_at = datetime('now') WHERE id = ?''',
            [*values, task_id],
        )
        after = dict(_row(connection, 'task_items', task_id))
        AuditRepo.record('task', task_id, 'update', operator, reason, dict(before_row), after, connection=connection)
        connection.commit()
    return _success(after, source='task_items', action='update')


@manage_bp.route('/api/manage/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    data = _payload()
    operator, reason = _operator_reason(data, '删除管理任务')
    with get_db() as connection:
        row = _row(connection, 'task_items', task_id)
        if row is None:
            return failure('NOT_FOUND', '任务不存在', status=404)
        connection.execute('DELETE FROM task_items WHERE id = ?', (task_id,))
        AuditRepo.record('task', task_id, 'delete', operator, reason, dict(row), {}, connection=connection)
        connection.commit()
    return _success({'task_id': task_id, 'deleted_count': 1}, source='task_items', action='delete')


@manage_bp.route('/api/manage/kpis', methods=['GET'])
def list_kpis():
    period = request.args.get('period', '')
    with get_db() as connection:
        rows = connection.execute(
            'SELECT * FROM user_kpis' + (' WHERE period = ?' if period else '') + ' ORDER BY achievement_rate DESC',
            (period,) if period else (),
        ).fetchall()
    values = [dict(row) for row in rows]
    return _success(values, source='user_kpis', action='list', row_count=len(values))


@manage_bp.route('/api/manage/kpis', methods=['POST'])
def create_kpi():
    data = _payload()
    user_name = str(data.get('user_name') or '').strip()
    if not user_name:
        return failure('VALIDATION_ERROR', 'KPI 负责人不能为空', status=422)
    values = (
        user_name, str(data.get('period') or ''), float(data.get('target_gmv') or 0),
        float(data.get('actual_gmv') or 0), float(data.get('achievement_rate') or 0),
        str(data.get('rating') or 'C'),
    )
    operator, reason = _operator_reason(data, '创建用户 KPI')
    with get_db() as connection:
        cursor = connection.execute(
            '''INSERT INTO user_kpis (user_name, period, target_gmv, actual_gmv, achievement_rate, rating)
               VALUES (?, ?, ?, ?, ?, ?)''', values,
        )
        item_id = cursor.lastrowid
        row = _row(connection, 'user_kpis', item_id)
        AuditRepo.record('user_kpi', item_id, 'create', operator, reason, {}, dict(row), connection=connection)
        connection.commit()
    return _success(dict(row), source='user_kpis', action='create', status=201)


@manage_bp.route('/api/manage/kpis/<int:kpi_id>', methods=['PUT'])
def update_kpi(kpi_id):
    data = _payload()
    operator, reason = _operator_reason(data, '更新用户 KPI')
    allowed = ('user_name', 'period', 'target_gmv', 'actual_gmv', 'achievement_rate', 'rating')
    assignments = [f'{field} = ?' for field in allowed if field in data]
    values = [data[field] for field in allowed if field in data]
    if not assignments:
        return failure('VALIDATION_ERROR', '没有可更新的 KPI 字段', status=422)
    with get_db() as connection:
        before_row = _row(connection, 'user_kpis', kpi_id)
        if before_row is None:
            return failure('NOT_FOUND', 'KPI 不存在', status=404)
        connection.execute(
            f'''UPDATE user_kpis SET {', '.join(assignments)}, updated_at = datetime('now') WHERE id = ?''',
            [*values, kpi_id],
        )
        after = dict(_row(connection, 'user_kpis', kpi_id))
        AuditRepo.record('user_kpi', kpi_id, 'update', operator, reason, dict(before_row), after, connection=connection)
        connection.commit()
    return _success(after, source='user_kpis', action='update')


@manage_bp.route('/api/manage/kpis/<int:kpi_id>', methods=['DELETE'])
def delete_kpi(kpi_id):
    data = _payload()
    operator, reason = _operator_reason(data, '删除用户 KPI')
    with get_db() as connection:
        row = _row(connection, 'user_kpis', kpi_id)
        if row is None:
            return failure('NOT_FOUND', 'KPI 不存在', status=404)
        connection.execute('DELETE FROM user_kpis WHERE id = ?', (kpi_id,))
        AuditRepo.record('user_kpi', kpi_id, 'delete', operator, reason, dict(row), {}, connection=connection)
        connection.commit()
    return _success({'kpi_id': kpi_id, 'deleted_count': 1}, source='user_kpis', action='delete')
