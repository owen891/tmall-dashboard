from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Rename columns in shop_targets
    result = conn.execute(text('PRAGMA table_info(shop_targets)'))
    columns = {row[1] for row in result}
    print('shop_targets columns:', columns)

    if 'target_gsv' in columns and 'gmv_target' not in columns:
        conn.execute(text('ALTER TABLE shop_targets RENAME COLUMN target_gsv TO gmv_target'))
        conn.commit()
        print('Renamed target_gsv to gmv_target')

    if 'target_conversion' in columns and 'conversion_target' not in columns:
        conn.execute(text('ALTER TABLE shop_targets RENAME COLUMN target_conversion TO conversion_target'))
        conn.commit()
        print('Renamed target_conversion to conversion_target')

    if 'target_ad_spend' in columns and 'ad_spend_target' not in columns:
        conn.execute(text('ALTER TABLE shop_targets RENAME COLUMN target_ad_spend TO ad_spend_target'))
        conn.commit()
        print('Renamed target_ad_spend to ad_spend_target')

    if 'remark' in columns and 'notes' not in columns:
        conn.execute(text('ALTER TABLE shop_targets RENAME COLUMN remark TO notes'))
        conn.commit()
        print('Renamed remark to notes')

    print('Done!')
