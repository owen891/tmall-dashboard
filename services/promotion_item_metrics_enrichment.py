"""把万相台后台采集的推广事实回填到商品列表接口。

为什么需要
----------
商品列表「推广与付费」分组下的绝大多数列（展现量、点击量、点击率、点击单价、
千次展现花费、直接/总成交额、加购次数、加购成本、新买家数、新买家占比、
点击转化率）在 `api/products_legacy_api.py` 里是从 `paid_detail` 取的，
而 `paid_detail` 实测是 **0 行** —— 这张表从来没有被采集链路写过。
所以这些列长期显示 `--`。

真实数据在 `promotion_daily_facts`（万相台后台采集，150201 行，日期覆盖
2025-09-01 ~ 2026-10-21）。仓库已有标准口径（`scripts/promo_review/build_data.py:326-340`）：

    grain='product' AND channel='全部' AND product_id NOT LIKE '-%'

这是**唯一带商品 ID 的完整商品级汇总**；其它 grain（campaign/unit/account）
行不带商品映射或会重复计数，绝不能混进来。

口径边界（照抄仓库既有结论，不要越界）
------------------------------------
1. `attributed_payment_amount`（归因成交）**不含间接成交**——
   `indirect_payment_amount` 全表 nn=0。所以它比真实成交额偏小，
   与账单口径的 `ad_spend` 不同源、不可相减（见 `scripts/promo_review/gen_report.py:1341`）。
2. 因此 `total_gmv` 用归因成交、`indirect_gmv` 保持 NULL（不拿 0 冒充"没有间接成交"）。
3. `cart_cost` 是**单位成本**，不能按行 SUM；用 花费/加购次数 重新推导。
4. 花费类列（cost / total_cost）不填——列表里已有账单口径的 `ad_spend`，
   再塞一个归因口径的花费会让同一屏出现两个不同数字。

与达摩盘回填的关系
------------------
两个模块互不重叠：达摩盘补复购/连带/免费搜索点击率/预售，本模块补推广转化。
都遵守「只填 NULL、不覆盖主源已有值」。
"""

from services.dmp_item_metrics import _prepare_connection

SOURCE_TABLE = 'promotion_daily_facts'

# 汇总 SQL 直接算出的原始量。
_RAW_FIELDS = (
    'impressions',
    'clicks',
    'ad_spend',
    'attributed_payment_amount',
    'direct_payment_amount',
    'indirect_payment_amount',
    'cart_adds',
    'new_buyers',
    'payment_buyers',
)

# 允许回填到商品列表的字段（只填 NULL）。
FILLABLE_FIELDS = (
    'impressions',
    'clicks',
    'direct_gmv',
    'indirect_gmv',
    'total_gmv',
    'cart_adds',
    'new_buyers',
)


def _has_source_table(conn):
    try:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (SOURCE_TABLE,),
        ).fetchone())
    except Exception:
        return False


def _ratio(numerator, denominator):
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError):
        return None


def fetch_promotion_metrics(conn, product_ids, start, end):
    """按商品聚合推广事实。返回 {product_id: metrics dict}。

    只返回**真实存在推广行**的商品；没有推广的商品不出现，对应字段保持 NULL
    （而不是被填成 0，因为"没投"和"投了但为 0"在业务上不同）。
    """
    if not product_ids or not start or not end:
        return {}
    if not _has_source_table(conn):
        return {}
    _prepare_connection(conn)
    placeholders = ','.join(['?'] * len(product_ids))
    sql = f'''
        SELECT f.product_id,
               SUM(COALESCE(f.impressions, 0)) AS impressions,
               SUM(COALESCE(f.clicks, 0)) AS clicks,
               SUM(COALESCE(f.ad_spend, 0)) AS ad_spend,
               SUM(COALESCE(f.attributed_payment_amount, 0)) AS attributed_payment_amount,
               SUM(COALESCE(f.direct_payment_amount, 0)) AS direct_payment_amount,
               SUM(COALESCE(f.cart_adds, 0)) AS cart_adds,
               SUM(COALESCE(f.new_buyers, 0)) AS new_buyers,
               SUM(COALESCE(f.payment_buyers, 0)) AS payment_buyers,
               SUM(f.indirect_payment_amount) AS indirect_payment_amount,
               COUNT(*) AS fact_rows
        FROM {SOURCE_TABLE} f
        WHERE f.date BETWEEN ? AND ?
          AND f.grain = 'product'
          AND f.channel = '全部'
          AND f.product_id NOT LIKE '-%'
          AND f.product_id IN ({placeholders})
        GROUP BY f.product_id
    '''
    params = [str(start)[:10], str(end)[:10]] + [str(p) for p in product_ids]
    try:
        records = conn.execute(sql, params).fetchall()
    except Exception:
        return {}

    metrics = {}
    for fact in records:
        record = dict(fact)
        product_id = str(record.get('product_id'))
        spend = record.get('ad_spend')
        clicks = record.get('clicks')
        impressions = record.get('impressions')
        carts = record.get('cart_adds')
        buyers = record.get('payment_buyers')
        record['ctr'] = _ratio(clicks, impressions)
        record['cpc'] = _ratio(spend, clicks)
        record['cpm'] = (spend / impressions * 1000.0) if _ratio(spend, impressions) is not None else None
        record['cart_cost'] = _ratio(spend, carts)
        record['new_buyer_ratio'] = _ratio(record.get('new_buyers'), buyers)
        record['click_conversion'] = _ratio(buyers, clicks)
        # 商品列表字段名 → 事实表列名。
        # direct_gmv=直接成交额、total_gmv=归因成交额（不含间接，见模块头说明）、
        # indirect_gmv 保持事实表原值（全表为空 → None，不伪造成 0）。
        record['direct_gmv'] = record.get('direct_payment_amount')
        record['total_gmv'] = record.get('attributed_payment_amount')
        record['indirect_gmv'] = record.get('indirect_payment_amount')
        # 归因成交不含间接成交（该列全表为空），此处不推导间接。
        metrics[product_id] = record
    return metrics


def enrich_rows(conn, rows, start, end):
    """用推广事实补齐 rows 里缺失的推广字段（原地修改并返回元信息）。

    返回 `{'applied': bool, 'filled': {product_id: n}, 'matched_items': n}`。
    """
    if not rows:
        return {'applied': False, 'reason': 'no rows'}
    product_ids = [str(row.get('product_id')) for row in rows if row.get('product_id')]
    if not product_ids:
        return {'applied': False, 'reason': 'no product ids'}
    metrics = fetch_promotion_metrics(conn, product_ids, start, end)
    if not metrics:
        return {'applied': False, 'reason': 'no promotion facts'}

    filled = {}
    for row in rows:
        product_id = str(row.get('product_id') or '')
        record = metrics.get(product_id)
        if not record:
            continue
        count = 0
        # 直接量：只填 NULL，且行里必须本来就有这一列。
        for field in FILLABLE_FIELDS:
            if field not in row or field not in record:
                continue
            incoming = record[field]
            if incoming is None:
                continue
            if row.get(field) is not None:
                continue
            # 归因成交为 0 且该商品只有 0 花费时，保留 NULL 更诚实。
            row[field] = incoming
            count += 1
        # 推导量：同样是只填 NULL。
        for field in ('ctr', 'cpc', 'cpm', 'cart_cost', 'new_buyer_ratio', 'click_conversion'):
            if field not in row or field not in record:
                continue
            incoming = record[field]
            if incoming is None:
                continue
            if row.get(field) is not None:
                continue
            row[field] = incoming
            count += 1
        if count:
            filled[product_id] = count

    return {
        'applied': bool(filled),
        'filled': filled,
        'matched_items': len(metrics),
    }


def source_metadata(rows_count):
    """接口层披露用。"""
    return {
        'source': SOURCE_TABLE,
        'grain': 'product',
        'channel': '全部',
        'fields': list(FILLABLE_FIELDS) + [
            'ctr', 'cpc', 'cpm', 'cart_cost', 'new_buyer_ratio', 'click_conversion',
        ],
        'matched_items': rows_count,
    }
