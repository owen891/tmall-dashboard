"""
Alert Service — 预警规则引擎。

从 data_api.py 的 /api/alert_checks 路由提取。
根据 alert_rules 表中的规则，检查当前数据并生成预警。
"""
import json
from repos.alert_repo import AlertRepo
from repos.data_repo import DataRepo
from utils.period import get_prev_period


class AlertService:

    @staticmethod
    def check_all_rules(dim, period):
        """
        检查所有启用的预警规则 — 替代原 /api/alert_checks 路由。

        遍历 alert_rules，对每条规则查询当前数据，如果触发则创建预警记录。
        """
        rules = AlertRepo.list_rules(enabled_only=True)
        triggered = []

        for rule in rules:
            alert = AlertService._check_rule(rule, dim, period)
            if alert:
                triggered.append(alert)

        return triggered

    @staticmethod
    def _check_rule(rule, dim, period):
        """检查单条规则"""
        # 获取当前周期的指标值
        metric_value = AlertService._get_metric_value(rule.metric, dim, period)
        if metric_value is None:
            return None

        # 比较
        is_triggered = AlertService._compare(metric_value, rule.operator, rule.threshold)
        if not is_triggered:
            return None

        # 创建预警记录
        return AlertRepo.create_alert(
            alert_date=period,
            alert_type=rule.metric,
            severity=rule.level,
            title=f'{rule.metric} {rule.operator} {rule.threshold}',
            detail=f'当前值: {metric_value:.4f}, 阈值: {rule.threshold}',
            metric_name=rule.metric,
            current_value=metric_value,
            target_value=rule.threshold,
            period=period,
        )

    @staticmethod
    def _get_metric_value(metric, dim, period):
        """从数据层获取指标值"""
        prev_period = get_prev_period(dim, period)
        data = DataRepo.get_kpi(dim, period, prev_period)
        cur = data['current']
        if not cur:
            return None

        metric_map = {
            'payment_amount': cur.total_payment,
            'refund_amount': cur.total_refund,
            'net_sales': cur.total_net,
            'payment_qty': cur.total_qty,
            'buyers': cur.total_buyers,
        }
        return metric_map.get(metric)

    @staticmethod
    def _compare(value, operator, threshold):
        """比较运算"""
        ops = {
            'gt': lambda a, b: a > b,
            'lt': lambda a, b: a < b,
            'gte': lambda a, b: a >= b,
            'lte': lambda a, b: a <= b,
        }
        return ops.get(operator, lambda a, b: False)(value, threshold)

    @staticmethod
    def dismiss_alert(alert_id):
        """忽略预警"""
        AlertRepo.dismiss(alert_id)

    @staticmethod
    def get_alerts(dismissed=0, alert_type=None):
        """获取预警列表"""
        return AlertRepo.list_alerts(dismissed, alert_type)
