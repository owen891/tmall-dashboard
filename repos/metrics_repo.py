from db import get_db


class MetricsRepo:
    @staticmethod
    def get_product_daily_totals(start_date, end_date):
        with get_db() as connection:
            store_row = connection.execute(
                '''SELECT SUM(payment_amount) AS payment_amount,
                          SUM(successful_refund_amount) AS successful_refund_amount,
                          SUM(ad_spend) AS ad_spend,
                          MIN(date) AS data_start_date, MAX(date) AS data_end_date,
                          COUNT(*) AS fact_count
                   FROM store_daily_facts WHERE date BETWEEN ? AND ?''',
                (start_date, end_date),
            ).fetchone()
            if store_row['fact_count']:
                return dict(store_row)
            row = connection.execute(
                '''
                SELECT
                    SUM(payment_amount) AS payment_amount,
                    SUM(refund_amount) AS successful_refund_amount,
                    SUM(ad_spend) AS ad_spend,
                    MIN(date) AS data_start_date,
                    MAX(date) AS data_end_date,
                    COUNT(*) AS fact_count
                FROM daily_data
                WHERE date BETWEEN ? AND ?
                ''',
                (start_date, end_date),
            ).fetchone()
        return dict(row)

    @staticmethod
    def get_daily_matrix(start_date, end_date):
        with get_db() as connection:
            store_count = connection.execute(
                'SELECT COUNT(*) AS count FROM store_daily_facts WHERE date BETWEEN ? AND ?',
                (start_date, end_date),
            ).fetchone()['count']
            if store_count:
                rows = connection.execute(
                    '''SELECT date, payment_amount, successful_refund_amount,
                              ad_spend, product_visitors AS visitors,
                              payment_buyers AS buyers, 'store_daily_facts' AS data_source
                       FROM store_daily_facts WHERE date BETWEEN ? AND ? ORDER BY date''',
                    (start_date, end_date),
                ).fetchall()
            else:
                rows = connection.execute(
                '''SELECT date, SUM(payment_amount) AS payment_amount,
                          SUM(refund_amount) AS successful_refund_amount,
                          SUM(ad_spend) AS ad_spend,
                          SUM(ipv) AS visitors, SUM(buyers) AS buyers,
                          SUM(payment_qty) AS payment_qty,
                          GROUP_CONCAT(DISTINCT data_source) AS data_source
                   FROM daily_data WHERE date BETWEEN ? AND ?
                   GROUP BY date ORDER BY date''',
                    (start_date, end_date),
                ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            payment = float(item.get('payment_amount') or 0)
            refund = float(item.get('successful_refund_amount') or 0)
            visitors = float(item.get('visitors') or 0)
            buyers = float(item.get('buyers') or 0)
            item['net_sales'] = round(payment - refund, 2)
            item['refund_rate'] = round(refund / payment, 6) if payment else None
            item['payment_conversion_rate'] = round(buyers / visitors, 6) if visitors else None
            item['expense_ratio'] = round(float(item.get('ad_spend') or 0) / payment, 6) if payment else None
            item['average_order_value'] = round(payment / buyers, 2) if buyers else None
            result.append(item)
        return result

    @staticmethod
    def overview_context():
        with get_db() as connection:
            batch = connection.execute(
                '''SELECT source_filename, completed_at, quality_summary FROM import_batches
                   WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1'''
            ).fetchone()
            latest = connection.execute('SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM daily_data').fetchone()
        return {**dict(latest), 'latest_import': dict(batch) if batch else None}

    @staticmethod
    def action_todos():
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT id, product_id, action_type, planned_at, status,
                          CASE WHEN planned_at < date('now') AND status IN ('pending_execution','executing') THEN 1 ELSE 0 END AS overdue
                   FROM product_actions
                   WHERE status IN ('pending_execution', 'executing', 'pending_review')
                   ORDER BY overdue DESC,
                     CASE status WHEN 'pending_review' THEN 1 WHEN 'executing' THEN 2 ELSE 3 END,
                     planned_at ASC'''
            ).fetchall()
        return [dict(row) for row in rows]
