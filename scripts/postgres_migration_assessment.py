"""Produce a read-only SQLite-to-PostgreSQL migration assessment."""

import argparse
import json
import sqlite3
from pathlib import Path


def assess(database):
    path = Path(database).resolve()
    with sqlite3.connect(path) as conn:
        tables = []
        for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append({'name': name, 'row_count': count, 'ddl_bytes': len(sql or '')})
        page_count = conn.execute('PRAGMA page_count').fetchone()[0]
        page_size = conn.execute('PRAGMA page_size').fetchone()[0]
    total_rows = sum(item['row_count'] for item in tables)
    return {
        'database': str(path), 'file_size_bytes': path.stat().st_size,
        'page_count': page_count, 'page_size': page_size,
        'table_count': len(tables), 'total_rows': total_rows, 'tables': tables,
        'recommendation': '继续使用 SQLite，先完成归档和读写拆分；达到多写入 worker 或锁等待明显增加后再迁移 PostgreSQL。',
        'migration_prerequisites': [
            '为日期/店铺/来源建立 PostgreSQL 分区与索引方案',
            '将采集 staging、运行记录、告警表先迁移并双写校验',
            '完成 lineage/raw 历史数据分层归档和回放校验',
            '进行并发写入、备份恢复和查询延迟压测',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description='Assess PostgreSQL migration readiness')
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = assess(args.database)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'table_count': report['table_count'],
                      'total_rows': report['total_rows']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
