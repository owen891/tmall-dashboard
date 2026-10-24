'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),vm=require('node:vm');
const arg=process.argv.indexOf('--root'),root=path.resolve(arg<0?path.join(__dirname,'..'):process.argv[arg+1]);
const file=path.join(root,'frontend/ui_demo/assets/promotion-live.js');
const metrics=require(file),source=fs.readFileSync(file,'utf8');
const changed=typeof metrics.valueText==='function';let checks=0;
function check(name,run){run();checks++;console.log('PASS '+name);}
function fixture(value,status){const row={metric_availability:{},metric_coverage:{}};for(const key of ['ad_spend','attributed_payment_amount','direct_payment_amount','indirect_payment_amount','clicks','impressions','payment_buyers','link_gsv']){row[key]=value;row.metric_availability[key]=status;row.metric_coverage[key]={observed_rows:1,expected_rows:2,source:'promotion_daily_facts'};}return row;}
check('original evidence-rich formatter and export remain intact',()=>{
 assert.ok(metrics.format(fixture(7,'partial'),'direct_payment_amount','money').includes('部分 1/2 promotion_daily_facts'));
 assert.ok(metrics.exportValue(fixture(7,'partial'),'direct_payment_amount').includes('部分 1/2'));
 assert.equal(metrics.chartValue(fixture(7,'partial'),'direct_payment_amount'),null);
});
if(changed){
 check('real zero stays zero without a false warning',()=>{const r=fixture(0,'available');assert.equal(metrics.valueText(r,'direct_payment_amount','money'),'￥0');assert.equal(metrics.statusLabel(r,'direct_payment_amount'),'');});
 check('missing and denominator-zero states do not become zero',()=>{for(const status of ['missing-fields','insufficient-data']){const r=fixture(null,status);assert.equal(metrics.valueText(r,'direct_payment_amount','money'),'--');assert.ok(metrics.statusLabel(r,'direct_payment_amount'));}});
 check('partial amount stays numeric but is explicitly marked partial',()=>{const r=fixture(7,'partial');assert.equal(metrics.valueText(r,'direct_payment_amount','money'),'￥7');assert.equal(metrics.statusLabel(r,'direct_payment_amount'),'部分数据');assert.equal(metrics.compact(r,'direct_payment_amount','money'),'￥7（部分数据）');});
 check('partial derived CTR remains unavailable and is never graphed as complete',()=>{const q=metrics.summarize([fixture(7,'partial')]);assert.equal(q.ctr,null);assert.equal(metrics.valueText(q,'ctr','percent'),'--');assert.equal(metrics.statusLabel(q,'ctr'),'部分数据');assert.equal(metrics.chartValue(q,'ctr'),null);});
 const nodes=new Map(),$=selector=>{if(!nodes.has(selector))nodes.set(selector,{textContent:'',dataset:{},hidden:false});return nodes.get(selector);};
 const context={promotionMetrics:metrics,$,state:{period:'2026-10'},number:metrics.number};vm.createContext(context);
 const start=source.indexOf('  function renderKpis('),end=source.indexOf('\n  function ',start+3);vm.runInContext(source.slice(start,end),context);
 check('real render function separates numeric value, status and full evidence',()=>{context.renderKpis([fixture(7,'partial')]);assert.equal($('[data-promotion-kpi="direct"]').textContent,'￥7');assert.equal($('[data-promotion-kpi-status="direct"]').textContent,'部分数据');assert.ok($('[data-promotion-quality-body]').textContent.includes('promotion_daily_facts'));assert.equal($('[data-promotion-quality]').hidden,false);});
 check('stale partial badges and evidence clear after a complete rerender',()=>{context.renderKpis([fixture(7,'available')]);assert.equal($('[data-promotion-kpi-status="direct"]').hidden,true);assert.equal($('[data-promotion-kpi-status="direct"]').textContent,'');assert.equal($('[data-promotion-quality]').hidden,false);/* paid_share absent is still honestly missing */assert.ok(!$('[data-promotion-quality-body]').textContent.includes('直接付费成交：'));});
 check('metadata cannot turn into markup',()=>{const r=fixture(7,'partial');r.metric_coverage.direct_payment_amount.source='<img src=x onerror=alert(1)>';context.renderKpis([r]);assert.ok($('[data-promotion-quality-body]').textContent.includes('<img src=x'));assert.ok(!source.slice(start,end).includes('innerHTML'));});
 const html=fs.readFileSync(path.join(root,'frontend/ui_demo/pages/promotion.html'),'utf8');
 check('native details and explicit secondary-metric names are retained',()=>{assert.ok(html.includes('<details class="promotion-quality"'));assert.ok(html.includes('商品支付转化率</span>'));assert.ok(html.includes('间接付费成交</span>'));});
}else check('baseline reproduces long coverage in numeric rendering',()=>assert.ok(metrics.format(fixture(7,'partial'),'direct_payment_amount','money').includes('promotion_daily_facts')));
console.log(`RESULT ${checks} passed; ${changed?'SEPARATE_VALUE_STATUS_EVIDENCE':'LEGACY_EVIDENCE_IN_VALUE'}`);
