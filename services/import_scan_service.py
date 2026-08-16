"""Local, lease-protected folder scanning for canonical imports.

The scanner owns discovery and scheduling only. Parsing, validation and writes
remain in ImportService so manual uploads and automatic imports share behavior.
"""

import fnmatch
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from flask import current_app, has_app_context

from db import get_db
from services.import_service import ImportValidationError, import_service


SUPPORTED_SUFFIXES = {'.xlsx', '.xls', '.csv', '.zip'}
LEASE_SECONDS = 120


class ImportScanValidationError(ValueError):
    pass


class ImportScanConflictError(RuntimeError):
    pass


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return str(value)


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def _row(row):
    if row is None:
        return None
    item = dict(row)
    if 'mapping_template_json' in item:
        try:
            item['mapping_template'] = json.loads(item.pop('mapping_template_json') or '{}')
        except json.JSONDecodeError:
            item['mapping_template'] = {}
    for key in ('enabled',):
        if key in item:
            item[key] = bool(item[key])
    return item


def _allowed_roots():
    configured = current_app.config.get('IMPORT_SCAN_ALLOWED_ROOTS') if has_app_context() else None
    if not configured:
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'import-inbox')
        configured = [root]
    if isinstance(configured, str):
        configured = [configured]
    return [os.path.realpath(os.path.abspath(str(item))) for item in configured if str(item).strip()]


def _is_within_root(candidate, root):
    try:
        return os.path.commonpath([candidate, root]) == root
    except ValueError:
        # Windows drives (or other incompatible path roots) cannot overlap.
        return False


def _validate_folder(value):
    raw = str(value or '').strip()
    if not raw or raw.startswith('\\\\') or raw.startswith('//'):
        raise ImportScanValidationError('folder_path must be a local path')
    normalized = raw.replace('\\', '/')
    if any(part == '..' for part in normalized.split('/')):
        raise ImportScanValidationError('folder_path cannot contain ..')
    candidate = os.path.realpath(os.path.abspath(raw))
    if not os.path.isdir(candidate):
        raise ImportScanValidationError('folder_path must be an existing directory')
    if os.path.islink(raw):
        raise ImportScanValidationError('symlink folders are not supported')
    if not any(_is_within_root(candidate, root) for root in _allowed_roots()):
        raise ImportScanValidationError('folder_path is outside IMPORT_SCAN_ALLOWED_ROOTS')
    return candidate


def _validate_pattern(value):
    pattern = str(value or '*').strip()
    if not pattern or pattern in {'.', '..'} or '/' in pattern or '\\' in pattern:
        raise ImportScanValidationError('file_pattern must match direct children only')
    if '..' in pattern:
        raise ImportScanValidationError('file_pattern cannot contain ..')
    return pattern


def _validate_cron(value):
    cron = str(value or '').strip()
    if len(cron.split()) != 5 or not re.fullmatch(r'[0-9*/?,\-]+(?:\s+[0-9*/?,\-]+){4}', cron):
        raise ImportScanValidationError('cron_expr must contain five cron fields')
    return cron


def _validate_source(source_type):
    value = str(source_type or 'auto').strip()
    from services.import_service import SOURCE_REQUIREMENTS
    if value != 'auto' and value not in SOURCE_REQUIREMENTS:
        raise ImportScanValidationError(f'unsupported source_type: {value}')
    return value


def _validate_mapping(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ImportScanValidationError('mapping_template must be an object')
    return value


class ImportScanService:
    @classmethod
    def create_job(cls, payload):
        payload = payload or {}
        task_name = str(payload.get('task_name') or '').strip()
        if not task_name:
            raise ImportScanValidationError('task_name is required')
        folder = _validate_folder(payload.get('folder_path'))
        pattern = _validate_pattern(payload.get('file_pattern', '*'))
        source_type = _validate_source(payload.get('source_type', 'auto'))
        mapping = _validate_mapping(payload.get('mapping_template'))
        cron = _validate_cron(payload.get('cron_expr', '* * * * *'))
        enabled = 1 if payload.get('enabled', True) else 0
        now = _utc_now()
        with get_db() as conn:
            cursor = conn.execute(
                '''INSERT INTO import_scan_jobs
                   (task_name, folder_path, file_pattern, source_type,
                    mapping_template_json, cron_expr, enabled, status, next_run,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (task_name, folder, pattern, source_type, json.dumps(mapping, ensure_ascii=False),
                 cron, enabled, 'active' if enabled else 'disabled', _iso(now), _iso(now), _iso(now)),
            )
            job_id = cursor.lastrowid
            conn.commit()
        return cls.get_job(job_id)

    @classmethod
    def get_job(cls, job_id):
        with get_db() as conn:
            return _row(conn.execute('SELECT * FROM import_scan_jobs WHERE id = ?', (job_id,)).fetchone())

    @classmethod
    def list_jobs(cls):
        with get_db() as conn:
            rows = conn.execute('SELECT * FROM import_scan_jobs ORDER BY id DESC').fetchall()
            jobs = [_row(item) for item in rows]
            for job in jobs:
                job['file_count'] = conn.execute(
                    'SELECT COUNT(*) FROM import_scan_files WHERE job_id = ?', (job['id'],)
                ).fetchone()[0]
            return jobs

    @classmethod
    def update_job(cls, job_id, payload):
        current = cls.get_job(job_id)
        if current is None:
            raise ImportScanValidationError('scan job not found')
        merged = {**current, **(payload or {})}
        folder = _validate_folder(merged.get('folder_path'))
        pattern = _validate_pattern(merged.get('file_pattern'))
        source_type = _validate_source(merged.get('source_type'))
        mapping = _validate_mapping(merged.get('mapping_template'))
        cron = _validate_cron(merged.get('cron_expr'))
        enabled = 1 if merged.get('enabled', True) else 0
        status = 'active' if enabled else 'disabled'
        now = _iso(_utc_now())
        with get_db() as conn:
            conn.execute(
                '''UPDATE import_scan_jobs
                   SET task_name=?, folder_path=?, file_pattern=?, source_type=?,
                       mapping_template_json=?, cron_expr=?, enabled=?, status=?,
                       lease_token=NULL, lease_until=NULL, updated_at=?
                   WHERE id=?''',
                (str(merged.get('task_name') or '').strip(), folder, pattern, source_type,
                 json.dumps(mapping, ensure_ascii=False), cron, enabled, status, now, job_id),
            )
            conn.commit()
        return cls.get_job(job_id)

    @classmethod
    def disable_job(cls, job_id):
        with get_db() as conn:
            result = conn.execute(
                "UPDATE import_scan_jobs SET enabled=0, status='disabled', lease_token=NULL, lease_until=NULL, updated_at=? WHERE id=?",
                (_iso(_utc_now()), job_id),
            )
            conn.commit()
        if not result.rowcount:
            raise ImportScanValidationError('scan job not found')
        return cls.get_job(job_id)

    @classmethod
    def list_runs(cls, job_id):
        with get_db() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM import_scan_runs WHERE job_id=? ORDER BY started_at DESC', (job_id,)
            ).fetchall()]

    @classmethod
    def list_files(cls, job_id, status=None):
        with get_db() as conn:
            query = 'SELECT * FROM import_scan_files WHERE job_id=?'
            params = [job_id]
            if status:
                query += ' AND status=?'
                params.append(status)
            query += ' ORDER BY updated_at DESC, id DESC'
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    @staticmethod
    def _file_hash(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _discover(cls, job):
        folder = _validate_folder(job['folder_path'])
        pattern = _validate_pattern(job['file_pattern'])
        now = _utc_now().timestamp()
        max_size = int(current_app.config.get('MAX_CONTENT_LENGTH', 25 * 1024 * 1024))
        candidates = []
        for entry in os.scandir(folder):
            if not entry.is_file(follow_symlinks=False) or entry.is_symlink():
                continue
            if not fnmatch.fnmatch(entry.name, pattern):
                continue
            suffix = Path(entry.name).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                continue
            stat = entry.stat(follow_symlinks=False)
            canonical = os.path.realpath(entry.path)
            if stat.st_size <= 0 or stat.st_size > max_size or now - stat.st_mtime < 60:
                cls._record_unstable(job['id'], canonical, entry.name, stat.st_size, stat.st_mtime_ns)
                continue
            with get_db() as conn:
                previous = conn.execute(
                    '''SELECT * FROM import_scan_files WHERE job_id=? AND canonical_path=?
                       ORDER BY id DESC LIMIT 1''', (job['id'], canonical)
                ).fetchone()
            stable = previous is not None and previous['size_bytes'] == stat.st_size and previous['mtime_ns'] == stat.st_mtime_ns
            if not stable:
                cls._record_unstable(job['id'], canonical, entry.name, stat.st_size, stat.st_mtime_ns)
                continue
            source_hash = cls._file_hash(canonical)
            candidates.append((canonical, entry.name, stat.st_size, stat.st_mtime_ns, source_hash))
        return candidates

    @staticmethod
    def _record_unstable(job_id, canonical, filename, size, mtime_ns):
        now = _iso(_utc_now())
        with get_db() as conn:
            existing = conn.execute(
                '''SELECT id FROM import_scan_files WHERE job_id=? AND canonical_path=?
                   AND size_bytes=? AND mtime_ns=? ORDER BY id DESC LIMIT 1''',
                (job_id, canonical, size, mtime_ns),
            ).fetchone()
            if existing:
                conn.execute('UPDATE import_scan_files SET updated_at=? WHERE id=?', (now, existing['id']))
            else:
                conn.execute(
                    '''INSERT INTO import_scan_files
                       (job_id, canonical_path, source_filename, size_bytes, mtime_ns,
                        source_hash, status, error_code, error_message, updated_at)
                       VALUES (?, ?, ?, ?, ?, '', 'ignored', 'FILE_UNSTABLE', ?, ?)''',
                    (job_id, canonical, filename, size, mtime_ns,
                     'file must remain unchanged across two scans', now),
                )
            conn.commit()

    @classmethod
    def _upsert_discovered(cls, job_id, item):
        canonical, filename, size, mtime_ns, source_hash = item
        now = _iso(_utc_now())
        with get_db() as conn:
            existing = conn.execute(
                '''SELECT * FROM import_scan_files WHERE job_id=? AND canonical_path=? AND source_hash=?''',
                (job_id, canonical, source_hash),
            ).fetchone()
            if existing is None:
                existing = conn.execute(
                    '''SELECT * FROM import_scan_files WHERE job_id=? AND canonical_path=?
                       AND source_hash='' AND size_bytes=? AND mtime_ns=?
                       ORDER BY id DESC LIMIT 1''',
                    (job_id, canonical, size, mtime_ns),
                ).fetchone()
                if existing is not None:
                    conn.execute(
                        '''UPDATE import_scan_files SET source_hash=?, status='discovered',
                           error_code=NULL, error_message=NULL, updated_at=? WHERE id=?''',
                        (source_hash, now, existing['id']),
                    )
                    conn.commit()
                    return {**dict(existing), 'source_hash': source_hash, 'status': 'discovered'}, True
            if existing:
                if existing['status'] in {'imported', 'blocked', 'failed'}:
                    return dict(existing), False
                conn.execute('UPDATE import_scan_files SET updated_at=? WHERE id=?', (now, existing['id']))
                conn.commit()
                return dict(existing), True
            cursor = conn.execute(
                '''INSERT INTO import_scan_files
                   (job_id, canonical_path, source_filename, size_bytes, mtime_ns,
                    source_hash, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'discovered', ?)''',
                (job_id, canonical, filename, size, mtime_ns, source_hash, now),
            )
            conn.commit()
            return {'id': cursor.lastrowid, 'status': 'discovered', 'source_hash': source_hash}, True

    @classmethod
    def _update_file(cls, file_id, **values):
        if not values:
            return
        values['updated_at'] = _iso(_utc_now())
        assignments = ', '.join(f'{key}=?' for key in values)
        with get_db() as conn:
            conn.execute(f'UPDATE import_scan_files SET {assignments} WHERE id=?', (*values.values(), file_id))
            conn.commit()

    @classmethod
    def _acquire_lease(cls, job_id):
        now = _utc_now()
        token = uuid4().hex
        until = _iso(now + timedelta(seconds=LEASE_SECONDS))
        with get_db() as conn:
            exists = conn.execute('SELECT id FROM import_scan_jobs WHERE id=?', (job_id,)).fetchone()
            if exists is None:
                raise ImportScanValidationError('scan job not found')
            result = conn.execute(
                '''UPDATE import_scan_jobs SET lease_token=?, lease_until=?, updated_at=?
                   WHERE id=? AND enabled=1 AND status='active'
                   AND (lease_until IS NULL OR lease_until < ?)''',
                (token, until, _iso(now), job_id, _iso(now)),
            )
            conn.commit()
        if result.rowcount != 1:
            raise ImportScanConflictError('scan job is already running or disabled')
        return token

    @classmethod
    def _release_lease(cls, job_id, token, **fields):
        fields.update({'lease_token': None, 'lease_until': None, 'updated_at': _iso(_utc_now())})
        assignments = ', '.join(f'{key}=?' for key in fields)
        with get_db() as conn:
            conn.execute(
                f'UPDATE import_scan_jobs SET {assignments} WHERE id=? AND lease_token=?',
                (*fields.values(), job_id, token),
            )
            conn.commit()

    @classmethod
    def run_job_once(cls, job_id):
        token = cls._acquire_lease(job_id)
        run_id = uuid4().hex
        started = _utc_now()
        counters = {'discovered_count': 0, 'imported_count': 0, 'blocked_count': 0, 'failed_count': 0}
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO import_scan_runs (id, job_id, started_at, status) VALUES (?, ?, ?, 'running')''',
                (run_id, job_id, _iso(started)),
            )
            conn.commit()
        try:
            job = cls.get_job(job_id)
            if not job:
                raise ImportScanValidationError('scan job not found')
            for item in cls._discover(job):
                scan_file, should_process = cls._upsert_discovered(job_id, item)
                if not should_process:
                    continue
                counters['discovered_count'] += 1
                file_id = scan_file['id']
                canonical, filename, _, _, _ = item
                try:
                    with open(canonical, 'rb') as handle:
                        content = handle.read()
                    preview = import_service.preview(
                        filename, content, job['source_type'], job.get('mapping_template') or None,
                    )
                    if preview.get('required_unmapped') or preview.get('invalid_rows') or preview.get('duplicate_keys'):
                        cls._update_file(
                            file_id, status='blocked', preview_id=preview.get('id'),
                            error_code='QUALITY_BLOCKED', error_message=json.dumps(preview, ensure_ascii=False),
                        )
                        counters['blocked_count'] += 1
                        continue
                    result = import_service.confirm(preview['id'], preview.get('mapping') or {})
                    cls._update_file(file_id, status='imported', preview_id=preview.get('id'), batch_id=result.get('id'), imported_at=_iso(_utc_now()))
                    counters['imported_count'] += 1
                except (ImportValidationError, OSError, ValueError) as error:
                    cls._update_file(file_id, status='failed', error_code='IMPORT_FAILED', error_message=str(error))
                    counters['failed_count'] += 1
            status = 'completed' if not (counters['failed_count'] or counters['blocked_count']) else 'partial'
            finished = _utc_now()
            with get_db() as conn:
                conn.execute(
                    '''UPDATE import_scan_runs SET completed_at=?, status=?, discovered_count=?, imported_count=?, blocked_count=?, failed_count=? WHERE id=?''',
                    (_iso(finished), status, counters['discovered_count'], counters['imported_count'], counters['blocked_count'], counters['failed_count'], run_id),
                )
                conn.commit()
            cls._release_lease(job_id, token, last_run=_iso(finished), next_run=_iso(finished + timedelta(minutes=1)), last_error=None)
            return {'id': run_id, 'job_id': job_id, 'status': status, **counters}
        except Exception as error:
            with get_db() as conn:
                conn.execute(
                    '''UPDATE import_scan_runs SET completed_at=?, status='failed', error_message=? WHERE id=?''',
                    (_iso(_utc_now()), str(error), run_id),
                )
                conn.commit()
            cls._release_lease(job_id, token, last_run=_iso(_utc_now()), last_error=str(error))
            raise

    @classmethod
    def run_due_jobs(cls, now=None):
        current = now or _utc_now()
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id FROM import_scan_jobs WHERE enabled=1 AND status='active' AND (next_run IS NULL OR next_run <= ?)",
                (_iso(current),),
            ).fetchall()
        results = []
        for row in rows:
            try:
                results.append(cls.run_job_once(row['id']))
            except ImportScanConflictError:
                continue
        return results
