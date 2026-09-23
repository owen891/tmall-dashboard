"""Product operating segments shared by overview cards and product lists."""

from __future__ import annotations


PRODUCT_RULES = (
    {
        "key": "all_products",
        "name": "全部有效商品",
        "group": "经营范围",
        "description": "当前周期有可用经营事实的商品",
        "condition": "d.product_id IS NOT NULL",
        "metric": "product_fact",
        "severity": "info",
        "version": "2026.09",
        "rule_type": "segmentation",
        "metric_key": "product_fact",
        "conditions": [],
    },
    {
        "key": "high_refund",
        "name": "高退款风险",
        "group": "成本与风险",
        "description": "退款金额占支付金额达到 20% 以上",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.payment_amount, 0) > 0 AND COALESCE(d.refund_amount, 0) / d.payment_amount >= 0.20",
        "metric": "refund_rate",
        "severity": "warning",
        "version": "2026.09",
        "rule_type": "alert",
        "metric_key": "refund_rate",
        "conditions": [{"field": "refund_rate", "label": "退款率", "operator": ">=", "value": 0.20, "unit": "%"}],
    },
    {
        "key": "high_paid_high_refund",
        "name": "高付费高退款",
        "group": "成本与风险",
        "description": "推广费比达到 30% 且退款率达到 20% 以上",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.payment_amount, 0) > 0 AND COALESCE(d.ad_spend, 0) / d.payment_amount >= 0.30 AND COALESCE(d.refund_amount, 0) / d.payment_amount >= 0.20",
        "metric": "expense_ratio_and_refund_rate",
        "severity": "danger",
        "version": "2026.09",
        "rule_type": "diagnosis",
        "metric_key": "expense_ratio_and_refund_rate",
        "conditions": [
            {"field": "expense_ratio", "label": "费比", "operator": ">=", "value": 0.30, "unit": "%"},
            {"field": "refund_rate", "label": "退款率", "operator": ">=", "value": 0.20, "unit": "%"},
        ],
    },
    {
        "key": "high_expense",
        "name": "高费比商品",
        "group": "成本与风险",
        "description": "推广费比达到 30% 以上",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.payment_amount, 0) > 0 AND COALESCE(d.ad_spend, 0) / d.payment_amount >= 0.30",
        "metric": "expense_ratio",
        "severity": "warning",
        "version": "2026.09",
        "rule_type": "alert",
        "metric_key": "expense_ratio",
        "conditions": [{"field": "expense_ratio", "label": "费比", "operator": ">=", "value": 0.30, "unit": "%"}],
    },
    {
        "key": "low_conversion",
        "name": "低转化商品",
        "group": "流量与转化",
        "description": "有访客且支付转化率低于 2%",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.visitors, d.ipv, 0) >= 100 AND COALESCE(d.payment_conversion, 0) < 0.02",
        "metric": "payment_conversion",
        "severity": "warning",
        "version": "2026.09",
        "rule_type": "alert",
        "metric_key": "payment_conversion_rate",
        "conditions": [
            {"field": "product_visitors", "label": "商品访客数", "operator": ">=", "value": 100, "unit": "人"},
            {"field": "payment_conversion_rate", "label": "支付转化率", "operator": "<", "value": 0.02, "unit": "%"},
        ],
    },
    {
        "key": "high_cart_zero_paid",
        "name": "高加购零付费",
        "group": "流量与转化",
        "description": "加购率达到 10% 且没有推广花费",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.cart_rate, 0) >= 0.10 AND COALESCE(d.ad_spend, 0) = 0",
        "metric": "cart_rate_and_ad_spend",
        "severity": "info",
        "version": "2026.09",
        "rule_type": "recommendation",
        "metric_key": "cart_rate_and_ad_spend",
        "conditions": [
            {"field": "cart_rate", "label": "加购率", "operator": ">=", "value": 0.10, "unit": "%"},
            {"field": "ad_spend", "label": "推广花费", "operator": "=", "value": 0, "unit": "元"},
        ],
    },
    {
        "key": "high_aov",
        "name": "高客单价商品",
        "group": "价格带",
        "description": "客单价达到 200 元以上",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.avg_order_value, 0) >= 200",
        "metric": "avg_order_value",
        "severity": "info",
        "version": "2026.09",
        "rule_type": "segmentation",
        "metric_key": "average_order_value",
        "conditions": [{"field": "average_order_value", "label": "客单价", "operator": ">=", "value": 200, "unit": "元"}],
    },
    {
        "key": "low_aov",
        "name": "低客单价商品",
        "group": "价格带",
        "description": "客单价不高于 50 元",
        "condition": "d.product_id IS NOT NULL AND COALESCE(d.avg_order_value, 0) > 0 AND d.avg_order_value <= 50",
        "metric": "avg_order_value",
        "severity": "info",
        "version": "2026.09",
        "rule_type": "segmentation",
        "metric_key": "average_order_value",
        "conditions": [
            {"field": "average_order_value", "label": "客单价", "operator": ">", "value": 0, "unit": "元"},
            {"field": "average_order_value", "label": "客单价", "operator": "<=", "value": 50, "unit": "元"},
        ],
    },
)

RULES_BY_KEY = {item["key"]: item for item in PRODUCT_RULES}


RULE_EVALUATIONS = {
    "all_products": {
        "requirements": (),
        "checks": (),
    },
    "high_refund": {
        "requirements": ("payment_amount", "refund_amount"),
        "checks": (("refund_rate", ">=", 0.20, "退款率"),),
    },
    "high_paid_high_refund": {
        "requirements": ("payment_amount", "ad_spend", "refund_amount"),
        "checks": (
            ("expense_ratio", ">=", 0.30, "费比"),
            ("refund_rate", ">=", 0.20, "退款率"),
        ),
    },
    "high_expense": {
        "requirements": ("payment_amount", "ad_spend"),
        "checks": (("expense_ratio", ">=", 0.30, "费比"),),
    },
    "low_conversion": {
        "requirements": ("product_visitors", "payment_buyers"),
        "checks": (
            ("product_visitors", ">=", 100, "商品访客数"),
            ("payment_conversion_rate", "<", 0.02, "支付转化率"),
        ),
    },
    "high_cart_zero_paid": {
        "requirements": ("cart_rate", "ad_spend"),
        "checks": (("cart_rate", ">=", 0.10, "加购率"), ("ad_spend", "=", 0, "推广花费")),
    },
    "high_aov": {
        "requirements": ("average_order_value",),
        "checks": (("average_order_value", ">=", 200, "客单价"),),
    },
    "low_aov": {
        "requirements": ("average_order_value",),
        "checks": (("average_order_value", ">", 0, "客单价"), ("average_order_value", "<=", 50, "客单价")),
    },
}


def _compare(value, operator, threshold):
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "=":
        return value == threshold
    if operator == ">":
        return value > threshold
    if operator == "<=":
        return value <= threshold
    raise ValueError(f"unsupported rule operator: {operator}")


def evaluate_rule(rule_key, metrics, *, has_facts=True):
    """Evaluate a registered product rule without synthesizing missing inputs."""
    rule = get_rule(rule_key)
    if not rule:
        return None
    if rule_key == "all_products":
        return {
            "status": "matched" if has_facts else "not-computable",
            "matched": bool(has_facts),
            "missing_fields": [] if has_facts else ["product_fact"],
            "matched_fields": [],
        }
    definition = RULE_EVALUATIONS.get(rule_key, {})
    missing = [key for key in definition.get("requirements", ()) if metrics.get(key) is None]
    if missing:
        return {"status": "not-computable", "matched": False, "missing_fields": missing, "matched_fields": []}
    matched_fields = []
    checks = []
    matched = True
    for key, operator, threshold, label in definition.get("checks", ()):
        value = metrics.get(key)
        check = value is not None and _compare(float(value), operator, threshold)
        item = {"key": key, "label": label, "value": value, "threshold": threshold, "operator": operator, "matched": check}
        checks.append(item)
        if check:
            matched_fields.append(item)
        else:
            matched = False
    return {
        "status": "matched" if matched else "not-matched",
        "matched": matched,
        "missing_fields": [],
        "matched_fields": matched_fields,
        "checks": checks,
    }


def list_rules():
    """Return serializable rule metadata for the UI and audits."""
    return [dict(item) for item in PRODUCT_RULES]


def get_rule(rule_key):
    if not rule_key:
        return None
    return RULES_BY_KEY.get(str(rule_key))


def condition_for(rule_key):
    rule = get_rule(rule_key)
    return rule["condition"] if rule else None


def condition_for_dimension(rule_key, dimension):
    condition = condition_for(rule_key)
    if not condition:
        return None
    return condition.replace("d.visitors", "d.ipv") if dimension != "monthly" else condition
