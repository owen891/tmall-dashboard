"""分析 sycm_item_flow_source_daily 的 page_id 层级结构。

目的：确认「第一次访问来源(farthest)」这批数据里的 page_id 是否携带点分路径，
      从而可以零成本重建层级树（不必依赖 belong=all 批次或浏览器重采）。
"""
import sqlite3
from collections import defaultdict

DB = r"E:\www\tmall-dashboard\data\dashboard.db"


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    print("=" * 72)
    print("1) 按 belong / level 统计行数")
    print("=" * 72)
    for r in c.execute("""SELECT belong, level, COUNT(*) AS n,
                                 COUNT(DISTINCT page_id) AS pages
                          FROM sycm_item_flow_source_daily
                          GROUP BY belong, level ORDER BY belong, level"""):
        print("  belong=%-9s level=%-4s rows=%-6s distinct_page_id=%s" % r)

    print()
    print("=" * 72)
    print("2) page_id 形态分布（是否点分路径）")
    print("=" * 72)
    for r in c.execute("""SELECT belong,
                                 CASE WHEN page_id IS NULL OR page_id='' THEN 'EMPTY'
                                      ELSE CAST(LENGTH(page_id) - LENGTH(REPLACE(page_id,'.','')) + 1 AS TEXT) END AS segs,
                                 COUNT(*) AS n
                          FROM sycm_item_flow_source_daily
                          GROUP BY belong, segs ORDER BY belong, segs"""):
        print("  belong=%-9s page_id段数=%-5s rows=%s" % r)

    print()
    print("=" * 72)
    print("3) page_id 段数 与 level 的关系（farthest）")
    print("=" * 72)
    for r in c.execute("""SELECT CASE WHEN page_id IS NULL OR page_id='' THEN -1
                                      ELSE LENGTH(page_id) - LENGTH(REPLACE(page_id,'.','')) + 1 END AS segs,
                                 level, COUNT(*) AS n
                          FROM sycm_item_flow_source_daily
                          WHERE belong='farthest'
                          GROUP BY segs, level ORDER BY segs, level"""):
        print("  段数=%-4s level=%-4s rows=%s" % r)

    print()
    print("=" * 72)
    print("4) page_id -> 渠道名 字典覆盖度（前缀父节点能否找到名字）")
    print("=" * 72)
    name_of = defaultdict(set)
    for pid, name in c.execute("""SELECT page_id, channel_name FROM sycm_item_flow_source_daily
                                  WHERE page_id IS NOT NULL AND page_id <> ''"""):
        name_of[pid].add(name)

    all_ids = set(name_of)
    prefixes = set()
    for pid in all_ids:
        parts = pid.split('.')
        for i in range(1, len(parts)):
            prefixes.add('.'.join(parts[:i]))
    missing = sorted(p for p in prefixes if p not in name_of)
    print("  已知 page_id 节点数: %d" % len(all_ids))
    print("  作为父节点出现的 page_id 数: %d" % len(prefixes))
    print("  其中查不到名字的: %d" % len(missing))
    if missing:
        print("  缺失清单(前 40): %s" % missing[:40])

    print()
    print("  父节点名字样例（id -> 名称，可能一名多值）:")
    shown = 0
    for pid in sorted(prefixes):
        if pid in name_of and shown < 25:
            print("    %-22s -> %s" % (pid, '/'.join(sorted(name_of[pid]))))
            shown += 1

    print()
    print("=" * 72)
    print("5) 两批数据口径对照：同一 page_id 的名称为否一致")
    print("=" * 72)
    for r in c.execute("""SELECT page_id,
                                 COUNT(DISTINCT channel_name) AS names,
                                 GROUP_CONCAT(DISTINCT belong) AS belongs
                          FROM sycm_item_flow_source_daily
                          WHERE page_id IS NOT NULL AND page_id <> ''
                          GROUP BY page_id
                          HAVING names > 1 ORDER BY names DESC LIMIT 15"""):
        print("  page_id=%-16s 名称数=%s belongs=%s" % r)

    print()
    print("=" * 72)
    print("6) 逐日层级覆盖（farthest 口径下的真实最大深度）")
    print("=" * 72)
    for r in c.execute("""SELECT stat_date,
                                 MAX(LENGTH(page_id) - LENGTH(REPLACE(page_id,'.','')) + 1) AS max_segs,
                                 COUNT(DISTINCT page_id) AS pages,
                                 COUNT(*) AS rows
                          FROM sycm_item_flow_source_daily
                          WHERE belong='farthest'
                          GROUP BY stat_date ORDER BY stat_date"""):
        print("  %s  max_page_id段数=%-4s 渠道数=%-5s rows=%s" % r)

    conn.close()


if __name__ == '__main__':
    main()
