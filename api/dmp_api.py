# -*- coding: utf-8 -*-
"""达摩盘数据查询API。

数据来源：collect_dmp_competition.py / collect_dmp_shop.py 采集落库的 dmp_* 表
（见 DATABASE_ARCHITECTURE.md §4.1）。

口径注意：达摩盘竞争数据是双窗口快照（endDate vs peerEndDate，与达摩盘页面对齐，
T-1/T-2 收口），与生意参谋 rival-* 的单日观察口径不同；前端展示需标注数据源。
空数据统一走 success + availability='no-data'（200 信封），不返回 400。
"""
from flask import Blueprint, request

from db import get_connection
from api.api_response import success

dmp_bp = Blueprint('dmp', __name__, url_prefix='/api/dmp')

LATEST_RUN_SQL = (
    "SELECT id, end_date, peer_end_date, started_at, finished_at, "
    "detected_cnt, monitored_cnt, indicator_cnt "
    "FROM dmp_competition_runs WHERE status='succeeded' "
    "ORDER BY id DESC LIMIT 1"
)


def _no_data():
    return success({'available': False}, availability='no-data',
                   limitations=['暂无达摩盘竞争分析数据，请先在采集中心运行 dmp_competition'])


def _latest_run(conn):
    return conn.execute(LATEST_RUN_SQL).fetchone()


@dmp_bp.route('/competition/summary', methods=['GET'])
def competition_summary():
    """最新竞争批次：双窗口日期、竞对计数、我方日消耗。"""
    conn = get_connection()
    try:
        run = _latest_run(conn)
        if not run:
            return _no_data()
        run_id, end_date, peer_end_date = run[0], run[1], run[2]
        day_cost = conn.execute(
            'SELECT day_cost FROM dmp_competition_indicators '
            'WHERE run_id=? AND day_cost IS NOT NULL LIMIT 1', (run_id,)).fetchone()
        # 份额分档只在 payload 里，取一个竞对样例展示字段存在性
        detected_top = conn.execute(
            'SELECT competitor_name, competitive_score FROM dmp_competitors_detection '
            'WHERE run_id=? AND competitive_score IS NOT NULL '
            'ORDER BY competitive_score DESC LIMIT 1', (run_id,)).fetchone()
        return success({
            'available': True,
            'end_date': end_date,
            'peer_end_date': peer_end_date,
            'finished_at': run[4],
            'detected_cnt': run[5],
            'monitored_cnt': run[6],
            'indicator_cnt': run[7],
            'own_day_cost': day_cost[0] if day_cost else None,
            'top_detected': {'name': detected_top[0], 'score': detected_top[1]} if detected_top else None,
        })
    finally:
        conn.close()


@dmp_bp.route('/competition/rivals', methods=['GET'])
def competition_rivals():
    """竞对列表：监控快照 join 每竞对指标，按人群争夺交集UV降序。"""
    conn = get_connection()
    try:
        run = _latest_run(conn)
        if not run:
            return _no_data()
        run_id = run[0]
        rows = conn.execute('''
            SELECT m.competitor_name, m.competition_type, m.attention_status,
                   i.day_cost, i.day_cost_rate, i.intersection_click_uv,
                   i.intersection_rate, i.buy_uv_rate, i.payload_json
            FROM dmp_competitor_monitor m
            LEFT JOIN dmp_competition_indicators i
              ON i.run_id = m.run_id AND i.competitor_name = m.competitor_name
            WHERE m.run_id = ?
            ORDER BY (i.intersection_click_uv IS NULL), i.intersection_click_uv DESC
        ''', (run_id,)).fetchall()
        rivals = []
        for (name, comp_type, attention, day_cost, day_cost_rate,
             inter_uv, inter_rate, buy_rate, payload_json) in rows:
            payload = {}
            if payload_json:
                try:
                    import json as _json
                    payload = _json.loads(payload_json) or {}
                except (ValueError, TypeError):
                    payload = {}
            rivals.append({
                'competitor_name': name,
                'competition_type': comp_type,
                'attention_status': bool(attention),
                'day_cost': day_cost,
                'day_cost_rate': day_cost_rate,
                'intersection_click_uv': inter_uv,
                'intersection_rate': inter_rate,
                'buy_uv_rate': buy_rate,
                'alipay_share': payload.get('alipayCnt') or {},
                'ipv_share': payload.get('ipv') or {},
                'cart_share': payload.get('cart') or {},
            })
        return success({
            'available': True,
            'end_date': run[1],
            'peer_end_date': run[2],
            'rivals': rivals,
        })
    finally:
        conn.close()


SHOP_OVERVIEW_KEYS = (
    'gmv', 'gmvGrowthRate', 'ipv', 'generalizedIpv', 'paidCvr',
    'generalizedPaidCvr', 'alipayCnt', 'itemCount', 'newCount',
    'newGmvContriRate', 'potentialCount', 'potentialGmvContriRate',
    'hotCount', 'hotGmvContriRate', 'tailCount', 'tailGmvContriRate', 'charge',
)


@dmp_bp.route('/shop/summary', methods=['GET'])
def shop_summary():
    """全店洞察最新批次：本店（benchmark=0）vs 同行同层（benchmark=1）概览。

    口径：达摩盘近 N 天窗口（periods 存于 run 行）；同行同层的 GMV/IPV 无精确值，
    只回 generalizedIpv / generalizedPaidCvr 分档串，前端不得与本店精确值直连比较。
    """
    import json as _json

    conn = get_connection()
    try:
        run = conn.execute(
            "SELECT id, end_date, periods FROM dmp_shop_runs "
            "WHERE status='succeeded' ORDER BY id DESC LIMIT 1").fetchone()
        if not run:
            return success({'available': False}, availability='no-data',
                           limitations=['暂无达摩盘全店洞察数据，请先在采集中心运行 dmp_shop'])
        run_id, end_date, period = run[0], run[1], run[2]
        out = {'available': True, 'end_date': end_date, 'period': period}
        for bench, key in ((0, 'own'), (1, 'peer')):
            row = conn.execute(
                'SELECT payload_json FROM dmp_shop_overview '
                'WHERE run_id=? AND benchmark=? AND period=? '
                'ORDER BY id DESC LIMIT 1', (run_id, bench, period)).fetchone()
            if not row:
                row = conn.execute(
                    'SELECT payload_json FROM dmp_shop_overview '
                    'WHERE run_id=? AND benchmark=? '
                    'ORDER BY id DESC LIMIT 1', (run_id, bench)).fetchone()
            payload = {}
            if row and row[0]:
                try:
                    payload = _json.loads(row[0]) or {}
                except (ValueError, TypeError):
                    payload = {}
            out[key] = {k: payload.get(k) for k in SHOP_OVERVIEW_KEYS}
        return success(out)
    finally:
        conn.close()


@dmp_bp.route('/competition/ad-strategy', methods=['GET'])
def competition_ad_strategy():
    """TOP单品 × 竞对同款投放借鉴：相似画像 + 策略簇（渠道/计划/圈人/关键词）。

    策略簇（cluster）是达摩盘对我方单品同类竞品投放的聚类样本：每簇含
    渠道消耗占比、代表计划名、圈选人群与购买关键词、簇均量级与ROI。
    """
    import json as _json

    conn = get_connection()
    try:
        run = _latest_run(conn)
        if not run:
            return _no_data()
        run_id = run[0]
        rows = conn.execute('''
            SELECT item_id, item_title, similarity_score, price_scope,
                   wj_amt_scope, cate_name, feature_insight,
                   similarity_json, strategy_json
            FROM dmp_competition_ad_strategy WHERE run_id=?
            ORDER BY similarity_score DESC''', (run_id,)).fetchall()
        items = []
        for (item_id, title, score, price_scope, wj_amt_scope, cate_name,
             insight, sim_json, strat_json) in rows:
            sim = {}
            strat = {}
            try:
                sim = _json.loads(sim_json) if sim_json else {}
            except (ValueError, TypeError):
                sim = {}
            try:
                strat = _json.loads(strat_json) if strat_json else {}
            except (ValueError, TypeError):
                strat = {}

            def _crowd_names(entry):
                try:
                    names = (entry.get('campaign_list') or [{}])[0] \
                        .get('campaign_settings', {}) \
                        .get('crowd_setting', {}).get('top5_crowd_name') or []
                    return [n.get('name') for n in names
                            if n.get('name')][:4]
                except (AttributeError, IndexError):
                    return []

            def _keywords(entry):
                try:
                    infos = (entry.get('campaign_list') or [{}])[0] \
                        .get('campaign_settings', {}) \
                        .get('keyword_setting', {}).get('top20_keyword_info') or []
                    return [k.get('keyword_name') for k in infos
                            if k.get('keyword_name')][:6]
                except (AttributeError, IndexError):
                    return []

            lessons = []
            for entry in (strat.get('list') or [])[:4]:
                channels = sorted(
                    (c for c in (entry.get('channelCostRateList') or [])
                     if c.get('costRate') is not None),
                    key=lambda c: c.get('costRate') or 0, reverse=True)
                core = entry.get('promotionCoreVO') or {}
                lessons.append({
                    'channels': [{'name': c.get('channelName') or c.get('channelId'),
                                  'rate': c.get('costRate')} for c in channels],
                    'campaign': (entry.get('campaign_list') or [{}])[0]
                        .get('campaign_name'),
                    'crowds': _crowd_names(entry),
                    'keywords': _keywords(entry),
                    'click': (core.get('click') or {}).get('value'),
                    'roi': (core.get('roi') or {}).get('value'),
                    'cost_click': (core.get('costClick') or {}).get('value'),
                })
            items.append({
                'item_id': item_id,
                'item_title': title,
                'similarity_score': score,
                'price_scope': price_scope,
                'wj_amt_scope': wj_amt_scope,
                'cate_name': cate_name,
                'feature_insight': insight,
                'lessons': lessons,
            })
        return success({
            'available': True,
            'end_date': run[1],
            'items': items,
        })
    finally:
        conn.close()


@dmp_bp.route('/competition/detection', methods=['GET'])
def competition_detection():
    """竞对探测候选列表（最新批次），可选 ?min_score= 过滤。"""
    conn = get_connection()
    try:
        run = _latest_run(conn)
        if not run:
            return _no_data()
        run_id = run[0]
        min_score = request.args.get('min_score', type=float)
        sql = ('SELECT competitor_name, competitor_id, recall_method, '
               'competitive_score, attention_status, gmv, look_cnt, alipay_cnt '
               'FROM dmp_competitors_detection WHERE run_id=?')
        params = [run_id]
        if min_score is not None:
            sql += ' AND competitive_score >= ?'
            params.append(min_score)
        sql += ' ORDER BY (competitive_score IS NULL), competitive_score DESC'
        detected = [
            {
                'competitor_name': r[0], 'competitor_id': r[1],
                'recall_method': r[2], 'competitive_score': r[3],
                'attention_status': bool(r[4]), 'gmv': r[5],
                'look_cnt': r[6], 'alipay_cnt': r[7],
            }
            for r in conn.execute(sql, params).fetchall()
        ]
        return success({
            'available': True,
            'end_date': run[1],
            'detected': detected,
        })
    finally:
        conn.close()
