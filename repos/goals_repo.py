import sqlite3
from datetime import date, timedelta

from db import get_db


class GoalsRepo:
    @staticmethod
    def prior_year_daily_weights(year):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT substr(date, 6, 5) AS month_day, SUM(MAX(payment_amount - refund_amount, 0)) AS weight
                   FROM daily_data WHERE substr(date, 1, 4) = ? GROUP BY substr(date, 6, 5)''',
                (str(year - 1),),
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
    def replace_year(year, annual_target, expected_version, days):
        with get_db() as connection:
            try:
                current = connection.execute(
                    'SELECT version FROM goal_versions WHERE year = ?', (year,)
                ).fetchone()
                if current and expected_version is not None and current['version'] != expected_version:
                    return None
                if not current and expected_version not in (None, 0):
                    return None
                locked = connection.execute(
                    'SELECT 1 FROM goal_locks WHERE year = ? LIMIT 1', (year,)
                ).fetchone()
                if locked:
                    return 'locked'
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
                '''SELECT d.goal_date, d.target_amount, d.source, d.reason, d.version,
                          EXISTS(SELECT 1 FROM goal_locks l
                                 WHERE l.year = d.year AND l.period_type = 'date'
                                   AND l.period_key = d.goal_date) AS locked
                   FROM daily_goals d WHERE d.year = ? ORDER BY d.goal_date''',
                (year,),
            ).fetchall()
        return (dict(version) if version else None, [dict(day) for day in days])

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
                '''SELECT substr(goal_date, 1, 7) AS period_key, SUM(target_amount) AS target_amount
                   FROM daily_goals WHERE year = ? GROUP BY substr(goal_date, 1, 7) ORDER BY period_key''',
                (year,),
            ).fetchall()
        return [dict(row) for row in rows]

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
        with get_db() as connection:
            store_count = connection.execute(
                "SELECT COUNT(*) AS count FROM store_daily_facts WHERE substr(date, 1, 4) = ?",
                (str(year),),
            ).fetchone()['count']
            if store_count:
                rows = connection.execute(
                    '''SELECT date, payment_amount, successful_refund_amount
                       FROM store_daily_facts WHERE substr(date, 1, 4) = ? ORDER BY date''',
                    (str(year),),
                ).fetchall()
            else:
                rows = connection.execute(
                '''SELECT date, SUM(payment_amount - refund_amount) AS net_sales
                   FROM daily_data WHERE substr(date, 1, 4) = ? GROUP BY date ORDER BY date''',
                (str(year),),
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
                current = connection.execute('SELECT version FROM goal_versions WHERE year = ?', (year,)).fetchone()
                if not current or current['version'] != expected_version:
                    return None
                all_rows = connection.execute(
                    'SELECT goal_date, target_amount FROM daily_goals WHERE year = ? ORDER BY goal_date', (year,)
                ).fetchall()
                dates = GoalsRepo._period_dates(year, period_type, period_key)
                target_dates = {item.isoformat() for item in dates}
                selected = [row for row in all_rows if row['goal_date'] in target_dates]
                if not selected:
                    raise ValueError('目标周期不属于该年度')
                locked_rows = connection.execute(
                    '''SELECT period_key FROM goal_locks WHERE year = ? AND period_type = 'date' ''', (year,)
                ).fetchall()
                locked = {row['period_key'] for row in locked_rows}
                unlocked = [row for row in selected if row['goal_date'] not in locked]
                locked_total = sum(float(row['target_amount']) for row in selected if row['goal_date'] in locked)
                remainder = float(target_amount) - locked_total
                if remainder < -1e-9:
                    raise ValueError('目标小于已锁定日期合计')
                if not unlocked:
                    raise ValueError('周期内没有可重分配日期')
                current_unlocked_total = sum(float(row['target_amount']) for row in unlocked)
                delta = remainder - current_unlocked_total
                other_unlocked = [row for row in all_rows if row['goal_date'] not in target_dates and row['goal_date'] not in locked]
                if delta > 0 and sum(float(row['target_amount']) for row in other_unlocked) + 1e-9 < delta:
                    raise ValueError('未锁定日期的可分配额度不足')
                new_version = expected_version + 1
                values = GoalsRepo._allocate_rows(unlocked, remainder, new_version, year, reason)
                if delta:
                    values += GoalsRepo._allocate_rows(other_unlocked, sum(float(row['target_amount']) for row in other_unlocked) - delta, new_version, year, None)
                connection.executemany(
                    '''UPDATE daily_goals SET target_amount = ?, source = CASE WHEN ? IS NULL THEN source ELSE 'manual' END,
                       reason = COALESCE(?, reason), version = ? WHERE year = ? AND goal_date = ?''', values
                )
                if lock:
                    connection.execute(
                        '''INSERT INTO goal_locks (year, period_type, period_key, version)
                           VALUES (?, 'date', ?, ?)''', (year, period_key, new_version)
                    )
                connection.execute('UPDATE goal_versions SET version = ?, updated_at = CURRENT_TIMESTAMP WHERE year = ?', (new_version, year))
                connection.execute(
                    '''INSERT INTO goal_adjustments (year, period_type, period_key, target_amount, operator, reason, version)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (year, period_type, period_key, target_amount, operator, reason, new_version),
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
    def _allocate_rows(rows, target, version, year, reason):
        total = sum(float(row['target_amount']) for row in rows)
        cents = round(float(target) * 100)
        if not rows:
            return []
        values, consumed = [], 0
        for index, row in enumerate(rows):
            allocated = cents - consumed if index == len(rows) - 1 else round(cents * float(row['target_amount']) / total) if total else cents // len(rows)
            consumed += allocated
            values.append((allocated / 100, reason, reason, version, year, row['goal_date']))
        return values

    @staticmethod
    def list_adjustments(year):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT period_type, period_key, target_amount, operator, reason, version, created_at
                   FROM goal_adjustments WHERE year = ? ORDER BY id DESC''', (year,)
            ).fetchall()
        return [dict(row) for row in rows]
