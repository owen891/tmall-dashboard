# -*- coding: utf-8 -*-
"""
promotion_daily_facts 存量行 grain 标注 + 清理维度混写污染。

背景：promotion_daily_facts 历史上混存渠道/计划/商品/单元多粒度行，
report 查询按渠道求和时会把不同粒度行加在一起。新增 grain 列后，
本脚本按维度列的填充情况给存量行打标：
    unit_id 非空          -> unit
    campaign_id 非空      -> campaign
    product_id 非空       -> product
    其余                  -> channel

同时清理 dims v3 试验写入的污染：
- paid_detail 里 date_range 为 '起_止' 格式的行（商品表错写计划/创意 ID）。

用法：
    python scripts/migrate_promotion_grain.py            # 预览
    python scripts/migrate_promotion_grain.py --apply    # 执行
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='promotion facts grain 标注迁移')
    parser.add_argument('--apply', action='store_true', help='实际执行（默认仅预览）')
    parser.add_argument('--db-path', default=os.environ.get('TMALL_DB_PATH'), help='数据库路径')
    args = parser.parse_args()

    db_path = args.db_path or db.get_db_path()
    conn = db.get_connection(db_path)
    cur = conn.cursor()

    total = cur.execute('SELECT COUNT(*) FROM promotion_daily_facts').fetchone()[0]
    untagged = cur.execute(
        "SELECT COUNT(*) FROM promotion_daily_facts WHERE grain = ''").fetchone()[0]
    print(f'promotion_daily_facts 总行数: {total}, 未打标: {untagged}')

    preview = cur.execute('''
        SELECT grain, channel, COUNT(*) AS rows,
               ROUND(SUM(spend), 2) AS spend
        FROM (
            SELECT CASE
                     WHEN unit_id != '' THEN 'unit'
                     WHEN campaign_id != '' THEN 'campaign'
                     WHEN product_id != '' THEN 'product'
                     WHEN channel = '全部' THEN 'account'
                     ELSE 'channel'
                   END AS grain,
                   channel,
                   COALESCE(ad_spend, 0) AS spend
            FROM promotion_daily_facts WHERE grain = ''
        )
        GROUP BY grain, channel ORDER BY spend DESC
    ''').fetchall()
    print('\n将打标:')
    for grain, channel, rows, spend in preview:
        print(f'  {grain:9s} {channel:10s} {rows:6d} 行  ¥{spend:,.2f}')

    polluted = cur.execute(
        "SELECT COUNT(*) FROM paid_detail WHERE date_range LIKE '____-__-______-__-__'"
        " OR (date_range LIKE '%_%' AND date_range != substr(date_range, 1, 7))"
    ).fetchone()[0]
    polluted = cur.execute(
        "SELECT COUNT(*) FROM paid_detail WHERE date_range GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
    ).fetchone()[0]
    print(f'\npaid_detail 维度混写污染行: {polluted}')

    if not args.apply:
        print('\n（预览模式，加 --apply 执行）')
        conn.close()
        return 0

    cur.execute('''
        UPDATE promotion_daily_facts SET grain = CASE
                 WHEN unit_id != '' THEN 'unit'
                 WHEN campaign_id != '' THEN 'campaign'
                 WHEN product_id != '' THEN 'product'
                 WHEN channel = '全部' THEN 'account'
                 ELSE 'channel'
               END
        WHERE grain = ''
    ''')
    tagged = cur.rowcount

    cur.execute(
        "DELETE FROM paid_detail WHERE date_range GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
    )
    deleted_paid = cur.rowcount
    conn.commit()

    remaining = cur.execute(
        "SELECT COUNT(*) FROM promotion_daily_facts WHERE grain = ''").fetchone()[0]
    print(f'\n已打标 {tagged} 行，剩余未打标 {remaining} 行')
    print(f'已删除 paid_detail 污染行 {deleted_paid} 行')
    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
