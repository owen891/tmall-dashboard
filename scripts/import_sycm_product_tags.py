# -*- coding: utf-8 -*-
"""从生意参谋「商品总览」导出 XLSX 同步商品标签到 products.shop_label。

背景（2026-10-04 排查结论）：BI（ecbis）接口拿不到商家品类标签（tagGroup
恒为 '--'），标签只在生意参谋侧维护（商品总览的「标签」筛选组）。本导入器
吃用户从 sycm 商品总览手动导出的 XLSX（支持按标签组筛选后的名单，或全量
名单），把标签写回 shop_label——这是采集链路之外唯一权威的标签来源。

用法：
    python scripts/import_sycm_product_tags.py --file "商品总览_2026-10-04.xlsx"
    python scripts/import_sycm_product_tags.py --latest   # 自动取 Downloads 里最新的商品总览导出
    python scripts/import_sycm_product_tags.py --file xxx.xlsx --dry-run

容错：表头在前 5 行内自动探测；商品ID列匹配 商品ID/goodsId/商品链接编码，
标签列匹配 标签/分组/商品标签。只更新文件里出现的商品（不在文件里的商品
标签保持原值，不会被清空）。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DB = PROJECT_ROOT / 'data' / 'dashboard.db'
DOWNLOADS = Path.home() / 'Downloads'
ID_HEADER = re.compile(r'商品ID|商品id|goodsId|ID', re.IGNORECASE)
LABEL_HEADER = re.compile(r'标签|分组|商品标记')
NOISE_LABELS = {'', '--', 'nan', 'none', 'null', '-'}


def _clean(value) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    return '' if text.lower() in NOISE_LABELS else text


def pick_latest_download() -> Path:
    candidates = sorted(
        (p for p in DOWNLOADS.glob('*.xlsx') if '商品总览' in p.name or '导出' in p.name),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if not candidates:
        raise SystemExit(f'{DOWNLOADS} 下没找到商品总览导出（*商品总览*.xlsx），请先在生意参谋导出')
    return candidates[0]


def extract_rows(xlsx: Path) -> list[tuple[str, str]]:
    """返回 [(product_id, label)]，表头在前 5 行内自动探测。"""
    from openpyxl import load_workbook

    workbook = load_workbook(xlsx, read_only=True, data_only=True)
    try:
        sheet = workbook[workbook.sheetnames[0]]
        rows = sheet.iter_rows(min_row=1, max_row=5, values_only=True)
        id_col = label_col = None
        header_row_index = 0
        for index, row in enumerate(rows):
            cells = [_clean(cell) for cell in row]
            for col, cell in enumerate(cells):
                if id_col is None and cell and ID_HEADER.search(cell):
                    id_col = col
                if label_col is None and cell and LABEL_HEADER.search(cell):
                    label_col = col
            if id_col is not None:
                header_row_index = index
                break
        if id_col is None:
            raise SystemExit('没找到商品ID列（表头需含「商品ID」）；请确认导出的是商品总览名单')
        if label_col is None:
            raise SystemExit('没找到标签列（表头需含「标签/分组」）；导出时请让标签列可见')

        out: list[tuple[str, str]] = []
        for row in sheet.iter_rows(min_row=header_row_index + 2, values_only=True):
            product_id = _clean(row[id_col]) if id_col < len(row) else ''
            digits = re.sub(r'\D', '', product_id)
            label = _clean(row[label_col]) if label_col < len(row) else ''
            if digits and label:
                out.append((digits, label))
        return out
    finally:
        workbook.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', help='sycm 商品总览导出 XLSX 路径')
    parser.add_argument('--latest', action='store_true', help='自动取 Downloads 里最新的导出')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    xlsx = Path(args.file) if args.file else (pick_latest_download() if args.latest else None)
    if not xlsx:
        parser.error('需要 --file 或 --latest')
    if not xlsx.exists():
        raise SystemExit(f'文件不存在: {xlsx}')

    pairs = extract_rows(xlsx)
    if not pairs:
        raise SystemExit('文件里没有可用的 (商品ID, 标签) 行——如果按标签组筛选后导出为空，请检查筛选条件')

    import sqlite3

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    distribution: Counter = Counter()
    updated = unchanged = missing = 0
    for product_id, label in pairs:
        row = connection.execute(
            'SELECT shop_label FROM products WHERE product_id = ?', (product_id,)
        ).fetchone()
        if row is None:
            missing += 1
            continue
        if (row['shop_label'] or '').strip() == label:
            unchanged += 1
            continue
        distribution[label] += 1
        if not args.dry_run:
            connection.execute(
                'UPDATE products SET shop_label = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
                (label, product_id),
            )
    if not args.dry_run:
        connection.commit()
    connection.close()

    action = '将更新' if args.dry_run else '已更新'
    print(f'文件: {xlsx.name}，有效行 {len(pairs)}')
    print(f'{action} {sum(distribution.values())} 款标签；无变化 {unchanged}；文件里有但商品库没有 {missing}')
    print('标签分布（本次变更）:')
    for label, count in distribution.most_common(15):
        print(f'  {label}: {count}')


if __name__ == '__main__':
    main()
