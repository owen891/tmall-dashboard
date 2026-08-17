from datetime import date, timedelta

from repos.lifecycle_repo import LifecycleRepo
from services.classification_service import enabled_values, label_for
from services.settings_service import settings_service


class LifecycleConflictError(ValueError):
    pass


class LifecycleValidationError(ValueError):
    pass


STAGES = {'new', 'growth', 'breakout', 'mature', 'decline', 'clearance'}
SEASONAL = {'stable', 'spring_summer', 'autumn_winter', 'single_peak', 'double_peak', 'promotion_driven', 'manual', None}


def _continuous_days(rows):
    if not rows:
        return 0
    dates = {date.fromisoformat(row['date']) for row in rows}
    cursor = max(dates)
    count = 0
    while cursor in dates:
        count += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return count


def _seasonality(monthly):
    complete = [row for row in monthly if int(row.get('covered_days') or 0) >= int(row.get('expected_days') or 0)]
    if len({row['month'] for row in complete}) < 12:
        return None, None
    values = {}
    for row in complete:
        values.setdefault(int(str(row['month'])[-2:]), []).append(float(row['payment_amount'] or 0))
    averages = {month: sum(items) / len(items) for month, items in values.items()}
    baseline = sum(averages.values()) / len(averages)
    if baseline <= 0:
        return 'stable', 'product'
    high = {month for month, amount in averages.items() if amount >= baseline * 1.25}
    spring_summer = {3, 4, 5, 6, 7, 8}
    autumn_winter = {9, 10, 11, 12, 1, 2}
    if len(high & spring_summer) >= 3 and len(high & autumn_winter) >= 3:
        return 'double_peak', 'product'
    if len(high & spring_summer) >= 3:
        return 'spring_summer', 'product'
    if len(high & autumn_winter) >= 3:
        return 'autumn_winter', 'product'
    if len(high) >= 2:
        return 'single_peak', 'product'
    return 'stable', 'product'


class LifecycleService:
    def assessment(self, product, context=None, dictionaries=None):
        product_id = product['product_id']
        if context is None:
            daily = LifecycleRepo.daily_rows(product_id)
            monthly = LifecycleRepo.monthly_rows(product_id)
            profile = LifecycleRepo.get_profile(product_id) or {'version': 0}
            history = LifecycleRepo.history(product_id)
        else:
            daily = context['daily'].get(product_id, [])
            monthly = context['monthly'].get(product_id, [])
            profile = context['profiles'].get(product_id) or {'version': 0}
            history = context['history'].get(product_id, [])
        continuous = _continuous_days(daily)
        listed_at = product.get('list_date')
        listed_days = None
        if listed_at:
            try:
                listed_days = max(0, (date.today() - date.fromisoformat(str(listed_at)[:10])).days)
            except ValueError:
                listed_days = None
        if continuous < 60:
            recommended = 'data_accumulating'
            confidence = 'low'
            rationale = f'连续有效日 {continuous}/60，暂不输出生命周期算法结论。'
        else:
            amounts = [float(row['payment_amount'] or 0) for row in daily[-30:]]
            prior = [float(row['payment_amount'] or 0) for row in daily[-60:-30]]
            recent = sum(amounts); before = sum(prior)
            recent_conversion = [float(row.get('payment_conversion') or 0) for row in daily[-30:]]
            prior_conversion = [float(row.get('payment_conversion') or 0) for row in daily[-60:-30]]
            recent_cvr = sum(recent_conversion) / len(recent_conversion) if recent_conversion else None
            prior_cvr = sum(prior_conversion) / len(prior_conversion) if prior_conversion else None
            recent_spend = sum(float(row.get('ad_spend') or 0) for row in daily[-30:])
            ad_dependency = recent_spend / recent if recent > 0 else None
            if before <= 0 and recent > 0: recommended = 'new'
            elif before and recent >= before * 1.25: recommended = 'breakout' if recent >= before * 1.6 else 'growth'
            elif before and recent <= before * .65: recommended = 'decline'
            else: recommended = 'mature'
            confidence = 'high' if continuous >= 180 and before > 0 else 'medium' if continuous >= 120 else 'low'
            rationale = (f'连续有效日 {continuous}；最近 30 天支付金额 {recent:.2f}，前 30 天 {before:.2f}；'
                         f'转化率 {recent_cvr:.4f}' if recent_cvr is not None else
                         f'连续有效日 {continuous}；最近 30 天支付金额 {recent:.2f}，前 30 天 {before:.2f}；转化率数据不足')
        complete_months = len({row['month'] for row in monthly if int(row.get('covered_days') or 0) >= int(row.get('expected_days') or 0)})
        seasonal, seasonal_source = _seasonality(monthly)
        latest_date = date.fromisoformat(str(daily[-1]['date'])[:10]) if daily else date.today()
        next_key_date = profile.get('next_key_date')
        if not next_key_date and seasonal:
            high_months = {int(str(row['month'])[-2:]) for row in monthly[-12:] if float(row['payment_amount'] or 0) > 0}
            if high_months:
                next_month = min((month for month in high_months if month > latest_date.month), default=min(high_months))
                year = latest_date.year + (1 if next_month <= latest_date.month else 0)
                next_key_date = date(year, next_month, 1).isoformat()
        if profile.get('stage_locked') and profile.get('manual_stage'):
            stage = profile['manual_stage']
        else:
            stage = profile.get('manual_stage') or recommended
        dictionaries = dictionaries or settings_service.get()['classification_dictionaries']
        seasonal_value = profile.get('seasonal_attribute') or seasonal
        return {
            'product_id': product['product_id'], 'title': product['title'], 'stage': stage,
            'stage_label': label_for(dictionaries, 'lifecycle_stages', stage, stage),
            'recommended_stage': recommended, 'manual_stage': profile.get('manual_stage'),
            'locked': bool(profile.get('stage_locked')), 'seasonal_attribute': seasonal_value,
            'seasonal_label': label_for(
                dictionaries, 'seasonal_attributes', seasonal_value,
                '数据不足' if seasonal_value is None else seasonal_value,
            ),
            'seasonal_source': profile.get('seasonal_source') or seasonal_source,
            'confidence': profile.get('confidence') or confidence, 'rationale': profile.get('rationale') or rationale,
            'next_key_date': next_key_date, 'continuous_valid_days': continuous,
            'data_cutoff_date': daily[-1]['date'] if daily else None,
            'listed_days': listed_days, 'conversion_trend': {
                'recent': locals().get('recent_cvr'), 'prior': locals().get('prior_cvr')},
            'promotion_dependency': locals().get('ad_dependency'),
            'history': history,
            'complete_months': complete_months, 'version': profile.get('version', 0),
        }

    def list(self):
        context = LifecycleRepo.assessment_context()
        dictionaries = settings_service.get()['classification_dictionaries']
        return [self.assessment(product, context, dictionaries) for product in LifecycleRepo.product_rows()]

    def get(self, product_id):
        product = LifecycleRepo.product_row(product_id)
        return self.assessment(product) if product else None

    def update(self, product_id, payload):
        product = next((item for item in LifecycleRepo.product_rows() if item['product_id'] == product_id), None)
        if not product:
            raise LifecycleValidationError('商品不存在')
        current = self.assessment(product)
        if payload.get('version') != current['version']:
            raise LifecycleConflictError('生命周期版本已更新，请刷新后重试')
        manual = payload.get('manual_stage')
        seasonal = payload.get('seasonal_attribute')
        dictionaries = settings_service.get()['classification_dictionaries']
        manual_stages = enabled_values(dictionaries, 'lifecycle_stages') - {'data_accumulating'}
        if manual and manual not in manual_stages:
            raise LifecycleValidationError('生命周期阶段不合法')
        if seasonal is not None and seasonal not in enabled_values(dictionaries, 'seasonal_attributes'):
            raise LifecycleValidationError('季节属性不合法')
        if not payload.get('reason') or not payload.get('operator'):
            raise LifecycleValidationError('调整必须填写原因和操作者')
        profile = {**current, 'product_id': product_id, 'manual_stage': manual, 'seasonal_attribute': seasonal,
                   'seasonal_source': 'manual' if seasonal else None, 'stage_locked': bool(payload.get('lock')),
                   'version': current['version']}
        version = LifecycleRepo.upsert(profile, payload['reason'], payload['operator'])
        if version is None:
            raise LifecycleConflictError('生命周期版本已更新，请刷新后重试')
        return self.assessment(product)


lifecycle_service = LifecycleService()
