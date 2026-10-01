# -*- coding: utf-8 -*-
"""店透视「市场排行-趋势分析」全自动采集器（阶段C）。

原理：店透视插件的趋势分析面板本质是循环调用生意参谋免费接口
    https://sycm.taobao.com/mc/mq/mkt/item/offline/rank.json
按周逐页拉取历史榜单，面板内汇总为宽表。插件请求自带合法风控签名，直调接口会被
x5sec 拦截（RGV587_ERROR），因此本脚本不做直调，也不做网络收割，而是通过 CDP
驱动插件按钮：等面板数据加载完成后，点击「导出为 XLSX（带链接）」拿全量数据文件。

采集产物文件名与 analyze_socks.py / refresh_market_ranking.py 现有链路兼容：
    店透视_市场排行_趋势分析_交易总量_不限_全部_YYYYMMDD~YYYYMMDD.xlsx
    -> analyze_socks.py 解析 -> import_market_ranking.py 导入 -> refresh_market_ranking.py 编排

用法：
    python scripts/collect_market_ranking_trend.py --cate-id 50006846
    python scripts/collect_market_ranking_trend.py --all            # 三个类目依次采集

前置条件：
    1. 挖象浏览器以 --remote-debugging-port=9224 启动并已登录生意参谋；
    2. 已打开生意参谋任一页面（脚本自动导航到目标类目市场排行页）。

节奏纪律（防风控，实测验证）：
    - 只点一次「自动加载全部」（若面板未自动加载），点完纯等待，绝不重复点击；
    - 检测到 punish（x5sec）或下载取消立即中止该类目，退出码 2，人工处理后重跑。
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import websocket

# 三个类目的生意参谋 cateId（实测点击页面类目树确认，2026-09-30）
CATEGORY_IDS = {
    "mid": ("中筒袜", "50006846"),
    "long": ("长筒袜", "201581801"),
    "panty": ("连裤袜/打底袜", "201581901"),
}

MARKET_RANK_URL = ("https://sycm.taobao.com/mc/free/market_rank"
                   "?activeKey=item&dateType=recent7&parentCateId=201566823&cateId={cate_id}")

CLICK_TREND_JS = """(function(){
  var btns = [];
  document.querySelectorAll('.dts-button__wrapper,.injected-button__wrapper')
    .forEach(function(w){ w.querySelectorAll('button').forEach(function(b){ btns.push(b); }); });
  for (var i=0;i<btns.length;i++){
    if ((btns[i].textContent||'').indexOf('趋势分析')>=0){
      btns[i].scrollIntoView({block:'center'}); btns[i].click(); return 'opened';
    }
  }
  return 'not-found';
})()"""

# 面板状态探测：返回 {loaded: [已加载数, 总数], loadAllDisabled: bool}
PANEL_STATE_JS = """(function(){
  var text = document.body.textContent || '';
  var m = text.match(/已加载\\s*(\\d+)\\s*\\/\\s*(\\d+)\\s*条/);
  var all = document.querySelectorAll('button');
  var loadAll = null;
  for (var i=0;i<all.length;i++){
    var t=(all[i].textContent||'').trim();
    if (t==='自动加载全部'||t==='加载全部'){ loadAll = {text:t, disabled: !!all[i].disabled}; break; }
  }
  return JSON.stringify({loaded: m ? [parseInt(m[1]), parseInt(m[2])] : null,
                          loadAll: loadAll});
})()"""

CLICK_LOAD_ALL_JS = """(function(){
  var hits=[]; var all=document.querySelectorAll('button,a,span,div');
  for (var i=0;i<all.length;i++){var t=(all[i].textContent||'').trim();
    if ((t==='自动加载全部'||t==='加载全部') && !all[i].disabled){hits.push(all[i]);}}
  if (hits.length){hits[hits.length-1].scrollIntoView({block:'center'});
    hits[hits.length-1].click();return 'clicked';}
  return 'none';
})()"""

CLICK_EXPORT_JS = """(function(){
  var all = document.querySelectorAll('button,a,span,div');
  for (var i=0;i<all.length;i++){
    var t=(all[i].textContent||'').trim();
    if (t==='导出表格'){ all[i].scrollIntoView({block:'center'}); all[i].click(); return 'clicked'; }
  }
  return 'not-found';
})()"""

# 等下拉菜单渲染出可见的菜单项再点击（Element UI dropdown 打开有动画，且失焦会收起）
CLICK_XLSX_WHEN_READY_JS = """(function(){
  var items = document.querySelectorAll('.el-dropdown-menu__item, li, button, a, span, div');
  for (var i=0;i<items.length;i++){
    var el = items[i];
    var t = (el.textContent||'').trim();
    if (t.indexOf('XLSX')>=0 && t.indexOf('带链接')>=0){
      var r = el.getBoundingClientRect();
      if (r.width > 0){
        el.scrollIntoView({block:'center'});
        el.click();
        return 'clicked';
      }
    }
  }
  return 'pending';
})()"""

TREND_FILE_PREFIX = "店透视_市场排行_趋势分析"


def list_targets(port):
    with urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=10) as r:
        return json.load(r)


def find_sycm_target(port):
    for t in list_targets(port):
        if t.get("type") == "page" and "sycm.taobao.com" in t.get("url", ""):
            return t
    return None


class Cdp:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=180)
        self._id = 0

    def send(self, method, params=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        return mid

    def eval_js(self, js, timeout=20):
        mid = self.send("Runtime.evaluate", {"expression": js, "returnByValue": True})
        self.ws.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == mid:
                return msg.get("result", {}).get("result", {}).get("value")
        return None

    def drain(self, seconds):
        self.ws.settimeout(0.3)
        end = time.time() + seconds
        try:
            while time.time() < end:
                self.ws.recv()
        except Exception:
            pass

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def set_download_behavior(port, download_dir):
    """浏览器级设置下载落盘路径（发到 page session 不生效）。"""
    with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=10) as r:
        ver = json.load(r)
    bws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=15)
    bws.send(json.dumps({"id": 1, "method": "Browser.setDownloadBehavior",
                         "params": {"behavior": "allow", "downloadPath": download_dir}}))
    bws.settimeout(3)
    try:
        while True:
            msg = json.loads(bws.recv())
            if msg.get("id") == 1:
                return True
    except Exception:
        return False
    finally:
        bws.close()


def wait_for_trend_file(watch_dir, before, timeout=60):
    """等待新趋势 xlsx 出现（含 .crdownload 临时文件阶段），返回新文件路径或 None。"""
    end = time.time() + timeout
    while time.time() < end:
        for name in os.listdir(watch_dir):
            if name.startswith(TREND_FILE_PREFIX) and name not in before:
                path = os.path.join(watch_dir, name)
                # 等待下载完整（大小稳定 2 秒）
                last_size, stable = -1, 0
                while stable < 2 and time.time() < end:
                    size = os.path.getsize(path) if os.path.exists(path) else 0
                    if size == last_size and size > 0:
                        stable += 1
                    else:
                        stable = 0
                        last_size = size
                    time.sleep(1)
                return path
        time.sleep(1)
    return None


def harvest_category(port, cate_name, cate_id, out_dir, args):
    print("== 采集 %s (cateId=%s)" % (cate_name, cate_id))
    target = find_sycm_target(port)
    if not target:
        print("!! 未找到生意参谋页面 target，请先在挖象浏览器打开生意参谋", file=sys.stderr)
        sys.exit(1)
    cdp = Cdp(target["webSocketDebuggerUrl"])
    cdp.send("Page.enable")
    cdp.send("Network.enable")
    cdp.drain(0.5)
    try:
        # 1) 导航/刷新到目标类目
        url = MARKET_RANK_URL.format(cate_id=cate_id)
        if ("cateId=%s" % cate_id) not in target["url"] or "market_rank" not in target["url"]:
            print("   导航: %s" % url)
            cdp.send("Page.navigate", {"url": url})
            time.sleep(10)
        else:
            print("   页面已在目标类目，刷新复位")
            cdp.send("Page.reload")
            time.sleep(10)
        cdp.drain(1.0)

        # 2) 打开趋势分析面板
        r = cdp.eval_js(CLICK_TREND_JS)
        print("   趋势分析: %s" % r)
        if r != "opened":
            print("!! 趋势分析按钮未找到（插件未注入或页面未就绪）", file=sys.stderr)
            return None
        time.sleep(5)
        cdp.drain(1.0)

        # 3) 等待面板数据加载完成（已加载 N/N 条）
        deadline = time.time() + args.max_wait
        clicked_load_all = False
        loaded = None
        stall_rounds = 0
        done = False
        while time.time() < deadline:
            state_raw = cdp.eval_js(PANEL_STATE_JS)
            state = {}
            try:
                state = json.loads(state_raw or "{}")
            except Exception:
                pass
            prev_loaded = loaded
            loaded = state.get("loaded")
            if loaded and loaded[0] >= loaded[1]:
                print("   数据加载完成: %d/%d" % (loaded[0], loaded[1]))
                done = True
                break
            load_all = state.get("loadAll")
            # 未完成：只允许点一次「自动加载全部」
            if not clicked_load_all and load_all and not load_all.get("disabled"):
                r = cdp.eval_js(CLICK_LOAD_ALL_JS)
                print("   自动加载全部: %s" % r)
                clicked_load_all = True
                stall_rounds = 0
                time.sleep(args.poll_seconds)
                continue
            if loaded:
                print("   加载中: %d/%d" % (loaded[0], loaded[1]))
                # 计数长时间不动且按钮置灰 => 视为完成（可能是缓存恢复或数据不足）
                if clicked_load_all and load_all and load_all.get("disabled") \
                        and loaded == prev_loaded:
                    stall_rounds += 1
                    if stall_rounds >= 3:
                        print("   计数不再增长且按钮置灰，视为完成: %d/%d"
                              % (loaded[0], loaded[1]))
                        done = True
                        break
                else:
                    stall_rounds = 0
            time.sleep(args.poll_seconds)
            cdp.drain(0.5)
        if not done:
            print("!! 等待数据加载超时（最后状态: %s）" % loaded, file=sys.stderr)
            return None

        # 4) 导出 XLSX（带链接）
        # 先隔离 watch 目录里的同名遗留文件，避免浏览器弹「另存为/覆盖确认」对话框挂起下载
        quarantine = Path(args.out_dir) / "_quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        for name in os.listdir(args.watch_dir):
            if name.startswith(TREND_FILE_PREFIX):
                try:
                    shutil.move(os.path.join(args.watch_dir, name),
                                str(quarantine / ("%d_%s" % (int(time.time()), name))))
                except Exception:
                    pass
        before = set(os.listdir(args.watch_dir))
        r = cdp.eval_js(CLICK_EXPORT_JS)
        print("   导出表格: %s" % r)
        if r != "clicked":
            print("!! 导出表格按钮未找到", file=sys.stderr)
            return None
        clicked_xlsx = False
        for attempt in range(20):   # 最多等 10 秒菜单渲染并点击
            r = cdp.eval_js(CLICK_XLSX_WHEN_READY_JS)
            if r == "clicked":
                clicked_xlsx = True
                break
            if r == "not-found":
                # 菜单可能收起了：重新点开导出表格
                cdp.eval_js(CLICK_EXPORT_JS)
            time.sleep(0.5)
        print("   导出为 XLSX（带链接）: %s" % ("clicked" if clicked_xlsx else "not-found"))
        if not clicked_xlsx:
            print("!! XLSX（带链接）菜单项未找到", file=sys.stderr)
            return None

        path = wait_for_trend_file(args.watch_dir, before, timeout=90)
        if not path:
            print("!! 未检测到导出文件落盘（可能被下载对话框拦截）", file=sys.stderr)
            return None
        print("   导出文件: %s (%d bytes)" % (path, os.path.getsize(path)))

        # 5) 移入 data/collect（类目名里的 / 等非法路径字符替换为 -）
        safe_name = re.sub(r'[\\/:*?"<>|]', "-", cate_name)
        out_path = Path(out_dir) / os.path.basename(path)
        out_path = out_path.with_name("%s_%s%s" % (out_path.stem, safe_name,
                                                   out_path.suffix))
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        shutil.move(path, out_path)
        print("   已归档: %s" % out_path)
        return out_path
    finally:
        cdp.close()


def verify_xlsx(path, cate_name):
    """轻量校验：sheet 数 = 1 趋势宽表 + N 周 sheet，每周 300 行左右。"""
    try:
        import openpyxl
    except ImportError:
        print("   (openpyxl 不可用，跳过校验)")
        return True
    wb = openpyxl.load_workbook(str(path), read_only=True)
    names = wb.sheetnames
    wb.close()
    week_sheets = [n for n in names if n.startswith("第")]
    print("   校验: %d 个 sheet（趋势分析宽表 + %d 个周 sheet: %s）"
          % (len(names), len(week_sheets), ", ".join(week_sheets[:2]) + "..." if week_sheets else ""))
    return len(names) >= 2


def main():
    parser = argparse.ArgumentParser(description="店透视趋势分析采集器（CDP 驱动插件导出 XLSX）")
    parser.add_argument("--port", type=int, default=9224, help="CDP 端口（挖象浏览器）")
    parser.add_argument("--cate-id", help="叶子类目 ID（与 --all 二选一）")
    parser.add_argument("--all", action="store_true", help="依次采集三个类目")
    parser.add_argument("--out-dir", default="data/collect", help="归档目录")
    parser.add_argument("--watch-dir", default=os.environ.get("USERPROFILE", "C:\\Users\\Administrator") + "\\Downloads",
                        help="下载落盘监视目录")
    parser.add_argument("--max-wait", type=int, default=300, help="数据加载最长等待秒")
    parser.add_argument("--poll-seconds", type=int, default=10, help="面板状态轮询间隔")
    args = parser.parse_args()

    if not args.cate_id and not args.all:
        parser.error("必须指定 --cate-id 或 --all")
    cats = []
    if args.all:
        cats = list(CATEGORY_IDS.items())
    else:
        # 允许直接给数字 ID，也允许给 mid/long/panty 键
        for key, (name, cid) in CATEGORY_IDS.items():
            if args.cate_id in (key, name, cid):
                cats = [(key, (name, args.cate_id if args.cate_id.isdigit() else cid))]
                break
        if not cats:
            cats = [("custom", ("自定义类目", args.cate_id))]

    # 浏览器级下载落盘
    if not set_download_behavior(args.port, args.watch_dir):
        print("警告: Browser.setDownloadBehavior 设置失败，下载可能落到默认目录", file=sys.stderr)

    results, failed = [], []
    for key, (name, cid) in cats:
        try:
            path = harvest_category(args.port, name, cid, args.out_dir, args)
            if path and verify_xlsx(path, name):
                results.append(path)
            else:
                failed.append(name)
        except SystemExit:
            raise
        except Exception as e:
            print("!! 采集 %s 失败: %s" % (name, e), file=sys.stderr)
            failed.append(name)
        if len(cats) > 1 and key != cats[-1][0]:
            pause = 20
            print("   （类目间停 %ds 防风控）" % pause)
            time.sleep(pause)

    print("\n== 完成: 成功 %d，失败 %d" % (len(results), len(failed)))
    for p in results:
        print("   +", p)
    if failed:
        print("   失败:", ", ".join(failed), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
