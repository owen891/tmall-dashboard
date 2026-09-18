"""
C4: 从 daily_data 按 shop_id+date 聚合，补 store_daily_facts。

daily_data 是商品粒度（每个商品每天一行），聚合到店铺日粒度：
  payment_amount             <- SUM(payment_amount)
  successful_refund_amount    <- SUM(refund_amount)
  product_visitors            <- SUM(ipv)
  payment_buyers              <- SUM(buyers)
  returning_payment_buyers    <- SUM(returning_payment_buyers)
  ad_spend                    <- SUM(ad_spend)
"""
import sqlite3
from datetime import datetime

DB = r'E:\www\tmall-dashboard\data\dashboard.db'
SHOP_ID = '3828498662'

con = sqlite3.connect(DB)
cur = con.cursor()

# 先看现状
before = cur.execute("SELECT COUNT(*) FROM store_daily_facts WHERE shop_id=?", (SHOP_ID,)).fetchone()[0]
print(f"聚合前 store_daily_facts {SHOP_ID} 行数: {before}")

# 聚合
cur.execute("""
    INSERT INTO store_daily_facts
        (shop_id, date, payment_amount, successful_refund_amount,
         product_visitors, payment_buyers, returning_payment_buyers,
         ad_spend, source_batch_id)
    SELECT
        ?,
        date,
        ROUND(SUM(COALESCE(payment_amount, 0)), 2),
        ROUND(SUM(COALESCE(refund_amount, 0)), 2),
        SUM(COALESCE(ipv, 0)),
        SUM(COALESCE(buyers, 0)),
        SUM(COALESCE(returning_payment_buyers, 0)),
        ROUND(SUM(COALESCE(ad_spend, 0)), 2),
        'aggregated_from_daily_data'
    FROM daily_data
    WHERE shop_id = ?
    GROUP BY date
    ON CONFLICT(shop_id, date) DO UPDATE SET
        payment_amount = excluded.payment_amount,
        successful_refund_amount = excluded.successful_refund_amount,
        product_visitors = excluded.product_visitors,
        payment_buyers = excluded.payment_buyers,
        returning_payment_buyers = excluded.returning_payment_buyers,
        ad_spend = excluded.ad_spend,
        source_batch_id = excluded.source_batch_id
""", (SHOP_ID, SHOP_ID))

con.commit()

after = cur.execute("SELECT COUNT(*) FROM store_daily_facts WHERE shop_id=?", (SHOP_ID,)).fetchone()[0]
print(f"聚合后 store_daily_facts {SHOP_ID} 行数: {after}")

# 验证最近 5 天
print("\n最近 5 天:")
for r in cur.execute("""SELECT date, payment_amount, successful_refund_amount,
                               product_visitors, payment_buyers, ad_spend
                        FROM store_daily_facts
                        WHERE shop_id=? ORDER BY date DESC LIMIT 5""", (SHOP_ID,)):
    print(r)

# 验证付费成交占比能不能算了
print("\n最近 30 天汇总:")
row = cur.execute("""SELECT SUM(payment_amount), SUM(ad_spend)
                     FROM store_daily_facts
                     WHERE shop_id=? AND date >= date('now', '-30 days')""", (SHOP_ID,)).fetchone()
print(f"店铺总支付: {row[0]:.2f}, 店铺总推广花费: {row[1]:.2f}")

con.close()
print("\nC4 完成")
