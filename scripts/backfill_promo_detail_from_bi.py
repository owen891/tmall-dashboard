"""Backfill daily_data 推广平台明细 columns from dated BI 商品总览 workbooks.

Why this exists
---------------
``daily_data`` 新增了 5 个推广平台明细列（无界花费 / 无界成交 / 全站推花费 /
全站推成交 / 礼金），但历史行是在这些列存在之前导入的，因此全是 NULL。
导入器（``import_paimi_bi_daily``）现在会映射它们，但重跑整表导入会重写
观测与血缘记录，代价高且有风险。

本脚本只做一件事：按日期+商品把源工作簿里的这 5 列 UPDATE 进 daily_data。
不删除任何行，不写观测表，不触碰其他列。默认 dry-run。

口径对照（BI 列 → daily_data 列）
---------------------------------
    货品全站推花费          → product_sitewide_spend
    全站推广成交金额         → product_sitewide_payment
    首单礼金               → gift_cost
    品牌新享营销托管软件服务费  → brand_marketing_spend

注意：BI 日度导出里「万相台」多数周期整列为 '--'（平台当期没有投放），
此时对应列保持 NULL，不会被写成 0。无界花费/成交因此不在这里回填，
真实数据在 promotion_daily_facts（万相台后台采集）。

用法::

    python scripts/backfill_promo_detail_from_bi.py                  # dry-run
    python scripts/backfill_promo_detail_from_bi.py --apply
    python scripts/backfill_promo_detail_from_bi.py --sources "E:\\派米\\BI销售数据\\26年9月" --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db_path, get_shop_id, init_db  # noqa: E402
from scripts.import_paimi_bi_daily import report_date_or_none  # noqa: E402
from scripts.import_paimi_bi_overview import source_rows  # noqa: E402

# daily_data 列 -> BI 列名（与 import_paimi_bi_daily.DAILY_SPECS 保持一致）
# 注意：无界花费/成交不在这里。BI 导出的「万相台」列在近两年整列为 '--'
# 或 0，真实无界数据在 promotion_daily_facts（万相台后台采集），
# 由 period_review_service 直接读取，无需回填到 daily_data。
PROMO_DETAIL_MAP: dict[str, str] = {
    'product_sitewide_spend': '货品全站推花费',
    'product_sitewide_payment': '全站推广成交金额',
    'gift_cost': '首单礼金',
    'brand_marketing_spend': '品牌新享营销托管软件服务费',
}

DEFAULT_SOURCES = (
    Path(r'E:\派米\BI销售数据\26年9月'),
    Path(r'E:\派米\BI销售数据\8月数据源-bi'),
    Path(r'E:\派米\BI销售数据\25年9月数据源-bi'),
)

MISSING_MARKERS = {'', '--', '-', 'nan', 'none', 'null', 'nat'}


def to_number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '').replace('¥', '').replace('￥', '')
    if text.lower() in MISSING_MARKERS:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def values_for_file(path: Path, stat_date: str) -> dict[str, dict[str, float]]:
    """返回 {product_id: {daily_column: value}}，只保留有数值的字段。"""
    result: dict[str, dict[str, float]] = {}
    for product_id, payload, progress in source_rows(path, stat_date):
        if product_id is None:
            if not progress.get('done'):
                raise RuntimeError(f'{path.name} 未正常完成读取')
            break
        picked: dict[str, float] = {}
        for column, bi_name in PROMO_DETAIL_MAP.items():
            number = to_number(payload.get(bi_name))
            if number is not None:
                picked[column] = number
        if picked:
            result[product_id] = picked
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill 推广平台明细 columns from BI workbooks.')
    parser.add_argument('--db', type=Path, default=Path(get_db_path()))
    parser.add_argument('--sources', nargs='*', type=Path, default=list(DEFAULT_SOURCES))
    parser.add_argument('--dates', nargs='*', help='Limit to YYYY-MM-DD values.')
    parser.add_argument('--apply', action='store_true', help='Write changes (default is dry-run).')
    parser.add_argument('--backup-destination', type=Path,
                        help='Required with --apply: SQLite backup path for this run.')
    args = parser.parse_args()

    files: list[Path] = []
    skipped: list[str] = []
    for source in args.sources:
        if not source.is_dir():
            print(f'跳过不存在的目录: {source}', flush=True)
            continue
        for candidate in source.glob('*.xlsx'):
            if report_date_or_none(candidate) is None:
                skipped.append(candidate.name)
                continue
            files.append(candidate)
    if args.dates:
        wanted = set(args.dates)
        files = [p for p in files if report_date_or_none(p) in wanted]
    files.sort(key=lambda p: report_date_or_none(p) or '')
    if skipped:
        print(f'跳过 {len(skipped)} 个无法识别日期的文件', flush=True)
    if not files:
        raise SystemExit('没有匹配的日度数据源文件')

    db_path = args.db.resolve()
    init_db(str(db_path))

    backup_path = None
    if args.apply:
        if not args.backup_destination:
            raise SystemExit('--apply 需要同时提供 --backup-destination')
        backup_path = args.backup_destination.resolve()
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(db_path)
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        print(f'已备份数据库到 {backup_path}', flush=True)

    connection = sqlite3.connect(db_path, timeout=300)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=300000')

    columns = [r['name'] for r in connection.execute('PRAGMA table_info(daily_data)').fetchall()]
    missing_columns = [c for c in PROMO_DETAIL_MAP if c not in columns]
    if missing_columns:
        connection.close()
        raise SystemExit(f'daily_data 缺少列 {missing_columns}，请先执行 init_db 迁移')

    set_sql = ', '.join(f'{c}=COALESCE(?, {c})' for c in PROMO_DETAIL_MAP)
    totals = Counter()
    touched_days: list[dict] = []

    # 每个文件单独一个事务：既避免长时间独占写锁阻塞线上服务，
    # 也让进度可见、中断后已提交的部分不会丢失。
    try:
        for index, path in enumerate(files, start=1):
            stat_date = report_date_or_none(path)
            assert stat_date is not None
            values = values_for_file(path, stat_date)
            if not values:
                print(f'[{index}/{len(files)}] {path.name}: 无可用明细值', flush=True)
                continue
            rows_updated = 0
            day_totals: Counter = Counter()
            if args.apply:
                connection.execute('BEGIN IMMEDIATE')
            try:
                for product_id, picked in values.items():
                    params = [picked.get(c) for c in PROMO_DETAIL_MAP]
                    cursor = connection.execute(
                        f'UPDATE daily_data SET {set_sql} WHERE shop_id = ? AND date = ? AND product_id = ?',
                        (*params, get_shop_id(), stat_date, product_id),
                    )
                    if cursor.rowcount:
                        rows_updated += cursor.rowcount
                        for column in picked:
                            day_totals[column] += 1
                if args.apply:
                    connection.commit()
            except Exception:
                if args.apply:
                    connection.rollback()
                raise
            totals.update(day_totals)
            detail = ' '.join(f'{c}={day_totals[c]}' for c in PROMO_DETAIL_MAP if day_totals[c])
            print(f'[{index}/{len(files)}] {stat_date}: 源商品 {len(values)}，命中库内行 {rows_updated}'
                  + (f'（{detail}）' if detail else ''), flush=True)
            touched_days.append({'date': stat_date, 'source_products': len(values), 'rows_updated': rows_updated})
    finally:
        connection.close()

    print('\n=== 汇总 ===')
    for column in PROMO_DETAIL_MAP:
        print(f'  {column:<26} 写入单元格数={totals[column]}')
    if not args.apply:
        print('\n这是 dry-run，未写入任何数据。加 --apply 才会落库。')
    elif backup_path:
        print(f'\n备份: {backup_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
