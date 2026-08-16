from copy import deepcopy
import re


DICTIONARY_GROUPS = ('tiers', 'styles', 'lifecycle_stages', 'seasonal_attributes')

DEFAULT_CLASSIFICATION_DICTIONARIES = {
    'tiers': [
        {'value': '爆款', 'label': '爆款', 'enabled': True, 'system': False},
        {'value': '引流款', 'label': '引流款', 'enabled': True, 'system': False},
        {'value': '利润款', 'label': '利润款', 'enabled': True, 'system': False},
        {'value': '形象款', 'label': '形象款', 'enabled': True, 'system': False},
    ],
    'styles': [],
    'lifecycle_stages': [
        {'value': 'data_accumulating', 'label': '数据积累中', 'enabled': True, 'system': True},
        {'value': 'new', 'label': '新品期', 'enabled': True, 'system': True},
        {'value': 'growth', 'label': '成长期', 'enabled': True, 'system': True},
        {'value': 'breakout', 'label': '爆发期', 'enabled': True, 'system': True},
        {'value': 'mature', 'label': '成熟期', 'enabled': True, 'system': True},
        {'value': 'decline', 'label': '衰退期', 'enabled': True, 'system': True},
        {'value': 'clearance', 'label': '清退期', 'enabled': True, 'system': True},
    ],
    'seasonal_attributes': [
        {'value': 'stable', 'label': '常年稳定型', 'enabled': True, 'system': True},
        {'value': 'spring_summer', 'label': '春夏型', 'enabled': True, 'system': True},
        {'value': 'autumn_winter', 'label': '秋冬型', 'enabled': True, 'system': True},
        {'value': 'single_peak', 'label': '单峰季节型', 'enabled': True, 'system': True},
        {'value': 'double_peak', 'label': '双峰季节型', 'enabled': True, 'system': True},
        {'value': 'promotion_driven', 'label': '节日/大促驱动型', 'enabled': True, 'system': True},
        {'value': 'manual', 'label': '人工维护', 'enabled': True, 'system': True},
    ],
}


class ClassificationValidationError(ValueError):
    pass


def default_dictionaries():
    return deepcopy(DEFAULT_CLASSIFICATION_DICTIONARIES)


def _custom_value(value, label):
    value = str(value or '').strip()
    if value:
        return value
    slug = re.sub(r'[^a-z0-9]+', '_', str(label).strip().lower()).strip('_')
    return slug or str(label).strip()


def normalize_dictionaries(value, existing=None):
    if not isinstance(value, dict) or set(value) != set(DICTIONARY_GROUPS):
        raise ClassificationValidationError('分类字典必须包含分层、风格、生命周期和季节属性')
    existing = existing or default_dictionaries()
    result = {}
    for group in DICTIONARY_GROUPS:
        items = value[group]
        if not isinstance(items, list):
            raise ClassificationValidationError('分类字典分组必须是列表')
        seen = set()
        normalized = []
        for raw in items:
            if not isinstance(raw, dict):
                raise ClassificationValidationError('分类字典项目格式错误')
            label = str(raw.get('label') or '').strip()
            if not label:
                raise ClassificationValidationError('分类名称不能为空')
            item_value = _custom_value(raw.get('value'), label)
            if item_value in seen:
                raise ClassificationValidationError(f'分类编码重复：{item_value}')
            seen.add(item_value)
            normalized.append({
                'value': item_value, 'label': label,
                'enabled': bool(raw.get('enabled', True)),
                'system': False,
            })
        result[group] = normalized

    for group in ('lifecycle_stages', 'seasonal_attributes'):
        required = {
            item['value'] for item in DEFAULT_CLASSIFICATION_DICTIONARIES[group] if item['system']
        }
        supplied = {item['value']: item for item in result[group]}
        if not required <= set(supplied):
            raise ClassificationValidationError('系统内置分类不能删除或修改编码')
        for key in required:
            supplied[key]['system'] = True
    return result


def merged_dictionaries(stored=None):
    if not stored:
        return default_dictionaries()
    try:
        return normalize_dictionaries(stored)
    except ClassificationValidationError:
        return default_dictionaries()


def enabled_values(dictionaries, group):
    return {item['value'] for item in dictionaries.get(group, []) if item.get('enabled')}


def label_for(dictionaries, group, value, fallback=None):
    if value is None:
        return fallback
    item = next((entry for entry in dictionaries.get(group, []) if entry['value'] == value), None)
    return item['label'] if item else (fallback if fallback is not None else value)
