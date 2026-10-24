#!/usr/bin/env node
'use strict';
// Runs actual production function bodies in a minimal DOM; no source-string assertions.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const rootArg = process.argv.indexOf('--root');
const root = path.resolve(rootArg >= 0 ? process.argv[rootArg + 1] : path.join(__dirname, '..'));
class Node {
  constructor() { this.textContent = ''; this.className = ''; this.dataset = {}; this.children = []; this.styles = {}; this.style = { setProperty: (k,v) => { this.styles[k]=v; } }; this.classes = new Set(); this.classList = { toggle: (k,v) => v ? this.classes.add(k) : this.classes.delete(k), add: k => this.classes.add(k) }; }
  append(...n) { this.children.push(...n); } appendChild(n) { this.children.push(n); return n; }
  replaceChildren(...n) { this.children = n; } closest() { return this; } setAttribute(k,v) { this[k]=v; }
}
const nodes = new Map();
const node = selector => { if(!nodes.has(selector)) nodes.set(selector,new Node()); return nodes.get(selector); };
const events = [];
const sandbox = { console, URLSearchParams, localStorage:{getItem:()=>null}, MetricPolarity:{deltaClass: (_,v)=>v>0?'is-up':'is-down'}, CustomEvent:class { constructor(type,init){ this.type=type;this.detail=init.detail; } }, document:{querySelector:node,querySelectorAll:s=>[node(s)],createElement:()=>new Node()}, window:{dispatchEvent:e=>events.push(e)}, DemoLabels:{label:(_,v)=>v} };
let source=fs.readFileSync(path.join(root,'frontend/ui_demo/assets/overview-live.js'),'utf8');
const marker="  const dialog = $('[data-overview-action-dialog]');";
assert.ok(source.includes(marker),'test harness initialization boundary exists');
source=source.slice(0,source.indexOf(marker))+`\n globalThis.testApi = {matrixValue,renderKpis,renderContext,renderQuality,renderAnomalies,fallbackTargetSummary,selectedPeriodLabel: typeof selectedPeriodLabel === 'function' ? selectedPeriodLabel : null,setPeriod:p=>{activePeriod=p;}};\n})();`;
vm.runInNewContext(source,sandbox,{filename:'overview-live.js'});
const api=sandbox.testApi;
let passed=0,failed=0;
function test(name,fn){ nodes.clear(); events.length=0;try{fn();passed++;console.log('PASS '+name);}catch(e){failed++;console.error('FAIL '+name+': '+e.message);} }
function fixture(){
 const overview={payment_amount:120,net_sales:100,ad_spend:20,visitors:40,refund_rate:1/6,expense_ratio:.2,payment_conversion_rate:.2,ad_roi:6,data_grain:'monthly',fallback_reason:'daily_facts_unavailable',start_date:'2026-09-01',end_date:'2026-09-30',data_cutoff_date:'2026-09',metric_availability:{net_sales:'available',expense_ratio:'available',refund_rate:'available'},context:{start_date:'2025-01',end_date:'2026-09',latest_import:{completed_at:'2026-10-01'}}};
 const comparison={availability:'available',period_a:'2026-08',period_b:'2026-09',kpi_compare:{gmv:{period_a:100,period_b:120,change_pct:20},net_sales:{period_a:80,period_b:100,change_pct:25},roi:{period_a:5,period_b:6,change_pct:20},conversion:{period_a:.1,period_b:.2,change_pct:100}}};
 const context={response:{availability:'available',filters:{start:'2026-09-01',end:'2026-09-30',shop_label:'标品袜子'},missing_ranges:[{start:'2026-09-01',end:'2026-09-30'}]},state:{startDate:'2026-09-01',endDate:'2026-09-30',compareMode:'previous_period'},period:'2026-09',comparePeriod:'2026-08',categoryMode:'sock'};
 return {overview,comparison,context};
}
function render(f){api.renderKpis(f.overview,f.comparison,{rows:[]},{net_sales_progress:50},f.context);}
const meta=k=>node(`[data-overview-kpi-meta="${k}"]`).textContent;
const noChange=(f,key='payment_amount')=>{render(f);assert.equal(meta(key),'暂无同范围比较');assert.equal(node(`[data-overview-kpi-meta="${key}"]`).classes.size,0);};
test('complete same-month payment and net-sales retain verified comparison windows',()=>{const f=fixture();render(f);assert.match(meta('payment_amount'),/20\.0%.*2026-08.*2026-09/);assert.match(meta('net_sales'),/25\.0%.*2026-08.*2026-09/);});
test('cross-month 30-day selection does not borrow monthly change',()=>{const f=fixture();f.context.state.startDate='2026-08-20';f.context.state.endDate='2026-09-18';noChange(f);});
test('month-to-date does not borrow full-month change',()=>{const f=fixture();f.context.state.endDate='2026-09-15';noChange(f);});
test('year-over-year labels real baseline month',()=>{const f=fixture();f.context.state.compareMode='year_over_year';f.context.comparePeriod=f.comparison.period_a='2025-09';render(f);assert.match(meta('net_sales'),/同比 2025-09 → 2026-09/);});
test('year-over-year mismatch is not accepted',()=>{const f=fixture();f.context.state.compareMode='year_over_year';noChange(f);});
test('complete daily month is not same grain as monthly compare',()=>{const f=fixture();f.overview.data_grain='daily';f.overview.data_cutoff_date='2026-09-30';noChange(f);});
test('older-month fallback is not selected month',()=>{const f=fixture();f.overview.data_cutoff_date='2026-08';noChange(f);});
test('unsupported product scope is not legacy category scope',()=>{const f=fixture();f.context.response.filters.product_id='p1';noChange(f);});
test('unpinned category scope is not comparable',()=>{const f=fixture();delete f.context.categoryMode;noChange(f);});
test('same-month but mismatched current value is not comparable',()=>{const f=fixture();f.overview.payment_amount=121;noChange(f);});
test('different formulas: attributed ROI and AVG conversion are not borrowed',()=>{const f=fixture();noChange(f,'ad_roi');noChange(f,'payment_conversion_rate');});
test('missing comparison is neutral, not flat growth',()=>{const f=fixture();f.comparison.kpi_compare={};noChange(f);});
test('partial comparison cannot display growth',()=>{const f=fixture();f.comparison.availability='partial';noChange(f);});
test('partial current availability cannot display growth',()=>{const f=fixture();f.context.response.availability='partial';noChange(f);});
test('null current stays unknown, does not display monthly growth',()=>{const f=fixture();f.overview.payment_amount=null;noChange(f);assert.equal(node('[data-overview-kpi="payment_amount"]').textContent,'--');});
test('null baseline value cannot become zero',()=>{const f=fixture();f.comparison.kpi_compare.gmv.period_a=null;noChange(f);});
test('zero baseline is not fabricated growth',()=>{const f=fixture();f.comparison.kpi_compare.gmv={period_a:0,period_b:120,change_pct:null};noChange(f);});
test('true current zero remains zero with -100 percent comparison',()=>{const f=fixture();f.overview.payment_amount=0;f.comparison.kpi_compare.gmv={period_a:100,period_b:0,change_pct:-100};render(f);assert.equal(node('[data-overview-kpi="payment_amount"]').textContent,'¥0.00万');assert.match(meta('payment_amount'),/100\.0%/);});
test('stale or forged percentage rejected',()=>{const f=fixture();f.comparison.kpi_compare.gmv.change_pct=99;noChange(f);});
test('metric missing-fields remains explained',()=>{const f=fixture();f.overview.metric_availability.net_sales='missing-fields';render(f);assert.equal(meta('net_sales'),'字段缺失，暂不可计算');});
test('history span is not daily coverage',()=>{const f=fixture();api.renderContext(f.overview,f.context.response);assert.match(node('[data-overview-context]').textContent,/历史跨度/);assert.doesNotMatch(node('[data-overview-coverage]').textContent,/覆盖 \d+/);});
test('envelope missing_ranges wins over stale nested field',()=>{const f=fixture();f.overview.data_grain='daily';f.overview.missing_date_ranges=[];f.context.response.missing_ranges=[{start:'2026-09-12',end:'2026-09-14'}];api.renderContext(f.overview,f.context.response);assert.match(node('[data-overview-missing-ranges]').textContent,/2026-09-12 至 2026-09-14/);assert.match(node('[data-overview-coverage]').textContent,/存在缺日/);});
test('absent coverage contract stays unknown',()=>{const f=fixture();delete f.context.response.missing_ranges;api.renderContext(f.overview,f.context.response);assert.equal(node('[data-overview-coverage]').textContent,'当前覆盖待核验');});
test('no missing dates does not imply complete fields',()=>{const f=fixture();f.overview.data_grain='daily';f.context.response.missing_ranges=[];api.renderContext(f.overview,f.context.response);assert.match(node('[data-overview-coverage]').textContent,/完整性待核验/);});
for(const [status,tone,label] of [['available','success','数据可用'],['partial','warning','部分可用'],['missing-fields','warning','字段缺失'],['source-unavailable','danger','来源不可用'],['calculation-failed','danger','计算失败'],['no-data','muted','暂无数据'],['loading','muted','加载中'],['unknown','muted','状态未知']]) test('quality '+status,()=>{api.renderQuality(status,{missing_fields:['payment_buyers']});assert.equal(node('[data-overview-quality]').textContent,label);assert.match(node('[data-overview-quality]').className,new RegExp('ui-badge--'+tone));assert.match(node('[data-overview-quality-details]').textContent,/payment_buyers/);});
test('monthly anomaly event carries both explicit months',()=>{api.setPeriod('2026-09');api.renderAnomalies({availability:'available',anomalies:[{metric:'gmv',current:120,change:20}]});const item=events.find(e=>e.type==='tmall:overview-anomalies-ready').detail.anomalies[0];assert.equal(item.period,'2026-09');assert.equal(item.prev_period,'2026-08');});
test('target summary states monthly scope',()=>{api.setPeriod('2026-09');api.fallbackTargetSummary({net_sales_progress:50});assert.match(node('[data-overview-target-scope]').textContent,/2026-09 月度/);});
for (const status of [undefined, 'unknown', 'loading', '']) test('unconfirmed response availability rejected: '+String(status),()=>{const f=fixture();f.context.response.availability=status;noChange(f);});
test('blank and NaN metric values remain unknown, not zero',()=>{const f=fixture();f.overview.payment_amount='';f.overview.net_sales='  ';f.overview.visitors=NaN;render(f);for(const key of ['payment_amount','net_sales','visitors'])assert.equal(node(`[data-overview-kpi="${key}"]`).textContent,'--');assert.equal(node('[data-overview-summary="net_sales"]').textContent,'--');});
test('unknown payment cannot produce a fabricated zero ROI',()=>{const f=fixture();f.overview.payment_amount=null;f.overview.ad_roi=null;render(f);assert.equal(node('[data-overview-kpi="ad_roi"]').textContent,'--');});
test('matrix fallback aggregates buyers over visitors, not daily average ratios',()=>{const f=fixture();f.overview.visitors=null;f.overview.payment_conversion_rate=null;api.renderKpis(f.overview,f.comparison,{rows:[{visitors:20,buyers:10},{visitors:80,buyers:8}]},{},f.context);assert.equal(node('[data-overview-kpi="visitors"]').textContent,'0.01万');assert.equal(node('[data-overview-kpi="payment_conversion_rate"]').textContent,'18.0%');});
test('authoritative zero cannot be overwritten by matrix fallback',()=>{const f=fixture();f.overview.visitors=0;f.overview.payment_conversion_rate=0;api.renderKpis(f.overview,f.comparison,{rows:[{visitors:100,buyers:18}]},{},f.context);assert.equal(node('[data-overview-kpi="visitors"]').textContent,'0.00万');assert.equal(node('[data-overview-kpi="payment_conversion_rate"]').textContent,'0.0%');});
test('absent matrix input remains unknown',()=>{const f=fixture();f.overview.visitors=null;f.overview.payment_conversion_rate=null;api.renderKpis(f.overview,f.comparison,{rows:[]},{},f.context);assert.equal(node('[data-overview-kpi="visitors"]').textContent,'--');assert.equal(node('[data-overview-kpi="payment_conversion_rate"]').textContent,'--');});
test('monthly target progress remains without previous-month data',()=>{const f=fixture();f.comparison={availability:'partial',kpi_compare:{}};render(f);assert.equal(node('[data-overview-kpi="net_sales"]').styles['--kpi-progress'],'50%');assert.equal(meta('net_sales'),'暂无同范围比较');});
test('partial selected month does not claim monthly target progress',()=>{const f=fixture();f.context.state.endDate='2026-09-15';render(f);assert.equal(node('[data-overview-kpi="net_sales"]').styles['--kpi-progress'],'0%');});
for(const [key,a,b,pct] of [['refund_rate',.05,.1,5],['expense_ratio',.1,.2,100]]){
 test('strict rate precision rejects mismatched '+key,()=>{const f=fixture();f.overview[key]=b+.004;f.comparison.kpi_compare[key]={period_a:a,period_b:b,change_pct:pct};noChange(f,key);});
 test('matching rate stays comparable '+key,()=>{const f=fixture();f.overview[key]=b;f.comparison.kpi_compare[key]={period_a:a,period_b:b,change_pct:pct};render(f);assert.match(meta(key),/2026-08.*2026-09/);});
}
test('subtitle separates selected dates from monthly diagnosis',()=>{assert.equal(api.selectedPeriodLabel({startDate:'2026-09-10',endDate:'2026-09-17'},'2026-09'),'所选区间 2026-09-10 ~ 2026-09-17 · 月度诊断 2026-09');});
test('matrix provenance retains filename and data source',()=>{const row={source_detail:{source_filename:'daily-fixture.xlsx',source_batch_id:'batch-7',data_source:'store_daily_facts'}};assert.equal(api.matrixValue(row,{key:'source_batch_id',format:'source'}),'daily-fixture.xlsx');assert.equal(api.matrixValue(row,{key:'data_source',format:'source'}),'store_daily_facts');});
test('monthly context is explicitly a monthly reference',()=>{const f=fixture();api.renderContext(f.overview,f.context.response);assert.match(node('[data-overview-context]').textContent,/月度数据/);assert.match(node('[data-overview-data-scope]').textContent,/月度汇总参考.*不是所选日期的日度实绩/);});
test('daily context is not mislabeled as monthly',()=>{const f=fixture();f.overview.data_grain='daily';delete f.overview.context.latest_import;api.renderContext(f.overview,f.context.response);assert.match(node('[data-overview-context]').textContent,/日度事实/);assert.doesNotMatch(node('[data-overview-context]').textContent,/没有导入/);assert.doesNotMatch(node('[data-overview-data-scope]').textContent,/月度/);});
test('unknown context grain stays unconfirmed',()=>{const f=fixture();delete f.overview.data_grain;api.renderContext(f.overview,f.context.response);assert.match(node('[data-overview-context]').textContent,/粒度待核验/);assert.doesNotMatch(node('[data-overview-context]').textContent,/日度事实|月度数据/);});
test('net profit amount and rate render on their own cards',()=>{const f=fixture();f.overview.profit=13500;f.overview.profit_rate=.135;render(f);assert.equal(node('[data-overview-kpi="profit"]').textContent,'¥1.35万');assert.equal(node('[data-overview-kpi="profit_rate"]').textContent,'13.5%');});
test('absent cost data keeps net profit unknown and explained',()=>{const f=fixture();f.overview.profit=null;f.overview.profit_rate=null;f.overview.metric_availability.profit='missing-fields';render(f);assert.equal(node('[data-overview-kpi="profit"]').textContent,'--');assert.equal(node('[data-overview-kpi="profit_rate"]').textContent,'--');assert.equal(meta('profit'),'字段缺失，暂不可计算');});
test('net profit never borrows a comparison the trend API does not provide',()=>{const f=fixture();f.overview.profit=13500;f.overview.profit_rate=.135;f.comparison.kpi_compare.profit={period_a:10000,period_b:13500,change_pct:35};render(f);assert.equal(meta('profit'),'暂无同范围比较');assert.equal(meta('profit_rate'),'暂无同范围比较');});
console.log(`SUMMARY ${passed} passed, ${failed} failed; root=${root}`);
process.exitCode=failed?1:0;