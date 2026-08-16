from db import get_db, get_shop_id
from repos.audit_repo import AuditRepo


class ActionsRepo:
    UPDATE_FIELDS = {
        'status', 'executed_at', 'blocked_reason', 'expected_recovery_at',
        'before_metric_value', 'after_metric_value', 'result_change', 'calculation_note',
        'review_effective', 'review_reason', 'review_conclusion', 'review_next_action',
        'reviewed_by', 'reviewed_at', 'version',
    }
    @staticmethod
    def create(action, operator=None, reason=None):
        fields = ', '.join(action)
        placeholders = ', '.join('?' for _ in action)
        with get_db() as connection:
            connection.execute(
                f'INSERT INTO product_actions ({fields}) VALUES ({placeholders})', tuple(action.values())
            )
            connection.execute(
                '''INSERT INTO product_action_history (action_id, from_status, to_status, detail, version)
                   VALUES (?, NULL, ?, '动作创建', 1)''', (action['id'], action['status'])
            )
            AuditRepo.record('action', action['id'], 'create', operator or action.get('assigned_to') or 'system',
                             reason or '创建运营动作', None, action, connection=connection)
            connection.commit()

    @staticmethod
    def create_many(actions, operator=None, reason=None):
        with get_db() as connection:
            try:
                for action in actions:
                    fields = ', '.join(action)
                    placeholders = ', '.join('?' for _ in action)
                    connection.execute(
                        f'INSERT INTO product_actions ({fields}) VALUES ({placeholders})', tuple(action.values())
                    )
                    connection.execute(
                        '''INSERT INTO product_action_history (action_id, from_status, to_status, detail, version)
                           VALUES (?, NULL, ?, '批量动作创建', 1)''', (action['id'], action['status'])
                    )
                    AuditRepo.record('action', action['id'], 'create', operator or action.get('assigned_to') or 'system',
                                     reason or '批量创建运营动作', None, action, connection=connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def get(action_id):
        with get_db() as connection:
            row = connection.execute('SELECT * FROM product_actions WHERE id = ?', (action_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update(action_id, values, expected_version=None, operator=None, reason=None):
        if not values or not set(values) <= ActionsRepo.UPDATE_FIELDS:
            raise ValueError('动作更新字段不合法')
        assignments = ', '.join(f'{key} = ?' for key in values)
        where = 'id = ?'
        parameters = [*values.values(), action_id]
        if expected_version is not None:
            where += ' AND version = ?'
            parameters.append(expected_version)
        with get_db() as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                before = connection.execute('SELECT * FROM product_actions WHERE id = ?', (action_id,)).fetchone()
                cursor = connection.execute(
                    f'UPDATE product_actions SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE {where}',
                    parameters,
                )
                if cursor.rowcount and 'status' in values:
                    connection.execute(
                        '''INSERT INTO product_action_history (action_id, from_status, to_status, detail, version)
                           VALUES (?, ?, ?, ?, ?)''',
                        (action_id, before['status'] if before else None, values['status'], values.get('calculation_note'), values['version']),
                    )
                if cursor.rowcount:
                    after = connection.execute('SELECT * FROM product_actions WHERE id = ?', (action_id,)).fetchone()
                    AuditRepo.record(
                        'action', action_id, 'update', operator or values.get('reviewed_by') or 'system',
                        reason or values.get('calculation_note') or values.get('review_reason') or '更新运营动作',
                        dict(before) if before else None, dict(after), connection=connection,
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return cursor.rowcount

    @staticmethod
    def observing():
        with get_db() as connection:
            rows = connection.execute("SELECT * FROM product_actions WHERE status = 'observing'").fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def metric_window(product_id, start_date, end_date, metric):
        if metric != 'payment_amount':
            return None
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT date, payment_amount FROM daily_data
                   WHERE shop_id = ? AND product_id = ? AND date BETWEEN ? AND ? ORDER BY date''',
                (shop_id, product_id, start_date, end_date),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def list_pending_review():
        with get_db() as connection:
            rows = connection.execute(
                "SELECT * FROM product_actions WHERE status = 'pending_review' ORDER BY planned_at"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def list_actions(product_id=None, limit=500, status=None):
        query = 'SELECT * FROM product_actions'
        parameters = []
        clauses = []
        if product_id:
            clauses.append('product_id = ?')
            parameters.append(product_id)
        if status:
            clauses.append('status = ?')
            parameters.append(status)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY planned_at DESC LIMIT ?'
        parameters.append(limit)
        with get_db() as connection:
            rows = connection.execute(query, parameters).fetchall()
            result = [dict(row) for row in rows]
            for item in result:
                history = connection.execute(
                    '''SELECT from_status, to_status, detail, operator, version, created_at
                       FROM product_action_history WHERE action_id = ? ORDER BY id''',
                    (item['id'],),
                ).fetchall()
                item['history'] = [dict(row) for row in history]
        return result

    @staticmethod
    def history(action_id):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT from_status, to_status, detail, operator, version, created_at
                   FROM product_action_history WHERE action_id = ? ORDER BY id''', (action_id,)
            ).fetchall()
        return [dict(row) for row in rows]
