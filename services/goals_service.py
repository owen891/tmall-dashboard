from calendar import isleap
from datetime import date, timedelta

from repos.goals_repo import GoalsRepo


class GoalConflictError(ValueError):
    pass


class GoalValidationError(ValueError):
    pass


def _days_for_year(year):
    cursor = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    result = []
    while cursor < end:
        result.append(cursor)
        cursor += timedelta(days=1)
    return result


def _validate_period_key(year, period_type, period_key):
    """Validate a period key before it reaches repository date arithmetic."""
    key = str(period_key or '')
    if period_type == 'year':
        if key != str(year):
            raise GoalValidationError('年度格式必须为 YYYY')
        return
    if period_type == 'quarter':
        if key not in {f'{year}-Q1', f'{year}-Q2', f'{year}-Q3', f'{year}-Q4'}:
            raise GoalValidationError('季度格式必须为 YYYY-Qn')
        return
    if period_type == 'date':
        try:
            parsed = date.fromisoformat(key)
        except ValueError as error:
            raise GoalValidationError('日期格式必须为 YYYY-MM-DD') from error
        if parsed.year != year:
            raise GoalValidationError('日期格式必须为 YYYY-MM-DD')
        return
    if period_type == 'month':
        try:
            parsed = date.fromisoformat(f'{key}-01')
        except ValueError as error:
            raise GoalValidationError('月份格式必须为 YYYY-MM') from error
        if parsed.year != year or key != f'{year:04d}-{parsed.month:02d}':
            raise GoalValidationError('月份格式必须为 YYYY-MM')
        return
    if period_type == 'week':
        if not key.startswith(f'{year:04d}-W'):
            raise GoalValidationError('周格式必须为 YYYY-Www')
        try:
            date.fromisocalendar(year, int(key[-2:]), 1)
        except (ValueError, TypeError) as error:
            raise GoalValidationError('周格式必须为 YYYY-Www') from error
        return
    raise GoalValidationError('不支持的目标周期')


def _allocate(annual_target, days, weights=None):
    cents = round(float(annual_target) * 100)
    if cents < 0:
        raise GoalValidationError('年度目标不能为负数')
    weights = weights or {}
    values = [max(0, float(weights.get(day.strftime('%m-%d'), 0))) for day in days]
    total_weight = sum(values)
    if not total_weight:
        base, remainder = divmod(cents, len(days))
        return [(day.isoformat(), (base + (1 if index < remainder else 0)) / 100)
                for index, day in enumerate(days)]
    allocated, consumed = [], 0
    for index, (day, weight) in enumerate(zip(days, values)):
        amount = cents - consumed if index == len(days) - 1 else round(cents * weight / total_weight)
        consumed += amount
        allocated.append((day.isoformat(), amount / 100))
    return allocated


class GoalsService:
    def create_or_replace(self, year, annual_target=None, expected_version=None, growth_multiplier=None,
                          operator='admin', reason='创建或更新年度目标'):
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise GoalValidationError('年份不合法')
        prior_year_net_sales = GoalsRepo.prior_year_net_sales(year)
        multiplier = float(growth_multiplier) if growth_multiplier is not None else None
        if annual_target is None:
            if multiplier is None or multiplier <= 0:
                raise GoalValidationError('年度目标或增长倍率至少提供一项')
            annual_target = prior_year_net_sales * multiplier
        if float(annual_target) < 0:
            raise GoalValidationError('年度目标不能为负数')
        days = _days_for_year(year)
        allocation = _allocate(annual_target, days, GoalsRepo.prior_year_daily_weights(year))
        version = GoalsRepo.replace_year(
            year, float(annual_target), expected_version, allocation, operator, reason,
        )
        if version == 'locked':
            raise GoalConflictError('该年度存在已锁定周期，不能覆盖重算年度目标')
        if version is None:
            raise GoalConflictError('目标版本已更新，请刷新后重试')
        return {
            'year': year, 'version': version, 'annual_total': round(float(annual_target), 2),
            'day_count': len(days), 'leap_year': isleap(year),
            'prior_year_net_sales': prior_year_net_sales,
            'growth_multiplier': multiplier,
            'suggested_annual_target': round(prior_year_net_sales * multiplier, 2) if multiplier is not None else None,
        }

    def suggest(self, year, growth_multiplier=1.0):
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise GoalValidationError('年份不合法')
        multiplier = float(growth_multiplier)
        if multiplier <= 0:
            raise GoalValidationError('增长倍率必须大于 0')
        prior = GoalsRepo.prior_year_net_sales(year)
        return {'year': year, 'prior_year_net_sales': prior, 'growth_multiplier': multiplier,
                'suggested_annual_target': round(prior * multiplier, 2)}

    def get_year(self, year):
        version, days = GoalsRepo.get_year(year)
        if not version:
            return None
        return {
            **version,
            'annual_total': round(sum(day['target_amount'] for day in days), 2),
            'days': days,
            'locks': GoalsRepo.list_locks(year),
            'adjustments': GoalsRepo.list_adjustments(year),
        }

    def lock_period(self, year, version, period_type, period_key):
        record = GoalsRepo.get_version(year)
        if not record or record['version'] != version:
            raise GoalConflictError('目标版本已更新，请刷新后重试')
        if period_type not in {'year', 'quarter', 'month', 'week', 'date'}:
            raise GoalValidationError('不支持的锁定周期')
        _validate_period_key(year, period_type, period_key)

        locks = GoalsRepo.list_locks(year)
        if period_type == 'week':
            week_number = int(period_key[-2:])
            monday = date.fromisocalendar(year, week_number, 1)
            sunday = monday + timedelta(days=6)
            months = {day.strftime('%Y-%m') for day in (monday, sunday)}
            locked_months = {lock['period_key'] for lock in locks if lock['period_type'] == 'month'}
            if months & locked_months:
                raise GoalConflictError('周目标跨越或包含已锁定月份，不能锁定')
        elif period_type == 'month':
            month_number = int(period_key[-2:])
            for lock in locks:
                if lock['period_type'] != 'week':
                    continue
                monday = date.fromisocalendar(year, int(lock['period_key'][-2:]), 1)
                if any(day.month == month_number and day.year == year for day in (monday, monday + timedelta(days=6))):
                    raise GoalConflictError('月份包含已锁定周，不能锁定')

        lock_result = GoalsRepo.add_lock(year, period_type, period_key, version)
        if lock_result is None:
            raise GoalConflictError('目标版本已更新，请刷新后重试')
        if not lock_result:
            raise GoalConflictError('该周期已锁定')
        return {'year': year, 'version': version, 'period_type': period_type, 'period_key': period_key, 'locked': True}

    def periods(self, year):
        record = GoalsRepo.get_version(year)
        if not record:
            return None
        return {'year': year, 'version': record['version'], 'months': GoalsRepo.periods(year),
                'levels': GoalsRepo.period_summaries(year), 'actual': GoalsRepo.actual_summaries(year)}

    def adjust_period(self, year, version, period_type, period_key, target_amount, operator, reason, lock=False):
        if period_type not in {'year', 'quarter', 'month', 'week', 'date'}:
            raise GoalValidationError('不支持的目标周期')
        _validate_period_key(year, period_type, period_key)
        if float(target_amount) < 0:
            raise GoalValidationError('目标值不能为负数')
        if not operator or not reason:
            raise GoalValidationError('调整必须填写操作者和原因')
        result = GoalsRepo.adjust_period(
            year, version, period_type, period_key, float(target_amount), operator, reason, bool(lock)
        )
        if result is None:
            raise GoalConflictError('目标版本已更新，请刷新后重试')
        return {'year': year, 'version': result, 'period_type': period_type, 'period_key': period_key}


goals_service = GoalsService()
