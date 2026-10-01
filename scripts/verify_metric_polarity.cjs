/**
 * 4-3 验证：MetricPolarity 已加载、判定符合预期、三个页面无 JS 报错。
 * 用法：NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/verify_metric_polarity.cjs
 */
const { chromium } = require('playwright-core');
const BASE = 'http://127.0.0.1:5000';
const ROUTES = ['/overview', '/period-review', '/lifecycle', '/products'];

(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined, args: ['--no-sandbox'] });
  const c = await b.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await c.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  p.on('console', (m) => { if (m.type() === 'error' && /MetricPolarity|is not defined/i.test(m.text())) errors.push('console: ' + m.text()); });

  let fail = 0;
  for (const route of ROUTES) {
    await p.goto(BASE + route, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(6000);
    const r = await p.evaluate(() => {
      const MP = window.MetricPolarity;
      if (!MP) return { loaded: false };
      const cases = [
        // ── 花费总额类：涨 = 投放规模扩大 = 好（2026-10-01 业务确认）──
        ['ad_spend', 10, false],
        ['ad_spend', -10, true],
        ['wujie_spend', 10, false],
        ['gift_cost', 10, false],
        // ── 费率类：涨 = 效率下降 = 坏 ──
        ['ad_ratio', 5, true],
        ['expense_ratio', 5, true],
        ['wujie_expense_ratio', 5, true],
        // ── 单位成本类：涨 = 获客变贵 = 坏 ──
        ['cpc', 5, true],
        ['paid_cpc', 5, true],
        // ── 越高越好 ──
        ['net_sales', 10, false],
        ['net_sales', -10, true],
        ['profit_rate', 2, false],
        // ── 损失类：涨 = 坏 ──
        ['refund_rate', 3, true],
        ['refund_amount', 3, true],
        // ── 持平 / deadBand ──
        ['gsv', 0, null],
        ['gsv', 0.01, null],
      ];
      const bad = [];
      cases.forEach(([key, chg, expectBad]) => {
        const good = MP.isGood(key, chg, { deadBand: key === 'gsv' && chg === 0.01 ? 0.05 : 0 });
        const actualBad = good === null ? null : !good;
        if (actualBad !== expectBad) bad.push(`${key}(${chg}): 期望坏=${expectBad} 实际坏=${actualBad}`);
      });
      // 显式覆盖优先：后端说 ad_spend 越低越差（lower_better=false）时应尊重
      const overrideRespected = MP.isGood('ad_spend', 10, { lowerBetter: false }) === true;
      return { loaded: true, bad, overrideRespected, lower: [...MP.LOWER_IS_BETTER].length };
    });
    if (!r.loaded) { console.log('FAIL ' + route + '  MetricPolarity 未加载'); fail++; continue; }
    const ok = r.bad.length === 0 && r.overrideRespected;
    if (!ok) fail++;
    console.log((ok ? 'PASS ' : 'FAIL ') + route + '  表内 ' + r.lower + ' 个负向指标；' +
      (r.bad.length ? '判定不符: ' + r.bad.join('; ') : '判定全部符合') +
      (r.overrideRespected ? '' : ' | 显式覆盖未生效'));
  }
  if (errors.length) { console.log('\nJS 报错:'); errors.slice(0, 10).forEach((e) => console.log('  ' + e)); }
  else console.log('\n无 JS 报错');
  console.log(fail ? '\n结果: FAIL (' + fail + ')' : '\n结果: PASS');
  await b.close();
  process.exit(fail ? 1 : 0);
})();
