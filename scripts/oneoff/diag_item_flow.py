"""诊断单品流量来源（sycm_item_flow_source_daily）某个商品的入库数据构成。

用法：
    .venv\\Scripts\\python.exe scripts\\diag_item_flow.py [item_id]

只读，不改数据。主要用来确认：
    - 每天/每个 belong 的层级（level）构成
    - 汇总 uv 是否把父子层级重复累加
"""

import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')
ITEM_ID = sys.argv[1] if len(sys.argv) > 1 else '711021416206'


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print('== 全表 belong / level 构成 ==')
    for row in c.execute(
        '''SELECT belong, level, COUNT(*), COUNT(DISTINCT stat_date), COUNT(DISTINCT item_id), ROUND(SUM(uv), 0)
           FROM sycm_item_flow_source_daily
           GROUP BY belong, level ORDER BY belong, level'''
    ):
        print('  belong=%s level=%s rows=%s dates=%s items=%s uv=%s' % row)

    print('\n== 全表按日期 × belong 的 level 集合 ==')
    for row in c.execute(
        '''SELECT stat_date, belong, GROUP_CONCAT(DISTINCT level) AS levels, COUNT(*) AS rows,
                  ROUND(SUM(uv), 0) AS uv
           FROM sycm_item_flow_source_daily
           GROUP BY stat_date, belong ORDER BY stat_date DESC, belong'''
    ):
        print('  %s | belong=%-9s levels=%-10s rows=%-5s uv=%s' % row)

    print('\n== 商品 %s 按日期 × belong × level ==' % ITEM_ID)
    for row in c.execute(
        '''SELECT stat_date, belong, level, COUNT(*) AS rows, ROUND(SUM(uv), 0) AS uv,
                  ROUND(SUM(pay_amount), 2) AS pay, SUM(pay_buyer_count) AS buyers
           FROM sycm_item_flow_source_daily
           WHERE CAST(item_id AS TEXT) = ?
           GROUP BY stat_date, belong, level ORDER BY stat_date DESC, belong, level''',
        (ITEM_ID,),
    ):
        print('  %s | belong=%-9s level=%-3s rows=%-4s uv=%-7s pay=%-9s buyers=%s' % row)

    print('\n== 商品 %s 最新一天的渠道明细 ==')
    latest = c.execute(
        'SELECT MAX(stat_date) FROM sycm_item_flow_source_daily WHERE CAST(item_id AS TEXT) = ?',
        (ITEM_ID,),
    ).fetchone()[0]
    print('  latest=%s' % latest)
    if latest:
        for row in c.execute(
            '''SELECT belong, level, parent_channel, channel_name, uv, pv, pay_amount, pay_buyer_count
               FROM sycm_item_flow_source_daily
               WHERE CAST(item_id AS TEXT) = ? AND stat_date = ?
               ORDER BY belong, level, uv DESC''',
            (ITEM_ID, latest),
        ):
            print('  %-9s L%s parent=%-12s %-16s uv=%-7s pv=%-7s pay=%-9s buyers=%s'
                  % tuple('-' if v is None else v for v in row))

    print('\n== 商品 %s 按日期汇总对比（全部层级 vs 仅 level=2）==' % ITEM_ID)
    for row in c.execute(
        '''SELECT stat_date,
                  ROUND(SUM(uv), 0) AS uv_all,
                  ROUND(SUM(CASE WHEN level = 2 THEN uv ELSE 0 END), 0) AS uv_l2,
                  SUM(CASE WHEN level = 2 THEN 1 ELSE 0 END) AS rows_l2,
                  COUNT(*) AS rows_all,
                  GROUP_CONCAT(DISTINCT belong) AS belongs
           FROM sycm_item_flow_source_daily
           WHERE CAST(item_id AS TEXT) = ?
           GROUP BY stat_date ORDER BY stat_date DESC''',
        (ITEM_ID,),
    ):
        print('  %s uv_all=%-8s uv_l2=%-8s rows_l2=%-4s rows_all=%-4s belongs=%s' % row)

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
