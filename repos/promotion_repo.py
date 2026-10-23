from db import get_db, get_shop_id

# 新品窗口：周期结束日前 N 天内上架视为新品（与复盘页 period_context 口径一致）。
NEW_PRODUCT_WINDOW_DAYS = 60


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

    FACT_METRICS = ('ad_spend', 'attributed_payment_amount', 'impressions', 'clicks',
                    'payment_buyers', 'direct_payment_amount', 'indirect_payment_amount',
                    'cart_adds', 'new_buyers')

    @staticmethod
    def _coverage_select(alias=''):
        # Denominator = selected stored fact rows, NOT products or calendar days.
        active_impressions = (
            f'({alias}impressions IS NOT NULL OR COALESCE({alias}ad_spend, 0) > 0 '
            f'OR COALESCE({alias}clicks, 0) > 0)'
        )
        return ', '.join([f'COUNT({alias}date) AS _expected_rows',
                          f'COUNT(CASE WHEN {active_impressions} THEN {alias}date END) AS _active_impressions_expected_rows',
                          f'COUNT(CASE WHEN {active_impressions} AND {alias}impressions IS NOT NULL THEN {alias}date END) AS _active_impressions_observed_rows'] + [
            f'COUNT({alias}{field}) AS _observed_{field}' for field in PromotionRepo.FACT_METRICS])

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
        if group_by == 'product':
            # 账户级总账行没有商品归属,不进商品排行(否则重复计账)
            where.append("pdf.product_id != ''")
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
                    MAX(link.expected_rows) AS _link_expected_rows,
                    MAX(link.observed_payment) AS _link_observed_payment,
                    MAX(link.observed_net) AS _link_observed_net,
                    MAX(link.link_net_sales) AS link_net_sales,'''
            if shop_id == 'default':
                product_select += '''
                    MAX(paid.paid_detail_rows) AS paid_detail_rows,
                    MAX(paid.observed_total_orders) AS _paid_observed_total_orders,
                    MAX(paid.observed_cart_adds) AS _paid_observed_cart_adds,
                    MAX(paid.observed_new_buyers) AS _paid_observed_new_buyers,
                    MAX(paid.observed_cart_cost) AS _paid_observed_cart_cost,
                    MAX(paid.observed_favs) AS _paid_observed_favs,
                    MAX(paid.observed_direct_cart_adds) AS _paid_observed_direct_cart_adds,
                    MAX(paid.observed_indirect_cart_adds) AS _paid_observed_indirect_cart_adds,
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
                               COUNT(total_orders) AS observed_total_orders,
                               COUNT(cart_adds) AS observed_cart_adds,
                               COUNT(new_buyers) AS observed_new_buyers,
                               COUNT(cart_cost) AS observed_cart_cost,
                               COUNT(favs) AS observed_favs,
                               COUNT(direct_cart_adds) AS observed_direct_cart_adds,
                               COUNT(indirect_cart_adds) AS observed_indirect_cart_adds,
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
                               COUNT(*) AS expected_rows, COUNT(payment_amount) AS observed_payment,
                               COUNT(CASE WHEN payment_amount IS NOT NULL AND refund_amount IS NOT NULL THEN 1 END) AS observed_net,
                               SUM(payment_amount) AS link_gsv,
                               SUM(payment_amount - refund_amount) AS link_net_sales
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
                    {PromotionRepo._coverage_select('pdf.')},
                    SUM(pdf.ad_spend) AS ad_spend,
                    SUM(pdf.attributed_payment_amount) AS attributed_payment_amount,
                    SUM(pdf.impressions) AS impressions, SUM(pdf.clicks) AS clicks,
                    SUM(pdf.payment_buyers) AS payment_buyers,
                    SUM(pdf.direct_payment_amount) AS direct_payment_amount,
                    SUM(pdf.indirect_payment_amount) AS indirect_payment_amount,
                    SUM(pdf.cart_adds) AS fact_cart_adds,
                    SUM(pdf.new_buyers) AS fact_new_buyers
                    FROM promotion_daily_facts pdf
                    LEFT JOIN products p ON p.product_id = pdf.product_id
                    {paid_join}
                    {link_join}
                    WHERE {' AND '.join(where)}
                    GROUP BY {grouping} ORDER BY ad_spend DESC''', query_params,
            ).fetchall()
            store_payment = connection.execute(
                "SELECT SUM(payment_amount), COUNT(*), COUNT(payment_amount) FROM store_daily_facts WHERE shop_id = ? AND date BETWEEN ? AND ?",
                (shop_id, start_date, end_date),
            ).fetchone()
        return [{**dict(row), 'store_payment_amount': store_payment[0],
                 '_store_expected_rows': store_payment[1], '_store_observed_rows': store_payment[2]} for row in rows]

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
                f'''SELECT date, {PromotionRepo._coverage_select()}, SUM(ad_spend) AS ad_spend,
                           SUM(attributed_payment_amount) AS attributed_payment_amount,
                           SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                           SUM(payment_buyers) AS payment_buyers,
                           SUM(direct_payment_amount) AS direct_payment_amount,
                           SUM(indirect_payment_amount) AS indirect_payment_amount,
                           SUM(cart_adds) AS cart_adds, SUM(new_buyers) AS new_buyers
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
        where = ['f.shop_id = ?', "f.product_id != ''", 'f.date BETWEEN ? AND ?']
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
                           SUM(f.cart_adds) AS cart_adds,
                           SUM(f.new_buyers) AS new_buyers
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
        """某商品关联的计划列表（计划/单元事实 × 计划商品映射）。"""
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT ci.campaign_id, {PromotionRepo._coverage_select('f.')}, MAX(ci.campaign_name) AS campaign_name,
                          MAX(ci.channel) AS channel,
                          SUM(f.ad_spend) AS ad_spend,
                          SUM(f.attributed_payment_amount) AS attributed_payment_amount,
                          SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks,
                          SUM(f.payment_buyers) AS payment_buyers,
                          SUM(f.direct_payment_amount) AS direct_payment_amount,
                          SUM(f.indirect_payment_amount) AS indirect_payment_amount,
                          SUM(f.cart_adds) AS cart_adds,
                          SUM(f.new_buyers) AS new_buyers
                   FROM promotion_campaign_items ci
                   LEFT JOIN promotion_daily_facts f
                       ON f.shop_id = ci.shop_id AND f.campaign_id = ci.campaign_id
                       AND f.grain IN ('campaign', 'unit') AND f.date BETWEEN ? AND ?
                   WHERE ci.shop_id = ? AND ci.product_id = ?
                   GROUP BY ci.campaign_id
                   HAVING SUM(COALESCE(f.ad_spend, 0)) > 0
                   ORDER BY ad_spend DESC''',
                [start_date, end_date, shop_id, product_id],
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def product_facts_for_product(start_date, end_date, product_id):
        """商品总账兜底：当计划映射没有有效事实时提供商品级推广汇总。"""
        shop_id = get_shop_id()
        with get_db() as connection:
            row = connection.execute(
                f'''SELECT ? AS campaign_id, {PromotionRepo._coverage_select()}, '商品推广总账' AS campaign_name,
                          MAX(channel) AS channel,
                          SUM(ad_spend) AS ad_spend,
                          SUM(attributed_payment_amount) AS attributed_payment_amount,
                          SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                          SUM(payment_buyers) AS payment_buyers,
                          SUM(direct_payment_amount) AS direct_payment_amount,
                          SUM(indirect_payment_amount) AS indirect_payment_amount,
                          SUM(cart_adds) AS cart_adds,
                          SUM(new_buyers) AS new_buyers
                   FROM promotion_daily_facts
                   WHERE shop_id = ? AND grain = 'product' AND product_id = ?
                     AND date BETWEEN ? AND ?''',
                [f'product:{product_id}', shop_id, product_id, start_date, end_date],
            ).fetchone()
        return dict(row) if row and row['ad_spend'] is not None else None

    @staticmethod
    def product_behavior_for_period(start_date, end_date, product_id):
        """商品经营侧潜客数据，按月份覆盖日期范围聚合。"""
        with get_db() as connection:
            row = connection.execute(
                '''SELECT SUM(COALESCE(guide_visits, 0)) AS guide_visits,
                          SUM(COALESCE(guide_visitors, 0)) AS guide_visitors,
                          SUM(COALESCE(guide_potential, 0)) AS guide_potential,
                          SUM(new_buyers) AS new_buyers
                   FROM monthly_data
                   WHERE product_id = ? AND month BETWEEN ? AND ?''',
                [product_id, str(start_date)[:7], str(end_date)[:7]],
            ).fetchone()
        return dict(row) if row else {}

    @staticmethod
    def creative_board(shop_label=None, product_id=None, include_system=False):
        """素材历史累计看板：以商品目录为主表关联素材，不含时间筛选。

        全局看板默认隐藏系统自动创意；商品级明细可显式包含它们，
        便于从新品或商品结构进入时查看该商品的完整素材投放记录。
        """
        shop_id = get_shop_id()
        where = [
            "COALESCE(p.product_id, '') != ''",
            "c.creative_id IS NOT NULL",
        ]
        params = [shop_id]
        if product_id:
            where.append('p.product_id = ?')
            params.append(product_id)
        if shop_label:
            where.append("(COALESCE(p.shop_label, '') = ? OR instr(',' || COALESCE(p.shop_label, '') || ',', ',' || ? || ',') > 0)")
            params.extend([shop_label, shop_label])
        creative_filter = '' if include_system else f'AND {PromotionRepo.SYSTEM_CREATIVE_SQL}'
        with get_db() as connection:
            rows = connection.execute(
                    f'''SELECT c.creative_id, MAX(c.creative_name) AS creative_name,
                           MAX(c.image_url) AS image_url, MAX(c.creative_format) AS creative_format,
                           p.product_id,
                           MAX(COALESCE(NULLIF(p.title, ''), NULLIF(c.product_name, ''), p.product_id)) AS title,
                           MAX(COALESCE(NULLIF(p.image_url, ''), '')) AS product_image,
                           MAX(COALESCE(p.shop_label, '')) AS shop_label,
                           COALESCE(SUM(f.ad_spend), 0) AS ad_spend,
                           COALESCE(SUM(f.attributed_payment_amount), 0) AS attributed_payment_amount,
                           COALESCE(SUM(f.impressions), 0) AS impressions,
                           COALESCE(SUM(f.clicks), 0) AS clicks,
                           COALESCE(SUM(f.payment_buyers), 0) AS payment_buyers,
                           COALESCE(SUM(f.direct_payment_amount), 0) AS direct_payment_amount,
                           COALESCE(SUM(f.cart_adds), 0) AS cart_adds,
                           COALESCE(SUM(f.new_buyers), 0) AS new_buyers,
                           MIN(f.date) AS first_date, MAX(f.date) AS last_date
                     FROM products p
                     LEFT JOIN promotion_creatives c
                         ON c.shop_id = ? AND c.product_id = p.product_id
                         {creative_filter}
                     LEFT JOIN promotion_creative_daily f
                         ON f.shop_id = c.shop_id AND f.creative_id = c.creative_id
                     WHERE {' AND '.join(where)}
                     GROUP BY c.creative_id, p.product_id
                     ORDER BY ad_spend DESC, p.product_id''', params,
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
                f'''SELECT {PromotionRepo._coverage_select()}, MAX(campaign_name) AS campaign_name, MAX(channel) AS channel,
                          SUM(ad_spend) AS ad_spend,
                          SUM(attributed_payment_amount) AS attributed_payment_amount,
                          SUM(impressions) AS impressions, SUM(clicks) AS clicks,
                          SUM(payment_buyers) AS payment_buyers,
                          SUM(direct_payment_amount) AS direct_payment_amount,
                          SUM(indirect_payment_amount) AS indirect_payment_amount,
                          SUM(cart_adds) AS cart_adds,
                          SUM(new_buyers) AS new_buyers
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
                f'''SELECT {PromotionRepo._coverage_select('f.')}, MAX(ci.channel) AS channel,
                          SUM(f.ad_spend) AS ad_spend,
                          SUM(f.attributed_payment_amount) AS attributed_payment_amount,
                          SUM(f.impressions) AS impressions, SUM(f.clicks) AS clicks,
                          SUM(f.payment_buyers) AS payment_buyers,
                          SUM(f.direct_payment_amount) AS direct_payment_amount,
                          SUM(f.indirect_payment_amount) AS indirect_payment_amount,
                          SUM(f.cart_adds) AS cart_adds,
                          SUM(f.new_buyers) AS new_buyers
                   FROM promotion_campaign_items ci
                   LEFT JOIN promotion_daily_facts f
                       ON f.shop_id = ci.shop_id AND f.campaign_id = ci.campaign_id
                       AND f.grain IN ('campaign', 'unit') AND f.date BETWEEN ? AND ?
                   WHERE ci.shop_id = ? AND ci.product_id = ?
                   GROUP BY ci.channel
                   HAVING SUM(COALESCE(f.ad_spend, 0)) > 0
                   ORDER BY ad_spend DESC''',
                [start_date, end_date, shop_id, product_id],
            ).fetchall()
        return [dict(row) for row in rows]

    # 新品 list_date 口径：入库时可能带 '2026-09-05 00:00:00' 一类脏值，
    # 统一截取前 10 位参与日期比较。
    NEW_DATE_COLUMNS = "substr(p.list_date, 1, 10)"

    @staticmethod
    def new_products(start_date, end_date, filters):
        """新品看板：周期结束日前 60 天内上架的商品 × 推广/销售聚合。

        新品口径与复盘页（period_context）一致：list_date 落在
        [end-60d, end] 区间。推广取 product/unit 粒度行（与商品视图同口径），
        销售从 daily_data 带出链接净销售额，供"推广是否拉动新品"判断。
        返回 (新品行, 新品全店总数, 全店推广盘汇总)。
        """
        shop_id = get_shop_id()
        filters = filters or {}
        date_col = PromotionRepo.NEW_DATE_COLUMNS
        where = [
            "(grain IN ('product', 'unit') OR grain = '')",
            'pdf.shop_id = ?',
            'pdf.date BETWEEN ? AND ?',
            "p.list_date IS NOT NULL AND p.list_date != ''",
            f"{date_col} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            f'{date_col} <= ?',
            f"date(?, '-' || ? || ' day') <= {date_col}",
        ]
        params = [shop_id, start_date, end_date, end_date, end_date, NEW_PRODUCT_WINDOW_DAYS]
        if filters.get('shop_label'):
            label = filters['shop_label']
            where.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
            params.extend([label, label])
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                where.append(f'pdf.{key} = ?')
                params.append(filters[key])
        with get_db() as connection:
            rows = connection.execute(
                f'''SELECT p.product_id,
                           MAX(p.title) AS title,
                           MAX(NULLIF(p.image_url, '')) AS image_url,
                           MAX({date_col}) AS list_date,
                           MAX(COALESCE(p.shop_label, '')) AS shop_label,
                           MAX(COALESCE(p.product_growth_stage, '')) AS growth_stage,
                           SUM(pdf.ad_spend) AS ad_spend,
                           SUM(pdf.attributed_payment_amount) AS attributed_payment_amount,
                           SUM(pdf.impressions) AS impressions,
                           SUM(pdf.clicks) AS clicks,
                           SUM(pdf.payment_buyers) AS payment_buyers,
                           SUM(COALESCE(pdf.cart_adds, 0)) AS cart_adds,
                           SUM(COALESCE(pdf.new_buyers, 0)) AS new_buyers,
                           COALESCE(link.link_gsv, 0) AS link_gsv,
                           COALESCE(link.link_net_sales, 0) AS link_net_sales
                    FROM promotion_daily_facts pdf
                    JOIN products p ON p.product_id = pdf.product_id
                    LEFT JOIN (
                        SELECT product_id,
                               SUM(COALESCE(payment_amount, 0)) AS link_gsv,
                               SUM(COALESCE(payment_amount, 0) - COALESCE(refund_amount, 0)) AS link_net_sales
                        FROM daily_data
                        WHERE shop_id = ? AND date BETWEEN ? AND ?
                        GROUP BY product_id
                    ) link ON link.product_id = pdf.product_id
                    WHERE {' AND '.join(where)}
                    GROUP BY p.product_id
                    ORDER BY ad_spend DESC''',
                [shop_id, start_date, end_date, *params],
            ).fetchall()
            total_where = [
                "p.list_date IS NOT NULL AND p.list_date != ''",
                f"{date_col} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
                f'{date_col} <= ?',
                f"date(?, '-' || ? || ' day') <= {date_col}",
            ]
            total_params = [end_date, end_date, NEW_PRODUCT_WINDOW_DAYS]
            if filters.get('shop_label'):
                label = filters['shop_label']
                total_where.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
                total_params.extend([label, label])
            new_total = connection.execute(
                f'''SELECT COUNT(DISTINCT p.product_id) FROM products p
                    WHERE {' AND '.join(total_where)}''',
                total_params,
            ).fetchone()[0]
            # 全店推广盘（同窗口、同品类筛选；不含 channel 等下钻维度，
            # 占比要对照"全店推广投放了多少给新品"）
            overall_where = ["(grain IN ('product', 'unit') OR grain = '')", 'shop_id = ?', 'date BETWEEN ? AND ?']
            overall_params = [shop_id, start_date, end_date]
            if filters.get('shop_label'):
                label = filters['shop_label']
                overall_where.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
                overall_params.extend([label, label])
            overall = connection.execute(
                f'''SELECT COALESCE(SUM(ad_spend), 0) AS ad_spend,
                           COALESCE(SUM(attributed_payment_amount), 0) AS attributed_payment_amount
                    FROM promotion_daily_facts pdf
                    JOIN products p ON p.product_id = pdf.product_id
                    WHERE {' AND '.join(overall_where)}''',
                overall_params,
            ).fetchone()
        return [dict(row) for row in rows], int(new_total or 0), dict(overall or {})

    @staticmethod
    def new_product_launches(start_date, end_date, filters):
        """按新品上架日期聚合全量新品，并左连接推广与销售事实。"""
        shop_id = get_shop_id()
        filters = filters or {}
        date_col = PromotionRepo.NEW_DATE_COLUMNS
        product_where = [
            "p.list_date IS NOT NULL AND p.list_date != ''",
            f"{date_col} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            f'{date_col} <= ?',
            f"date(?, '-' || ? || ' day') <= {date_col}",
        ]
        product_params = [end_date, end_date, NEW_PRODUCT_WINDOW_DAYS]
        if filters.get('shop_label'):
            label = filters['shop_label']
            product_where.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
            product_params.extend([label, label])
        if filters.get('product_id'):
            product_where.append('p.product_id = ?')
            product_params.append(filters['product_id'])

        fact_where = [
            "(pdf.grain IN ('product', 'unit') OR pdf.grain = '')",
            'pdf.shop_id = ?',
            'pdf.date BETWEEN ? AND ?',
            "pdf.product_id != ''",
        ]
        fact_params = [shop_id, start_date, end_date]
        for key in ('channel', 'campaign_id', 'unit_id', 'product_id'):
            if filters.get(key):
                fact_where.append(f'pdf.{key} = ?')
                fact_params.append(filters[key])

        with get_db() as connection:
            rows = connection.execute(
                f'''WITH candidates AS (
                        SELECT p.product_id, {date_col} AS list_date
                        FROM products p
                        WHERE {' AND '.join(product_where)}
                    ), facts AS (
                        SELECT pdf.product_id,
                               SUM(COALESCE(pdf.ad_spend, 0)) AS ad_spend,
                               SUM(COALESCE(pdf.attributed_payment_amount, 0)) AS attributed_payment_amount,
                               SUM(COALESCE(pdf.impressions, 0)) AS impressions,
                               SUM(COALESCE(pdf.clicks, 0)) AS clicks,
                               SUM(COALESCE(pdf.payment_buyers, 0)) AS payment_buyers,
                               SUM(COALESCE(pdf.cart_adds, 0)) AS cart_adds,
                               SUM(COALESCE(pdf.new_buyers, 0)) AS new_buyers
                        FROM promotion_daily_facts pdf
                        WHERE {' AND '.join(fact_where)}
                        GROUP BY pdf.product_id
                    ), links AS (
                        SELECT dd.product_id,
                               SUM(COALESCE(dd.payment_amount, 0)) AS link_gsv,
                               SUM(COALESCE(NULLIF(dd.net_sales, 0), dd.payment_amount - dd.refund_amount, 0)) AS link_net_sales
                        FROM daily_data dd
                        WHERE dd.shop_id = ? AND dd.date BETWEEN ? AND ?
                        GROUP BY dd.product_id
                    )
                    SELECT c.list_date,
                           COUNT(*) AS total_product_count,
                           SUM(CASE WHEN f.product_id IS NOT NULL THEN 1 ELSE 0 END) AS promoted_product_count,
                           SUM(CASE WHEN f.product_id IS NULL THEN 1 ELSE 0 END) AS unpromoted_product_count,
                           COALESCE(SUM(f.ad_spend), 0) AS ad_spend,
                           COALESCE(SUM(f.attributed_payment_amount), 0) AS attributed_payment_amount,
                           COALESCE(SUM(f.impressions), 0) AS impressions,
                           COALESCE(SUM(f.clicks), 0) AS clicks,
                           COALESCE(SUM(f.payment_buyers), 0) AS payment_buyers,
                           COALESCE(SUM(f.cart_adds), 0) AS cart_adds,
                           COALESCE(SUM(f.new_buyers), 0) AS new_buyers,
                           COALESCE(SUM(l.link_gsv), 0) AS link_gsv,
                           COALESCE(SUM(l.link_net_sales), 0) AS link_net_sales
                    FROM candidates c
                    LEFT JOIN facts f ON f.product_id = c.product_id
                    LEFT JOIN links l ON l.product_id = c.product_id
                    GROUP BY c.list_date
                    ORDER BY c.list_date DESC''',
                [*product_params, *fact_params, shop_id, start_date, end_date],
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # 新老品 × 渠道投放矩阵（/promotion-matrix）
    # ------------------------------------------------------------------

    @staticmethod
    def _table_exists(connection, name):
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    @staticmethod
    def product_channel_facts(start_date, end_date, filters=None):
        """商品 × 渠道投放事实（创意明细口径）。

        覆盖 `promotion_creative_daily` 已有的渠道（关键词/人群/店铺直达）。
        全站推广不在该表内，由调用方用计划 1:1 精确归因补全
        （见 `services/promotion_matrix_service.py`），两边口径相加不重复。
        """
        shop_id = get_shop_id()
        filters = filters or {}
        where = ['f.shop_id = ?', 'f.date BETWEEN ? AND ?', "f.product_id != ''"]
        params = [shop_id, start_date, end_date]
        if filters.get('channel'):
            where.append('f.channel = ?')
            params.append(filters['channel'])
        if filters.get('product_id'):
            where.append('f.product_id = ?')
            params.append(filters['product_id'])
        category_sql, category_params = '', []
        if filters.get('shop_label'):
            label = filters['shop_label']
            category_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            category_params = [label, label]
        with get_db() as connection:
            if not PromotionRepo._table_exists(connection, 'promotion_creative_daily'):
                return []
            rows = connection.execute(
                f'''SELECT f.product_id, f.channel,
                           SUM(COALESCE(f.ad_spend, 0)) AS ad_spend,
                           SUM(COALESCE(f.attributed_payment_amount, 0)) AS attributed_payment,
                           SUM(COALESCE(f.direct_payment_amount, 0)) AS direct_payment,
                           SUM(COALESCE(f.impressions, 0)) AS impressions,
                           SUM(COALESCE(f.clicks, 0)) AS clicks,
                           SUM(COALESCE(f.payment_buyers, 0)) AS payment_buyers,
                           SUM(COALESCE(f.cart_adds, 0)) AS cart_adds,
                           SUM(COALESCE(f.new_buyers, 0)) AS new_buyers
                    FROM promotion_creative_daily f
                    LEFT JOIN products p ON p.product_id = f.product_id
                    WHERE {' AND '.join(where)}{category_sql}
                    GROUP BY f.product_id, f.channel
                    HAVING SUM(COALESCE(f.ad_spend, 0)) > 0''',
                [*params, *category_params],
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def products_meta(product_ids):
        """批量取商品主数据（标题/主图/品类/上架日），供矩阵页补全商品身份。"""
        ids = [str(pid) for pid in product_ids if pid]
        if not ids:
            return {}
        rows = []
        with get_db() as connection:
            for start in range(0, len(ids), 400):
                chunk = ids[start:start + 400]
                placeholders = ','.join('?' for _ in chunk)
                rows.extend(connection.execute(
                    f'''SELECT p.product_id,
                               MAX(p.title) AS title,
                               MAX(NULLIF(p.image_url, '')) AS image_url,
                               MAX(COALESCE(p.shop_label, '')) AS shop_label,
                               MAX({PromotionRepo.NEW_DATE_COLUMNS}) AS list_date
                        FROM products p
                        WHERE p.product_id IN ({placeholders})
                        GROUP BY p.product_id''',
                    chunk,
                ).fetchall())
        return {row['product_id']: dict(row) for row in rows}

    @staticmethod
    def link_sales_by_product(start_date, end_date, product_ids):
        """周期内商品链接销售额/净销售额（daily_data），用于矩阵页费比。"""
        ids = [str(pid) for pid in product_ids if pid]
        if not ids:
            return {}
        shop_id = get_shop_id()
        rows = []
        with get_db() as connection:
            for start in range(0, len(ids), 400):
                chunk = ids[start:start + 400]
                placeholders = ','.join('?' for _ in chunk)
                rows.extend(connection.execute(
                    f'''SELECT dd.product_id,
                               SUM(COALESCE(dd.payment_amount, 0)) AS link_gsv,
                               SUM(COALESCE(dd.payment_amount, 0) - COALESCE(dd.refund_amount, 0)) AS link_net_sales
                        FROM daily_data dd
                        WHERE dd.shop_id = ? AND dd.date BETWEEN ? AND ?
                          AND dd.product_id IN ({placeholders})
                        GROUP BY dd.product_id''',
                    [shop_id, start_date, end_date, *chunk],
                ).fetchall())
        return {row['product_id']: dict(row) for row in rows}

    @staticmethod
    def bill_totals(start_date, end_date, filters=None):
        """账单口径商品级合计（grain='product' + channel='全部'），做覆盖率分母。

        矩阵页的商品×渠道明细只有 8 成多覆盖，这里给出同周期的账单口径总盘，
        让页面能显式标出「未归因」而不是让读者以为明细就是全部。
        """
        shop_id = get_shop_id()
        filters = filters or {}
        where = ["f.shop_id = ?", "f.date BETWEEN ? AND ?",
                 "f.grain = 'product'", "f.channel = '全部'"]
        params = [shop_id, start_date, end_date]
        if filters.get('product_id'):
            where.append('f.product_id = ?')
            params.append(filters['product_id'])
        category_sql, category_params = '', []
        if filters.get('shop_label'):
            label = filters['shop_label']
            category_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            category_params = [label, label]
        with get_db() as connection:
            row = connection.execute(
                f'''SELECT SUM(COALESCE(f.ad_spend, 0)) AS ad_spend,
                           SUM(COALESCE(f.attributed_payment_amount, 0)) AS attributed_payment,
                           COUNT(DISTINCT f.date) AS sample_days
                    FROM promotion_daily_facts f
                    LEFT JOIN products p ON p.product_id = f.product_id
                    WHERE {' AND '.join(where)}{category_sql}''',
                [*params, *category_params],
            ).fetchone()
        return dict(row) if row else {}

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
