"""等待人工完成淘宝系登录（滑块/验证码），然后自动跑完剩余的重采任务。

用法：
    TMALL_CDP_PORT=9223 python scripts/wait_login_then_collect.py

背景：
- 生意参谋与万相台共用淘宝登录态，自动登录能填账密但过不了滑块，
  必须人工在采集专用 Chrome 里拖一次。
- 登录态会写入持久化 profile，之后日常自动采集可复用。
- 本脚本先把账密提交后等待人工介入，检测到登录成功后自动续跑采集，
  省去人工确认一轮。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))
PYTHON = os.environ.get('TMALL_COLLECT_PYTHON', r'E:\www\tmall-dashboard\.venv\Scripts\python.exe')
COLLECTORS = os.environ.get('TMALL_COLLECTORS_DIR', r'E:\www\BI采集\collectors')
DB_PATH = os.environ.get('TMALL_DB_PATH', r'E:\www\tmall-dashboard\data\dashboard.db')
WAIT_SECONDS = int(os.environ.get('TMALL_LOGIN_WAIT_SECONDS', '900'))


def tabs():
    with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json', timeout=5) as resp:
        return json.loads(resp.read().decode())


def wxt_logged_in():
    """万相台标签页离开 /login 即视为淘宝登录态已建立。"""
    for t in tabs():
        if t.get('type') == 'page' and 'one.alimama.com' in t.get('url', ''):
            return 'login' not in t.get('url', '')
    return False


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def run(script, *args):
    cmd = [PYTHON, os.path.join(COLLECTORS, script), *args]
    log('执行: ' + ' '.join(cmd))
    env = dict(os.environ, TMALL_CDP_PORT=str(CDP_PORT), TMALL_DB_PATH=DB_PATH)
    return subprocess.run(cmd, cwd=COLLECTORS, env=env).returncode


def main():
    log(f'等待人工完成淘宝登录，最多 {WAIT_SECONDS} 秒...')
    log('请在采集专用 Chrome（9223）里完成滑块/验证码')
    deadline = time.time() + WAIT_SECONDS
    ok = False
    while time.time() < deadline:
        if wxt_logged_in():
            log('检测到万相台已登录')
            ok = True
            break
        time.sleep(3)
    if not ok:
        log('等待超时，未检测到登录成功，跳过后续采集')
        return 1

    results = []

    log('--- 1/3 万相台补采 9-18 ~ 9-19 ---')
    results.append(('万相台补采', run('collect_wanxiangtai_dims_v4.py',
                                      '--start', '2026-09-18', '--end', '2026-09-19')))

    log('--- 2/3 单品流量重采 9-18（MAX_ITEMS=200）---')
    env_backup = os.environ.get('TMALL_ITEM_MAX_ITEMS')
    os.environ['TMALL_ITEM_MAX_ITEMS'] = '200'
    results.append(('单品流量 9-18', run('collect_sycm_item_flow_v6.py', '2026-09-18')))

    log('--- 3/3 单品流量重采 9-17 ---')
    results.append(('单品流量 9-17', run('collect_sycm_item_flow_v6.py', '2026-09-17')))
    if env_backup is None:
        os.environ.pop('TMALL_ITEM_MAX_ITEMS', None)
    else:
        os.environ['TMALL_ITEM_MAX_ITEMS'] = env_backup

    log('=== 汇总 ===')
    for name, code in results:
        log(f'  {name}: {"成功" if code == 0 else f"失败(退出码 {code})"}')
    return 0 if all(c == 0 for _, c in results) else 1


if __name__ == '__main__':
    sys.exit(main())
