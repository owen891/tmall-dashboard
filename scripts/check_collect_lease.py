# -*- coding: utf-8 -*-
"""采集租约检查：计划任务链与 RPA 链（/api/collect/trigger）的数据库层互斥。

用法（run_daily_collect.ps1 在启动每个采集器前调用）：
    python scripts/check_collect_lease.py <source_key> --db-path <path>

退出码：
    0  该数据源无活跃租约，可以启动
    3  存在活跃租约（另一条采集链正在采该源），跳过
    4  数据库不可达（视为可启动：计划任务链自身有数据库，
       而锁检查失败不应静默吞掉整晚采集）

租约表 collector_leases 与 services.collector_run_service.acquire_lease
同源：TTL 15 分钟，崩溃残留由 acquire_lease 的清扫路径回收。
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone


def _db_path_from_env(arg_path):
    if arg_path:
        return arg_path
    return os.environ.get('TMALL_DB_PATH') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'dashboard.db',
    )


def lease_is_active(db_path, source_key):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT lease_until FROM collector_leases WHERE source_key = ? ORDER BY lease_until DESC LIMIT 1",
            (source_key,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return False
    try:
        until = datetime.fromisoformat(row[0])
    except (TypeError, ValueError):
        return False
    return until > datetime.now(timezone.utc)


def main():
    parser = argparse.ArgumentParser(description='检查采集数据源的跨进程租约')
    parser.add_argument('source_key')
    parser.add_argument('--db-path', default=None)
    args = parser.parse_args()
    db_path = _db_path_from_env(args.db_path)
    try:
        active = lease_is_active(db_path, args.source_key)
    except sqlite3.Error as error:
        print(f'lease-check: 数据库不可达（{error}），视为可启动', file=sys.stderr)
        return 4
    if active:
        print(f'lease-check: {args.source_key} 存在活跃租约（另一采集链进行中），跳过', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
