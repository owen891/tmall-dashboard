# -*- coding: utf-8 -*-
"""生意参谋数据API
流量来源、竞店竞品、市场排行等数据查询接口
"""
from datetime import date as date_type, timedelta
from flask import Blueprint, request, jsonify
from api.api_response import success, failure

sycm_bp = Blueprint('sycm', __name__, url_prefix='/api/sycm')


from repos.sycm_repo import (
    expected_days as _expected_days,
    latest_date as _repo_latest_date,
    rival_trend as _repo_rival_trend,
    rival_entities as _repo_rival_entities,
    rival_entity_trend as _repo_rival_entity_trend,
    flow_source_level1 as _repo_flow_level1,
    flow_source_level2 as _repo_flow_level2,
    flow_source_recent_trend as _repo_flow_recent_trend,
    shop_tree_group_map as _repo_shop_tree_group_map,
    item_flow_source_dates as _repo_item_flow_dates,
    item_flow_channel_rollup as _repo_item_flow_channels,
    item_flow_product_totals as _repo_item_flow_product_totals,
    item_flow_top_items as _repo_item_flow_top_items,
    competitor_item_table as _repo_competitor_item_table,
    rival_shop_day_list as _repo_rival_shop_day_list,
    rival_shop_day_summary as _repo_rival_shop_day_summary,
    rival_items_day_list as _repo_rival_items_day_list,
    market_item_rank_rows as _repo_market_item_rank_rows,
    market_item_rank_result as _repo_market_item_rank_result,
    NativeMarketReadError as _NativeMarketReadError,
    market_search_rank_rows as _repo_market_search_rank_rows,
    market_category_list as _repo_market_category_list,
    market_item_sample_daily as _repo_market_item_sample_daily,
    market_search_daily as _repo_market_search_daily,
    market_keyword_heat_rows as _repo_market_keyword_heat_rows,
    market_item_rank_window_rows as _repo_market_item_rank_window_rows,
    market_shop_entities as _repo_market_shop_entities,
    market_shop_entity_trend as _repo_market_shop_entity_trend,
    market_item_entities as _repo_market_item_entities,
    market_item_entity_trend as _repo_market_item_entity_trend,
    snapshot_batches as _repo_snapshot_batches,
    snapshot_batch_rows as _repo_snapshot_batch_rows,
)


def get_latest_date(table, date_col='stat_date'):
    """获取最新数据日期（实现已下沉 repos/sycm_repo.py）"""
    return _repo_latest_date(table, date_col)


def get_query_date_range(table):
    """Resolve a single date or the selected inclusive date range."""
    single = request.args.get('date')
    end_date = request.args.get('end') or request.args.get('end_date') or single
    start_date = request.args.get('start') or request.args.get('start_date') or single
    end_date = end_date or get_latest_date(table)
    start_date = start_date or end_date
    return start_date, end_date


def _competitor_item_table():
    """实现已下沉 repos/sycm_repo.py。"""
    return _repo_competitor_item_table()





# ==================== 流量来源 ====================

@sycm_bp.route('/flow-source/summary', methods=['GET'])
def flow_source_summary():
    """流量来源汇总：一级渠道数据"""
    start_date, end_date = get_query_date_range('sycm_flow_source_daily')
    if not end_date:
        return failure('NO_DATA', '暂无流量来源数据')

    level1 = _repo_flow_level1(start_date, end_date)
    total_uv = sum(ch['uv'] or 0 for ch in level1)
    total_pay = sum(ch['pay_amount'] or 0 for ch in level1)

    return success({
        'stat_date': end_date,
        'start_date': start_date,
        'end_date': end_date,
        'belong': 'farthest',
        'belong_name': '第一次访问来源',
        'total_uv': total_uv,
        'total_pay_amount': total_pay,
        'level1_channels': level1,
    })


@sycm_bp.route('/flow-source/detail', methods=['GET'])
def flow_source_detail():
    """流量来源详情：二级渠道数据"""
    start_date, end_date = get_query_date_range('sycm_flow_source_daily')
    parent = request.args.get('parent', '')
    if not end_date:
        return failure('NO_DATA', '暂无流量来源数据')

    channels = _repo_flow_level2(start_date, end_date, parent)
    return success({'stat_date': end_date, 'start_date': start_date, 'end_date': end_date, 'channels': channels})


@sycm_bp.route('/flow-source/trend', methods=['GET'])
def flow_source_trend():
    """流量来源趋势：最近N天的一级渠道数据"""
    days = int(request.args.get('days', 14))
    trend = _repo_flow_recent_trend(days)
    dates = sorted(trend.keys())
    return success({
        'dates': dates,
        'trend': {d: trend[d] for d in dates},
    })


# ==================== 单品流量来源 ====================

# 参与聚合/合成的指标列（渠道行与合成分组行共用）
_CHANNEL_METRIC_KEYS = (
    'uv', 'pv', 'pay_amount', 'pay_buyer_count', 'cart_buyer_count',
    'collect_item_count', 'new_uv', 'deal_buyer_count', 'pay_item_count',
)


def _empty_channel(name, parent, level):
    channel = {'channel_name': name, 'parent_channel': parent, 'level': level,
               'channel_type': None, 'pay_rate': 0, 'parent_derived': False,
               'synthetic': False}
    for key in _CHANNEL_METRIC_KEYS:
        channel[key] = 0
    return channel


def _item_flow_no_data(item_id, belong, requested_start, requested_end, message):
    """范围内无数据回 200 + no-data 信封而非 400。

    前端两个消费方（product-detail-dialog / product-detail-live）都以
    「channels 为空」渲染空态或回退另一口径；400 会让 domainRequest 直接 throw、
    且被 audit_core_interactions 记为 browserError（products 页长期基线失败项）。
    """
    return success({
        'item_id': item_id or None,
        'belong': belong,
        'stat_date': None,
        'start_date': None,
        'end_date': None,
        'requested_start': requested_start,
        'requested_end': requested_end,
        'data_dates': [],
        'data_days': 0,
        'is_range': False,
        'total_uv': 0,
        'total_pay_amount': 0,
        'channel_totals': {'uv': 0, 'pv': 0, 'pay_amount': 0, 'pay_buyer_count': 0, 'leaf_channels': 0},
        'product_totals': None,
        'derived_parent_count': 0,
        'hierarchy_source': 'api' if belong == 'all' else 'shop_tree',
        'levels': [],
        'channels': [],
    }, availability='no-data', evidence_level='insufficient', limitations=[message])


@sycm_bp.route('/item-flow/summary', methods=['GET'])
def item_flow_summary():
    """单品流量来源汇总

    查询参数：
        item_id   商品 ID，可选；不传则按渠道汇总全部单品
        date      单日，可选（默认取表内最新日期）
        start/end 日期范围，优先级高于 date
        belong    farthest=第一次访问来源（默认）
                  all=全程来源（接口自带多级渠道树）

    层级说明：
        all 口径自带多级父子关系（付费推广 → 无界 → 关键词推广）。
        farthest 口径接口只返回平铺一层，早前父级全空，前端因此无法下钻；
        现在会按「店铺渠道树上溯」补出根层分组（平台流量 / 广告流量…），
        并合成分组行，使两种口径都能正常逐级下钻/回退。

    刻意返回两套口径，避免把「渠道相加」误当成「商品总计」：
        channel_totals —— 渠道明细合计，只统计**叶子渠道**（不再把父级和子级重复相加）。
        product_totals —— 商品维度真实值，取自 daily_data
                          （ipv / pv / 支付金额 / 买家数），与商品经营口径一致。
    两者都用「流量来源表在所选范围内实际有数据的日期」计算，保证时间窗一致。
    """
    item_id = (request.args.get('item_id') or '').strip()
    belong = (request.args.get('belong') or 'farthest').strip() or 'farthest'
    start_arg = (request.args.get('start') or '').strip()
    end_arg = (request.args.get('end') or '').strip()
    date_arg = (request.args.get('date') or '').strip()

    if start_arg and end_arg:
        bound_start, bound_end = sorted((start_arg, end_arg))
    elif date_arg:
        bound_start = bound_end = date_arg
    else:
        latest = get_latest_date('sycm_item_flow_source_daily')
        if not latest:
            return _item_flow_no_data(item_id, belong, start_arg or date_arg or None,
                                      end_arg or date_arg or None, '暂无单品流量来源数据')
        bound_start = bound_end = latest

    # 日期口径必须跟着 belong 走：全程来源(all)目前只有个别日期有数据，
    # 若这里不过滤 belong，就会出现「渠道侧 1 天、商品侧 10 天」的时间窗错配。
    dates = _repo_item_flow_dates(bound_start, bound_end, belong)
    if not dates:
        return _item_flow_no_data(item_id, belong, bound_start, bound_end,
                                  '所选范围内暂无单品流量来源数据')

    channels = _repo_item_flow_channels(bound_start, bound_end, belong, item_id)

    # ---- 补层级：只有「全程来源」自带父子关系，其余口径用店铺渠道树上溯 ----
    derived_count = 0
    if channels:
        group_map = _repo_shop_tree_group_map()
        present = {ch['channel_name'] for ch in channels}
        for ch in channels:
            if ch['parent_channel']:
                continue
            group = group_map.get(ch['channel_name'])
            if group and group != ch['channel_name'] and group not in present:
                ch['parent_channel'] = group
                ch['parent_derived'] = True
                ch['level'] = 1
                derived_count += 1

    # ---- 合成分组行（父级没有自己的数据行时补一行，否则前端下钻会落空）----
    groups = {}
    present = {ch['channel_name'] for ch in channels}
    for ch in channels:
        parent = ch['parent_channel']
        if not parent or parent in present:
            continue
        bucket = groups.setdefault(parent, _empty_channel(parent, '', 0))
        for key in _CHANNEL_METRIC_KEYS:
            bucket[key] = (bucket[key] or 0) + (ch.get(key) or 0)
    for name in sorted(groups, key=lambda n: -(groups[n]['uv'] or 0)):
        bucket = groups[name]
        uv = bucket['uv'] or 0
        bucket['pay_amount'] = round(bucket['pay_amount'] or 0, 2)
        bucket['pay_rate'] = round((bucket['pay_buyer_count'] or 0) / uv, 6) if uv else 0
        bucket['synthetic'] = True
        channels.insert(0, bucket)

    # ---- 合计只算叶子渠道：父子同表时直接相加会重复计数 ----
    parent_names = {ch['parent_channel'] for ch in channels if ch['parent_channel']}
    leaves = [ch for ch in channels if ch['channel_name'] not in parent_names]
    total_uv = sum(ch['uv'] or 0 for ch in leaves)
    total_pv = sum(ch['pv'] or 0 for ch in leaves)
    total_pay = sum(ch['pay_amount'] or 0 for ch in leaves)
    total_buyers = sum(ch['pay_buyer_count'] or 0 for ch in leaves)
    levels = sorted({ch['level'] for ch in channels
                     if isinstance(ch['level'], int) and ch['level'] >= 0})

    product_totals = _repo_item_flow_product_totals(item_id, dates) if item_id else None

    return success({
        'item_id': item_id or None,
        'belong': belong,
        # 兼容旧字段：只在单日查询时有值
        'stat_date': dates[0] if len(dates) == 1 else None,
        'start_date': dates[0],
        'end_date': dates[-1],
        'requested_start': bound_start,
        'requested_end': bound_end,
        'data_dates': dates,
        'data_days': len(dates),
        'is_range': len(dates) > 1,
        'total_uv': total_uv,
        'total_pay_amount': round(total_pay, 2),
        'channel_totals': {
            'uv': total_uv,
            'pv': total_pv,
            'pay_amount': round(total_pay, 2),
            'pay_buyer_count': total_buyers,
            'leaf_channels': len(leaves),
        },
        'product_totals': product_totals,
        'derived_parent_count': derived_count,
        'hierarchy_source': 'api' if belong == 'all' else 'shop_tree',
        'levels': levels,
        'channels': channels,
    })


@sycm_bp.route('/item-flow/top-items', methods=['GET'])
def item_flow_top_items():
    """流量来源TOP商品"""
    stat_date = request.args.get('date') or get_latest_date('sycm_item_flow_source_daily')
    channel = request.args.get('channel', '')
    limit = int(request.args.get('limit', 20))
    items = _repo_item_flow_top_items(stat_date, channel, limit)
    return success({'stat_date': stat_date, 'channel': channel, 'items': items})


# ==================== 竞店分析 ====================

@sycm_bp.route('/rival-shops/list', methods=['GET'])
def rival_shops_list():
    """竞店列表"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_rival_shop')
    if not stat_date:
        return failure('NO_DATA', '暂无竞店数据')
    return success({'stat_date': stat_date, 'shops': _repo_rival_shop_day_list(stat_date)})


@sycm_bp.route('/rival-shops/summary', methods=['GET'])
def rival_shops_summary():
    """竞店分析汇总"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_rival_shop')
    if not stat_date:
        return failure('NO_DATA', '暂无竞店数据')

    summary, top_shops = _repo_rival_shop_day_summary(stat_date)
    return success({
        'stat_date': stat_date,
        'total_shops': summary[0],
        'avg_uv': summary[1],
        'avg_pay_buyers': summary[2],
        'avg_pay_rate': summary[3],
        'tmall_count': summary[4],
        'taobao_count': summary[5],
        'top_shops': top_shops,
    })


@sycm_bp.route('/rival-shops/trend', methods=['GET'])
def rival_shops_trend():
    """竞店周期趋势：返回实际采集日与覆盖口径，不将缺失日当作零。"""
    start_date, end_date = get_query_date_range('sycm_market_rival_shop')
    if not end_date:
        return failure('NO_DATA', '暂无竞店数据')
    payload = _repo_rival_trend('sycm_market_rival_shop', 'shop_id', start_date, end_date)
    if not payload or not payload['observed_days']:
        return failure('NO_DATA', '所选范围暂无竞店趋势数据')
    return success(payload)


@sycm_bp.route('/rival-shops/entity-trend', methods=['GET'])
def rival_shop_entity_trend():
    """One monitored shop's daily UV, buyers and conversion trend."""
    entity_id = request.args.get('shop_id', '').strip()
    if not entity_id:
        return failure('VALIDATION_ERROR', '缺少 shop_id')
    start_date, end_date = get_query_date_range('sycm_market_rival_shop')
    payload = _repo_rival_entity_trend('sycm_market_rival_shop', 'shop_id', entity_id, start_date, end_date)
    if not payload or not payload['observed_days']:
        return failure('NO_DATA', '所选范围暂无该竞店趋势数据')
    return success(payload)


@sycm_bp.route('/rival-shops/entities', methods=['GET'])
def rival_shop_entities():
    start_date, end_date = get_query_date_range('sycm_market_rival_shop')
    return success({'entities': _repo_rival_entities('sycm_market_rival_shop', 'shop_id', 'shop_name', start_date, end_date)})


# ==================== 竞品分析 ====================

@sycm_bp.route('/rival-items/list', methods=['GET'])
def rival_items_list():
    """竞品列表"""
    source_table = _competitor_item_table()
    stat_date = request.args.get('date') or get_latest_date(source_table)
    if not stat_date:
        return failure('NO_DATA', '暂无竞品数据')

    items, excluded_own_count = _repo_rival_items_day_list(source_table, stat_date)
    return success({'stat_date': stat_date, 'items': items, 'excluded_own_count': excluded_own_count})


@sycm_bp.route('/rival-items/trend', methods=['GET'])
def rival_items_trend():
    """竞品周期趋势：按实际采集日汇总推荐竞品样本。"""
    source_table = _competitor_item_table()
    start_date, end_date = get_query_date_range(source_table)
    if not end_date:
        return failure('NO_DATA', '暂无竞品数据')
    payload = _repo_rival_trend(source_table, 'item_id', start_date, end_date)
    if not payload or not payload['observed_days']:
        return failure('NO_DATA', '所选范围暂无竞品趋势数据')
    return success(payload)


@sycm_bp.route('/rival-items/entity-trend', methods=['GET'])
def rival_item_entity_trend():
    """One monitored competitor item daily trend."""
    entity_id = request.args.get('item_id', '').strip()
    if not entity_id:
        return failure('VALIDATION_ERROR', '缺少 item_id')
    source_table = _competitor_item_table()
    start_date, end_date = get_query_date_range(source_table)
    payload = _repo_rival_entity_trend(source_table, 'item_id', entity_id, start_date, end_date)
    if not payload or not payload['observed_days']:
        return failure('NO_DATA', '所选范围暂无该竞品趋势数据')
    return success(payload)


@sycm_bp.route('/rival-items/entities', methods=['GET'])
def rival_item_entities():
    source_table = _competitor_item_table()
    start_date, end_date = get_query_date_range(source_table)
    return success({'entities': _repo_rival_entities(source_table, 'item_id', 'title', start_date, end_date)})


# ==================== 市场排行（生意参谋新数据） ====================

def _market_rank_response(*, categories_only=False):
    """Use the app-bound authorized shop; client source options never select an owner."""
    from db import get_shop_id
    import sqlite3
    try:
        limit = 300 if categories_only else int(request.args.get('limit',50))
        payload = _repo_market_item_rank_result(
            request.args.get('date') or None, request.args.get('cate_id',''),request.args.get('cate_name',''),limit,
            shop_id=str(get_shop_id()),source=request.args.get('source','auto'),rank_type=request.args.get('rank_type','交易总量'))
    except _NativeMarketReadError as error:
        if str(error)=='native_reader_not_installed':
            return failure('ENVIRONMENT_ERROR','插件日报读取组件尚未配套部署',status=503)
        return failure('QUALITY_GATE_FAILED','插件日报来源或完整性校验未通过，未回退到其他来源',status=409)
    except PermissionError:
        return failure('UNSUPPORTED_SCOPE','历史市场数字表不支持所请求的店铺范围',status=422)
    except (ValueError,TypeError):
        return failure('VALIDATION_ERROR','日期、页数、来源或榜单筛选参数无效',status=422)
    except sqlite3.Error:
        return failure('ENVIRONMENT_ERROR','市场日报读取暂不可用',status=503)
    available = bool(payload['items'])
    pending = payload['pending_native_partitions']
    if categories_only:
        payload = {key:value for key,value in payload.items() if key!='items'}
    return success(payload,availability='available' if available else 'partial' if pending else 'no-data',
        capabilities=payload['capabilities'],filters={
            'shop_id':payload['shop_id'],'source':payload['requested_source'],'rank_type':payload['rank_type'],
            'cate_id':request.args.get('cate_id',''),'cate_name':request.args.get('cate_name','')},
        source_batches=payload['native_partitions'],evidence_level='partial' if available or pending else 'insufficient',
        limitations=payload['limitations'],freshness={'period':payload['stat_date'],'source_mode':payload['source_mode']})


@sycm_bp.route('/market/item-rank', methods=['GET'])
def market_item_rank():
    return _market_rank_response()


@sycm_bp.route('/market/search-rank', methods=['GET'])
def market_search_rank():
    """搜索排行榜"""
    stat_date = request.args.get('date') or get_latest_date('sycm_market_search_rank')
    cate_id = request.args.get('cate_id', '')
    cate_name = request.args.get('cate_name', '')
    limit = int(request.args.get('limit', 50))
    keywords = _repo_market_search_rank_rows(stat_date, cate_id, cate_name, limit)
    return success({'stat_date': stat_date, 'keywords': keywords})


@sycm_bp.route('/market/keyword-insights', methods=['GET'])
def market_keyword_insights():
    """关键词洞察：8大归类+词根需求 / 蓝海机会词 / 趋势节点（XMind 市场监控-行业）。

    口径迁移自月复盘 SKILL：蓝海=细分词高搜索×高转化（剔除泛词；供给覆盖
    字段未采集，用近似口径并标注）；趋势节点=近7天 vs 前置窗口日均增速。
    """
    from services.market_monitor_service import keyword_insights, blue_ocean_words
    end_date = (request.args.get('end') or request.args.get('end_date')
                or get_latest_date('sycm_market_search_rank'))
    start_date = request.args.get('start') or request.args.get('start_date')
    start_date = start_date or (date_type.fromisoformat(str(end_date)) - timedelta(days=29)).isoformat()
    rows = _repo_market_keyword_heat_rows(str(start_date), str(end_date))
    if not rows:
        return success(
            {'available': False, 'missing_inputs': ['sycm_market_search_rank'],
             'categories': [], 'blue_ocean': [], 'trend_nodes': {'rising': [], 'cooling': []}},
            availability='no-data',
            freshness={'period': f'{start_date}~{end_date}'},
        )
    payload = keyword_insights(str(start_date), str(end_date), [tuple(row) for row in rows])
    # 蓝海完整口径（SKILL 阶段二点五）：最新采集日在榜商品 title 匹配 → 每万覆盖。
    # 与近似口径（蓝海度）并存：近似口径看「有没有需求」，完整口径看「供给挤不挤」。
    item_titles = [row['title'] for row in _repo_market_item_rank_window_rows(
        str(end_date), str(end_date))]
    payload['blue_ocean_full'] = blue_ocean_words([tuple(row) for row in rows], item_titles)
    if item_titles:
        payload['limitations'] = [
            '蓝海分级依据「每万搜索覆盖」（最新采集日在榜商品 title 匹配）：<5 高潜蓝海、5-10 中等、>10 供给偏多。'
        ]
    return success(payload, freshness={'period': f'{start_date}~{end_date}'})


@sycm_bp.route('/market/rival-item-moves', methods=['GET'])
def market_rival_item_moves():
    """竞店爆品排名变化：商品榜窗口首尾对比（XMind 竞店-爆品排名变化）。"""
    from services.market_monitor_service import rival_item_moves
    end_date = (request.args.get('end') or request.args.get('end_date')
                or get_latest_date('sycm_market_item_rank'))
    start_date = request.args.get('start') or request.args.get('start_date')
    start_date = start_date or (date_type.fromisoformat(str(end_date)) - timedelta(days=13)).isoformat()
    rows = _repo_market_item_rank_window_rows(str(start_date), str(end_date))
    if not rows:
        return success(
            {'available': False, 'missing_inputs': ['sycm_market_item_rank'], 'shops': []},
            availability='no-data',
            freshness={'period': f'{start_date}~{end_date}'},
        )
    payload = rival_item_moves(str(start_date), str(end_date), [tuple(row) for row in rows])
    return success(payload, freshness={'period': f'{start_date}~{end_date}'})


@sycm_bp.route('/market/categories', methods=['GET'])
def market_categories():
    return _market_rank_response(categories_only=True)


@sycm_bp.route('/market/trend', methods=['GET'])
def market_trend():
    """Daily trend for search demand and ranked product samples."""
    start_date, end_date = get_query_date_range('sycm_market_search_rank')
    if not end_date:
        return failure('NO_DATA', '暂无市场趋势数据')
    item_rows = _repo_market_item_sample_daily(start_date, end_date)
    search_rows = _repo_market_search_daily(start_date, end_date)
    expected_days = _expected_days(start_date, end_date)
    if not expected_days:
        return failure('VALIDATION_ERROR', '日期范围无效')
    item_by_date = {row['stat_date']: dict(row) for row in item_rows}
    search_by_date = {row['stat_date']: dict(row) for row in search_rows}
    first_day = date_type.fromisoformat(start_date)
    daily = []
    for offset in range(expected_days):
        stat_date = (first_day + timedelta(days=offset)).isoformat()
        item = item_by_date.get(stat_date, {})
        search = search_by_date.get(stat_date, {})
        daily.append({
            'stat_date': stat_date,
            'item_count': item.get('item_count'),
            'avg_item_uv': item.get('avg_item_uv'),
            'avg_item_buyers': item.get('avg_item_buyers'),
            'keyword_count': search.get('keyword_count'),
            'avg_search_heat': search.get('avg_search_heat'),
            'avg_pay_rate': search.get('avg_pay_rate'),
            'avg_click_rate': search.get('avg_click_rate'),
        })
    item_observed_days = len(item_by_date)
    search_observed_days = len(search_by_date)
    observed_days = sum(1 for row in daily if row['item_count'] is not None or row['keyword_count'] is not None)
    coverage_rate = observed_days / expected_days
    item_coverage_rate = item_observed_days / expected_days
    search_coverage_rate = search_observed_days / expected_days
    return success({
        'start_date': start_date, 'end_date': end_date,
        'expected_days': expected_days, 'observed_days': observed_days,
        'coverage_rate': coverage_rate,
        'item_observed_days': item_observed_days,
        'item_coverage_rate': item_coverage_rate,
        'search_observed_days': search_observed_days,
        'search_coverage_rate': search_coverage_rate,
        'coverage_status': 'complete' if coverage_rate == 1 else ('partial' if observed_days else 'no_data'),
        'trend_comparable': item_coverage_rate >= 0.8 and search_coverage_rate >= 0.8,
        'daily': daily,
    })


@sycm_bp.route('/market/shops/entities', methods=['GET'])
def market_shop_entities():
    """市场商品榜覆盖到的店铺实体列表。"""
    start_date, end_date = get_query_date_range('sycm_market_item_rank')
    if not end_date:
        return success({'entities': []})
    return success({'entities': _repo_market_shop_entities(start_date, end_date)})


@sycm_bp.route('/market/shops/entity-trend', methods=['GET'])
def market_shop_entity_trend():
    """单个市场店铺逐日趋势，按该店铺外部商品榜样本聚合。"""
    entity_id = request.args.get('shop_id', '').strip()
    if not entity_id:
        return failure('VALIDATION_ERROR', '缺少 shop_id')
    start_date, end_date = get_query_date_range('sycm_market_item_rank')
    rows, product_rows = _repo_market_shop_entity_trend(start_date, end_date, entity_id)
    expected_days = _expected_days(start_date, end_date)
    daily = [dict(row) for row in rows]
    observed_days = len(daily)
    totals = {
        'uv': sum(float(row['uv'] or 0) for row in daily),
        'pay_buyer_count': sum(float(row['pay_buyer_count'] or 0) for row in daily),
    }
    totals['pay_rate'] = totals['pay_buyer_count'] / totals['uv'] if totals['uv'] else None
    coverage_rate = observed_days / expected_days if expected_days else None
    if not daily:
        return failure('NO_DATA', '所选范围暂无该市场店铺趋势数据')
    return success({
        'entity_id': entity_id, 'entity_name': daily[-1].get('shop_name'),
        'start_date': start_date, 'end_date': end_date,
        'expected_days': expected_days, 'observed_days': observed_days,
        'coverage_rate': coverage_rate,
        'coverage_status': 'complete' if coverage_rate == 1 else ('partial' if observed_days else 'no_data'),
        'trend_comparable': bool(expected_days and coverage_rate >= 0.8),
        'totals': totals, 'daily': daily,
        'items': [
            {**dict(row), 'detail_url': row['detail_url'] or f"https://item.taobao.com/item.htm?id={row['item_id']}"}
            for row in product_rows
        ],
    })


@sycm_bp.route('/market/items/entities', methods=['GET'])
def market_item_entities():
    """市场外部单品实体列表。"""
    start_date, end_date = get_query_date_range('sycm_market_item_rank')
    if not end_date:
        return success({'entities': []})
    return success({'entities': _repo_market_item_entities(start_date, end_date)})


@sycm_bp.route('/market/items/entity-trend', methods=['GET'])
def market_item_entity_trend():
    """单个市场外部单品逐日趋势。"""
    entity_id = request.args.get('item_id', '').strip()
    if not entity_id:
        return failure('VALIDATION_ERROR', '缺少 item_id')
    start_date, end_date = get_query_date_range('sycm_market_item_rank')
    rows = _repo_market_item_entity_trend(start_date, end_date, entity_id)
    expected_days = _expected_days(start_date, end_date)
    daily = [dict(row) for row in rows]
    for row in daily:
        uv = row.get('uv')
        row['pay_rate'] = (float(row.get('pay_buyer_count') or 0) / float(uv)) if uv else None
    observed_days = len(daily)
    coverage_rate = observed_days / expected_days if expected_days else None
    if not daily:
        return failure('NO_DATA', '所选范围暂无该市场单品趋势数据')
    return success({
        'entity_id': entity_id, 'entity_name': daily[-1].get('title'),
        'shop_name': daily[-1].get('shop_name'), 'shop_id': daily[-1].get('shop_id'),
        'start_date': start_date, 'end_date': end_date,
        'expected_days': expected_days, 'observed_days': observed_days,
        'coverage_rate': coverage_rate,
        'coverage_status': 'complete' if coverage_rate == 1 else ('partial' if observed_days else 'no_data'),
        'trend_comparable': bool(expected_days and coverage_rate >= 0.8),
        'daily': daily,
    })


@sycm_bp.route('/market/snapshots', methods=['GET'])
def market_period_snapshots():
    """周期快照概览：读取浏览器插件导出的周/月榜单，不混入日趋势。"""
    batches = _repo_snapshot_batches()
    comparisons = {}
    for snapshot_type, table, entity, label_column, value in (
        ('item', 'market_snapshot_items', 'item_id', 'title', 'pay_buyer_value'),
        ('search', 'market_snapshot_searches', 'keyword', 'keyword', 'search_heat_value'),
        ('rival_item', 'market_snapshot_rival_items', 'item_id', 'title', 'pay_buyer_value'),
        ('rival_shop', 'market_snapshot_rival_shops', 'shop_id', 'shop_name', 'pay_buyer_value'),
    ):
        typed = [item for item in batches if item['snapshot_type'] == snapshot_type]
        if len(typed) < 2:
            comparisons[snapshot_type] = {'status': 'insufficient_periods', 'rows': []}
            continue
        current, previous = typed[0], typed[1]
        current_rows = _repo_snapshot_batch_rows(table, entity, label_column, value, current['id'])
        previous_rows = _repo_snapshot_batch_rows(table, entity, label_column, value, previous['id'])
        old = {str(row['entity_id']): dict(row) for row in previous_rows}
        rows = []
        for row in current_rows:
            key = str(row['entity_id'])
            if key not in old:
                continue
            current_metric, previous_metric = row['metric'], old[key]['metric']
            delta = None
            if current_metric is not None and previous_metric not in (None, 0):
                delta = (float(current_metric) - float(previous_metric)) / abs(float(previous_metric))
            rows.append({
                'entity_id': key,
                'entity_name': row['entity_name'] or old[key]['entity_name'] or key,
                'current_metric': current_metric,
                'previous_metric': previous_metric,
                'delta_rate': delta,
            })
        rows.sort(key=lambda item: abs(item['delta_rate'] or 0), reverse=True)
        comparisons[snapshot_type] = {
            'status': 'comparable',
            'current_period': {'start': current['period_start'], 'end': current['period_end']},
            'previous_period': {'start': previous['period_start'], 'end': previous['period_end']},
            'shared_entity_count': len(rows),
            'rows': rows,
        }
    availability = 'available' if batches else 'no-data'
    return success({
        'batches': batches,
        'comparisons': comparisons,
        'availability': availability,
        'note': '周期榜单保留原始统计区间；区间数值为导出范围中点估算，不代表精确成交量。',
    })
