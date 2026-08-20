from datetime import date
import math
import re


TASK_STATUSES = {'todo', 'in_progress', 'done', 'completed', 'cancelled'}
TASK_PRIORITIES = {'P0', 'P1', 'P2', 'P3'}


def kpi_number(value, label, *, default=0.0):
    if value is None or value == '':
        value = default
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{label}必须是数字') from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f'{label}必须是大于等于 0 的有限数字')
    return number


def validate_kpi_fields(fields, *, partial=False):
    if not partial or 'user_name' in fields:
        if not str(fields.get('user_name') or '').strip():
            raise ValueError('KPI 负责人不能为空')
    if not partial or 'period' in fields:
        period = str(fields.get('period') or '')
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', period):
            raise ValueError('KPI 周期必须是 YYYY-MM')
    for field, label in (('target_gmv', '目标 GMV'), ('actual_gmv', '实际 GMV')):
        if not partial or field in fields:
            kpi_number(fields.get(field), label)
    if not partial or 'achievement_rate' in fields:
        rate = kpi_number(fields.get('achievement_rate'), '达成率')
        if rate > 1:
            raise ValueError('达成率必须在 0 到 1 之间')
    if not partial or 'rating' in fields:
        if str(fields.get('rating') or '') not in {'A', 'B', 'C', 'D'}:
            raise ValueError('评级必须是 A、B、C 或 D')


def validate_task_fields(fields, *, partial=False):
    if not partial or 'status' in fields:
        status = str(fields.get('status') or '')
        if status not in TASK_STATUSES:
            raise ValueError('status 必须是 todo、in_progress、done、completed 或 cancelled')
    if not partial or 'priority' in fields:
        priority = str(fields.get('priority') or '')
        if priority not in TASK_PRIORITIES:
            raise ValueError('priority 必须是 P0-P3')
    if not partial or 'due_date' in fields:
        due_date = str(fields.get('due_date') or '')
        if due_date:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', due_date):
                raise ValueError('due_date 必须是 YYYY-MM-DD')
            try:
                date.fromisoformat(due_date)
            except ValueError as error:
                raise ValueError('due_date 必须是 YYYY-MM-DD') from error
    for field in ('title', 'description', 'assignee'):
        if field in fields and len(str(fields.get(field) or '')) > 2000:
            raise ValueError(f'{field} 长度不能超过 2000 个字符')
    if 'title' in fields and not str(fields.get('title') or '').strip():
        raise ValueError('任务标题不能为空')
