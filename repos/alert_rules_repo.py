from db import get_db


class AlertRulesRepo:
    """预警规则读写。

    所有写方法都接受可选的 ``connection``：传入时复用调用方的事务（不自行
    commit），由调用方决定提交或回滚。这样「规则变更 + 审计记录」才能落在同一个
    事务里——见 `services/alert_rules_service.py`（原先规则先提交、审计另开连接，
    审计失败会留下「改动已生效但没有审计证据」的状态）。
    """

    @staticmethod
    def list(scope=None, enabled=None):
        query = 'SELECT * FROM alert_rules WHERE 1=1'
        params = []
        if scope:
            query += ' AND scope = ?'
            params.append(scope)
        if enabled is not None:
            query += ' AND enabled = ?'
            params.append(1 if enabled else 0)
        query += ' ORDER BY id'
        with get_db() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    @staticmethod
    def get(rule_id, connection=None):
        if connection is not None:
            row = connection.execute('SELECT * FROM alert_rules WHERE id = ?', (rule_id,)).fetchone()
            return dict(row) if row else None
        with get_db() as conn:
            row = conn.execute('SELECT * FROM alert_rules WHERE id = ?', (rule_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(values, connection=None):
        statement = (
            '''INSERT INTO alert_rules (name, scope, metric, operator, threshold, level, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?)'''
        )
        params = (
            values['name'], values['scope'], values['metric'], values['operator'],
            values['threshold'], values['level'], 1 if values['enabled'] else 0,
        )
        if connection is not None:
            cursor = connection.execute(statement, params)
            return AlertRulesRepo.get(cursor.lastrowid, connection=connection)
        with get_db() as conn:
            cursor = conn.execute(statement, params)
            conn.commit()
            rule_id = cursor.lastrowid
        return AlertRulesRepo.get(rule_id)

    @staticmethod
    def update(rule_id, values, connection=None):
        assignments = ', '.join(f'{key} = ?' for key in values)
        params = [1 if key == 'enabled' and value else 0 if key == 'enabled' else value for key, value in values.items()]
        params.append(rule_id)
        statement = f'UPDATE alert_rules SET {assignments} WHERE id = ?'
        if connection is not None:
            cursor = connection.execute(statement, params)
            if not cursor.rowcount:
                return None
            return AlertRulesRepo.get(rule_id, connection=connection)
        with get_db() as conn:
            cursor = conn.execute(statement, params)
            conn.commit()
        return AlertRulesRepo.get(rule_id) if cursor.rowcount else None

    @staticmethod
    def delete(rule_id, connection=None):
        statement = 'DELETE FROM alert_rules WHERE id = ?'
        if connection is not None:
            return connection.execute(statement, (rule_id,)).rowcount > 0
        with get_db() as conn:
            cursor = conn.execute(statement, (rule_id,))
            conn.commit()
        return cursor.rowcount > 0
