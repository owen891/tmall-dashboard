from db import get_db, get_shop_id


class MetricsRepo:
    @staticmethod
    def _product_filter_sql(filters):
        filters = filters or {}
        clauses = []
        params = []
        if filters.get('product_id'):
            clauses.append('d.product_id = ?'); params.append(filters['product_id'])
        if filters.get('tier'):
            clauses.append('p.tier = ?'); params.append(filters['tier'])
        if filters.get('lifecycle_stage'):
            clauses.append("COALESCE(lp.manual_stage, lp.recommended_stage, '') = ?")
            params.append(filters['lifecycle_stage'])
        if filters.get('promotion_channel'):
            clauses.append('''EXISTS (SELECT 1 FROM promotion_daily_facts pf
                               WHERE pf.shop_id = d.shop_id AND pf.date = d.date AND pf.product_id = d.product_id
                                 AND pf.channel = ?)''')
            params.append(filters['promotion_channel'])
        return clauses, params

    @staticmethod
    def get_product_daily_totals(start_date, end_date, filters=None):
        shop_id = get_shop_id()
        with get_db() as connection:
            filters = {key: value for key, value in (filters or {}).items() if value}
            store_row = connection.execute(
                '''SELECT SUM(payment_amount) AS payment_amount,
                          SUM(successful_refund_amount) AS successful_refund_amount,
                          SUM(ad_spend) AS ad_spend,
                          SUM(product_visitors) AS product_visitors,
                          SUM(payment_buyers) AS payment_buyers,
                          SUM(returning_payment_buyers) AS returning_payment_buyers,
                          MIN(date) AS data_start_date, MAX(date) AS data_end_date,
                          COUNT(*) AS fact_count
                   FROM store_daily_facts WHERE shop_id = ? AND date BETWEEN ? AND ?''',
                (shop_id, start_date, end_date),
            ).fetchone()
            if store_row['fact_count'] and not filters:
                return dict(store_row)
            clauses, filter_params = MetricsRepo._product_filter_sql(filters)
            where = ' AND '.join(['d.shop_id = ?', 'd.date BETWEEN ? AND ?', *clauses])
            row = connection.execute(
                '''
                SELECT
                    SUM(d.payment_amount) AS payment_amount,
                    SUM(d.refund_amount) AS successful_refund_amount,
                    SUM(d.ad_spend) AS ad_spend,
                    NULL AS product_visitors,
                    NULL AS payment_buyers,
                    NULL AS returning_payment_buyers,
                    MIN(d.date) AS data_start_date,
                    MAX(d.date) AS data_end_date,
                    COUNT(*) AS fact_count
                FROM daily_data d
                JOIN products p ON p.product_id = d.product_id
                LEFT JOIN lifecycle_profiles lp ON lp.product_id = d.product_id
                WHERE ''' + where,
                [shop_id, start_date, end_date, *filter_params],
            ).fetchone()
        return dict(row)

    @staticmethod
    def get_daily_matrix(start_date, end_date, filters=None):
        shop_id = get_shop_id()
        with get_db() as connection:
            filters = {key: value for key, value in (filters or {}).items() if value}
            store_count = connection.execute(
                'SELECT COUNT(*) AS count FROM store_daily_facts WHERE shop_id = ? AND date BETWEEN ? AND ?',
                (shop_id, start_date, end_date),
            ).fetchone()['count']
            if store_count and not filters:
                rows = connection.execute(
                    '''SELECT f.date, f.payment_amount, f.successful_refund_amount,
                              ad_spend, product_visitors AS visitors,
                              payment_buyers AS buyers, returning_payment_buyers,
                              f.source_batch_id, 'store_daily_facts' AS data_source,
                              b.source_type, b.source_filename, b.completed_at, b.quality_summary
                       FROM store_daily_facts f LEFT JOIN import_batches b ON b.id = f.source_batch_id
                       WHERE f.shop_id = ? AND f.date BETWEEN ? AND ? ORDER BY f.date''',
                    (shop_id, start_date, end_date),
                ).fetchall()
            else:
                clauses, filter_params = MetricsRepo._product_filter_sql(filters)
                where = ' AND '.join(['d.shop_id = ?', 'd.date BETWEEN ? AND ?', *clauses])
                rows = connection.execute(
                '''WITH source_meta AS (
                       SELECT shop_id, product_id, date, source_filename,
                              source_batch_id, source_type,
                              ROW_NUMBER() OVER (
                                  PARTITION BY shop_id, product_id, date, source_filename
                                  ORDER BY observed_at DESC, id DESC
                              ) AS source_rank
                       FROM daily_data_observations
                   )
                   SELECT d.date, SUM(d.payment_amount) AS payment_amount,
                          SUM(d.refund_amount) AS successful_refund_amount,
                          SUM(d.ad_spend) AS ad_spend,
                          SUM(d.ipv) AS visitors, SUM(d.buyers) AS buyers,
                          SUM(d.returning_payment_buyers) AS returning_payment_buyers,
                          SUM(d.payment_qty) AS payment_qty,
                          GROUP_CONCAT(DISTINCT d.data_source) AS data_source,
                          GROUP_CONCAT(DISTINCT d.data_source) AS source_filename,
                          GROUP_CONCAT(DISTINCT sm.source_batch_id) AS source_batch_id,
                          GROUP_CONCAT(DISTINCT sm.source_type) AS source_type,
                          MAX(b.completed_at) AS completed_at,
                          MAX(b.quality_summary) AS quality_summary
                   FROM daily_data d JOIN products p ON p.product_id = d.product_id
                   LEFT JOIN lifecycle_profiles lp ON lp.product_id = d.product_id
                   LEFT JOIN source_meta sm
                     ON sm.shop_id = d.shop_id AND sm.product_id = d.product_id
                    AND sm.date = d.date AND sm.source_filename = d.data_source
                    AND sm.source_rank = 1
                   LEFT JOIN import_batches b ON b.id = sm.source_batch_id
                   WHERE ''' + where + ''' GROUP BY d.date ORDER BY d.date''',
                    [shop_id, start_date, end_date, *filter_params],
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
            returning = item.get('returning_payment_buyers')
            item['returning_buyer_ratio'] = round(float(returning) / buyers, 6) if returning is not None and buyers else None
            item['source_detail'] = {key: item.get(key) for key in ('source_batch_id', 'source_type', 'source_filename', 'completed_at', 'quality_summary') if item.get(key) is not None}
            result.append(item)
        previous = None
        for item in result:
            changes = {}
            if previous:
                for metric in ('payment_amount', 'net_sales', 'refund_rate', 'expense_ratio', 'returning_buyer_ratio'):
                    current = item.get(metric)
                    prior = previous.get(metric)
                    changes[metric] = round((current - prior) / prior, 6) if current is not None and prior not in (None, 0) else None
            item['changes'] = changes
            previous = item
        from datetime import date, timedelta
        present = {item['date'] for item in result}
        cursor = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        missing = []
        while cursor <= end:
            key = cursor.isoformat()
            if key not in present:
                begin = cursor
                while cursor <= end and cursor.isoformat() not in present:
                    cursor += timedelta(days=1)
                missing.append({'start': begin.isoformat(), 'end': (cursor - timedelta(days=1)).isoformat()})
            else:
                cursor += timedelta(days=1)
        source_batches = []
        seen_batches = set()
        for item in result:
            detail = item.get('source_detail') or {}
            batch_id = detail.get('source_batch_id')
            if batch_id and batch_id not in seen_batches:
                seen_batches.add(batch_id)
                source_batches.append({**detail, 'id': batch_id})
        return {'rows': result, 'missing_date_ranges': missing, 'source_batches': source_batches}

    @staticmethod
    def overview_context():
        shop_id = get_shop_id()
        with get_db() as connection:
            batch = connection.execute(
                '''SELECT id, source_type, source_filename, source_hash, completed_at, quality_summary FROM import_batches
                   WHERE status = 'completed'
                     AND (
                       EXISTS (SELECT 1 FROM store_daily_facts f
                              WHERE f.source_batch_id = import_batches.id AND f.shop_id = ?)
                       OR EXISTS (SELECT 1 FROM promotion_daily_facts pf
                                  WHERE pf.source_batch_id = import_batches.id AND pf.shop_id = ?)
                       OR EXISTS (SELECT 1 FROM daily_data_observations o
                                  WHERE o.source_batch_id = import_batches.id AND o.shop_id = ?)
                     )
                   ORDER BY completed_at DESC LIMIT 1''',
                (shop_id, shop_id, shop_id),
            ).fetchone()
            latest = connection.execute('SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM daily_data WHERE shop_id = ?', (shop_id,)).fetchone()
        return {**dict(latest), 'latest_import': dict(batch) if batch else None}

    @staticmethod
    def action_todos():
        if get_shop_id() != 'default':
            return []
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
