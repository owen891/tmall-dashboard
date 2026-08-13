from db import get_db


class PromotionRepo:
    GROUP_COLUMNS = {
        'channel': ('channel',),
        'campaign': ('channel', 'campaign_id'),
        'unit': ('channel', 'campaign_id', 'unit_id'),
        'product': ('channel', 'product_id'),
    }

    @staticmethod
    def list(start_date, end_date, group_by, filters):
        columns = PromotionRepo.GROUP_COLUMNS[group_by]
        where = ['date BETWEEN ? AND ?']
        params = [start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'{key} = ?')
                params.append(filters[key])
        select = ', '.join(columns)
        grouping = ', '.join(columns)
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT {select}, SUM(ad_spend) AS ad_spend,
                    SUM(attributed_payment_amount) AS attributed_payment_amount,
                    SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                    SUM(payment_buyers) AS payment_buyers,
                    SUM(direct_payment_amount) AS direct_payment_amount,
                    SUM(indirect_payment_amount) AS indirect_payment_amount
                    FROM promotion_daily_facts WHERE {' AND '.join(where)}
                    GROUP BY {grouping} ORDER BY ad_spend DESC''', params,
            ).fetchall()
            store_payment = connection.execute(
                "SELECT SUM(payment_amount) FROM store_daily_facts WHERE date BETWEEN ? AND ?", (start_date, end_date)
            ).fetchone()[0]
        return [{**dict(row), 'store_payment_amount': store_payment} for row in rows]
