"""
KPI Service — KPI 聚合计算、环比、异常检测。

从 data_api.py 的 /api/kpi 路由提取业务逻辑。
路由层只负责 HTTP 参数提取，计算逻辑集中在此。
"""
from repos.data_repo import DataRepo
from utils.period import get_prev_period
from utils.format import fmt_wan, fmt_percent, calc_change_rate


class KpiService:

    @staticmethod
    def get_kpi_summary(dim, period):
        """
        KPI 概览 — 替代原 /api/kpi 路由中的计算逻辑。

        返回结构：
        {
            "payment_amount": {"value": 123456, "prev": 100000, "change": 0.23},
            "refund_amount": {...},
            "net_sales": {...},
            ...
        }
        """
        prev_period = get_prev_period(dim, period)
        data = DataRepo.get_kpi(dim, period, prev_period)

        cur = data['current']
        prev = data['previous']

        def build_kpi(current_val, prev_val):
            return {
                'value': current_val or 0,
                'prev': prev_val or 0,
                'change': calc_change_rate(current_val, prev_val),
            }

        return {
            'payment_amount': build_kpi(cur.total_payment, prev.total_payment),
            'refund_amount': build_kpi(cur.total_refund, prev.total_refund),
            'net_sales': build_kpi(cur.total_net, prev.total_net),
            'payment_qty': build_kpi(cur.total_qty, 0),
            'buyers': build_kpi(cur.total_buyers, 0),
            'period': period,
            'prev_period': prev_period,
        }

    @staticmethod
    def get_trend_data(dim, period, metric='payment_amount', limit=30):
        """趋势数据 — 替代原 /api/trend 路由"""
        return DataRepo.get_trend(dim, period, metric, limit)

    @staticmethod
    def detect_anomalies(dim, period):
        """
        异常检测 — 替代原 /api/anomalies 路由。

        检测逻辑：
        - 支付金额环比下降超过 20%
        - 退款率超过 15%
        - 转化率低于 1%
        - ROI 低于 1
        """
        prev_period = get_prev_period(dim, period)
        data = DataRepo.get_kpi(dim, period, prev_period)
        cur = data['current']
        prev = data['previous']

        anomalies = []

        # 支付金额下降
        if prev and prev.total_payment and cur and cur.total_payment:
            change = (cur.total_payment - prev.total_payment) / prev.total_payment
            if change < -0.20:
                anomalies.append({
                    'type': 'payment_drop',
                    'severity': 'danger',
                    'message': f'支付金额环比下降 {abs(change)*100:.1f}%',
                    'current': cur.total_payment,
                    'previous': prev.total_payment,
                })

        # 退款率
        if cur and cur.total_payment and cur.total_refund:
            refund_rate = cur.total_refund / cur.total_payment
            if refund_rate > 0.15:
                anomalies.append({
                    'type': 'high_refund',
                    'severity': 'warning',
                    'message': f'退款率 {refund_rate*100:.1f}%，超过 15% 阈值',
                    'current': refund_rate,
                })

        return anomalies
