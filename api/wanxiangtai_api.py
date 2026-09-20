"""
万相台（one.alimama.com）报表数据导入 API。

提供万相台接口 JSON 数据的直接导入能力，将数据写入 promotion_daily_facts 表，
供推广分析模块使用。

端点：
- POST /api/wanxiangtai/import   — 导入万相台 JSON 数据
- POST /api/wanxiangtai/preview  — 预览转换结果（不写入数据库）
"""

import json
from datetime import date
from uuid import uuid4

from flask import Blueprint, request, current_app

from api.api_response import failure, success
from db import get_db, get_shop_id
from services.wanxiangtai_service import (
    WanxiangtaiValidationError,
    wanxiangtai_service,
)


wanxiangtai_bp = Blueprint('wanxiangtai', __name__)


KNOWN_REPORT_TYPES = {
    'account', 'campaign', 'adgroup', 'bidword', 'crowd',
    'item', 'item_promotion', 'creative', 'area', 'channel', 'product', 'unit',
}


def _sniff_report_type(payload: dict) -> str:
    """report_type 缺省或未知时，按行内维度字段嗅探报表类型。"""
    rows = (payload.get('data') or {}).get('list') or []
    if rows and all(isinstance(row, dict) for row in rows[:5]):
        if any(row.get('creativeId') for row in rows[:5]):
            return 'creative'
        if any(row.get('campaignName') for row in rows[:5]):
            return 'campaign'
        if any(row.get('promotionId') for row in rows[:5]):
            return 'item_promotion'
    return 'account'


def _parse_query_payload(payload: dict, report_type: str, split_type: str,
                         start_date, end_date) -> dict:
    """解析 query.json 响应；report_type 未知时按行嗅探。"""
    if report_type not in KNOWN_REPORT_TYPES:
        report_type = _sniff_report_type(payload)
    return report_type, wanxiangtai_service.parse_report_payload(
        payload, report_type, split_type, start_date, end_date
    )


def _upsert_creatives(conn, shop_id: str, creatives: list[dict]) -> None:
    for row in creatives:
        conn.execute(
            '''INSERT INTO promotion_creatives
               (shop_id, creative_id, creative_name, image_url, video_url,
                creative_format, product_id, product_name, channel, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(shop_id, creative_id) DO UPDATE SET
                 creative_name=excluded.creative_name,
                 image_url=CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE promotion_creatives.image_url END,
                 video_url=CASE WHEN excluded.video_url != '' THEN excluded.video_url ELSE promotion_creatives.video_url END,
                 creative_format=excluded.creative_format,
                 product_id=CASE WHEN excluded.product_id != '' THEN excluded.product_id ELSE promotion_creatives.product_id END,
                 product_name=excluded.product_name,
                 channel=CASE WHEN excluded.channel != '' THEN excluded.channel ELSE promotion_creatives.channel END,
                 updated_at=CURRENT_TIMESTAMP''',
            (shop_id, row['creative_id'], row['creative_name'], row['image_url'],
             row['video_url'], row['creative_format'], row['product_id'],
             row['product_name'], row['channel']),
        )


def _upsert_campaign_items(conn, shop_id: str, items: list[dict]) -> None:
    for row in items:
        conn.execute(
            '''INSERT INTO promotion_campaign_items
               (shop_id, campaign_id, product_id, campaign_name, product_name,
                image_url, channel, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(shop_id, campaign_id, product_id) DO UPDATE SET
                 campaign_name=excluded.campaign_name,
                 product_name=CASE WHEN excluded.product_name != '' THEN excluded.product_name ELSE promotion_campaign_items.product_name END,
                 image_url=CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE promotion_campaign_items.image_url END,
                 channel=CASE WHEN excluded.channel != '' THEN excluded.channel ELSE promotion_campaign_items.channel END,
                 updated_at=CURRENT_TIMESTAMP''',
            (shop_id, row['campaign_id'], row['product_id'], row['campaign_name'],
             row['product_name'], row['image_url'], row['channel']),
        )


@wanxiangtai_bp.route('/api/wanxiangtai/preview', methods=['POST'])
def preview():
    """
    预览万相台 JSON 数据转换结果，不写入数据库。

    Request Body (JSON):
    {
        "payload": {...},              // 万相台接口返回的完整 JSON
        "report_type": "account",      // 报表类型
        "split_type": "day",           // 时间粒度
        "start_date": "2026-09-10",   // 开始日期（可选，用于补全）
        "end_date": "2026-09-16"      // 结束日期（可选，用于补全）
    }
    """
    body = _parse_json_body()
    if isinstance(body, tuple):  # 错误响应
        return body

    payload = body.get('payload')
    if not payload:
        return failure('VALIDATION_ERROR', '必须提供万相台接口返回的 payload', status=422)

    report_type = body.get('report_type', 'account')
    split_type = body.get('split_type', 'day')
    start_date = body.get('start_date')
    end_date = body.get('end_date')

    try:
        # 判断是 query.json 还是 chargeSum.json 响应
        if 'contentSceneCharge' in (payload.get('data') or {}) or 'searchCharge' in (payload.get('data') or {}):
            rows = wanxiangtai_service.parse_charge_sum_response(payload, start_date, end_date)
            source = 'chargeSum.json'
        else:
            rows = wanxiangtai_service.parse_query_response(
                payload, report_type, split_type, start_date, end_date
            )
            source = 'query.json'

        # 统计信息
        date_range = _extract_date_range(rows)
        channels = sorted({r['channel'] for r in rows if r.get('channel')})
        total_spend = sum(float(r.get('ad_spend') or 0) for r in rows)

        return success({
            'rows': rows,
            'row_count': len(rows),
            'source': source,
            'date_range': date_range,
            'channels': channels,
            'total_spend': round(total_spend, 2),
        }, availability='available' if rows else 'no-data')

    except WanxiangtaiValidationError as exc:
        return failure('VALIDATION_ERROR', str(exc), status=422)


@wanxiangtai_bp.route('/api/wanxiangtai/import', methods=['POST'])
def import_data():
    """
    导入万相台 JSON 数据到 promotion_daily_facts 表。

    Request Body (JSON):
    {
        "payload": {...},              // 万相台接口返回的完整 JSON
        "report_type": "account",      // 报表类型
        "split_type": "day",           // 时间粒度
        "start_date": "2026-09-10",   // 开始日期
        "end_date": "2026-09-16",     // 结束日期
        "source_note": "手动导入"      // 来源备注（可选）
    }
    """
    body = _parse_json_body()
    if isinstance(body, tuple):
        return body

    payload = body.get('payload')
    if not payload:
        return failure('VALIDATION_ERROR', '必须提供万相台接口返回的 payload', status=422)

    report_type = body.get('report_type', 'account')
    split_type = body.get('split_type', 'day')
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    source_note = body.get('source_note', '万相台API导入')
    source_run_id = str(body.get('source_run_id') or '').strip()

    try:
        # 解析数据
        if 'contentSceneCharge' in (payload.get('data') or {}) or 'searchCharge' in (payload.get('data') or {}):
            rows = wanxiangtai_service.parse_charge_sum_response(payload, start_date, end_date)
            parsed = {'facts': rows, 'creatives': [], 'campaign_items': []}
            source_api = '/report/chargeSum.json'
        else:
            report_type, parsed = _parse_query_payload(
                payload, report_type, split_type, start_date, end_date
            )
            rows = parsed['facts']
            source_api = '/report/query.json'

        if not rows:
            return failure('NO_DATA', '解析后无有效数据行', status=422)

        # 多日 chargeSum 是区间汇总，写入独立汇总表，不能伪装成某一天的日事实。
        summary_rows = [r for r in rows if r.get('granularity') == 'summary' or not r.get('date')]

        # 写入数据库
        batch_id = f'{source_run_id}:{uuid4().hex}' if source_run_id else str(uuid4())
        shop_id = get_shop_id()
        inserted = 0
        updated = 0

        with get_db() as conn:
            conn.execute('DELETE FROM collector_data_staging WHERE batch_id = ?', (batch_id,))
            staging_rows = summary_rows if summary_rows else rows
            for index, row in enumerate(staging_rows, start=1):
                unit_type = 'channel' if summary_rows else 'row'
                unit_key = f"{row.get('channel', 'unknown')}:{row.get('date') or row.get('period_start') or index}"
                conn.execute(
                    '''INSERT INTO collector_data_staging
                       (source_key, batch_id, unit_type, unit_key, payload_json, status, quality_message)
                       VALUES (?, ?, ?, ?, ?, 'staged', ?)''',
                    ('wanxiangtai', batch_id, unit_type, unit_key,
                     json.dumps(row, ensure_ascii=False), 'staging-first'),
                )
            if not staging_rows or any(not isinstance(row, dict) for row in staging_rows):
                conn.execute(
                    "UPDATE collector_data_staging SET status='rejected', quality_message='empty or invalid result' WHERE batch_id = ?",
                    (batch_id,),
                )
                conn.commit()
                return failure('QUALITY_GATE_FAILED', '万相台 staging 质量门禁失败', status=422)
            if summary_rows:
                for row in summary_rows:
                    conn.execute(
                        '''INSERT INTO promotion_period_summary
                           (shop_id, period_start, period_end, channel, ad_spend, source_batch_id)
                           VALUES (?, ?, ?, ?, ?, ?)
                           ON CONFLICT(shop_id, period_start, period_end, channel)
                           DO UPDATE SET ad_spend=excluded.ad_spend,
                                         source_batch_id=excluded.source_batch_id''',
                        (shop_id, row.get('period_start') or start_date,
                         row.get('period_end') or end_date, row['channel'],
                         row.get('ad_spend'), batch_id),
                    )
                conn.execute(
                    '''INSERT INTO import_batches (id, shop_id, source_type, source_filename, source_hash,
                       status, total_rows, valid_rows, invalid_rows, inserted_count, updated_count,
                       completed_at, quality_summary)
                       VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, 0, ?, 0, datetime('now'), ?)''',
                    (batch_id, shop_id, 'wanxiangtai_api', source_api, '',
                     len(summary_rows), len(summary_rows), len(summary_rows),
                     f'{source_note}; summary rows; {report_type}/{split_type}'),
                )
                conn.execute(
                    "UPDATE collector_data_staging SET status='published', published_at=CURRENT_TIMESTAMP WHERE batch_id = ?",
                    (batch_id,),
                )
                conn.commit()
                return success({
                    'batch_id': batch_id, 'inserted': len(summary_rows), 'updated': 0,
                    'total_rows': len(summary_rows), 'source_api': source_api,
                    'date_range': _extract_date_range(rows), 'report_type': report_type,
                    'split_type': split_type, 'target': 'promotion_period_summary',
                }, status=201, availability='available')
            # 记录导入批次
            conn.execute(
                '''INSERT INTO import_batches (id, shop_id, source_type, source_filename, source_hash,
                   status, total_rows, valid_rows, invalid_rows, inserted_count, updated_count,
                   completed_at, quality_summary)
                   VALUES (?, ?, ?, ?, ?, 'processing', ?, ?, 0, 0, 0, datetime('now'), ?)''',
                (batch_id, shop_id, 'wanxiangtai_api', source_api, '',
                 len(rows), len(rows),
                 f'{source_note}; {len(rows)} rows; {report_type}/{split_type}')
            )

            # 维度表先落：创意库 + 计划×商品映射
            _upsert_creatives(conn, shop_id, parsed.get('creatives') or [])
            _upsert_campaign_items(conn, shop_id, parsed.get('campaign_items') or [])

            # 创意报表的事实行只写 promotion_creative_daily，不进主事实表，
            # 否则会在 promotion_daily_facts 里留下无主键维度的幽灵行。
            facts_to_store = rows if report_type != 'creative' else []

            # 账户总账行(grain='account', 无计划/商品归属)是账户级汇总口径，与
            # campaign/product 明细求和互斥。一旦同日混入，会让当日花费虚高数倍
            # （2026-09-13 曾混入 141,471 的跨口径总账，真实花费仅 44,847）。
            # 因此：同日已有明细时，丢弃总账行，仅保留明细口径。
            dropped_account = 0
            if facts_to_store:
                kept = []
                for row in facts_to_store:
                    if (row.get('grain') == 'account'
                            and not row.get('campaign_id') and not row.get('product_id')):
                        has_detail = conn.execute(
                            '''SELECT 1 FROM promotion_daily_facts
                               WHERE shop_id = ? AND date = ?
                                 AND grain IN ('campaign', 'product') LIMIT 1''',
                            (shop_id, row.get('date'))
                        ).fetchone()
                        if has_detail:
                            dropped_account += 1
                            continue
                    kept.append(row)
                facts_to_store = kept
            if dropped_account:
                current_app.logger.warning(
                    '万相台导入：丢弃 %d 行账户总账(grain=account)，同日已存在明细口径',
                    dropped_account,
                )

            for row in facts_to_store:
                # 检查是否已存在（UPSERT）
                existing = conn.execute(
                    '''SELECT 1 FROM promotion_daily_facts
                       WHERE shop_id = ? AND date = ? AND channel = ?
                         AND campaign_id = ? AND unit_id = ? AND product_id = ?''',
                    (shop_id, row['date'], row['channel'],
                     row.get('campaign_id', ''), row.get('unit_id', ''),
                     row.get('product_id', ''))
                ).fetchone()

                if existing:
                    # 更新已有记录（仅更新非空字段）
                    sets = []
                    params = []
                    for col in ('ad_spend', 'attributed_payment_amount', 'impressions',
                                'clicks', 'payment_buyers', 'direct_payment_amount',
                                'indirect_payment_amount', 'cart_adds', 'cart_cost',
                                'new_buyers'):
                        if row.get(col) is not None:
                            sets.append(f'{col} = ?')
                            params.append(row[col])
                    if row.get('campaign_name'):
                        sets.append('campaign_name = ?')
                        params.append(row['campaign_name'])
                    if row.get('grain'):
                        sets.append('grain = ?')
                        params.append(row['grain'])
                    if sets:
                        sets.append('source_batch_id = ?')
                        params.append(batch_id)
                        params.extend([shop_id, row['date'], row['channel'],
                                       row.get('campaign_id', ''), row.get('unit_id', ''),
                                       row.get('product_id', '')])
                        conn.execute(
                            f'''UPDATE promotion_daily_facts SET {', '.join(sets)}
                                WHERE shop_id = ? AND date = ? AND channel = ?
                                  AND campaign_id = ? AND unit_id = ? AND product_id = ?''',
                            params
                        )
                        updated += 1
                else:
                    # 插入新记录
                    conn.execute(
                        '''INSERT INTO promotion_daily_facts
                           (shop_id, date, channel, campaign_id, unit_id, product_id,
                            grain, campaign_name, cart_adds, cart_cost, new_buyers,
                            ad_spend, attributed_payment_amount, impressions, clicks,
                            payment_buyers, direct_payment_amount, indirect_payment_amount,
                            source_batch_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (shop_id, row['date'], row['channel'],
                         row.get('campaign_id', ''), row.get('unit_id', ''),
                         row.get('product_id', ''),
                         row.get('grain', ''), row.get('campaign_name', ''),
                         row.get('cart_adds'), row.get('cart_cost'), row.get('new_buyers'),
                         row.get('ad_spend'), row.get('attributed_payment_amount'),
                         row.get('impressions'), row.get('clicks'),
                         row.get('payment_buyers'), row.get('direct_payment_amount'),
                         row.get('indirect_payment_amount'),
                         batch_id)
                    )
                    inserted += 1

            # 创意日事实
            creative_facts = rows if report_type == 'creative' else []
            creative_stored = 0
            for row in creative_facts:
                conn.execute(
                    '''INSERT INTO promotion_creative_daily
                       (shop_id, date, channel, creative_id, product_id, campaign_id,
                        ad_spend, attributed_payment_amount, impressions, clicks,
                        payment_buyers, direct_payment_amount, indirect_payment_amount,
                        cart_adds, new_buyers, source_batch_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(shop_id, date, channel, creative_id) DO UPDATE SET
                         product_id=excluded.product_id,
                         campaign_id=excluded.campaign_id,
                         ad_spend=excluded.ad_spend,
                         attributed_payment_amount=excluded.attributed_payment_amount,
                         impressions=excluded.impressions,
                         clicks=excluded.clicks,
                         payment_buyers=excluded.payment_buyers,
                         direct_payment_amount=excluded.direct_payment_amount,
                         indirect_payment_amount=excluded.indirect_payment_amount,
                         cart_adds=excluded.cart_adds,
                         new_buyers=excluded.new_buyers,
                         source_batch_id=excluded.source_batch_id''',
                    (shop_id, row['date'], row['channel'], row['creative_id'],
                     row.get('product_id', ''), row.get('campaign_id', ''),
                     row.get('ad_spend'), row.get('attributed_payment_amount'),
                     row.get('impressions'), row.get('clicks'),
                     row.get('payment_buyers'), row.get('direct_payment_amount'),
                     row.get('indirect_payment_amount'), row.get('cart_adds'),
                     row.get('new_buyers'), batch_id),
                )
                creative_stored += 1

            # 更新批次记录状态和统计
            conn.execute(
                '''UPDATE import_batches SET status = 'completed', inserted_count = ?, updated_count = ?
                   WHERE id = ?''',
                (inserted + creative_stored, updated, batch_id)
            )

            conn.execute(
                "UPDATE collector_data_staging SET status='published', published_at=CURRENT_TIMESTAMP WHERE batch_id = ?",
                (batch_id,),
            )

            # 提交事务
            conn.commit()

        date_range = _extract_date_range(rows)

        return success({
            'batch_id': batch_id,
            'inserted': inserted + creative_stored,
            'updated': updated,
            'total_rows': len(rows),
            'source_api': source_api,
            'date_range': date_range,
            'report_type': report_type,
            'split_type': split_type,
            'target': 'promotion_creative_daily' if report_type == 'creative' else 'promotion_daily_facts',
        }, status=201, availability='available')

    except WanxiangtaiValidationError as exc:
        return failure('VALIDATION_ERROR', str(exc), status=422)
    except Exception as exc:
        # 解析或数据库阶段失败时，不留下永久 processing 批次。
        if 'batch_id' in locals() and batch_id:
            try:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE import_batches SET status = 'failed', quality_summary = ? WHERE id = ?",
                        (f'{source_note}; error: {exc}', batch_id),
                    )
                    conn.commit()
            except Exception:
                pass
        return failure('IMPORT_ERROR', f'导入失败: {exc}', status=500)


@wanxiangtai_bp.route('/api/wanxiangtai/period-summary', methods=['GET'])
def period_summary():
    """Query interval-level charge summaries without treating them as daily facts."""
    shop_id = get_shop_id()
    period_start = request.args.get('start_date')
    period_end = request.args.get('end_date')
    channel = request.args.get('channel')
    clauses = ['shop_id = ?']
    params = [shop_id]
    if period_start:
        clauses.append('period_end >= ?')
        params.append(period_start)
    if period_end:
        clauses.append('period_start <= ?')
        params.append(period_end)
    if channel:
        clauses.append('channel = ?')
        params.append(channel)
    with get_db(current_app.config.get('DATABASE_PATH')) as conn:
        rows = conn.execute(
            f'''SELECT shop_id, period_start, period_end, channel, ad_spend,
                       source_batch_id, created_at
                FROM promotion_period_summary
                WHERE {' AND '.join(clauses)}
                ORDER BY period_start, period_end, channel''',
            params,
        ).fetchall()
    data = [dict(row) for row in rows]
    return success({
        'rows': data,
        'row_count': len(data),
        'date_range': {
            'start': min((r['period_start'] for r in data), default=None),
            'end': max((r['period_end'] for r in data), default=None),
        },
    }, availability='available' if data else 'no-data',
       evidence=[{'source': 'promotion_period_summary', 'row_count': len(data)}])


# ── 辅助函数 ──────────────────────────────────────────────────────────────

def _parse_json_body():
    """解析请求 JSON body，返回解析后的 dict 或错误响应 tuple。"""
    try:
        return request.get_json(force=True)
    except (json.JSONDecodeError, Exception):
        return failure('VALIDATION_ERROR', '请求体必须是有效的 JSON', status=422)


def _extract_date_range(rows: list[dict]) -> dict:
    """从数据行中提取日期范围。"""
    if not rows:
        return {}
    dates = sorted({r['date'] for r in rows if r.get('date')})
    if not dates:
        return {}
    return {'start': dates[0], 'end': dates[-1], 'days': len(dates)}
