# -*- coding: utf-8 -*-
"""修复 market_products 上升/下降榜 rank 与 buyers 字段错位的历史数据。

历史导入把「排名变化幅度」写进 rank、「当前排名」写进 buyers。本脚本：
  1. 给 market_products 增加 rank_change 列（若不存在）；
  2. 把 rank <- 原 buyers（当前排名），rank_change <- 原 rank（变化幅度），
     buyers 置 NULL，仅作用于 list_type IN ('上升榜','下降榜') 且 buyers 非空的行；
  3. 新上榜（new_entries）语义本来正确（rank=当前排名），不处理。

默认 dry-run 仅打印迁移计划；--apply 需要提供完整性校验备份路径。
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



def migrate(conn, apply=False):
    c = conn.cursor()
    cols = [row[1] for row in c.execute('PRAGMA table_info(market_products)').fetchall()]
    plan = {}
    if 'rank_change' not in cols:
        plan['add_column'] = 'market_products.rank_change INTEGER'
        if apply:
            c.execute('ALTER TABLE market_products ADD COLUMN rank_change INTEGER')

    rows = c.execute(
        '''SELECT id, rank, buyers FROM market_products
           WHERE list_type IN ('上升榜','下降榜') AND buyers IS NOT NULL'''
    ).fetchall()
    plan['affected_rows'] = len(rows)
    preview = [
        {'id': rid, 'rank_old': rank, 'buyers_old': buyers,
         'rank_new': int(buyers), 'rank_change_new': int(rank)}
        for rid, rank, buyers in rows[:5]
    ]
    plan['preview'] = preview

    if apply:
        c.execute(
            '''UPDATE market_products
               SET rank_change = rank, rank = buyers, buyers = NULL
               WHERE list_type IN ('上升榜','下降榜') AND buyers IS NOT NULL'''
        )
        conn.commit()
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description='修复上升/下降榜字段错位')
    parser.add_argument('--db', default=os.environ.get('TMALL_DB_PATH', 'data/dashboard.db'))
    parser.add_argument('--apply', action='store_true', help='实际写入；默认 dry-run')
    parser.add_argument('--backup-destination',
                        help='Required with --apply: integrity-checked SQLite backup path')
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--apply 需要同时提供 --backup-destination')

    if args.apply:
        from scripts.backup_database import backup_database
        backup = backup_database(args.db, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')

    conn = sqlite3.connect(args.db)
    try:
        plan = migrate(conn, apply=args.apply)
    finally:
        conn.close()

    report = {'mode': 'apply' if args.apply else 'dry-run', 'db': args.db, **plan}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
