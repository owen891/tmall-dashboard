"""规整 sycm_item_flow_source_daily 里「全程来源(belong=all)」批次的错误父级。

背景：9-16 那批多级渠道数据（belong=all）导入时，部分行的 parent_channel 明显张冠李戴：
  - 一淘 / 淘宝直播 / 芭芭农场 / 天猫榜单 / 百亿补贴 / 88VIP / 逛逛 / 日常营销活动 /
    淘金币 / 天猫APP / 淘宝秒杀频道 / 榜单会场 被挂到了「经营优势」下；
  - 购物车 / 淘口令分享 / 手淘拍立淘 被挂到了「站内沟通 / 站外沟通」下。
这些渠道按生意参谋的店铺渠道树都属于「平台流量」。

判定规则（客观、可复核，不做主观猜测）：
  1) parent_channel = '经营优势' 但 page_id 前缀不是 'reward'  → 父级错误
  2) parent_channel ∈ {'站内沟通','站外沟通'} 但 page_id 前缀不是 '100.1'/'100.2' → 父级错误
  3) 新父级取自店铺渠道树（sycm_flow_source_daily）上溯得到的根层分组；
     店铺树里查不到该渠道名的行保持原样不动。

用法：
    .venv\\Scripts\\python.exe scripts/normalize_item_flow_parents.py --dry-run
    .venv\\Scripts\\python.exe scripts/normalize_item_flow_parents.py --apply
"""
import argparse
import os
import sqlite3

DB = os.environ.get('TMALL_DB_PATH', r'E:\www\tmall-dashboard\data\dashboard.db')

# 参与「多级」的只有 all 口径；farthest 的父级由接口按店铺树实时推导，不写库
TARGET_BELONG = 'all'
SUSPECT_REWARD = '经营优势'
SUSPECT_IO = ('站内沟通', '站外沟通')


def shop_group_map(conn):
    """渠道名 -> 店铺渠道树根层分组名。"""
    parent_of = {}
    for name, parent in conn.execute(
            'SELECT channel_name, IFNULL(parent_channel, "") FROM sycm_flow_source_daily'):
        if name and name not in parent_of:
            parent_of[name] = parent or ''
    cache = {}

    def root_of(name):
        if name in cache:
            return cache[name]
        seen, cur = set(), name
        while True:
            parent = parent_of.get(cur, '')
            if not parent or parent == cur or parent in seen:
                break
            seen.add(parent)
            cur = parent
        cache[name] = cur
        return cur

    return {name: root_of(name) for name in parent_of}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写库（默认只做 dry-run）')
    ap.add_argument('--backup-destination', help='Required with --apply: integrity-checked SQLite backup path')
    args = ap.parse_args()
    if args.apply and not args.backup_destination:
        ap.error('--backup-destination is required with --apply')

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    groups = shop_group_map(conn)

    rows = list(conn.execute(
        '''SELECT id, stat_date, item_id, channel_name, page_id, parent_channel
           FROM sycm_item_flow_source_daily WHERE belong = ?''', (TARGET_BELONG,)))

    fixes = {}
    skipped = {}
    for row in rows:
        parent = (row['parent_channel'] or '').strip()
        page_id = (row['page_id'] or '').strip()
        prefix = page_id.split('.')[0]
        bad = False
        if parent == SUSPECT_REWARD and prefix != 'reward':
            bad = True
        if parent in SUSPECT_IO and prefix not in ('100',):
            bad = True
        if not bad:
            continue
        new_parent = groups.get(row['channel_name'], '')
        if not new_parent:
            # 店铺树里查不到这个名字：若 page_id 本身没有点号（结构上就是根层）且
            # 当前父级属于可疑集合，则去掉父级让它回到根层，而不是保留一个明显错误的父亲。
            if '.' not in page_id and parent in SUSPECT_IO + (SUSPECT_REWARD,):
                new_parent = ''
            else:
                skipped[row['channel_name']] = parent
                continue
        elif new_parent == parent:
            continue
        key = (parent, new_parent, row['channel_name'], prefix)
        fixes.setdefault(key, []).append(row['id'])

    print('belong=%s 共 %d 行；命中需修正 %d 组、%d 行；无法自动修正 %d 个渠道'
          % (TARGET_BELONG, len(rows), len(fixes), sum(len(v) for v in fixes.values()), len(skipped)))
    print()
    for (parent, new_parent, name, prefix), ids in sorted(fixes.items()):
        print('  %-12s -> %-8s  %-16s page_id前缀=%-8s 行数=%s'
              % (parent, new_parent or '(根层)', name, prefix, len(ids)))
    if skipped:
        print('\n  保持原样（店铺树里没有该渠道名）:')
        for name, parent in sorted(skipped.items()):
            print('    %-16s parent=%s' % (name, parent))

    if not args.apply:
        print('\n[dry-run] 未写库。加 --apply 执行。')
        conn.close()
        return 0

    from scripts.backup_database import backup_database

    backup = backup_database(DB, args.backup_destination)
    if not backup['ok']:
        raise RuntimeError('database backup integrity check failed')
    print('\n已备份: %s' % backup['destination'])

    cur = conn.cursor()
    total = 0
    try:
        for (parent, new_parent, name, prefix), ids in fixes.items():
            cur.execute(
                '''UPDATE sycm_item_flow_source_daily
                   SET parent_channel = ?, level = CASE WHEN ? = '' THEN 0 ELSE level END
                   WHERE id IN (%s)''' % ','.join('?' for _ in ids),
                [new_parent, new_parent] + ids)
            total += cur.rowcount
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError('database integrity check failed before commit')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print('已修正 %d 行' % total)
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
