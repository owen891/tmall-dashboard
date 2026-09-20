/**
 * 视觉验收：品类经营看板（成本/利润口径改造后）。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_category_dashboard.js
 *
 * 校验点：
 *   1. 经营利润显示真实值（标品袜子本月应为负），不再是「净销售额 − 推广花费」
 *   2. 利润口径徽标为「BI 支付预估」，利润面板逐项列出成本
 *   3. 「数据截至」等于库内真实最后一天
 *   4. 对比方式切到「去年同期」后 KPI 标签随之变化
 *   5. 趋势图出现当前周期 + 对比周期两条线
 *   6. 无控制台错误、无 ECharts 重复实例告警
 */
const path = require('path');

const PORT = process.env.TMALL_VERIFY_PORT || '5099';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT = path.join(__dirname, '..', 'logs', 'category_dashboard_profit.png');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const kpiTexts = () => [...document.querySelectorAll('#categoryDashboardKpis .dashboard-kpi')]
  .map((node) => ({
    title: (node.querySelector('span')?.innerText || '').trim(),
    value: (node.querySelector('strong')?.innerText || '').trim(),
    note: (node.querySelector('small')?.innerText || '').trim(),
  }));

const profitRows = () => [...document.querySelectorAll('#categoryDashboardProfit > div')]
  .map((node) => `${(node.querySelector('span')?.innerText || '').trim()}=${(node.querySelector('strong')?.innerText || '').trim()}`);

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
  const errors = [];
  const IGNORE = /icon name was not found|gitcode\.com|ERR_FAILED|status of 404/;
  page.on('console', (m) => {
    if ((m.type() === 'error' || m.type() === 'warning') && !IGNORE.test(m.text())) errors.push(`${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));

  await page.goto(`${BASE}/category-dashboard`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);

  const report = {};
  report.state = (await page.locator('#categoryDashboardState').innerText()).trim();
  report.periodLabel = (await page.locator('#dashboardPeriodLabel').innerText()).trim();
  report.kpis = await page.evaluate(kpiTexts);
  report.profitBadge = (await page.locator('#dashboardProfitBadge').innerText()).trim();
  report.profitRows = await page.evaluate(profitRows);
  report.profitNote = (await page.locator('.dashboard-profit-note').first().innerText().catch(() => '')).trim();
  report.trendMeta = (await page.locator('#dashboardTrendMeta').innerText()).trim();

  // 主指标切到经营利润，确认 KPI 与洞察条口径
  await page.selectOption('#dashboardMetric', 'operating_profit');
  await page.waitForTimeout(3000);
  report.operatingProfitKpis = await page.evaluate(kpiTexts);
  report.insight = (await page.locator('#dashboardInsight').innerText()).trim();

  // 对比方式切到「去年同期」
  await page.selectOption('#dashboardMetric', 'net_sales');
  await page.waitForTimeout(2500);
  await page.selectOption('#dashboardCompareMode', 'yoy');
  await page.waitForTimeout(3000);
  report.yoyPeriodLabel = (await page.locator('#dashboardPeriodLabel').innerText()).trim();
  report.yoyKpis = await page.evaluate(kpiTexts);

  // 切「无对比」
  await page.selectOption('#dashboardCompareMode', 'none');
  await page.waitForTimeout(2500);
  report.noComparePeriodLabel = (await page.locator('#dashboardPeriodLabel').innerText()).trim();
  report.noCompareKpis = await page.evaluate(kpiTexts);

  // 趋势序列条数（验证对比线）
  await page.selectOption('#dashboardCompareMode', 'previous');
  await page.waitForTimeout(3000);
  report.trendSeriesCount = await page.evaluate(() => {
    const node = document.getElementById('categoryDashboardTrend');
    const chart = window.echarts?.getInstanceByDom(node);
    return chart ? (chart.getOption()?.series || []).length : 0;
  });

  await page.screenshot({ path: OUT, fullPage: true });
  report.consoleIssues = errors;
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})();
