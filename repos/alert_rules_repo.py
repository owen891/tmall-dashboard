from db import get_db


class AlertRulesRepo:
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
    def get(rule_id):
        with get_db() as connection:
            row = connection.execute('SELECT * FROM alert_rules WHERE id = ?', (rule_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(values):
        with get_db() as connection:
            cursor = connection.execute(
                '''INSERT INTO alert_rules (name, scope, metric, operator, threshold, level, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    values['name'], values['scope'], values['metric'], values['operator'],
                    values['threshold'], values['level'], 1 if values['enabled'] else 0,
                ),
            )
            connection.commit()
            rule_id = cursor.lastrowid
        return AlertRulesRepo.get(rule_id)

    @staticmethod
    def update(rule_id, values):
        assignments = ', '.join(f'{key} = ?' for key in values)
        params = [1 if key == 'enabled' and value else 0 if key == 'enabled' else value for key, value in values.items()]
        params.append(rule_id)
        with get_db() as connection:
            cursor = connection.execute(f'UPDATE alert_rules SET {assignments} WHERE id = ?', params)
            connection.commit()
        return AlertRulesRepo.get(rule_id) if cursor.rowcount else None

    @staticmethod
    def delete(rule_id):
        with get_db() as connection:
            cursor = connection.execute('DELETE FROM alert_rules WHERE id = ?', (rule_id,))
            connection.commit()
        return cursor.rowcount > 0
