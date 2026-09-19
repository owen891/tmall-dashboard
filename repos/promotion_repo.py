from db import get_db, get_shop_id


class PromotionRepo:
    GROUP_COLUMNS = {
        'channel': ('channel',),
        'campaign': ('channel', 'campaign_id'),
        'unit': ('channel', 'campaign_id', 'unit_id'),
        'product': ('product_id',),
    }

    # 粒度过滤：维度报表回填后，同一笔花费只以一个粒度落库（计划/商品/创意
    # 各自独立成行），report 查询按 grain 过滤避免跨粒度重复求和。
    # unit 行同时携带 campaign/product 维度（旧关键词报表），可参与更粗粒度
    # 的聚合；渠道视图只认 channel/campaign 行——商品行（channel='全部'）
    # 不带渠道归属，不得计入渠道对比。grain='' 是迁移前/旧代码写入的行，
    # 按旧规则通配参与所有视图。
    GROUP_GRAINS = {
        'channel': ('channel', 'campaign'),
        'campaign': ('campaign', 'unit'),
        'unit': ('unit',),
        'product': ('product', 'unit'),
    }

    @staticmethod
    def _grain_filter(group_by, alias='pdf.'):
        grains = PromotionRepo.GROUP_GRAINS[group_by]
        marks = ','.join('?' for _ in grains)
        return f"{alias}grain IN ({marks}) OR {alias}grain = ''", list(grains)

    BREAKDOWN_COLUMNS = {
        'keywords': ('keyword_spend', 'keyword_sales', 'keyword_visitors', 'keyword_ppc'),
        'crowd': ('crowd_spend', 'crowd_sales', 'crowd_visitors', 'crowd_ppc'),
        'site': ('site_spend', 'site_sales', 'site_visitors', 'site_ppc'),
    }

    @staticmethod
    def list(start_date, end_date, group_by, filters):
        shop_id = get_shop_id()
        columns = PromotionRepo.GROUP_COLUMNS[group_by]
        grain_clause, grains = PromotionRepo._grain_filter(group_by)
        where = [f'({grain_clause})', 'pdf.shop_id = ?', 'pdf.date BETWEEN ? AND ?']
        params = [*grains, shop_id, start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'pdf.{key} = ?')
                params.append(filters[key])
        if filters.get('shop_label'):
            label = filters['shop_label']
            label_match = "(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            if group_by == 'campaign':
                # 计划行没有直接商品关联：按计划投放的商品命中品类收窄
                where.append(
                    f"({label_match} OR EXISTS ("
                    "    SELECT 1 FROM promotion_campaign_items ci"
                    "    JOIN products cp ON cp.product_id = ci.product_id"
                    "    WHERE ci.shop_id = pdf.shop_id AND ci.campaign_id = pdf.campaign_id"
                    "      AND (cp.shop_label = ? OR instr(',' || cp.shop_label || ',', ',' || ? || ',') > 0)))"
                )
                params.extend([label, label, label, label])
            else:
                # 无商品行（渠道/账户粒度）不携带品类，按全店口径保留
                where.append(f"(pdf.product_id = '' OR {label_match})")
                params.extend([label, label])
        select = ', '.join(f'pdf.{column}' for column in columns) + ','
        grouping = ', '.join(f'pdf.{column}' for column in columns)
        product_select = ''
        paid_join = ''
        link_join = ''
        # 参数顺序必须与 SQL 文本中的占位符顺序一致：
        # paid 子查询 -> link 子查询 -> 主 WHERE。
        paid_params = []
        link_params = []
        if group_by == 'product':
            product_select = ''' MAX(p.title) AS title,
                    MAX(NULLIF(p.image_url, '')) AS image_url,
                    MAX(link.link_gsv) AS link_gsv,
                    MAX(link.link_net_sales) AS link_net_sales,'''
            if shop_id == 'default':
                product_select += '''
                    MAX(paid.paid_detail_rows) AS paid_detail_rows,
                    MAX(paid.total_orders) AS total_orders,
                    MAX(paid.cart_adds) AS paid_cart_adds,
                    MAX(paid.new_buyers) AS paid_new_buyers,
                    MAX(paid.cart_cost) AS source_cart_cost,
                    MAX(paid.favs) AS favs,
                    MAX(paid.direct_cart_adds) AS direct_cart_adds,
                    MAX(paid.indirect_cart_adds) AS indirect_cart_adds,'''
                paid_join = '''
                    LEFT JOIN (
                        SELECT product_id,
                               COUNT(*) AS paid_detail_rows,
                               SUM(total_orders) AS total_orders,
                               SUM(cart_adds) AS cart_adds,
                               SUM(new_buyers) AS new_buyers,
                               SUM(cart_cost) AS cart_cost,
                               SUM(favs) AS favs,
                               SUM(direct_cart_adds) AS direct_cart_adds,
                               SUM(indirect_cart_adds) AS indirect_cart_adds
                        FROM paid_detail
                        WHERE date_range BETWEEN ? AND ?
                        GROUP BY product_id
                    ) paid ON paid.product_id = pdf.product_id'''
                paid_params = [start_date[:7], end_date[:7]]
            else:
                product_select += '''
                    0 AS paid_detail_rows,
                    NULL AS total_orders,
                    NULL AS paid_cart_adds,
                    NULL AS paid_new_buyers,
                    NULL AS source_cart_cost,
                    NULL AS favs,
                    NULL AS direct_cart_adds,
                    NULL AS indirect_cart_adds,'''
            link_join = '''
                    LEFT JOIN (
                        SELECT product_id,
                               SUM(COALESCE(payment_amount, 0)) AS link_gsv,
                               SUM(COALESCE(payment_amount, 0) - COALESCE(refund_amount, 0)) AS link_net_sales
                        FROM daily_data
                        WHERE shop_id = ? AND date BETWEEN ? AND ?
                        GROUP BY product_id
                    ) link ON link.product_id = pdf.product_id'''
            link_params = [shop_id, start_date, end_date]
        campaign_name_select = ' MAX(pdf.campaign_name) AS campaign_name,' if group_by == 'campaign' else ''
        query_params = [*paid_params, *link_params, *params]
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT {select}{product_select}{campaign_name_select}
                    SUM(pdf.ad_spend) AS ad_spend,
                    SUM(pdf.attributed_payment_amount) AS attributed_payment_amount,
                    SUM(pdf.impressions) AS impressions, SUM(pdf.clicks) AS clicks,
                    SUM(pdf.payment_buyers) AS payment_buyers,
                    SUM(pdf.direct_payment_amount) AS direct_payment_amount,
                    SUM(pdf.indirect_payment_amount) AS indirect_payment_amount,
                    SUM(COALESCE(pdf.cart_adds, 0)) AS fact_cart_adds,
                    SUM(COALESCE(pdf.new_buyers, 0)) AS fact_new_buyers
                    FROM promotion_daily_facts pdf
                    LEFT JOIN products p ON p.product_id = pdf.product_id
                    {paid_join}
                    {link_join}
                    WHERE {' AND '.join(where)}
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
        where = ["(grain IN ('product', 'unit') OR grain = '')", 'shop_id = ?', 'date BETWEEN ? AND ?']
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
        where_sql = ' AND '.join(where)
        wildcard = " OR grain = ''"
        with get_db() as connection:
            row = connection.execute(
                f'''SELECT (SELECT COUNT(DISTINCT channel) FROM promotion_daily_facts
                            WHERE (grain IN ('channel', 'campaign'){wildcard}) AND {where_sql}) AS channels,
                           (SELECT COUNT(DISTINCT NULLIF(campaign_id, '')) FROM promotion_daily_facts
                            WHERE (grain = 'campaign' OR grain = 'unit'{wildcard}) AND {where_sql}) AS campaigns,
                           (SELECT COUNT(DISTINCT NULLIF(unit_id, '')) FROM promotion_daily_facts
                            WHERE (grain = 'unit'{wildcard}) AND {where_sql}) AS units,
                           (SELECT COUNT(DISTINCT NULLIF(product_id, '')) FROM promotion_daily_facts
                            WHERE (grain IN ('product', 'unit'){wildcard}) AND {where_sql}) AS products''',
                params + params + params + params,
            ).fetchone()
        mapping = [('channel', 'channels'), ('campaign', 'campaigns'), ('unit', 'units'), ('product', 'products')]
        return [grain for grain, column in mapping if row[column]]

    # 系统自动生成的创意（智能创意/黑盒/主图自动命名的创意_时间戳/店铺直达）
    # 对运营没有评估价值，素材看板默认不展示；原始数据仍保留在库中。
    SYSTEM_CREATIVE_SQL = (
        "COALESCE(c.creative_name, '') NOT LIKE '%智能创意%'"
        " AND COALESCE(c.creative_name, '') NOT LIKE '%黑盒%'"
        " AND COALESCE(c.creative_name, '') NOT GLOB '创意_[0-9]*'"
        " AND COALESCE(c.channel, '') != '店铺直达'"
    )

    @staticmethod
    def creatives(start_date, end_date, product_id=None, channel=None, sort='clicks', filters=None):
        """素材维度汇总：promotion_creative_daily × promotion_creatives（排除系统创意）。"""
        shop_id = get_shop_id()
        where = ['f.shop_id = ?', 'f.date BETWEEN ? AND ?']
        params = [shop_id, start_date, end_date]
        filters = filters or {}
        if filters.get('shop_label'):
            label = filters['shop_label']
            where.append("(f.product_id = '' OR p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
            params.extend([label, label])
        if product_id:
            where.append('f.product_id = ?')
            params.append(product_id)
        if channel:
            where.append('f.channel = ?')
            params.append(channel)
        # SQL 侧只按实际列排序；ctr/cvr 是派生指标，由服务层在归一化后排序
        order_column = {'clicks': 'clicks', 'ad_spend': 'ad_spend',
                        'cart_cost': 'cart_cost'}.get(sort, 'clicks')
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT c.creative_id, MAX(c.creative_name) AS creative_name,
                           MAX(c.image_url) AS image_url, MAX(c.video_url) AS video_url,
                           MAX(c.creative_format) AS creative_format,
                           f.product_id, MAX(c.product_name) AS product_name,
                           f.channel, MAX(p.title) AS title,
                           SUM(f.ad_spend) AS ad_spend,
                           SUM(f.attributed_payment_amount) AS attributed_payment_amount,
                           SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks,
                           SUM(f.payment_buyers) AS payment_buyers,
                           SUM(f.direct_payment_amount) AS direct_payment_amount,
                           SUM(COALESCE(f.cart_adds, 0)) AS cart_adds,
                           SUM(COALESCE(f.new_buyers, 0)) AS new_buyers
                    FROM promotion_creative_daily f
                    LEFT JOIN promotion_creatives c
                        ON c.shop_id = f.shop_id AND c.creative_id = f.creative_id
                    LEFT JOIN products p ON p.product_id = f.product_id
                    WHERE {' AND '.join(where)}
                      AND {PromotionRepo.SYSTEM_CREATIVE_SQL}
                    GROUP BY c.creative_id, f.product_id, f.channel
                    ORDER BY {order_column} DESC''', params,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def campaigns_for_product(start_date, end_date, product_id):
        """某商品关联的计划列表（计划粒度事实 × 计划商品映射）。"""
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT ci.campaign_id, MAX(ci.campaign_name) AS campaign_name,
                          MAX(ci.channel) AS channel,
                          SUM(f.ad_spend) AS ad_spend,
                          SUM(f.attributed_payment_amount) AS attributed_payment_amount,
                          SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks,
                          SUM(f.payment_buyers) AS payment_buyers,
                          SUM(COALESCE(f.cart_adds, 0)) AS cart_adds,
                          SUM(COALESCE(f.new_buyers, 0)) AS new_buyers
                   FROM promotion_campaign_items ci
                   LEFT JOIN promotion_daily_facts f
                       ON f.shop_id = ci.shop_id AND f.campaign_id = ci.campaign_id
                       AND f.grain = 'campaign' AND f.date BETWEEN ? AND ?
                   WHERE ci.shop_id = ? AND ci.product_id = ?
                   GROUP BY ci.campaign_id
                   ORDER BY ad_spend DESC''',
                [start_date, end_date, shop_id, product_id],
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def campaign_products(campaign_id):
        """某计划下投放的商品（计划×商品映射 + 商品目录图）。"""
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT ci.product_id, MAX(ci.product_name) AS product_name,
                          MAX(ci.image_url) AS image_url,
                          MAX(COALESCE(NULLIF(p.title, ''), ci.product_name)) AS title,
                          COUNT(c.creative_id) AS creative_count
                   FROM promotion_campaign_items ci
                   LEFT JOIN products p ON p.product_id = ci.product_id
                   LEFT JOIN promotion_creatives c
                       ON c.shop_id = ci.shop_id AND c.product_id = ci.product_id
                       AND {PromotionRepo.SYSTEM_CREATIVE_SQL}
                   WHERE ci.shop_id = ? AND ci.campaign_id = ?
                   GROUP BY ci.product_id ORDER BY product_name''',
                [shop_id, campaign_id],
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def campaign_summary(start_date, end_date, campaign_id):
        """某计划的汇总指标（计划粒度事实行）。"""
        shop_id = get_shop_id()
        with get_db() as connection:
            row = connection.execute(
                '''SELECT MAX(campaign_name) AS campaign_name, MAX(channel) AS channel,
                          SUM(ad_spend) AS ad_spend,
                          SUM(attributed_payment_amount) AS attributed_payment_amount,
                          SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                          SUM(payment_buyers) AS payment_buyers,
                          SUM(COALESCE(cart_adds, 0)) AS cart_adds,
                          SUM(COALESCE(new_buyers, 0)) AS new_buyers
                   FROM promotion_daily_facts
                   WHERE shop_id = ? AND grain = 'campaign' AND campaign_id = ?
                     AND date BETWEEN ? AND ?''',
                [shop_id, campaign_id, start_date, end_date],
            ).fetchone()
        return dict(row) if row else {}

    @staticmethod
    def channel_mix_for_product(start_date, end_date, product_id):
        """某商品的渠道花费结构（按 promoting campaign 的渠道归因）。"""
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT MAX(ci.channel) AS channel,
                          SUM(f.ad_spend) AS ad_spend,
                          SUM(f.attributed_payment_amount) AS attributed_payment_amount
                   FROM promotion_campaign_items ci
                   LEFT JOIN promotion_daily_facts f
                       ON f.shop_id = ci.shop_id AND f.campaign_id = ci.campaign_id
                       AND f.grain = 'campaign' AND f.date BETWEEN ? AND ?
                   WHERE ci.shop_id = ? AND ci.product_id = ?
                   GROUP BY ci.channel ORDER BY ad_spend DESC''',
                [start_date, end_date, shop_id, product_id],
            ).fetchall()
        return [dict(row) for row in rows]

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
