# -*- coding: utf-8 -*-
"""滚动重采包装：定期把 BI 的修订值刷回 daily_data。

背景（2026-09/10 对账实测）：
- BI 的「利润(支付预估)」列事后会修订——9 月标品袜子靠补采 09-01~13+29/30 把
  利润差从 2,768 收敛到 120。日常采集只抓昨天一次，修订永远拿不到。
- BI 近 ~13 天的日期不返回退款字段（字段窗口），窗口过后才会返回完整字段，
  所以窗口期刚过的日期必须再采一遍才能补上退款。
- 本包装只负责算窗口、拿互斥锁、串起 登录→补采 两步；防爬限速全部沿用
  backfill_overview_history.py 自身的默认参数（天间隔 60~120s）。

用法（计划任务调用）：
    python scripts/backfill_rolling.py --mode weekly   # 近 14 天（T-14 ~ T-1）
    python scripts/backfill_rolling.py --mode monthly  # 上个自然月
手动：
    python scripts/backfill_rolling.py --start 2026-10-02 --end 2026-10-03
    python scripts/backfill_rolling.py --mode weekly --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLLECTORS_DIR = Path(os.environ.get('TMALL_COLLECTORS_DIR', str(PROJECT_ROOT / 'collectors')))
LOG_DIR = PROJECT_ROOT / 'logs'
LOCK_PATH = LOG_DIR / 'collect.lock'
LOCK_TTL_SECONDS = 7200  # 与 auto-collect.ps1 的互斥锁同一份文件、同一 TTL


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / 'backfill_rolling.log', 'a', encoding='utf-8') as handle:
        handle.write(line + '\n')


def compute_window(mode: str, today: date) -> tuple[date, date]:
    if mode == 'weekly':
        return today - timedelta(days=14), today - timedelta(days=1)
    if mode == 'monthly':
        first = today.replace(day=1)
        last_prev = first - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    raise ValueError(f'unknown mode: {mode}')


def lock_is_busy() -> bool:
    """与 auto-collect.ps1 共用 logs/collect.lock（PID + 写入时间，2h TTL）。"""
    if not LOCK_PATH.exists():
        return False
    try:
        raw = LOCK_PATH.read_text(encoding='utf-8', errors='ignore')
        match = re.search(r'"pid"\s*:\s*(\d+)', raw)
        owner_pid = int(match.group(1)) if match else 0
        age = time.time() - LOCK_PATH.stat().st_mtime
        if age < LOCK_TTL_SECONDS and owner_pid:
            os.kill(owner_pid, 0)  # 不发信号，只探活
            return True
    except (OSError, ValueError):
        pass
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass
    return False


def acquire_lock() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(
        json.dumps({'pid': os.getpid(), 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S')}),
        encoding='utf-8',
    )


def release_lock() -> None:
    try:
        if LOCK_PATH.exists():
            owner = LOCK_PATH.read_text(encoding='utf-8', errors='ignore')
            if str(os.getpid()) in owner:
                LOCK_PATH.unlink()
    except OSError:
        pass


def run_step(name: str, command: list[str]) -> None:
    log(f'→ {name}: {" ".join(command)}')
    result = subprocess.run(command, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise SystemExit(f'{name} 失败（exit {result.returncode}），中止本次滚动重采')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('weekly', 'monthly'), help='窗口模式')
    parser.add_argument('--start', help='手动指定起始日期 YYYY-MM-DD')
    parser.add_argument('--end', help='手动指定结束日期 YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='只打印窗口与命令')
    args = parser.parse_args()

    if args.start and args.end:
        start, end = args.start, args.end
    else:
        if not args.mode:
            parser.error('需要 --mode weekly|monthly 或 --start/--end')
        start, end = compute_window(args.mode, date.today())

    LOG_DIR.mkdir(exist_ok=True)
    python = sys.executable
    collector_python = os.environ.get('TMALL_COLLECT_PYTHON') or str(PROJECT_ROOT / '.venv' / 'Scripts' / 'python.exe')
    backfill_script = COLLECTORS_DIR / 'backfill_overview_history.py'
    if not backfill_script.exists():
        raise SystemExit(f'补采脚本不存在: {backfill_script}')

    commands = [
        ('BI 登录', [python, str(PROJECT_ROOT / 'scripts' / 'auto_login_bi.py'), '--sources', 'bi_daily']),
        ('滚动补采', [collector_python, str(backfill_script),
                      '--start', str(start), '--end', str(end), '--force']),
    ]

    print(f'窗口: {start} ~ {end}（--force 强制重采，忽略断点状态）')
    if args.dry_run:
        for name, command in commands:
            print(f'[dry-run] {name}: {" ".join(command)}')
        return

    if lock_is_busy():
        log('SKIP: 另一条采集链正在运行（logs/collect.lock），本次退出避免双链并发。')
        return
    acquire_lock()
    try:
        log(f'滚动重采开始：{start} ~ {end}')
        for name, command in commands:
            run_step(name, command)
        log(f'滚动重采完成：{start} ~ {end}')
    finally:
        release_lock()


if __name__ == '__main__':
    main()
