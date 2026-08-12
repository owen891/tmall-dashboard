const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'docs', 'ui_demo');
const pagesDir = path.join(root, 'pages');
const required = ['products', 'promotion', 'lifecycle', 'compare', 'manage'];
const errors = [];

function read(file) {
  try { return fs.readFileSync(file, 'utf8'); } catch { errors.push(`missing file: ${path.relative(root, file)}`); return ''; }
}

function assert(condition, message) { if (!condition) errors.push(message); }

for (const name of required) {
  const file = path.join(pagesDir, `${name}.html`);
  const html = read(file);
  if (!html) continue;
  const relative = path.relative(root, file);
  assert(/<title>[^<]+<\/title>/i.test(html), `${relative}: missing page title`);
  assert(/<main\b/i.test(html), `${relative}: missing main landmark`);
  assert(new RegExp(`data-page=["']${name}["']`).test(html), `${relative}: data-page must be ${name}`);
  assert(html.includes('../assets/tokens.css') && html.includes('../assets/shell.css') && html.includes('../assets/components.css'), `${relative}: missing shared CSS assets`);
  assert(html.includes('../assets/shell.js'), `${relative}: missing shell.js`);
  assert(!/<svg\b/i.test(html), `${relative}: inline SVG is not allowed; use icon data attributes`);
  assert(!/\b(?:TODO|TBD)\b/i.test(html), `${relative}: unresolved TODO/TBD marker`);
  const ids = [...html.matchAll(/(?<![\w-])id=["']([^"']+)["']/gi)].map((match) => match[1]);
  const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
  assert(duplicates.length === 0, `${relative}: duplicate ids: ${[...new Set(duplicates)].join(', ')}`);

  if (name === 'lifecycle') {
    assert(html.includes('2025-01') && html.includes('2026-03'), `${relative}: lifecycle must use the current database month range`);
    assert(html.includes('733037806819'), `${relative}: lifecycle must include a real product from the current database`);
    assert(html.includes('id="lifecycleScaleChart"'), `${relative}: missing lifecycle scale chart`);
    assert(html.includes('id="lifecycleEfficiencyChart"'), `${relative}: missing lifecycle efficiency chart`);
    assert(!html.includes('2026-07'), `${relative}: stale mock lifecycle period found`);
  }

  if (name === 'products') {
    assert(!html.includes('<h3>推广分析</h3>'), `${relative}: promotion analysis must live on its own page`);
    assert(!html.includes('id="adScatter"') && !html.includes('id="adTrend"'), `${relative}: stale promotion charts found`);
    assert(!html.includes("DemoCharts.bubble('adScatter'") && !html.includes("DemoCharts.adTrend('adTrend'"), `${relative}: stale promotion chart initialization found`);
    assert(html.includes('demo_product_field_templates'), `${relative}: personal templates must persist in localStorage`);
    assert(html.includes("querySelectorAll('[data-open-columns]')"), `${relative}: every field-template entry point must open the dialog`);
    assert(html.includes('data-field-key='), `${relative}: product columns need field keys for custom templates`);
    assert(html.includes('data-delete-template'), `${relative}: saved templates need delete controls`);
    assert(html.includes('field-template-bar__presets') && html.includes('aria-label="商品字段模板"'), `${relative}: field templates need one unified switcher`);
    assert(!html.includes('class="segmented product-view"') && !html.includes('data-view='), `${relative}: duplicate product metric view controls found`);
  }

  if (name === 'promotion') {
    const promotionJs = read(path.join(root, 'assets', 'promotion.js'));
    assert(html.includes('../assets/promotion.js'), `${relative}: missing promotion interaction module`);
    for (const scope of ['products', 'keywords', 'audience', 'creative', 'content']) {
      assert(html.includes(`data-promotion-template-scope="${scope}"`), `${relative}: missing ${scope} field-template scope`);
    }
    assert(html.includes('data-rule-builder') && promotionJs.includes('data-rule-group'), `${relative}: missing nested alert rule builder`);
    assert(promotionJs.includes('data-add-rule-condition') && promotionJs.includes('data-add-rule-group'), `${relative}: missing rule group controls`);
    for (const preset of ['低效消耗', '高点击低转化', '高花费零成交', '曝光不足', '点击异常']) {
      assert(html.includes(preset), `${relative}: missing alert preset ${preset}`);
    }
    assert(html.includes('data-product-image-id="985897754523"'), `${relative}: missing first linked product image`);
    assert(html.includes('data-product-image-id="1011889511510"'), `${relative}: missing second linked product image`);
    assert(html.includes('data-product-unlinked="971290805262"'), `${relative}: missing explicit unlinked product state`);
    assert(html.includes('¥71,698.43') && html.includes('¥425,422.12') && html.includes('5.93'), `${relative}: missing canonical April promotion totals`);
    assert(html.includes('计划 ID 78505702126') && html.includes('商品主体 985897754523'), `${relative}: missing verified plan/product identifiers`);
    assert(!html.includes('计划 ID 80545140474') && !html.includes('商品主体 1045733194511'), `${relative}: stale unverified identifiers found`);
    assert(html.includes('货品全站推广') && html.includes('关键词推广') && html.includes('超级短视频') && html.includes('人群推广'), `${relative}: missing promotion scene analysis`);
    assert(html.includes('投放关键词') && html.includes('人群分析') && html.includes('创意分析'), `${relative}: missing promotion subviews`);
    assert(html.includes('计划报表不含商品ID'), `${relative}: plan detail must disclose unavailable product linkage`);
    assert(html.includes('data-promotion-tab'), `${relative}: promotion subviews need interactive tab controls`);
    assert(html.includes("querySelectorAll('[role=\"tab\"][data-promotion-tab]')"), `${relative}: ARIA tab state must be scoped to role=tab controls`);
    assert(html.includes('data-drill-root="promotion"'), `${relative}: missing promotion drill-down root`);
    assert(html.includes('data-drill-level="product"') && html.includes('data-drill-level="plan"'), `${relative}: missing product-to-plan drill levels`);
    assert(html.includes('data-drill-level="detail"'), `${relative}: missing downstream detail drill level`);
    assert(html.includes('data-product-id="985897754523"') && html.includes('data-plan-id="78505702126"'), `${relative}: missing explicit product/plan mapping`);
    assert(html.includes('data-mapping-status="linked"') && html.includes('data-mapping-status="unassigned"'), `${relative}: missing linked and unassigned mapping states`);
    assert(html.includes('data-drill-filter') && html.includes('data-drill-back'), `${relative}: drill-down controls must preserve navigation context`);
    assert(html.includes('未归属计划汇总') && html.includes('待补商品计划映射'), `${relative}: unassigned promotion summary must disclose mapping gap`);
  }
}

const catalog = read(path.join(root, 'index.html'));
assert(/data-page=["']catalog["']/.test(catalog), 'index.html: data-page must be catalog');
assert(/assets\/shell\.js/.test(catalog), 'index.html: missing shell.js');
assert(/pages\/promotion\.html/.test(catalog), 'index.html: missing promotion catalog entry');
assert(!/\b(?:TODO|TBD)\b/i.test(catalog), 'index.html: unresolved TODO/TBD marker');

const shell = read(path.join(root, 'assets', 'shell.js'));
assert(shell.includes("['promotion', '推广分析'"), 'assets/shell.js: missing promotion navigation');
assert(shell.includes('accept=".xlsx,.xls,.zip,.csv"'), 'assets/shell.js: toolbox must accept Excel, ZIP and CSV');
assert(shell.includes('按表头识别'), 'assets/shell.js: toolbox must explain header-based detection');
assert(shell.includes('const detectImportDomain'), 'assets/shell.js: missing header-based import detector');
assert(shell.includes('file.arrayBuffer()'), 'assets/shell.js: CSV auto-detection must read actual file bytes');
assert(shell.includes("new TextDecoder('gb18030')"), 'assets/shell.js: CSV auto-detection must support source report encoding');
assert(shell.includes('window.DemoImportDetector'), 'assets/shell.js: import detector must be exposed for integration tests');
['店铺日数据', '商品日数据', '商品来源', '计划报表', '推广商品', '关键词', '人群', '创意', '内容', '地域'].forEach((label) => {
  assert(shell.includes(label), `assets/shell.js: missing import type ${label}`);
});
assert(shell.includes('data-import-history'), 'assets/shell.js: recent imports must expose batch history');

if (errors.length) {
  console.error(`${errors.length} UI demo validation error(s)`);
  errors.forEach((error) => console.error(`- ${error}`));
  process.exitCode = 1;
} else {
  console.log(`${required.length} demo pages validated`);
}
