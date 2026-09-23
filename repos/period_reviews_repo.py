import json

from db import get_db
from repos.audit_repo import AuditRepo


class PeriodReviewsRepo:
    """经营周期复盘读写。

    结构化段落存于 sections（JSON 文本），同时把结论映射回
    summary/conclusions/next_actions 历史字段，保证旧查询与旧接口可用。

    目标区支持四项：销售额（target_amount，净销售额口径）、净利润额（target_profit）、
    推广费（target_ad_spend）、净费比（target_net_expense_ratio，推广花费 ÷ 净销售额）。
    """

    #: 目标字段 -> 是否比率（比率用小数存储，如 0.237 表示 23.7%）
    TARGET_FIELDS = {
        'target_amount': False,
        'target_profit': False,
        'target_ad_spend': False,
        'target_net_expense_ratio': True,
    }

    @staticmethod
    def _serialize_sections(value):
        if value in (None, ''):
            return '{}'
        if isinstance(value, str):
            # 存库前校验，避免写入非法 JSON
            json.loads(value)
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _target_value(payload, key):
        """空串 / None 一律存 NULL，避免把「没填」当成 0 目标。"""
        raw = payload.get(key)
        if raw in ('', None):
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if key in ('target_amount', 'target_profit', 'target_ad_spend') and value < 0:
            # 利润目标允许为负（亏损目标），销售额/推广费目标不允许
            if key != 'target_profit':
                return None
        return value

    @staticmethod
    def _deserialize(row):
        item = dict(row)
        raw = item.get('sections') or '{}'
        try:
            item['sections'] = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            item['sections'] = {}
        return item

    @staticmethod
    def get(period_type, period_key):
        with get_db() as connection:
            row = connection.execute(
                'SELECT * FROM period_reviews WHERE period_type = ? AND period_key = ?',
                (period_type, period_key),
            ).fetchone()
        return PeriodReviewsRepo._deserialize(row) if row else None

    @staticmethod
    def upsert(period_type, period_key, payload):
        sections = PeriodReviewsRepo._serialize_sections(payload.get('sections'))
        status = str(payload.get('status') or 'draft')[:32]
        template_version = str(payload.get('template_version') or '')[:32]
        targets = {key: PeriodReviewsRepo._target_value(payload, key)
                   for key in PeriodReviewsRepo.TARGET_FIELDS}
        category_mode = str(payload.get('category_mode') or '')[:64]

        with get_db() as connection:
            before = connection.execute(
                'SELECT * FROM period_reviews WHERE period_type = ? AND period_key = ?',
                (period_type, period_key),
            ).fetchone()
            connection.execute(
                '''INSERT INTO period_reviews
                       (period_type, period_key, summary, conclusions, next_actions, reviewer,
                        sections, status, template_version, target_amount, category_mode,
                        target_profit, target_ad_spend, target_net_expense_ratio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(period_type, period_key) DO UPDATE SET
                     summary=excluded.summary, conclusions=excluded.conclusions,
                     next_actions=excluded.next_actions, reviewer=excluded.reviewer,
                     sections=excluded.sections, status=excluded.status,
                     template_version=excluded.template_version, target_amount=excluded.target_amount,
                     category_mode=excluded.category_mode,
                     target_profit=excluded.target_profit,
                     target_ad_spend=excluded.target_ad_spend,
                     target_net_expense_ratio=excluded.target_net_expense_ratio,
                     updated_at=CURRENT_TIMESTAMP''',
                (period_type, period_key, payload['summary'], payload['conclusions'],
                 payload['next_actions'], payload['reviewer'], sections, status,
                 template_version, targets['target_amount'], category_mode,
                 targets['target_profit'], targets['target_ad_spend'],
                 targets['target_net_expense_ratio']),
            )
            after = connection.execute(
                'SELECT * FROM period_reviews WHERE period_type = ? AND period_key = ?',
                (period_type, period_key),
            ).fetchone()
            AuditRepo.record(
                'period_review', f'{period_type}:{period_key}', 'upsert', payload['reviewer'],
                payload.get('reason') or '保存经营复盘', dict(before) if before else None,
                dict(after), connection=connection,
            )
            connection.commit()
        return PeriodReviewsRepo._deserialize(after)

    @staticmethod
    def list(period_type=None):
        with get_db() as connection:
            query = 'SELECT * FROM period_reviews'; params = []
            if period_type: query += ' WHERE period_type = ?'; params.append(period_type)
            query += ' ORDER BY period_key DESC'
            rows = connection.execute(query, params).fetchall()
        return [PeriodReviewsRepo._deserialize(row) for row in rows]
