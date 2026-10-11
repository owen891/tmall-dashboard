#!/usr/bin/env node
/**
 * 时间选择器浏览器冒烟门禁（零依赖，直接驱动 Chrome DevTools Protocol）。
 *
 * 用法：
 *   node scripts/smoke_date_picker.cjs                          # 默认 http://127.0.0.1:5000
 *   node scripts/smoke_date_picker.cjs http://127.0.0.1:8770    # 指定服务地址
 *   TMALL_CHROME="C:\\path\\chrome.exe" node scripts/smoke_date_picker.cjs
 *
 * 为什么需要它：
 *   静态 CSS 门禁（scripts/check_css_syntax.py）只能证明语法合法，**证明不了元素可见可点**。
 *   真实事故：弹窗因浮层样式被 CSS 解析错误吞掉，以 position:static 渲染在文档流底部
 *   （top: 2432px，视口高 800px），页面表现是「点了没反应」。
 *   此时 console 无报错、异常捕获为空、单测全绿 —— 只有真实浏览器点击才能发现。
 *
 * 判据（每条都是事故的实际症状）：
 *   1. 点击 日/周/月/年 必须出现对应标题的弹窗
 *   2. 弹窗必须在视口内，且中心点命中测试落在弹窗内部（不被遮挡）
 *   3. 弹窗 position 必须是 fixed/absolute，不能是 static
 *   4. 点击粒度后，该粒度按钮必须高亮，且同一时刻只有一处高亮
 *   5. 点击自定义必须出现含起止输入与应用按钮的弹窗
 *   6. 全程不得出现未捕获异常
 *
 * 退出码：0 全部通过；1 存在失败。
 */
'use strict';

const { spawn } = require('node:child_process');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const BASE = (process.argv[2] || process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:5000').replace(/\/$/, '');
const PAGE = process.env.TMALL_SMOKE_PAGE || '/overview';
const DEBUG_PORT = Number(process.env.TMALL_CDP_PORT || 9411);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findChrome() {
  const candidates = [
    process.env.TMALL_CHROME,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(os.homedir(), 'AppData', 'Local', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ].filter(Boolean);
  return candidates.find((candidate) => {
    try { return fs.statSync(candidate).isFile(); } catch { return false; }
  }) || null;
}

function httpGet(pathname) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port: DEBUG_PORT, path: pathname }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

async function main() {
  const chromePath = findChrome();
  if (!chromePath) {
    console.error('[SKIP] 未找到 Chrome，无法运行浏览器冒烟门禁。');
    console.error('       设置 TMALL_CHROME 环境变量指向 chrome.exe 后重试。');
    return 0;
  }

  const profileDir = path.join(os.tmpdir(), `tmall-smoke-picker-${process.pid}`);
  const chrome = spawn(chromePath, [
    `--remote-debugging-port=${DEBUG_PORT}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1440,900',
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: 'ignore' });

  let socketUrl = null;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const targets = JSON.parse(await httpGet('/json/list'));
      const page = targets.find((target) => target.type === 'page');
      if (page && page.webSocketDebuggerUrl) { socketUrl = page.webSocketDebuggerUrl; break; }
    } catch { /* chrome 尚未就绪，继续重试 */ }
    await sleep(250);
  }
  if (!socketUrl) {
    console.error('[FAIL] 无法连接 Chrome DevTools Protocol。');
    chrome.kill();
    return 1;
  }

  const socket = new WebSocket(socketUrl);
  let messageId = 0;
  const pending = new Map();
  const exceptions = [];

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
    }
    if (message.method === 'Runtime.exceptionThrown') {
      const details = message.params.exceptionDetails || {};
      exceptions.push(details.exception?.description?.split('\n')[0] || details.text || 'unknown');
    }
  });

  const send = (method, params = {}) => new Promise((resolve) => {
    const id = ++messageId;
    pending.set(id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
  });

  await new Promise((resolve) => socket.addEventListener('open', resolve, { once: true }));
  await send('Runtime.enable');
  await send('Page.enable');

  const evaluate = async (expression) => {
    const response = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (response.result?.exceptionDetails) {
      throw new Error(response.result.exceptionDetails.exception?.description || 'evaluate failed');
    }
    return response.result?.result?.value;
  };

  const failures = [];
  const check = (condition, label, detail) => {
    if (condition) {
      console.log(`  [ok] ${label}`);
    } else {
      console.log(`  [FAIL] ${label}${detail ? ` -> ${detail}` : ''}`);
      failures.push(label);
    }
  };

  try {
    await send('Page.navigate', { url: `${BASE}${PAGE}` });
    await sleep(3500);

    const ready = await evaluate(`Boolean(window.TmallDateRange && window.TmallDateRange.getState().startDate)`);
    check(ready, '日期范围状态仓已就绪');
    if (!ready) throw new Error('date range store not ready');

    const grains = [
      { key: 'daily', title: '选择日期' },
      { key: 'weekly', title: '选择周' },
      { key: 'monthly', title: '选择月份' },
      { key: 'yearly', title: '选择年份' },
    ];

    for (const grain of grains) {
      console.log(`\n== 粒度：${grain.key} ==`);
      const result = await evaluate(`(async () => {
        const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
        const button = document.querySelector('[data-inline-grain="${grain.key}"]');
        if (!button) return { error: 'grain button missing' };
        button.click();
        await sleep(500);
        const picker = document.querySelector('.demo-picker');
        if (!picker) return { error: 'picker not opened' };
        // 浮层定位可能由 TmallUI.popover 外层（.ui-popover，fixed）或旧的
        // .demo-picker__backdrop 承担；两者都必须是浮层定位，否则会退回文档流。
        // 用「最近的可定位祖先」判定，避免把普通 static 容器误判为浮层。
        let overlay = picker;
        while (overlay && overlay !== document.body) {
          const pos = getComputedStyle(overlay).position;
          if (pos === 'fixed' || pos === 'absolute') break;
          overlay = overlay.parentElement;
        }
        const overlayPosition = overlay && overlay !== document.body ? getComputedStyle(overlay).position : 'static';
        const rect = picker.getBoundingClientRect();
        const cx = Math.round(rect.left + rect.width / 2);
        const cy = Math.round(rect.top + rect.height / 2);
        const hit = document.elementFromPoint(cx, cy);
        const actives = [...document.querySelectorAll('.demo-period__inline button.is-active')]
          .map((b) => b.textContent.trim());
        // 锚定校验：浮层必须贴着被点击的粒度按钮，而不是退化到视口角落。
        // 真实事故：锚点元素被 hidden 后 rect 全为 0，浮层贴到了左上角，
        // 而"在视口内 / 可命中"这些断言当时仍然全部通过。
        const anchorBtn = document.querySelector('[data-inline-grain="${grain.key}"]');
        const ar = anchorBtn ? anchorBtn.getBoundingClientRect() : null;
        const anchoredBelow = Boolean(ar) && Math.abs(rect.left - ar.left) <= 24 && rect.top >= ar.bottom - 4;
        return {
          title: picker.querySelector('.demo-picker__header strong')?.textContent || '',
          backdropPosition: overlayPosition,
          usesPopoverPrimitive: Boolean(picker.closest('.ui-popover')),
          top: Math.round(rect.top),
          left: Math.round(rect.left),
          anchorLeft: ar ? Math.round(ar.left) : null,
          anchorBottom: ar ? Math.round(ar.bottom) : null,
          anchoredBelow,
          height: Math.round(rect.height),
          viewportHeight: window.innerHeight,
          inViewport: rect.top >= 0 && rect.top < window.innerHeight && rect.height > 0,
          hitInside: Boolean(hit && picker.contains(hit)),
          actives,
        };
      })()`);

      if (result?.error) {
        check(false, `${grain.key}: 打开弹窗`, result.error);
        continue;
      }
      check(result.title === grain.title, `${grain.key}: 弹窗标题为「${grain.title}」`, result.title);
      check(result.backdropPosition === 'fixed', `${grain.key}: 浮层容器为 fixed 定位`, `position=${result.backdropPosition}`);
      check(result.usesPopoverPrimitive, `${grain.key}: 走 TmallUI.popover 原语`);
      check(result.anchoredBelow, `${grain.key}: 浮层锚定在被点击按钮下方`,
        `panelLeft=${result.left} anchorLeft=${result.anchorLeft} panelTop=${result.top} anchorBottom=${result.anchorBottom}`);
      check(result.inViewport, `${grain.key}: 弹窗在视口内`, `top=${result.top} 视口高=${result.viewportHeight}`);
      check(result.hitInside, `${grain.key}: 弹窗中心可命中（未被遮挡）`);
      check(result.actives.length === 1 && result.actives[0] === grainLabel(grain.key),
        `${grain.key}: 仅该粒度高亮`, `实际高亮=[${result.actives.join(',')}]`);

      await evaluate(`document.querySelector('.demo-picker__close')?.click(), 1`);
      await sleep(200);
    }

    console.log('\n== 自定义 ==');
    const custom = await evaluate(`(async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      document.querySelector('[data-inline-custom]')?.click();
      await sleep(500);
      const picker = document.querySelector('.demo-picker');
      if (!picker) return { error: 'custom picker not opened' };
      const rect = picker.getBoundingClientRect();
      return {
        title: picker.querySelector('.demo-picker__header strong')?.textContent || '',
        hasStart: Boolean(picker.querySelector('[data-picker-start]')),
        hasEnd: Boolean(picker.querySelector('[data-picker-end]')),
        hasApply: Boolean(picker.querySelector('[data-picker-action="custom-apply"]')),
        hasCancel: Boolean(picker.querySelector('[data-picker-action="close"]')),
        inViewport: rect.top >= 0 && rect.top < window.innerHeight,
      };
    })()`);
    if (custom?.error) {
      check(false, 'custom: 打开弹窗', custom.error);
    } else {
      check(custom.title === '自定义日期范围', 'custom: 弹窗标题正确', custom.title);
      check(custom.hasStart && custom.hasEnd, 'custom: 含起止日期输入');
      check(custom.hasApply && custom.hasCancel, 'custom: 含应用与取消');
      check(custom.inViewport, 'custom: 弹窗在视口内');
    }

    check(exceptions.length === 0, '全程无未捕获异常', exceptions.slice(0, 3).join(' | '));

    // ===== 选中即生效 =====
    // 为什么必须有这一段：此前的门禁只验证「弹窗打开」，于是漏掉了一个真实 bug ——
    // 月份格子的点击处理器引用了 render() 作用域里的局部变量，点月份抛
    // ReferenceError: year is not defined，选「3月」却静默停在当前月。
    // 点击"成功"、弹窗"打开"、高亮"正确"，但状态没变。只有断言"选完必须变"才能拦住。
    console.log('\n== 选中即生效 ==');
    const applyCases = [
      {
        label: '月',
        open: `document.querySelector('[data-inline-grain="monthly"]').click()`,
        pick: `document.querySelector('[data-picker-month="2"]')`,   // 3 月
        expect: (before) => {
          const year = before.endDate.slice(0, 4);
          return { startDate: `${year}-03-01`, endDate: `${year}-03-31`, dim: 'monthly' };
        },
      },
      {
        label: '年',
        open: `document.querySelector('[data-inline-grain="yearly"]').click()`,
        pick: `document.querySelector('[data-picker-year="2025"]')`,
        expect: () => ({ startDate: '2025-01-01', endDate: '2025-12-31', dim: 'yearly' }),
      },
    ];

    for (const item of applyCases) {
      const outcome = await evaluate(`(async () => {
        const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
        const before = window.TmallDateRange.getState();
        ${item.open};
        await sleep(450);
        const target = ${item.pick};
        if (!target) return { error: '找不到待点击的格子' };
        target.click();
        await sleep(450);
        const after = window.TmallDateRange.getState();
        return { before: { startDate: before.startDate, endDate: before.endDate, dim: before.dim }, after: { startDate: after.startDate, endDate: after.endDate, dim: after.dim } };
      })()`);
      if (outcome?.error) {
        check(false, `${item.label}: 点击后生效`, outcome.error);
        continue;
      }
      const want = item.expect(outcome.before);
      const changed = outcome.before.startDate !== outcome.after.startDate || outcome.before.endDate !== outcome.after.endDate;
      check(changed, `${item.label}: 点击后日期范围必须变化`, `before=${outcome.before.startDate}~${outcome.before.endDate} after=${outcome.after.startDate}~${outcome.after.endDate}`);
      check(
        outcome.after.startDate === want.startDate && outcome.after.endDate === want.endDate && outcome.after.dim === want.dim,
        `${item.label}: 落到期望范围 ${want.startDate}~${want.endDate} [${want.dim}]`,
        `实际 ${outcome.after.startDate}~${outcome.after.endDate} [${outcome.after.dim}]`,
      );
    }

    // 初始状态必须是合法日期，不能是 NaN（空数据源时曾出现 NaN-NaN-NaN）
    const initialValid = await evaluate(`(() => {
      const s = window.TmallDateRange.getState();
      return /^\\d{4}-\\d{2}-\\d{2}$/.test(s.startDate || '') && /^\\d{4}-\\d{2}-\\d{2}$/.test(s.endDate || '');
    })()`);
    check(initialValid, '日期范围始终是合法 ISO 日期（非 NaN）');
  } catch (error) {
    failures.push(`运行异常: ${error.message}`);
    console.error('[FAIL]', error.message);
  } finally {
    socket.close();
    chrome.kill();
    await sleep(300);
  }

  console.log('');
  if (failures.length) {
    console.log(`[FAIL] 时间选择器冒烟门禁未通过，共 ${failures.length} 项：`);
    failures.forEach((item) => console.log(`  - ${item}`));
    return 1;
  }
  console.log('[OK] 时间选择器冒烟门禁通过：弹窗可见可点、高亮唯一、无异常。');
  return 0;
}

function grainLabel(key) {
  return { daily: '日', weekly: '周', monthly: '月', yearly: '年' }[key] || key;
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error('[FAIL]', error);
  process.exit(1);
});
