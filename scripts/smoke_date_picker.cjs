#!/usr/bin/env node
/**
 * 时间选择器浏览器冒烟门禁（零依赖，直接驱动 Chrome DevTools Protocol）。
 *
 * 用法：python scripts/run_quality_gates.py --tier integration
 * 只接受执行器所有的临时服务、专用浏览器与 profile；无默认生产端口。
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

const { launchGateChrome, safeSocketUrl } = require('./gate_browser.cjs');
const BASE = process.argv[2] || process.env.TMALL_SMOKE_BASE;
const PAGE = process.env.TMALL_SMOKE_PAGE || '/overview';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function main() {
  const owned = await launchGateChrome(BASE);
  const httpGet = owned.httpGet;
  try {
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
    await owned.close();
    return 1;
  }

  const socket = new WebSocket(safeSocketUrl(socketUrl, owned.port));
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
        // The shared popover legitimately shifts left at the viewport edge.
        // Require the visible anchor and the exact clamped overlay position,
        // not an arbitrary distance from its unclamped left coordinate.
        const overlayRect = overlay.getBoundingClientRect();
        const expectedLeft = ar ? Math.min(Math.max(8, ar.left), Math.max(8, document.documentElement.clientWidth - overlayRect.width - 8)) : null;
        const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
        const anchorStyle = anchorBtn ? getComputedStyle(anchorBtn) : null;
        const finiteBox = (box) => box && ['left','top','right','bottom','width','height'].every((key) => Number.isFinite(box[key]));
        const inside = (box) => finiteBox(box) && box.width > 0 && box.height > 0 && box.left >= -1 && box.top >= -1 && box.right <= vw + 1 && box.bottom <= vh + 1;
        const anchoredBelow = finiteBox(ar) && ar.width > 0 && ar.height > 0
          && ar.right > 0 && ar.bottom > 0 && ar.left < vw && ar.top < vh
          && anchorStyle.visibility === 'visible' && anchorStyle.display !== 'none' && Number(anchorStyle.opacity) > 0
          && inside(overlayRect) && inside(rect)
          && Math.abs(overlayRect.left - expectedLeft) <= 1
          && overlayRect.top >= ar.bottom - 1 && overlayRect.top <= ar.bottom + 10
          && rect.left >= overlayRect.left && rect.right <= overlayRect.right
          && rect.top >= overlayRect.top && rect.bottom <= overlayRect.bottom;
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
        months: picker.querySelectorAll('.demo-picker__month').length,
        readoutInHeader: Boolean(picker.querySelector('.demo-picker__header .demo-picker__range-readout')),
        navInMonthHead: picker.querySelectorAll('.demo-picker__month-head-row [data-picker-action]').length,
        redundantInputs: picker.querySelectorAll('[data-picker-start], [data-picker-end]').length,
        hasApply: Boolean(picker.querySelector('[data-picker-action="custom-apply"]')),
        hasCancel: Boolean(picker.querySelector('[data-picker-action="close"]')),
        inViewport: rect.top >= 0 && rect.top < window.innerHeight,
      };
    })()`);
    if (custom?.error) {
      check(false, 'custom: 打开弹窗', custom.error);
    } else {
      check(custom.title === '自定义日期范围', 'custom: 弹窗标题正确', custom.title);
      check(custom.months === 2, 'custom: 双月并排日历', `月份面板数=${custom.months}`);
      // 信息密度：同一个区间此前被显示三遍（输入框行 + 独立读数行 + 日历高亮）。
      // 这两条锁住「去冗余」的决定，防止有人把输入行/独立读数行加回来。
      check(custom.readoutInHeader, 'custom: 区间读数只在标题行一处');
      check(custom.redundantInputs === 0, 'custom: 不再有冗余的起止日期输入行', `仍存在 ${custom.redundantInputs} 个输入框`);
      check(custom.navInMonthHead >= 2, 'custom: 翻页按钮并入月份标题行', `${custom.navInMonthHead} 个`);
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

    // 自定义弹窗是双月并排日历：点两下定区间、悬停预览、点「应用」才落库。
    // 这一段必须断言"应用之后范围真的变了"，否则「点得动但没生效」的 bug 会再次溜过去。
    const customOutcome = await evaluate(`(async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const before = window.TmallDateRange.getState();
      document.querySelector('[data-inline-custom]').click();
      await sleep(450);
      const picker = document.querySelector('.demo-picker--custom');
      if (!picker) return { error: '自定义弹窗未打开' };
      const months = picker.querySelectorAll('.demo-picker__month');
      if (months.length !== 2) return { error: '未渲染双月并排日历（月份面板数=' + months.length + '）' };
      const enabled = Array.from(picker.querySelectorAll('[data-picker-date]:not([disabled])'))
        .map((btn) => btn.dataset.pickerDate).sort();
      if (enabled.length < 2) return { error: '可点日期不足（' + enabled.length + ' 个）' };
      const a = enabled[Math.min(4, enabled.length - 1)];
      const b = enabled[Math.min(19, enabled.length - 1)];
      const lo = a <= b ? a : b;
      const hi = a <= b ? b : a;
      const cell = (value) => picker.querySelector('[data-picker-date="' + value + '"]');
      // 闪烁回归门禁：交互期间骨架节点必须原地复用。
      // 改前每点一下/悬停一格都重写 body.innerHTML，原生 <input type="date"> 连同
      // 42 个日期格被销毁重建，浏览器重新挂载控件，视觉上就是「点一下闪一下」。
      const applyProbe = picker.querySelector('[data-picker-action="custom-apply"]');
      if (!applyProbe) return { error: '缺少应用按钮' };
      applyProbe.dataset.smokeProbe = 'stable';
      cell(lo).click();
      await sleep(150);
      // 悬停预览：定好起点后扫过终点，读数应当先变，但全局范围此时必须还没动。
      cell(hi).dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      await sleep(150);
      // 悬停是高频路径：扫过多个格子后节点仍须是同一个，否则就是整块重建。
      const enabledCells = Array.from(picker.querySelectorAll('[data-picker-date]:not([disabled])'));
      enabledCells.slice(0, 6).forEach((btn) => btn.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })));
      await sleep(120);
      const skeletonReused = picker.querySelector('[data-picker-action="custom-apply"]')?.dataset.smokeProbe === 'stable'
        && picker.querySelectorAll('.demo-picker__month').length === 2;
      // 扫完之后把预览重新指回终点，下面读数断言仍按 lo~hi 校验。
      cell(hi).dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      await sleep(120);
      const preview = picker.querySelector('.demo-picker__range-readout')?.textContent?.trim() || '';
      const midState = window.TmallDateRange.getState();
      const leaked = midState.startDate !== before.startDate || midState.endDate !== before.endDate;
      cell(hi).click();
      await sleep(150);
      const applyBtn = picker.querySelector('[data-picker-action="custom-apply"]');
      if (!applyBtn) return { error: '缺少应用按钮' };
      applyBtn.click();
      await sleep(450);
      const after = window.TmallDateRange.getState();
      return {
        before: { startDate: before.startDate, endDate: before.endDate },
        after: { startDate: after.startDate, endDate: after.endDate },
        lo, hi, preview, leaked, skeletonReused,
        stillOpen: Boolean(document.querySelector('.demo-picker--custom')),
      };
    })()`);
    if (customOutcome?.error) {
      check(false, '自定义: 双月日历选区间后应用生效', customOutcome.error);
    } else {
      check(!customOutcome.leaked, '自定义: 点「应用」前不得改动全局范围', `预览期间已变为 ${customOutcome.after.startDate}~${customOutcome.after.endDate}`);
      check(
        customOutcome.skeletonReused,
        '自定义: 悬停/点击原地更新骨架（不重建 DOM，无闪烁）',
        '交互后开始日期输入框被替换或双月面板数量异常，说明整块重写了 innerHTML',
      );
      check(
        customOutcome.preview.includes(customOutcome.lo) && customOutcome.preview.includes(customOutcome.hi),
        '自定义: 悬停预览显示待选区间',
        `读数="${customOutcome.preview}" 期望含 ${customOutcome.lo} 与 ${customOutcome.hi}`,
      );
      check(
        customOutcome.after.startDate === customOutcome.lo && customOutcome.after.endDate === customOutcome.hi,
        `自定义: 应用后落到所选区间 ${customOutcome.lo}~${customOutcome.hi}`,
        `实际 ${customOutcome.after.startDate}~${customOutcome.after.endDate}`,
      );
      check(!customOutcome.stillOpen, '自定义: 应用后弹窗关闭');
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
    await owned.close();
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
  } finally { await owned.close(); }
}

function grainLabel(key) {
  return { daily: '日', weekly: '周', monthly: '月', yearly: '年' }[key] || key;
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error('[FAIL]', error);
  process.exit(1);
});
