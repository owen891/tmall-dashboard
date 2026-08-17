from db import get_db
from repos.audit_repo import AuditRepo


class PeriodReviewsRepo:
    @staticmethod
    def upsert(period_type, period_key, payload):
        with get_db() as connection:
            before = connection.execute(
                'SELECT * FROM period_reviews WHERE period_type = ? AND period_key = ?',
                (period_type, period_key),
            ).fetchone()
            connection.execute(
                '''INSERT INTO period_reviews (period_type, period_key, summary, conclusions, next_actions, reviewer)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(period_type, period_key) DO UPDATE SET summary=excluded.summary,
                     conclusions=excluded.conclusions, next_actions=excluded.next_actions, reviewer=excluded.reviewer,
                     updated_at=CURRENT_TIMESTAMP''',
                (period_type, period_key, payload['summary'], payload['conclusions'], payload['next_actions'], payload['reviewer']),
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

    @staticmethod
    def list(period_type=None):
        with get_db() as connection:
            query = 'SELECT * FROM period_reviews'; params = []
            if period_type: query += ' WHERE period_type = ?'; params.append(period_type)
            query += ' ORDER BY period_key DESC'
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
