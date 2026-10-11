#!/usr/bin/env node
/**
 * 浮层原语（TmallUI.popover）浏览器门禁。
 *
 * 为什么单独测这个原语：
 *   本仓库此前的浮层都是页面自己写定位，真实事故是浮层退回 static 渲染到文档流底部
 *   （top 2211px / 视口 800px），页面表现为「点了没反应」，而 console 无报错、单测全绿。
 *   把定位收进原语后，必须验证原语本身真的把浮层放在了视口内，否则等于没修。
 *
 * 判据：
 *   1. 打开后浮层为 fixed 定位，且被挂到 body（不被祖先裁切）
 *   2. 浮层完整落在视口内
 *   3. 浮层中心可命中（未被遮挡）
 *   4. 紧贴锚点（在锚点下方或上方，水平重叠）
 *   5. 点外部关闭；Esc 关闭；同一时刻只有一个浮层
 *   6. 空间不足时自动翻转，不会溢出视口
 *
 * 用法：node scripts/smoke_popover.cjs [baseUrl]
 */
'use strict';

const { spawn } = require('node:child_process');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const BASE = (process.argv[2] || process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:5000').replace(/\/$/, '');
const PAGE = process.env.TMALL_SMOKE_PAGE || '/component-catalog';
const DEBUG_PORT = Number(process.env.TMALL_CDP_PORT || 9412);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findChrome() {
  const candidates = [
    process.env.TMALL_CHROME,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(os.homedir(), 'AppData', 'Local', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    '/usr/bin/google-chrome', '/usr/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ].filter(Boolean);
  return candidates.find((candidate) => { try { return fs.statSync(candidate).isFile(); } catch { return false; } }) || null;
}

function httpGet(pathname) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: DEBUG_PORT, path: pathname }, (res) => {
      let data = ''; res.on('data', (c) => { data += c; }); res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

async function main() {
  const chromePath = findChrome();
  if (!chromePath) {
    console.error('[SKIP] 未找到 Chrome，跳过浮层原语门禁（设置 TMALL_CHROME 后重试）。');
    return 0;
  }
  const chrome = spawn(chromePath, [
    `--remote-debugging-port=${DEBUG_PORT}`, '--headless=new', '--disable-gpu',
    '--no-first-run', '--no-default-browser-check', '--window-size=1440,900',
    `--user-data-dir=${path.join(os.tmpdir(), `tmall-smoke-popover-${process.pid}`)}`, 'about:blank',
  ], { stdio: 'ignore' });

  let socketUrl = null;
  for (let i = 0; i < 80; i += 1) {
    try {
      const targets = JSON.parse(await httpGet('/json/list'));
      const page = targets.find((t) => t.type === 'page');
      if (page?.webSocketDebuggerUrl) { socketUrl = page.webSocketDebuggerUrl; break; }
    } catch { /* retry */ }
    await sleep(250);
  }
  if (!socketUrl) { console.error('[FAIL] 无法连接 DevTools'); chrome.kill(); return 1; }

  const socket = new WebSocket(socketUrl);
  let messageId = 0;
  const pending = new Map();
  const exceptions = [];
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id); }
    if (message.method === 'Runtime.exceptionThrown') {
      const d = message.params.exceptionDetails || {};
      exceptions.push(d.exception?.description?.split('\n')[0] || d.text || 'unknown');
    }
  });
  const send = (method, params = {}) => new Promise((resolve) => {
    const id = ++messageId; pending.set(id, resolve); socket.send(JSON.stringify({ id, method, params }));
  });
  await new Promise((resolve) => socket.addEventListener('open', resolve, { once: true }));
  await send('Runtime.enable'); await send('Page.enable');
  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'evaluate failed');
    return r.result?.result?.value;
  };

  const failures = [];
  const check = (ok, label, detail) => {
    if (ok) console.log(`  [ok] ${label}`);
    else { console.log(`  [FAIL] ${label}${detail ? ` -> ${detail}` : ''}`); failures.push(label); }
  };

  try {
    await send('Page.navigate', { url: `${BASE}${PAGE}` });
    await sleep(3000);
    const hasPrimitive = await evaluate(`Boolean(window.TmallUI && typeof window.TmallUI.popover === 'function')`);
    check(hasPrimitive, 'TmallUI.popover 已导出');
    if (!hasPrimitive) throw new Error('popover primitive missing');

    console.log('\n== 锚定在页面中部：应显示在锚点下方且完整可见 ==');
    const mid = await evaluate(`(async () => {
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));
      const anchor = document.createElement('button');
      anchor.textContent = '锚点';
      anchor.style.cssText = 'position:fixed;top:200px;left:300px;width:160px;height:36px;z-index:1';
      document.body.append(anchor);
      const content = document.createElement('div');
      content.textContent = '浮层内容';
      content.style.padding = '12px';
      const handle = window.TmallUI.popover({ anchor, content, matchAnchorWidth: true });
      await sleep(120);
      const node = document.querySelector('.ui-popover');
      const panel = node?.querySelector('.ui-popover__panel');
      if (!node || !panel) return { error: 'popover not rendered' };
      const ar = anchor.getBoundingClientRect();
      const pr = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      const hit = document.elementFromPoint(Math.round(pr.left + pr.width / 2), Math.round(pr.top + pr.height / 2));
      return {
        position: style.position,
        parentIsBody: node.parentElement === document.body,
        top: Math.round(pr.top), left: Math.round(pr.left), width: Math.round(pr.width), height: Math.round(pr.height),
        vw: document.documentElement.clientWidth, vh: document.documentElement.clientHeight,
        anchorBottom: Math.round(ar.bottom), anchorLeft: Math.round(ar.left), anchorWidth: Math.round(ar.width),
        minWidth: node.style.minWidth,
        inViewport: pr.top >= 0 && pr.left >= 0 && pr.bottom <= innerHeight + 0.5 && pr.right <= innerWidth + 0.5,
        hitInside: Boolean(hit && node.contains(hit)),
        ariaExpanded: anchor.getAttribute('aria-expanded'),
      };
    })()`);
    if (mid?.error) { check(false, '中部锚定渲染', mid.error); }
    else {
      check(mid.position === 'fixed', '浮层为 fixed 定位', mid.position);
      check(mid.parentIsBody, '浮层挂在 body 上（不被祖先裁切）');
      check(mid.inViewport, '浮层完整落在视口内', `top=${mid.top} left=${mid.left} w=${mid.width} vh=${mid.vh}`);
      check(mid.hitInside, '浮层中心可命中（未被遮挡）');
      check(mid.top >= mid.anchorBottom, '浮层显示在锚点下方', `panelTop=${mid.top} anchorBottom=${mid.anchorBottom}`);
      check(Math.abs(mid.left - mid.anchorLeft) <= 2, '水平对齐锚点', `left=${mid.left} anchorLeft=${mid.anchorLeft}`);
      check(mid.ariaExpanded === 'true', '锚点 aria-expanded=true');
    }

    console.log('\n== 视口底部锚点：应自动翻转且不溢出 ==');
    const bottom = await evaluate(`(async () => {
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));
      document.querySelectorAll('.ui-popover').forEach(n => n.remove());
      const anchor = document.createElement('button');
      anchor.style.cssText = 'position:fixed;bottom:8px;left:600px;width:140px;height:36px;z-index:1';
      document.body.append(anchor);
      const content = document.createElement('div');
      content.style.cssText = 'padding:12px;height:260px';
      window.TmallUI.popover({ anchor, content });
      await sleep(120);
      const node = document.querySelector('.ui-popover');
      const pr = node.getBoundingClientRect();
      return {
        top: Math.round(pr.top), bottom: Math.round(pr.bottom), vh: document.documentElement.clientHeight,
        placement: node.dataset.placement,
        insideViewport: pr.top >= 0 && pr.bottom <= innerHeight + 0.5,
      };
    })()`);
    check(bottom?.insideViewport, '底部锚点时浮层不溢出视口', `top=${bottom?.top} bottom=${bottom?.bottom} vh=${bottom?.vh}`);
    check(bottom?.placement === 'top', '空间不足时翻转到上方', `placement=${bottom?.placement}`);

    console.log('\n== 关闭行为：点外关闭 / Esc / 单例 ==');
    const closeBehavior = await evaluate(`(async () => {
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));
      document.querySelectorAll('.ui-popover').forEach(n => n.remove());
      const mk = (left) => { const b = document.createElement('button'); b.style.cssText = 'position:fixed;top:300px;left:' + left + 'px;width:120px;height:32px;z-index:1'; document.body.append(b); return b; };
      const a1 = mk(200);
      const content = document.createElement('div');
      content.style.padding = '10px';
      const h1 = window.TmallUI.popover({ anchor: a1, content });
      await sleep(100);
      const opened = document.querySelectorAll('.ui-popover').length;
      // 打开第二个：第一个应自动关闭（单例）
      const a2 = mk(500);
      const h2 = window.TmallUI.popover({ anchor: a2, content: content.cloneNode(true) });
      await sleep(100);
      const afterSecond = document.querySelectorAll('.ui-popover').length;
      const firstClosed = !h1.isOpen();
      // 点外部关闭
      document.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
      await sleep(100);
      const afterOutside = document.querySelectorAll('.ui-popover').length;
      // Esc 关闭
      const a3 = mk(700);
      window.TmallUI.popover({ anchor: a3, content: content.cloneNode(true) });
      await sleep(100);
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      await sleep(100);
      const afterEsc = document.querySelectorAll('.ui-popover').length;
      const a3Expanded = a3.getAttribute('aria-expanded');
      document.querySelectorAll('.ui-popover').forEach(n => n.remove());
      return { opened, afterSecond, firstClosed, afterOutside, afterEsc, a3Expanded };
    })()`);
    check(closeBehavior?.opened === 1, '首次打开只有 1 个浮层', String(closeBehavior?.opened));
    check(closeBehavior?.afterSecond === 1 && closeBehavior?.firstClosed, '同时只允许一个浮层（单例）', `count=${closeBehavior?.afterSecond} firstClosed=${closeBehavior?.firstClosed}`);
    check(closeBehavior?.afterOutside === 0, '点击外部关闭', `count=${closeBehavior?.afterOutside}`);
    check(closeBehavior?.afterEsc === 0, 'Esc 关闭', `count=${closeBehavior?.afterEsc}`);
    check(closeBehavior?.a3Expanded === 'false', '关闭后锚点 aria-expanded 复位', String(closeBehavior?.a3Expanded));

    check(exceptions.length === 0, '全程无未捕获异常', exceptions.slice(0, 3).join(' | '));
  } catch (error) {
    failures.push(`运行异常: ${error.message}`);
    console.error('[FAIL]', error.message);
  } finally {
    socket.close(); chrome.kill(); await sleep(300);
  }

  console.log('');
  if (failures.length) {
    console.log(`[FAIL] 浮层原语门禁未通过，共 ${failures.length} 项：`);
    failures.forEach((f) => console.log(`  - ${f}`));
    return 1;
  }
  console.log('[OK] 浮层原语门禁通过：定位正确、视口约束、自动翻转、关闭语义、单例。');
  return 0;
}

main().then((code) => process.exit(code)).catch((error) => { console.error('[FAIL]', error); process.exit(1); });
