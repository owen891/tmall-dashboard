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
import re
import sqlite3
from email.utils import parsedate_to_datetime

from db import get_db


def _now():
    return datetime.now(timezone.utc).isoformat()


def classify_collection_failure(lines, return_code=None, *, now=None):
    """Conservative retry policy: only positively identified transient failures retry."""
    tail = '\n'.join(str(line).strip() for line in (lines or []) if str(line).strip())[-4000:]
    text = tail.lower()
    category, code, status = 'unknown', 'PROCESS_FAILED', 'failed'
    groups = (
        ('cancelled', 'CANCELLED', 'cancelled', ('cancelled', 'canceled', 'keyboardinterrupt')),
        ('auth', 'AUTH_REQUIRED', 'auth_required', ('manual_login_required', 'login_required', 'login_unknown', 'auth_required', 'session expired', '登录失效', '验证码', 'http 401')),
        ('permission', 'PERMISSION_DENIED', 'blocked', ('permissionerror', 'permission denied', 'access is denied', 'winerror 5', '只读文件', '不可写')),
        ('rate_limit', 'RATE_LIMITED', 'blocked', ('rate_limit', 'too many requests', 'http 429', 'quota exceeded', '配额耗尽', '限流')),
        ('quality', 'QUALITY_GATE_FAILED', 'failed', ('quality_gate_failed',)),
        ('schema', 'SCHEMA_ERROR', 'blocked', ('schema_changed', 'schema mismatch', 'no such column', 'keyerror:', '字段缺失')),
        ('transport', 'CDP_UNAVAILABLE', 'failed', ('get_cookies_from_cdp', 'cdp_unavailable')),
        ('transport', 'TIMEOUT', 'failed', ('timeoutexpired', 'timed out', 'timeout')),
        ('transport', 'NETWORK_ERROR', 'failed', ('connectionrefusederror', 'winerror 10061', 'connection reset', 'temporary failure', 'http 502', 'http 503', 'http 504')),
    )
    for candidate, candidate_code, candidate_status, markers in groups:
        if any(marker in text for marker in markers):
            category, code, status = candidate, candidate_code, candidate_status
            break
    if category == 'transport' and ('127.0.0.1:' in text or '/json' in text):
        code = 'CDP_UNAVAILABLE'
    retry_after = None
    match = re.search(r'retry-after\s*[:=]\s*([^\r\n]+)', tail, re.I)
    if match:
        value = match.group(1).strip()
        try:
            retry_after = max(0, int(value))
        except ValueError:
            try:
                until = parsedate_to_datetime(value)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                retry_after = max(0, (until - (now or datetime.now(timezone.utc))).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return {'code': code, 'category': category, 'status': status,
            'retryable': category == 'transport' or (category == 'rate_limit' and retry_after is not None),
            'retry_after_seconds': retry_after,
            'message': (f'采集失败，返回码 {return_code}\n{tail}')[:2000]}


def retry_decision(failure, *, attempt, elapsed_seconds, max_attempts=3,
                   budget_seconds=900, default_delay=30):
    delay = failure.get('retry_after_seconds')
    delay = default_delay if delay is None else max(default_delay, delay)
    remaining = max(0, budget_seconds - max(0, elapsed_seconds))
    reason = ('non_retryable' if not failure.get('retryable') else
              'attempt_budget_exhausted' if attempt >= max_attempts else
              'time_budget_exhausted' if delay >= remaining else 'transient_retry')
    return {'retry': reason == 'transient_retry', 'reason': reason,
            'delay_seconds': delay, 'remaining_seconds': remaining}


def collection_completion_evidence(lines, *, run_id, source_key, window_start, window_end,
                                   db_path=None):
    """A zero exit and nonempty historical table are not a collection receipt."""
    failure = classify_collection_failure(lines, 0)
    if failure['category'] != 'unknown':
        return {'ok': False, 'code': failure['code'], 'status': failure['status']}
    checkpoints = list_checkpoints(run_id, db_path=db_path)
    if any(row['status'] in {'failed', 'blocked', 'auth_required', 'cancelled', 'partial'} for row in checkpoints):
        return {'ok': False, 'code': 'CHECKPOINT_FAILED', 'status': 'failed'}
    if any(row['unit_type'] != 'process' and row['status'] != 'succeeded' for row in checkpoints):
        return {'ok': False, 'code': 'CHECKPOINT_INCOMPLETE', 'status': 'blocked'}
    receipt = None
    for line in lines:
        if str(line).startswith('RESULT_JSON '):
            try:
                value = json.loads(str(line)[len('RESULT_JSON '):])
                if isinstance(value, dict):
                    # A later success must not erase an earlier explicit quality failure.
                    if (value.get('status') in {'failed', 'blocked', 'partial', 'cancelled', 'auth_required'}
                            or value.get('quality_gate') == 'failed' or value.get('error_code')):
                        return {'ok': False, 'code': 'QUALITY_GATE_FAILED', 'status': 'failed'}
                    receipt = value
            except ValueError:
                pass
    if receipt is None:
        return {'ok': False, 'code': 'COMPLETION_UNVERIFIED', 'status': 'blocked'}
    coverage = receipt.get('coverage') or {}
    if not isinstance(coverage, dict):
        return {'ok': False, 'code': 'INCOMPLETE_COLLECTION', 'status': 'blocked'}
    counts = [coverage.get(key) for key in ('expected_units', 'succeeded_units', 'failed_units')]
    valid = (type(receipt.get('schema_version')) is int and receipt['schema_version'] == 1
             and receipt.get('event') == 'result'
             and type(receipt.get('return_code')) is int and receipt['return_code'] == 0
             and receipt.get('run_id') == run_id and receipt.get('source_key') == source_key
             and receipt.get('window_start') == window_start and receipt.get('window_end') == window_end
             and receipt.get('status') == 'succeeded' and receipt.get('quality_gate') == 'passed'
             and not receipt.get('error_code') and all(type(x) is int for x in counts)
             and counts[0] > 0 and counts[0] == counts[1] and counts[2] == 0
             and coverage.get('complete') is True and type(receipt.get('row_count')) is int
             and receipt['row_count'] >= counts[1])
    return {'ok': valid, 'code': None if valid else 'INCOMPLETE_COLLECTION',
            'status': 'succeeded' if valid else 'blocked', 'receipt': receipt}


def healthcheck_coverage(path, *, now=None, stale_after_seconds=93600):
    """Independent request-time observation, NOT an external uptime monitor."""
    result = {'observer': 'health_api_on_request', 'autonomous_detection': False,
              'host_or_api_down': 'uncovered', 'status': 'missing'}
    try:
        record = json.loads(Path(path).read_text(encoding='utf-8'))
        last = _parse_timestamp(record.get('checked_at'))
        if not last:
            raise ValueError('invalid heartbeat timestamp')
        age = ((now or datetime.now(timezone.utc)) - last).total_seconds()
        result.update(checked_at=last.isoformat(), age_seconds=max(0, age),
                      status='invalid' if age < -60 else 'stale' if age > stale_after_seconds else 'active',
                      last_result=record.get('status', 'unknown'))
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, AttributeError):
        result['status'] = 'unknown'
    return result


def _run_owner_clause(table, shop_id, params):
    """Scope a child table to rows whose owning run belongs to shop_id."""
    if shop_id is None:
        return ''
    params.append(shop_id)
    return (f' AND EXISTS (SELECT 1 FROM collector_runs scope_owner'
            f' WHERE scope_owner.shop_id = ?'
            f' AND scope_owner.id = {table}.run_id)')


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


def get_run(run_id, *, db_path=None, shop_id=None):
    params = [run_id]
    sql = 'SELECT * FROM collector_runs WHERE id = ?'
    if shop_id is not None:
        sql += ' AND shop_id = ?'
        params.append(shop_id)
    with get_db(db_path) as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
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
        # SQLite UNIQUE permits multiple NULL values: a queued unpaged unit must
        # be updated, not duplicated when its successful event arrives.
        if page_no is None:
            updated = conn.execute(
                '''UPDATE collector_checkpoints SET cursor=?, status=?, row_count=?, source_hash=?,
                   last_error_code=?, last_error_message=?, updated_at=?
                   WHERE run_id=? AND unit_type=? AND unit_key=? AND page_no IS NULL''',
                (cursor, status, row_count, source_hash, error_code,
                 str(error_message)[:2000] if error_message else None, now, run_id, unit_type, unit_key),
            )
            if updated.rowcount:
                conn.commit()
                return
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


def list_checkpoints(run_id, *, db_path=None, shop_id=None):
    params = [run_id]
    sql = ('SELECT * FROM collector_checkpoints WHERE run_id = ?'
           + _run_owner_clause('collector_checkpoints', shop_id, params)
           + ' ORDER BY unit_type, unit_key, page_no')
    with get_db(db_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def list_quality_results(run_id, *, db_path=None, shop_id=None):
    params = [run_id]
    sql = ('SELECT * FROM collector_quality_results WHERE run_id = ?'
           + _run_owner_clause('collector_quality_results', shop_id, params)
           + ' ORDER BY id')
    with get_db(db_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
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


def quality_gate(run_id, *, db_path=None, shop_id=None):
    """Summarize persisted quality observations into a publish decision."""
    results = list_quality_results(run_id, db_path=db_path, shop_id=shop_id)
    failed = [row for row in results if row.get('status') in {'failed', 'blocked'}
              and row.get('severity') in {'error', 'critical'}]
    return {
        'status': 'failed' if failed else ('passed' if results else 'not-evaluated'),
        'rules': len(results),
        'failed_rules': len(failed),
    }


def record_health_alert(source_key, alert_type, message, *, severity='warning',
                        fingerprint=None, details=None, db_path=None):
    """Upsert an open operational alert without creating notification spam.

    The conflict target is the identity of the alert (source/type/fingerprint),
    not including ``status``: re-triggering a resolved alert reopens the same
    row, which is what keeps ``resolve_health_alert`` from ever colliding with
    a historical resolved row.
    """
    fingerprint = fingerprint or hashlib.sha256(
        f'{source_key}:{alert_type}'.encode('utf-8')).hexdigest()[:32]
    with get_db(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        previous = conn.execute(
            'SELECT status, details_json FROM collector_health_alerts WHERE source_key=? AND alert_type=? AND fingerprint=?',
            (source_key, alert_type, fingerprint),
        ).fetchone()
        old = json.loads(previous['details_json'] or '{}') if previous else {}
        events = old.get('events', [])
        if not previous or previous['status'] != 'open':
            events.append({'id': uuid4().hex, 'kind': 'fault', 'detected_at': _now(),
                           'local_delivery': 'persisted', 'external_delivery': 'unconfigured'})
        payload = json.dumps({**(details or {}), 'events': events}, ensure_ascii=False, sort_keys=True)
        conn.execute(
            '''INSERT INTO collector_health_alerts
               (source_key, alert_type, severity, fingerprint, message, details_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_key, alert_type, fingerprint) DO UPDATE SET
                 severity=excluded.severity, message=excluded.message,
                 details_json=excluded.details_json, last_seen_at=CURRENT_TIMESTAMP,
                 resolved_at=NULL, status='open' ''',
            (source_key, alert_type, severity, fingerprint, message, payload),
        )
        conn.commit()
    return fingerprint


def resolve_health_alert(source_key, alert_type, fingerprint, *, db_path=None):
    with get_db(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            '''SELECT details_json FROM collector_health_alerts WHERE source_key=? AND alert_type=?
               AND fingerprint=? AND status='open' ''', (source_key, alert_type, fingerprint),
        ).fetchone()
        if not row:
            return False
        details = json.loads(row['details_json'] or '{}')
        details.setdefault('events', []).append(
            {'id': uuid4().hex, 'kind': 'recovery', 'detected_at': _now(),
             'local_delivery': 'persisted', 'external_delivery': 'unconfigured'})
        conn.execute(
            '''UPDATE collector_health_alerts
               SET status='resolved', resolved_at=CURRENT_TIMESTAMP,
                   last_seen_at=CURRENT_TIMESTAMP, details_json=?
               WHERE source_key=? AND alert_type=? AND fingerprint=? AND status='open' ''',
            (json.dumps(details, ensure_ascii=False), source_key, alert_type, fingerprint),
        )
        conn.commit()
    return True


def pending_health_events(*, db_path=None):
    events = []
    for status in ('open', 'resolved'):
        for alert in list_health_alerts(status=status, db_path=db_path):
            details = json.loads(alert.get('details_json') or '{}')
            for event in details.get('events', []):
                if event.get('external_delivery') != 'delivered':
                    events.append({**event, 'source_key': alert['source_key'],
                                   'alert_type': alert['alert_type'], 'fingerprint': alert['fingerprint']})
    return events


def record_event_delivery(event_id, status, *, db_path=None):
    if status not in {'unconfigured', 'delivered', 'failed', 'dry_run'}:
        raise ValueError('invalid delivery status')
    with get_db(db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        for row in conn.execute('SELECT id, details_json FROM collector_health_alerts').fetchall():
            details = json.loads(row['details_json'] or '{}')
            for event in details.get('events', []):
                if event['id'] == event_id:
                    event['external_delivery'] = status
                    event['delivery_checked_at'] = _now()
                    if status == 'delivered':
                        event['delivered_at'] = event['delivery_checked_at']
                    conn.execute('UPDATE collector_health_alerts SET details_json=? WHERE id=?',
                                 (json.dumps(details, ensure_ascii=False), row['id']))
                    conn.commit()
                    return True
    return False


def reconcile_date_gaps(source_key, missing_dates, *, verified_dates=(), db_path=None):
    """Keep a durable queue; disappearance from a report or run success is not acceptance."""
    missing, verified = set(missing_dates), set(verified_dates)
    for day in sorted(missing):
        datetime.strptime(day, '%Y-%m-%d')  # reject malformed keys
        record_health_alert(source_key, 'date_gap', f'日期 {day} 尚未覆盖验收',
                            fingerprint=day, details={'date': day, 'coverage': 'missing'}, db_path=db_path)
    closed = []
    for row in list_health_alerts(source_key=source_key, db_path=db_path):
        if row['alert_type'] == 'date_gap' and row['fingerprint'] in verified - missing:
            resolve_health_alert(source_key, 'date_gap', row['fingerprint'], db_path=db_path)
            closed.append(row['fingerprint'])
    return {'closed': closed, 'open_dates': sorted(row['fingerprint'] for row in
            list_health_alerts(source_key=source_key, db_path=db_path) if row['alert_type'] == 'date_gap')}


def verify_fact_dates(conn, table, date_col, required_fields, dates, *, shop_id=None):
    """Date presence + non-null critical-field acceptance; zero metrics are valid.

    This does not claim full source-population coverage. Unknown schemas never pass.
    Identifiers must originate from the server's source catalog, not request data.
    """
    identifiers = [table, date_col, *(required_fields or [])]
    if not required_fields or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', x) for x in identifiers):
        return {'status': 'unknown', 'verified_dates': [], 'reason': 'unsupported_catalog'}
    try:
        columns = {row['name'] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if not set(identifiers[1:]) <= columns:
            return {'status': 'unknown', 'verified_dates': [], 'reason': 'missing_required_columns'}
        if shop_id is not None and 'shop_id' not in columns:
            return {'status': 'unknown', 'verified_dates': [], 'reason': 'unverifiable_shop_scope'}
        invalid = ' OR '.join(f'"{field}" IS NULL OR CAST("{field}" AS TEXT)=\'\'' for field in required_fields)
        verified = []
        rejected = []
        for day in sorted(set(dates)):
            datetime.strptime(day, '%Y-%m-%d')
            row = conn.execute(
                f'''SELECT COUNT(*) AS total, SUM(CASE WHEN {invalid} THEN 1 ELSE 0 END) AS invalid
                    FROM "{table}" WHERE substr("{date_col}",1,10)=?'''
                + (' AND shop_id=?' if shop_id is not None else ''),
                (day, shop_id) if shop_id is not None else (day,),
            ).fetchone()
            (verified if row['total'] > 0 and not row['invalid'] else rejected).append(day)
        return {'status': 'verified' if not rejected else 'partial', 'verified_dates': verified,
                'rejected_dates': rejected, 'scope': 'date_presence_and_required_fields',
                'population_completeness': 'not_evaluated'}
    except (ValueError, TypeError, sqlite3.Error):
        return {'status': 'unknown', 'verified_dates': [], 'reason': 'unverifiable_facts'}


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


def list_artifacts(run_id, *, db_path=None, shop_id=None):
    params = [run_id]
    sql = ('SELECT * FROM collector_artifacts WHERE run_id = ?'
           + _run_owner_clause('collector_artifacts', shop_id, params)
           + ' ORDER BY id')
    with get_db(db_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def list_data_staging(batch_id, *, db_path=None, shop_id=None):
    params = [batch_id, f'{batch_id}:%']
    sql = ('''SELECT id, source_key, batch_id, unit_type, unit_key,
                     payload_json, status, quality_message, created_at, published_at
              FROM collector_data_staging
              WHERE (batch_id = ? OR batch_id LIKE ?)''')
    if shop_id is not None:
        # ``batch_id`` is the owning run id, optionally with a ``:<suffix>`` tail
        # (see api/wanxiangtai_api.py), so the ownership join is a prefix match.
        sql += (' AND EXISTS (SELECT 1 FROM collector_runs scope_owner'
                ' WHERE scope_owner.shop_id = ?'
                " AND (collector_data_staging.batch_id = scope_owner.id"
                " OR collector_data_staging.batch_id LIKE scope_owner.id || ':%'))")
        params.append(shop_id)
    sql += ' ORDER BY id'
    with get_db(db_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
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


def stage_source_snapshot(batch_id, source_key, table, date_col, *, db_path=None,
                          window_start=None, window_end=None, expected_rows=None, required_fields=None):
    """Snapshot the latest successful collector partition into audit staging.

    Legacy collectors still write their own fact tables. This adapter gives
    those collectors the same auditable staging and quality contract while
    they are migrated to native two-phase publishing.
    """
    import json as _json
    if source_key == 'dts_market':
        if window_start:
            return {'row_count': 0, 'status': 'rejected', 'reason': 'window_adapter_not_configured'}
        return _stage_dts_market_snapshot(batch_id, db_path=db_path)
    allowed_tables = {
        'daily_data', 'monthly_data', 'sycm_flow_source_daily',
        'sycm_item_flow_source_daily', 'sycm_market_item_rank',
        'promotion_daily_facts',
    }
    if table not in allowed_tables or date_col not in {'date', 'month', 'stat_date'}:
        raise ValueError('不允许对该采集表建立 staging 快照')
    with get_db(db_path) as conn:
        # Keep the source read and its published audit snapshot on one locked view.
        conn.execute('BEGIN IMMEDIATE')
        owner = conn.execute('SELECT shop_id,source_key FROM collector_runs WHERE id=?', (batch_id,)).fetchone()
        if not owner or owner['source_key'] != source_key:
            return {'row_count': 0, 'status': 'rejected', 'reason': 'snapshot_owner_mismatch'}
        columns = {row['name'] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if 'shop_id' not in columns:
            return {'row_count': 0, 'status': 'rejected', 'reason': 'unverifiable_shop_scope'}
        shop_id = owner['shop_id']
        existing_row = conn.execute(
            "SELECT COUNT(*) AS count, SUM(status = 'published') AS published "
            "FROM collector_data_staging WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if (source_key != 'wanxiangtai' and not window_start and existing_row['count']
                and existing_row['count'] == existing_row['published']):
            return {'row_count': existing_row['count'], 'status': 'published', 'source': 'collector-native-staging'}
        latest = conn.execute(
            f'SELECT MAX({date_col}) AS latest FROM {table} WHERE shop_id=?', (shop_id,)
        ).fetchone()['latest']
        if latest is None:
            return {'row_count': 0, 'status': 'rejected', 'reason': 'empty_source'}
        if window_start:
            start, end = (window_start[:7], window_end[:7]) if date_col == 'month' else (window_start, window_end)
            rows = conn.execute(f'SELECT * FROM {table} WHERE shop_id=? AND {date_col} BETWEEN ? AND ?', (shop_id, start, end)).fetchall()
            if not rows:
                return {'row_count': 0, 'status': 'rejected', 'reason': 'requested_window_empty'}
        else:
            rows = conn.execute(f'SELECT * FROM {table} WHERE shop_id=? AND {date_col} = ?', (shop_id, latest)).fetchall()
        if expected_rows is not None and len(rows) != expected_rows:
            return {'row_count': len(rows), 'status': 'rejected', 'reason': 'receipt_row_count_mismatch'}
        if window_start:
            first, last = datetime.fromisoformat(window_start).date(), datetime.fromisoformat(window_end).date()
            expected_dates = {(first + timedelta(days=offset)).isoformat()[:7 if date_col == 'month' else 10]
                              for offset in range((last - first).days + 1)}
            present_dates = {str(row[date_col])[:7 if date_col == 'month' else 10] for row in rows}
            if not expected_dates <= present_dates:
                return {'row_count': len(rows), 'status': 'rejected', 'reason': 'requested_window_gap'}
        if required_fields is not None and (not required_fields or any(
                field not in row.keys() or row[field] is None or str(row[field]).strip() == ''
                for row in rows for field in required_fields)):
            return {'row_count': len(rows), 'status': 'rejected', 'reason': 'required_fields_incomplete'}
        identity_columns = [column[1] for column in sorted(
            conn.execute(f'PRAGMA table_info({table})').fetchall(),
            key=lambda column: column[5]) if column[5]]
        if not identity_columns:
            return {'row_count': len(rows), 'status': 'rejected',
                    'reason': 'source_primary_identity_unavailable'}
        if source_key == 'wanxiangtai':
            # Import replay confirms a historical operation, not current facts.
            # Before replacing this run's audit snapshot, verify both targets
            # against its native published inputs on the same locked DB view.
            prefix = batch_id + ':'
            owned_batches = conn.execute(
                "SELECT b.id,b.status,b.total_rows,b.valid_rows,b.invalid_rows,"
                "COUNT(s.id) AS staged_count,"
                "SUM(CASE WHEN s.source_key='wanxiangtai' AND s.status='published' "
                "THEN 1 ELSE 0 END) AS published_count "
                "FROM import_batches b LEFT JOIN collector_data_staging s ON s.batch_id=b.id "
                "WHERE b.shop_id=? AND b.source_type='wanxiangtai_api' "
                "AND substr(b.id,1,?)=? AND length(b.id)=? "
                "AND substr(b.id,?) NOT GLOB '*[^0-9a-f]*' GROUP BY b.id",
                (shop_id, len(prefix), prefix, len(prefix) + 32, len(prefix) + 1),
            ).fetchall()
            if not owned_batches or any(
                    batch['status'] != 'completed' or not isinstance(batch['total_rows'], int)
                    or batch['total_rows'] <= 0 or batch['invalid_rows'] != 0
                    or not (batch['total_rows'] == batch['valid_rows']
                            == batch['staged_count'] == batch['published_count'])
                    for batch in owned_batches):
                return {'row_count': len(rows), 'status': 'rejected',
                        'reason': 'snapshot_native_batch_incomplete'}
            evidence = conn.execute(
                "SELECT s.payload_json,b.source_hash FROM collector_data_staging s "
                "JOIN import_batches b ON b.id=s.batch_id "
                "WHERE s.source_key='wanxiangtai' AND s.status='published' "
                "AND b.shop_id=? AND b.source_type='wanxiangtai_api' "
                "AND b.status='completed' AND substr(b.id,1,?)=? "
                "AND length(b.id)=? AND substr(b.id,?) NOT GLOB '*[^0-9a-f]*'",
                (shop_id, len(prefix), prefix, len(prefix) + 32, len(prefix) + 1),
            ).fetchall()
            expected = {'promotion_daily_facts': {}, 'promotion_creative_daily': {}}
            key_columns = {table: identity_columns}
            key_columns['promotion_creative_daily'] = [column[1] for column in sorted(
                conn.execute('PRAGMA table_info(promotion_creative_daily)').fetchall(),
                key=lambda column: column[5]) if column[5]]
            reason = None
            native_counts, cohort_hashes = {}, {}
            for entry in evidence:
                try:
                    payload = _json.loads(entry['payload_json'])
                except (ValueError, TypeError):
                    reason = 'snapshot_native_evidence_invalid'
                    break
                if not isinstance(payload, dict) or not payload.get('date'):
                    reason = 'snapshot_native_evidence_invalid'
                    break
                if not ((start <= payload['date'] <= end) if window_start
                        else payload['date'] == latest):
                    continue
                target = ('promotion_creative_daily' if 'creative_id' in payload
                          else 'promotion_daily_facts')
                payload = dict(payload, shop_id=shop_id)
                source_hash = entry['source_hash']
                if (not isinstance(source_hash, str) or len(source_hash) != 64
                        or any(char not in '0123456789abcdef' for char in source_hash)
                        or not key_columns[target]
                        or any(column not in payload for column in key_columns[target])):
                    reason = 'snapshot_native_evidence_invalid'
                    break
                report = ('creative' if target == 'promotion_creative_daily' else
                          'campaign' if payload.get('grain') == 'campaign' else
                          'item_promotion' if payload.get('grain') == 'product' else None)
                if report is None:
                    reason = 'snapshot_native_report_invalid'
                    break
                unit = (report, payload['date'])
                native_counts[unit] = native_counts.get(unit, 0) + 1
                cohort_hashes.setdefault(unit, set()).add(source_hash)
                if len(cohort_hashes[unit]) != 1:
                    reason = 'snapshot_native_evidence_ambiguous'
                    break
                key = tuple(payload[column] for column in key_columns[target])
                value = (payload, source_hash)
                if key in expected[target]:
                    reason = 'snapshot_native_evidence_ambiguous'
                    break
                expected[target][key] = value
            if not reason:
                wanted_dates = expected_dates if window_start else {latest}
                wanted_units = {(report, day) for day in wanted_dates
                                for report in ('campaign', 'item_promotion', 'creative')}
                checkpoint_counts = {}
                for checkpoint in conn.execute(
                        "SELECT unit_key,status,row_count FROM collector_checkpoints "
                        "WHERE run_id=? AND unit_type='report' AND page_no IS NULL", (batch_id,)):
                    parts = checkpoint['unit_key'].rsplit(':', 1)
                    if len(parts) != 2 or parts[1] not in wanted_dates:
                        continue
                    unit = tuple(parts)
                    if (unit in checkpoint_counts or checkpoint['status'] != 'succeeded'
                            or not isinstance(checkpoint['row_count'], int)
                            or checkpoint['row_count'] <= 0):
                        reason = 'snapshot_native_checkpoint_invalid'
                        break
                    checkpoint_counts[unit] = checkpoint['row_count']
                if (not reason and (set(native_counts) != wanted_units
                                    or native_counts != checkpoint_counts)):
                    reason = 'snapshot_native_checkpoint_mismatch'
            if not reason:
                creative_rows = conn.execute(
                    'SELECT * FROM promotion_creative_daily WHERE shop_id=? '
                    + ('AND date BETWEEN ? AND ?' if window_start else 'AND date=?'),
                    (shop_id, start, end) if window_start else (shop_id, latest),
                ).fetchall()
                source_hashes = {}
                for target, actual in ((table, rows), ('promotion_creative_daily', creative_rows)):
                    actual_by_key = {tuple(row[column] for column in key_columns[target]): row
                                     for row in actual}
                    if (not expected[target] or len(actual_by_key) != len(actual)
                            or actual_by_key.keys() != expected[target].keys()):
                        reason = 'snapshot_native_coverage_mismatch'
                        break
                    for key, row in actual_by_key.items():
                        payload, wanted_hash = expected[target][key]
                        source_batch = row['source_batch_id']
                        if source_batch not in source_hashes:
                            source = conn.execute(
                                "SELECT source_hash FROM import_batches WHERE id=? AND shop_id=? "
                                "AND source_type='wanxiangtai_api' AND status='completed'",
                                (source_batch, shop_id),
                            ).fetchone()
                            source_hashes[source_batch] = source['source_hash'] if source else None
                        # Daily UPSERT intentionally preserves unknown (None)
                        # measures and empty display names; creative UPSERT does not.
                        mismatched = any(
                            column in row.keys() and row[column] != value
                            for column, value in payload.items()
                            if target == 'promotion_creative_daily' or (
                                value is not None and not (
                                    column == 'campaign_name' and not value)))
                        if source_hashes[source_batch] != wanted_hash or mismatched:
                            reason = 'snapshot_native_facts_mismatch'
                            break
                    if reason:
                        break
            if reason:
                return {'row_count': len(rows), 'status': 'rejected', 'reason': reason}
        conn.execute('DELETE FROM collector_data_staging WHERE batch_id = ?', (batch_id,))
        for index, row in enumerate(rows, start=1):
            payload = dict(row)
            unit_key = _json.dumps(
                [table, [payload[column] for column in identity_columns]],
                ensure_ascii=False, separators=(',', ':'), default=str)
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


def read_artifact(artifact_id, run_id, *, db_path=None, shop_id=None):
    """Read one compressed artifact after enforcing its run and path scope."""
    import gzip
    params = [artifact_id, run_id]
    sql = 'SELECT * FROM collector_artifacts WHERE id = ? AND run_id = ?'
    sql += _run_owner_clause('collector_artifacts', shop_id, params)
    with get_db(db_path) as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
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
