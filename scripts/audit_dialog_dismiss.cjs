#!/usr/bin/env node
/**
 * 弹窗「点击遮罩关闭」双向回归防线。
 *
 * 背景：2026-10-03 修掉「周月复盘设置弹窗点遮罩不关」时，给公共组件加了
 * 文档级 click 委托兜底（ui-components.js 的 lightDismiss / enableLightDismiss），
 * 用来覆盖静态写在 HTML 里、以及运行时动态创建的 <dialog>。委托是全局的，
 * 所以它有两个方向都可能出问题：
 *
 *   A) 该关的没关 —— 遮罩点击不生效（原始 bug 的形态）
 *   B) 不该关的关了 —— 把 dismissible:false 的「不可误关弹窗」也关掉（新引入的风险）
 *
 * 本脚本同时守住这两边，任何一边破了都退出码 1。
 *
 * 用例：
 *   A. period-review 复盘设置弹窗（静态 <dialog>，原始 bug 现场）
 *      —— 遮罩 / Esc / 取消按钮 三条路径都必须能关
 *   B. component-catalog 组件演示（TmallUI.modal / confirm 运行时创建）
 *      —— dismissible:false 的弹窗，遮罩与 Esc 都必须**无效**，只能走页脚按钮
 *      —— 普通弹窗（dismissible 默认 true）遮罩必须能关
 *   C. 移动端侧栏抽屉（375×812）—— 本质也是「带遮罩/Esc 的浮层」，同族防线
 *      —— 打开时 .demo-main / skip-link 必须被 inert（遮罩下内容不可达），
 *         但 aria-live 状态区与 toolbox-dialog 必须**不**被 inert（一刀切会误伤）
 *      —— Tab 45 次不得逃逸到抽屉外（只允许 body 环绕点）
 *      —— 抽屉内开工具箱后遮罩必须撤掉（曾残留导致整页点不动）
 *      —— 遮罩 / Esc 关闭后无残留 inert，Esc 关闭焦点回到汉堡按钮
 *   D. 板块数据抽屉（period-review，非模态右侧面板）
 *      —— 六段证据默认收起（2026-10-03 前默认展开，证据区合计约 7200px 把写作区推到 12 屏外）
 *      —— 抽屉内容按段渲染 + 锚点 chips 对齐；开 / 点外部 / Esc / 关闭按钮 四条路径
 *      —— 非模态：无遮罩、不锁滚动、不做焦点陷阱（左侧写作区仍可编辑）
 *
 * 用法：
 *   node scripts/audit_dialog_dismiss.cjs
 *   node scripts/audit_dialog_dismiss.cjs http://127.0.0.1:5000
 *
 * 退出码：0 = 全部通过；1 = 有断言失败。
 */
const path = require('node:path');
const { chromium } = require(path.join(__dirname, '..', 'desktop', 'node_modules', 'playwright'));

const BASE = process.argv[2] || 'http://127.0.0.1:5000';
let pass = 0;
let fail = 0;
const ok = (cond, label, extra = '') => {
  if (cond) { pass += 1; console.log(`  OK   ${label}`); }
  else { fail += 1; console.log(`  FAIL ${label} ${extra}`); }
};

const openState = (page, sel) => page.evaluate((s) => {
  const d = document.querySelector(s);
  return d ? d.open === true : null;
}, sel);

const anyOpenDialog = (page) => page.evaluate(() => Boolean(document.querySelector('dialog[open]')));

// 落点 (8,8)：modal 弹窗在 top layer，该点必然落在 ::backdrop 上，
// 事件 target 即 <dialog> 本身 —— 与用户真实点遮罩完全一致。
const clickBackdrop = async (page) => { await page.mouse.click(8, 8); await page.waitForTimeout(400); };

(async () => {
  const browser = await chromium.launch({ headless: true });

  console.log('\n[A] period-review 复盘设置弹窗（静态 <dialog>）');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).split('\n')[0]));
    await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);

    const SEL = '[data-pr-settings-dialog]';
    const OPEN = '[data-pr-settings-open]';

    await page.locator(OPEN).first().click();
    await page.waitForTimeout(400);
    ok(await openState(page, SEL) === true, 'A1 点「设置」可打开弹窗');

    await clickBackdrop(page);
    ok(await openState(page, SEL) === false, 'A2 点遮罩可关闭（原始 bug 已修）');

    await page.locator(OPEN).first().click();
    await page.waitForTimeout(300);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    ok(await openState(page, SEL) === false, 'A3 Esc 可关闭');

    await page.locator(OPEN).first().click();
    await page.waitForTimeout(300);
    await page.locator('[data-pr-settings-cancel]').first().click();
    await page.waitForTimeout(300);
    ok(await openState(page, SEL) === false, 'A4 「取消」按钮可关闭');

    ok(errs.length === 0, 'A5 无 pageerror', errs.join(' | '));
    await page.close();
  }

  console.log('\n[B] component-catalog 不可误关弹窗（运行时创建）');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).split('\n')[0]));
    await page.goto(`${BASE}/pages/component-catalog.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const result = () => page.locator('[data-catalog-modal-result]').first().textContent().then((t) => (t || '').trim());

    // B1-B6 dismissible:false —— 遮罩与 Esc 必须无效
    await page.locator('[data-catalog-modal="static"]').first().click();
    await page.waitForTimeout(400);
    ok(await anyOpenDialog(page), 'B1 打开「不可误关弹窗」');
    await clickBackdrop(page);
    ok(await anyOpenDialog(page), 'B2 遮罩点击后仍然打开（未被越权关闭）');
    ok(!(await result()).includes('onClose'), 'B3 onClose 未被触发');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    ok(await anyOpenDialog(page), 'B4 Esc 后仍然打开');
    await page.locator('dialog[open] .ui-modal__footer button', { hasText: '我知道了' }).first().click();
    await page.waitForTimeout(300);
    ok(!(await anyOpenDialog(page)), 'B5 页脚按钮可关闭');
    ok((await result()).includes('onClose'), 'B6 关闭触发 onClose', `实际="${await result()}"`);

    // B7-B10 confirm()（内部即 dismissible:false）
    await page.locator('[data-catalog-modal="confirm"]').first().click();
    await page.waitForTimeout(400);
    ok(await anyOpenDialog(page), 'B7 打开 confirm 弹窗');
    await clickBackdrop(page);
    ok(await anyOpenDialog(page), 'B8 confirm 遮罩点击无效');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    ok(await anyOpenDialog(page), 'B9 confirm Esc 无效');
    await page.locator('dialog[open] .ui-modal__footer button', { hasText: '取消' }).first().click();
    await page.waitForTimeout(300);
    ok(!(await anyOpenDialog(page)), 'B10 confirm「取消」可关闭');

    // B11-B12 普通弹窗必须能遮罩关闭
    await page.locator('[data-catalog-modal="form"]').first().click();
    await page.waitForTimeout(400);
    ok(await anyOpenDialog(page), 'B11 打开普通表单弹窗');
    await clickBackdrop(page);
    ok(!(await anyOpenDialog(page)), 'B12 普通弹窗遮罩可关闭');

    ok(errs.length === 0, 'B13 无 pageerror', errs.join(' | '));
    await page.close();
  }

  console.log('\n[C] 移动端侧栏抽屉（375×812，焦点收容 + 遮罩/Esc 关闭）');
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).split('\n')[0]));
    await page.goto(`${BASE}/pages/overview.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const snap = () => page.evaluate(() => {
      const q = (s) => document.querySelector(s);
      const act = document.activeElement;
      return {
        sidebarOpen: q('#demo-sidebar')?.classList.contains('is-open'),
        sidebarInert: q('#demo-sidebar')?.hasAttribute('inert'),
        mainInert: q('.demo-main')?.hasAttribute('inert'),
        skipInert: q('[data-skip-link]')?.hasAttribute('inert'),
        statusInert: q('[data-demo-status]')?.hasAttribute('inert'),
        toastInert: q('[data-demo-toast]')?.hasAttribute('inert'),
        toolboxInert: q('[data-toolbox-dialog]')?.hasAttribute('inert'),
        toolboxOpen: q('[data-toolbox-dialog]')?.open,
        bodyLock: document.body.classList.contains('demo-scroll-lock'),
        activeTag: act ? act.tagName.toLowerCase() + (typeof act.className === 'string' && act.className ? '.' + act.className.trim().split(/\s+/).join('.') : '') : '(null)',
      };
    });

    const s0 = await snap();
    ok(s0.mainInert === false && s0.skipInert === false, 'C1 初始页面无 inert');

    await page.locator('[data-mobile-nav]').first().click();
    await page.waitForTimeout(500);
    const s1 = await snap();
    ok(s1.sidebarOpen === true && s1.sidebarInert === false, 'C2 抽屉打开、侧栏未 inert');
    ok(s1.mainInert === true && s1.skipInert === true, 'C3 .demo-main 与 skip-link 被 inert（遮罩下内容不可达）');
    ok(s1.statusInert === false && s1.toastInert === false, 'C4 aria-live 状态区未被 inert（播报不被静音）');
    ok(s1.toolboxInert === false, 'C5 toolbox-dialog 未被 inert（否则 showModal 打不开）');

    // 键盘收容：真实 Tab 驱动。走完容器内元素后 activeElement 会短暂落到 body（环绕点），
    // 故允许极少数「落在抽屉外」，但不应有其它元素可达。
    let outside = 0;
    for (let i = 0; i < 45; i += 1) {
      await page.keyboard.press('Tab');
      const dir = await page.evaluate(() => {
        const a = document.activeElement;
        return a && a.closest && a.closest('#demo-sidebar') ? 'in' : 'out';
      });
      if (dir === 'out') outside += 1;
    }
    ok(outside <= 4, `C6 Tab 45 次仅 ${outside} 次落在抽屉外（只应有 body 环绕点）`);

    // 抽屉内打开工具箱：原先只 remove('is-open')，遮罩会残留在页面上拦截指针事件。
    await page.locator('#demo-sidebar [data-open-toolbox]').first().click();
    await page.waitForTimeout(600);
    const s2 = await snap();
    ok(s2.toolboxOpen === true, 'C7 抽屉内「导入数据」可打开工具箱');
    ok(s2.mainInert === false && s2.skipInert === false, 'C8 打开工具箱后抽屉的 inert 已撤掉');
    const backdropGone = await page.evaluate(() => {
      const b = document.querySelector('.demo-nav-backdrop');
      return !b || b.hidden || !b.classList.contains('is-visible');
    });
    ok(backdropGone, 'C9 抽屉遮罩已撤（原 bug：遮罩残留导致整页点不动）');

    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    const s3 = await snap();
    ok(s3.toolboxOpen === false, 'C10 Esc 关闭工具箱');
    ok(s3.mainInert === false && s3.skipInert === false, 'C11 关闭后页面无残留 inert');
    ok(s3.bodyLock === false, 'C12 滚动锁已释放');

    // 关闭路径 1：点遮罩
    await page.locator('[data-mobile-nav]').first().click();
    await page.waitForTimeout(400);
    await page.mouse.click(370, 400);
    await page.waitForTimeout(400);
    const s4 = await snap();
    ok(s4.sidebarOpen === false && s4.mainInert === false && s4.skipInert === false, 'C13 点遮罩关抽屉且无残留 inert');

    // 关闭路径 2：Esc，焦点应回到汉堡按钮
    await page.locator('[data-mobile-nav]').first().click();
    await page.waitForTimeout(400);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    const s5 = await snap();
    ok(s5.sidebarOpen === false && s5.sidebarInert === true, 'C14 Esc 关抽屉、侧栏恢复 inert');
    ok(s5.activeTag.includes('demo-mobile-nav'), 'C15 焦点回到汉堡按钮', `实际 ${s5.activeTag}`);

    ok(errs.length === 0, 'C16 无 pageerror', errs.join(' | '));
    await page.close();
    await ctx.close();
  }

  console.log('\n[D] 板块数据抽屉（非模态右侧面板，period-review）');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).split('\n')[0]));
    await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);

    const DRAWER = '[data-pr-drawer]';
    const isOpen = () => page.locator(DRAWER).evaluate((el) => el.classList.contains('is-open'));

    ok((await page.locator('.pr-evidence').count()) > 0, 'D1 六段证据区存在');
    const anyEvOpen = await page.evaluate(() => [...document.querySelectorAll('.pr-evidence')].some((d) => d.open));
    ok(!anyEvOpen, 'D2 证据默认收起（表格墙不铺在段落里）');
    ok((await page.locator('.pr-evidence__open-drawer').count()) > 0, 'D3 每段有「在右侧展开 →」入口');
    ok((await isOpen()) === false, 'D4 初始抽屉关闭');
    const secs = await page.locator('[data-pr-drawer-body] > .pr-drawer__section').count();
    ok(secs > 0, `D5 抽屉内容已渲染（${secs} 段）`);
    ok((await page.locator('[data-pr-drawer-nav] .pr-drawer__nav-chip').count()) === secs, 'D6 锚点 chips 与段数一致');

    await page.locator('.pr-evidence__open-drawer').first().click();
    await page.waitForTimeout(500);
    ok(await isOpen(), 'D7 点入口打开抽屉');

    await page.locator('.ui-page-header h1').click();
    await page.waitForTimeout(400);
    ok(!(await isOpen()), 'D8 点抽屉外部关闭');

    await page.locator('.pr-evidence__open-drawer').first().click();
    await page.waitForTimeout(400);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    ok(!(await isOpen()), 'D9 Esc 关闭');

    await page.locator('.pr-evidence__open-drawer').first().click();
    await page.waitForTimeout(400);
    await page.locator('[data-pr-drawer-close]').click();
    await page.waitForTimeout(400);
    ok(!(await isOpen()), 'D10 关闭按钮关闭');

    await page.locator('.pr-evidence__open-drawer').nth(1).click();
    await page.waitForTimeout(700);
    const scrolled = await page.evaluate(() => document.querySelector('[data-pr-drawer-body]').scrollTop);
    ok(scrolled > 0, `D11 按锚点定位（scrollTop=${scrolled}）`);

    ok(errs.length === 0, 'D12 无 pageerror', errs.join(' | '));
    await page.close();
  }

  await browser.close();
  console.log(`\n==== ${pass} 通过 / ${fail} 失败 ====`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('FAILED:', e); process.exit(1); });
