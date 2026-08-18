import sqlite3
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from db import get_db, get_shop_id
from repos.audit_repo import AuditRepo
from utils.goal_allocation import allocate_cents


class GoalsRepo:
    @staticmethod
    def _money_cents(value):
        """Normalize persisted/input money to integer cents before arithmetic."""
        try:
            amount = Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError('金额必须为有效数字') from error
        return int(amount * 100)

    @staticmethod
    def prior_year_net_sales(year):
        shop_id = get_shop_id()
        with get_db() as connection:
            store = connection.execute(
                "SELECT SUM(payment_amount - successful_refund_amount) AS total FROM store_daily_facts WHERE shop_id = ? AND substr(date, 1, 4) = ?",
                (shop_id, str(year - 1)),
            ).fetchone()
            if store and store['total'] is not None:
                return round(float(store['total']), 2)
            row = connection.execute(
                "SELECT SUM(payment_amount - refund_amount) AS total FROM daily_data WHERE shop_id = ? AND substr(date, 1, 4) = ?",
                (shop_id, str(year - 1)),
            ).fetchone()
        return round(float(row['total'] or 0), 2)
    @staticmethod
    def prior_year_daily_weights(year):
        shop_id = get_shop_id()
        with get_db() as connection:
            store_total = connection.execute(
                '''SELECT SUM(payment_amount - successful_refund_amount) AS total
                   FROM store_daily_facts WHERE shop_id = ? AND substr(date, 1, 4) = ?''',
                (shop_id, str(year - 1)),
            ).fetchone()
            if store_total and store_total['total'] is not None:
                rows = connection.execute(
                    '''SELECT substr(date, 6, 5) AS month_day,
                              SUM(MAX(payment_amount - successful_refund_amount, 0)) AS weight
                       FROM store_daily_facts
                       WHERE shop_id = ? AND substr(date, 1, 4) = ?
                       GROUP BY substr(date, 6, 5)''',
                    (shop_id, str(year - 1)),
                ).fetchall()
            else:
                rows = connection.execute(
                    '''SELECT substr(date, 6, 5) AS month_day,
                              SUM(MAX(payment_amount - refund_amount, 0)) AS weight
                       FROM daily_data
                       WHERE shop_id = ? AND substr(date, 1, 4) = ?
                       GROUP BY substr(date, 6, 5)''',
                    (shop_id, str(year - 1)),
                ).fetchall()
        return {row['month_day']: float(row['weight'] or 0) for row in rows}
    @staticmethod
    def get_version(year):
        with get_db() as connection:
            row = connection.execute(
                'SELECT year, version, annual_target FROM goal_versions WHERE year = ?',
                (year,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def replace_year(year, annual_target, expected_version, days, operator='admin', reason='创建或更新年度目标'):
        with get_db() as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                current = connection.execute(
                    'SELECT * FROM goal_versions WHERE year = ?', (year,)
                ).fetchone()
                if current and expected_version is not None and current['version'] != expected_version:
                    connection.rollback()
                    return None
                if not current and expected_version not in (None, 0):
                    connection.rollback()
                    return None
                locked = connection.execute(
                    'SELECT 1 FROM goal_locks WHERE year = ? LIMIT 1', (year,)
                ).fetchone()
                daily_exists = connection.execute(
                    'SELECT 1 FROM daily_goals WHERE year = ? LIMIT 1', (year,)
                ).fetchone()
                if locked and daily_exists:
                    return 'locked'
                if locked:
                    # A partially initialized year can retain locks without any
                    # daily targets; those locks cannot protect real data.
                    connection.execute('DELETE FROM goal_locks WHERE year = ?', (year,))
                version = (current['version'] if current else 0) + 1
                connection.execute(
                    '''INSERT INTO goal_versions (year, version, annual_target)
                       VALUES (?, ?, ?)
                       ON CONFLICT(year) DO UPDATE SET
                         version = excluded.version, annual_target = excluded.annual_target,
                         updated_at = CURRENT_TIMESTAMP''',
                    (year, version, annual_target),
                )
                connection.execute('DELETE FROM daily_goals WHERE year = ?', (year,))
                connection.executemany(
                    '''INSERT INTO daily_goals (year, goal_date, target_amount, version)
                       VALUES (?, ?, ?, ?)''',
                    [(year, day, amount, version) for day, amount in days],
                )
                after = connection.execute(
                    'SELECT * FROM goal_versions WHERE year = ?', (year,)
                ).fetchone()
                AuditRepo.record(
                    'goal', year, 'replace', operator, reason,
                    dict(current) if current else None, dict(after), connection=connection,
                )
                connection.commit()
                return version
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def get_year(year):
        with get_db() as connection:
            version = connection.execute(
                'SELECT year, version, annual_target FROM goal_versions WHERE year = ?', (year,)
            ).fetchone()
            days = connection.execute(
                '''SELECT goal_date, target_amount, source, reason, version
                   FROM daily_goals WHERE year = ? ORDER BY goal_date''',
                (year,),
            ).fetchall()
            locks = connection.execute(
                'SELECT period_type, period_key FROM goal_locks WHERE year = ?', (year,)
            ).fetchall()
        # Only explicit date locks freeze individual daily values. Period locks
        # are aggregate constraints and are handled during reallocation.
        locked_dates = GoalsRepo._locked_dates(year, locks)
        result_days = [{**dict(day), 'locked': int(day['goal_date'] in locked_dates)} for day in days]
        return (dict(version) if version else None, result_days)

    @staticmethod
    def list_locks(year):
        with get_db() as connection:
            rows = connection.execute(
                'SELECT period_type, period_key, version FROM goal_locks WHERE year = ?', (year,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def periods(year):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT substr(goal_date, 1, 7) AS period_key, SUM(target_amount) AS target_amount,
                          MAX(CASE WHEN source = 'manual' THEN 1 ELSE 0 END) AS has_manual_source
                   FROM daily_goals WHERE year = ? GROUP BY substr(goal_date, 1, 7) ORDER BY period_key''',
                (year,),
            ).fetchall()
            goal_dates = connection.execute(
                'SELECT goal_date FROM daily_goals WHERE year = ?', (year,)
            ).fetchall()
            locks = connection.execute(
                'SELECT period_type, period_key FROM goal_locks WHERE year = ?', (year,)
            ).fetchall()
        month_days = {}
        for row in goal_dates:
            month_days.setdefault(row['goal_date'][:7], set()).add(row['goal_date'])
        locked_months = sorted(
            lock['period_key'] for lock in locks
            if lock['period_type'] == 'month' and lock['period_key'] in month_days
        )
        months = []
        for row in rows:
            month = dict(row)
            month['source'] = 'manual' if month.pop('has_manual_source') else 'automatic'
            months.append(month)
        return {'months': months, 'locked_months': locked_months}

    @staticmethod
    def period_summaries(year):
        """Return all supported period aggregates from the atomic daily goals."""
        with get_db() as connection:
            rows = connection.execute(
                'SELECT goal_date, target_amount FROM daily_goals WHERE year = ? ORDER BY goal_date',
                (year,),
            ).fetchall()
        days = [dict(row) for row in rows]
        result = {'year': round(sum(float(row['target_amount']) for row in days), 2),
                  'quarter': {}, 'month': {}, 'week': {}, 'date': {}}
        for row in days:
            current = date.fromisoformat(row['goal_date'])
            amount = float(row['target_amount'])
            result['date'][row['goal_date']] = round(amount, 2)
            month_key = current.strftime('%Y-%m')
            quarter_key = f'{current.year}-Q{((current.month - 1) // 3) + 1}'
            week_key = f'{current.isocalendar().year}-W{current.isocalendar().week:02d}'
            for grain, key in (('month', month_key), ('quarter', quarter_key), ('week', week_key)):
                result[grain][key] = round(result[grain].get(key, 0) + amount, 2)
        return result

    @staticmethod
    def actual_summaries(year):
        shop_id = get_shop_id()
        with get_db() as connection:
            store_count = connection.execute(
                "SELECT COUNT(*) AS count FROM store_daily_facts WHERE shop_id = ? AND substr(date, 1, 4) = ?",
                (shop_id, str(year)),
            ).fetchone()['count']
            if store_count:
                rows = connection.execute(
                    '''SELECT date, payment_amount - successful_refund_amount AS net_sales
                       FROM store_daily_facts WHERE shop_id = ? AND substr(date, 1, 4) = ? ORDER BY date''',
                    (shop_id, str(year)),
                ).fetchall()
            else:
                rows = connection.execute(
                '''SELECT date, SUM(payment_amount - refund_amount) AS net_sales
                   FROM daily_data WHERE shop_id = ? AND substr(date, 1, 4) = ? GROUP BY date ORDER BY date''',
                (shop_id, str(year)),
                ).fetchall()
        result = {'year': 0.0, 'quarter': {}, 'month': {}, 'week': {}, 'date': {}}
        for row in rows:
            current = date.fromisoformat(row['date'])
            amount = float(row['net_sales'] or 0)
            result['date'][row['date']] = round(amount, 2)
            result['year'] += amount
            keys = {
                'month': current.strftime('%Y-%m'),
                'quarter': f'{current.year}-Q{((current.month - 1) // 3) + 1}',
                'week': f'{current.isocalendar().year}-W{current.isocalendar().week:02d}',
            }
            for grain, key in keys.items(): result[grain][key] = round(result[grain].get(key, 0) + amount, 2)
        result['year'] = round(result['year'], 2)
        return result

    @staticmethod
    def add_lock(year, period_type, period_key, version):
        with get_db() as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                current = connection.execute('SELECT version FROM goal_versions WHERE year = ?', (year,)).fetchone()
                if not current or current['version'] != version:
                    connection.rollback()
                    return None
                connection.execute(
                    '''INSERT INTO goal_locks (year, period_type, period_key, version)
                       VALUES (?, ?, ?, ?)''',
                    (year, period_type, period_key, version),
                )
                connection.commit()
                return True
            except sqlite3.IntegrityError:
                connection.rollback()
                return False

    @staticmethod
    def adjust_period(year, expected_version, period_type, period_key, target_amount, operator, reason, lock):
        with get_db() as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
                current = connection.execute('SELECT version FROM goal_versions WHERE year = ?', (year,)).fetchone()
                if not current or current['version'] != expected_version:
                    connection.rollback()
                    return None
                all_rows = connection.execute(
                    'SELECT goal_date, target_amount FROM daily_goals WHERE year = ? ORDER BY goal_date', (year,)
                ).fetchall()
                dates = GoalsRepo._period_dates(year, period_type, period_key)
                target_dates = {item.isoformat() for item in dates}
                selected = [row for row in all_rows if row['goal_date'] in target_dates]
                if not selected:
                    raise ValueError('目标周期不属于该年度')
                lock_rows = connection.execute(
                    'SELECT period_type, period_key FROM goal_locks WHERE year = ?', (year,)
                ).fetchall()
                locked = GoalsRepo._locked_dates(year, lock_rows)
                aggregate_locked = GoalsRepo._aggregate_locked_dates(year, lock_rows)
                protected = locked | aggregate_locked
                unlocked = [row for row in selected if row['goal_date'] not in protected]
                target_cents = GoalsRepo._money_cents(target_amount)
                locked_total_cents = sum(
                    GoalsRepo._money_cents(row['target_amount'])
                    for row in selected if row['goal_date'] in protected
                )
                remainder_cents = target_cents - locked_total_cents
                if remainder_cents < 0:
                    raise ValueError('目标小于已锁定日期合计')
                if not unlocked:
                    raise ValueError('周期内没有可重分配日期')
                current_unlocked_total_cents = sum(
                    GoalsRepo._money_cents(row['target_amount']) for row in unlocked
                )
                delta_cents = remainder_cents - current_unlocked_total_cents
                other_unlocked = [
                    row for row in all_rows
                    if row['goal_date'] not in target_dates and row['goal_date'] not in protected
                ]
                other_unlocked_total_cents = sum(
                    GoalsRepo._money_cents(row['target_amount']) for row in other_unlocked
                )
                if period_type != 'year' and delta_cents and not other_unlocked:
                    raise ValueError('未锁定日期不足，无法保持年度总额')
                if period_type != 'year' and delta_cents > 0 and other_unlocked_total_cents < delta_cents:
                    raise ValueError('未锁定日期的可分配额度不足')
                new_version = expected_version + 1
                values = GoalsRepo._allocate_rows_cents(unlocked, remainder_cents, new_version, year, reason)
                if delta_cents:
                    values += GoalsRepo._allocate_rows_cents(
                        other_unlocked, other_unlocked_total_cents - delta_cents,
                        new_version, year, None,
                    )
                connection.executemany(
                    '''UPDATE daily_goals SET target_amount = ?, source = CASE WHEN ? IS NULL THEN source ELSE 'manual' END,
                       reason = COALESCE(?, reason), version = ? WHERE year = ? AND goal_date = ?''', values
                )
                if lock:
                    connection.execute(
                        '''INSERT INTO goal_locks (year, period_type, period_key, version)
                           VALUES (?, ?, ?, ?)''', (year, period_type, period_key, new_version)
                    )
                connection.execute('UPDATE goal_versions SET version = ?, updated_at = CURRENT_TIMESTAMP WHERE year = ?', (new_version, year))
                if period_type == 'year':
                    connection.execute(
                        'UPDATE goal_versions SET annual_target = ? WHERE year = ?',
                        (target_cents / 100, year),
                    )
                connection.execute(
                    '''INSERT INTO goal_adjustments (year, period_type, period_key, target_amount, operator, reason, version)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (year, period_type, period_key, target_cents / 100, operator, reason, new_version),
                )
                connection.commit()
                return new_version
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _period_dates(year, period_type, period_key):
        if period_type == 'date':
            return [date.fromisoformat(period_key)]
        if period_type == 'year':
            return [date(year, 1, 1) + timedelta(days=index) for index in range((date(year + 1, 1, 1) - date(year, 1, 1)).days)]
        if period_type == 'quarter':
            quarter = int(period_key[-1])
            start = date(year, (quarter - 1) * 3 + 1, 1)
            end = date(year + 1, 1, 1) if quarter == 4 else date(year, quarter * 3 + 1, 1)
        elif period_type == 'month':
            start = date.fromisoformat(f'{period_key}-01')
            end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
        elif period_type == 'week':
            start = date.fromisocalendar(year, int(period_key[-2:]), 1)
            end = start + timedelta(days=7)
        else:
            raise ValueError('不支持的目标周期')
        return [start + timedelta(days=index) for index in range((end - start).days) if (start + timedelta(days=index)).year == year]

    @staticmethod
    def _locked_dates(year, lock_rows):
        locked = set()
        for lock_row in lock_rows:
            if lock_row['period_type'] != 'date':
                continue
            locked.update(item.isoformat() for item in GoalsRepo._period_dates(
                year, lock_row['period_type'], lock_row['period_key'],
            ))
        return locked

    @staticmethod
    def _aggregate_locked_dates(year, lock_rows):
        locked = set()
        for lock_row in lock_rows:
            if lock_row['period_type'] == 'date':
                continue
            locked.update(item.isoformat() for item in GoalsRepo._period_dates(
                year, lock_row['period_type'], lock_row['period_key'],
            ))
        return locked

    @staticmethod
    def _allocate_rows(rows, target, version, year, reason):
        cents = GoalsRepo._money_cents(target)
        return GoalsRepo._allocate_rows_cents(rows, cents, version, year, reason)

    @staticmethod
    def _allocate_rows_cents(rows, cents, version, year, reason):
        if not rows:
            return []
        allocated = allocate_cents(cents, [row['target_amount'] for row in rows])
        return [(amount / 100, reason, reason, version, year, row['goal_date'])
                for row, amount in zip(rows, allocated)]

    @staticmethod
    def list_adjustments(year):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT period_type, period_key, target_amount, operator, reason, version, created_at
                   FROM goal_adjustments WHERE year = ? ORDER BY id DESC''', (year,)
            ).fetchall()
        return [dict(row) for row in rows]
