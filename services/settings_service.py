from repos.settings_repo import SettingsRepo


DEFAULTS = {
    'shop_name': '', 'timezone': 'Asia/Shanghai', 'currency': 'CNY',
    'week_starts_on': 'monday', 'annual_target_default': 0.0,
    'lifecycle_thresholds': {'continuous_days': 60, 'seasonal_months': 12},
    'field_mappings': {}, 'mapping_templates': {},
    'product_view_template': 'default', 'view_templates': {'default': ['net_sales', 'payment_amount', 'payment_conversion', 'refund_rate', 'roi']},
}


class SettingsValidationError(ValueError):
    pass


class SettingsService:
    def get(self):
        return {**DEFAULTS, **SettingsRepo.get_all()}

    def update(self, payload):
        unknown = set(payload) - set(DEFAULTS)
        if unknown:
            raise SettingsValidationError(f'不允许修改配置：{", ".join(sorted(unknown))}')
        values = {key: payload[key] for key in payload}
        if 'timezone' in values and values['timezone'] != 'Asia/Shanghai':
            raise SettingsValidationError('当前版本固定使用 Asia/Shanghai 时区')
        if 'currency' in values and values['currency'] != 'CNY':
            raise SettingsValidationError('当前版本固定使用 CNY 货币')
        if 'week_starts_on' in values and values['week_starts_on'] not in {'monday', 'sunday'}:
            raise SettingsValidationError('周起始日必须为 monday 或 sunday')
        if 'annual_target_default' in values:
            try:
                values['annual_target_default'] = float(values['annual_target_default'])
            except (TypeError, ValueError) as error:
                raise SettingsValidationError('年度目标默认值必须是数字') from error
        if 'annual_target_default' in values and values['annual_target_default'] < 0:
            raise SettingsValidationError('annual_target_default cannot be negative')
        for key in ('lifecycle_thresholds', 'field_mappings', 'mapping_templates', 'view_templates'):
            if key in values and not isinstance(values[key], dict):
                raise SettingsValidationError(f'{key} must be an object')
        if 'lifecycle_thresholds' in values:
            thresholds = values['lifecycle_thresholds']
            if int(thresholds.get('continuous_days', 60)) < 60 or int(thresholds.get('seasonal_months', 12)) < 12:
                raise SettingsValidationError('lifecycle thresholds are below the minimum')
        SettingsRepo.upsert(values)
        return self.get()


settings_service = SettingsService()
