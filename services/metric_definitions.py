from collections import OrderedDict


def _ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) / float(denominator), 6)


METRIC_DEFINITIONS = OrderedDict([
    ('net_sales', ('payment_amount', 'successful_refund_amount')),
    ('refund_rate', ('successful_refund_amount', 'payment_amount')),
    ('payment_conversion_rate', ('payment_buyers', 'product_visitors')),
    ('average_order_value', ('payment_amount', 'payment_buyers')),
    ('expense_ratio', ('ad_spend', 'payment_amount')),
    ('ad_roi', ('attributed_payment_amount', 'ad_spend')),
    ('returning_buyer_ratio', ('returning_payment_buyers', 'payment_buyers')),
])


METRIC_METADATA = OrderedDict([
    ('net_sales', {
        'label': '\u51c0\u9500\u552e\u989d',
        'formula': 'payment_amount - successful_refund_amount',
        'unit': 'currency',
        'aggregation': 'sum_then_calculate',
    }),
    ('refund_rate', {
        'label': '\u9000\u6b3e\u7387',
        'formula': 'successful_refund_amount / payment_amount',
        'unit': 'ratio',
        'aggregation': 'sum_then_calculate',
    }),
    ('payment_conversion_rate', {
        'label': '\u652f\u4ed8\u8f6c\u5316\u7387',
        'formula': 'payment_buyers / product_visitors',
        'unit': 'ratio',
        'aggregation': 'sum_then_calculate',
    }),
    ('average_order_value', {
        'label': '\u5ba2\u5355\u4ef7',
        'formula': 'payment_amount / payment_buyers',
        'unit': 'currency',
        'aggregation': 'sum_then_calculate',
    }),
    ('expense_ratio', {
        'label': '\u8d39\u7528\u7387',
        'formula': 'ad_spend / payment_amount',
        'unit': 'ratio',
        'aggregation': 'sum_then_calculate',
    }),
    ('ad_roi', {
        'label': 'ROI',
        'formula': 'attributed_payment_amount / ad_spend',
        'unit': 'ratio',
        'aggregation': 'sum_then_calculate',
    }),
    ('returning_buyer_ratio', {
        'label': '\u8001\u5ba2\u5360\u6bd4',
        'formula': 'returning_payment_buyers / payment_buyers',
        'unit': 'ratio',
        'aggregation': 'sum_then_calculate',
    }),
])


def metric_metadata():
    """Return defensive metric metadata for catalogs and configuration surfaces."""
    return {
        name: {
            **metadata,
            'dependencies': list(METRIC_DEFINITIONS[name]),
        }
        for name, metadata in METRIC_METADATA.items()
    }


def _calculate(name, values):
    if name == 'net_sales':
        return round(float(values['payment_amount']) - float(values['successful_refund_amount']), 6)
    if name == 'refund_rate':
        return _ratio(values['successful_refund_amount'], values['payment_amount'])
    if name == 'payment_conversion_rate':
        return _ratio(values['payment_buyers'], values['product_visitors'])
    if name == 'average_order_value':
        return _ratio(values['payment_amount'], values['payment_buyers'])
    if name == 'expense_ratio':
        return _ratio(values['ad_spend'], values['payment_amount'])
    if name == 'ad_roi':
        return _ratio(values['attributed_payment_amount'], values['ad_spend'])
    if name == 'returning_buyer_ratio':
        return _ratio(values['returning_payment_buyers'], values['payment_buyers'])
    raise KeyError(name)


def derive_metrics(facts, names=None):
    selected = tuple(names or METRIC_DEFINITIONS)
    values = {name: None for name in selected}
    metric_availability = {}
    missing_fields = []

    for name in selected:
        dependencies = METRIC_DEFINITIONS[name]
        missing = [field for field in dependencies if facts.get(field) is None]
        for field in missing:
            if field not in missing_fields:
                missing_fields.append(field)
        if missing:
            metric_availability[name] = 'missing-fields'
            continue
        try:
            values[name] = _calculate(name, facts)
        except (TypeError, ValueError, ZeroDivisionError):
            metric_availability[name] = 'calculation-failed'
            continue
        metric_availability[name] = 'available' if values[name] is not None else 'insufficient-data'

    return {
        'values': values,
        'metric_availability': metric_availability,
        'missing_fields': missing_fields,
    }
