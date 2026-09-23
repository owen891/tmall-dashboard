import calendar
import math
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from repos.actions_repo import ActionsRepo


class ActionValidationError(ValueError):
    pass


class ActionConflictError(ValueError):
    pass


class ActionNotFoundError(ValueError):
    pass


TRANSITIONS = {
    'draft': {'pending_execution', 'cancelled'},
    'pending_execution': {'executing', 'blocked', 'cancelled'},
    'executing': {'observing', 'blocked', 'cancelled'},
    'observing': {'pending_review', 'blocked', 'calculation_failed'},
    'pending_review': {'blocked'},
    'blocked': {'pending_execution', 'cancelled'},
    'calculation_failed': {'observing', 'blocked'},
    'completed': {'pending_review'}, 'cancelled': set(),
}


class ActionsService:
    SUPPORTED_METRICS = {'payment_amount', 'visitors', 'conversion', 'aov', 'ad_roi', 'refund_rate'}

    @classmethod
    def _validate_metric(cls, value):
        metric = str(value or '').strip()
        if metric not in cls.SUPPORTED_METRICS:
            raise ActionValidationError('目标指标不受支持')
        return metric

    @staticmethod
    def _target_value(value):
        if value is None or value == '':
            return None
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ActionValidationError('目标值必须是数字') from error
        if not math.isfinite(number):
            raise ActionValidationError('目标值必须是有限数字')
        return number

    @staticmethod
    def _month_bounded_week_key(day):
        first = date(day.year, day.month, 1)
        first_week_end = first + timedelta(days=6 - first.weekday())
        if day <= first_week_end:
            week_num = 1
        else:
            week_num = 2 + (day.day - first_week_end.day - 1) // 7
        return f'{day.year:04d}-{day.month:02d}-W{week_num}'

    @staticmethod
    def _next_period(period_type, period_key):
        period_type = str(period_type or '').strip()
        period_key = str(period_key or '').strip()
        try:
            if period_type == 'week' and len(period_key) == 10 and period_key[4] == '-' and period_key[7] == '-' and period_key[8] == 'W':
                year, month, week_num = int(period_key[:4]), int(period_key[5:7]), int(period_key[9:])
                first = date(year, month, 1)
                last = date(year, month, calendar.monthrange(year, month)[1])
                first_week_end = min(first + timedelta(days=6 - first.weekday()), last)
                max_week_num = int(ActionsService._month_bounded_week_key(last)[-1:])
                if week_num < 1 or week_num > max_week_num:
                    return None, None
                period_end = first_week_end if week_num == 1 else min(first_week_end + timedelta(days=7 * (week_num - 1)), last)
                return period_type, ActionsService._month_bounded_week_key(period_end + timedelta(days=1))
            if period_type == 'week' and len(period_key) == 8 and period_key[4] == '-':
                year, week = int(period_key[:4]), int(period_key[-2:])
                iso = (date.fromisocalendar(year, week, 1) + timedelta(days=7)).isocalendar()
                return period_type, f'{iso.year:04d}-W{iso.week:02d}'
            if period_type == 'month' and len(period_key) == 7 and period_key[4] == '-':
                year, month = int(period_key[:4]), int(period_key[-2:])
                if month == 12:
                    year, month = year + 1, 1
                else:
                    month += 1
                return period_type, f'{year:04d}-{month:02d}'
        except (TypeError, ValueError):
            return None, None
        return None, None

    @staticmethod
    def _window_days(value):
        if isinstance(value, bool):
            raise ActionValidationError('观察窗口必须是正整数')
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise ActionValidationError('观察窗口必须是正整数') from error
        if number < 1 or number > 365 or str(value).strip() != str(number):
            raise ActionValidationError('观察窗口必须是 1 到 365 天的正整数')
        return number

    @staticmethod
    def _date_value(value, label):
        text = str(value or '').strip()
        try:
            date.fromisoformat(text)
        except (TypeError, ValueError) as error:
            raise ActionValidationError(f'{label}必须是 YYYY-MM-DD') from error
        return text

    @staticmethod
    def _boolean(value, label):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {'true', 'false'}:
            return value.strip().lower() == 'true'
        if isinstance(value, int) and value in {0, 1}:
            return bool(value)
        raise ActionValidationError(f'{label}必须是布尔值')

    def create(self, payload):
        required = ('product_id', 'purpose_type', 'purpose_note', 'action_type', 'action_detail',
                    'target_metric', 'planned_at', 'observer_window_days')
        missing = [name for name in required if not payload.get(name)]
        if missing:
            raise ActionValidationError(f'缺少必填字段：{", ".join(missing)}')
        target_metric = self._validate_metric(payload['target_metric'])
        observer_window_days = self._window_days(payload['observer_window_days'])
        planned_at = self._date_value(payload['planned_at'], '计划日期')
        source_period_type = payload.get('source_period_type')
        source_period_key = payload.get('source_period_key') or payload.get('source_period')
        verification_period_type = payload.get('verification_period_type')
        verification_period_key = payload.get('verification_period_key')
        if not verification_period_type or not verification_period_key:
            verification_period_type, verification_period_key = self._next_period(source_period_type, source_period_key)
        action = {
            'id': uuid4().hex, 'action_group_id': payload.get('action_group_id'),
            'product_id': payload['product_id'], 'purpose_type': payload['purpose_type'],
            'purpose_note': payload['purpose_note'], 'action_type': payload['action_type'],
            'action_detail': payload['action_detail'], 'target_metric': target_metric,
            'expected_change': payload.get('expected_change'), 'target_value': self._target_value(payload.get('target_value')),
            'acceptance_criteria': payload.get('acceptance_criteria'), 'status': 'draft',
            'planned_at': planned_at, 'observer_window_days': observer_window_days,
            'assigned_to': payload.get('assigned_to'),
            'source_rule_key': payload.get('source_rule_key'),
            'source_rule_name': payload.get('source_rule_name'),
            'source_period': payload.get('source_period'),
            'source_category_mode': payload.get('source_category_mode'),
            'source_period_type': source_period_type,
            'source_period_key': source_period_key,
            'source_compare_mode': payload.get('source_compare_mode'),
            'source_compare_period_key': payload.get('source_compare_period_key'),
            'source_product_id': payload.get('source_product_id') or payload.get('product_id'),
            'source_problem_key': payload.get('source_problem_key') or payload.get('source_rule_key'),
            'source_diagnosis_snapshot': payload.get('source_diagnosis_snapshot'),
            'verification_period_type': verification_period_type,
            'verification_period_key': verification_period_key,
        }
        ActionsRepo.create(action, payload.get('operator'), payload.get('reason'))
        return ActionsRepo.get(action['id'])

    def create_batch(self, payload):
        product_ids = payload.get('product_ids')
        if not isinstance(product_ids, list) or not product_ids:
            raise ActionValidationError('批量创建必须提供 product_ids')
        group_id = payload.get('action_group_id') or uuid4().hex
        actions = []
        for product_id in product_ids:
            item = {**payload, 'product_id': product_id, 'action_group_id': group_id}
            required = ('product_id', 'purpose_type', 'purpose_note', 'action_type', 'action_detail', 'target_metric', 'planned_at', 'observer_window_days')
            if any(not item.get(name) for name in required):
                raise ActionValidationError('批量动作缺少必填字段')
            observer_window_days = self._window_days(item['observer_window_days'])
            planned_at = self._date_value(item['planned_at'], '计划日期')
            target_metric = self._validate_metric(item['target_metric'])
            verification_period_type = item.get('verification_period_type')
            verification_period_key = item.get('verification_period_key')
            if not verification_period_type or not verification_period_key:
                verification_period_type, verification_period_key = self._next_period(
                    item.get('source_period_type'), item.get('source_period_key') or item.get('source_period')
                )
            actions.append({
                'id': uuid4().hex, 'action_group_id': group_id, 'product_id': product_id,
                'purpose_type': item['purpose_type'], 'purpose_note': item['purpose_note'],
                'action_type': item['action_type'], 'action_detail': item['action_detail'],
                'target_metric': target_metric, 'expected_change': item.get('expected_change'),
                'target_value': self._target_value(item.get('target_value')),
                'acceptance_criteria': item.get('acceptance_criteria'), 'status': 'draft',
                'planned_at': planned_at, 'observer_window_days': observer_window_days, 'assigned_to': item.get('assigned_to'),
                'source_period_type': item.get('source_period_type'),
                'source_period_key': item.get('source_period_key') or item.get('source_period'),
                'source_compare_mode': item.get('source_compare_mode'),
                'source_compare_period_key': item.get('source_compare_period_key'),
                'source_product_id': item.get('source_product_id') or product_id,
                'source_problem_key': item.get('source_problem_key') or item.get('source_rule_key'),
                'source_diagnosis_snapshot': item.get('source_diagnosis_snapshot'),
                'verification_period_type': verification_period_type,
                'verification_period_key': verification_period_key,
            })
        ActionsRepo.create_many(actions, payload.get('operator'), payload.get('reason'))
        return {'action_group_id': group_id, 'actions': [ActionsRepo.get(action['id']) for action in actions]}

    def transition(self, action_id, target, payload):
        action = ActionsRepo.get(action_id)
        if not action:
            raise ActionValidationError('动作不存在')
        if payload.get('version') != action['version']:
            raise ActionConflictError('动作版本已更新，请刷新后重试')
        if target == 'completed':
            raise ActionValidationError('动作必须通过复盘接口完成')
        if target not in TRANSITIONS.get(action['status'], set()):
            raise ActionConflictError(f'不允许从 {action["status"]} 转为 {target}')
        values = {'status': target, 'version': action['version'] + 1}
        if action['status'] == 'completed' and target == 'pending_review':
            values['calculation_note'] = '动作已重开，保留原结果和复盘，等待重新确认。'
        if target == 'blocked':
            if not payload.get('blocked_reason') or not payload.get('expected_recovery_at'):
                raise ActionValidationError('阻塞必须填写原因和预计恢复时间')
            recovery_at = self._date_value(payload['expected_recovery_at'], '预计恢复日期')
            values.update({'blocked_reason': payload['blocked_reason'], 'expected_recovery_at': recovery_at})
        if target == 'observing':
            values['executed_at'] = self._date_value(payload.get('executed_at') or action['planned_at'], '执行日期')
        if not ActionsRepo.update(
            action_id, values, expected_version=action['version'],
            operator=payload.get('operator'), reason=payload.get('reason'),
        ):
            raise ActionConflictError('动作版本已更新，请刷新后重试')
        return ActionsRepo.get(action_id)

    def delete(self, action_id, payload):
        action = ActionsRepo.get(action_id)
        if not action:
            raise ActionNotFoundError('动作不存在')
        if payload.get('version') != action['version']:
            raise ActionConflictError('动作版本已更新，请刷新后重试')
        if action['status'] not in {'draft', 'pending_execution', 'blocked'}:
            raise ActionConflictError(f'当前状态（{action["status"]}）不允许删除动作')
        if not ActionsRepo.delete(
            action_id, expected_version=action['version'], operator=payload.get('operator'),
            reason=payload.get('reason') or '删除运营动作',
        ):
            raise ActionConflictError('动作版本已更新，请刷新后重试')
        return {'id': action_id, 'deleted_count': 1}

    def recalculate(self):
        updated = []
        for action in ActionsRepo.observing():
            try:
                executed = date.fromisoformat(action['executed_at'] or action['planned_at'])
            except (TypeError, ValueError):
                if ActionsRepo.update(action['id'], {
                    'status': 'calculation_failed',
                    'calculation_note': '执行日期格式无效，无法计算观察窗口。',
                    'version': action['version'] + 1,
                }, expected_version=action['version'], operator='system', reason='观察窗口日期无效'):
                    updated.append(ActionsRepo.get(action['id']))
                continue
            window = action['observer_window_days']
            before_start = executed - timedelta(days=window)
            before_end = executed - timedelta(days=1)
            after_start = executed + timedelta(days=1)
            after_end = executed + timedelta(days=window)
            before = ActionsRepo.metric_window(action['product_id'], before_start.isoformat(), before_end.isoformat(), action['target_metric'])
            after = ActionsRepo.metric_window(action['product_id'], after_start.isoformat(), after_end.isoformat(), action['target_metric'])
            if before is None or after is None:
                ActionsRepo.update(action['id'], {
                    'status': 'calculation_failed',
                    'calculation_note': '目标指标不受当前数据表支持，无法回算，请修改动作指标后重试',
                    'version': action['version'] + 1,
                }, expected_version=action['version'], operator='system', reason='目标指标不支持')
                updated.append(ActionsRepo.get(action['id']))
                continue
            if len(before) != window or len(after) != window:
                ActionsRepo.update(action['id'], {
                    'calculation_note': (
                        f'观察窗口数据不完整：动作前 {len(before)}/{window} 天，'
                        f'动作后 {len(after)}/{window} 天；等待数据补齐后重新计算。'
                    ),
                }, expected_version=action['version'], operator='system', reason='观察窗口数据不足')
                continue
            if any(row.get('metric_value') is None for row in [*before, *after]):
                ActionsRepo.update(action['id'], {
                    'calculation_note': '观察窗口存在无法计算的指标值，等待补数后重新计算',
                }, expected_version=action['version'], operator='system', reason='观察指标值缺失')
                continue
            before_value = sum(float(row['metric_value']) for row in before) / window
            after_value = sum(float(row['metric_value']) for row in after) / window
            if not ActionsRepo.update(action['id'], {
                'status': 'pending_review', 'before_metric_value': before_value,
                'after_metric_value': after_value, 'result_change': after_value - before_value,
                'calculation_note': f'动作前后各 {window} 天完整覆盖，按日均支付金额计算',
                'version': action['version'] + 1,
            }, expected_version=action['version'], operator='system', reason='自动回算观察窗口'):
                continue
            updated.append(ActionsRepo.get(action['id']))
        return {'updated_count': len(updated), 'actions': updated}

    def review(self, action_id, payload):
        action = ActionsRepo.get(action_id)
        if not action or action['status'] != 'pending_review':
            raise ActionConflictError('只有待复盘动作可以提交复盘')
        if payload.get('version') != action['version']:
            raise ActionConflictError('动作版本已更新，请刷新后重试')
        required = ('effective', 'reason', 'conclusion', 'next_action', 'reviewer')
        missing = [name for name in required if payload.get(name) is None or payload.get(name) == '']
        if missing:
            raise ActionValidationError(f'缺少复盘字段：{", ".join(missing)}')
        if not ActionsRepo.update(action_id, {
            'status': 'completed', 'review_effective': int(self._boolean(payload['effective'], '复盘是否有效')),
            'review_reason': payload['reason'], 'review_conclusion': payload['conclusion'],
            'review_next_action': payload['next_action'], 'reviewed_by': payload['reviewer'],
            'reviewed_at': datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(), 'version': action['version'] + 1,
        }, expected_version=action['version'], operator=payload.get('operator') or payload.get('reviewer'),
           reason=payload.get('audit_reason') or payload.get('reason') or '提交动作复盘'):
            raise ActionConflictError('动作版本已更新，请刷新后重试')
        return ActionsRepo.get(action_id)

    def history(self, action_id):
        if not ActionsRepo.get(action_id):
            raise ActionValidationError('动作不存在')
        return ActionsRepo.history(action_id)


actions_service = ActionsService()
