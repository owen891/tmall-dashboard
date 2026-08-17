import math
import operator as comparison

from repos.alert_rules_repo import AlertRulesRepo
from repos.audit_repo import AuditRepo


class AlertRuleValidationError(ValueError):
    pass


class AlertRuleNotFoundError(LookupError):
    pass


SCOPES = {
    'store': {'gmv', 'net_sales', 'visitors', 'conversion', 'refund_rate', 'roi', 'ad_spend'},
    'promotion_product': {
        'roi', 'ad_spend', 'attributed_payment_amount', 'impressions', 'clicks',
        'ctr', 'payment_buyers', 'cvr', 'cpc', 'direct_payment_amount',
        'indirect_payment_amount', 'paid_share',
    },
}
OPERATORS = {'gt', 'lt', 'gte', 'lte'}
LEVELS = {'info', 'warning', 'danger'}
LEVEL_PRIORITY = {'info': 1, 'warning': 2, 'danger': 3}
COMPARATORS = {
    'gt': comparison.gt,
    'lt': comparison.lt,
    'gte': comparison.ge,
    'lte': comparison.le,
}


class AlertRulesService:
    def list(self, scope=None):
        if scope and scope not in SCOPES:
            raise AlertRuleValidationError('不支持的预警作用域')
        return [self._serialize(rule) for rule in AlertRulesRepo.list(scope=scope)]

    def create(self, payload):
        values = self._validate(payload, require_all=True)
        rule = AlertRulesRepo.create(values)
        AuditRepo.record(
            'alert_rule', rule['id'], 'create', payload.get('actor') or 'admin',
            payload.get('reason') or '创建预警规则', None, self._serialize(rule),
        )
        return self._serialize(rule)

    def update(self, rule_id, payload):
        current = AlertRulesRepo.get(rule_id)
        if not current:
            raise AlertRuleNotFoundError('预警规则不存在')
        merged = {**current, **payload}
        values = self._validate(merged, require_all=True)
        updated = AlertRulesRepo.update(rule_id, values)
        serialized = self._serialize(updated)
        AuditRepo.record(
            'alert_rule', rule_id, 'update', payload.get('actor') or 'admin',
            payload.get('reason') or '更新预警规则', self._serialize(current), serialized,
        )
        return serialized

    def delete(self, rule_id, actor='admin', reason='删除预警规则'):
        current = AlertRulesRepo.get(rule_id)
        if not current or not AlertRulesRepo.delete(rule_id):
            raise AlertRuleNotFoundError('预警规则不存在')
        AuditRepo.record(
            'alert_rule', rule_id, 'delete', actor or 'admin', reason or '删除预警规则',
            self._serialize(current), None,
        )

    def evaluate_promotion(self, rows):
        rules = AlertRulesRepo.list(scope='promotion_product', enabled=True)
        matches = {}
        for row in rows:
            identity = str(row.get('product_id') or row.get('unit_id') or row.get('campaign_id') or row.get('channel') or '')
            for rule in rules:
                value = row.get(rule['metric'])
                if value is None:
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(number) or not COMPARATORS[rule['operator']](number, float(rule['threshold'])):
                    continue
                key = (identity, rule['metric'])
                current = matches.get(key)
                if current and LEVEL_PRIORITY[current['severity']] >= LEVEL_PRIORITY[rule['level']]:
                    continue
                matches[key] = {
                    **{field: row.get(field) for field in ('channel', 'campaign_id', 'unit_id', 'product_id')},
                    'rule_id': rule['id'],
                    'rule_name': rule['name'],
                    'severity': rule['level'],
                    'title': row.get('title') or row.get('product_id') or row.get('channel') or '推广单元',
                    'message': self._message(rule, number),
                    'metric': rule['metric'],
                    'operator': rule['operator'],
                    'value': number,
                    'threshold': float(rule['threshold']),
                }
        return list(matches.values())

    def _validate(self, payload, require_all=False):
        required = {'name', 'scope', 'metric', 'operator', 'threshold', 'level'}
        if require_all and any(payload.get(key) in (None, '') for key in required):
            raise AlertRuleValidationError('请完整填写预警规则')
        scope = str(payload.get('scope', '')).strip()
        metric = str(payload.get('metric', '')).strip()
        operator_name = str(payload.get('operator', '')).strip()
        level = str(payload.get('level', '')).strip()
        if scope not in SCOPES:
            raise AlertRuleValidationError('不支持的预警作用域')
        if metric not in SCOPES[scope]:
            raise AlertRuleValidationError('当前作用域不支持该指标')
        if operator_name not in OPERATORS:
            raise AlertRuleValidationError('不支持的预警运算符')
        if level not in LEVELS:
            raise AlertRuleValidationError('不支持的预警级别')
        try:
            threshold = float(payload.get('threshold'))
        except (TypeError, ValueError) as error:
            raise AlertRuleValidationError('预警阈值必须是数字') from error
        if not math.isfinite(threshold):
            raise AlertRuleValidationError('预警阈值必须是有限数字')
        return {
            'name': str(payload.get('name', '')).strip(),
            'scope': scope,
            'metric': metric,
            'operator': operator_name,
            'threshold': threshold,
            'level': level,
            'enabled': bool(payload.get('enabled', True)),
        }

    @staticmethod
    def _serialize(rule):
        return {**rule, 'threshold': float(rule['threshold']), 'enabled': bool(rule['enabled'])}

    @staticmethod
    def _message(rule, value):
        symbols = {'gt': '>', 'lt': '<', 'gte': '>=', 'lte': '<='}
        return f"{rule['name']}：{rule['metric']} {value:.2f}，命中 {symbols[rule['operator']]} {float(rule['threshold']):.2f}"


alert_rules_service = AlertRulesService()
