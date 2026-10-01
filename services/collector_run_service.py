"""Persistent run records for API-driven collectors.

This is intentionally small: it gives the existing subprocess-based collector
API a durable run id without changing the collector scripts yet. Later stages
can add leases, checkpoints and worker ownership on top of these records.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import gzip
import hashlib
import json
from pathlib import Path

from db import get_db


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_run(source_key, shop_id, *, db_path=None, mode='manual', window_start=None,
               window_end=None, requested_by='dashboard'):
    run_id = uuid4().hex
    now = _now()
    with get_db(db_path) as conn:
        conn.execute(
            '''INSERT INTO collector_runs
               (id, source_key, shop_id, window_start, window_end, mode, status,
                requested_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)''',
            (run_id, source_key, shop_id, window_start, window_end, mode,
             requested_by, now, now),
        )
        conn.commit()
    return run_id


def update_run(run_id, *, status=None, db_path=None, attempt=None, worker_id=None,
               error_code=None, error_message=None, stats=None):
    assignments = ['updated_at = ?']
    values = [_now()]
    if status is not None:
        assignments.append('status = ?')
        values.append(status)
        if status == 'running':
            assignments.append('started_at = COALESCE(started_at, ?)')
            values.append(_now())
        if status in {'succeeded', 'succeeded_with_warnings', 'partial', 'blocked',
                      'auth_required', 'failed', 'cancelled'}:
            assignments.append('finished_at = ?')
            values.append(_now())
    if attempt is not None:
        assignments.append('attempt = ?')
        values.append(attempt)
    if worker_id is not None:
        assignments.append('worker_id = ?')
        values.append(worker_id)
    if error_code is not None:
        assignments.append('error_code = ?')
        values.append(error_code)
    if error_message is not None:
        assignments.append('error_message = ?')
        values.append(str(error_message)[:2000])
    if stats is not None:
        import json
        assignments.append('stats_json = ?')
        values.append(json.dumps(stats, ensure_ascii=False))
    values.append(run_id)
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE collector_runs SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        conn.commit()


def get_run(run_id, *, db_path=None):
    with get_db(db_path) as conn:
        row = conn.execute('SELECT * FROM collector_runs WHERE id = ?', (run_id,)).fetchone()
    return dict(row) if row else None


ACTIVE_RUN_STATUSES = {'queued', 'running'}
TERMINAL_RUN_STATUSES = {
    'succeeded', 'succeeded_with_warnings', 'partial', 'blocked',
    'auth_required', 'failed', 'cancelled',
}


def _parse_timestamp(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reconcile_stale_runs(*, db_path=None, stale_after_seconds=7200, now=None):
    """Fail abandoned queued/running runs and release their leases.

    A collector process is considered abandoned only when its durable
    ``updated_at`` is older than the threshold and its database lease is
    missing or expired. The operation is idempotent and returns the runs
    changed during this call.
    """
    threshold = max(1, int(stale_after_seconds))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    cutoff = current - timedelta(seconds=threshold)
    changed = []
    with get_db(db_path) as conn:
        rows = conn.execute(
            '''SELECT id, source_key, shop_id, status, updated_at, created_at
               FROM collector_runs
               WHERE status IN ('queued', 'running')'''
        ).fetchall()
        for row in rows:
            updated_at = _parse_timestamp(row['updated_at'] or row['created_at'])
            if not updated_at or updated_at > cutoff:
                continue
            lease = conn.execute(
                '''SELECT lease_until FROM collector_leases
                   WHERE source_key = ? AND shop_id = ? AND run_id = ?''',
                (row['source_key'], row['shop_id'], row['id']),
            ).fetchone()
            lease_until = _parse_timestamp(lease['lease_until']) if lease else None
            if lease_until and lease_until > current:
                continue
            message = (
                f"采集运行超过 {threshold} 秒未更新，已自动标记为失败"
            )
            conn.execute(
                '''UPDATE collector_runs
                   SET status='failed', error_code='STALE_RUN',
                       error_message=?, finished_at=?, updated_at=?
                   WHERE id=? AND status IN ('queued', 'running')''',
                (message, current.isoformat(), current.isoformat(), row['id']),
            )
            conn.execute(
                '''UPDATE collector_checkpoints
                   SET status='failed', last_error_code='STALE_RUN',
                       last_error_message=?, finished_at=?, updated_at=?
                   WHERE run_id=? AND status IN ('queued', 'running')''',
                (message, current.isoformat(), current.isoformat(), row['id']),
            )
            existing_quality = conn.execute(
                '''SELECT 1 FROM collector_quality_results
                   WHERE run_id=? AND rule_key='stale_run' LIMIT 1''',
                (row['id'],),
            ).fetchone()
            if not existing_quality:
                conn.execute(
                    '''INSERT INTO collector_quality_results
                       (run_id, rule_key, severity, expected_value,
                        actual_value, status, message)
                       VALUES (?, 'stale_run', 'error', 'active',
                               'abandoned', 'failed', ?)''',
                    (row['id'], message),
                )
            conn.execute(
                '''DELETE FROM collector_leases
                   WHERE source_key=? AND shop_id=? AND run_id=?''',
                (row['source_key'], row['shop_id'], row['id']),
            )
            changed.append({
                'id': row['id'],
                'source_key': row['source_key'],
                'shop_id': row['shop_id'],
                'previous_status': row['status'],
                'status': 'failed',
                'error_code': 'STALE_RUN',
            })
        if changed:
            conn.commit()
    return changed


def latest_runs_by_source(*, db_path=None, shop_id=None):
    """Return the newest durable run for each source key."""
    with get_db(db_path) as conn:
        params = []
        shop_clause = ''
        if shop_id is not None:
            shop_clause = ' AND candidate.shop_id = ?'
            params.append(shop_id)
        query = f'''
            SELECT run.*
            FROM collector_runs run
            WHERE NOT EXISTS (
                SELECT 1
                FROM collector_runs candidate
                WHERE candidate.source_key = run.source_key
                  {shop_clause}
                  AND (
                      candidate.created_at > run.created_at
                      OR (
                          candidate.created_at = run.created_at
                          AND candidate.id > run.id
                      )
                  )
            )
        '''
        if shop_id is not None:
            query += ' AND run.shop_id = ?'
            params.append(shop_id)
        query += ' ORDER BY run.source_key'
        rows = conn.execute(query, params).fetchall()
    return {row['source_key']: dict(row) for row in rows}


def upsert_checkpoint(run_id, unit_type, unit_key, *, db_path=None, status,
                      page_no=None, cursor=None, row_count=0, source_hash=None,
                      error_code=None, error_message=None):
    """Persist one resumable collection unit.

    ``page_no`` is part of the natural key so paginated collectors can resume
    without overwriting a different page of the same unit.
    """
    now = _now()
    with get_db(db_path) as conn:
        conn.execute(
            '''INSERT INTO collector_checkpoints
               (run_id, unit_type, unit_key, page_no, cursor, status, row_count,
                source_hash, last_error_code, last_error_message, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(run_id, unit_type, unit_key, page_no) DO UPDATE SET
                 cursor=excluded.cursor, status=excluded.status,
                 row_count=excluded.row_count, source_hash=excluded.source_hash,
                 last_error_code=excluded.last_error_code,
                 last_error_message=excluded.last_error_message,
                 updated_at=excluded.updated_at''',
            (run_id, unit_type, unit_key, page_no, cursor, status, row_count,
             source_hash, error_code, str(error_message)[:2000] if error_message else None, now),
        )
        conn.commit()


def list_checkpoints(run_id, *, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            '''SELECT * FROM collector_checkpoints
               WHERE run_id = ? ORDER BY unit_type, unit_key, page_no''',
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_quality_results(run_id, *, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            '''SELECT * FROM collector_quality_results
               WHERE run_id = ? ORDER BY id''',
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def record_quality_result(run_id, rule_key, *, severity='error', expected_value=None,
                          actual_value=None, status='passed', message=None, db_path=None):
    """Persist one quality-gate observation for a collector run."""
    with get_db(db_path) as conn:
        conn.execute(
            '''INSERT INTO collector_quality_results
               (run_id, rule_key, severity, expected_value, actual_value, status, message)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (run_id, rule_key, severity,
             None if expected_value is None else str(expected_value),
             None if actual_value is None else str(actual_value), status,
             None if message is None else str(message)[:2000]),
        )
        conn.commit()


def quality_gate(run_id, *, db_path=None):
    """Summarize persisted quality observations into a publish decision."""
    results = list_quality_results(run_id, db_path=db_path)
    failed = [row for row in results if row.get('status') in {'failed', 'blocked'}
              and row.get('severity') in {'error', 'critical'}]
    return {
        'status': 'failed' if failed else ('passed' if results else 'not-evaluated'),
        'rules': len(results),
        'failed_rules': len(failed),
    }


def record_health_alert(source_key, alert_type, message, *, severity='warning',
                        fingerprint=None, details=None, db_path=None):
    """Upsert an open operational alert without creating notification spam."""
    fingerprint = fingerprint or hashlib.sha256(
        f'{source_key}:{alert_type}'.encode('utf-8')).hexdigest()[:32]
    payload = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    with get_db(db_path) as conn:
        conn.execute(
            '''INSERT INTO collector_health_alerts
               (source_key, alert_type, severity, fingerprint, message, details_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_key, alert_type, fingerprint, status) DO UPDATE SET
                 severity=excluded.severity, message=excluded.message,
                 details_json=excluded.details_json, last_seen_at=CURRENT_TIMESTAMP,
                 resolved_at=NULL''',
            (source_key, alert_type, severity, fingerprint, message, payload),
        )
        conn.commit()
    return fingerprint


def resolve_health_alert(source_key, alert_type, fingerprint, *, db_path=None):
    with get_db(db_path) as conn:
        conn.execute(
            '''UPDATE collector_health_alerts
               SET status='resolved', resolved_at=CURRENT_TIMESTAMP,
                   last_seen_at=CURRENT_TIMESTAMP
               WHERE source_key=? AND alert_type=? AND fingerprint=? AND status='open' ''',
            (source_key, alert_type, fingerprint),
        )
        conn.commit()


def list_health_alerts(*, source_key=None, status='open', db_path=None):
    with get_db(db_path) as conn:
        if source_key:
            rows = conn.execute(
                '''SELECT * FROM collector_health_alerts
                   WHERE source_key=? AND status=? ORDER BY last_seen_at DESC''',
                (source_key, status),
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT * FROM collector_health_alerts
                   WHERE status=? ORDER BY last_seen_at DESC''', (status,)
            ).fetchall()
    return [dict(row) for row in rows]


def save_schema_snapshot(source_key, schema, *, db_path=None):
    """Persist a canonical catalog schema and return change metadata."""
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    schema_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    with get_db(db_path) as conn:
        previous = conn.execute(
            '''SELECT schema_hash FROM collector_schema_snapshots
               WHERE source_key=? ORDER BY observed_at DESC, id DESC LIMIT 1''',
            (source_key,),
        ).fetchone()
        conn.execute(
            '''INSERT OR IGNORE INTO collector_schema_snapshots
               (source_key, schema_hash, schema_json) VALUES (?, ?, ?)''',
            (source_key, schema_hash, canonical),
        )
        conn.commit()
    return {
        'source_key': source_key,
        'schema_hash': schema_hash,
        'previous_hash': previous['schema_hash'] if previous else None,
        'changed': bool(previous and previous['schema_hash'] != schema_hash),
    }


def persist_artifact(run_id, artifact_type, content, *, db_path=None):
    """Store compressed raw collector output beside the configured database."""
    raw = content.encode('utf-8', errors='replace') if isinstance(content, str) else bytes(content or b'')
    digest = hashlib.sha256(raw).hexdigest()
    base_dir = Path(db_path).resolve().parent if db_path else Path.cwd() / 'data'
    artifact_dir = base_dir / 'collector_artifacts'
    artifact_dir.mkdir(parents=True, exist_ok=True)
    target = artifact_dir / f'{run_id}-{artifact_type}-{digest[:16]}.json.gz'
    with gzip.open(target, 'wb') as handle:
        handle.write(raw)
    with get_db(db_path) as conn:
        conn.execute(
            '''INSERT INTO collector_artifacts
               (run_id, artifact_type, path, sha256, size_bytes)
               VALUES (?, ?, ?, ?, ?)''',
            (run_id, artifact_type, str(target), digest, len(raw)),
        )
        conn.commit()
    return {'path': str(target), 'sha256': digest, 'size_bytes': len(raw)}


def list_artifacts(run_id, *, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            'SELECT * FROM collector_artifacts WHERE run_id = ? ORDER BY id',
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_data_staging(batch_id, *, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            '''SELECT id, source_key, batch_id, unit_type, unit_key,
                      payload_json, status, quality_message, created_at, published_at
               FROM collector_data_staging
               WHERE batch_id = ? OR batch_id LIKE ? ORDER BY id''',
            (batch_id, f'{batch_id}:%'),
        ).fetchall()
    return [dict(row) for row in rows]


def summarize_data_staging(rows):
    """Return deterministic quality counters for a staging batch."""
    status_counts = {}
    unit_counts = {}
    empty_payload = 0
    for row in rows:
        status = row.get('status') or 'unknown'
        status_counts[status] = status_counts.get(status, 0) + 1
        unit_key = (row.get('unit_type') or 'row', row.get('unit_key') or '')
        unit_counts[unit_key] = unit_counts.get(unit_key, 0) + 1
        payload = row.get('payload_json')
        if payload in (None, '', '{}', '[]'):
            empty_payload += 1
    duplicate_units = [
        {'unit_type': key[0], 'unit_key': key[1], 'count': count}
        for key, count in sorted(unit_counts.items()) if count > 1
    ]
    rejected = status_counts.get('rejected', 0)
    quality_status = 'failed' if empty_payload or rejected or duplicate_units else 'passed'
    return {
        'status': quality_status,
        'row_count': len(rows),
        'status_counts': status_counts,
        'empty_payload_count': empty_payload,
        'duplicate_unit_count': len(duplicate_units),
        'duplicate_units': duplicate_units,
        'rejected_count': rejected,
    }


def stage_source_snapshot(batch_id, source_key, table, date_col, *, db_path=None):
    """Snapshot the latest successful collector partition into audit staging.

    Legacy collectors still write their own fact tables. This adapter gives
    those collectors the same auditable staging and quality contract while
    they are migrated to native two-phase publishing.
    """
    import json as _json
    if source_key == 'dts_market':
        return _stage_dts_market_snapshot(batch_id, db_path=db_path)
    allowed_tables = {
        'daily_data', 'monthly_data', 'sycm_flow_source_daily',
        'sycm_item_flow_source_daily', 'sycm_market_item_rank',
        'promotion_daily_facts',
    }
    if table not in allowed_tables or date_col not in {'date', 'month', 'stat_date'}:
        raise ValueError('不允许对该采集表建立 staging 快照')
    with get_db(db_path) as conn:
        existing_row = conn.execute(
            "SELECT COUNT(*) AS count, SUM(status = 'published') AS published "
            "FROM collector_data_staging WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if existing_row['count'] and existing_row['count'] == existing_row['published']:
            return {'row_count': existing_row['count'], 'status': 'published', 'source': 'collector-native-staging'}
        latest = conn.execute(
            f'SELECT MAX({date_col}) AS latest FROM {table}'
        ).fetchone()['latest']
        if latest is None:
            return {'row_count': 0, 'status': 'rejected', 'reason': 'empty_source'}
        rows = conn.execute(
            f'SELECT * FROM {table} WHERE {date_col} = ?', (latest,)
        ).fetchall()
        conn.execute('DELETE FROM collector_data_staging WHERE batch_id = ?', (batch_id,))
        for index, row in enumerate(rows, start=1):
            payload = dict(row)
            unit_key = str(payload.get('id') or payload.get('item_id')
                           or payload.get('product_id') or index)
            conn.execute(
                '''INSERT INTO collector_data_staging
                   (source_key, batch_id, unit_type, unit_key, payload_json, status,
                    quality_message, published_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                (source_key, batch_id, 'row', unit_key,
                 _json.dumps(payload, ensure_ascii=False, default=str), 'published',
                 f'legacy snapshot date={latest}'),
            )
        conn.commit()
    return {'row_count': len(rows), 'status': 'published', 'latest': latest}


def _stage_dts_market_snapshot(batch_id, *, db_path=None):
    """dts_market 快照分支：按最新市场分析批次快照 market_products 行。

    该源按 4 周窗口成批导入（无单一日期事实表），采集器自身已写
    collector-native staging 摘要行；这里校验最新批次并发布快照摘要。
    """
    import json as _json
    with get_db(db_path) as conn:
        existing_row = conn.execute(
            "SELECT COUNT(*) AS count, SUM(status = 'published') AS published "
            "FROM collector_data_staging WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if existing_row['count'] and existing_row['count'] == existing_row['published']:
            return {'row_count': existing_row['count'], 'status': 'published',
                    'source': 'collector-native-staging'}
        latest = conn.execute(
            "SELECT id, analysis_date FROM market_analysis_runs "
            "WHERE source='店透视市场排行' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            return {'row_count': 0, 'status': 'rejected', 'reason': 'empty_source'}
        row_count = conn.execute(
            'SELECT COUNT(*) FROM market_products WHERE run_id = ?', (latest['id'],)
        ).fetchone()[0]
        conn.execute('DELETE FROM collector_data_staging WHERE batch_id = ?', (batch_id,))
        payload = {
            'market_run_id': latest['id'],
            'analysis_date': latest['analysis_date'],
            'row_count': row_count,
        }
        conn.execute(
            '''INSERT INTO collector_data_staging
               (source_key, batch_id, unit_type, unit_key, payload_json, status,
                quality_message, published_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            ('dts_market', batch_id, 'market_batch', f"run:{latest['id']}",
             _json.dumps(payload, ensure_ascii=False), 'published',
             f"market batch snapshot date={latest['analysis_date']}"),
        )
        conn.commit()
    return {'row_count': row_count, 'status': 'published',
            'latest': latest['analysis_date']}


def read_artifact(artifact_id, run_id, *, db_path=None):
    """Read one compressed artifact after enforcing its run and path scope."""
    import gzip
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT * FROM collector_artifacts WHERE id = ? AND run_id = ?',
            (artifact_id, run_id),
        ).fetchone()
    if not row:
        return None
    record = dict(row)
    base_dir = (Path(db_path).resolve().parent if db_path else Path.cwd() / 'data') / 'collector_artifacts'
    artifact_path = Path(record['path']).resolve()
    if base_dir.resolve() not in artifact_path.parents:
        raise ValueError('artifact 路径不在允许目录内')
    with gzip.open(artifact_path, 'rb') as handle:
        content = handle.read()
    if hashlib.sha256(content).hexdigest() != record['sha256']:
        raise ValueError('artifact hash 校验失败')
    record['content'] = content.decode('utf-8', errors='replace')
    return record


def acquire_lease(source_key, shop_id, run_id, *, db_path=None, ttl_seconds=900):
    """Acquire a cross-process lease for one source/shop pair."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    lease_until = (now + timedelta(seconds=max(1, int(ttl_seconds)))).isoformat()
    with get_db(db_path) as conn:
        # A process crash can leave a lease whose TTL has not elapsed yet. If
        # its durable run is already terminal, reclaim it immediately while
        # preserving leases for queued/running work.
        conn.execute(
            '''DELETE FROM collector_leases
               WHERE lease_until <= ?
                  OR run_id IN (
                       SELECT id FROM collector_runs
                       WHERE status IN ('succeeded', 'succeeded_with_warnings',
                                        'partial', 'blocked', 'auth_required',
                                        'failed', 'cancelled')
                   )''',
            (now.isoformat(),),
        )
        try:
            conn.execute(
                '''INSERT INTO collector_leases (source_key, shop_id, run_id, lease_until)
                   VALUES (?, ?, ?, ?)''',
                (source_key, shop_id, run_id, lease_until),
            )
        except Exception:
            conn.rollback()
            return False
        conn.commit()
    return True


def release_lease(source_key, shop_id, run_id, *, db_path=None):
    with get_db(db_path) as conn:
        conn.execute(
            'DELETE FROM collector_leases WHERE source_key = ? AND shop_id = ? AND run_id = ?',
            (source_key, shop_id, run_id),
        )
        conn.commit()
