from datetime import datetime

from flask import Blueprint, request

from api.api_response import failure, success
from db import get_db
from repos.audit_repo import AuditRepo
from api.data_api import _cron_to_label, _parse_cron_expr, _scheduled_matches, _validate_file_pattern


schedules_bp = Blueprint('schedules', __name__)


@schedules_bp.before_request
def reject_removed_schedule_api():
    return failure(
        'LEGACY_SCHEDULE_REMOVED',
        '旧定时任务已下线，请使用 /api/import-scans',
        status=410,
    )


def _payload():
    return request.get_json(silent=True) or {}


def _operator_reason(data, default_reason):
    return data.get('operator') or data.get('actor') or 'admin', data.get('reason') or default_reason


def _task(row):
    result = dict(row)
    result['cron_label'] = _cron_to_label(result.get('cron_expr'))
    return result


def _success(data, *, action, row_count=1, status=200, unknowns=None):
    return success(
        data,
        status=status,
        availability='available' if row_count else 'no-data',
        evidence_level='full' if row_count else 'insufficient',
        evidence=[{'source': 'scheduled_tasks', 'action': action, 'row_count': row_count}],
        unknowns=list(unknowns or []),
    )


def _get_task(connection, task_id):
    return connection.execute(
        '''SELECT id, task_name, task_type, cron_expr, file_pattern, enabled,
                  last_run, next_run, status, created_at
           FROM scheduled_tasks WHERE id = ?''',
        (task_id,),
    ).fetchone()


@schedules_bp.route('/api/manage/schedules', methods=['GET'])
def list_schedules():
    with get_db() as connection:
        rows = connection.execute(
            '''SELECT id, task_name, task_type, cron_expr, file_pattern, enabled,
                      last_run, next_run, status, created_at
               FROM scheduled_tasks ORDER BY id DESC'''
        ).fetchall()
    tasks = [_task(row) for row in rows]
    return _success(tasks, action='list', row_count=len(tasks))


@schedules_bp.route('/api/manage/schedules', methods=['POST'])
def create_schedule():
    data = _payload()
    task_name = str(data.get('task_name') or '').strip()
    cron_expr = str(data.get('cron_expr') or '').strip()
    if not task_name or not cron_expr:
        return failure('VALIDATION_ERROR', '任务名称和调度表达式不能为空', status=422)
    try:
        file_pattern = _validate_file_pattern(data.get('file_pattern') or '*.xlsx')
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    task_type = str(data.get('task_type') or 'data_import').strip()
    next_run = _parse_cron_expr(cron_expr)
    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None
    operator, reason = _operator_reason(data, '创建定时任务')

    with get_db() as connection:
        cursor = connection.execute(
            '''INSERT INTO scheduled_tasks (task_name, task_type, cron_expr, file_pattern, next_run)
               VALUES (?, ?, ?, ?, ?)''',
            (task_name, task_type, cron_expr, file_pattern, next_run_str),
        )
        task_id = cursor.lastrowid
        AuditRepo.record(
            'scheduled_task', task_id, 'create', operator, reason,
            {}, {'task_name': task_name, 'task_type': task_type, 'cron_expr': cron_expr, 'file_pattern': file_pattern},
            connection=connection,
        )
        row = _get_task(connection, task_id)
        connection.commit()
    return _success(_task(row), action='create', status=201)


@schedules_bp.route('/api/manage/schedules/<int:task_id>', methods=['PUT'])
def update_schedule(task_id):
    data = _payload()
    operator, reason = _operator_reason(data, '更新定时任务')
    with get_db() as connection:
        row = _get_task(connection, task_id)
        if row is None:
            return failure('NOT_FOUND', '任务不存在', status=404)
        before = _task(row)
        assignments, values = [], []
        if 'enabled' in data:
            assignments.append('enabled = ?')
            values.append(1 if data['enabled'] else 0)
            if data['enabled']:
                assignments.append("status = CASE WHEN status = 'error' THEN 'active' ELSE status END")
        if data.get('cron_expr'):
            cron_expr = str(data['cron_expr']).strip()
            next_run = _parse_cron_expr(cron_expr)
            assignments.extend(['cron_expr = ?', 'next_run = ?'])
            values.extend([cron_expr, next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None])
        for key in ('task_name', 'file_pattern', 'task_type'):
            if key in data:
                assignments.append(f'{key} = ?')
                if key == 'file_pattern':
                    try:
                        values.append(_validate_file_pattern(data[key]))
                    except ValueError as error:
                        return failure('VALIDATION_ERROR', str(error), status=422)
                else:
                    values.append(str(data[key] or '').strip())
        if not assignments:
            return failure('VALIDATION_ERROR', '没有可更新的调度字段', status=422)
        connection.execute(
            f'UPDATE scheduled_tasks SET {", ".join(assignments)} WHERE id = ?',
            [*values, task_id],
        )
        after = _task(_get_task(connection, task_id))
        AuditRepo.record('scheduled_task', task_id, 'update', operator, reason, before, after, connection=connection)
        connection.commit()
    return _success(after, action='update')


@schedules_bp.route('/api/manage/schedules/<int:task_id>', methods=['DELETE'])
def delete_schedule(task_id):
    data = _payload()
    operator, reason = _operator_reason(data, '删除定时任务')
    with get_db() as connection:
        row = _get_task(connection, task_id)
        if row is None:
            return failure('NOT_FOUND', '任务不存在', status=404)
        connection.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
        AuditRepo.record('scheduled_task', task_id, 'delete', operator, reason, _task(row), {}, connection=connection)
        connection.commit()
    return _success({'task_id': task_id, 'deleted_count': 1}, action='delete')


@schedules_bp.route('/api/manage/schedules/<int:task_id>/run', methods=['POST'])
def run_schedule(task_id):
    data = _payload()
    operator, reason = _operator_reason(data, '手动执行定时任务')
    with get_db() as connection:
        row = _get_task(connection, task_id)
        if row is None:
            return failure('NOT_FOUND', '任务不存在', status=404)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        connection.execute(
            "UPDATE scheduled_tasks SET last_run = ?, status = 'running' WHERE id = ?",
            (now_str, task_id),
        )
        status = 'active'
        message = f'任务 "{row["task_name"]}" 执行完成'
        try:
            pattern = row['file_pattern'] or '*.xlsx'
            matched_files = _scheduled_matches(pattern)
            if matched_files:
                from scripts.import_data import import_excel_file
                import_excel_file(matched_files[0])
        except Exception as error:
            status = 'error'
            message = f'任务执行失败: {error}'
        next_run = _parse_cron_expr(row['cron_expr'])
        next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None
        connection.execute(
            'UPDATE scheduled_tasks SET status = ?, next_run = ? WHERE id = ?',
            (status, next_run_str, task_id),
        )
        after = _task(_get_task(connection, task_id))
        after['message'] = message
        AuditRepo.record('scheduled_task', task_id, 'run', operator, reason, _task(row), after, connection=connection)
        connection.commit()
    return _success(after, action='run')
