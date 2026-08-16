"""Canonical source specifications used by import-facing adapters."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpec:
    name: str
    required_fields: frozenset
    allowed_fields: frozenset
    key_fields: tuple
    target_table: str
    target_key_fields: tuple
    source_system: str


def _build_specs():
    from services.import_service import SOURCE_ALLOWED_FIELDS, SOURCE_KEY_FIELDS, SOURCE_REQUIREMENTS
    targets = {
        'product_day': ('daily_data', ('shop_id', 'product_id', 'date')),
        'dmp_product_day': ('daily_data', ('shop_id', 'product_id', 'date')),
        'store_day': ('store_daily_facts', ('shop_id', 'date')),
        'refund_day': ('store_daily_facts', ('shop_id', 'date')),
        'customer_day': ('store_daily_facts', ('shop_id', 'date')),
        'product_week': ('weekly_data', ('product_id', 'week_start')),
        'product_month': ('monthly_data', ('product_id', 'month')),
        'promotion_channel_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
        'promotion_campaign_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
        'promotion_unit_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
        'promotion_product_day': ('promotion_daily_facts', ('shop_id', 'date', 'channel', 'campaign_id', 'unit_id', 'product_id')),
    }
    return {
        name: SourceSpec(
            name=name,
            required_fields=frozenset(SOURCE_REQUIREMENTS[name]),
            allowed_fields=frozenset(SOURCE_ALLOWED_FIELDS[name]),
            key_fields=tuple(SOURCE_KEY_FIELDS[name]),
            target_table=targets[name][0],
            target_key_fields=tuple(targets[name][1]),
            source_system='dmp' if name == 'dmp_product_day' else 'business_advisor',
        )
        for name in SOURCE_REQUIREMENTS
    }


SOURCE_SPECS = _build_specs()


def get_source_spec(source_type):
    try:
        return SOURCE_SPECS[source_type]
    except KeyError as error:
        raise ValueError(f'unsupported source_type: {source_type}') from error
