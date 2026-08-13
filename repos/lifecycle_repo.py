from db import get_db


class LifecycleRepo:
    @staticmethod
    def product_rows():
        with get_db() as connection:
            rows = connection.execute('SELECT product_id, title, list_date FROM products ORDER BY product_id').fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def daily_rows(product_id):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT date, payment_amount, ipv, buyers, payment_conversion, ad_spend
                   FROM daily_data WHERE product_id = ? ORDER BY date''', (product_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def monthly_rows(product_id):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT month, payment_amount FROM monthly_data WHERE product_id = ? ORDER BY month''', (product_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_profile(product_id):
        with get_db() as connection:
            row = connection.execute('SELECT * FROM lifecycle_profiles WHERE product_id = ?', (product_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def upsert(profile, reason, operator):
        with get_db() as connection:
            try:
                existing = connection.execute('SELECT version FROM lifecycle_profiles WHERE product_id = ?', (profile['product_id'],)).fetchone()
                if existing and existing['version'] != profile['version']:
                    return None
                version = (existing['version'] if existing else 0) + 1
                connection.execute(
                    '''INSERT INTO lifecycle_profiles (
                         product_id, recommended_stage, manual_stage, stage_locked, seasonal_attribute,
                         seasonal_source, confidence, rationale, next_key_date, version, updated_by
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(product_id) DO UPDATE SET
                         recommended_stage=excluded.recommended_stage, manual_stage=excluded.manual_stage,
                         stage_locked=excluded.stage_locked, seasonal_attribute=excluded.seasonal_attribute,
                         seasonal_source=excluded.seasonal_source, confidence=excluded.confidence,
                         rationale=excluded.rationale, next_key_date=excluded.next_key_date,
                         version=excluded.version, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP''',
                    (profile['product_id'], profile.get('recommended_stage'), profile.get('manual_stage'),
                     int(bool(profile.get('stage_locked'))), profile.get('seasonal_attribute'),
                     profile.get('seasonal_source'), profile.get('confidence'), profile.get('rationale'),
                     profile.get('next_key_date'), version, operator),
                )
                connection.execute(
                    '''INSERT INTO lifecycle_history (product_id, recommended_stage, manual_stage, seasonal_attribute,
                       locked, reason, operator, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (profile['product_id'], profile.get('recommended_stage'), profile.get('manual_stage'),
                     profile.get('seasonal_attribute'), int(bool(profile.get('stage_locked'))), reason, operator, version),
                )
                connection.commit()
                return version
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def history(product_id):
        with get_db() as connection:
            rows = connection.execute('SELECT * FROM lifecycle_history WHERE product_id = ? ORDER BY id DESC', (product_id,)).fetchall()
        return [dict(row) for row in rows]
