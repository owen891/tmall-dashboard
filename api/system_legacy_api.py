from datetime import datetime
from datetime import timedelta
"""System Legacy API - 系统管理相关接口（旧版）

从 data_api.py 拆分出来的独立模块，包含：
- 数据库备份
- 运营动作 CRUD
- 任务 CRUD
- 动作统计
- 日志 CRUD
- 图表事件 CRUD
- 定时任务 CRUD/运行
"""

import io
import threading
import time
from api.data_api import _legacy_task_payload, _scheduled_matches, _validate_file_pattern, _validate_period_arg, cached_api

import pandas as pd
from flask import Blueprint, current_app, jsonify, request

from db import get_db
from api.api_response import failure, json_object, success
from repos.audit_repo import AuditRepo
from services.management_validation import (
    TASK_PRIORITIES as _TASK_PRIORITIES,
    TASK_STATUSES as _TASK_STATUSES,
    validate_task_fields as _validate_task_fields,
)


system_legacy_bp = Blueprint('system_legacy', __name__)



@system_legacy_bp.route('/api/backup', methods=['POST'])
def trigger_backup():
    """手动触发数据库备份"""
    if current_app.config.get('TESTING'):
        return jsonify({'success': True, 'skipped': 'testing'})
    from scripts.import_data import backup_database
    success = backup_database()
    return jsonify({'success': success})

@system_legacy_bp.route('/api/legacy/actions', methods=['GET'])
def get_actions():
    """运营动作列表"""
    period = request.args.get('period', '')
    product_id = request.args.get('product_id', '')
    limit = request.args.get('limit', 100, type=int)
    limit = max(1, min(limit or 100, 500))

    with get_db() as conn:
        clauses = []
        params = []
        if period:
            clauses.append('a.action_date LIKE ?')
            params.append(f'{period}%')
        if product_id:
            clauses.append('a.product_id = ?')
            params.append(product_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        params.append(limit)
        rows = [dict(r) for r in conn.execute(f'''
            SELECT a.id, a.product_id, a.action_date, a.action_type, a.action_detail,
                   a.effectiveness_score, p.title, p.image_url
            FROM operation_actions a
            JOIN products p ON a.product_id = p.product_id
            {where_sql}
            ORDER BY a.action_date DESC
            LIMIT ?
        ''', params).fetchall()]
    return jsonify(rows)

# ==================== 流量结构分析 API ====================

@system_legacy_bp.route('/api/legacy/actions', methods=['POST'])
def create_action():
    return failure(
        'LEGACY_READ_ONLY',
        'Legacy actions are read-only; use /api/actions.',
        details={'replacement': '/api/actions'},
        status=409,
    )

@system_legacy_bp.route('/api/legacy/actions/<int:action_id>', methods=['PUT'])
def update_action(action_id):
    return failure(
        'LEGACY_READ_ONLY',
        'Legacy actions are read-only; use /api/actions.',
        details={'replacement': '/api/actions'},
        status=409,
    )

@system_legacy_bp.route('/api/legacy/actions/<int:action_id>', methods=['DELETE'])
def delete_action(action_id):
    return failure(
        'LEGACY_READ_ONLY',
        'Legacy actions are read-only; use /api/actions.',
        details={'replacement': '/api/actions'},
        status=409,
    )

@system_legacy_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    status = 'in_progress' if status == 'doing' else status
    if status and status not in _TASK_STATUSES:
        return jsonify({'error': 'status 参数不合法'}), 422
    if priority and priority not in _TASK_PRIORITIES:
        return jsonify({'error': 'priority 参数不合法'}), 422
    with get_db() as conn:
        where = ['1=1']
        params = []
        if status:
            where.append('status = ?')
            params.append(status)
        if priority:
            where.append('priority = ?')
            params.append(priority)
        rows = [_legacy_task_payload(r) for r in conn.execute(f'''
            SELECT * FROM task_items WHERE {' AND '.join(where)}
            ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                     due_date IS NULL, due_date ASC, created_at DESC
        ''', params).fetchall()]
    return jsonify(rows)

@system_legacy_bp.route('/api/tasks', methods=['POST'])
def create_task():
    """创建任务"""
    data = json_object(request)
    fields = {
        'title': str(data.get('title') or '').strip(),
        'description': str(data.get('description') or ''),
        'status': str(data.get('status') or 'todo'),
        'priority': str(data.get('priority') or 'P2'),
        'assignee': str(data.get('assignee') or ''),
        'due_date': str(data.get('due_date') or ''),
    }
    if fields['status'] == 'doing':
        fields['status'] = 'in_progress'
    try:
        _validate_task_fields(fields)
    except ValueError as error:
        return jsonify({'error': str(error)}), 422
    operator = data.get('operator') or data.get('actor') or 'admin'
    reason = data.get('reason') or '创建管理任务'
    with get_db() as conn:
        conn.execute('''INSERT INTO task_items (title, description, status, priority, assignee, due_date)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (fields['title'], fields['description'], fields['status'],
             fields['priority'], fields['assignee'], fields['due_date']))
        item_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        row = conn.execute('SELECT * FROM task_items WHERE id = ?', (item_id,)).fetchone()
        AuditRepo.record('task', item_id, 'create', operator, reason, {}, dict(row), connection=conn)
        conn.commit()
        return jsonify({'success': True, 'data': _legacy_task_payload(row)})

@system_legacy_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    data = json_object(request)
    normalized = dict(data)
    for field in ('title', 'description', 'status', 'priority', 'assignee', 'due_date'):
        if field in normalized:
            normalized[field] = str(normalized.get(field) or '').strip()
    if normalized.get('status') == 'doing':
        normalized['status'] = 'in_progress'
    allowed = ('title', 'description', 'status', 'priority', 'assignee', 'due_date')
    if not any(field in normalized for field in allowed):
        return jsonify({'error': 'No fields to update'}), 422
    try:
        _validate_task_fields(normalized, partial=True)
    except ValueError as error:
        return jsonify({'error': str(error)}), 422
    operator = data.get('operator') or data.get('actor') or 'admin'
    reason = data.get('reason') or '更新管理任务'
    with get_db() as conn:
        sets = []
        params = []
        for field in allowed:
            if field in normalized:
                sets.append(f'{field} = ?')
                params.append(normalized[field])
        before = conn.execute('SELECT * FROM task_items WHERE id = ?', (task_id,)).fetchone()
        if before is None:
            return jsonify({'error': 'Task not found'}), 404
        sets.append("updated_at = datetime('now')")
        params.append(task_id)
        conn.execute(f'UPDATE task_items SET {", ".join(sets)} WHERE id = ?', params)
        after = conn.execute('SELECT * FROM task_items WHERE id = ?', (task_id,)).fetchone()
        AuditRepo.record('task', task_id, 'update', operator, reason, dict(before), dict(after), connection=conn)
        conn.commit()
        return jsonify({'success': True, 'data': _legacy_task_payload(after)})

@system_legacy_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    elif not isinstance(data, dict):
        return failure('VALIDATION_ERROR', '请求体必须是 JSON 对象', status=422)
    operator = data.get('operator') or data.get('actor') or 'admin'
    reason = data.get('reason') or '删除管理任务'
    with get_db() as conn:
        before = conn.execute('SELECT * FROM task_items WHERE id = ?', (task_id,)).fetchone()
        if before is None:
            return jsonify({'error': 'Task not found'}), 404
        cursor = conn.execute('DELETE FROM task_items WHERE id = ?', (task_id,))
        AuditRepo.record('task', task_id, 'delete', operator, reason, dict(before), {}, connection=conn)
        conn.commit()
        return jsonify({'success': True, 'deleted_count': cursor.rowcount})

# ==================== 用户KPI API ====================

#

@system_legacy_bp.route('/api/action_stats', methods=['GET'])
@cached_api('get_action_stats', ttl=60)
def get_action_stats():
    """动作类型效果统计"""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute('''
            SELECT action_type,
                   COUNT(*) as count,
                   AVG(payment_change) as avg_payment_change,
                   AVG(conversion_change) as avg_conversion_change,
                   AVG(effectiveness_score) as avg_score
            FROM operation_actions
            WHERE effectiveness_score > 0
            GROUP BY action_type
            ORDER BY avg_score DESC
        ''').fetchall()]
    return jsonify(rows)

# 预留接口：异常检测（前端暂未调用）

@system_legacy_bp.route('/api/logs', methods=['GET'])
def get_logs():
    """获取最近操作日志"""
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()]
    return jsonify(rows)

@system_legacy_bp.route('/api/logs', methods=['POST'])
def create_log():
    """记录操作日志"""
    data = json_object(request)
    action = str(data.get('action') or '').strip()
    detail = str(data.get('detail') or '').strip()
    operator = str(data.get('operator') or 'admin').strip() or 'admin'
    if not action:
        return failure('VALIDATION_ERROR', 'action is required', status=422)
    with get_db() as conn:
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (action, detail, operator)
        )
        conn.commit()
    return jsonify({'success': True})


#

@system_legacy_bp.route('/api/chart_events', methods=['GET'])
def get_chart_events():
    """获取图表事件标注"""
    chart_type = request.args.get('chart_type', 'sales')
    with get_db() as conn:
        rows = conn.execute(
            'SELECT id, event_date, title, description, color, chart_type, created_at FROM chart_events WHERE chart_type = ? ORDER BY event_date',
            (chart_type,)
        ).fetchall()
        events = [dict(r) for r in rows]
    return jsonify(events)

@system_legacy_bp.route('/api/chart_events', methods=['POST'])
def create_chart_event():
    """创建图表事件标注"""
    data = json_object(request)
    event_date = str(data.get('event_date') or '').strip()
    title = str(data.get('title') or '').strip()
    description = str(data.get('description') or '').strip()
    color = str(data.get('color') or '#EF4444').strip()
    chart_type = str(data.get('chart_type') or 'sales').strip()

    if not event_date or not title:
        return failure('VALIDATION_ERROR', '日期和标题不能为空', status=422)
    invalid = _validate_period_arg('daily', event_date, 'event_date')
    if invalid:
        return invalid

    with get_db() as conn:
        conn.execute(
            'INSERT INTO chart_events (event_date, title, description, color, chart_type) VALUES (?, ?, ?, ?, ?)',
            (event_date, title, description, color, chart_type)
        )
        conn.commit()
    return jsonify({'success': True, 'message': '标注已添加'})

@system_legacy_bp.route('/api/chart_events/<int:event_id>', methods=['DELETE'])
def delete_chart_event(event_id):
    """删除图表事件标注"""
    with get_db() as conn:
        conn.execute('DELETE FROM chart_events WHERE id = ?', (event_id,))
        conn.commit()
    return jsonify({'success': True, 'message': '标注已删除'})


# ==================== Feature 8: 智能数据导入调度 ====================
# 内存中的调度器状态
_scheduler_lock = threading.Lock()
_scheduler_running = False


def _parse_cron_expr(cron_expr):
    """解析简单 cron 表达式，返回下次运行时间"""
    try:
        parts = cron_expr.strip().lower().split()
        if not parts:
            return None
        now = datetime.now()

        if parts[0] == 'daily':
            # daily HH:MM
            time_str = parts[1] if len(parts) > 1 else '08:00'
            h, m = map(int, time_str.split(':'))
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif parts[0] == 'weekly':
            # weekly day HH:MM
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            day_name = parts[1] if len(parts) > 1 else 'mon'
            time_str = parts[2] if len(parts) > 2 else '08:00'
            h, m = map(int, time_str.split(':'))
            target_day = day_map.get(day_name, 0)
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            days_ahead = (target_day - now.weekday()) % 7
            if days_ahead == 0 and next_run <= now:
                days_ahead = 7
            next_run += timedelta(days=days_ahead)
            return next_run

        elif parts[0] == 'monthly':
            # monthly DD HH:MM
            dom = int(parts[1]) if len(parts) > 1 else 1
            time_str = parts[2] if len(parts) > 2 else '08:00'
            h, m = map(int, time_str.split(':'))
            try:
                next_run = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
            except ValueError:
                # 处理月末日期（如31号在某些月份不存在）
                last_day = _calendar.monthrange(now.year, now.month)[1]
                dom = min(dom, last_day)
                next_run = now.replace(day=dom, hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run

    except Exception:
        # cron 表达式解析失败时返回 None，由调用方处理
        pass
    return None


def _cron_to_label(cron_expr):
    """将 cron 表达式转为可读中文标签"""
    try:
        parts = cron_expr.strip().lower().split()
        if parts[0] == 'daily':
            time_str = parts[1] if len(parts) > 1 else '08:00'
            return f"每天 {time_str}"
        elif parts[0] == 'weekly':
            day_names = {'mon': '周一', 'tue': '周二', 'wed': '周三', 'thu': '周四', 'fri': '周五', 'sat': '周六', 'sun': '周日'}
            day_name = day_names.get(parts[1] if len(parts) > 1 else 'mon', '周一')
            time_str = parts[2] if len(parts) > 2 else '08:00'
            return f"每{day_name} {time_str}"
        elif parts[0] == 'monthly':
            dom = parts[1] if len(parts) > 1 else '1'
            time_str = parts[2] if len(parts) > 2 else '08:00'
            return f"每月{dom}号 {time_str}"
    except Exception:
        # cron 表达式描述解析失败时返回原始表达式
        pass
    return cron_expr


def _check_and_run_scheduled_tasks():
    # Deprecated: the standalone scanner owns all scheduled imports.
    return []
    """检查并执行到期的定时任务"""
    with _scheduler_lock:
        with get_db() as conn:
            tasks = conn.execute(
                'SELECT id, task_name, cron_expr, file_pattern, last_run, next_run FROM scheduled_tasks WHERE enabled = 1 AND status = ?',
                ('active',)
            ).fetchall()

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            now = datetime.now()

            for task in tasks:
                next_run_str = task['next_run']
                if not next_run_str:
                    # 计算下次运行时间
                    next_run = _parse_cron_expr(task['cron_expr'])
                    if next_run:
                        conn.execute(
                            'UPDATE scheduled_tasks SET next_run = ? WHERE id = ?',
                            (next_run.strftime('%Y-%m-%d %H:%M:%S'), task['id'])
                        )
                    continue

                try:
                    next_run_dt = datetime.strptime(next_run_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    continue

                if now >= next_run_dt:
                    # 执行任务
                    conn.execute(
                        'UPDATE scheduled_tasks SET last_run = ?, status = ? WHERE id = ?',
                        (now_str, 'running', task['id'])
                    )
                    conn.commit()

                    # 模拟执行导入（实际环境中会读取文件）
                    try:
                        # 这里可以调用实际的导入逻辑
                        pattern = task['file_pattern'] or '*.xlsx'
                        matched_files = _scheduled_matches(pattern)

                        if matched_files:
                            # 执行导入
                            from scripts.import_data import import_excel_file
                            for fpath in matched_files[:1]:  # 每次最多导入一个文件
                                import_excel_file(fpath)

                        status = 'active'
                    except Exception:
                        status = 'error'

                    # 计算下次运行时间
                    next_run = _parse_cron_expr(task['cron_expr'])
                    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None

                    conn.execute(
                        'UPDATE scheduled_tasks SET status = ?, next_run = ? WHERE id = ?',
                        (status, next_run_str, task['id'])
                    )
                    conn.commit()


# 在每个请求前检查定时任务
@system_legacy_bp.before_request
def _scheduler_check():
    if request.path == '/api/scheduled_tasks' or request.path.startswith('/api/scheduled_tasks/'):
        return failure(
            'LEGACY_SCHEDULE_REMOVED',
            '旧定时任务已下线，请使用 /api/import-scans',
            status=410,
        )
    # Scheduling is intentionally performed by scripts/run_import_scanner.py.
    # Flask requests must never execute imports as a side effect.
    return None

@system_legacy_bp.route('/api/scheduled_tasks', methods=['GET'])
def get_scheduled_tasks():
    """获取所有定时任务"""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT id, task_name, task_type, cron_expr, file_pattern, enabled, last_run, next_run, status, created_at FROM scheduled_tasks ORDER BY id DESC'
        ).fetchall()
        tasks = []
        for r in rows:
            t = dict(r)
            t['cron_label'] = _cron_to_label(t['cron_expr'])
            tasks.append(t)
    return jsonify(tasks)

@system_legacy_bp.route('/api/scheduled_tasks', methods=['POST'])
def create_scheduled_task():
    """创建定时任务"""
    data = json_object(request)
    task_name = str(data.get('task_name') or '').strip()
    cron_expr = str(data.get('cron_expr') or '').strip()
    try:
        file_pattern = _validate_file_pattern(data.get('file_pattern', '*.xlsx'))
    except ValueError as error:
        return jsonify({'success': False, 'error': str(error)}), 422

    if not task_name or not cron_expr:
        return failure('VALIDATION_ERROR', '任务名称和调度表达式不能为空', status=422)

    next_run = _parse_cron_expr(cron_expr)
    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None

    with get_db() as conn:
        conn.execute(
            'INSERT INTO scheduled_tasks (task_name, cron_expr, file_pattern, next_run) VALUES (?, ?, ?, ?)',
            (task_name, cron_expr, file_pattern, next_run_str)
        )
        conn.commit()
    return jsonify({'success': True, 'message': '任务已创建'})

@system_legacy_bp.route('/api/scheduled_tasks/<int:task_id>', methods=['PUT'])
def update_scheduled_task(task_id):
    """更新定时任务"""
    data = json_object(request)

    with get_db() as conn:
        row = conn.execute('SELECT id FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return jsonify({'error': '任务不存在'}), 404

        if 'enabled' in data:
            conn.execute('UPDATE scheduled_tasks SET enabled = ? WHERE id = ?', (1 if data['enabled'] else 0, task_id))
            if data['enabled']:
                conn.execute("UPDATE scheduled_tasks SET status = 'active' WHERE id = ? AND status = 'error'", (task_id,))
        if 'cron_expr' in data and data['cron_expr']:
            cron_expr = str(data['cron_expr']).strip()
            next_run = _parse_cron_expr(cron_expr)
            next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None
            conn.execute('UPDATE scheduled_tasks SET cron_expr = ?, next_run = ? WHERE id = ?', (cron_expr, next_run_str, task_id))
        if 'task_name' in data:
            conn.execute('UPDATE scheduled_tasks SET task_name = ? WHERE id = ?', (str(data['task_name'] or '').strip(), task_id))
        if 'file_pattern' in data:
            try:
                file_pattern = _validate_file_pattern(data['file_pattern'])
            except ValueError as error:
                return jsonify({'success': False, 'error': str(error)}), 422
            conn.execute('UPDATE scheduled_tasks SET file_pattern = ? WHERE id = ?', (file_pattern, task_id))

        conn.commit()
    return jsonify({'success': True, 'message': '任务已更新'})

@system_legacy_bp.route('/api/scheduled_tasks/<int:task_id>', methods=['DELETE'])
def delete_scheduled_task(task_id):
    """删除定时任务"""
    with get_db() as conn:
        conn.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
        conn.commit()
    return jsonify({'success': True, 'message': '任务已删除'})

@system_legacy_bp.route('/api/scheduled_tasks/<int:task_id>/run', methods=['POST'])
def run_scheduled_task(task_id):
    """手动触发定时任务"""
    with get_db() as conn:
        row = conn.execute('SELECT id, task_name, cron_expr, file_pattern FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return jsonify({'error': '任务不存在'}), 404

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE scheduled_tasks SET last_run = ?, status = ? WHERE id = ?', (now_str, 'running', task_id))
        conn.commit()

        # 模拟执行
        try:
            pattern = row['file_pattern'] or '*.xlsx'
            matched_files = _scheduled_matches(pattern)
            if matched_files:
                from scripts.import_data import import_excel_file
                import_excel_file(matched_files[0])
            status = 'active'
            message = f'任务 "{row["task_name"]}" 执行完成'
        except Exception:
            current_app.logger.exception('Legacy scheduled task failed: %s', task_id)
            status = 'error'
            message = '任务执行失败，请检查导入任务配置和文件内容'

        next_run = _parse_cron_expr(row['cron_expr'])
        next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None
        conn.execute('UPDATE scheduled_tasks SET status = ?, next_run = ? WHERE id = ?', (status, next_run_str, task_id))
        conn.commit()

    return jsonify({'success': True, 'message': message})


# ==================== Feature 9: 商品批量打标签 ====================

