"""Import market item images and detail links keyed by item_id."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import openpyxl


def normalize_image(value: object) -> str:
    text = str(value or '').strip()
    if text.startswith('//'):
        return 'https:' + text
    return text if text.startswith(('http://', 'https://')) else ''


def read_rows(path: Path) -> list[dict[str, str]]:
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(value or '').strip() for value in rows[0]]
    aliases = {
        'item_id': ('商品ID', '商品 Id', 'item_id'),
        'pic_url': ('商品图片链接', '商品图片地址', 'pic_url'),
        'detail_url': ('商品链接', '商品链接地址', 'detail_url'),
        'title': ('商品名称', '商品标题', 'title'),
    }
    positions = {}
    for key, names in aliases.items():
        positions[key] = next((headers.index(name) for name in names if name in headers), None)
    if positions['item_id'] is None:
        raise ValueError(f'未找到商品ID列，实际表头：{headers}')
    records = {}
    for row in rows[1:]:
        item_id = str(row[positions['item_id']] or '').strip()
        if not item_id:
            continue
        records[item_id] = {
            'item_id': item_id,
            'title': str(row[positions['title']] or '').strip() if positions['title'] is not None else '',
            'pic_url': normalize_image(row[positions['pic_url']]) if positions['pic_url'] is not None else '',
            'detail_url': str(row[positions['detail_url']] or '').strip() if positions['detail_url'] is not None else '',
        }
    return list(records.values())


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS market_item_links (
            item_id TEXT PRIMARY KEY,
            title TEXT,
            pic_url TEXT,
            detail_url TEXT,
            source_filename TEXT NOT NULL,
            period_start TEXT,
            period_end TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def import_rows(conn: sqlite3.Connection, rows: list[dict[str, str]], source: Path) -> int:
    period_start, period_end = '', ''
    for value in source.stem.split('_'):
        if '~' in value:
            period_start, period_end = value.split('~', 1)
            break
    for row in rows:
        conn.execute('''
            INSERT INTO market_item_links
                (item_id, title, pic_url, detail_url, source_filename, period_start, period_end, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                title=CASE WHEN excluded.title <> '' THEN excluded.title ELSE market_item_links.title END,
                pic_url=CASE WHEN excluded.pic_url <> '' THEN excluded.pic_url ELSE market_item_links.pic_url END,
                detail_url=CASE WHEN excluded.detail_url <> '' THEN excluded.detail_url ELSE market_item_links.detail_url END,
                source_filename=excluded.source_filename,
                period_start=excluded.period_start,
                period_end=excluded.period_end,
                updated_at=CURRENT_TIMESTAMP
        ''', (row['item_id'], row['title'], row['pic_url'], row['detail_url'], source.name, period_start, period_end))
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--xlsx', required=True)
    parser.add_argument('--db', default='data/dashboard.db')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = Path(args.xlsx)
    rows = read_rows(source)
    report = {
        'file': str(source),
        'unique_item_ids': len(rows),
        'with_images': sum(bool(row['pic_url']) for row in rows),
        'with_detail_urls': sum(bool(row['detail_url']) for row in rows),
        'mode': 'apply' if args.apply else 'dry-run',
    }
    if args.apply:
        conn = sqlite3.connect(args.db)
        try:
            ensure_schema(conn)
            imported = import_rows(conn, rows, source)
            conn.commit()
            report['imported'] = imported
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    print(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
