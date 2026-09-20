"""清理万相台 grain='account' 账户总账脏行。

背景：collect_wanxiangtai_dims_v4.py 在个别日期会额外写入一行 channel='全部'、
campaign_id 为空的账户总账（grain='account'），其口径与当日的 campaign/product
明细不一致（疑似多日累计或全周期口径），导致该日花费虚高数倍。

本脚本：归档 -> 删除 -> 校验。
用法：
    python scripts/fix_wanxiangtai_account_rows.py --dry-run   # 只看不动
    python scripts/fix_wanxiangtai_account_rows.py             # 实际清理
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.environ.get(
    "TMALL_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dashboard.db"),
)
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "fix_backups")

# 正常日全店花费量级（用于校验清理后是否回到合理区间）
SANE_MIN, SANE_MAX = 20000.0, 80000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="只处理指定日期，默认全部")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sql = "SELECT rowid, * FROM promotion_daily_facts WHERE grain='account'"
    params: tuple = ()
    if args.date:
        sql += " AND date=?"
        params = (args.date,)
    sql += " ORDER BY date"
    rows = [dict(r) for r in conn.execute(sql, params)]

    if not rows:
        print("未发现 grain='account' 行，无需处理。")
        return 0

    print("发现 %d 行账户总账(grain='account')：" % len(rows))
    for r in rows:
        print("  %s  花费=%s  支付=%s  曝光=%s  batch=%s"
              % (r["date"], round(r["ad_spend"] or 0, 1), r["attributed_payment_amount"],
                 r["impressions"], (r["source_batch_id"] or "")[:8]))

    if args.dry_run:
        print("\n[dry-run] 未做任何修改。")
        return 0

    # 1) 归档
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(BACKUP_DIR, "wanxiangtai_account_rows_%s.json" % stamp)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    print("\n已归档 -> %s" % out)

    # 2) 数据库整体备份
    bak = DB_PATH + ".bak_" + stamp
    shutil.copy2(DB_PATH, bak)
    print("已备份数据库 -> %s" % bak)

    # 3) 删除
    dates = sorted({r["date"] for r in rows})
    q = "DELETE FROM promotion_daily_facts WHERE grain='account'"
    p: tuple = ()
    if args.date:
        q += " AND date=?"
        p = (args.date,)
    cur = conn.execute(q, p)
    conn.commit()
    print("已删除 %d 行" % cur.rowcount)

    # 4) 校验
    print("\n清理后各日总花费(campaign+product)：")
    for d in dates:
        tot = conn.execute(
            "SELECT round(sum(ad_spend),1) FROM promotion_daily_facts WHERE date=? AND grain IN ('campaign','product')",
            (d,),
        ).fetchone()[0] or 0
        flag = "" if SANE_MIN <= tot <= SANE_MAX else "  <<< 仍偏离合理区间"
        print("  %s  %s%s" % (d, format(tot, ","), flag))

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
