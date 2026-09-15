from db import get_db, get_shop_id, require_default_shop_scope
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
        require_default_shop_scope()
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
        require_default_shop_scope()
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
        require_default_shop_scope()
        with get_db() as connection:
            row = connection.execute('SELECT * FROM product_actions WHERE id = ?', (action_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update(action_id, values, expected_version=None, operator=None, reason=None):
        require_default_shop_scope()
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
    def delete(action_id, expected_version=None, operator=None, reason=None):
        require_default_shop_scope()
        with get_db() as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                before = connection.execute('SELECT * FROM product_actions WHERE id = ?', (action_id,)).fetchone()
                if before is None or (expected_version is not None and before['version'] != expected_version):
                    connection.rollback()
                    return 0
                AuditRepo.record(
                    'action', action_id, 'delete', operator or before['assigned_to'] or 'system',
                    reason or '删除运营动作', dict(before), None, connection=connection,
                )
                connection.execute('DELETE FROM product_action_history WHERE action_id = ?', (action_id,))
                cursor = connection.execute(
                    'DELETE FROM product_actions WHERE id = ?' + (' AND version = ?' if expected_version is not None else ''),
                    (action_id, expected_version) if expected_version is not None else (action_id,),
                )
                connection.commit()
                return cursor.rowcount
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def observing():
        require_default_shop_scope()
        with get_db() as connection:
            rows = connection.execute("SELECT * FROM product_actions WHERE status = 'observing'").fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def metric_window(product_id, start_date, end_date, metric):
        require_default_shop_scope()
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
        require_default_shop_scope()
        with get_db() as connection:
            rows = connection.execute(
                "SELECT * FROM product_actions WHERE status = 'pending_review' ORDER BY planned_at"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def list_actions(product_id=None, limit=500, status=None, shop_label=None):
        require_default_shop_scope()
        query = '''SELECT pa.*, p.title AS product_title, p.image_url AS product_image
                   FROM product_actions pa
                   LEFT JOIN products p ON p.product_id = pa.product_id'''
        parameters = []
        clauses = []
        if product_id:
            clauses.append('pa.product_id = ?')
            parameters.append(product_id)
        if status:
            clauses.append('pa.status = ?')
            parameters.append(status)
        if shop_label:
            clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
            parameters.extend([shop_label, shop_label])
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY pa.planned_at DESC LIMIT ?'
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
    def list_calendar_actions(start_date, end_date, status=None, shop_label=None):
        require_default_shop_scope()
        query = '''SELECT pa.*, p.title AS product_title, p.image_url AS product_image
                   FROM product_actions pa
                   LEFT JOIN products p ON p.product_id = pa.product_id
                   WHERE pa.planned_at BETWEEN ? AND ?'''
        parameters = [start_date, end_date]
        if status:
            query += ' AND pa.status = ?'
            parameters.append(status)
        if shop_label:
            query += " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
            parameters.extend([shop_label, shop_label])
        query += ' ORDER BY pa.planned_at ASC, pa.updated_at DESC, pa.id ASC'
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
        require_default_shop_scope()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT from_status, to_status, detail, operator, version, created_at
                   FROM product_action_history WHERE action_id = ? ORDER BY id''', (action_id,)
            ).fetchall()
        return [dict(row) for row in rows]
