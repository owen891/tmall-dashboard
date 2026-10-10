# -*- coding: utf-8 -*-
"""补 13 款 9 月上新袜子的 product_tags（2026-10-06 月复盘对账发现的漏标批复）。

背景：标品组 9 月集中上新，其中 13 款链接 BI 侧未带「标品袜子」标签
（生意参谋按标签筛选导出的《商品总览》不含未打标链接，故无证据文件），
用户已在复盘对话中逐一确认这 13 个商品 ID 属于标品袜子。走本脚本写入，
与 fix_product_tags_from_bi.py 同款安全模式：先备份、只补空值、写审计。

名单依据（月复盘对账 2026-10-06）：
- 12 款 9 月有 monthly_data 但 product_tags 为空（合计 GSV 247 元）
- 1 款 1088416873408（10-01 上架，9 月无数据）一并补标

⚠️ 全店 9 月无标签商品 1731 个（多为其他小组链接），**严禁**扩大名单；
新增款须用户逐个确认后加入 KNOWN_IDS。

用法::
    python scripts/fix_socks_untagged_20261006.py            # dry-run
    python scripts/fix_socks_untagged_20261006.py --apply \
        --backup-destination data/backups/dashboard-<ts>-before-socks-tags.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, init_db  # noqa: E402
from scripts.backup_database import backup_database  # noqa: E402

# 用户确认的 13 款标品袜子（2026-10-06 月复盘对账）
KNOWN_IDS = [
    '1082834087859', '1086818556682', '1088234273533', '1086286799100',
    '1088262869360', '1087199646531', '1087206850328', '1086337303120',
    '1089129316479', '1086348935662', '1086391379337', '1086413739848',
    '1088416873408',
]
TAG = '标品袜子'


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill 13 confirmed socks product_tags (empty-only).')
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--apply', action='store_true', help='Write changes (default dry-run).')
    parser.add_argument('--backup-destination', help='Required with --apply.')
    args = parser.parse_args()
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')

    db_path = args.db.resolve()
    if args.apply:
        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')
        init_db(str(db_path))

    conn = sqlite3.connect(db_path, timeout=300)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=300000')

    placeholders = ','.join('?' for _ in KNOWN_IDS)
    rows = conn.execute(f"""
        SELECT product_id, product_tags, title FROM products
        WHERE product_id IN ({placeholders})
    """, KNOWN_IDS).fetchall()
    by_id = {r['product_id']: r for r in rows}
    missing = [pid for pid in KNOWN_IDS if pid not in by_id]
    todo = [r for r in rows if not (r['product_tags'] or '').strip()]
    tagged_other = [r for r in rows if (r['product_tags'] or '').strip() and r['product_tags'] != TAG]

    print(f'名单 {len(KNOWN_IDS)} 款：待补 {len(todo)}，已有其他标签 {len(tagged_other)}，products 表无 {len(missing)}')
    for r in todo:
        print(f'  [补 {TAG}] {r["product_id"]} {(r["title"] or "")[:20]}')
    for r in tagged_other:
        print(f'  [跳过，已有标签 {r["product_tags"]!r}] {r["product_id"]}')
    for pid in missing:
        print(f'  [跳过，products 表无此商品] {pid}')

    if args.apply and todo:
        from repos.audit_repo import AuditRepo  # 写审计，与 API 同款
        conn.execute('BEGIN IMMEDIATE')
        try:
            for r in todo:
                conn.execute("""
                    UPDATE products SET product_tags = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE product_id = ? AND (product_tags IS NULL OR product_tags = '')
                """, (TAG, r['product_id']))
                AuditRepo.record('product', r['product_id'], 'update_metadata',
                                 'monthly-review-skill', '2026-10-06月复盘对账补标（用户确认13款）',
                                 {'product_tags': r['product_tags']}, {'product_tags': TAG},
                                 connection=conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print(f'已回填 {len(todo)} 行（空值才补，写审计）')

    remaining = conn.execute(f"""
        SELECT COUNT(*) FROM products
        WHERE product_id IN ({placeholders}) AND (product_tags IS NULL OR product_tags = '')
    """, KNOWN_IDS).fetchone()[0]
    print(f'名单内仍为空: {remaining}')
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
