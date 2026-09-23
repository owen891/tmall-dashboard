/**
 * 验证「复盘设置里的 4 项目标」在页面上的行为（只读，不落库）。
 *
 * 断言三件事：
 *   1. 输入框回填 = 服务端已保存的目标（含净费比按百分数显示）
 *   2. 改动输入框后，「目标 vs 实际」表即时重算，且净费比按小数口径参与计算
 *      （曾经漏了 ÷100，把 24.5 当成 2450% 算）
 *   3. 重新加载后输入框仍是服务端值（本脚本不点保存，确保没有副作用）
 *
 * 注意：复盘周期来自顶栏共享时间范围，不是 URL 参数；且页面只认有数据的周期，
 * 传未来月份会被静默忽略。所以这里固定用已知有数据的 9 月周区间。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_period_review_targets.js [port] [start] [end]
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const RANGE_START = process.argv[3] || '2026-09-14';
const RANGE_END = process.argv[4] || '2026-09-20';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

// 期望：净费比输入 24.5(%) → 落库口径 0.245，不是 24.5
const TYPED = {
  '[data-pr-target]': '500000',
  '[data-pr-target-profit]': '35000',
  '[data-pr-target-ad-spend]': '120000',
  '[data-pr-target-net-expense-ratio]': '24.5',
};

const failures = [];

function check(label, actual, expected) {
  const ok = String(actual) === String(expected);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${label}: ${JSON.stringify(actual)}${ok ? '' : ` (期望 ${JSON.stringify(expected)})`}`);
  if (!ok) failures.push(label);
}

async function readInputs(page) {
  return page.evaluate(() => {
    const pick = (sel) => {
      const el = document.querySelector(sel);
      return el ? el.value : null;
    };
    return {
      sales: pick('[data-pr-target]'),
      profit: pick('[data-pr-target-profit]'),
      adSpend: pick('[data-pr-target-ad-spend]'),
      netRatio: pick('[data-pr-target-net-expense-ratio]'),
    };
  });
}

async function readTargetRows(page) {
  return page.evaluate(() => {
    const box = document.querySelector('[data-pr-overview] .pr-target-table');
    if (!box) return null;
    const tbl = box.querySelector('table');
    const headers = [...tbl.querySelectorAll('thead th')].map((th) => th.innerText.trim());
    const rows = {};
    [...tbl.querySelectorAll('tbody tr')].forEach((tr) => {
      rows[tr.getAttribute('data-pr-target-row')] =
        [...tr.querySelectorAll('td')].map((td) => td.innerText.trim());
    });
    return { headers, rows };
  });
}

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1400 } });
  page.on('pageerror', (err) => console.log('PAGE-EXCEPTION ' + err.message));

  await page.addInitScript(() => {
    try { window.localStorage.setItem('dashboard.categoryMode', 'sock'); } catch (_) {}
  });

  const load = async () => {
    await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);
    await page.evaluate(({ start, end }) => {
      window.TmallDateRange?.setRange?.(start, end, 'custom');
    }, { start: RANGE_START, end: RANGE_END });
    await page.waitForTimeout(7000);
  };

  await load();

  const period = await page.evaluate(() => {
    const el = document.querySelector('[data-pr-overview] .section-kicker, [data-pr-overview] h3, [data-pr-overview]');
    return (el ? el.innerText : '').split('\n').slice(0, 2).join(' | ');
  });
  console.log('PERIOD ' + JSON.stringify(period));

  const before = await readInputs(page);
  console.log('BEFORE ' + JSON.stringify(before));

  // 2) 改输入框，看即时重算
  for (const [sel, value] of Object.entries(TYPED)) {
    const el = page.locator(sel);
    await el.fill(value);
    await el.dispatchEvent('input');
  }
  await page.waitForTimeout(600);

  const table = await readTargetRows(page);
  console.log('LIVE-TABLE ' + JSON.stringify(table, null, 2));
  check('表头 差距列名', table.headers[4], '差距（目标-实际）');
  check('表头 时间进度列名', table.headers[5], '时间进度');
  check('净费比 目标显示', table.rows.net_expense_ratio[1], '24.50%');
  // 实际净费比 50239.26 / 192225.88 = 26.1355% → 反向达成率 = 0.245 / 0.261355 = 93.74%
  // （注意不能用表上四舍五入后的 26.14% 反推，会差 0.01pt）
  check('净费比 达成率', table.rows.net_expense_ratio[3], '93.74%');
  check('销售额 达成率', table.rows.net_sales[3], '38.45%');
  // 推广费是「预算使用率」= 实际 ÷ 目标（用户表口径）：50239.26 / 120000 = 41.87%
  check('推广费 达成率', table.rows.ad_spend[3], '41.87%');
  // 时间进度 = 周期结束日 / 当月天数：W3 结束于 9/20 → 20/30 = 66.67%
  check('时间进度', table.rows.net_sales[5], '66.67%');

  await page.screenshot({ path: path.join(OUT_DIR, 'pr_targets_live.png'), fullPage: true });

  // 3) 重载（不保存），确认服务端值没被写坏
  await load();
  const after = await readInputs(page);
  console.log('AFTER-RELOAD ' + JSON.stringify(after));
  Object.entries(before).forEach(([key, value]) => check(`重载后 ${key} 未变`, after[key], value));

  await browser.close();
  if (failures.length) {
    console.log('FAILED ' + failures.length + ' 项: ' + failures.join(' / '));
    process.exit(1);
  }
  console.log('ALL CHECKS PASSED');
})().catch((e) => { console.error('FAIL', e); process.exit(1); });
