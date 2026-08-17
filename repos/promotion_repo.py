from db import get_db, get_shop_id


class PromotionRepo:
    GROUP_COLUMNS = {
        'channel': ('channel',),
        'campaign': ('channel', 'campaign_id'),
        'unit': ('channel', 'campaign_id', 'unit_id'),
        'product': ('product_id',),
    }

    BREAKDOWN_COLUMNS = {
        'keywords': ('keyword_spend', 'keyword_sales', 'keyword_visitors', 'keyword_ppc'),
        'crowd': ('crowd_spend', 'crowd_sales', 'crowd_visitors', 'crowd_ppc'),
        'site': ('site_spend', 'site_sales', 'site_visitors', 'site_ppc'),
    }

    @staticmethod
    def list(start_date, end_date, group_by, filters):
        shop_id = get_shop_id()
        columns = PromotionRepo.GROUP_COLUMNS[group_by]
        where = ['shop_id = ?', 'date BETWEEN ? AND ?']
        params = [shop_id, start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'{key} = ?')
                params.append(filters[key])
        select = ', '.join(f'pdf.{column}' for column in columns)
        grouping = ', '.join(f'pdf.{column}' for column in columns)
        product_select = ''
        paid_join = ''
        link_join = ''
        query_params = list(params)
        if group_by == 'product':
            paid_select = '''
                    MAX(paid.paid_detail_rows) AS paid_detail_rows,
                    MAX(paid.total_orders) AS total_orders,
                    MAX(paid.cart_adds) AS cart_adds,
                    MAX(paid.cart_cost) AS source_cart_cost,
                    MAX(paid.new_buyers) AS new_buyers,
                    MAX(paid.favs) AS favs,
                    MAX(paid.direct_cart_adds) AS direct_cart_adds,
                    MAX(paid.indirect_cart_adds) AS indirect_cart_adds'''
            if shop_id != 'default':
                paid_select = '''
                    NULL AS paid_detail_rows,
                    NULL AS total_orders,
                    NULL AS cart_adds,
                    NULL AS source_cart_cost,
                    NULL AS new_buyers,
                    NULL AS favs,
                    NULL AS direct_cart_adds,
                    NULL AS indirect_cart_adds'''
            product_select = ''', MAX(p.title) AS title,
                    MAX(NULLIF(p.image_url, '')) AS image_url,
                    MAX(link.link_gsv) AS link_gsv,
                    MAX(link.link_net_sales) AS link_net_sales,'''+ paid_select
            if shop_id == 'default':
                paid_join = '''
                    LEFT JOIN (
                        SELECT product_id,
                               COUNT(*) AS paid_detail_rows,
                               SUM(total_orders) AS total_orders,
                               SUM(cart_adds) AS cart_adds,
                               SUM(cart_cost) AS cart_cost,
                               SUM(new_buyers) AS new_buyers,
                               SUM(favs) AS favs,
                               SUM(direct_cart_adds) AS direct_cart_adds,
                               SUM(indirect_cart_adds) AS indirect_cart_adds
                        FROM paid_detail
                        WHERE date_range BETWEEN ? AND ?
                        GROUP BY product_id
                    ) paid ON paid.product_id = pdf.product_id'''
            link_join = '''
                    LEFT JOIN (
                        SELECT product_id,
                               SUM(COALESCE(payment_amount, 0)) AS link_gsv,
                               SUM(COALESCE(payment_amount, 0) - COALESCE(refund_amount, 0)) AS link_net_sales
                        FROM daily_data
                        WHERE shop_id = ? AND date BETWEEN ? AND ?
                        GROUP BY product_id
                    ) link ON link.product_id = pdf.product_id'''
            query_params = [shop_id, start_date, end_date, *params]
            if shop_id == 'default':
                query_params = [start_date[:7], end_date[:7], *query_params]
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT {select}{product_select}, SUM(pdf.ad_spend) AS ad_spend,
                    SUM(pdf.attributed_payment_amount) AS attributed_payment_amount,
                    SUM(pdf.impressions) AS impressions, SUM(pdf.clicks) AS clicks,
                    SUM(pdf.payment_buyers) AS payment_buyers,
                    SUM(pdf.direct_payment_amount) AS direct_payment_amount,
                    SUM(pdf.indirect_payment_amount) AS indirect_payment_amount
                    FROM promotion_daily_facts pdf
                    LEFT JOIN products p ON p.product_id = pdf.product_id
                    {paid_join}
                    {link_join}
                    WHERE {' AND '.join(f'pdf.{clause}' for clause in where)}
                    GROUP BY {grouping} ORDER BY ad_spend DESC''', query_params,
            ).fetchall()
            store_payment = connection.execute(
                "SELECT SUM(payment_amount) FROM store_daily_facts WHERE shop_id = ? AND date BETWEEN ? AND ?",
                (shop_id, start_date, end_date),
            ).fetchone()[0]
        return [{**dict(row), 'store_payment_amount': store_payment} for row in rows]

    @staticmethod
    def monthly_breakdowns(start_date, end_date, product_ids=None):
        start_month = start_date[:7]
        end_month = end_date[:7]
        product_filter = ''
        product_params = []
        if product_ids is not None:
            if not product_ids:
                return {key: [] for key in PromotionRepo.BREAKDOWN_COLUMNS}
            placeholders = ','.join('?' for _ in product_ids)
            product_filter = f' AND md.product_id IN ({placeholders})'
            product_params = list(product_ids)

        result = {}
        with get_db() as connection:
            for key, (spend, sales, visitors, ppc) in PromotionRepo.BREAKDOWN_COLUMNS.items():
                rows = connection.execute(
                    f'''SELECT md.product_id, MAX(p.title) AS title,
                               SUM(md.{spend}) AS spend, SUM(md.{sales}) AS sales,
                               SUM(md.{visitors}) AS visitors,
                               SUM(CASE WHEN md.{ppc} > 0 THEN md.{spend} / md.{ppc} ELSE 0 END) AS estimated_clicks
                        FROM monthly_data md
                        LEFT JOIN products p ON p.product_id = md.product_id
                        WHERE md.month BETWEEN ? AND ?{product_filter}
                          AND (md.{spend} > 0 OR md.{sales} > 0 OR md.{visitors} > 0)
                        GROUP BY md.product_id
                        ORDER BY spend DESC''',
                    [start_month, end_month, *product_params],
                ).fetchall()
                result[key] = [dict(row) for row in rows]
        return result

    @staticmethod
    def trend(start_date, end_date, filters):
        shop_id = get_shop_id()
        where = ['shop_id = ?', 'date BETWEEN ? AND ?']
        params = [shop_id, start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'{key} = ?')
                params.append(filters[key])
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT date, SUM(ad_spend) AS ad_spend,
                           SUM(attributed_payment_amount) AS attributed_payment_amount,
                           SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                           SUM(payment_buyers) AS payment_buyers,
                           SUM(direct_payment_amount) AS direct_payment_amount,
                           SUM(indirect_payment_amount) AS indirect_payment_amount
                    FROM promotion_daily_facts WHERE {' AND '.join(where)}
                    GROUP BY date ORDER BY date''', params,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def available_grains(start_date, end_date, filters):
        shop_id = get_shop_id()
        where = ['shop_id = ?', 'date BETWEEN ? AND ?']
        params = [shop_id, start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'{key} = ?')
                params.append(filters[key])
        with get_db() as connection:
            row = connection.execute(
                f'''SELECT COUNT(DISTINCT NULLIF(channel, '')) AS channels,
                           COUNT(DISTINCT NULLIF(campaign_id, '')) AS campaigns,
                           COUNT(DISTINCT NULLIF(unit_id, '')) AS units,
                           COUNT(DISTINCT NULLIF(product_id, '')) AS products
                    FROM promotion_daily_facts WHERE {' AND '.join(where)}''', params,
            ).fetchone()
        mapping = [('channel', 'channels'), ('campaign', 'campaigns'), ('unit', 'units'), ('product', 'products')]
        return [grain for grain, column in mapping if row[column]]

    @staticmethod
    def source_batches(start_date, end_date, filters):
        shop_id = get_shop_id()
        where = ['pdf.shop_id = ?', 'pdf.date BETWEEN ? AND ?']
        params = [shop_id, start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'pdf.{key} = ?')
                params.append(filters[key])
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT DISTINCT b.id, b.source_type, b.source_filename, b.source_hash,
                          b.completed_at, b.quality_summary
                   FROM promotion_daily_facts pdf
                   JOIN import_batches b ON b.id = pdf.source_batch_id
                   WHERE ''' + ' AND '.join(where) + '''
                   ORDER BY b.completed_at DESC''',
                params,
            ).fetchall()
        return [dict(row) for row in rows]
