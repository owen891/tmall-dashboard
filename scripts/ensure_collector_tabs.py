"""Ensure the collector browser has the tabs each collector needs.

Opens a background tab for every required target that is not already present.
Read-only with respect to pages: it never navigates an existing tab, so a tab
that is already logged in or mid-work is left untouched.

2026-10-22 变更：匹配从「host 出现过」改成「host+关键路径出现过」。
原因：边界BI 的采集器要求标签页 URL 含 `/workTable/productOverview`。若开机时
BI 处于未登录状态，该标签页会被重定向到 `/login`，之后按 host 判断就一直
「已存在」→ 再也不补，BI 日度永远采不到。改成路径匹配后，下次开机/兜底会
新开一个 productOverview 后台标签（不导航旧标签，用户正在输入的登录页不动）。

同一 host 的标签页数量有上限（MAX_TABS_PER_HOST），避免未登录期间每次开机
都叠一个新标签。

Usage:
    python scripts/ensure_collector_tabs.py [--port 9223] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# (key, host, 需要打开的完整 URL, 判定「已存在」用的 URL 片段)
_BI_HOST = os.environ.get("TMALL_BI_HOST", "")

REQUIRED_TABS = (
    ("sycm", "sycm.taobao.com", "https://sycm.taobao.com/portal/home.htm", "sycm.taobao.com"),
    ("alimama", "one.alimama.com", "https://one.alimama.com/index.html", "one.alimama.com"),
    # BI 租户域名是部署私有配置（公开源码不携带），经 TMALL_BI_HOST 注入。
    *((("bi", _BI_HOST, f"https://{_BI_HOST}/workTable/productOverview", _BI_HOST),) if _BI_HOST else ()),
)

MAX_TABS_PER_HOST = 4


def _http_json(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _connect(ws_url: str, timeout: float = 30.0):
    import websocket  # provided by the collector runtime

    return websocket.create_connection(ws_url, suppress_origin=True, timeout=timeout)


def _call(ws, method: str, params: dict | None = None, session: str | None = None,
          *, call_id: list[int], timeout: float = 30.0):
    call_id[0] += 1
    mid = call_id[0]
    message = {"id": mid, "method": method}
    if params:
        message["params"] = params
    if session:
        message["sessionId"] = session
    ws.send(json.dumps(message))
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = json.loads(ws.recv())
        if payload.get("id") == mid:
            return payload
    raise TimeoutError(f"CDP call timed out: {method}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Open missing collector tabs over CDP")
    parser.add_argument("--port", type=int, default=9223)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--json", action="store_true", help="machine-readable result")
    args = parser.parse_args(argv)

    base = f"http://{args.host}:{args.port}"
    try:
        version = _http_json(f"{base}/json/version")
    except (urllib.error.URLError, OSError) as exc:
        print(json.dumps({"ok": False, "code": "CDP_UNREACHABLE", "error": str(exc)}))
        return 21

    try:
        pages = [t for t in _http_json(f"{base}/json") if t.get("type") == "page"]
    except (urllib.error.URLError, OSError) as exc:
        print(json.dumps({"ok": False, "code": "CDP_LIST_FAILED", "error": str(exc)}))
        return 21

    urls = [str(t.get("url", "")) for t in pages]

    def host_tab_count(host: str) -> int:
        return sum(1 for u in urls if host in u)

    opened: list[str] = []
    existing: list[str] = []
    capped: list[str] = []
    failed: list[dict] = []

    browser_ws = None
    call_id = [0]
    for key, host, url, match in REQUIRED_TABS:
        if any(match in u for u in urls):
            existing.append(key)
            continue
        if host_tab_count(host) >= MAX_TABS_PER_HOST:
            # 该 host 已有太多标签（多半是一直停在登录页），不再叠加
            capped.append(key)
            continue
        try:
            if browser_ws is None:
                browser_ws = _connect(version["webSocketDebuggerUrl"])
            result = _call(browser_ws, "Target.createTarget",
                           {"url": url, "background": True}, call_id=call_id)
            target_id = result.get("result", {}).get("targetId")
            if target_id:
                opened.append(key)
                urls.append(url)
            else:
                failed.append({"key": key, "error": json.dumps(result)[:200]})
        except Exception as exc:  # noqa: BLE001 - report, do not abort the boot
            failed.append({"key": key, "error": str(exc)[:200]})

    if browser_ws is not None:
        try:
            browser_ws.close()
        except Exception:
            pass

    payload = {
        "ok": not failed,
        "browser": version.get("Browser"),
        "existing": existing,
        "opened": opened,
        "capped": capped,
        "failed": failed,
    }
    print(json.dumps(payload, ensure_ascii=not args.json))
    return 0 if not failed else 22


if __name__ == "__main__":
    sys.exit(main())
