"""Safely restore provenance for legacy daily facts with an exact import match.

The command is read-only by default.  ``--apply`` only writes rows when one
completed product-day batch uniquely matches the data_source, shop, date range,
and valid row count.  Ambiguous or manually-entered facts are reported and
left untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db, get_db_path
from services.source_resolution_service import record_daily_observation


def _batch_range(batch):
    try:
        quality = json.loads(batch['quality_summary'] or '{}')
    except (TypeError, json.JSONDecodeError):
        return None, None
    date_range = quality.get('date_range') or {}
    return date_range.get('start'), date_range.get('end')


def plan_backfill(connection):
    """Return exact-match batches and the facts eligible for repair."""
    batches = connection.execute(
        """SELECT * FROM import_batches
           WHERE status='completed' AND source_type='product_day'
           ORDER BY created_at, id"""
    ).fetchall()
    grouped = defaultdict(list)
    for batch in batches:
        # A filename is the only identifier legacy daily_data retained.  A
        # changed hash therefore makes the filename ambiguous too; never
        # choose between same-named batches automatically.
        grouped[(batch['shop_id'] or 'default', batch['source_filename'])].append(batch)

    eligible = []
    skipped = []
    for key, candidates in grouped.items():
        shop_id, source_filename = key
        if len(candidates) != 1:
            skipped.append({'source_filename': source_filename, 'reason': 'ambiguous_batch', 'batch_count': len(candidates)})
            continue
        batch = candidates[0]
        start, end = _batch_range(batch)
        if not start or not end:
            skipped.append({'source_filename': source_filename, 'reason': 'missing_date_range'})
            continue
        matching_count = connection.execute(
            """SELECT COUNT(*) FROM daily_data d
               WHERE d.shop_id=? AND d.data_source=? AND d.date BETWEEN ? AND ?""",
            (shop_id, source_filename, start, end),
        ).fetchone()[0]
        rows = connection.execute(
            """SELECT d.* FROM daily_data d
               WHERE d.shop_id=? AND d.data_source=? AND d.date BETWEEN ? AND ?
                 AND NOT EXISTS (
                   SELECT 1 FROM daily_data_observations o
                   WHERE o.shop_id=d.shop_id AND o.product_id=d.product_id AND o.date=d.date
                 )
               ORDER BY d.date, d.product_id""",
            (shop_id, source_filename, start, end),
        ).fetchall()
        expected = int(batch['valid_rows'] or 0)
        if len(rows) == 0 and matching_count == expected:
            skipped.append({'source_filename': source_filename, 'reason': 'already_traceable', 'rows': expected})
            continue
        if len(rows) != expected:
            skipped.append({
                'source_filename': source_filename,
                'reason': 'row_count_mismatch',
                'expected': expected,
                'actual': len(rows),
            })
            continue
        eligible.append({'batch': dict(batch), 'rows': rows})
    return eligible, skipped


def run(database_path, apply=False):
    with get_db(database_path) as connection:
        eligible, skipped = plan_backfill(connection)
        report = {
            'database': str(Path(database_path).resolve()),
            'apply': bool(apply),
            'eligible_batches': [
                {'id': item['batch']['id'], 'source_filename': item['batch']['source_filename'], 'rows': len(item['rows'])}
                for item in eligible
            ],
            'skipped': skipped,
            'written': 0,
        }
        if apply:
            for item in eligible:
                batch = item['batch']
                for row in item['rows']:
                    record_daily_observation(
                        connection,
                        dict(row),
                        batch['source_type'],
                        source_filename=batch['source_filename'],
                        source_batch_id=batch['id'],
                        shop_id=batch['shop_id'] or 'default',
                    )
                report['written'] += len(item['rows'])
            connection.commit()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='按精确导入批次恢复日事实来源记录。')
    parser.add_argument('--database', default=get_db_path())
    parser.add_argument('--apply', action='store_true', help='写入唯一匹配批次；默认只读预览')
    args = parser.parse_args(argv)
    print(json.dumps(run(os.path.abspath(args.database), apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
