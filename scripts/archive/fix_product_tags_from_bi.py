# -*- coding: utf-8 -*-
"""Backfill products.product_tags from a BI 商品总览 workbook (empty-only).

背景：部分商品的 product_tags 列为空（BI 按天/区间导出里有 商品标签 证据，
但 overview 月度导入链路未覆盖这些商品）。本脚本从 BI 工作簿读取 商品id→商品标签
证据，只回填 product_tags 为空的行，**绝不覆盖已有标签**。

与 products.product_tags 相关的其他写入路径（勿混用）：
- import_paimi_bi_overview.py：会替换所涉月份的 monthly_data，勿用于只补标签
- enrich_products_from_standard_reference.py：写入"分类标签:标品"词汇，与精确
  匹配 '标品袜子' 的下游过滤不兼容
- POST /api/products/batch-tags：写的是 product_tags 标签表（多对多），不是本列

用法::

    python scripts/fix_product_tags_from_bi.py --file <商品总览.xlsx>            # dry-run
    python scripts/fix_product_tags_from_bi.py --file <商品总览.xlsx> --apply \
        --backup-destination data/backups/dashboard-<ts>-before-tags-backfill.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, init_db  # noqa: E402
from scripts.backup_database import backup_database  # noqa: E402

MISSING = {'', '-', '--', '—', 'none', 'null', 'nan'}


def load_evidence(file_path: Path) -> dict[str, str]:
    """从 BI 工作簿提取 商品id -> 商品标签 证据（跳过无标签行）"""
    df = pd.read_excel(file_path, header=1)
    df.columns = [str(c).strip() for c in df.columns]
    if '商品id' not in df.columns or '商品标签' not in df.columns:
        raise SystemExit(f'工作簿缺少 商品id/商品标签 列，实际列: {list(df.columns)[:12]}')
    evidence: dict[str, str] = {}
    for _, row in df.iterrows():
        pid = str(row['商品id']).strip()
        tag = str(row['商品标签']).strip() if pd.notna(row['商品标签']) else ''
        if pid and pid not in MISSING and tag and tag not in MISSING:
            evidence[pid] = tag
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill products.product_tags from BI workbook (empty-only).')
    parser.add_argument('--file', type=Path, required=True, help='BI 商品总览工作簿')
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--apply', action='store_true', help='Write changes (default dry-run).')
    parser.add_argument('--backup-destination', help='Required with --apply.')
    args = parser.parse_args()
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')

    evidence = load_evidence(args.file)
    print(f'工作簿证据: {len(evidence)} 个商品带标签')

    db_path = args.db.resolve()
    if args.apply:
        backup = backup_database(db_path, args.backup_destination)
        if not backup['ok']:
            raise RuntimeError('database backup integrity check failed')
        init_db(str(db_path))

    conn = sqlite3.connect(db_path, timeout=300)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=300000')

    placeholders = ','.join('?' for _ in evidence)
    rows = conn.execute(f"""
        SELECT product_id, product_tags FROM products
        WHERE product_id IN ({placeholders})
          AND (product_tags IS NULL OR product_tags = '')
    """, list(evidence)).fetchall()

    if not rows:
        print('无需回填：证据内商品没有 product_tags 为空的行。')
        conn.close()
        return 0

    by_tag: dict[str, list[str]] = {}
    for r in rows:
        by_tag.setdefault(evidence[r['product_id']], []).append(r['product_id'])
    print(f'待回填 {len(rows)} 个空标签商品:')
    for tag, ids in sorted(by_tag.items()):
        print(f'  [{tag}] {len(ids)} 个: {", ".join(ids[:8])}{" ..." if len(ids) > 8 else ""}')

    if args.apply:
        conn.execute('BEGIN IMMEDIATE')
        try:
            for tag, ids in by_tag.items():
                ph = ','.join('?' for _ in ids)
                conn.execute(f"""
                    UPDATE products SET product_tags = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE product_id IN ({ph}) AND (product_tags IS NULL OR product_tags = '')
                """, [tag, *ids])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print(f'已回填 {len(rows)} 行（空值才补，未覆盖任何已有标签）')
    else:
        print('（dry-run，未写入。加 --apply --backup-destination 执行）')

    remaining = conn.execute(
        "SELECT COUNT(*) FROM products WHERE (product_tags IS NULL OR product_tags = '') "
        "AND product_id IN (" + ','.join('?' for _ in evidence) + ")",
        list(evidence)).fetchone()[0]
    print(f'证据内仍为空的商品: {remaining}')
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
