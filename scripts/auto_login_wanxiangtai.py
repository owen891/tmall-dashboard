#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
万相台自动登录脚本（CDP 方式）

流程：
1. 检查 Chrome 调试模式是否运行
2. 打开万相台页面，检查登录态
3. 如未登录，打开淘宝登录页，自动填入账密并提交
4. 遇到滑块验证时提示用户手动完成
5. 登录成功后 cookie 自动保存在 Chrome 用户数据目录中

凭据从环境变量读取：
  WXT_USERNAME  - 万相台/淘宝账号
  WXT_PASSWORD  - 万相台/淘宝密码
"""

import json
import os
import sys
import time
import urllib.request
import websocket

CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9222'))
WXT_URL = 'https://one.alimama.com/'
TAOBAO_LOGIN_URL = 'https://login.taobao.com/member/login.jhtml?redirectURL=https%3A%2F%2Fone.alimama.com%2F&style=mini&newMini2=true'

USERNAME = os.environ.get('WXT_USERNAME', '')
PASSWORD = os.environ.get('WXT_PASSWORD', '')


def get_tabs():
    with urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json', timeout=5) as f:
        return json.loads(f.read())


def get_browser_ws():
    ver = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=5).read())
    return ver['webSocketDebuggerUrl']


def create_tab(url):
    ws = websocket.create_connection(get_browser_ws(), timeout=10)
    ws.send(json.dumps({'id': 1, 'method': 'Target.createTarget', 'params': {'url': url}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == 1:
            target_id = msg.get('result', {}).get('targetId')
            ws.close()
            return target_id


def find_tab(url_contains):
    for t in get_tabs():
        if t.get('type') == 'page' and url_contains in t.get('url', ''):
            return t
    return None


def cdp_eval(ws_url, expression, timeout=15):
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
        'expression': expression, 'returnByValue': True, 'awaitPromise': True
    }}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == 1:
            ws.close()
            return msg.get('result', {}).get('result', {}).get('value')


def check_login():
    """检查万相台是否已登录。返回 True/False。"""
    tab = find_tab('one.alimama.com')
    if not tab:
        print('[登录] 未找到万相台标签页，新开一个...')
        create_tab(WXT_URL)
        time.sleep(5)
        tab = find_tab('one.alimama.com')
        if not tab:
            print('[错误] 无法打开万相台页面')
            return False

    url = tab.get('url', '')
    if 'login' not in url:
        print(f'[登录] 万相台已登录: {url[:60]}')
        return True

    print(f'[登录] 万相台未登录，URL: {url[:60]}')
    return False


def do_login():
    """走淘宝账密登录流程。"""
    if not USERNAME or not PASSWORD:
        print('[错误] 未设置 WXT_USERNAME / WXT_PASSWORD 环境变量')
        return False

    # 打开淘宝登录页
    print('[登录] 打开淘宝登录页...')
    tab = find_tab('login.taobao.com')
    if not tab:
        create_tab(TAOBAO_LOGIN_URL)
        time.sleep(5)
        tab = find_tab('login.taobao.com')
        if not tab:
            print('[错误] 无法打开淘宝登录页')
            return False

    # 填账密
    print('[登录] 填入账密...')
    result = cdp_eval(tab['webSocketDebuggerUrl'], f'''
        (function() {{
            var user = document.getElementById('fm-login-id');
            var pass = document.getElementById('fm-login-password');
            if (!user || !pass) return 'inputs_not_found';
            user.focus(); user.value = {json.dumps(USERNAME)};
            user.dispatchEvent(new Event('input', {{bubbles: true}}));
            pass.focus(); pass.value = {json.dumps(PASSWORD)};
            pass.dispatchEvent(new Event('input', {{bubbles: true}}));
            return 'filled';
        }})()
    ''')
    print(f'  填写: {result}')
    time.sleep(1)

    # 点登录
    result = cdp_eval(tab['webSocketDebuggerUrl'], '''
        (function() {
            var btns = document.querySelectorAll('button, a, input[type=submit]');
            for (var i = 0; i < btns.length; i++) {
                var b = btns[i];
                if (b.offsetParent && b.innerText && b.innerText.trim() === '登录' && b.children.length === 0) {
                    b.click(); return 'clicked';
                }
            }
            return 'no_button';
        })()
    ''')
    print(f'  点击登录: {result}')
    time.sleep(5)

    # 检查是否出现滑块
    result = cdp_eval(tab['webSocketDebuggerUrl'], '''
        (function() {
            var iframes = document.querySelectorAll('iframe');
            for (var i = 0; i < iframes.length; i++) {
                if (iframes[i].src && iframes[i].src.indexOf('punish') >= 0) return 'need_slider';
            }
            return 'no_slider';
        })()
    ''')

    if result == 'need_slider':
        print('\n[需要手动操作] 检测到滑块验证，请在 Chrome 浏览器中手动拖动滑块完成登录。')
        print('[等待] 最多等待 120 秒...')
        for i in range(60):
            time.sleep(2)
            tab = find_tab('one.alimama.com')
            if tab and 'login' not in tab.get('url', ''):
                print(f'\n[登录] 万相台登录成功！({i*2}秒)')
                return True
            tab = find_tab('login.taobao.com')
            if tab:
                # 检查是否还在登录页
                url = tab.get('url', '')
                if 'login' not in url:
                    print(f'\n[登录] 已跳转: {url[:60]}')
                    return True
        print('[超时] 等待滑块完成超时')
        return False

    # 检查登录结果
    time.sleep(3)
    tab = find_tab('one.alimama.com')
    if tab and 'login' not in tab.get('url', ''):
        print(f'[登录] 万相台登录成功')
        return True

    print('[登录] 登录结果未知，仍在登录页')
    return False


def main():
    print('=' * 50)
    print('  万相台自动登录')
    print('=' * 50)

    # 检查 Chrome 调试模式
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{CDP_PORT}/json/version', timeout=3)
        print(f'[1/3] Chrome 调试模式运行中 (端口 {CDP_PORT})')
    except Exception as e:
        print(f'[1/3] Chrome 调试模式未启动: {e}')
        return 1

    # 检查登录态
    print('[2/3] 检查万相台登录态...')
    if check_login():
        print('[3/3] 无需登录，cookie 有效')
        return 0

    # 需要登录
    print('[3/3] 开始自动登录...')
    if do_login():
        print('\n✓ 登录成功，cookie 已保存')
        return 0
    else:
        print('\n✗ 登录失败')
        return 1


if __name__ == '__main__':
    sys.exit(main())
