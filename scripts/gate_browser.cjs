'use strict';
// All real browser gates consume an owned runner scope; no user browser fallback.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { spawn } = require('node:child_process');

function inside(child, parent) {
  const relative = path.relative(parent, child);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}
function loadScope(env = process.env) {
  if (!env.TMALL_GATE_ROOT || !env.TMALL_GATE_BROWSER_SCOPE) throw new Error('ISOLATED_GATE_SCOPE_REQUIRED');
  const root = fs.realpathSync(env.TMALL_GATE_ROOT);
  const marker = fs.realpathSync(env.TMALL_GATE_BROWSER_SCOPE);
  if (!inside(marker, root)) throw new Error('SCOPE_OUTSIDE_GATE_ROOT');
  const scope = JSON.parse(fs.readFileSync(marker, 'utf8'));
  if (scope.root !== root || scope.nonce !== env.TMALL_GATE_NONCE || !/^[a-f0-9]{48}$/.test(scope.nonce)) throw new Error('SCOPE_OWNER_MISMATCH');
  const base = new URL(scope.base);
  const port = Number(base.port);
  if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || port <= 1023 || [5000, 9223].includes(port)
      || base.pathname !== '/' || base.username || base.password || base.search || base.hash) throw new Error('UNSAFE_GATE_BASE');
  if (env.TMALL_SMOKE_BASE !== scope.base) throw new Error('BASE_OWNER_MISMATCH');
  const browser = fs.realpathSync(scope.browser);
  if (!fs.statSync(browser).isFile() || !inside(browser, fs.realpathSync(scope.browser_root))) throw new Error('DEDICATED_BROWSER_REQUIRED');
  for (const name of ['TMALL_CHROME', 'TMALL_CHROME_PATH', 'PW_CHROMIUM']) {
    if (env[name] !== scope.browser) throw new Error('BROWSER_OWNER_MISMATCH');
  }
  if (env.TMALL_CDP_PORT) throw new Error('INHERITED_CDP_PORT_FORBIDDEN');
  return { ...scope, root, browser };
}
function assertBase(base, scope = loadScope()) {
  if (base.replace(/\/$/, '') !== scope.base.replace(/\/$/, '')) throw new Error('BASE_OWNER_MISMATCH');
  return scope;
}
function safeSocketUrl(url, port) {
  const parsed = new URL(url);
  if (parsed.protocol !== 'ws:' || parsed.hostname !== '127.0.0.1' || Number(parsed.port) !== port
      || !parsed.pathname.startsWith('/devtools/')) throw new Error('FOREIGN_CDP_TARGET');
  return url;
}
function getJson(port, pathname) {
  return new Promise((resolve, reject) => {
    const request = http.get({ host: '127.0.0.1', port, path: pathname, timeout: 2000 }, response => {
      let data = '';
      response.on('data', chunk => { data += chunk; });
      response.on('end', () => response.statusCode === 200 ? resolve(data) : reject(new Error('CDP_HTTP_ERROR')));
    });
    request.on('timeout', () => request.destroy(new Error('CDP_TIMEOUT')));
    request.on('error', reject);
  });
}
async function launchGateChrome(base, dependencies = {}) {
  const scope = assertBase(base);
  const launch = dependencies.spawn || spawn;
  const request = dependencies.getJson || getJson;
  const sleep = dependencies.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  const profile = fs.mkdtempSync(path.join(scope.root, 'cdp-profile-'));
  const diagnosticRoot = path.join(scope.root, 'browser-diagnostics');
  fs.mkdirSync(diagnosticRoot, { recursive: true });
  const diagnosticDirectory = fs.mkdtempSync(path.join(diagnosticRoot, 'launch-'));
  const diagnostics = { stdout: path.join(diagnosticDirectory, 'stdout.txt'),
    stderr: path.join(diagnosticDirectory, 'stderr.txt'), executable: scope.browser, profile };
  let stdoutFd, stderrFd;
  let child;
  try {
  stdoutFd = fs.openSync(diagnostics.stdout, 'wx');
  stderrFd = fs.openSync(diagnostics.stderr, 'wx');
  child = launch(scope.browser, ['--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--window-size=1440,900',
    '--disable-background-networking', '--disable-component-update', '--disable-sync', '--metrics-recording-only',
    `--user-data-dir=${profile}`, 'about:blank'], { stdio: ['ignore', stdoutFd, stderrFd], windowsHide: true });
  } catch (error) {
    fs.rmSync(profile, { recursive: true, force: true });
    throw error;
  } finally {
    if (stdoutFd !== undefined) fs.closeSync(stdoutFd);
    if (stderrFd !== undefined) fs.closeSync(stderrFd);
  }
  let launchError;
  child.once('error', error => { launchError = error; });
  let closed = false;
  const running = () => child.exitCode === null && !child.signalCode;
  const emergencyStop = () => { if (running()) child.kill('SIGKILL'); };
  process.once('exit', emergencyStop);
  async function close() {
    if (closed) return;
    if (launchError && !child.pid) {
      closed = true;
      process.removeListener('exit', emergencyStop);
      fs.rmSync(profile, { recursive: true, force: true });
      return;
    }
    if (running()) {
      child.kill();
      for (let n = 0; n < 40 && running(); n++) await sleep(50);
      if (running()) {
        child.kill('SIGKILL');
        for (let n = 0; n < 40 && running(); n++) await sleep(50);
      }
      if (running()) throw new Error('OWNED_BROWSER_DID_NOT_EXIT');
    }
    closed = true;
    process.removeListener('exit', emergencyStop);
    fs.rmSync(profile, { recursive: true, force: true });
  }
  try {
    for (let n = 0; n < 100; n++) {
      if (launchError) throw launchError;
      if (!running()) throw new Error('OWNED_BROWSER_EXITED');
      const active = path.join(profile, 'DevToolsActivePort');
      if (fs.existsSync(active)) {
        const [rawPort, browserPath] = fs.readFileSync(active, 'utf8').trim().split(/\r?\n/);
        const port = Number(rawPort);
        if (!Number.isInteger(port) || port <= 1023 || port > 65535 || [5000, 9223].includes(port)
            || !browserPath?.startsWith('/devtools/browser/')) throw new Error('UNSAFE_OWNED_CDP');
        const version = JSON.parse(await request(port, '/json/version'));
        if (new URL(safeSocketUrl(version.webSocketDebuggerUrl, port)).pathname !== browserPath) throw new Error('CDP_OWNER_MISMATCH');
        console.log('GATE_BROWSER_DIAGNOSTICS=' + diagnosticDirectory);
        return { child, port, close, diagnostics, httpGet: pathname => request(port, pathname) };
      }
      await sleep(50);
    }
    throw new Error('OWNED_CDP_TIMEOUT');
  } catch (error) {
    try { await close(); } catch (cleanupError) { error.message += '; cleanup=' + cleanupError.message; }
    const details = { ...diagnostics, pid: child.pid, exitCode: child.exitCode, signalCode: child.signalCode,
      stderrTail: fs.readFileSync(diagnostics.stderr, 'utf8').slice(-16384) };
    fs.writeFileSync(path.join(diagnosticDirectory, 'failure.json'), JSON.stringify(details, null, 2));
    error.message += '; diagnostics=' + JSON.stringify(details);
    throw error;
  }
}
function gateChromium(dependencies = {}) {
  const scope = loadScope();
  const { chromium } = dependencies.playwright || require(require.resolve('playwright', { paths: [path.join(__dirname, '..', 'desktop')] }));
  return { launch: options => {
    options = options || {};
    if (options.channel || options.ignoreDefaultArgs || options.chromiumSandbox === false
        || (options.executablePath && fs.realpathSync(options.executablePath) !== scope.browser)
        || (options.args || []).some(arg => /remote-debugging|user-data-dir|no-sandbox|disable.*sandbox/i.test(arg))) throw new Error('BROWSER_OVERRIDE_FORBIDDEN');
    return chromium.launch({ ...options, executablePath: scope.browser, headless: true,
      chromiumSandbox: true,
      env: { ...process.env, TEMP: scope.root, TMP: scope.root, TMPDIR: scope.root } });
  } };
}
/**
 * 页面清单：公开 checkout 只审计实际随仓库分发的页面。
 * 私有部署把额外页面登记在 data/private_edition.json（不进公开仓库）。
 */
function publicPages(names) {
  const fs = require('node:fs');
  const path = require('node:path');
  const root = path.resolve(__dirname, '..');
  const privateNames = new Set();
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'data', 'private_edition.json'), 'utf8'));
    for (const item of manifest.pages || []) privateNames.add(String(item));
  } catch (e) { /* 公开 checkout：无私有清单 */ }
  return names.filter((name) => !privateNames.has(name)
    && fs.existsSync(path.join(root, 'frontend', 'ui_demo', 'pages', `${name}.html`)));
}

module.exports = { loadScope, assertBase, safeSocketUrl, launchGateChrome, gateChromium, publicPages };
