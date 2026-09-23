# -*- coding: utf-8 -*-
"""市场分析数据建表+导入脚本
从 analysis_result.json 导入店透视市场排行数据到看板数据库
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get('TMALL_DB_PATH', 'data/dashboard.db')
JSON_PATH = os.environ.get('TMALL_MARKET_RANKING_JSON', r'E:\skill-dianshang\月复盘SKILL\analysis_result.json')

def create_tables(conn, commit=True):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS market_analysis_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_date TEXT NOT NULL,
        period_start TEXT,
        period_end TEXT,
        source TEXT DEFAULT '店透视市场排行',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(analysis_date, source)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS market_category_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        shop_tmall INTEGER DEFAULT 0,
        shop_taobao INTEGER DEFAULT 0,
        trend_flat INTEGER DEFAULT 0,
        trend_up INTEGER DEFAULT 0,
        trend_down INTEGER DEFAULT 0,
        trend_out INTEGER DEFAULT 0,
        trend_new INTEGER DEFAULT 0,
        concentration_top10 REAL,
        concentration_top50 REAL,
        total_buyers REAL,
        FOREIGN KEY (run_id) REFERENCES market_analysis_runs(id),
        UNIQUE(run_id, category)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS market_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        list_type TEXT NOT NULL,
        rank INTEGER,
        title TEXT,
        shop TEXT,
        buyers REAL,
        visitors REAL,
        product_url TEXT,
        image_url TEXT,
        FOREIGN KEY (run_id) REFERENCES market_analysis_runs(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS market_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        keyword_type TEXT NOT NULL,
        keyword TEXT NOT NULL,
        count INTEGER DEFAULT 0,
        rank INTEGER,
        FOREIGN KEY (run_id) REFERENCES market_analysis_runs(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS market_overlap_shops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        shop_name TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES market_analysis_runs(id)
    )''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_mp_run_cat ON market_products(run_id, category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_mp_list_type ON market_products(list_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_mk_run_cat ON market_keywords(run_id, category)')
    if commit:
        conn.commit()
    print("建表完成")

def import_data(conn, commit=True):
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    c = conn.cursor()

    # 1. 创建分析批次
    analysis_date = '2026-09-13'
    period_start = '2026-08-17'
    period_end = '2026-09-13'
    c.execute('''INSERT OR IGNORE INTO market_analysis_runs
        (analysis_date, period_start, period_end, source) VALUES (?, ?, ?, ?)''',
        (analysis_date, period_start, period_end, '店透视市场排行'))
    c.execute('SELECT id FROM market_analysis_runs WHERE analysis_date=? AND source=?',
        (analysis_date, '店透视市场排行'))
    run_id = c.fetchone()[0]
    print(f"分析批次ID: {run_id}")

    # 清理旧数据
    for table in ['market_category_stats', 'market_products', 'market_keywords', 'market_overlap_shops']:
        c.execute(f'DELETE FROM {table} WHERE run_id=?', (run_id,))

    cat_map = {'mid': '中筒袜', 'long': '长筒袜'}
    list_type_map = {
        'top_buyers': '支付买家数TOP',
        'top_visitors': '访客数TOP',
        'top_shops': '店铺TOP',
        'rising': '上升榜',
        'falling': '下降榜',
        'new_entries': '新上榜',
    }

    for cat_key, cat_name in cat_map.items():
        cat_data = data[cat_key]
        print(f"\n处理 {cat_name}...")

        # 2. 类目统计
        shop_types = cat_data.get('shop_types', {})
        trends = cat_data.get('trends', {})
        conc = cat_data.get('concentration', {})
        c.execute('''INSERT INTO market_category_stats
            (run_id, category, shop_tmall, shop_taobao,
             trend_flat, trend_up, trend_down, trend_out, trend_new,
             concentration_top10, concentration_top50, total_buyers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (run_id, cat_name,
             shop_types.get('天猫', 0), shop_types.get('淘宝', 0),
             trends.get('持平', 0), trends.get('上升', 0), trends.get('下降', 0),
             trends.get('跌出榜', 0), trends.get('新上榜', 0),
             conc.get('top10'), conc.get('top50'), conc.get('total')))

        # 3. 商品榜单
        for list_key, list_type in list_type_map.items():
            items = cat_data.get(list_key, [])
            for i, item in enumerate(items):
                if list_key in ('top_buyers', 'top_visitors'):
                    # [title, shop, value, rank]
                    title = item[0] if len(item) > 0 else ''
                    shop = item[1] if len(item) > 1 else ''
                    value = item[2] if len(item) > 2 else None
                    rank = item[3] if len(item) > 3 else (i + 1)
                    if list_key == 'top_buyers':
                        c.execute('''INSERT INTO market_products
                            (run_id, category, list_type, rank, title, shop, buyers)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (run_id, cat_name, list_type, rank, title, shop, value))
                    else:
                        c.execute('''INSERT INTO market_products
                            (run_id, category, list_type, rank, title, shop, visitors)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (run_id, cat_name, list_type, rank, title, shop, value))
                elif list_key == 'top_shops':
                    # [shop_name, ...]
                    shop = item[0] if isinstance(item, list) and item else str(item)
                    c.execute('''INSERT INTO market_products
                        (run_id, category, list_type, rank, shop)
                        VALUES (?, ?, ?, ?, ?)''',
                        (run_id, cat_name, list_type, i + 1, shop))
                elif list_key in ('rising', 'falling', 'new_entries'):
                    # [rank, title, shop, buyers, ?, buyers] or similar
                    rank = item[0] if len(item) > 0 else (i + 1)
                    title = item[1] if len(item) > 1 else ''
                    shop = item[2] if len(item) > 2 else ''
                    buyers = item[3] if len(item) > 3 else None
                    c.execute('''INSERT INTO market_products
                        (run_id, category, list_type, rank, title, shop, buyers)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (run_id, cat_name, list_type, rank, title, shop, buyers))

        # 4. 关键词
        for kw_type, kw_key in [('搜索词', 'keywords'), ('标题词', 'title_keywords')]:
            kws = cat_data.get(kw_key, [])
            for i, kw in enumerate(kws):
                keyword = kw[0] if isinstance(kw, list) and kw else str(kw)
                count = kw[1] if isinstance(kw, list) and len(kw) > 1 else 0
                c.execute('''INSERT INTO market_keywords
                    (run_id, category, keyword_type, keyword, count, rank)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (run_id, cat_name, kw_type, keyword, count, i + 1))

    # 5. 重叠店铺
    overlap = data.get('overlap_shops', [])
    for shop in overlap:
        c.execute('''INSERT INTO market_overlap_shops (run_id, shop_name) VALUES (?, ?)''',
            (run_id, shop))

    if commit:
        conn.commit()

    # 统计
    c.execute('SELECT COUNT(*) FROM market_products WHERE run_id=?', (run_id,))
    print(f"\n导入完成: 商品榜单 {c.fetchone()[0]} 条")
    c.execute('SELECT COUNT(*) FROM market_keywords WHERE run_id=?', (run_id,))
    print(f"关键词 {c.fetchone()[0]} 条")
    c.execute('SELECT COUNT(*) FROM market_overlap_shops WHERE run_id=?', (run_id,))
    print(f"重叠店铺 {c.fetchone()[0]} 个")
    c.execute('SELECT COUNT(*) FROM market_category_stats WHERE run_id=?', (run_id,))
    print(f"类目统计 {c.fetchone()[0]} 条")

def preview_data(path):
    with open(path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)
    summary = {}
    for category in ('mid', 'long'):
        section = data.get(category) or {}
        summary[category] = {
            'products': sum(len(section.get(key) or []) for key in (
                'top_buyers', 'top_visitors', 'top_shops', 'rising', 'falling', 'new_entries')),
            'keywords': sum(len(section.get(key) or []) for key in ('keywords', 'title_keywords')),
        }
    summary['overlap_shops'] = len(data.get('overlap_shops') or [])
    return summary


def main(argv=None):
    global JSON_PATH
    parser = argparse.ArgumentParser(description='Import market ranking JSON safely.')
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--json', dest='json_path', default=JSON_PATH)
    parser.add_argument('--apply', action='store_true', help='Persist tables and ranking rows.')
    parser.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path.')
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    if not os.path.isfile(args.json_path):
        raise SystemExit(f'JSON does not exist: {args.json_path}')

    summary = preview_data(args.json_path)
    if not args.apply:
        print(json.dumps({'mode': 'dry-run', 'database': os.path.abspath(args.db),
                          'json': os.path.abspath(args.json_path), 'summary': summary},
                         ensure_ascii=False, indent=2))
        return 0

    from scripts.backup_database import backup_database

    backup = backup_database(args.db, args.backup_destination)
    if not backup['ok']:
        raise RuntimeError('database backup integrity check failed')
    conn = sqlite3.connect(args.db)
    try:
        JSON_PATH = args.json_path
        create_tables(conn, commit=False)
        import_data(conn, commit=False)
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError('database integrity check failed before commit')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(json.dumps({'mode': 'apply', 'database': os.path.abspath(args.db),
                      'json': os.path.abspath(args.json_path), 'backup': backup,
                      'summary': summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
