import json

from db import get_db, get_shop_id
from repos.audit_repo import AuditRepo
from services.source_resolution_service import _materialize_daily_fact, record_daily_observation


class ImportRevertConflictError(ValueError):
    pass


class ImportRevertScopeError(ValueError):
    pass


def _daily_business_key(shop_id, product_id, stat_date):
    return json.dumps({
        'shop_id': str(shop_id or 'default'),
        'product_id': str(product_id),
        'date': str(stat_date),
    }, ensure_ascii=False, sort_keys=True)


def _parse_daily_business_key(value):
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        return (
            str(parsed.get('shop_id') or 'default'),
            str(parsed['product_id']),
            str(parsed['date']),
        )
    product_id, stat_date = str(value).split('|', 1)
    return 'default', product_id, stat_date


class ImportRepo:
    @staticmethod
    def complete_product_daily_batch(batch, rows):
        inserted_count = 0
        updated_count = 0
        resolution_summary = {
            'fallback_filled': 0,
            'reference_only': 0,
            'conflicts': 0,
            'primary_kept': 0,
            'effective_unique': 0,
        }
        with get_db() as connection:
            try:
                shop_id = str(batch.get('shop_id') or next(
                    (row.get('shop_id') for row in rows if row.get('shop_id')), 'default'
                ))
                connection.execute(
                    '''INSERT INTO import_batches (
                        id, shop_id, source_type, source_filename, source_hash, status,
                        total_rows, valid_rows, invalid_rows, quality_summary
                    ) VALUES (?, ?, ?, ?, ?, 'processing', ?, ?, ?, ?)''',
                    (
                        batch['id'], shop_id, batch['source_type'], batch['source_filename'],
                        batch['source_hash'], batch['total_rows'], batch['valid_rows'],
                        batch['invalid_rows'], batch['quality_summary'],
                    ),
                )
                for row in rows:
                    shop_id = str(row.get('shop_id') or 'default')
                    existing = connection.execute(
                        'SELECT * FROM daily_data WHERE shop_id = ? AND product_id = ? AND date = ?',
                        (shop_id, row['product_id'], row['date']),
                    ).fetchone()
                    if existing:
                        updated_count += 1
                    else:
                        inserted_count += 1

                    connection.execute(
                        '''INSERT INTO import_batch_changes (batch_id, table_name, business_key, previous_row, written_by)
                           VALUES (?, 'daily_data', ?, ?, ?)''',
                        (
                            batch['id'], _daily_business_key(shop_id, row['product_id'], row['date']),
                            json.dumps(dict(existing), ensure_ascii=False) if existing else None, batch['id'],
                        ),
                    )

                    prior_product = connection.execute(
                        'SELECT title, parent_product_id, product_type, sku_code, source_status, product_tags FROM products WHERE product_id = ?',
                        (row['product_id'],),
                    ).fetchone()
                    connection.execute(
                        '''
                        INSERT INTO products (
                            product_id, title, status, parent_product_id, product_type,
                            sku_code, source_status, product_tags, product_growth_stage
                        ) VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(product_id) DO UPDATE SET
                            title = COALESCE(NULLIF(excluded.title, ''), products.title),
                            parent_product_id = COALESCE(NULLIF(excluded.parent_product_id, ''), products.parent_product_id),
                            product_type = COALESCE(NULLIF(excluded.product_type, ''), products.product_type),
                            sku_code = COALESCE(NULLIF(excluded.sku_code, ''), products.sku_code),
                            source_status = COALESCE(NULLIF(excluded.source_status, ''), products.source_status),
                            product_tags = COALESCE(NULLIF(excluded.product_tags, ''), products.product_tags),
                            product_growth_stage = COALESCE(NULLIF(excluded.product_growth_stage, ''), products.product_growth_stage),
                            updated_at = CURRENT_TIMESTAMP
                        ''',
                        (
                            row['product_id'], row.get('product_name', ''), row.get('parent_product_id', ''),
                            row.get('product_type', ''), row.get('sku_code', ''), row.get('source_status', ''),
                            row.get('product_tags', ''), row.get('product_growth_stage', ''),
                        ),
                    )
                    if batch['source_type'] == 'dmp_product_day' and prior_product:
                        # DMP may create a missing product, but never replace
                        # an identity already owned by the business-advisor feed.
                        connection.execute(
                            '''UPDATE products
                               SET title = ?, parent_product_id = ?, product_type = ?, sku_code = ?,
                                   source_status = ?, product_tags = ?
                               WHERE product_id = ?''',
                            (*tuple(prior_product), row['product_id']),
                        )
                    resolution_row = dict(row)
                    result = record_daily_observation(
                        connection,
                        resolution_row,
                        source_type=batch['source_type'],
                        source_filename=batch['source_filename'],
                        source_batch_id=batch['id'],
                        shop_id=shop_id,
                    )
                    resolution_summary['fallback_filled'] += len(result.get('fallback_fields', []))
                    resolution_summary['reference_only'] += len(result.get('reference_fields', []))
                    resolution_summary['conflicts'] += len(result.get('conflict_fields', []))
                    resolution_summary['primary_kept'] += len(result.get('primary_fields', []))
                    resolution_summary['effective_unique'] += len(result.get('unique_fields', []))
                    if result['inserted'] and existing:
                        inserted_count -= 1
                        updated_count += 1

                quality_summary = json.loads(batch['quality_summary']) if isinstance(batch.get('quality_summary'), str) else dict(batch.get('quality_summary') or {})
                quality_summary['source_resolution'] = resolution_summary
                batch['quality_summary'] = json.dumps(quality_summary, ensure_ascii=False)
                connection.execute(
                    '''UPDATE import_batches
                       SET status = 'completed', inserted_count = ?, updated_count = ?, quality_summary = ?,
                           completed_at = CURRENT_TIMESTAMP
                       WHERE id = ?''',
                    (inserted_count, updated_count, json.dumps(quality_summary, ensure_ascii=False), batch['id']),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return inserted_count, updated_count

    @staticmethod
    def complete_generic_batch(batch, table_name, key_columns, rows):
        allowed = {
            'store_daily_facts', 'promotion_daily_facts', 'weekly_data', 'monthly_data',
        }
        if table_name not in allowed:
            raise ValueError('不支持的导入目标')
        inserted_count = updated_count = 0
        resolution_summary = {
            'fallback_filled': 0, 'reference_only': 0, 'conflicts': 0,
            'primary_kept': 0, 'effective_unique': 0,
        }
        with get_db() as connection:
            try:
                connection.execute(
                    '''INSERT INTO import_batches (id, shop_id, source_type, source_filename, source_hash, status,
                       total_rows, valid_rows, invalid_rows, quality_summary)
                       VALUES (?, ?, ?, ?, ?, 'processing', ?, ?, ?, ?)''',
                    (batch['id'], batch.get('shop_id', 'default'), batch['source_type'], batch['source_filename'], batch['source_hash'],
                     batch['total_rows'], batch['valid_rows'], batch['invalid_rows'], batch['quality_summary']),
                )
                for row in rows:
                    where = ' AND '.join(f'{column} = ?' for column in key_columns)
                    values = [row[column] for column in key_columns]
                    existing = connection.execute(f'SELECT * FROM {table_name} WHERE {where}', values).fetchone()
                    if existing: updated_count += 1
                    else: inserted_count += 1
                    connection.execute(
                        '''INSERT INTO import_batch_changes (batch_id, table_name, business_key, previous_row, written_by)
                           VALUES (?, ?, ?, ?, ?)''',
                        (batch['id'], table_name, json.dumps({key: row[key] for key in key_columns}, ensure_ascii=False),
                         json.dumps(dict(existing), ensure_ascii=False) if existing else None, batch['id']),
                    )
                    columns = list(row)
                    updates = ', '.join(f'{column} = excluded.{column}' for column in columns if column not in key_columns)
                    connection.execute(
                        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
                        f"ON CONFLICT({', '.join(key_columns)}) DO UPDATE SET {updates or key_columns[0] + '=' + key_columns[0]}",
                        [row[column] for column in columns],
                    )
                if table_name == 'promotion_daily_facts':
                    grouped = {}
                    for row in rows:
                        product_id = str(row.get('product_id') or '').strip()
                        if not product_id:
                            continue
                        key = (str(row.get('shop_id') or 'default'), product_id, row['date'])
                        item = grouped.setdefault(key, {
                            'shop_id': str(row.get('shop_id') or 'default'),
                            'product_id': product_id, 'date': row['date'],
                            'ad_spend': 0.0, 'attributed_payment_amount': 0.0,
                            'has_spend': False, 'has_attributed': False,
                        })
                        if row.get('ad_spend') is not None:
                            item['ad_spend'] += float(row['ad_spend']); item['has_spend'] = True
                        if row.get('attributed_payment_amount') is not None:
                            item['attributed_payment_amount'] += float(row['attributed_payment_amount']); item['has_attributed'] = True
                    for (shop_id, product_id, stat_date), observation in grouped.items():
                        existing_fact = connection.execute(
                            'SELECT * FROM daily_data WHERE shop_id = ? AND product_id = ? AND date = ?',
                            (shop_id, product_id, stat_date),
                        ).fetchone()
                        connection.execute(
                            '''INSERT INTO import_batch_changes (batch_id, table_name, business_key, previous_row, written_by)
                               VALUES (?, 'daily_data', ?, ?, ?)''',
                            (batch['id'], _daily_business_key(shop_id, product_id, stat_date),
                             json.dumps(dict(existing_fact), ensure_ascii=False) if existing_fact else None,
                             batch['id']),
                        )
                        payload = {'product_id': product_id, 'date': stat_date}
                        if observation['has_spend']:
                            payload['ad_spend'] = observation['ad_spend']
                        if observation['has_attributed']:
                            payload['attributed_payment_amount'] = observation['attributed_payment_amount']
                        result = record_daily_observation(
                            connection, payload, source_type=batch['source_type'],
                            source_system='promotion_tool', source_filename=batch['source_filename'],
                            source_batch_id=batch['id'],
                            shop_id=observation.get('shop_id', 'default'),
                        )
                        resolution_summary['fallback_filled'] += len(result.get('fallback_fields', []))
                        resolution_summary['reference_only'] += len(result.get('reference_fields', []))
                        resolution_summary['conflicts'] += len(result.get('conflict_fields', []))
                        resolution_summary['primary_kept'] += len(result.get('primary_fields', []))
                        resolution_summary['effective_unique'] += len(result.get('unique_fields', []))
                quality_summary = json.loads(batch['quality_summary']) if isinstance(batch.get('quality_summary'), str) else dict(batch.get('quality_summary') or {})
                quality_summary['source_resolution'] = resolution_summary
                connection.execute(
                    "UPDATE import_batches SET status = 'completed', inserted_count = ?, updated_count = ?, quality_summary = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (inserted_count, updated_count, json.dumps(quality_summary, ensure_ascii=False), batch['id']),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return inserted_count, updated_count

    @staticmethod
    def list_batches(limit=100):
        shop_id = get_shop_id()
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT id, shop_id, source_type, source_filename, source_hash, status, total_rows, valid_rows,
                          invalid_rows, inserted_count, updated_count, quality_summary,
                          created_at, completed_at
                   FROM import_batches WHERE shop_id = ? ORDER BY created_at DESC LIMIT ?''',
                (shop_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def revert_batch(batch_id, shop_id=None):
        with get_db() as connection:
            try:
                batch = connection.execute(
                    'SELECT id, shop_id, status FROM import_batches WHERE id = ?', (batch_id,)
                ).fetchone()
                if not batch:
                    return None
                if shop_id is not None and str(batch['shop_id'] or 'default') != str(shop_id):
                    raise ImportRevertScopeError('导入批次不属于当前店铺')
                if batch['status'] == 'reverted':
                    return False
                changes = connection.execute(
                    '''SELECT id, table_name, business_key, previous_row, reverted_at FROM import_batch_changes
                       WHERE batch_id = ? ORDER BY id DESC''', (batch_id,)
                ).fetchall()
                restored_count = 0
                skipped_count = 0
                affected_products = set()
                affected_dates = {}
                revertable_observation_keys = set()
                for change in changes:
                    if change['reverted_at']:
                        continue
                    newer = connection.execute(
                        '''SELECT 1 FROM import_batch_changes later
                           JOIN import_batches later_batch ON later_batch.id = later.batch_id
                           WHERE later.table_name = ? AND later.business_key = ?
                             AND later.id > ? AND later.reverted_at IS NULL
                             AND later_batch.status IN ('completed', 'partially_reverted')
                           LIMIT 1''',
                        (change['table_name'], change['business_key'], change['id']),
                    ).fetchone()
                    if newer:
                        skipped_count += 1
                        continue
                    table_name = change['table_name']
                    if table_name == 'daily_data':
                        shop_id, product_id, fact_date = _parse_daily_business_key(change['business_key'])
                        # product_actions is a legacy single-shop table. A
                        # non-default import must not mutate default actions.
                        if shop_id == 'default':
                            affected_products.add(product_id)
                        affected_dates.setdefault(product_id, set()).add(fact_date)
                        revertable_observation_keys.add((shop_id, product_id, fact_date))
                    if table_name not in {'daily_data', 'store_daily_facts', 'promotion_daily_facts', 'weekly_data', 'monthly_data'}:
                        raise ValueError('不支持的撤销目标')
                    if table_name == 'daily_data':
                        shop_id, product_id, fact_date = _parse_daily_business_key(change['business_key'])
                        key = {'shop_id': shop_id, 'product_id': product_id, 'date': fact_date}
                    else:
                        key = json.loads(change['business_key'])
                    where = ' AND '.join(f'{column} = ?' for column in key)
                    if change['previous_row'] is None:
                        connection.execute(
                            f'DELETE FROM {table_name} WHERE {where}', list(key.values())
                        )
                        restored_count += 1
                        connection.execute('UPDATE import_batch_changes SET reverted_at = CURRENT_TIMESTAMP WHERE id = ?', (change['id'],))
                        continue
                    previous = json.loads(change['previous_row'])
                    columns = [key for key in previous if key != 'id']
                    connection.execute(
                        f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                        [previous[key] for key in columns],
                    )
                    restored_count += 1
                    connection.execute('UPDATE import_batch_changes SET reverted_at = CURRENT_TIMESTAMP WHERE id = ?', (change['id'],))
                for shop_id, product_id, fact_date in revertable_observation_keys:
                    connection.execute(
                        '''DELETE FROM daily_data_observations
                           WHERE source_batch_id = ? AND shop_id = ? AND product_id = ? AND date = ?''',
                        (batch_id, shop_id, product_id, fact_date),
                    )
                    _materialize_daily_fact(
                        connection, product_id, fact_date,
                        shop_id=shop_id, preserve_legacy=False,
                    )
                remaining = connection.execute(
                    'SELECT COUNT(*) FROM import_batch_changes WHERE batch_id = ? AND reverted_at IS NULL', (batch_id,)
                ).fetchone()[0]
                final_status = 'partially_reverted' if remaining else 'reverted'
                connection.execute(
                    "UPDATE import_batches SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (final_status, batch_id),
                )
                if affected_products:
                    placeholders = ','.join('?' for _ in affected_products)
                    connection.execute(
                        f'''INSERT INTO product_action_history
                            (action_id, from_status, to_status, detail, operator, version)
                            SELECT id, status,
                                   CASE WHEN status = 'executing' THEN 'observing' ELSE 'pending_review' END,
                                   '导入撤销影响观察窗口，原结果失效并等待重算', 'system', version + 1
                            FROM product_actions
                            WHERE product_id IN ({placeholders})
                              AND status IN ('completed', 'observing', 'executing')
                              AND EXISTS (
                                SELECT 1 FROM import_batch_changes bc
                                WHERE bc.batch_id = ? AND bc.table_name = 'daily_data'
                                  AND CASE WHEN json_valid(bc.business_key)
                                        THEN json_extract(bc.business_key, '$.product_id')
                                        ELSE substr(bc.business_key, 1, instr(bc.business_key, '|') - 1) END = product_actions.product_id
                                  AND date(CASE WHEN json_valid(bc.business_key)
                                        THEN json_extract(bc.business_key, '$.date')
                                        ELSE substr(bc.business_key, instr(bc.business_key, '|') + 1) END)
                                      BETWEEN date(COALESCE(product_actions.executed_at, product_actions.planned_at), '-' || COALESCE(product_actions.observer_window_days, 0) || ' day')
                                          AND date(COALESCE(product_actions.executed_at, product_actions.planned_at), '+' || COALESCE(product_actions.observer_window_days, 0) || ' day')
                                  AND date(CASE WHEN json_valid(bc.business_key)
                                        THEN json_extract(bc.business_key, '$.date')
                                        ELSE substr(bc.business_key, instr(bc.business_key, '|') + 1) END)
                                      <> date(COALESCE(product_actions.executed_at, product_actions.planned_at))
                              )''',
                        [*affected_products, batch_id],
                    )
                    connection.execute(
                        f'''UPDATE product_actions
                            SET status = CASE WHEN status = 'executing' THEN 'observing' ELSE 'pending_review' END,
                                calculation_note = COALESCE(calculation_note, '') ||
                                  '；导入撤销影响观察窗口，原结果已失效，保留结果和复盘供重新确认。',
                                version = version + 1, updated_at = CURRENT_TIMESTAMP
                            WHERE product_id IN ({placeholders})
                              AND status IN ('completed', 'observing', 'executing')
                              AND EXISTS (
                                SELECT 1 FROM import_batch_changes bc
                                WHERE bc.batch_id = ? AND bc.table_name = 'daily_data'
                                  AND CASE WHEN json_valid(bc.business_key)
                                        THEN json_extract(bc.business_key, '$.product_id')
                                        ELSE substr(bc.business_key, 1, instr(bc.business_key, '|') - 1) END = product_actions.product_id
                                  AND date(CASE WHEN json_valid(bc.business_key)
                                        THEN json_extract(bc.business_key, '$.date')
                                        ELSE substr(bc.business_key, instr(bc.business_key, '|') + 1) END)
                                      BETWEEN date(COALESCE(product_actions.executed_at, product_actions.planned_at), '-' || COALESCE(product_actions.observer_window_days, 0) || ' day')
                                          AND date(COALESCE(product_actions.executed_at, product_actions.planned_at), '+' || COALESCE(product_actions.observer_window_days, 0) || ' day')
                                  AND date(CASE WHEN json_valid(bc.business_key)
                                        THEN json_extract(bc.business_key, '$.date')
                                        ELSE substr(bc.business_key, instr(bc.business_key, '|') + 1) END)
                                      <> date(COALESCE(product_actions.executed_at, product_actions.planned_at))
                              )''',
                        [*affected_products, batch_id],
                    )
                AuditRepo.record(
                    'import_batch', batch_id, 'revert', 'admin', '撤销导入批次',
                    {'status': batch['status']},
                    {'status': final_status, 'restored_count': restored_count, 'skipped_count': skipped_count},
                    connection=connection,
                )
                connection.commit()
                return {'restored_count': restored_count, 'skipped_count': skipped_count}
            except Exception:
                connection.rollback()
                raise
