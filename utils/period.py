from datetime import datetime, timedelta


def get_prev_period(period, dim):
    try:
        if dim == 'monthly':
            year, month = period.split('-')
            month = int(month) - 1
            if month == 0:
                return f'{int(year) - 1}-12'
            return f'{year}-{month:02d}'
        date = datetime.strptime(period, '%Y-%m-%d')
        date -= timedelta(days=7 if dim == 'weekly' else 1)
        return date.strftime('%Y-%m-%d')
    except (TypeError, ValueError, AttributeError):
        return period

