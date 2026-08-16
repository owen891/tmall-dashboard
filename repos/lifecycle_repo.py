from db import get_db, get_shop_id
from repos.audit_repo import AuditRepo


class LifecycleRepo:
    @staticmethod
    def product_row(product_id):
        with get_db() as connection:
            row = connection.execute(
                'SELECT product_id, title, list_date FROM products WHERE product_id = ?',
                (product_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def product_rows():
        with get_db() as connection:
            rows = connection.execute('SELECT product_id, title, list_date FROM products ORDER BY product_id').fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def assessment_context():
        shop_id = get_shop_id()
        with get_db() as connection:
            daily = connection.execute(
                '''SELECT product_id, date, payment_amount, ipv, buyers, payment_conversion, ad_spend
                   FROM daily_data WHERE shop_id = ? ORDER BY product_id, date''', (shop_id,)
            ).fetchall()
            monthly = connection.execute(
                '''SELECT m.product_id, m.month, m.payment_amount,
                          COUNT(DISTINCT d.date) AS covered_days,
                          CAST(strftime('%d', date(m.month || '-01', '+1 month', '-1 day')) AS INTEGER) AS expected_days
                   FROM monthly_data m
                   LEFT JOIN daily_data d ON d.shop_id = ? AND d.product_id = m.product_id AND substr(d.date, 1, 7) = m.month
                   GROUP BY m.product_id, m.month, m.payment_amount
                   ORDER BY m.product_id, m.month'''
                , (shop_id,)).fetchall()
            profiles = connection.execute('SELECT * FROM lifecycle_profiles').fetchall()
            history = connection.execute('SELECT * FROM lifecycle_history ORDER BY product_id, id DESC').fetchall()

        context = {'daily': {}, 'monthly': {}, 'profiles': {}, 'history': {}}
        for row in daily:
            item = dict(row)
            context['daily'].setdefault(item.pop('product_id'), []).append(item)
        for row in monthly:
            item = dict(row)
            context['monthly'].setdefault(item.pop('product_id'), []).append(item)
        for row in profiles:
            item = dict(row)
            context['profiles'][item['product_id']] = item
        for row in history:
            item = dict(row)
            context['history'].setdefault(item['product_id'], []).append(item)
        return context

    @staticmethod
    def daily_rows(product_id):
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT date, payment_amount, ipv, buyers, payment_conversion, ad_spend
                   FROM daily_data WHERE shop_id = ? AND product_id = ? ORDER BY date''', (shop_id, product_id)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def monthly_rows(product_id):
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT m.month, m.payment_amount,
                          COUNT(DISTINCT d.date) AS covered_days,
                          CAST(strftime('%d', date(m.month || '-01', '+1 month', '-1 day')) AS INTEGER) AS expected_days
                   FROM monthly_data m
                   LEFT JOIN daily_data d ON d.shop_id = ? AND d.product_id = m.product_id AND substr(d.date, 1, 7) = m.month
                   WHERE m.product_id = ?
                   GROUP BY m.month, m.payment_amount ORDER BY m.month''', (shop_id, product_id)
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
                existing = connection.execute('SELECT * FROM lifecycle_profiles WHERE product_id = ?', (profile['product_id'],)).fetchone()
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
                after = connection.execute(
                    'SELECT * FROM lifecycle_profiles WHERE product_id = ?', (profile['product_id'],)
                ).fetchone()
                AuditRepo.record(
                    'lifecycle', profile['product_id'], 'update', operator, reason,
                    dict(existing) if existing else None, dict(after), connection=connection,
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
