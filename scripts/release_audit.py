"""Read-only release audit for the current checkout and SQLite database."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path


def _git_status(repo_root):
    result = subprocess.run(
        ['git', 'status', '--porcelain=v1'],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def _worktree_report(repo_root):
    changed = untracked = deleted = 0
    for entry in _git_status(repo_root):
        status = entry[:2]
        if status == '??':
            untracked += 1
        elif 'D' in status:
            deleted += 1
        else:
            changed += 1
    return {'changed': changed, 'untracked': untracked, 'deleted': deleted}


def _database_report(database_path):
    path = Path(database_path).resolve()
    if not path.is_file():
        return {
            'path': str(path),
            'integrity': 'missing',
            'tables': 0,
            'import_batches': {'demo': 0, 'real': 0},
        }

    with closing(sqlite3.connect(path)) as connection:
        integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
        table_names = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        tables = len(table_names)
        has_batches = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'import_batches'"
        ).fetchone()[0]
        batches = {'demo': 0, 'real': 0}
        if has_batches:
            for batch_id, filename in connection.execute(
                'SELECT id, source_filename FROM import_batches'
            ):
                marker = f'{batch_id or ""} {filename or ""}'.lower()
                batches['demo' if 'demo' in marker or '演示' in marker else 'real'] += 1
        provenance = {
            'daily_rows': 0,
            'without_observations': 0,
            'without_lineage': 0,
        }
        if 'daily_data' in table_names:
            provenance['daily_rows'] = connection.execute(
                'SELECT COUNT(*) FROM daily_data'
            ).fetchone()[0]
            if 'daily_data_observations' in table_names:
                provenance['without_observations'] = connection.execute(
                    '''SELECT COUNT(*) FROM daily_data d
                       WHERE NOT EXISTS (
                         SELECT 1 FROM daily_data_observations o
                         WHERE o.shop_id = d.shop_id
                           AND o.product_id = d.product_id
                           AND o.date = d.date
                       )'''
                ).fetchone()[0]
            else:
                provenance['without_observations'] = provenance['daily_rows']
            if 'fact_field_lineage' in table_names:
                provenance['without_lineage'] = connection.execute(
                    '''SELECT COUNT(*) FROM daily_data d
                       WHERE NOT EXISTS (
                         SELECT 1 FROM fact_field_lineage l
                         WHERE l.shop_id = d.shop_id
                           AND l.product_id = d.product_id
                           AND l.date = d.date
                       )'''
                ).fetchone()[0]
            else:
                provenance['without_lineage'] = provenance['daily_rows']
    return {
        'path': str(path),
        'integrity': integrity,
        'tables': tables,
        'import_batches': batches,
        'provenance': provenance,
    }


def build_report(repo_root, database_path):
    worktree = _worktree_report(repo_root)
    database = _database_report(database_path)
    blockers = []
    warnings = []
    if any(worktree.values()):
        blockers.append('dirty_worktree')
    if database['integrity'] != 'ok':
        blockers.append('database_integrity_not_ok')
    provenance = database.get('provenance', {})
    if provenance.get('daily_rows') and (
        provenance.get('without_observations') or provenance.get('without_lineage')
    ):
        blockers.append('untraceable_daily_facts')
    if database['import_batches']['demo'] and database['import_batches']['real']:
        warnings.append('mixed_demo_and_real_batches')
    return {
        'worktree': worktree,
        'database': database,
        'blockers': blockers,
        'warnings': warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='只读检查当前工作树和生产数据库发布风险。')
    parser.add_argument('--repo-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--database', default='data/dashboard.db')
    parser.add_argument('--strict', action='store_true', help='存在 blocker 或 warning 时返回 1')
    args = parser.parse_args(argv)

    database = Path(args.database)
    if not database.is_absolute():
        database = Path(args.repo_root) / database
    report = build_report(str(Path(args.repo_root).resolve()), str(database))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if args.strict and (report['blockers'] or report['warnings']) else 0)


if __name__ == '__main__':
    main()
