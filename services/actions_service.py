from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from repos.actions_repo import ActionsRepo


class ActionValidationError(ValueError):
    pass


class ActionConflictError(ValueError):
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
        if payload['target_metric'] != 'payment_amount':
            raise ActionValidationError('当前仅支持 payment_amount 作为观察指标')
        observer_window_days = self._window_days(payload['observer_window_days'])
        planned_at = self._date_value(payload['planned_at'], '计划日期')
        action = {
            'id': uuid4().hex, 'action_group_id': payload.get('action_group_id'),
            'product_id': payload['product_id'], 'purpose_type': payload['purpose_type'],
            'purpose_note': payload['purpose_note'], 'action_type': payload['action_type'],
            'action_detail': payload['action_detail'], 'target_metric': payload['target_metric'],
            'expected_change': payload.get('expected_change'), 'status': 'draft',
            'planned_at': planned_at, 'observer_window_days': observer_window_days,
            'assigned_to': payload.get('assigned_to'),
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
            if item['target_metric'] != 'payment_amount':
                raise ActionValidationError('批量动作观察参数不合法')
            actions.append({
                'id': uuid4().hex, 'action_group_id': group_id, 'product_id': product_id,
                'purpose_type': item['purpose_type'], 'purpose_note': item['purpose_note'],
                'action_type': item['action_type'], 'action_detail': item['action_detail'],
                'target_metric': item['target_metric'], 'expected_change': item.get('expected_change'), 'status': 'draft',
                'planned_at': planned_at, 'observer_window_days': observer_window_days, 'assigned_to': item.get('assigned_to'),
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
            if len(before) != window or len(after) != window:
                ActionsRepo.update(action['id'], {
                    'calculation_note': (
                        f'观察窗口数据不完整：动作前 {len(before)}/{window} 天，'
                        f'动作后 {len(after)}/{window} 天；等待数据补齐后重新计算。'
                    ),
                }, expected_version=action['version'], operator='system', reason='观察窗口数据不足')
                continue
            before_value = sum(row['payment_amount'] for row in before) / window
            after_value = sum(row['payment_amount'] for row in after) / window
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
