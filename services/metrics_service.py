def _ratio(numerator, denominator):
    if denominator in (None, 0):
        return None
    return round(numerator / denominator, 6)


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
                'refund_rate': None,
                'expense_ratio': None,
                'payment_conversion_rate': None,
                'average_order_value': None,
                'returning_buyer_ratio': None,
                'metric_availability': {},
            },
        }

    payment_amount = float(totals['payment_amount'] or 0)
    refund_amount = float(totals['successful_refund_amount'] or 0)
    ad_spend = float(totals['ad_spend'] or 0)
    unavailable = {
        'payment_conversion_rate': 'missing-fields',
        'average_order_value': 'missing-fields',
        'returning_buyer_ratio': 'missing-fields',
    }
    return {
        'availability': 'insufficient-data',
        'data': {
            'start_date': start_date,
            'end_date': end_date,
            'data_cutoff_date': totals['data_end_date'],
            'payment_amount': payment_amount,
            'successful_refund_amount': refund_amount,
            'net_sales': payment_amount - refund_amount,
            'ad_spend': ad_spend,
            'refund_rate': _ratio(refund_amount, payment_amount),
            'expense_ratio': _ratio(ad_spend, payment_amount),
            'payment_conversion_rate': None,
            'average_order_value': None,
            'returning_buyer_ratio': None,
            'metric_availability': unavailable,
        },
    }
