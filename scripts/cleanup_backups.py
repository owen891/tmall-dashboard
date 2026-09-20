"""清理历史数据库备份（默认只打印计划，加 --apply 才真正删除）。

保留策略：
- ``data/backups/*.db``：只留最新 2 份（同一批导入前后几分钟的快照，留 2 份足够回滚）
- ``data/dashboard.db.bak_*``：按文件名白名单保留（每个风险点一份回滚点），其余删除
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backup_retention import prune_backups  # noqa: E402

BACKUPS_DIR = ROOT / 'data' / 'backups'
KEEP_NEWEST_BACKUPS = 2
# 每个风险点保留一份回滚快照：成本列迁移前、渠道父级规整前
KEEP_BAK = (
    'dashboard.db.bak_costcols_20260920_221255',
    'dashboard.db.bak_parents_20260920_214057',
)


def gb(size):
    return size / 1024 ** 3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    # ---- data/backups/*.db ----
    candidates = [p for p in BACKUPS_DIR.glob('*.db') if p.is_file()]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    keep = candidates[:KEEP_NEWEST_BACKUPS]
    drop = candidates[KEEP_NEWEST_BACKUPS:]

    print('== data/backups/ ==')
    for path in keep:
        print('  保留  %7.2fGB  %s' % (gb(path.stat().st_size), path.name))
    for path in drop:
        print('  删除  %7.2fGB  %s' % (gb(path.stat().st_size), path.name))
    print('  小计：保留 %d 份 / 删除 %d 份，释放 %.2fGB' % (
        len(keep), len(drop), sum(gb(p.stat().st_size) for p in drop)))

    # ---- data/dashboard.db.bak_* ----
    baks = sorted(p for p in (ROOT / 'data').glob('dashboard.db.bak_*') if p.is_file())
    keep_bak = [p for p in baks if p.name in KEEP_BAK]
    drop_bak = [p for p in baks if p.name not in KEEP_BAK]

    print('== data/dashboard.db.bak_* ==')
    for path in keep_bak:
        print('  保留  %7.2fGB  %s' % (gb(path.stat().st_size), path.name))
    for path in drop_bak:
        print('  删除  %7.2fGB  %s' % (gb(path.stat().st_size), path.name))
    print('  小计：保留 %d 份 / 删除 %d 份，释放 %.2fGB' % (
        len(keep_bak), len(drop_bak), sum(gb(p.stat().st_size) for p in drop_bak)))

    total = sum(gb(p.stat().st_size) for p in drop + drop_bak)
    print('合计可释放 %.2fGB' % total)
    if not args.apply:
        print('（dry-run，未删除。加 --apply 执行）')
        return 0

    planned_bytes = sum(p.stat().st_size for p in drop + drop_bak)

    removed = []
    removed.extend(prune_backups(BACKUPS_DIR, keep_newest=KEEP_NEWEST_BACKUPS,
                                 max_total_bytes=1024 ** 4, pattern='*.db'))
    for path in drop_bak:
        try:
            path.unlink()
            removed.append(path)
        except OSError as error:
            print('删除失败 %s: %s' % (path, error))
    print('实际删除 %d 个文件，释放 %.2fGB' % (len(removed), gb(planned_bytes)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
