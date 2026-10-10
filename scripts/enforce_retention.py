"""Enforce the retention policies declared in ``retention_policies``.

This is the executor that ``db_maintenance.py`` (read-only report) previews for:
it reads each policy, archives or purges the rows past their cutoff, records
every archive in ``archive_catalog`` with a SHA-256 manifest, and never
touches protected tables. Default is dry-run; pass ``--apply`` to mutate.

Modes:
  archive           export rows to JSONL gzip + manifest, catalog them, delete
  purge_after_archive  delete rows past cutoff without exporting (the rows
                      remain recoverable from the upstream collector artifacts)
  compact / retain   not implemented here; compacted or kept as-is
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# policy mode -> (time column, cutoff kind, extra row filter)
# ``month`` columns compare by month start, everything else by ISO date.
# retention_policies stores DAYS, so month-granular tables convert days -> months.
TABLE_SPECS = {
    'collector_data_staging': ('published_at', 'date', "status = 'published'"),
    'collector_artifacts': ('created_at', 'date', None),
    'collector_checkpoints': ('updated_at', 'date', None),
    'monthly_source_payload': ('month', 'month', None),
    'bi_product_daily_raw': ('date', 'date', None),
}

def _column_has_time(conn, table: str, column: str) -> bool:
    """Return True when ``column`` actually stores timestamps, not pure dates.

    2026-10-08：cutoff 的**格式必须匹配列的存储格式**，否则字符串比较会错一天。

    - 时间戳列（``'2026-09-24 01:30:28'``）：纯日期 cutoff ``'2026-09-24'`` 会让
      ``'... 01:30:28' < '2026-09-24'`` 判假 ⇒ **截止日当天全部行永不清理**
      （生产库实测：enforce 报 0、quality_check 报 8316）。
    - 纯日期列（``'2025-09-01'``）：时间戳 cutoff ``'2026-04-11 22:32:56'`` 会让
      ``'2026-04-11' < '2026-04-11 22:32:56'`` 判真 ⇒ **边界当天的行被提前一天归档**
      （``bi_product_daily_raw`` 正是这种列）。

    两种列方向相反，因此不能一刀切。

    探测方式：取 ``MAX(LENGTH(column))`` 而非 ``LIMIT 1`` 单行取样。单行取样对
    混合格式列会**依赖扫描顺序**（先命中纯日期就误判为纯日期列），结果不确定；
    取最大值则只要列中出现过时间戳就一定判定为时间戳列，**与行序无关**。
    时间戳列用时间戳 cutoff 是安全侧选择：对偶发的纯日期行，其 cutoff 当天会被
    保留而非误删。
    """
    try:
        row = conn.execute(
            f'SELECT MAX(LENGTH("{column}")) FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL'
        ).fetchone()
    except sqlite3.Error:
        return False
    if not row or row[0] is None:
        return False
    try:
        return int(row[0]) > 10
    except (TypeError, ValueError):
        return False


def _date_cutoff(days: int) -> str:
    """Retention cutoff for **timestamp** columns (``YYYY-MM-DD HH:MM:SS``).

    见 ``_column_has_time``：时间戳列必须用带时分秒的 cutoff，否则截止日当天
    的行会被判为「未超期」而永远清理不掉。纯日期列请用 ``_pure_date_cutoff``。
    """
    return (datetime.now() - timedelta(days=int(days))).strftime('%Y-%m-%d %H:%M:%S')


def _pure_date_cutoff(days: int) -> str:
    """Retention cutoff for **pure-date** columns (``YYYY-MM-DD``)。

    纯日期列（如 ``bi_product_daily_raw.date``）必须用纯日期 cutoff，否则
    ``'<date>' < '<date> HH:MM:SS'`` 为真，边界当天的行会被提前归档。
    """
    return (date.today() - timedelta(days=int(days))).isoformat()


def _cutoff_for(conn, table: str, column: str, days: int) -> str:
    """Pick the cutoff format matching the column's real storage format."""
    if _column_has_time(conn, table, column):
        return _date_cutoff(days)
    return _pure_date_cutoff(days)


def _month_cutoff(months: int) -> str:
    total = date.today().year * 12 + date.today().month - 1 - int(months)
    return f'{total // 12:04d}-{total % 12 + 1:02d}'


CUTOFF_COLUMN = {'date': _date_cutoff, 'month': _month_cutoff}

EPOCH = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_policies(conn: sqlite3.Connection) -> list[dict]:
    if not _table_exists(conn, 'retention_policies'):
        return []
    rows = conn.execute(
        'SELECT policy_key, source_kind, source_table, retention_days, mode, protected '
        'FROM retention_policies ORDER BY policy_key'
    ).fetchall()
    return [
        {
            'policy_key': r[0], 'source_kind': r[1], 'source_table': r[2],
            'retention_days': int(r[3]), 'mode': r[4], 'protected': bool(r[5]),
        }
        for r in rows
    ]


def eligible_count(conn, table, column, cutoff, extra_where):
    if not _table_exists(conn, table):
        return None
    where = f'"{column}" < ?'
    params = [cutoff]
    if extra_where:
        where += f' AND {extra_where}'
    return int(conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE {where}', params
    ).fetchone()[0])


def export_rows(conn, table, column, cutoff, extra_where, target: Path):
    """Export eligible rows to JSONL gzip, return (count, running sha256)."""
    digest = hashlib.sha256()
    count = 0
    columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
    select_cols = ', '.join(f'"{c}"' for c in columns)
    where = f'"{column}" < ?'
    params = [cutoff]
    if extra_where:
        where += f' AND {extra_where}'
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, 'wb') as handle:
        for row in conn.execute(f'SELECT {select_cols} FROM "{table}" WHERE {where}', params):
            payload = (json.dumps(
                dict(zip(columns, row)), ensure_ascii=False, default=str
            ).encode('utf-8') + b'\n')
            handle.write(payload)
            digest.update(payload)
            count += 1
    return count, digest.hexdigest()


def enforce(database, apply_changes=False, archive_dir=None):
    db_path = Path(database).resolve()
    archive_dir = Path(archive_dir or db_path.parent / 'retention_archives')
    report = {
        'manifest_version': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'database': str(db_path),
        'apply': apply_changes,
        'policies': [],
        'policy': {
            'mutations_performed': apply_changes,
            'delete_performed': False,
            'protected_tables': [],
        },
    }
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # 2026-10-08：归档导出对整表做 ORDER BY / 大范围筛选，SQLite 默认
    # temp_store=FILE 会落系统临时目录；Temp 不可写时抛误导性的
    # "unable to open database file"（实测 monthly_source_payload 归档必失败）。
    # 与 db.get_connection 保持一致。
    conn.execute('PRAGMA temp_store=MEMORY')
    try:
        if not _table_exists(conn, 'retention_policies'):
            report['error'] = 'retention_policies table missing; nothing to enforce'
            return report
        for spec in load_policies(conn):
            table = spec['source_table']
            item = {**spec, 'table_exists': _table_exists(conn, table), 'eligible_count': 0}
            report['policies'].append(item)
            if not item['table_exists'] or spec['protected'] or spec['mode'] == 'retain':
                if spec['protected']:
                    report['policy']['protected_tables'].append(table)
                continue
            if table not in TABLE_SPECS:
                item['action'] = 'unsupported_table'
                continue
            column, cutoff_kind, extra_where = TABLE_SPECS[table]
            if spec['mode'] not in ('archive', 'purge_after_archive'):
                item['action'] = f"unsupported_mode:{spec['mode']}"
                continue
            if cutoff_kind == 'month':
                # retention_days is a day count; month-granular tables archive
                # whole months, so convert with a conservative 30-day month.
                cutoff = CUTOFF_COLUMN['month'](spec['retention_days'] // 30)
            else:
                # 格式必须匹配列的实际存储格式，否则边界会错一天（见 _column_has_time）。
                cutoff = _cutoff_for(conn, table, column, spec['retention_days'])
            item['cutoff'] = cutoff
            item['eligible_count'] = eligible_count(conn, table, column, cutoff, extra_where)
            if item['eligible_count'] == 0:
                item['action'] = 'noop'
                continue
            if not apply_changes:
                item['action'] = 'would_archive' if spec['mode'] == 'archive' else 'would_purge'
                continue
            if spec['mode'] == 'archive':
                target = archive_dir / f'{table}-before-{cutoff}-{EPOCH}.jsonl.gz'
                count, sha = export_rows(conn, table, column, cutoff, extra_where, target)
                actual = eligible_count(conn, table, column, cutoff, extra_where)
                if actual != count:
                    Path(target).unlink(missing_ok=True)
                    raise RuntimeError(
                        f'{table}: row count changed during export ({count} -> {actual})')
                manifest_path = archive_dir / f'manifest-{table}-before-{cutoff}-{EPOCH}.json'
                manifest = {
                    'source_table': table, 'cutoff': cutoff, 'row_count': count,
                    'sha256': sha, 'archive_path': str(target),
                }
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
                if _table_exists(conn, 'archive_catalog'):
                    bounds = conn.execute(
                        f'SELECT MIN("{column}"), MAX("{column}") FROM "{table}" '
                        f'WHERE "{column}" < ?', (cutoff,)).fetchone()
                    conn.execute(
                        '''INSERT OR REPLACE INTO archive_catalog
                           (archive_key, source_kind, source_table, archive_path, source_sha256,
                            row_count, min_value, max_value, status, metadata_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?)''',
                        (f'{table}:{cutoff}:{sha}', spec['source_kind'], table,
                         str(target), sha, count, bounds[0], bounds[1],
                         json.dumps({'cutoff': cutoff, 'manifest': str(manifest_path),
                                     'extra_where': extra_where}, ensure_ascii=False)))
                _delete_eligible(conn, table, column, cutoff, extra_where)
                conn.commit()
                item.update({'action': 'archived', 'archive_path': str(target),
                             'row_count': count, 'sha256': sha})
                report['policy']['delete_performed'] = True
            else:  # purge_after_archive
                _delete_eligible(conn, table, column, cutoff, extra_where)
                conn.commit()
                item['action'] = 'purged'
                item['row_count'] = item['eligible_count']
                report['policy']['delete_performed'] = True
        return report
    finally:
        conn.close()


def _delete_eligible(conn, table, column, cutoff, extra_where):
    where = f'"{column}" < ?'
    params = [cutoff]
    if extra_where:
        where += f' AND {extra_where}'
    conn.execute(f'DELETE FROM "{table}" WHERE {where}', params)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Enforce retention_policies')
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--archive-dir', default=None)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    report = enforce(args.database, apply_changes=args.apply, archive_dir=args.archive_dir)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding='utf-8')
    print(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
