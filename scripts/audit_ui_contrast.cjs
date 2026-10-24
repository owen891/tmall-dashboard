#!/usr/bin/env node
/**
 * 全站色彩对比度审计（WCAG 2.1 AA）—— 一个脚本，三种模式。
 *
 * 用法：
 *   node scripts/audit_ui_contrast.cjs                        # 模式 1：文本静态对比度（浅色 + 桌面）
 *   node scripts/audit_ui_contrast.cjs --theme both           # 浅色 + 深色
 *   node scripts/audit_ui_contrast.cjs --theme both --viewport both   # 全矩阵（4 遍，约 3 分钟）
 *   node scripts/audit_ui_contrast.cjs --states               # 模式 2：交互态（hover/focus/active）文本对比度
 *   node scripts/audit_ui_contrast.cjs --focus                # 模式 3：键盘焦点指示器（2.4.7 + 1.4.11）
 *   node scripts/audit_ui_contrast.cjs --focus --theme dark
 *   node scripts/audit_ui_contrast.cjs --focus --viewport mobile   # 移动端 375×812（触摸尺寸 token 不同）
 *   node scripts/audit_ui_contrast.cjs --focus --tabs 60      # 每页最多 Tab 次数
 *
 * BASE 取 `BASE=` / `TMALL_SMOKE_BASE=` 环境变量，或命令行里第一个 http(s) 开头的参数。
 *
 * ── 三种模式的分工 ──
 *   模式 1  文本静态对比度：页面加载即渲染的文本（含伪元素 content 文本）。
 *           判据：正文（<24px 且非粗体）4.5:1，大字（>=24px 或 >=18.66px 粗体）3:1。
 *           禁用态（[disabled] / .is-muted / [aria-disabled]）单独计数 —— WCAG 1.4.3
 *           明确豁免「非活动用户界面组件」，不算需修。
 *   模式 2  交互态文本对比度：`:hover` / `:focus` / `.active` 这些只在交互时才成立的
 *           渲染态，模式 1 扫不到。用真实鼠标移动 / 聚焦 / 点击后重扫同一套 AA 判据。
 *   模式 3  键盘焦点指示器：模式 1、2 都只审**文本**；「Tab 过去看不看得见焦点环」
 *           属 WCAG 2.4.7（焦点可见）+ 1.4.11（非文本对比 3:1），由本模式负责。
 *           用**真实 Tab 按键**驱动，不是 el.focus() —— `:focus-visible` 是否命中取决于
 *           最近的交互来源，程序化 focus() 对按钮往往只命中 `:focus`，测不到键盘态真实焦点环。
 *
 * ⚠️ 改任何语义色 / token 之后都要跑，**两个主题都要跑** —— 这是 A-2 的回归防线。
 * ⚠️ 模式 3 已知的两个假阳性源（脚本会跳过，不计入需修）：
 *      1. `outline-style: auto`（浏览器自绘环）。Chromium 画的是双色自适应环，
 *         `outlineColor` 只是其中一条描边，拿来算对比度会在深色底上误报 1.3~1.5:1。
 *         像素差实测暗色下为 12.32:1，可见。故 auto 只记存在性。
 *      2. `type=date` 等带内部子字段的控件：Tab 进入后焦点会在 shadow 内部的
 *         年/月/日之间移动，那些瞬间 `:focus` 不匹配（页面 CSS 管不到），由浏览器
 *         自绘分段高亮。只在 `el.matches(':focus')` 为真时判定。
 *
 * 底色是**向上找第一个不透明的 background-color**，所以 tint 背景（brand-tint 等）会被算进去。
 *
 * 2026-10-03 合并说明：原先「焦点指示器」是独立脚本 audit_focus_indicator.cjs，
 * 与本文件重复了页面清单、Playwright 骨架、WCAG 计算核心。现合并为本文件的 --focus 模式，
 * WCAG 计算核心抽成下面的 WCAG_JS / Node 侧助手，**一处改动三模式同时生效**。
 */
const path = require('node:path');
// 两种加载方式都支持：设了 NODE_PATH 时用 playwright-core（quality-gate 的老用法），
// 没设时回退到仓库内的 desktop/node_modules —— 不必再记 NODE_PATH=...
const { gateChromium, assertBase } = require('./gate_browser.cjs');
const gateBrowser = require('./gate_browser.cjs');
const chromium = gateChromium();

const args = process.argv.slice(2);
const getArg = (n, d) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const BASE = process.env.BASE || process.env.TMALL_SMOKE_BASE
  || args.find((a) => a.startsWith('http')) || 'http://127.0.0.1:5000';
assertBase(BASE);
const THEME = getArg('--theme', 'light');
const THEMES = THEME === 'both' ? ['light', 'dark'] : [THEME];
const VIEWPORT = getArg('--viewport', 'desktop');
const VIEWPORTS = VIEWPORT === 'both'
  ? [{ name: 'desktop', width: 1440, height: 900 }, { name: 'mobile', width: 375, height: 812 }]
  : [{ name: VIEWPORT, width: VIEWPORT === 'mobile' ? 375 : 1440, height: VIEWPORT === 'mobile' ? 812 : 900 }];
const STATES_MODE = args.includes('--states');
const FOCUS_MODE = args.includes('--focus');

// Execution failures are not contrast findings, but still invalidate the audit.
const ACTION_TIMEOUT = 5000;
const auditErrors = { static: 0, states: 0, focus: 0 };
function auditError(mode, location, error) {
  auditErrors[mode] += 1;
  process.exitCode = 1;
  console.log('[AUDIT_ERROR] ' + mode + ' ' + JSON.stringify(location) + ' ' + String(error && error.message || error));
}
async function closeOwned(resource, mode, location) {
  if (!resource) return;
  try { await resource.close(); }
  catch (error) { auditError(mode, { ...location, action: 'close' }, error); }
}

const MAX_TABS = Number(getArg('--tabs', '45'));

const PAGES = ['overview', 'products', 'promotion', 'keyword-promotion', 'new-products',
  'market-ranking', 'flow-source', 'rival-analysis', 'lifecycle', 'reviews', 'period-review',
  'data-center', 'analysis', 'category-dashboard', 'component-catalog', 'creative-board',
  'data-collection', 'goals', 'settings', 'product-detail'];
// 只审计随本 checkout 分发的页面（私有页清单不在公开仓库）。
const AUDIT_PAGES = typeof gateBrowser.publicPages === 'function' ? gateBrowser.publicPages(PAGES) : PAGES;

// ─────────────────────────────────────────────────────────────────────────────
// WCAG 计算核心（注入页面的字符串，三个模式共用一份）。改这里三处同时生效。
//
// parse 必须同时认两种语法：
//   - rgb()/rgba()                        —— 普通色值
//   - color(srgb r g b / a)               —— Chromium 对 color-mix() 的计算值就走这个
// 早先只认 rgb() 时，color-mix 出来的底色（如 period-review 的 .pr-metric-card.is-success）
// 解析失败会被 bgOf 当成透明跳过，于是**往上找祖先背景**、按错的底色算对比度。
// ─────────────────────────────────────────────────────────────────────────────
const WCAG_JS = `
  function parse(c) {
    const s = String(c).trim();
    const m = s.match(/rgba?\\(([^)]+)\\)/);
    if (m) {
      const p = m[1].split(/[,\\s\\/]+/).filter(Boolean).map(Number);
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    const cm = s.match(/^color\\(\\s*srgb\\s+([\\d.eE+-]+)\\s+([\\d.eE+-]+)\\s+([\\d.eE+-]+)\\s*(?:\\/\\s*([\\d.eE+-]+)\\s*)?\\)$/);
    if (cm) {
      return { r: Number(cm[1]) * 255, g: Number(cm[2]) * 255, b: Number(cm[3]) * 255, a: cm[4] === undefined ? 1 : Number(cm[4]) };
    }
    return null;
  }
  function lum(c) {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function over(fg, bg) {
    if (fg.a >= 1) return { r: fg.r, g: fg.g, b: fg.b, a: 1 };
    return { r: fg.r*fg.a + bg.r*(1-fg.a), g: fg.g*fg.a + bg.g*(1-fg.a), b: fg.b*fg.a + bg.b*(1-fg.a), a: 1 };
  }
  function bgOf(el) {
    let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a >= 0.99) return c;
      n = n.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  }
  function ratio(a, b) { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); }
  function needFor(fs, bold) { return (fs >= 24 || (bold && fs >= 18.66)) ? 3 : 4.5; }
  function path(el, pseudo) {
    const parts = [];
    let n = el;
    for (let i = 0; i < 4 && n && n !== document.body; i++) {
      const c = typeof n.className === 'string' ? n.className.trim().split(/\\s+/)[0] : '';
      parts.unshift(n.tagName.toLowerCase() + (c ? '.' + c : ''));
      n = n.parentElement;
    }
    return parts.join('>') + (pseudo || '');
  }
`;

// ── 模式 1 的页面内扫描：普通文本节点 + 伪元素文本 ──
const SCRIPT = `(() => {
  ${WCAG_JS}
  const out = [];

  // ── 1) 普通文本节点 ──
  document.querySelectorAll('*').forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || !el.offsetParent) return;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) return;
    const txt = (el.textContent || '').replace(/\\s+/g, ' ').trim();
    if (!txt) return;
    const fg = parse(cs.color); if (!fg) return;
    const bg = bgOf(el);
    const comp = over(fg, bg);
    const fs = Number.parseFloat(cs.fontSize);
    const need = needFor(fs, Number(cs.fontWeight) >= 700);
    const r = ratio(comp, bg);
    if (r >= need) return;
    out.push({
      path: path(el), fs, txt: txt.slice(0, 22),
      ratio: Math.round(r*100)/100, need,
      disabled: !!el.closest('[disabled],.is-muted,[aria-disabled="true"]'),
      color: 'rgb('+Math.round(comp.r)+','+Math.round(comp.g)+','+Math.round(comp.b)+')',
      bg: 'rgb('+Math.round(bg.r)+','+Math.round(bg.g)+','+Math.round(bg.b)+')',
    });
  });

  // ── 2) 伪元素文本（content: '→' 这类 —— 上面的 '*' 扫不到）──
  document.querySelectorAll('*').forEach((el) => {
    ['::before', '::after'].forEach((pseudo) => {
      const ps = getComputedStyle(el, pseudo);
      if (ps.display === 'none' || ps.visibility === 'hidden') return;
      const raw = ps.content;
      if (!raw || raw === 'none' || raw === 'normal') return;
      // content 可能是 counter()/attr()/url()，只保留引号包裹的字面文本
      const m = String(raw).match(/^["'](.*)["']$/);
      if (!m) return;
      const txt = m[1].replace(/\\s+/g, ' ').trim();
      if (!txt) return;
      const fg = parse(ps.color); if (!fg) return;
      const bg = bgOf(el);
      const comp = over(fg, bg);
      const fs = Number.parseFloat(ps.fontSize) || Number.parseFloat(getComputedStyle(el).fontSize);
      const need = needFor(fs, Number(ps.fontWeight) >= 700);
      const r = ratio(comp, bg);
      if (r >= need) return;
      out.push({
        path: path(el, pseudo), fs, txt: txt.slice(0, 22),
        ratio: Math.round(r*100)/100, need,
        disabled: !!el.closest('[disabled],.is-muted,[aria-disabled="true"]'),
        color: 'rgb('+Math.round(comp.r)+','+Math.round(comp.g)+','+Math.round(comp.b)+')',
        bg: 'rgb('+Math.round(bg.r)+','+Math.round(bg.g)+','+Math.round(bg.b)+')',
      });
    });
  });

  return out;
})()`;

// ── 模式 2 的页面内扫描：交互态子树重扫 ──
const STATE_SCAN = `(() => {
  ${WCAG_JS}
  function scan(root, out) {
    const cs = getComputedStyle(root);
    if (!(cs.display === 'none' || cs.visibility === 'hidden') && root.getClientRects().length) {
      const own = [...root.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (own) {
        const txt = (root.textContent || '').replace(/\\s+/g, ' ').trim();
        const fg = parse(cs.color);
        if (txt && fg) {
          const bg = bgOf(root);
          const fs = Number.parseFloat(cs.fontSize);
          const need = needFor(fs, Number(cs.fontWeight) >= 700);
          const comp = over(fg, bg);
          const r = ratio(comp, bg);
          if (r < need) out.push({ path: path(root), txt: txt.slice(0, 22), fs, ratio: Math.round(r*100)/100, need, disabled: !!root.closest('[disabled],.is-muted,[aria-disabled="true"]'), color: 'rgb('+Math.round(comp.r)+','+Math.round(comp.g)+','+Math.round(comp.b)+')', bg: 'rgb('+Math.round(bg.r)+','+Math.round(bg.g)+','+Math.round(bg.b)+')' });
        }
      }
    }
    [...root.children].forEach((child) => scan(child, out));
    return out;
  }
  window.__tmallStateScan = (root) => scan(root, []);
})()`;

// ── 模式 3 的页面内扫描：只取当前焦点元素的样式，对比度在 Node 侧算 ──
const FOCUS_SCAN = `(() => {
  ${WCAG_JS}
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  const cs = getComputedStyle(el);
  const cls = typeof el.className === 'string' ? el.className.trim().split(/\\s+/).filter(Boolean).slice(0, 2).join('.') : '';
  const offset = parseFloat(cs.outlineOffset) || 0;
  // 相邻背景：outline-offset >= 0 时环画在元素盒**外侧**，取父级；< 0（内缩环）取自身。
  const bg = bgOf(offset >= 0 ? (el.parentElement || el) : el);
  return {
    tag: el.tagName.toLowerCase(),
    cls,
    text: (el.getAttribute('aria-label') || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 20),
    focusVisible: el.matches(':focus-visible'),
    // type=date 这类带内部子字段的控件，Tab 进去后 Chromium 会在 shadow 内部的
    // 年/月/日/日历按钮之间移动焦点。那些瞬间 activeElement 仍是本元素，但
    // :focus / :focus-visible 都不匹配 —— 此时是浏览器自己在画分段高亮，页面 CSS
    // 管不到也不该管。用 focusMatch 把这些瞬间区分出来，避免误报「无焦点指示器」。
    focusMatch: el.matches(':focus'),
    outlineWidth: parseFloat(cs.outlineWidth) || 0,
    outlineStyle: cs.outlineStyle,
    outlineColor: cs.outlineColor,
    outlineOffset: offset,
    boxShadow: cs.boxShadow,
    bg: [Math.round(bg.r), Math.round(bg.g), Math.round(bg.b)],
  };
})()`;

// ── Node 侧 WCAG 助手（模式 3 用；模式 1/2 在页面内算）──
const parseColor = (c) => {
  const s = String(c).trim();
  const m = s.match(/rgba?\(([^)]+)\)/);
  if (m) {
    const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
    return { rgb: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 };
  }
  const cm = s.match(/^color\(\s*srgb\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*(?:\/\s*([\d.eE+-]+)\s*)?\)$/);
  if (cm) {
    return {
      rgb: [Number(cm[1]) * 255, Number(cm[2]) * 255, Number(cm[3]) * 255].map((v) => Math.round(v)),
      a: cm[4] === undefined ? 1 : Number(cm[4]),
    };
  }
  return null;
};
const lum = ([r, g, b]) => {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
const over = (fg, bg) => fg.rgb.map((v, i) => Math.round(v * fg.a + bg[i] * (1 - fg.a)));

// [页面或 '*'（全站）, 选择器, 状态集]。选择器只写「能看到的那一层」：
// 行 hover 测 tr 子树（td 的颜色变化会被子树扫描捕获）。
const STATE_PROBES = [
  ['*', '.ui-button:not([disabled])', ['hover', 'focus']],
  ['*', '.ui-button--primary:not([disabled])', ['hover']],
  ['*', '.ui-data-table tbody tr', ['hover']],
  ['*', '.demo-nav__item', ['hover']],
  ['*', '.segmented button', ['hover']],
  ['*', '.input:not([disabled])', ['focus']],
  ['*', '.select:not([disabled])', ['focus']],
  ['rival-analysis', '.rival-tab', ['hover', 'active']],
  ['rival-analysis', '.rival-entry-card, .rival-item-card', ['hover']],
  ['flow-source', '.flow-table tbody tr', ['hover']],
  ['market-ranking', '.market-mode-tabs button', ['hover', 'active']],
  ['market-ranking', '.market-entity-row', ['hover']],
  ['market-ranking', '.market-workbench-tabs button', ['hover', 'active']],
  ['products', '.product-table tbody tr', ['hover']],
  ['period-review', '.leaf-board__row', ['hover']],
  ['period-review', '.pr-history__item', ['hover']],
  ['lifecycle', '.lifecycle-card', ['hover']],
];

// ───────────────────────── 模式 1：文本静态对比度 ─────────────────────────
(async () => {
  if (STATES_MODE || FOCUS_MODE) return;
  let browser;
  try {
  browser = await chromium.launch({ headless: true });
  let grandFail = 0;

  for (const vp of VIEWPORTS) {
    for (const theme of THEMES) {
      console.log(`\n################ 主题 ${theme} / 视口 ${vp.name} ${vp.width}×${vp.height} ################`);
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const agg = new Map();
      let fail = 0, disabledN = 0, total = 0;
      try {
      ctx.setDefaultTimeout(ACTION_TIMEOUT);
      // 页面主题来自 localStorage['tmall-demo-theme']（shell.js:213-221），newContext 不设它就永远是浅色
      await ctx.addInitScript((t) => {
        try { window.localStorage.setItem('tmall-demo-theme', t); } catch (e) {}
      }, theme);


      for (const name of AUDIT_PAGES) {
        let page;
        let action = 'new-page';
        let rows = [];
        try {
          page = await ctx.newPage();
          page.setDefaultTimeout(ACTION_TIMEOUT);
          action = 'goto';
          await page.goto(`${BASE}/pages/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
          await page.waitForTimeout(1700);
          action = 'evaluate';
          const actual = await page.evaluate(() => document.documentElement.dataset.theme);
          if (actual !== theme) console.log(`${name} ⚠️ 主题未生效（实际 ${actual}）`);
          rows = await page.evaluate(SCRIPT);
        } catch (error) { auditError('static', { theme, viewport: vp.name, page: name, action }, error); }
        finally { await closeOwned(page, 'static', { theme, page: name, resource: 'page' }); }
        const bad = rows.filter((r) => !r.disabled);
        total += rows.length; fail += bad.length; disabledN += rows.length - bad.length;
        if (rows.length) console.log(`${name.padEnd(18)} 未过 AA ${String(rows.length).padStart(3)}（其中禁用态 ${rows.length - bad.length}）`);
        bad.slice(0, 6).forEach((r) => console.log(`    - ${r.path}  ${r.fs}px ${r.ratio}:1(需${r.need}) ${r.color} on ${r.bg}  "${r.txt}"`));
        bad.forEach((r) => { const k = `${r.path} | ${r.fs}px | ${r.ratio}:1 | ${r.color}`; agg.set(k, (agg.get(k) || 0) + 1); });
      }
      } finally { await closeOwned(ctx, 'static', { theme, viewport: vp.name, resource: 'context' }); }
      grandFail += fail;
      console.log(`\n[${theme}/${vp.name}] 合计未过 AA ${total}（禁用态 ${disabledN}，需修 ${fail}）`);
      if (agg.size) {
        console.log(`[${theme}/${vp.name}] 按 路径/字号/对比度/色值 汇总（仅需修）:`);
        [...agg.entries()].sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${String(v).padStart(4)}  ${k}`));
      }
    }
  }


  console.log(`\n===== 全部组合合计需修 ${grandFail} =====`);
  if (grandFail > 0) process.exitCode = 1;
  } catch (error) { auditError('static', { action: 'mode-setup-or-summary' }, error); }
  finally {
    await closeOwned(browser, 'static', { resource: 'browser' });
    console.log('[AUDIT_EXECUTION] static errors=' + auditErrors.static);
  }
})();

// ───────────────────────── 模式 2：交互态文本对比度 ─────────────────────────
(async () => {
  if (!STATES_MODE) return;
  let browser;
  try {
  browser = await chromium.launch({ headless: true });
  let grandFail = 0;
  for (const theme of THEMES) {
    console.log(`\n################ 交互态 ${theme}（桌面 1440×900） ################`);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const agg = new Map();
    let checked = 0, fail = 0;
    try {
    ctx.setDefaultTimeout(ACTION_TIMEOUT);
    await ctx.addInitScript((t) => { try { window.localStorage.setItem('tmall-demo-theme', t); } catch (e) {} }, theme);
    await ctx.addInitScript(STATE_SCAN);

    for (const name of AUDIT_PAGES) {
      let page;
      let action = 'new-page';
      try {
        page = await ctx.newPage();
        page.setDefaultTimeout(ACTION_TIMEOUT);
        action = 'goto';
        await page.goto(`${BASE}/pages/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await page.waitForTimeout(1500);
        for (const [scope, selector, states] of STATE_PROBES) {
          if (scope !== '*' && scope !== name) continue;
          const firstSel = selector.split(',')[0].trim();
          for (const state of states) {
            action = selector + ' @' + state;
            let handle = null;
            const count = await page.locator(selector).count();
            for (let i = 0; i < Math.min(count, 15); i++) {
              const candidate = page.locator(selector).nth(i);
              if (await candidate.isVisible()) { handle = candidate; break; }
            }
            if (!handle) continue;
            let rows = [];
            if (state === 'hover') {
              await handle.hover({ timeout: ACTION_TIMEOUT });
              await page.waitForTimeout(120);
              rows = await handle.evaluate((el) => window.__tmallStateScan(el));
            } else if (state === 'focus') {
              await handle.focus({ timeout: ACTION_TIMEOUT });
              await page.waitForTimeout(80);
              rows = await handle.evaluate((el) => window.__tmallStateScan(el));
              await page.evaluate(() => { const a = document.activeElement; if (a && a.blur) a.blur(); });
            } else if (state === 'active') {
              await handle.click({ timeout: ACTION_TIMEOUT });
              await page.waitForTimeout(350);
              rows = await page.evaluate((sel) => {
                const el = document.querySelector(sel + '.is-active') || document.querySelector(sel + '.active');
                return el ? window.__tmallStateScan(el) : [];
              }, firstSel);
            }
            checked += 1;
            const bad = rows.filter((r) => !r.disabled);
            if (bad.length) {
              fail += bad.length;
              bad.slice(0, 4).forEach((r) => console.log(`  ✗ ${name} ${firstSel} @${state}  ${r.path} ${r.fs}px ${r.ratio}:1(需${r.need}) ${r.color} on ${r.bg} "${r.txt}"`));
              bad.forEach((r) => { const k = `[${theme}] ${r.path} | ${r.fs}px | ${r.ratio}:1 | @${state}`; agg.set(k, (agg.get(k) || 0) + 1); });
            }
            await page.mouse.move(3, 3);
          }
        }
      } catch (error) { auditError('states', { theme, viewport: 'desktop', page: name, action }, error); }
      finally { await closeOwned(page, 'states', { theme, page: name, resource: 'page' }); }
    }
    } finally { await closeOwned(ctx, 'states', { theme, viewport: 'desktop', resource: 'context' }); }
    grandFail += fail;
    console.log(`\n[${theme}] 交互态探针组合 ${checked}，需修 ${fail}`);
    if (agg.size) {
      console.log(`[${theme}] 按 路径/字号/对比度/状态 汇总（仅需修）:`);
      [...agg.entries()].sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${String(v).padStart(4)}  ${k}`));
    }
  }

  console.log(`\n===== 交互态合计需修 ${grandFail} =====`);
  if (grandFail > 0) process.exitCode = 1;
  } catch (error) { auditError('states', { action: 'mode-setup-or-summary' }, error); }
  finally {
    await closeOwned(browser, 'states', { resource: 'browser' });
    console.log('[AUDIT_EXECUTION] states errors=' + auditErrors.states);
  }
})();

// ───────────────────────── 模式 3：键盘焦点指示器 ─────────────────────────
(async () => {
  if (!FOCUS_MODE) return;
  let browser;
  try {
  browser = await chromium.launch({ headless: true });
  let grandFail = 0;

  // 视口 × 主题 组合。用扁平列表而不是嵌套循环，避免给整个块再缩进一层。
  const combos = [];
  for (const vp of VIEWPORTS) for (const theme of THEMES) combos.push({ vp, theme });

  for (const { vp, theme } of combos) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    try {
    ctx.setDefaultTimeout(ACTION_TIMEOUT);
    await ctx.addInitScript((t) => { try { window.localStorage.setItem('tmall-demo-theme', t); } catch (e) {} }, theme);

    console.log(`\n######## 焦点指示器审计  主题=${theme} / 视口 ${vp.name} ${vp.width}×${vp.height}  每页最多 ${MAX_TABS} 次 Tab ########\n`);

    const agg = new Map();        // 对比度不足
    const noIndicator = new Map();// 完全没有指示器
    const unparsed = new Map();   // 色值解析不了（脚本盲区）
    let checked = 0, internalFocus = 0, uaAuto = 0;

    for (const name of AUDIT_PAGES) {
      let page;
      let action = 'new-page';
      const seen = new Set();
      try {
        page = await ctx.newPage();
        page.setDefaultTimeout(ACTION_TIMEOUT);
        action = 'goto';
        await page.goto(`${BASE}/pages/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await page.waitForTimeout(2200);
        // 先动一下鼠标把输入模态切到指针；Tab 本身属键盘态，:focus-visible 照常命中。
        // 用 move 而不是 click：移动不激活任何元素，移动端不会误点到吸底操作栏 / 汉堡按钮。
        await page.mouse.move(vp.width - 12, vp.height - 12);

        for (let i = 0; i < MAX_TABS; i++) {
          action = 'Tab/evaluate #' + i;
          await page.keyboard.press('Tab');
          const info = await page.evaluate(FOCUS_SCAN);
          if (!info) continue;
          if (!info.focusMatch) { internalFocus += 1; continue; }
          const sig = `${info.tag}${info.cls ? '.' + info.cls : ''}|${info.outlineWidth}px ${info.outlineStyle} ${info.outlineColor}|${info.outlineOffset}|${info.boxShadow.slice(0, 40)}`;
          if (seen.has(sig)) continue;
          seen.add(sig);
          checked += 1;

          const hasOutline = info.outlineStyle !== 'none' && info.outlineWidth > 0;
          const shadowColor = parseColor(info.boxShadow);
          const hasShadow = Boolean(shadowColor && shadowColor.a > 0 && info.boxShadow !== 'none');
          const label = `${info.tag}${info.cls ? '.' + info.cls : ''}`;
          const sample = `"${info.text}"`;

          if (!hasOutline && !hasShadow) {
            if (!noIndicator.has(label)) noIndicator.set(label, { pages: new Set(), sample });
            noIndicator.get(label).pages.add(name);
            continue;
          }
          // outline-style: auto —— 浏览器自绘的自适应焦点环。Chromium 画的是**双色环**
          // （深色描边 + 一条与背景反色的描边），`outlineColor` 只反映其中一条，
          // 拿它算对比度会在深色底上得出「1.3~1.5:1」的假阳性。
          // 2026-10-03 用「聚焦/失焦同区域像素差」验证过：暗色下 .rival-tab 的 auto 环
          // 实际最大对比度 12.32:1（纯白环 vs rgb(41,52,81)），完全可见。
          // 故 auto 只记存在性，不参与对比度判定。
          if (hasOutline && info.outlineStyle === 'auto') { uaAuto += 1; continue; }
          if (!hasOutline) continue; // 纯 box-shadow 环：颜色可解析性差，暂只做存在性判断

          const fg = parseColor(info.outlineColor);
          if (!fg) {
            // 解析不了就显式报出来 —— 不能让一个没见过的色值语法把整个审计变成假绿。
            const k = `${label} | outline ${info.outlineWidth}px ${info.outlineColor}`;
            if (!unparsed.has(k)) unparsed.set(k, { pages: new Set(), sample });
            unparsed.get(k).pages.add(name);
            continue;
          }
          if (fg.a === 0) continue;
          const ring = over(fg, info.bg);
          const r = ratio(ring, info.bg);
          if (r >= 3) continue;

          const k = `${label} | outline ${info.outlineWidth}px ${info.outlineColor} | offset ${info.outlineOffset}`;
          if (!agg.has(k)) agg.set(k, { count: 0, worst: r, pages: new Set(), sample, ring, bg: info.bg, fv: info.focusVisible });
          const e = agg.get(k);
          e.count += 1;
          e.worst = Math.min(e.worst, r);
          e.pages.add(name);
        }
      } catch (error) { auditError('focus', { theme, viewport: vp.name, page: name, action }, error); }
      finally { await closeOwned(page, 'focus', { theme, page: name, resource: 'page' }); }
    }

    console.log(`共检查 ${checked} 个去重后的焦点态（另有 ${internalFocus} 次落在控件内部子字段的瞬时态、${uaAuto} 次为浏览器自绘 auto 环，均已跳过）\n`);

    if (noIndicator.size) {
      console.log(`── 缺焦点指示器（WCAG 2.4.7）${noIndicator.size} 类 ──`);
      [...noIndicator.entries()].forEach(([k, v]) => {
        console.log(`  ✗ ${k}  出现于 ${v.pages.size} 页  ${v.sample}`);
      });
      console.log('');
    }

    if (unparsed.size) {
      console.log(`── ⚠ 焦点环色值无法解析（脚本盲区，需人工确认）${unparsed.size} 类 ──`);
      [...unparsed.entries()].forEach(([k, v]) => console.log(`  ? ${k}  出现于 ${v.pages.size} 页  ${v.sample}`));
      console.log('');
    }

    if (agg.size) {
      console.log(`── 焦点环对比度 < 3:1（WCAG 1.4.11）${agg.size} 类 ──`);
      [...agg.entries()].sort((a, b) => a[1].worst - b[1].worst).forEach(([k, v]) => {
        console.log(`  ✗ ${v.worst.toFixed(2)}:1  ${k}`);
        console.log(`        环渲染色 rgb(${v.ring.join(',')}) on 背景 rgb(${v.bg.join(',')})  出现于 ${v.pages.size} 页  ${v.sample}`);
      });
      console.log('');
    }


    const bad = agg.size + noIndicator.size + unparsed.size;
    grandFail += bad;
    console.log(`==== 需修 ${bad} 类（缺指示器 ${noIndicator.size} + 对比度不足 ${agg.size} + 未解析 ${unparsed.size}） ====`);
    } finally { await closeOwned(ctx, 'focus', { theme, viewport: vp.name, resource: 'context' }); }
  }


  if (grandFail > 0) process.exitCode = 1;
  } catch (error) { auditError('focus', { action: 'mode-setup-or-summary' }, error); }
  finally {
    await closeOwned(browser, 'focus', { resource: 'browser' });
    console.log('[AUDIT_EXECUTION] focus errors=' + auditErrors.focus);
  }
})();
