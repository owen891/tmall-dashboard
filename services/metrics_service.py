from services.metric_definitions import derive_metrics


def build_overview(totals, start_date, end_date):
    if not totals['fact_count']:
        return {
            'availability': 'no-data',
            'data': {
                'start_date': start_date,
                'end_date': end_date,
                'data_cutoff_date': None,
                'payment_amount': None,
                'successful_refund_amount': None,
                'net_sales': None,
                'ad_spend': None,
                'visitors': None,
                'refund_rate': None,
                'expense_ratio': None,
                'payment_conversion_rate': None,
                'average_order_value': None,
                'returning_buyer_ratio': None,
                'metric_availability': {},
                'missing_fields': [],
                'data_grain': totals.get('data_grain'),
                'fallback_reason': totals.get('fallback_reason'),
                'fact_count': totals.get('fact_count', 0),
            },
        }

    payment_amount = None if totals['payment_amount'] is None else float(totals['payment_amount'])
    refund_amount = None if totals['successful_refund_amount'] is None else float(totals['successful_refund_amount'])
    ad_spend = None if totals['ad_spend'] is None else float(totals['ad_spend'])
    metric_names = (
        'net_sales', 'refund_rate', 'payment_conversion_rate',
        'average_order_value', 'expense_ratio', 'returning_buyer_ratio',
    )
    if totals.get('attributed_payment_amount') is not None:
        metric_names += ('ad_roi',)
    derived_result = derive_metrics({
        'payment_amount': payment_amount,
        'successful_refund_amount': refund_amount,
        'product_visitors': totals.get('product_visitors'),
        'payment_buyers': totals.get('payment_buyers'),
        'returning_payment_buyers': totals.get('returning_payment_buyers'),
        'ad_spend': ad_spend,
        'attributed_payment_amount': totals.get('attributed_payment_amount'),
    }, names=metric_names)
    derived = derived_result['values']
    unavailable = {
        key: state for key, state in derived_result['metric_availability'].items()
        if state != 'available'
    }
    return {
        'availability': 'available' if not unavailable else 'insufficient-data',
        'data': {
            'start_date': start_date,
            'end_date': end_date,
            'data_cutoff_date': totals['data_end_date'],
            'payment_amount': payment_amount,
            'successful_refund_amount': refund_amount,
            'ad_spend': ad_spend,
            'visitors': totals.get('product_visitors'),
            **derived,
            'metric_availability': derived_result['metric_availability'],
            'missing_fields': derived_result['missing_fields'],
            'data_grain': totals.get('data_grain'),
            'fallback_reason': totals.get('fallback_reason'),
            'fact_count': totals.get('fact_count', 0),
        },
    }
