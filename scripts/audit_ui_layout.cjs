/**
 * UI 布局只读审计（NUI 现状快照）
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules \
 *   node scripts/audit_ui_layout.cjs [--base http://127.0.0.1:5000] [--out .tmp/ui-audit]
 *
 * 只读：不写业务数据，只访问 GET 页面与接口。
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const args = process.argv.slice(2);
const getArg = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const BASE = getArg('--base', 'http://127.0.0.1:5000');
const OUT = path.resolve(getArg('--out', '.tmp/ui-audit'));

const PAGES = [
  ['overview', '/'],
  ['category-dashboard', '/category-dashboard'],
  ['goals', '/goals'],
  ['reviews', '/reviews'],
  ['period-review', '/period-review'],
  ['products', '/products'],
  ['lifecycle', '/lifecycle'],
  ['keyword-promotion', '/keyword-promotion'],
  ['promotion', '/promotion'],
  ['new-products', '/new-products'],
  ['creative-board', '/creative-board'],
  ['flow-source', '/flow-source'],
  ['rival-analysis', '/rival-analysis'],
  ['market-ranking', '/market-ranking'],
  ['analysis', '/analysis'],
  ['data-collection', '/data-collection'],
  ['data-center', '/data-center'],
  ['settings', '/settings'],
  ['product-detail', '/product-detail'],
  // 4-8：compare / manage 页面已删除（路由保留 302），不再列入审计清单。
  ['component-catalog', '/component-catalog'],
];

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'compact', width: 768, height: 1024 },
  { name: 'mobile', width: 390, height: 844 },
];

const MEASURE = () => {
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const doc = document.documentElement;

  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // 横向溢出：右边界超出视口（允许 1px 误差），且元素本身比视口宽
  const offenders = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (!visible(el)) return;
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && r.width > 24) {
      const s = getComputedStyle(el);
      if (s.position === 'fixed') return;
      // 找到最近的横向滚动容器祖先：如果它自己可滚动，就不算「泄漏」
      let p = el.parentElement;
      let contained = false;
      while (p && p !== document.body) {
        const ps = getComputedStyle(p);
        if ((ps.overflowX === 'auto' || ps.overflowX === 'scroll' || ps.overflowX === 'hidden') && p.scrollWidth > p.clientWidth) {
          contained = true;
          break;
        }
        p = p.parentElement;
      }
      if (contained) return;
      offenders.push({
        tag: el.tagName.toLowerCase(),
        cls: (el.className || '').toString().slice(0, 90),
        right: Math.round(r.right),
        width: Math.round(r.width),
        text: (el.textContent || '').trim().slice(0, 40),
      });
    }
  });

  // 卡片/面板密度
  const cardSelectors = ['.ui-card', '.panel', '.metric-card', '.card', '[class*="-card"]', '[class*="panel"]'];
  const cardSet = new Set();
  cardSelectors.forEach((sel) => document.querySelectorAll(sel).forEach((el) => cardSet.add(el)));
  const cards = [...cardSet].filter(visible);

  // 标题层级
  const headings = [...document.querySelectorAll('h1,h2,h3,h4')].filter(visible).map((el) => ({
    level: Number(el.tagName[1]),
    text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60),
  }));
  const headingCounts = {};
  headings.forEach((h) => { headingCounts[h.text] = (headingCounts[h.text] || 0) + 1; });
  const duplicatedHeadings = Object.entries(headingCounts).filter(([, n]) => n > 1).map(([t, n]) => `${t} ×${n}`);

  // 首屏内容密度
  const firstScreen = [...document.querySelectorAll('body *')].filter((el) => {
    if (!visible(el)) return false;
    const r = el.getBoundingClientRect();
    if (r.top > vh || r.bottom < 0) return false;
    if (el.children.length) return false;
    return (el.textContent || '').trim().length > 1;
  });
  const firstScreenText = firstScreen.map((el) => (el.textContent || '').trim()).filter(Boolean);

  // 表格
  const tables = [...document.querySelectorAll('table')].filter(visible).map((t) => {
    const wrap = t.parentElement;
    const ws = wrap ? getComputedStyle(wrap) : null;
    return {
      cols: t.querySelectorAll('thead th').length || (t.querySelector('tr')?.children.length ?? 0),
      rows: t.querySelectorAll('tbody tr').length,
      tableWidth: Math.round(t.getBoundingClientRect().width),
      scrollWidth: t.scrollWidth,
      wrapperOverflowX: ws ? ws.overflowX : null,
      wrapperWidth: wrap ? Math.round(wrap.getBoundingClientRect().width) : null,
      horizontalScroll: wrap ? wrap.scrollWidth > wrap.clientWidth + 1 : false,
    };
  });

  // 固定/吸底元素
  const fixedBars = [...document.querySelectorAll('body *')].filter((el) => {
    if (!visible(el)) return false;
    const s = getComputedStyle(el);
    if (s.position !== 'fixed' && s.position !== 'sticky') return false;
    const r = el.getBoundingClientRect();
    return r.width > vw * 0.5 && r.height > 30 && r.height < vh * 0.4;
  }).map((el) => ({
    cls: (el.className || '').toString().slice(0, 80),
    pos: getComputedStyle(el).position,
    height: Math.round(el.getBoundingClientRect().height),
    bottom: Math.round(el.getBoundingClientRect().bottom),
    top: Math.round(el.getBoundingClientRect().top),
  }));

  // 按钮/控件统计（首屏）
  const controls = [...document.querySelectorAll('button, select, input, a[role="button"]')].filter(visible);
  const firstScreenControls = controls.filter((el) => {
    const r = el.getBoundingClientRect();
    return r.top < vh && r.bottom > 0;
  });

  // 未命名图标按钮（无 aria-label / title / 文本）
  const unnamedIconButtons = controls.filter((el) => {
    if (el.tagName !== 'BUTTON') return false;
    const hasText = (el.textContent || '').trim().length > 0;
    return !hasText && !el.getAttribute('aria-label') && !el.getAttribute('title');
  }).length;

  const main = document.querySelector('main.demo-page, main');
  const header = document.querySelector('[data-shell-header]');
  const sidebar = document.querySelector('[data-shell-sidebar]');

  return {
    viewport: { vw, vh },
    docScrollWidth: doc.scrollWidth,
    docClientWidth: doc.clientWidth,
    horizontalOverflow: doc.scrollWidth > doc.clientWidth + 1,
    overflowPx: Math.max(0, doc.scrollWidth - doc.clientWidth),
    bodyHeight: Math.round(document.body.getBoundingClientRect().height),
    pageScrollHeight: doc.scrollHeight,
    offenders: offenders.slice(0, 12),
    offenderCount: offenders.length,
    cards: cards.length,
    cardWallRatio: cards.length ? Number((cards.filter((c) => c.getBoundingClientRect().height > 60).length / cards.length).toFixed(2)) : 0,
    headings,
    headingDepth: headings.length ? Math.max(...headings.map((h) => h.level)) : 0,
    duplicatedHeadings,
    firstScreenTextCount: firstScreenText.length,
    firstScreenText: firstScreenText.slice(0, 45),
    tables,
    fixedBars,
    controlsTotal: controls.length,
    controlsFirstScreen: firstScreenControls.length,
    unnamedIconButtons,
    shell: {
      headerHeight: header ? Math.round(header.getBoundingClientRect().height) : null,
      sidebarWidth: sidebar ? Math.round(sidebar.getBoundingClientRect().width) : null,
      sidebarVisible: sidebar ? getComputedStyle(sidebar).display !== 'none' : false,
      mainWidth: main ? Math.round(main.getBoundingClientRect().width) : null,
      mainPaddingLeft: main ? getComputedStyle(main).paddingLeft : null,
      mainPaddingRight: main ? getComputedStyle(main).paddingRight : null,
    },
    pageTitle: document.title,
    bodyPage: document.body.dataset.page || null,
  };
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const shots = path.join(OUT, 'shots');
  fs.mkdirSync(shots, { recursive: true });

  const browser = await chromium.launch({
    channel: undefined,
    executablePath: process.env.PW_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const report = { base: BASE, generatedAt: new Date().toISOString(), pages: {} };

  for (const [name, route] of PAGES) {
    report.pages[name] = { route, viewports: {} };
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      const consoleErrors = [];
      const pageErrors = [];
      const failedRequests = [];
      page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300)); });
      page.on('pageerror', (e) => pageErrors.push(String(e.message).slice(0, 300)));
      page.on('requestfailed', (r) => failedRequests.push(`${r.method()} ${r.url().slice(0, 140)} :: ${r.failure()?.errorText}`));

      let measure = null;
      try {
        await page.goto(BASE + route, { waitUntil: 'networkidle', timeout: 60000 });
        await page.waitForTimeout(2200);
        measure = await page.evaluate(MEASURE);
        const shot = path.join(shots, `${name}__${vp.name}.png`);
        await page.screenshot({ path: shot, fullPage: true });
        measure.screenshot = shot;
      } catch (err) {
        measure = { error: String(err.message).slice(0, 400) };
      }
      measure.consoleErrors = consoleErrors;
      measure.pageErrors = pageErrors;
      measure.failedRequests = failedRequests.slice(0, 10);
      report.pages[name].viewports[vp.name] = measure;
      await ctx.close();
      process.stdout.write(`. ${name} ${vp.name}\n`);
    }
  }

  await browser.close();
  const outFile = path.join(OUT, 'audit.json');
  fs.writeFileSync(outFile, JSON.stringify(report, null, 2), 'utf8');
  console.log('\nWROTE ' + outFile);
})().catch((e) => { console.error(e); process.exit(1); });
