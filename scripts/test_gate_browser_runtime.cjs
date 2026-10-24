// Pure mocked launch: no browser executable, HTTP client or child process runs.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const gate = require('./gate_browser.cjs');
const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'gate-browser-contract-')));
const browserRoot = path.join(root, 'dedicated');
fs.mkdirSync(browserRoot);
const browser = path.join(browserRoot, 'fixture-not-executable');
fs.writeFileSync(browser, 'NOT AN EXECUTABLE');
const scope = { root, browser, browser_root: browserRoot, base: 'http://127.0.0.1:49123', nonce: 'a'.repeat(48) };
const marker = path.join(root, 'scope.json');
fs.writeFileSync(marker, JSON.stringify(scope));
const env = { TMALL_GATE_ROOT: root, TMALL_GATE_BROWSER_SCOPE: marker, TMALL_GATE_NONCE: scope.nonce,
  TMALL_SMOKE_BASE: scope.base, TMALL_CHROME: browser, TMALL_CHROME_PATH: browser, PW_CHROMIUM: browser };
const saved = { ...process.env };
async function main() {
  assert.throws(() => gate.loadScope({}), /ISOLATED_GATE_SCOPE_REQUIRED/);
  assert.equal(gate.loadScope(env).browser, browser);
  for (const mutation of [{ TMALL_CDP_PORT: '9223' }, { TMALL_CHROME: 'user.exe' },
    { TMALL_GATE_NONCE: 'foreign' }, { TMALL_SMOKE_BASE: 'http://127.0.0.1:5000' }]) {
    assert.throws(() => gate.loadScope({ ...env, ...mutation }));
  }
  for (const base of ['http://127.0.0.1:9223', 'http://127.0.0.1:5000', 'https://example.com', 'http://localhost:49123']) {
    fs.writeFileSync(marker, JSON.stringify({ ...scope, base }));
    assert.throws(() => gate.loadScope({ ...env, TMALL_SMOKE_BASE: base }), /UNSAFE_GATE_BASE/);
  }
  fs.writeFileSync(marker, JSON.stringify(scope));
  assert.throws(() => gate.safeSocketUrl('ws://127.0.0.1:9223/devtools/page/x', 49123), /FOREIGN_CDP/);
  assert.throws(() => gate.safeSocketUrl('ws://remote.invalid:49123/devtools/page/x', 49123), /FOREIGN_CDP/);
  Object.assign(process.env, env);
  delete process.env.TMALL_CDP_PORT;
  const launchedOptions = [];
  const chromium = gate.gateChromium({ playwright: { chromium: { launch: options => {
    launchedOptions.push(options); return Promise.resolve('MOCK_BROWSER');
  } } } });
  assert.throws(() => chromium.launch({ channel: 'chrome' }), /BROWSER_OVERRIDE/);
  assert.throws(() => chromium.launch({ args: ['--remote-debugging-port=9223'] }), /BROWSER_OVERRIDE/);
  assert.throws(() => chromium.launch({ args: ['--user-data-dir=user-profile'] }), /BROWSER_OVERRIDE/);
  assert.throws(() => chromium.launch({ args: ['--no-sandbox'] }), /BROWSER_OVERRIDE/);
  assert.throws(() => chromium.launch({ chromiumSandbox: false }), /BROWSER_OVERRIDE/);
  assert.throws(() => chromium.launch({ ignoreDefaultArgs: true }), /BROWSER_OVERRIDE/);
  assert.equal(launchedOptions.length, 0);
  assert.equal(await chromium.launch({ headless: false }), 'MOCK_BROWSER');
  assert.equal(launchedOptions[0].headless, true);
  assert.equal(launchedOptions[0].chromiumSandbox, true);
  assert.equal(launchedOptions[0].executablePath, browser);
  assert.equal(launchedOptions[0].env.TMPDIR, root);
  let launched = 0, killed = 0;
  const mockSpawn = (executable, args, spawnOptions) => {
    launched++;
    assert.equal(executable, browser);
    assert(args.includes('--remote-debugging-port=0'));
    assert(!args.includes('--no-sandbox'));
    if (spawnOptions) {
      assert.equal(spawnOptions.windowsHide, true);
      assert(Array.isArray(spawnOptions.stdio));
      fs.writeSync(spawnOptions.stdio[2], 'MOCK_STDERR_NOT_DISCARDED\n');
    }
    const profile = args.find(arg => arg.startsWith('--user-data-dir=')).split('=').slice(1).join('=');
    assert(path.relative(root, profile).startsWith('cdp-profile-'));
    fs.writeFileSync(path.join(profile, 'DevToolsActivePort'), '49234\n/devtools/browser/fixture-owner\n');
    const child = new EventEmitter();
    child.exitCode = null;
    child.kill = () => { killed++; child.exitCode = 0; child.emit('exit', 0); };
    return child;
  };
  const options = { spawn: mockSpawn, getJson: async (port, route) => {
    assert.equal(port, 49234); assert.equal(route, '/json/version');
    return JSON.stringify({ webSocketDebuggerUrl: 'ws://127.0.0.1:49234/devtools/browser/fixture-owner' });
  }, sleep: async () => {} };
  await assert.rejects(gate.launchGateChrome('http://127.0.0.1:9223', options), /BASE_OWNER_MISMATCH/);
  assert.equal(launched, 0);
  const owned = await gate.launchGateChrome(scope.base, options);
  assert.equal(owned.port, 49234);
  assert.equal(fs.readFileSync(owned.diagnostics.stderr, 'utf8'), 'MOCK_STDERR_NOT_DISCARDED\n');
  await owned.close(); await owned.close();
  assert.equal(killed, 1);
  await assert.rejects(gate.launchGateChrome(scope.base, { ...options, getJson: async () => JSON.stringify({
    webSocketDebuggerUrl: 'ws://127.0.0.1:49234/devtools/browser/FOREIGN' }) }), /CDP_OWNER_MISMATCH/);
  assert.equal(killed, 2);
  await assert.rejects(gate.launchGateChrome(scope.base, { ...options, spawn: () => { throw new Error('SPAWN_FAILED'); } }), /SPAWN_FAILED/);
  const signaled = await gate.launchGateChrome(scope.base, { ...options, spawn: (exe, args) => {
    const child = mockSpawn(exe, args);
    child.kill = () => { child.signalCode = 'SIGTERM'; };
    return child;
  } });
  await signaled.close();
  await assert.rejects(gate.launchGateChrome(scope.base, { ...options, spawn: () => {
    const child = new EventEmitter(); child.exitCode = null;
    child.kill = () => { throw new Error('MUST_NOT_KILL_UNSPAWNED_CHILD'); };
    queueMicrotask(() => child.emit('error', new Error('ASYNC_SPAWN_FAILED')));
    return child;
  } }), /ASYNC_SPAWN_FAILED/);
  await assert.rejects(gate.launchGateChrome(scope.base, { ...options, spawn: (exe, args, opts) => {
    const child = mockSpawn(exe, args, opts); child.exitCode = 13; return child;
  } }), error => error.message.includes('OWNED_BROWSER_EXITED') && error.message.includes('MOCK_STDERR_NOT_DISCARDED')
    && error.message.includes('"exitCode":13'));
  const reports = fs.readdirSync(path.join(root, 'browser-diagnostics')).flatMap(name => {
    const file = path.join(root, 'browser-diagnostics', name, 'failure.json');
    return fs.existsSync(file) ? [JSON.parse(fs.readFileSync(file, 'utf8'))] : [];
  });
  assert(reports.some(report => report.exitCode === 13 && report.stderrTail.includes('MOCK_STDERR_NOT_DISCARDED')));
  assert.equal(fs.readdirSync(root).filter(name => name.startsWith('cdp-profile-')).length, 0);
  console.log('GATE_BROWSER_MOCK_OK: scope, production ports, executable, profile, dynamic CDP, foreign owner, cleanup');
}
main().finally(() => {
  for (const key of Object.keys(process.env)) if (!(key in saved)) delete process.env[key];
  Object.assign(process.env, saved);
  fs.rmSync(root, { recursive: true, force: true });
}).catch(error => { console.error(error); process.exitCode = 1; });
