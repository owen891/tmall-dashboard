#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 daily_data 聚合店铺日汇总到 store_daily_facts。
每天采集完原始数据后跑一次，确保 store_daily_facts 不缺天。
"""
import sqlite3, os, sys
from datetime import datetime

DB_PATH = os.environ.get('TMALL_DB_PATH') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'dashboard.db'
)

# 只补最近 N 天，避免全量重算
LOOKBACK_DAYS = 14


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 从 daily_data 聚合
    cur.execute(f"""
        SELECT
            shop_id,
            date,
            ROUND(SUM(payment_amount), 2),
            ROUND(SUM(refund_amount), 2),
            ROUND(SUM(ipv), 0),
            ROUND(SUM(buyers), 0),
            ROUND(SUM(returning_payment_buyers), 0),
            ROUND(SUM(ad_spend), 2)
        FROM daily_data
        WHERE date >= date('now', '-{LOOKBACK_DAYS} days')
        GROUP BY shop_id, date
    """)
    rows = cur.fetchall()

    inserted = 0
    updated = 0
    for shop_id, date, sales, refund, visitors, buyers, returning, ad_spend in rows:
        cur.execute(
            'SELECT rowid FROM store_daily_facts WHERE shop_id=? AND date=?',
            (shop_id, date)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE store_daily_facts SET
                    payment_amount=?, successful_refund_amount=?, product_visitors=?,
                    payment_buyers=?, returning_payment_buyers=?, ad_spend=?
                WHERE shop_id=? AND date=?
            """, (sales, refund or 0, visitors, buyers, returning, ad_spend, shop_id, date))
            updated += 1
        else:
            cur.execute("""
                INSERT INTO store_daily_facts
                    (shop_id, date, payment_amount, successful_refund_amount,
                     product_visitors, payment_buyers, returning_payment_buyers, ad_spend)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (shop_id, date, sales, refund or 0, visitors, buyers, returning, ad_spend))
            inserted += 1

    con.commit()

    # 输出最近几天状态
    cur.execute("""
        SELECT date, payment_amount, product_visitors, payment_buyers, ad_spend
        FROM store_daily_facts ORDER BY date DESC LIMIT 5
    """)
    print(f'[聚合] 插入={inserted}, 更新={updated}')
    for r in cur.fetchall():
        print(f'  {r[0]}  sales={r[1]:>10}  visitors={r[2]:>6}  buyers={r[3]:>5}  ad_spend={r[4]}')

    con.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
