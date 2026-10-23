"""批量补采流量数据（店铺流量 + 单品流量）。

用法:
    python scripts/backfill_flow_range.py --start 2026-09-10 --end 2026-09-15
    python scripts/backfill_flow_range.py --start 2026-09-10 --end 2026-09-15 --shop-only
    python scripts/backfill_flow_range.py --start 2026-09-10 --end 2026-09-15 --item-only

说明:
- 直接以子进程方式调用项目内 collectors/ 私有插件目录下的采集器，
  避免依赖 bash 的 sleep/grep（该机器上不可用）。
- 逐天串行执行，失败不中断，最后汇总每天的成功/失败。
- 单品流量每天约 5 分钟（200 商品），店铺流量每天约 20 秒。
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import date, timedelta

COLLECTORS_DIR = os.environ.get(
    'TMALL_COLLECTORS_DIR',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'collectors'))
PROJECT_VENV_PY = r'E:\www\tmall-dashboard\.venv\Scripts\python.exe'
DB_PATH = r'E:\www\tmall-dashboard\data\dashboard.db'


def run_collector(script, args, cdp_port='9223', extra_env=None, timeout=1200):
    env = dict(os.environ)
    env['TMALL_CDP_PORT'] = cdp_port
    env['TMALL_DB_PATH'] = DB_PATH
    env['PYTHONIOENCODING'] = 'utf-8'
    if extra_env:
        env.update(extra_env)
    cmd = [PROJECT_VENV_PY, os.path.join(COLLECTORS_DIR, script)] + list(args)
    try:
        proc = subprocess.run(
            cmd, cwd=COLLECTORS_DIR, env=env, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        out = proc.stdout.decode('utf-8', errors='replace')
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return -1, 'TIMEOUT'
    except Exception as exc:  # noqa: BLE001
        return -2, f'{type(exc).__name__}: {exc}'


def tail(text, n=6):
    lines = [l for l in text.splitlines() if l.strip()]
    return '\n'.join('      ' + l for l in lines[-n:])


def daterange(start, end):
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    d = d0
    while d <= d1:
        yield d.isoformat()
        d += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--cdp-port', default='9223')
    ap.add_argument('--max-items', default='200')
    ap.add_argument('--shop-only', action='store_true')
    ap.add_argument('--item-only', action='store_true')
    a = ap.parse_args()

    days = list(daterange(a.start, a.end))
    print(f'补采区间: {a.start} ~ {a.end}  共 {len(days)} 天')
    results = []

    if not a.item_only:
        print('\n########## 店铺流量 sycm_flow_source_daily ##########')
        for d in days:
            t0 = time.time()
            rc, out = run_collector('collect_sycm_flow.py', [d], a.cdp_port)
            ok = (rc == 0) and ('已保存' in out)
            saved = ''
            for l in out.splitlines():
                if '已保存' in l or '汇总' in l:
                    saved = l.strip()
            print(f'  {d}  rc={rc}  {"OK" if ok else "FAIL"}  {saved}  ({time.time()-t0:.0f}s)')
            if not ok:
                print(tail(out, 8))
            results.append(('shop', d, ok))
            time.sleep(2)

    if not a.shop_only:
        print('\n########## 单品流量 sycm_item_flow_source_daily ##########')
        for d in days:
            t0 = time.time()
            rc, out = run_collector(
                'collect_sycm_item_flow_v6.py', [d], a.cdp_port,
                extra_env={'TMALL_ITEM_MAX_ITEMS': a.max_items},
                timeout=1800,
            )
            ok = (rc == 0) and ('失败' not in out.split('完成')[-1][:200] or '完成' in out)
            summary = ''
            for l in out.splitlines():
                if '完成' in l or '商品' in l and '条' in l:
                    summary = l.strip()
            print(f'  {d}  rc={rc}  {"OK" if rc == 0 else "FAIL"}  {summary[:90]}  ({time.time()-t0:.0f}s)')
            if rc != 0:
                print(tail(out, 10))
            results.append(('item', d, rc == 0))
            time.sleep(3)

    print('\n========== 汇总 ==========')
    for kind in ('shop', 'item'):
        sub = [(d, ok) for k, d, ok in results if k == kind]
        if not sub:
            continue
        bad = [d for d, ok in sub if not ok]
        print(f'  {kind}: {len(sub) - len(bad)}/{len(sub)} 成功' + (f'  失败: {bad}' if bad else ''))


if __name__ == '__main__':
    sys.exit(main())
