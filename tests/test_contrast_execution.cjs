const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const sourcePath=path.resolve(process.argv[2]||path.join(__dirname,'../scripts/audit_ui_contrast.cjs'));
const raw=fs.readFileSync(sourcePath,'utf8');
assert.equal((raw.match(/chromium.launch\(\{ headless: true \}\)/g)||[]).length,3);
assert.match(raw,/assertBase\(BASE\)/);assert.match(raw,/require\('\.\/gate_browser.cjs'\)/);
assert.doesNotMatch(raw,/no-sandbox|executablePath|connectOverCDP/);
const source=raw.replace(/^\(async \(\) => \{$/gm,'__pending.push((async () => {').replace(/^\}\)\(\);$/gm,'})());');
async function run(mode,fault){
 let pages=0,closed=0,contexts=0,contextClosed=0,browserClosed=0,injected=false,timeoutSeen=false;
 const logs=[],calls=[],bad={path:'fixture',fs:14,ratio:1,need:4.5,disabled:false,color:'white',bg:'white',txt:'bad'};
 function fail(stage,id=1){if(fault===stage&&id===1&&!injected){injected=true;throw Error('SEALED_'+stage);}}
 async function action(stage,id,options){calls.push([stage,options]);const probeId=stage==='click'?1:id;fail(stage,probeId);if(fault==='pending-'+stage&&probeId===1&&!injected){injected=true;assert.equal(options.timeout,5000);await new Promise((_,reject)=>setTimeout(()=>{timeoutSeen=true;reject(Error('SEALED_TIMEOUT_'+stage));},2));}}
 const browser={newContext:async()=>{fail('newContext');contexts++;return{
  setDefaultTimeout:n=>assert.equal(n,5000),addInitScript:async()=>fail('init'),
  newPage:async()=>{fail('newPage');const id=++pages;return{
   setDefaultTimeout:n=>assert.equal(n,5000),goto:async(url,opts)=>{assert.equal(opts.timeout,25000);fail('goto',id);},waitForTimeout:async()=>{},
   close:async()=>{closed++;fail('pageClose',id);},mouse:{move:async()=>fail('mouse',id)},keyboard:{press:async()=>fail('keyboard',id)},
   evaluate:async code=>{fail('evaluate',id);if(typeof code==='function')return String(code).includes('dataset.theme')?'light':[];
    if(code.includes('outlineWidth:'))return fault==='contrast'?{tag:'button',cls:'x',text:'x',focusMatch:true,focusVisible:true,outlineWidth:0,outlineStyle:'none',outlineColor:'black',outlineOffset:0,boxShadow:'none',bg:[255,255,255]}:null;
    return fault==='contrast'?[bad]:[];},
   locator:()=>({count:async()=>{fail('count',id);return fault==='absent'?0:1;},nth:()=>({isVisible:async()=>{fail('visible',id);return true;},hover:o=>action('hover',id,o),focus:o=>action('focus',id,o),click:o=>action('click',id,o),evaluate:async()=>{fail('scan',id);return fault==='contrast'?[bad]:[];}})})
  };},close:async()=>{contextClosed++;fail('contextClose');}
 };},close:async()=>{browserClosed++;fail('browserClose');}};
 const proc={argv:['node','audit',...(mode==='static'?[]:['--'+mode]),'--tabs','2'],env:{TMALL_SMOKE_BASE:'http://127.0.0.1:48881'},exitCode:0};
 const sandbox={__pending:[],process:proc,console:{log:(...v)=>logs.push(v.join(' '))},require:n=>{
  if(n==='node:path')return path;
  if(n==='./gate_browser.cjs')return{assertBase:b=>assert.equal(b,proc.env.TMALL_SMOKE_BASE),gateChromium:()=>({launch:async options=>{assert.deepEqual(JSON.parse(JSON.stringify(options)),{headless:true});fail('launch');return browser;}})};
  throw Error('FORBIDDEN_REQUIRE '+n);
 }};
 vm.runInNewContext(source,sandbox,{timeout:2000});const settled=await Promise.allSettled(sandbox.__pending);
 assert.equal(settled.filter(v=>v.status==='rejected').length,0,mode+':'+fault+' unhandled rejection');
 const clean=['clean','absent'].includes(fault);assert.equal(proc.exitCode,clean?0:1,mode+':'+fault);
 if(!clean&&fault!=='contrast')assert.equal(injected,true,mode+':'+fault+' injection missing');
 if(fault.startsWith('pending-'))assert.equal(timeoutSeen,true);
 assert.equal(closed,pages,'every acquired page close attempted');assert.equal(contextClosed,contexts,'every acquired context close attempted');assert.equal(browserClosed,fault==='launch'?0:1);
 if(!['launch','newContext','init','newPage'].includes(fault))assert.equal(pages,20,'no page removed');
 if(mode==='states')for(const [stage,o] of calls)assert.equal(o.timeout,5000,stage+' must be bounded');
 if(!clean&&fault!=='contrast')assert.ok(logs.some(v=>v.includes('[AUDIT_ERROR]')));
 return{mode,fault,exit:proc.exitCode,pages,closed,contexts,contextClosed,browserClosed,injected,timeoutSeen,logs};
}
(async()=>{const results=[];for(const mode of ['static','states','focus'])for(const fault of ['clean','contrast','goto','evaluate','launch','newContext','init','newPage','pageClose','contextClose','browserClose'])results.push(await run(mode,fault));
 for(const fault of ['hover','focus','click','scan','count','visible','mouse','pending-hover','pending-focus','pending-click','absent'])results.push(await run('states',fault));
 for(const fault of ['keyboard','mouse'])results.push(await run('focus',fault));
 console.log(JSON.stringify({passed:results.length,browser:0,network:0,results},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
