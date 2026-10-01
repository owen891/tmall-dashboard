/**
 * 全站「可见文本」对比度审计（WCAG 2.1 AA）。
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules \
 *   PW_CHROMIUM="$HOME/AppData/Local/ms-playwright/chromium-1187/chrome-win/chrome.exe" \
 *   node scripts/audit_ui_contrast.cjs                        # 浅色 + 桌面视口（默认）
 *   node scripts/audit_ui_contrast.cjs --theme both           # 浅色 + 深色
 *   node scripts/audit_ui_contrast.cjs --theme both --viewport both   # 全矩阵（4 遍，约 3 分钟）
 *
 * 判据：正文（<24px 且非粗体）4.5:1，大字（>=24px 或 >=18.66px 粗体）3:1。
 * 结论看最后一行「需修 N」—— 禁用态（[disabled] / .is-muted / [aria-disabled]）单独计数，
 * WCAG 1.4.3 明确豁免「非活动用户界面组件」，不算需修。
 *
 * ⚠️ 只测**文本**。语义色用作图表填充 / 边框时适用 WCAG 1.4.11（3:1），不在本脚本范围。
 * ⚠️ 改任何语义色 / token 之后都要跑一遍，**两个主题都要跑** —— 这是 A-2 的回归防线。
 *
 * 三个曾经踩过的盲区（前两个已修，第三个见下）：
 *   1. **伪元素文本**：`querySelectorAll('*')` 不返回伪元素，`content: '→'` 生成的文本
 *      既不在 `childNodes` 里也不在 `'*'` 集合里 —— 会完全漏掉。现在用
 *      `getComputedStyle(el, '::before'|'::after').content` 单独扫一遍。
 *   2. **主题**：页面主题取自 `localStorage['tmall-demo-theme']`（落成 `html[data-theme]`），
 *      `newContext()` 不设它 → 只跑浅色。现在用 `addInitScript` 注入。
 *      实测只跑浅色时「全站需修 0」，补上深色立刻暴露 data-collection 单页 97 项
 *      （根因是 `var(--surface-primary, #fff)` —— 幽灵 token，暗色下卡片仍是白底）。
 *   3. **响应式断点**：`--viewport both` 会再跑一遍 375×812。移动端有独立的字号/颜色覆盖。
 *   4. **仍未覆盖**：hover / focus / active 等**交互态**（截图里不出现）。
 *      已知 `.rival-tab.active`、`.flow-table tr:hover` 这类只在交互时渲染，
 *      它们的 token 已人工修过，但本脚本验证不到 —— 改这块要手工点一遍。
 *
 * 底色是**向上找第一个不透明的 background-color**，所以 tint 背景（brand-tint 等）会被算进去，
 * 这也是 `--text-secondary` 在灰底上差 0.11 被发现的原因。
 */
const { chromium } = require('playwright-core');

const BASE = process.env.BASE || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const getArg = (n, d) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const THEME = getArg('--theme', 'light');
const THEMES = THEME === 'both' ? ['light', 'dark'] : [THEME];
const VIEWPORT = getArg('--viewport', 'desktop');
const VIEWPORTS = VIEWPORT === 'both'
  ? [{ name: 'desktop', width: 1440, height: 900 }, { name: 'mobile', width: 375, height: 812 }]
  : [{ name: VIEWPORT, width: VIEWPORT === 'mobile' ? 375 : 1440, height: VIEWPORT === 'mobile' ? 812 : 900 }];

const PAGES = ['overview', 'products', 'promotion', 'keyword-promotion', 'new-products',
  'market-ranking', 'flow-source', 'rival-analysis', 'lifecycle', 'reviews', 'period-review',
  'data-center', 'analysis', 'category-dashboard', 'component-catalog', 'creative-board',
  'data-collection', 'goals', 'settings', 'product-detail'];

const SCRIPT = `(() => {
  function parse(c) {
    const m = String(c).match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[,\\s\\/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function lum({ r, g, b }) {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function over(fg, bg) {
    if (fg.a >= 1) return fg;
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
  function ratio(a, b) { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1,l2), lo = Math.min(l1,l2); return (hi+0.05)/(lo+0.05); }
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
  function needFor(fs, bold) { return (fs >= 24 || (bold && fs >= 18.66)) ? 3 : 4.5; }

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

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined, args: ['--no-sandbox'] });
  let grandFail = 0;

  for (const vp of VIEWPORTS) {
    for (const theme of THEMES) {
      console.log(`\n################ 主题 ${theme} / 视口 ${vp.name} ${vp.width}×${vp.height} ################`);
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      // 页面主题来自 localStorage['tmall-demo-theme']（shell.js:213-221），newContext 不设它就永远是浅色
      await ctx.addInitScript((t) => {
        try { window.localStorage.setItem('tmall-demo-theme', t); } catch (e) {}
      }, theme);

      const agg = new Map();
      let fail = 0, disabledN = 0, total = 0;
      for (const name of PAGES) {
        const page = await ctx.newPage();
        let rows = [];
        try {
          await page.goto(`${BASE}/pages/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
          await page.waitForTimeout(1700);
          const actual = await page.evaluate(() => document.documentElement.dataset.theme);
          if (actual !== theme) console.log(`${name} ⚠️ 主题未生效（实际 ${actual}）`);
          rows = await page.evaluate(SCRIPT);
        } catch (e) { console.log(`${name} ERROR ${String(e.message).slice(0, 90)}`); }
        await page.close();
        const bad = rows.filter((r) => !r.disabled);
        total += rows.length; fail += bad.length; disabledN += rows.length - bad.length;
        if (rows.length) console.log(`${name.padEnd(18)} 未过 AA ${String(rows.length).padStart(3)}（其中禁用态 ${rows.length - bad.length}）`);
        bad.slice(0, 6).forEach((r) => console.log(`    - ${r.path}  ${r.fs}px ${r.ratio}:1(需${r.need}) ${r.color} on ${r.bg}  "${r.txt}"`));
        bad.forEach((r) => { const k = `${r.path} | ${r.fs}px | ${r.ratio}:1 | ${r.color}`; agg.set(k, (agg.get(k) || 0) + 1); });
      }
      await ctx.close();
      grandFail += fail;
      console.log(`\n[${theme}/${vp.name}] 合计未过 AA ${total}（禁用态 ${disabledN}，需修 ${fail}）`);
      if (agg.size) {
        console.log(`[${theme}/${vp.name}] 按 路径/字号/对比度/色值 汇总（仅需修）:`);
        [...agg.entries()].sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${String(v).padStart(4)}  ${k}`));
      }
    }
  }

  await browser.close();
  console.log(`\n===== 全部组合合计需修 ${grandFail} =====`);
})();
