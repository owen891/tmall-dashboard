'use strict';
// Node lifecycle contract, NOT a renderer/layout/browser substitute.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[2]||path.resolve(__dirname,'..');
const primitive=process.argv[3]||path.join(root,'frontend/ui_demo/assets/ui-components.js');
class Node {
 constructor(tag='div'){this.nodeType=1;this.tagName=tag.toUpperCase();this.children=[];this.parentNode=null;this.events=new Map();this.attrs={};this.dataset={};this.className='';this.hidden=false;this.checked=false;this.value='';this.style={setProperty(k,v){this[k]=v;},removeProperty(k){delete this[k];}};this.classList={toggle(){},add(){},remove(){}};this.rect={left:33,top:430,right:189,bottom:462,width:156,height:32};}
 append(...ns){for(const n of ns){n.remove();this.children.push(n);n.parentNode=this;}} insertBefore(n,next){n.remove();const i=next?this.children.indexOf(next):-1;if(next&&i<0)throw Error('invalid sibling');if(i<0)this.children.push(n);else this.children.splice(i,0,n);n.parentNode=this;}
 remove(){if(this.parentNode){const p=this.parentNode;p.children.splice(p.children.indexOf(this),1);this.parentNode=null;}} get nextSibling(){if(!this.parentNode)return null;return this.parentNode.children[this.parentNode.children.indexOf(this)+1]||null;}
 contains(n){return n===this||this.children.some(x=>x.contains(n));} setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k]??null;}hasAttribute(k){return k in this.attrs;}
 addEventListener(k,f){if(!this.events.has(k))this.events.set(k,new Set());this.events.get(k).add(f);}removeEventListener(k,f){this.events.get(k)?.delete(f);}emit(k,event={}){for(const f of [...(this.events.get(k)||[])])f({target:this,preventDefault(){},stopPropagation(){},...event});}
 focus(){doc.activeElement=this;}closest(selector){return selector==='[data-overview-trend-control]'?home:null;}querySelectorAll(){return[];}getBoundingClientRect(){return this.className.includes('ui-popover')?{left:0,top:0,width:250,height:331,right:250,bottom:331}:this.rect;}
}
const doc=new Node();doc.nodeType=9;doc.body=new Node('body');doc.append(doc.body);doc.documentElement=Object.assign(new Node('html'),{clientWidth:390,clientHeight:844});doc.createElement=tag=>new Node(tag);doc.activeElement=doc.body;
const home=new Node(),trigger=new Node('button'),menu=new Node(),sentinel=new Node();menu.className='trend-picker__menu';menu.hidden=true;home.append(trigger,menu,sentinel);doc.body.append(home);
const inputs=['net_sales','payment_amount','refund_amount','ipv'].map(value=>{const n=new Node('input');n.value=value;n.dataset.overviewTrendMode=value;menu.append(n);return n;});
doc.querySelectorAll=selector=>selector==='[data-overview-trend-mode]'?inputs:[];
const w=new Node();w.DemoShell={showToast:x=>toasts.push(x)};const toasts=[];let copies=0;const frames=[];
const context={window:w,document:doc,console,requestAnimationFrame:f=>frames.push(f),setTimeout(){},clearTimeout(){},HTMLElement:Node,Element:Node,Node,
 $:s=>s==='[data-overview-trend-trigger]'?trigger:s==='[data-overview-trend-menu]'?menu:null,
 homeTrendModes:['net_sales','payment_amount','refund_amount'],trendMetricLabels:{net_sales:'net',payment_amount:'payment',refund_amount:'refund',ipv:'visitors'},latestTrendRows:[],updateTrendCopy:()=>copies++,renderTrend(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync(primitive,'utf8'),context,{filename:primitive});
const source=fs.readFileSync(path.join(root,'frontend/ui_demo/assets/overview-live.js'),'utf8');
const a=source.indexOf('  function selectTrendModes(modes) {'),b=source.indexOf("  document.querySelectorAll('[data-overview-kpi-select]').forEach((card)",a);assert(a>=0&&b>a);
vm.runInContext(source.slice(a,b),context,{filename:'actual-overview-selection-and-lifecycle.js'});
context.selectTrendModes(context.homeTrendModes);const counts=inputs.map(n=>n.events.get('change').size);
const basePointerCount=doc.events.get('pointerdown')?.size||0; const checkClosed=()=>{assert.equal(menu.hidden,true);assert.equal(trigger.getAttribute('aria-expanded'),'false');assert.equal(menu.parentNode,home);assert.equal(menu.nextSibling,sentinel);assert.equal(doc.activeElement,trigger);assert.equal(doc.events.get('pointerdown')?.size||0,basePointerCount);assert.equal(doc.events.get('keydown')?.size||0,0);};
for(const way of ['escape','outside','trigger']){
 trigger.emit('click');assert.equal(menu.hidden,false);assert.notEqual(menu.parentNode,home,'must portal original menu, not use clipped local absolute layout');assert.equal(trigger.getAttribute('aria-expanded'),'true');
 const popup=menu.parentNode.parentNode;assert.equal(popup.parentNode,doc.body);assert.ok(popup.className.includes('overview-trend-popover'));
 doc.emit('pointerdown',{target:inputs[0]});assert.equal(menu.hidden,false,'internal checkbox click must not close');
 const before=copies;inputs[0].checked=!inputs[0].checked;inputs[0].emit('change');assert.equal(copies,before+1);assert.equal(inputs[0].parentNode,menu);
 doc.documentElement.clientWidth=320;trigger.rect.left=15;w.emit('resize');assert.equal(popup.style.left,'15px');trigger.rect.left=25;w.emit('scroll');assert.equal(popup.style.left,'25px');
 if(way==='escape')doc.emit('keydown',{key:'Escape'});if(way==='outside')doc.emit('pointerdown',{target:doc.body});if(way==='trigger')trigger.emit('click');checkClosed();
 assert.deepEqual(inputs.map(n=>n.events.get('change').size),counts,'no duplicated change listeners');
}
context.selectTrendModes(['net_sales','payment_amount','refund_amount']);inputs[3].checked=true;inputs[3].emit('change');assert.equal(inputs[3].checked,false);assert.equal(context.homeTrendModes.length,3);assert.equal(toasts.length,1);
// Another real shared popover replaces this one and must also return same node.
trigger.emit('click');const other=w.TmallUI.popover({anchor:trigger,content:new Node()});assert.equal(menu.hidden,true);assert.equal(menu.parentNode,home);other.close();
const css=fs.readFileSync(path.join(root,'frontend/ui_demo/assets/components.css'),'utf8');const rule=css.match(/\.overview-trend-popover \.trend-picker__menu\s*\{([^}]+)\}/);assert.ok(rule,'scoped portal CSS required');for(const token of ['position: static','top: auto','right: auto','box-sizing: border-box','border: 0','box-shadow: none'])assert.ok(rule[1].includes(token),token);
assert.match(css,/\.ui-popover \{ position: fixed;/);assert.match(css,/\.ui-popover__panel \{[^}]*overflow: auto;/);
console.log(JSON.stringify({ok:true,closeModes:3,originalNodeRestored:true,checkboxListenersPreserved:true,maxSelected:3,resizeScroll:'actual primitive callbacks, synthetic rects only',css:'scoped rule checked',browser:'NOT RUN'}));
