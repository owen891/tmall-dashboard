const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const i=process.argv.indexOf('--root'),root=path.resolve(i<0?path.join(__dirname,'..'):process.argv[i+1]);
const read=f=>fs.readFileSync(path.join(root,'frontend/ui_demo/assets',f),'utf8');
const shell=read('shell.css');
function last(css,selector,prop){let out;for(const m of css.replace(/\/\*[\s\S]*?\*\//g,'').matchAll(/([^{}]+)\{([^{}]*)\}/g)){if(m[1].split(',').map(x=>x.trim()).includes(selector)){for(const d of m[2].split(';')){const k=d.indexOf(':');if(d.slice(0,k).trim()===prop)out=d.slice(k+1).trim();}}}return out;}
const tests=[
 ['sidebar line removed',()=>assert.equal(last(shell,'.demo-nav__item[aria-current="page"]','border-left'),'0')],
 ['collapsed sidebar marker removed',()=>assert.equal(last(shell,'body.demo-sidebar-collapsed .demo-nav__item[aria-current="page"]::before','content'),'none')],
 ['period controls have no underline',()=>{for(const s of ['.demo-period__inline button.is-active','.demo-period__inline-custom.is-active'])assert.equal(last(shell,s,'box-shadow'),'none');}],
 ['tabs retain selection without strokes',()=>{for(const [f,s] of [['category-dashboard.css','.dashboard-mode-tabs button.is-active'],['period-review.css','.pr-workbench-tabs button.is-active'],['themes/product-domain.css','.product-workbench__tab[aria-selected="true"]']])assert.equal(last(read(f),s,'border-bottom-color'),'transparent');}],
 ['compact native navigation',()=>{assert.equal(last(shell,'.demo-nav__item','min-height'),'var(--control-height-sm)');assert.equal(last(shell,'.demo-nav__item:hover','transform'),'none');assert.equal(last(shell,'body:not(.demo-sidebar-collapsed) .demo-sidebar','width'),'224px');}],
 ['selection background and safety affordances retained',()=>{assert.equal(last(shell,'.demo-nav__item[aria-current="page"]','background'),'var(--brand-tint)');assert.ok(shell.includes('outline: 2px solid var(--focus-ring)'));assert.ok(shell.includes('box-shadow: var(--anchor-ring)'));}],
];let failures=0;for(const [name,run] of tests){try{run();console.log('PASS '+name);}catch(e){failures++;console.log('FAIL '+name+': '+e.message.split('\n')[0]);}}console.log(`RESULT ${tests.length-failures}/${tests.length} passed; ${failures} failed`);process.exitCode=failures?1:0;
