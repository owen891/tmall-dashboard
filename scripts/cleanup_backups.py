"""清理已验证的同源备份；默认 dry-run，不删除未知/异源文件。

【已作废 2026-10-18】旧“最新2份 + .bak文件名白名单”策略会绕过
SAFE-01 恢复代保护。现在唯一删除入口是 prune_verified_backups。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path  # noqa: E402
from scripts.backup_retention import prune_verified_backups, retention_settings  # noqa: E402

BACKUPS_DIR = ROOT / 'data' / 'backups'
# Historical identifiers retained for callers; no longer deletion authority.
KEEP_NEWEST_BACKUPS = 2
KEEP_BAK = (
    'dashboard.db.bak_costcols_20260920_221255',
    'dashboard.db.bak_parents_20260920_214057',
)


def gb(size):
    return size / 1024 ** 3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--source', type=Path, default=None,
                        help='Only rotate verified backups belonging to this exact source database')
    args = parser.parse_args()
    source = (args.source or Path(get_db_path())).resolve()
    keep, cap = retention_settings()
    print(f'源数据库: {source}')
    print(f'备份目录: {BACKUPS_DIR.resolve()}')
    print(f'策略: 至少 {max(3, keep)} 个已验证同源代，容量 {gb(cap):.2f}GB；冲突告警不删保护代')
    print('未验证、异源、源数据库及 .bak_* 文件全部保护；非递归，仅验证 sidecar 成员')
    baks = sorted(p for p in (ROOT / 'data').glob('dashboard.db.bak_*') if p.is_file())
    for path in baks:
        print(f'  保护未验证旧备份: {path.name}')
    if not args.apply:
        # No second, approximate pruning algorithm: exact delete eligibility is
        # determined by the single verified policy at explicit apply time.
        print('dry-run: 仅展示策略，不声明未经完整验证的可删除清单；未删除。加 --apply 执行')
        return 0
    report = {}
    removed = prune_verified_backups(BACKUPS_DIR, keep_newest=keep,
                                    max_total_bytes=cap, protected=[source],
                                    source=source, report=report)
    for path in removed:
        print(f'  已删除已验证轮换代: {path.name}')
    for warning in report.get('warnings', []):
        print(f'WARNING: {warning}')
    print(f"实际删除 {len(removed)} 个备份；有效同源代 {report.get('verified_generations', 0)}；"
          f"目录当前容量 {gb(report.get('total_bytes', 0)):.2f}GB")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
