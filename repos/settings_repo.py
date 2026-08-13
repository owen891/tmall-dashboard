import json

from db import get_db


class SettingsRepo:
    @staticmethod
    def get_all():
        with get_db() as connection:
            rows = connection.execute('SELECT setting_key, setting_value FROM app_settings').fetchall()
        return {row['setting_key']: json.loads(row['setting_value']) for row in rows}

    @staticmethod
    def upsert(values):
        with get_db() as connection:
            connection.executemany(
                '''INSERT INTO app_settings (setting_key, setting_value)
                   VALUES (?, ?)
                   ON CONFLICT(setting_key) DO UPDATE SET
                     setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP''',
                [(key, json.dumps(value, ensure_ascii=False)) for key, value in values.items()],
            )
            connection.commit()
