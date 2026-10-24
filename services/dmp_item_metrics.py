"""达摩盘货品洞察单品指标 → 商品列表指标的回填桥。

为什么要这个模块
----------------
`daily_data` 里的下面这些列从来没有被采集链路写过非零值（2026-10-22 全表扫描：
1057829 行中仅 47737 行 notnull，且这些行**全部为 0**）：

    repurchase_rate / repurchase_users / search_click_rate / category_width /
    cross_sell_qty / cross_sell_rate / presale_amount / presale_qty

所以商品列表这些列长期显示 `--`（`api/products_legacy_api.py` 用 `NULLIF(x,0)`
把"没采到的 0"还原成 NULL）。唯一真实来源是达摩盘「货品洞察-全店洞察」快照表
`dmp_shop_item_indicators`（7 天 / 30 天滚动窗口，`end_date` 为窗口末日），
实测 run5/period=7 覆盖 1593 个单品，其中 1584 个能与 `daily_data` 的
product_id 对上。

`industry_ctr`（行业点击率）取的是同一个指标的 `peer_value`（同行同层），
而不是 `value`（本店），见 `DMP_PEER_FIELDS`。

窗口语义（关键，不能放松）
--------------------------
快照是**滚动窗口**，不是单日事实。同一个 `rebuyRate` 在 7 天窗口和 30 天窗口
里含义完全不同，所以：

1. 精确对齐：请求区间天数 == 快照 `period` 且请求末日 == 快照 `end_date`。
   此时快照值就是本期口径。
2. 最近快照：请求区间天数 == 快照 `period`，快照 `end_date` 落在请求末日前
   不超过 `MAX_ALIGN_GAP_DAYS` 天。此时仍是同长度的真实窗口，只是窗口末日
   与所选区间末日有几天错位——必须通过 `aligned_days` 向前端披露，不能静默
   当成"本期"。

天数对不上（例如用 7 天快照冒充 30 天区间）一律返回 None，让列表继续显示
`--`。这与 `services/period_context_ads.py::_dmp_traffic_dimension` 已有的
「宁可返回 None 退回 daily_data，也绝不拿错窗口数据冒充本期」口径一致。
"""

from datetime import date, datetime, timedelta

# 达摩盘 ind_key → daily_data / 商品列表字段名。
# 依据 dmp_shop_indicator_dict（ind_name 为 GBK 存储，需
# `s.encode('latin-1').decode('gbk')` 才能读出中文）实测确认：
#   searchCtr = 免费搜索点击率、relatedAlipayCateCnt = 连带购买叶子类目宽度、
#   relatedAlipayCnt = 连带购买量、relatedAlipayRate = 连带购买率、
#   rebuyRate = 复购率、rebuyUv = 复购用户数、
#   preAlipayAmt = 预售支付金额、preAlipayCnt = 预售销量。
DMP_INDICATOR_FIELDS = {
    'searchCtr': 'search_click_rate',
    'relatedAlipayCateCnt': 'category_width',
    'rebuyRate': 'repurchase_rate',
    'rebuyUv': 'repurchase_users',
    'relatedAlipayCnt': 'cross_sell_qty',
    'relatedAlipayRate': 'cross_sell_rate',
    'preAlipayAmt': 'presale_amount',
    'preAlipayCnt': 'presale_qty',
}

# 达摩盘 `peer_value`（同行同层）→ 商品列表字段名。
# 用户 2026-10-22 明确要求「行业搜索点击率」走达摩盘口径：
# `searchCtr` 的 `peer_value` 就是平台给出的同行同层搜索点击率，
# 实测 run5/period7 覆盖 1593/1593 且全非零。
# 列名沿用列表既有的 `industry_ctr`（行业点击率）。
# ⚠️ 口径是「同行同层」不是「全行业」，响应 limitations 里要写明。
DMP_PEER_FIELDS = {
    'searchCtr': 'industry_ctr',
}

# 达摩盘 row_json 原始键 → 商品列表字段名。
# 这几个是「流量来源拆分」，只在 `dmp_shop_items.row_json` 里有，
# `dmp_shop_item_indicators` 的 34 个 ind_key 里没有对应项（实测）。
# 与 `services/period_context_ads.py::_dmp_traffic_dimension` 用的是同一批键，
# 口径一致：paidIpv=付费访客、freeIpv=自然访客（含搜索+推荐）、
# recommendFreeIpv=推荐访客。
DMP_TRAFFIC_FIELDS = {
    'paidIpv': 'paid_ipv',
    'freeIpv': 'organic_ipv',
    'recommendFreeIpv': 'recommend_ipv',
}

# 允许「最近快照」的最大末日错位。达摩盘数据 T-1/T-2 收口，再放宽就会把
# 一周前的窗口当成今天。
MAX_ALIGN_GAP_DAYS = 7

SOURCE_TABLE = 'dmp_shop_item_indicators'
TRAFFIC_TABLE = 'dmp_shop_items'


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _prepare_connection(conn):
    """把临时表放内存。

    本库是 23 GB 的 WAL 库，`GROUP BY` 透视 40 万行指标时 SQLite 默认要在
    磁盘建临时 b-tree；在只读连接 / 受限 TEMP 目录下会直接抛
    `sqlite3.OperationalError: unable to open database file`（实测第二次查询
    必失败）。放内存后稳定，且这批透视结果只有几千行。
    """
    try:
        conn.execute('PRAGMA temp_store=MEMORY')
    except Exception:
        pass


def _has_source_table(conn):
    try:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (SOURCE_TABLE,),
        ).fetchone())
    except Exception:
        return False


def resolve_dmp_snapshot(conn, start, end):
    """找出与请求区间对齐的达摩盘单品快照。

    返回 dict（含 run_id / period / end_date / aligned_days / sql / fields），
    没有可用快照或天数对不上时返回 None。
    """
    start_date, end_date = _parse_iso(start), _parse_iso(end)
    if not start_date or not end_date or start_date > end_date:
        return None
    days = (end_date - start_date).days + 1
    if days < 1:
        return None
    if not _has_source_table(conn):
        return None

    _prepare_connection(conn)
    try:
        rows = conn.execute(
            f'''SELECT MAX(run_id) AS run_id
                FROM {SOURCE_TABLE}
                WHERE period = ? AND end_date <= ?
                GROUP BY end_date
                ORDER BY end_date DESC
                LIMIT 1''',
            (days, end.isoformat() if hasattr(end, 'isoformat') else str(end)[:10]),
        ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    run_id = rows[0]['run_id'] if hasattr(rows[0], 'keys') else rows[0][0]
    if run_id is None:
        return None

    # 取该 run 内同 period 的最大 end_date，并校验错位天数。
    snapshot = conn.execute(
        f'''SELECT run_id, period, end_date
            FROM {SOURCE_TABLE}
            WHERE run_id = ? AND period = ?
            ORDER BY end_date DESC
            LIMIT 1''',
        (run_id, days),
    ).fetchone()
    if not snapshot:
        return None
    snapshot_end = _parse_iso(snapshot['end_date'])
    if not snapshot_end:
        return None
    gap = (end_date - snapshot_end).days
    if gap < 0 or gap > MAX_ALIGN_GAP_DAYS:
        return None

    # 单品维度的指标透视。run_id / period 都是库内整数，直接内联进 SQL，
    # 这样不会打乱上层查询的 params 顺序。
    run_id = int(snapshot['run_id'])
    period = int(snapshot['period'])
    pivot_columns = []
    for ind_key, field in DMP_INDICATOR_FIELDS.items():
        pivot_columns.append(
            f"MAX(CASE WHEN ind_key = '{_escape_literal(ind_key)}' THEN value END) AS {field}"
        )
    for ind_key, field in DMP_PEER_FIELDS.items():
        pivot_columns.append(
            f"MAX(CASE WHEN ind_key = '{_escape_literal(ind_key)}' THEN peer_value END) AS {field}"
        )
    sql = (
        '(SELECT item_id, '
        + ', '.join(pivot_columns)
        + f' FROM {SOURCE_TABLE} WHERE run_id = {run_id} AND period = {period}'
        + ' GROUP BY item_id)'
    )
    traffic_sql = _build_traffic_sql(conn, run_id, period)
    return {
        'run_id': run_id,
        'period': period,
        'end_date': str(snapshot['end_date'])[:10],
        'aligned_days': gap,
        'exact': gap == 0,
        'sql': sql,
        'traffic_sql': traffic_sql,
        'fields': (
            tuple(DMP_INDICATOR_FIELDS.values())
            + tuple(DMP_PEER_FIELDS.values())
            + tuple(DMP_TRAFFIC_FIELDS.values())
        ),
    }


def _has_traffic_table(conn):
    try:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (TRAFFIC_TABLE,),
        ).fetchone())
    except Exception:
        return False


def _build_traffic_sql(conn, run_id, period):
    """从 row_json 抽流量来源拆分。

    `dmp_shop_items` 在 (run_id, period, item_id) 上是唯一行（实测 run5/p7
    1593 行 = 1593 个单品），所以不需要聚合。`json_valid` 防御坏 JSON。
    """
    if not _has_traffic_table(conn):
        return None
    columns = []
    for json_key, field in DMP_TRAFFIC_FIELDS.items():
        columns.append(
            "CASE WHEN json_valid(row_json) "
            f"THEN json_extract(row_json, '$.{_escape_literal(json_key)}') END AS {field}"
        )
    return (
        '(SELECT item_id, ' + ', '.join(columns)
        + f' FROM {TRAFFIC_TABLE} WHERE run_id = {run_id} AND period = {period})'
    )


def _escape_literal(value):
    """ind_key 全部是字母数字，这里只做防御性处理。"""
    return str(value).replace("'", "''")
