"""Convert validated frames into ImportRepo-ready rows without DB access."""

from services.import_service import NUMERIC_FIELDS, PERCENTAGE_FIELDS, import_service


def normalize_rows(frame, mapping, spec, quality=None, shop_id='default', preview_id=None):
    source_type = spec.name if hasattr(spec, 'name') else str(spec)
    rows = []
    quality = quality or {}
    invalid_fields = {}
    for warning in quality.get('invalid_field_rows', quality.get('field_warnings', [])):
        invalid_fields.setdefault(int(warning.get('row_number', 0)) - 2, set()).add(warning.get('standard_field'))
    for index, source in frame.iterrows():
        def value(field, default=None):
            column = mapping.get(field)
            return source[column] if column else default

        row = {'shop_id': shop_id, 'date': import_service._date(value('date'))}
        for field in mapping:
            if field == 'date' or field in {'shop_id'}:
                continue
            if source_type == 'dmp_product_day' and field in invalid_fields.get(index, set()):
                continue
            raw = value(field)
            if raw is None or str(raw).strip() in {'', '-', '--', 'nan'}:
                continue
            if field in {'product_id', 'product_name', 'parent_product_id', 'product_type', 'sku_code', 'source_status', 'product_tags', 'product_growth_stage', 'channel', 'campaign_id', 'unit_id'}:
                row[field] = str(raw).strip()
            elif field in NUMERIC_FIELDS or field in PERCENTAGE_FIELDS:
                normalized = import_service._optional_number(raw, percentage=field in PERCENTAGE_FIELDS)
                if normalized is not None:
                    row[field] = normalized
            else:
                row[field] = str(raw).strip()
        if source_type.startswith('promotion_'):
            row.setdefault('channel', '')
            row.setdefault('campaign_id', '')
            row.setdefault('unit_id', '')
            row.setdefault('product_id', '')
        if 'payment_amount' in row and 'successful_refund_amount' in row:
            row['net_sales'] = row['payment_amount'] - row['successful_refund_amount']
        rows.append(row)
    return rows
