"""清理 data/ 目录下过期的空导入审计 JSON（轮转缺失问题）。

背景：派米 BI / 市场一键导出等导入流程会在 data/ 根目录落下
``*_import_*.json`` 审计文件，其中大量为 0 字节（无数据结果）且从不轮转，
长期堆积数十个。

策略（保守）：
- 只处理文件名匹配 ``*_import_YYYYMMDD_HHMMSS.json`` 的空文件（size == 0）
- 保留最近 30 天（含当天）；更早的空文件删除
- 非空审计文件、无日期戳文件、其他备份性质文件一律不动

用法：
    py -3 scripts/cleanup_import_audit_logs.py            # dry-run 预览
    py -3 scripts/cleanup_import_audit_logs.py --apply    # 实际删除
    py -3 scripts/cleanup_import_audit_logs.py --days 60  # 自定义保留天数
"""

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / 'data'

# _YYYYMMDD_HHMMSS.json 后缀
_TIMESTAMP_RE = re.compile(r'_(\d{8})_\d{6}\.json$')


def collect_candidates(data_dir, retention_days, now=None):
    now = now or dt.date.today()
    candidates = []
    for path in sorted(data_dir.glob('*_import_*.json')):
        if path.stat().st_size != 0:
            continue  # 有内容的审计文件保留
        match = _TIMESTAMP_RE.search(path.name)
        if not match:
            continue  # 无日期戳（如 import_log.json）不动
        try:
            file_date = dt.datetime.strptime(match.group(1), '%Y%m%d').date()
        except ValueError:
            continue
        age_days = (now - file_date).days
        if age_days > retention_days:
            candidates.append((path, file_date, age_days))
    return candidates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='实际删除；默认仅预览')
    parser.add_argument('--days', type=int, default=30, help='保留天数（默认 30）')
    parser.add_argument('--data-dir', default=str(DATA_DIR), help='数据目录（默认 data/）')
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f'数据目录不存在: {data_dir}')
        return 2

    candidates = collect_candidates(data_dir, args.days)
    if not candidates:
        print(f'无需清理：{data_dir} 下无超过 {args.days} 天的空导入审计文件。')
        return 0

    total_bytes = 0
    for path, file_date, age_days in candidates:
        size = path.stat().st_size
        total_bytes += size
        action = '删除' if args.apply else '待删'
        print(f'{action}  {path.name}  (日期 {file_date}, {age_days} 天前, {size} B)')

    print(f'\n共 {len(candidates)} 个空审计文件, 释放 {total_bytes} B')
    if not args.apply:
        print('dry-run 模式，未做任何修改。加 --apply 实际执行。')
        return 0

    for path, _, _ in candidates:
        try:
            path.unlink()
        except OSError as error:
            print(f'删除失败 {path.name}: {error}')
            return 1
    print(f'已删除 {len(candidates)} 个文件。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
