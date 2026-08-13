import json

from db import get_db


class ImportRevertConflictError(ValueError):
    pass


class ImportRepo:
    @staticmethod
    def complete_product_daily_batch(batch, rows):
        inserted_count = 0
        updated_count = 0
        with get_db() as connection:
            try:
                connection.execute(
                    '''INSERT INTO import_batches (
                        id, source_type, source_filename, source_hash, status,
                        total_rows, valid_rows, invalid_rows, quality_summary
                    ) VALUES (?, ?, ?, ?, 'processing', ?, ?, ?, ?)''',
                    (
                        batch['id'], batch['source_type'], batch['source_filename'],
                        batch['source_hash'], batch['total_rows'], batch['valid_rows'],
                        batch['invalid_rows'], batch['quality_summary'],
                    ),
                )
                for row in rows:
                    existing = connection.execute(
                        'SELECT * FROM daily_data WHERE product_id = ? AND date = ?',
                        (row['product_id'], row['date']),
                    ).fetchone()
                    if existing:
                        updated_count += 1
                    else:
                        inserted_count += 1

                    connection.execute(
                        '''INSERT INTO import_batch_changes (batch_id, table_name, business_key, previous_row, written_by)
                           VALUES (?, 'daily_data', ?, ?, ?)''',
                        (
                            batch['id'], f"{row['product_id']}|{row['date']}",
                            json.dumps(dict(existing), ensure_ascii=False) if existing else None, batch['id'],
                        ),
                    )

                    connection.execute(
                        '''
                        INSERT INTO products (product_id, title, status)
                        VALUES (?, ?, 'active')
                        ON CONFLICT(product_id) DO UPDATE SET
                            title = COALESCE(NULLIF(excluded.title, ''), products.title),
                            updated_at = CURRENT_TIMESTAMP
                        ''',
                        (row['product_id'], row['product_name']),
                    )
                    connection.execute(
                        '''
                        INSERT INTO daily_data (
                            product_id, date, payment_amount, refund_amount, net_sales,
                            ipv, buyers, ad_spend, data_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(product_id, date) DO UPDATE SET
                            payment_amount = excluded.payment_amount,
                            refund_amount = excluded.refund_amount,
                            net_sales = excluded.net_sales,
                            ipv = excluded.ipv,
                            buyers = excluded.buyers,
                            ad_spend = excluded.ad_spend,
                            data_source = excluded.data_source,
                            imported_at = CURRENT_TIMESTAMP
                        ''',
                        (
                            row['product_id'], row['date'], row['payment_amount'],
                            row['successful_refund_amount'], row['net_sales'],
                            row['product_visitors'], row['payment_buyers'], row['ad_spend'],
                            batch['source_filename'],
                        ),
                    )

                connection.execute(
                    '''UPDATE import_batches
                       SET status = 'completed', inserted_count = ?, updated_count = ?,
                           completed_at = CURRENT_TIMESTAMP
                       WHERE id = ?''',
                    (inserted_count, updated_count, batch['id']),
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
        with get_db() as connection:
            try:
                connection.execute(
                    '''INSERT INTO import_batches (id, source_type, source_filename, source_hash, status,
                       total_rows, valid_rows, invalid_rows, quality_summary)
                       VALUES (?, ?, ?, ?, 'processing', ?, ?, ?, ?)''',
                    (batch['id'], batch['source_type'], batch['source_filename'], batch['source_hash'],
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
                connection.execute(
                    "UPDATE import_batches SET status = 'completed', inserted_count = ?, updated_count = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (inserted_count, updated_count, batch['id']),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return inserted_count, updated_count

    @staticmethod
    def list_batches(limit=100):
        with get_db() as connection:
            rows = connection.execute(
                '''SELECT id, source_type, source_filename, status, total_rows, valid_rows,
                          invalid_rows, inserted_count, updated_count, quality_summary,
                          created_at, completed_at
                   FROM import_batches ORDER BY created_at DESC LIMIT ?''',
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def revert_batch(batch_id):
        with get_db() as connection:
            try:
                batch = connection.execute(
                    'SELECT id, status FROM import_batches WHERE id = ?', (batch_id,)
                ).fetchone()
                if not batch:
                    return None
                if batch['status'] == 'reverted':
                    return False
                changes = connection.execute(
                    '''SELECT id, table_name, business_key, previous_row FROM import_batch_changes
                       WHERE batch_id = ? ORDER BY id DESC''', (batch_id,)
                ).fetchall()
                for change in changes:
                    newer = connection.execute(
                        '''SELECT 1 FROM import_batch_changes later
                           JOIN import_batches later_batch ON later_batch.id = later.batch_id
                           WHERE later.table_name = ? AND later.business_key = ?
                             AND later.id > ? AND later_batch.status = 'completed'
                           LIMIT 1''',
                        (change['table_name'], change['business_key'], change['id']),
                    ).fetchone()
                    if newer:
                        raise ImportRevertConflictError('该批次影响的数据已被后续成功导入覆盖，请先撤销后续批次')
                    table_name = change['table_name']
                    if table_name not in {'daily_data', 'store_daily_facts', 'promotion_daily_facts', 'weekly_data', 'monthly_data'}:
                        raise ValueError('不支持的撤销目标')
                    if table_name == 'daily_data':
                        key = dict(zip(('product_id', 'date'), change['business_key'].split('|', 1)))
                    else:
                        key = json.loads(change['business_key'])
                    where = ' AND '.join(f'{column} = ?' for column in key)
                    if change['previous_row'] is None:
                        connection.execute(
                            f'DELETE FROM {table_name} WHERE {where}', list(key.values())
                        )
                        continue
                    previous = json.loads(change['previous_row'])
                    columns = [key for key in previous if key != 'id']
                    connection.execute(
                        f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                        [previous[key] for key in columns],
                    )
                connection.execute(
                    "UPDATE import_batches SET status = 'reverted', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (batch_id,),
                )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise
