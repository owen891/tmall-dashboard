// Pure Node/VM: no browser, HTTP, subprocess, credentials or production files.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/ui_demo/assets/shell.js'), 'utf8');
const start = source.indexOf('  const assetBase =');
const end = source.indexOf('  const liveAdapters =', start);
assert(start > 0 && end > start);
const loaded = [], reports = [];
let updates = 0;
const document = {
  currentScript: {src: 'http://fixture/assets/releases/' + 'a'.repeat(64) + '/shell.js'},
  baseURI: 'http://fixture/promotion', scripts: [],
  createElement: () => ({dataset: {}}),
  head: {appendChild(script) { loaded.push(script); script.onload(); }},
};
const window = {location: {href: 'http://fixture/promotion'}, TmallAssetUpdateRequired: () => updates++,
  TmallFrontendErrors: {report: (...args) => reports.push(args)}};
const context = {URL, Map, Promise, document, window, console};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + '\nglobalThis.load = loadScriptOnce;', context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  assert(loaded.length >= 5);
  assert(loaded.every(script => script.src.startsWith('http://fixture/assets/releases/' + 'a'.repeat(64) + '/')));
  assert(loaded.every(script => !script.src.includes('?v=')));
  document.currentScript.src = 'http://fixture/assets/releases/' + 'b'.repeat(64) + '/shell.js';
  await context.load('runtime/delayed.js');
  assert(loaded.at(-1).src.includes('/' + 'a'.repeat(64) + '/runtime/delayed.js'));
  const before = loaded.length;
  await context.load('runtime/delayed.js');
  assert.equal(loaded.length, before);
  document.head.appendChild = script => {loaded.push(script); script.onerror();};
  await assert.rejects(context.load('missing.js'), /UPDATE_REQUIRED/);
  assert.equal(updates, 1);
  assert.equal(reports.length, 1);
  assert(loaded.at(-1).src.includes('/' + 'a'.repeat(64) + '/missing.js')); // no fallback to B

  const helper = fs.readFileSync(path.join(root, 'utils/static_release.py'), 'utf8');
  const guard = helper.match(/UPDATE_GUARD = """<script[^>]*>([\s\S]*?)<\/script>"""/)[1];
  const nodes = new Map(), callbacks = {};
  let reloads = 0;
  const doc = {getElementById: id => nodes.get(id), createElement: () => ({setAttribute(){},appendChild(child){this.child=child;}}),
    documentElement: {appendChild(node){nodes.set(node.id,node);}}};
  const win = {location: {reload(){reloads++;}}, addEventListener: (name, callback) => {callbacks[name]=callback;}};
  vm.runInNewContext(guard, {document:doc,window:win});
  callbacks.error({target:{src:'http://fixture/assets/releases/retired/shell.js'}});
  assert.match(nodes.get('tmall-update-required').textContent, /刷新整个页面/);
  nodes.get('tmall-update-required').child.onclick();
  assert.equal(reloads,1);
  callbacks.error({target:{src:'http://fixture/unrelated.png'}});
  assert.equal(nodes.size,1);
  for(const name of ['version-check.js','desktop-integration.js']) {
    const text=fs.readFileSync(path.join(root,'frontend/ui_demo/assets',name),'utf8');
    assert(!text.includes("new URL('../api/version"));
    assert(text.includes("new URL('/api/version"));
  }
  console.log('STATIC_RELEASE_RUNTIME_OK');
})().catch(error => {console.error(error);process.exitCode=1;});
