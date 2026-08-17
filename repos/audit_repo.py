import json

from db import get_db


class AuditRepo:
    @staticmethod
    def record(entity_type, entity_id, action, operator, reason, before, after, connection=None):
        values = (
            entity_type, str(entity_id), action, operator, reason,
            json.dumps(before, ensure_ascii=False, sort_keys=True),
            json.dumps(after, ensure_ascii=False, sort_keys=True),
        )
        statement = (
            '''INSERT INTO audit_logs
               (entity_type, entity_id, action, operator, reason, before_value, after_value)
               VALUES (?, ?, ?, ?, ?, ?, ?)'''
        )
        if connection is not None:
            connection.execute(statement, values)
            return
        with get_db() as connection:
            connection.execute(statement, values)
            connection.commit()

    @staticmethod
    def list(entity_type=None, entity_id=None, limit=200):
        where, params = [], []
        if entity_type:
            where.append('entity_type = ?')
            params.append(entity_type)
        if entity_id:
            where.append('entity_id = ?')
            params.append(str(entity_id))
        query = 'SELECT * FROM audit_logs'
        if where:
            query += ' WHERE ' + ' AND '.join(where)
        query += ' ORDER BY id DESC LIMIT ?'
        params.append(limit)
        with get_db() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
