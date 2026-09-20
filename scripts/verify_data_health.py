# -*- coding: utf-8 -*-
"""数据完整性 + 正确性终检报告。

只读，不改任何数据。用法：
    .venv\Scripts\python.exe scripts\verify_data_health.py
"""
import sqlite3
from datetime import datetime, timedelta

DB = r"E:\www\tmall-dashboard\data\dashboard.db"

# 表 -> (日期列, 业务名)
TABLES = [
    ("daily_data", "date", "BI 商品日度"),
    ("sycm_item_flow_source_daily", "stat_date", "单品流量"),
    ("sycm_flow_source_daily", "stat_date", "店铺流量"),
    ("promotion_daily_facts", "date", "万相台推广"),
]

# daily_data 里必须非 0 的核心指标
CORE_METRICS = [
    ("pv", "浏览量"),
    ("uv", "访客数"),
    ("payment_amount", "支付金额"),
    ("refund_amount", "退款金额"),
    ("cart_qty", "加购件数"),
    ("fav_users", "收藏人数"),
    ("ad_spend", "推广花费"),
    ("ad_roi", "推广ROI"),
    ("search_conversion", "搜索转化率"),
]


def days_back(n):
    return [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n, 0, -1)]


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    window = days_back(10)
    lo, hi = window[0], window[-1]

    print("=" * 78)
    print(f"数据健康终检   窗口 {lo} ~ {hi}   (生成于 {datetime.now():%Y-%m-%d %H:%M:%S})")
    print("=" * 78)

    # ---------- 1. 日期覆盖 ----------
    print("\n[1] 日期覆盖（最近 10 天，✓有 ✗缺 △偏少）")
    for table, dcol, label in TABLES:
        rows = {
            r[dcol]: r["c"]
            for r in conn.execute(
                f"SELECT {dcol}, COUNT(*) c FROM {table} "
                f"WHERE {dcol} BETWEEN ? AND ? GROUP BY {dcol}",
                (lo, hi),
            )
        }
        line = []
        for d in window:
            c = rows.get(d, 0)
            line.append(f"{d[5:]} {'✓' if c else '✗'}{c if c < 10000 else str(c // 1000) + 'k'}")
        print(f"  {label:<10} " + "  ".join(line))

    # ---------- 2. BI 日度核心字段 ----------
    print("\n[2] BI 商品日度核心字段（有值行数 / 总行数）")
    total_cols = [r[1] for r in conn.execute("PRAGMA table_info(daily_data)")]
    avail = [c for c, _ in CORE_METRICS if c in total_cols]
    header = f"  {'日期':<12}{'商品数':>7}" + "".join(f"{lbl:>8}" for c, lbl in CORE_METRICS if c in avail)
    print(header)
    for r in conn.execute(
        f"""SELECT date, COUNT(*) tot
            {''.join(f', SUM(CASE WHEN {c}>0 THEN 1 ELSE 0 END) ok_{c}' for c in avail)}
            FROM daily_data WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date""",
        (lo, hi),
    ):
        cells = ""
        for c in avail:
            ok, tot = r[f"ok_{c}"], r["tot"]
            ratio = ok / tot if tot else 0
            mark = "OK" if ratio > 0.5 else ("~" if ok else "0")
            cells += f"{str(ok) + mark:>8}"
        print(f"  {r['date']:<12}{r['tot']:>7}" + cells)

    # ---------- 3. 数据源口径 ----------
    print("\n[3] BI 日度数据源（口径是否统一）")
    for r in conn.execute(
        """SELECT date, data_source, COUNT(*) c FROM daily_data
           WHERE date BETWEEN ? AND ? GROUP BY date, data_source ORDER BY date""",
        (lo, hi),
    ):
        print(f"  {r['date']}  {str(r['data_source'])[:52]:<54} {r['c']:>5} 行")

    # ---------- 4. 单品流量口径 ----------
    print("\n[4] 单品流量口径（belong / level 是否统一）")
    for r in conn.execute(
        """SELECT stat_date, belong, COUNT(*) c, COUNT(DISTINCT item_id) items,
                  ROUND(SUM(uv)) uv, MIN(level) mn, MAX(level) mx
           FROM sycm_item_flow_source_daily WHERE stat_date BETWEEN ? AND ?
           GROUP BY stat_date, belong ORDER BY stat_date""",
        (lo, hi),
    ):
        print(f"  {r['stat_date']}  belong={str(r['belong']):<10} 行{r['c']:>6} "
              f"商品{r['items']:>5}  uv{r['uv'] or 0:>8}  level {r['mn']}~{r['mx']}")

    print("\n  每商品渠道数（偏离均值 >30% 标红）:")
    rows = conn.execute(
        """SELECT stat_date, COUNT(*) c, COUNT(DISTINCT item_id) items
           FROM sycm_item_flow_source_daily WHERE stat_date BETWEEN ? AND ?
           GROUP BY stat_date ORDER BY stat_date""", (lo, hi)
    ).fetchall()
    vals = [r["c"] / r["items"] for r in rows if r["items"]]
    avg = sum(vals) / len(vals) if vals else 0
    for r in rows:
        if not r["items"]:
            continue
        v = r["c"] / r["items"]
        flag = "  <<< 异常" if avg and abs(v - avg) / avg > 0.3 else ""
        print(f"    {r['stat_date']}  {v:>5.1f} 渠道/商品 (均值 {avg:.1f}){flag}")

    # ---------- 5. 万相台异常值 ----------
    print("\n[5] 万相台日花费（偏离相邻日 2 倍以上标红）")
    rows = conn.execute(
        """SELECT date, ROUND(SUM(ad_spend)) s FROM promotion_daily_facts
           WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date""", (lo, hi)
    ).fetchall()
    for i, r in enumerate(rows):
        prev = rows[i - 1]["s"] if i else None
        nxt = rows[i + 1]["s"] if i + 1 < len(rows) else None
        ref = [x for x in (prev, nxt) if x]
        base = sum(ref) / len(ref) if ref else 0
        flag = ""
        if base and r["s"] and (r["s"] > base * 2 or r["s"] < base / 2):
            flag = f"  <<< 异常（相邻均值 {base:,.0f}）"
        print(f"  {r['date']}  {r['s'] or 0:>10,}{flag}")

    # ---------- 6. 僵尸指标 ----------
    print("\n[6] daily_data 中永远为 0 的列（僵尸指标）")
    zombie = []
    cols = [r[1] for r in conn.execute("PRAGMA table_info(daily_data)")]
    for c in cols:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM daily_data WHERE {c} NOT IN (0) AND {c} IS NOT NULL").fetchone()[0]
        except Exception:
            continue
        if n == 0:
            zombie.append(c)
    print(f"  共 {len(zombie)} 列全表无值:")
    for i in range(0, len(zombie), 6):
        print("    " + ", ".join(zombie[i:i + 6]))

    # ---------- 7. 跨日剧烈波动 ----------
    print("\n[7] BI 日度支付金额逐日环比（>±60% 标红，辅助判断）")
    rows = conn.execute(
        """SELECT date, ROUND(SUM(payment_amount)) pay FROM daily_data
           WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date""", (lo, hi)
    ).fetchall()
    for i, r in enumerate(rows):
        if i == 0:
            print(f"  {r['date']}  {r['pay'] or 0:>12,}")
            continue
        prev = rows[i - 1]["pay"] or 0
        cur = r["pay"] or 0
        chg = (cur - prev) / prev if prev else 0
        flag = "  <<< 剧烈波动" if abs(chg) > 0.6 else ""
        print(f"  {r['date']}  {cur:>12,}  {chg * 100:>+7.1f}%{flag}")

    conn.close()
    print("\n" + "=" * 78)
    print("终检结束（本脚本只读，未修改任何数据）")


if __name__ == "__main__":
    main()
