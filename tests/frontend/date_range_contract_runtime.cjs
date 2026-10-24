'use strict';
// Execute the shipped store, not a copied date algorithm. DOM doubles prove state
// contracts only; browser_prd_gates owns visibility, geometry and HTTP assertions.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = process.argv[2] || path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/ui_demo/assets/runtime/date-range-store.js'), 'utf8');
const shell = fs.readFileSync(path.join(root, 'frontend/ui_demo/assets/shell.js'), 'utf8');
const cases = [
  ['2026-10-17', ['2026-10-12','2026-10-17'], ['2026-10-05','2026-10-11'], ['2026-10-01','2026-10-17'], ['2026-09-01','2026-09-30']],
  ['2024-03-01', ['2024-02-26','2024-03-01'], ['2024-02-19','2024-02-25'], ['2024-03-01','2024-03-01'], ['2024-02-01','2024-02-29']],
  ['2025-01-01', ['2024-12-30','2025-01-01'], ['2024-12-23','2024-12-29'], ['2025-01-01','2025-01-01'], ['2024-12-01','2024-12-31']],
  ['2024-02-29', ['2024-02-26','2024-02-29'], ['2024-02-19','2024-02-25'], ['2024-02-01','2024-02-29'], ['2024-01-01','2024-01-31']],
  ['2026-10-19', ['2026-10-19','2026-10-19'], ['2026-10-12','2026-10-18'], ['2026-10-01','2026-10-19'], ['2026-09-01','2026-09-30']],
];
const keys = ['this_week', 'last_week', 'this_month', 'last_month'];
function harness(today, search = '?start=2023-07-14&end=2023-08-12') {
  const sections = [], documentEvents = {}, events = [], historyWrites = [];
  let active = null, resolveApi;
  class Element {
    constructor() { this.children = new Map(); this.events = {}; this.dataset = {}; this.textContent = ''; this.hidden = false; this.nodeType = 1; this.attrs = {}; this.classList = {toggle(){},add(){},remove(){},contains(){return false;}}; }
    querySelector(key) { if (!this.children.has(key)) this.children.set(key, new Element()); return this.children.get(key); }
    querySelectorAll(key) { return key === '[data-inline-preset]' ? presets : []; }
    addEventListener(key, fn) { this.events[key] = fn; }
    setAttribute(key, value) { this.attrs[key] = value; }
    toggleAttribute(key, enabled) { if (enabled) this.attrs[key] = ''; else delete this.attrs[key]; }
    appendChild() {} remove() { this.removed = true; } hasAttribute(key) { return key in this.attrs; }
    contains() { return false; } getClientRects() { return [{}]; } focus() {}
  }
  const presets = [...shell.matchAll(/data-inline-preset="([^"]+)"/g)].map(m => { const e=new Element(); e.dataset.inlinePreset=m[1]; return e; });
  const header = new Element(); header.querySelector('[data-period-popover]').attrs.hidden = '';
  const [y,m,d] = today.split('-').map(Number);
  class FixedDate extends Date { constructor(...args) { super(...(args.length ? args : [y,m-1,d,12])); } }
  const window = {location:{href:'http://fixture.invalid/products'+search,search},addEventListener(){},dispatchEvent(e){events.push(e);},matchMedia(){return {matches:false,addEventListener(){},removeEventListener(){}};},TmallUI:{popover(options){active=options.content; return {node:active,close(){ active=null; options.onClose(); }};}}};
  const document = {body:new Element(),createElement(tag){const e=new Element(); if(tag==='section')sections.push(e); return e;},querySelector(){return new Element();},addEventListener(k,f){documentEvents[k]=f;}};
  vm.runInNewContext(source,{window,document,Date:FixedDate,matchMedia(){return {matches:false,addEventListener(){},removeEventListener(){}};},URL,URLSearchParams,Set,Promise,console,HTMLElement:Element,HTMLButtonElement:Element,getComputedStyle(){return {visibility:'visible'};},matchMedia(){return {matches:false,addEventListener(){},removeEventListener(){}};},CustomEvent:class {constructor(type,opts){this.type=type; this.detail=opts.detail;}},history:{pushState(_a,_b,url){historyWrites.push(String(url)); window.location.href=String(url); window.location.search=url.search;}}});
  const apiReady = new Promise(resolve => {resolveApi=resolve;});
  const store=window.TmallRuntime.createDateRangeStore({header,currentPage:'products',apiReady,pagesWithoutDateRange:new Set()});
  const snapshot=()=>JSON.stringify({state:store.getState(),url:window.location.href,events,historyWrites});
  return {store,header,events,historyWrites,snapshot,sections,get active(){return active;},
    async api(rows=[{period:'2023-09-17'}]){resolveApi({request:async()=>rows}); await new Promise(r=>setImmediate(r));},
    preset(key){const button=presets.find(b=>b.dataset.inlinePreset===key); assert.ok(button,'visible shell preset absent: '+key); button.events.click();},
    custom(){const b=header.querySelector('[data-inline-custom]'); b.events.click({currentTarget:b});},
    click(type,value){assert.ok(active,'picker closed'); const e=new Element(); e.dataset[type==='date'?'pickerDate':'pickerAction']=value; e.closest=(s)=>s===(type==='date'?'[data-picker-date]':'[data-picker-action]')?e:null; active.events.click({target:e});},
    escape(){documentEvents.keydown({key:'Escape',preventDefault(){},stopPropagation(){}});},
    changes(){return events.filter(e=>e.type==='tmall:date-range-change').length;},
  };
}
(async()=>{
  let count=0;
  const clock=harness('2026-10-17'); await clock.api(); clock.preset('7d');
  assert.deepEqual([clock.store.getState().startDate,clock.store.getState().endDate],['2026-10-11','2026-10-17'],'system day, not imported latest');
  for (const [today,...ranges] of cases) {
    for (const historical of [true,false]) {
      const h=harness(today,historical?undefined:'');
      const before=h.snapshot();
      await h.api([{period:'2023-09-17'},{period:'2023-10-01'},{period:'invalid'}]);
      assert.equal(h.snapshot(),before,'API mutated state/URL/events');
      assert.equal(h.header.querySelector('[data-period-freshness]').textContent,'数据截至 2023-10-01');
      for (let i=0;i<keys.length;i++) {
        h.preset(keys[i]); const s=h.store.getState();
        assert.deepEqual([s.startDate,s.endDate],ranges[i],today+': '+keys[i]);
        const url=new URL(h.historyWrites.at(-1)); assert.equal(url.searchParams.get('start'),s.startDate); assert.equal(url.searchParams.get('end'),s.endDate);
        count++;
      }
    }
  }
  const h=harness('2026-10-17'); const start=h.snapshot();
  h.custom(); assert.equal(h.snapshot(),start,'opening custom committed state');
  h.click('date','2023-07-16'); const half=h.snapshot();
  assert.equal(half,start,'first custom date committed');
  const readout=h.active.querySelector('.demo-picker__range-readout').textContent;
  await h.api(); assert.equal(h.snapshot(),half); assert.equal(h.active.querySelector('.demo-picker__range-readout').textContent,readout,'API changed draft');
  h.preset('this_week'); assert.equal(h.active,null,'preset left stale picker open');
  h.custom(); assert.equal(h.active.querySelector('.demo-picker__range-readout').textContent,'2026-10-12 ~ 2026-10-17');
  const committed=h.snapshot(); h.click('date','2026-10-13'); assert.equal(h.snapshot(),committed); h.click('action','close'); assert.equal(h.snapshot(),committed);
  h.custom(); h.click('date','2026-10-14'); h.escape(); assert.equal(h.active,null); assert.equal(h.snapshot(),committed);
  h.custom(); h.click('date','2026-10-13'); h.click('date','2026-10-15'); const n=h.changes(); h.click('action','custom-apply'); assert.equal(h.changes(),n+1); assert.equal(h.active,null);
  assert.deepEqual([h.store.getState().startDate,h.store.getState().endDate],['2026-10-13','2026-10-15']);
  const previous=h.snapshot(); assert.equal(h.store.setRange('2026-10-18','2026-10-19'),false); assert.equal(h.snapshot(),previous);
  const empty=harness('2026-10-17'); const es=empty.snapshot(); await empty.api([]); assert.equal(empty.snapshot(),es); assert.equal(empty.header.querySelector('[data-period-freshness]').textContent,'数据截至未知');
  console.log(JSON.stringify({ok:true,naturalRanges:count,delayedApi:'state/url/events/draft unchanged',draft:'first-click/cancel/Escape/preset/reopen/apply-once PASS',future:'rejected',scope:'pure Node actual runtime; no browser/layout/network claim'}));
})().catch(error=>{console.error(error);process.exitCode=1;});
