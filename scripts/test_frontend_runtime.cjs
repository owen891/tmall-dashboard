const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const context = {
  URL,
  URLSearchParams,
  AbortController,
  window: { location: { origin: 'http://127.0.0.1:8770', href: 'http://127.0.0.1:8770/products' } },
};
context.window.window = context.window;
vm.createContext(context);

for (const file of [
  'frontend/ui_demo/assets/runtime/request-scope.js',
  'frontend/ui_demo/assets/runtime/event-scope.js',
  'frontend/ui_demo/assets/pages/products/query-model.js',
]) {
  vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, { filename: file });
}

const runtime = context.window.TmallRuntime;
const requests = runtime.createRequestScope();
const first = requests.begin('products');
const second = requests.begin('products');
assert.equal(first.signal.aborted, true);
assert.equal(first.isCurrent(), false);
assert.equal(second.isCurrent(), true);
second.finish();

const query = runtime.createProductsQuery({
  filterKeys: ['search', 'status', 'sort', 'order'],
});
const restored = query.readUrl('http://127.0.0.1:8770/products?search=chair&status=active&page=2&page_size=50&starred=1');
assert.deepEqual(restored.filters, { search: 'chair', status: 'active' });
assert.equal(restored.page, 2);
assert.equal(restored.pageSize, 50);
assert.equal(restored.starredOnly, true);
assert.equal(query.buildApiUrl({
  range: { startDate: '2026-09-20', endDate: '2026-09-20' },
  page: 2,
  pageSize: 50,
  filters: { search: 'chair', status: 'active' },
}), '/api/products?dim=daily&limit=50&offset=50&start=2026-09-20&end=2026-09-20&search=chair&status=active');

// --- shared HTML-escaping helper: single contract source --------------------
// assets/format.js is the one escaping contract for the demo shell; every
// adapter takes escapeHtml from it instead of rolling a local copy.
const formatFile = 'frontend/ui_demo/assets/format.js';
vm.runInContext(fs.readFileSync(path.join(root, formatFile), 'utf8'), context, { filename: formatFile });
const escapeHtml = context.window.DemoFormat && context.window.DemoFormat.escapeHtml;
assert.equal(typeof escapeHtml, 'function', 'format.js must export DemoFormat.escapeHtml');
assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
assert.equal(escapeHtml('"\'&<>'), '&quot;&#39;&amp;&lt;&gt;');
assert.equal(escapeHtml('Tom & Jerry'), 'Tom &amp; Jerry');
assert.equal(escapeHtml('普通商品标题 A-1'), '普通商品标题 A-1');
assert.equal(escapeHtml(null), '');
assert.equal(escapeHtml(undefined), '');
assert.equal(escapeHtml(0), '0');

// --- static guard: raw server data must not reach an HTML sink --------------
// Two filters keep this both meaningful and quiet:
//   1. only templates bound to innerHTML / outerHTML / insertAdjacentHTML /
//      document.write are inspected, so markup assembled into a plain string
//      is not reported;
//   2. a finding needs a receiver-qualified access to a known server field
//      (row.title, entity.shop_name, ...) that no escaping call wraps. A bare
//      name is only reported when the file never declares it, which is what
//      keeps local labels such as the destructured `${title}` in
//      analysis-live.js out of the report.
const ESCAPING_CALLS = [
  'escapeHtml', 'escape', 'esc', 'escapeAttr', 'escapeUrl', 'encodeURIComponent',
  'safeHttpUrl', 'formatValue', 'fmtWan', 'fmtPct1', 'money', 'moneyWan',
  'moneyCompact', 'numberWan', 'percent', 'ratio', 'roiTone',
];
const SERVER_FIELDS = [
  'title', 'product_id', 'product_name', 'item_title', 'item_id', 'shop_name',
  'shop_label', 'competitor_name', 'cate_name', 'keyword', 'campaign', 'crowds',
  'channels', 'message', 'runtime_status', 'record_count', 'source_tables',
  'missing_fields', 'name', 'id', 'label', 'status', 'value',
  'image_url', 'pic_url', 'detail_url',
];
const LOCAL_RECEIVERS = [
  'config', 'cfg', 'opts', 'options', 'column', 'columns', 'params', 'meta',
  'chartTypeLabels', 'metricLabels', 'dimensionLabels', 'PRESET_LABELS',
  'dataStateTitles', 'dataStateDetails', 'state', 'settings', 'labels',
  // `group` only ever iterates the literal PRESET_GROUPS label table.
  'group',
];

// Skip a regex literal that starts at `start` (the index of `/`), returning
// the index just past its closing slash. Character classes are honoured so a
// `/` inside `[...]` does not end the literal early. Needed because character
// classes such as /[&<>"']/ contain quote characters that would otherwise be
// mistaken for string delimiters and desync the whole scan.
const skipRegexLiteral = (src, start) => {
  let i = start + 1;
  let inClass = false;
  while (i < src.length) {
    const char = src[i];
    if (char === '\\') { i += 2; continue; }
    if (char === '\n') return i; // unterminated: treat the line as consumed
    if (char === '[') inClass = true;
    else if (char === ']') inClass = false;
    else if (char === '/' && !inClass) return i + 1;
    i += 1;
  }
  return i;
};

// A `/` begins a regex literal only where a value may start; after an
// identifier, `)`, `]` or a number it is division.
const startsRegexLiteral = (src, index) => {
  let back = index - 1;
  while (back >= 0 && /\s/.test(src[back])) back -= 1;
  if (back < 0) return true;
  return !/[\w$)\]]/.test(src[back]);
};

// Read the `${ ... }` body that starts at `start`, honouring nested braces,
// strings and template literals.
const readInterpolation = (src, start) => {
  let depth = 1;
  let i = start;
  while (i < src.length && depth > 0) {
    const char = src[i];
    if (char === '\\') { i += 2; continue; }
    if (char === "'" || char === '"') {
      const quote = char;
      i += 1;
      while (i < src.length && src[i] !== quote) { if (src[i] === '\\') i += 1; i += 1; }
      i += 1;
      continue;
    }
    if (char === '/' && src[i + 1] !== '/' && src[i + 1] !== '*' && startsRegexLiteral(src, i)) {
      i = skipRegexLiteral(src, i);
      continue;
    }
    if (char === '`') {
      // Nested template literal: recurse into its own `${...}` bodies so a
      // nested interpolation cannot swallow the remainder of the expression.
      i += 1;
      while (i < src.length && src[i] !== '`') {
        if (src[i] === '\\') { i += 2; continue; }
        if (src[i] === '$' && src[i + 1] === '{') {
          const nested = readInterpolation(src, i + 2);
          i = nested.end;
          continue;
        }
        i += 1;
      }
      i += 1;
      continue;
    }
    if (char === '{') depth += 1;
    else if (char === '}') depth -= 1;
    i += 1;
  }
  return { expr: src.slice(start, i - 1), end: i };
};

// Blank out string literals but keep the interpolations of nested templates,
// so `"${row.title}"` is still visible while pure markup is not.
const stripStrings = (text) => {
  let out = '';
  let i = 0;
  while (i < text.length) {
    const char = text[i];
    if (char === "'" || char === '"') {
      const quote = char;
      i += 1;
      out += '""';
      while (i < text.length && text[i] !== quote) { if (text[i] === '\\') i += 1; i += 1; }
      i += 1;
      continue;
    }
    if (char === '/' && text[i + 1] !== '/' && text[i + 1] !== '*' && startsRegexLiteral(text, i)) {
      i = skipRegexLiteral(text, i);
      out += 'RX';
      continue;
    }
    if (char === '`') {
      i += 1;
      out += 'TX';
      while (i < text.length && text[i] !== '`') {
        if (text[i] === '\\') { i += 2; continue; }
        if (text[i] === '$' && text[i + 1] === '{') {
          const nested = readInterpolation(text, i + 2);
          out += '${' + nested.expr + '}';
          i = nested.end;
          continue;
        }
        i += 1;
      }
      i += 1;
      continue;
    }
    out += char;
    i += 1;
  }
  return out;
};

// Drop `escapeHtml(...)` / `formatValue(...)` argument lists so escaped fields
// are not reported.
const stripEscapingCalls = (expr) => {
  const pattern = new RegExp(`(?:^|[^\\w$.])(?:${ESCAPING_CALLS.join('|')})\\s*\\(`);
  let current = expr;
  for (let pass = 0; pass < 16; pass += 1) {
    pattern.lastIndex = 0;
    const match = pattern.exec(current);
    if (!match) return current;
    let i = match.index + match[0].length;
    let depth = 1;
    while (i < current.length && depth > 0) {
      const char = current[i];
      if (char === "'" || char === '"') {
        const quote = char;
        i += 1;
        while (i < current.length && current[i] !== quote) { if (current[i] === '\\') i += 1; i += 1; }
        i += 1;
        continue;
      }
      if (char === '(') depth += 1;
      else if (char === ')') depth -= 1;
      i += 1;
    }
    current = current.slice(0, match.index) + ' SAFE ' + current.slice(i);
  }
  return current;
};

// Every identifier the file introduces itself: locals, params, destructuring
// targets and arrow parameters. A sensitive name in here is ours, not server
// data.
const declaredNames = (src) => {
  const names = new Set();
  const add = (name) => { if (name) names.add(name); };
  for (const match of src.matchAll(/\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g)) add(match[1]);
  for (const match of src.matchAll(/\b(?:const|let|var)\s*[{[][^}\]]*[}\]]\s*=/g)) {
    for (const name of match[0].matchAll(/[A-Za-z_$][\w$]*/g)) add(name[0]);
  }
  for (const match of src.matchAll(/\bfunction\s+[A-Za-z_$][\w$]*\s*\(([^)]*)\)/g)) {
    for (const name of match[1].matchAll(/[A-Za-z_$][\w$]*/g)) add(name[0]);
  }
  for (const match of src.matchAll(/\(([^()]*)\)\s*(?:=>|\{)/g)) {
    for (const name of match[1].matchAll(/[A-Za-z_$][\w$]*/g)) add(name[0]);
  }
  for (const match of src.matchAll(/\b([A-Za-z_$][\w$]*)\s*=>/g)) add(match[1]);
  return names;
};

const inspectInterpolation = (expr, declared) => {
  let text = stripStrings(expr);
  text = stripEscapingCalls(text);
  const findings = [];
  const property = new RegExp(`\\b([A-Za-z_$][\\w$]*)\\s*\\??\\.\\s*(${SERVER_FIELDS.join('|')})\\b`, 'g');
  let match;
  while ((match = property.exec(text))) {
    if (LOCAL_RECEIVERS.includes(match[1])) continue;
    // A field read used only as a truthiness test or a length test is never
    // emitted: `${x.title ? A : B}` and `${x.fields?.length ? A : B}` are safe,
    // and any real emission of the raw value is a second occurrence further
    // along the expression. `||`, `??` and `&&` are deliberately NOT exempt
    // because they forward the raw value into the output.
    const trailing = text.slice(match.index + match[0].length);
    if (/^\s*\?(?![\?.])/.test(trailing)) continue;
    if (/^\s*(?:\?\.|\.)\s*(?:length|size)\b/.test(trailing)) continue;
    findings.push(`.${match[2]} on ${match[1]}`);
  }
  const bare = new RegExp(`(^|[^\\w$.'"])([A-Za-z_$][\\w$]*)`, 'g');
  while ((match = bare.exec(text))) {
    if (!SERVER_FIELDS.includes(match[2])) continue;
    if (declared.has(match[2])) continue;
    findings.push(`bare ${match[2]}`);
  }
  return findings;
};

// Where an HTML sink token can begin. Each matcher is sticky, so it only
// fires at the exact position it is probed with.
const SINK_MATCHERS = [
  /(?:innerHTML|outerHTML)\s*=/y,
  /insertAdjacentHTML\s*\(/y,
  /document\s*\.\s*write(?:ln)?\s*\(/y,
];

// Find template literals bound to an HTML sink and inspect their `${...}`s.
// A template counts as sink-bound when the nearest sink token is still in the
// same statement, i.e. no `;` has been passed since. Semicolons, strings,
// comments and regex literals are tracked by this walk so markup punctuation
// and character classes cannot desync it.
const scanHtmlSinks = (src) => {
  const hits = [];
  const declared = declaredNames(src);
  let i = 0;
  let lastSemicolon = -1;
  let lastSinkEnd = -1;
  while (i < src.length) {
    const char = src[i];
    if (char === "'" || char === '"') {
      const quote = char;
      i += 1;
      while (i < src.length && src[i] !== quote) { if (src[i] === '\\') i += 1; i += 1; }
      i += 1;
      continue;
    }
    if (char === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i += 1; continue; }
    if (char === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i) + 2; continue; }
    if (char === '/' && startsRegexLiteral(src, i)) { i = skipRegexLiteral(src, i); continue; }
    if (char === ';') { lastSemicolon = i; i += 1; continue; }

    if (char !== '`') {
      let matched = false;
      for (const matcher of SINK_MATCHERS) {
        matcher.lastIndex = i;
        const sink = matcher.exec(src);
        if (sink && sink.index === i) {
          lastSinkEnd = i + sink[0].length;
          i = lastSinkEnd;
          matched = true;
          break;
        }
      }
      if (matched) continue;
      i += 1;
      continue;
    }

    const bound = lastSinkEnd > lastSemicolon;
    const open = i;
    i += 1;
    const interpolations = [];
    while (i < src.length && src[i] !== '`') {
      if (src[i] === '\\') { i += 2; continue; }
      if (src[i] === '$' && src[i + 1] === '{') {
        const nested = readInterpolation(src, i + 2);
        interpolations.push({ line: src.slice(0, i + 2).split('\n').length, expr: nested.expr });
        i = nested.end;
        continue;
      }
      i += 1;
    }
    i += 1;
    if (!bound) continue;

    const sinkLine = src.slice(0, open).split('\n').length;
    for (const item of interpolations) {
      const findings = inspectInterpolation(item.expr, declared);
      if (findings.length) {
        hits.push({
          sinkLine,
          line: item.line,
          detail: findings.join(', '),
          expr: item.expr.replace(/\s+/g, ' ').trim().slice(0, 120),
        });
      }
    }
  }
  return hits;
};

const listScripts = (dir, out = []) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) listScripts(full, out);
    else if (entry.name.endsWith('.js')) out.push(full);
  }
  return out;
};

const assetsDir = path.join(root, 'frontend', 'ui_demo', 'assets');
const scanned = listScripts(assetsDir);
assert.ok(scanned.length > 20, `expected to scan the demo adapters, found ${scanned.length} scripts`);
const sinkViolations = [];
for (const file of scanned) {
  const rel = path.relative(root, file).split(path.sep).join('/');
  for (const hit of scanHtmlSinks(fs.readFileSync(file, 'utf8'))) {
    sinkViolations.push(`${rel}:${hit.line} ${hit.detail} in \${${hit.expr}} (sink at line ${hit.sinkLine})`);
  }
}
assert.deepEqual(
  sinkViolations,
  [],
  `server data interpolated into HTML without escaping:\n  ${sinkViolations.join('\n  ')}`,
);

// Self-test: the guard must still catch the defect it was written for, and
// must stay quiet on local labels and static markup.
const SINK_CASES = [
  {
    name: 'attribute template',
    code: [
      'function render(rows) {',
      '  const node = document.getElementById("x");',
      '  node.innerHTML = `<tr><td>${row.title || row.product_id || "--"}</td></tr>`;',
      '}',
    ].join('\n'),
    expected: 1,
  },
  {
    name: 'nested map template',
    code: [
      'function render(products) {',
      '  const card = document.getElementById("c");',
      '  card.innerHTML = `<tbody>${products.map((p) => `<tr><td>${p.title}</td></tr>`).join("")}</tbody>`;',
      '}',
    ].join('\n'),
    expected: 1,
  },
  {
    name: 'insertAdjacentHTML',
    code: [
      'function render(entity) {',
      '  document.body.insertAdjacentHTML("beforeend", `<span>${entity.shop_name}</span>`);',
      '}',
    ].join('\n'),
    expected: 1,
  },
  {
    name: 'destructured local label',
    code: [
      'function render(data) {',
      '  const cards = document.getElementById("c");',
      '  cards.innerHTML = [["当前周期", data.value]]',
      '    .map(([title, value]) => `<div><span>${title}</span><strong>${value}</strong></div>`).join("");',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    name: 'local function parameter',
    code: [
      'function createChartCard(title) {',
      '  const card = document.getElementById("c");',
      '  card.innerHTML = `<h3 class="t">${title}</h3>`;',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    name: 'escaped server field',
    code: [
      'function render(product) {',
      '  const box = document.getElementById("b");',
      '  box.innerHTML = `<tr><td>${escapeHtml(product.title || product.product_id)}</td></tr>`;',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    name: 'static markup',
    code: [
      'function render() {',
      '  const box = document.getElementById("b");',
      '  box.innerHTML = \'<div class="empty"><span style="color:red">暂无数据</span></div>\';',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    name: 'server field outside a sink',
    code: [
      'function readOnly(rows) {',
      '  const cells = rows.map((row) => `<td>${row.title}</td>`);',
      '  return cells;',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    // The emitted value is escaped; only the ternary test reads the raw field,
    // so this must not be reported (real case: creative-board-live.js:59).
    name: 'field used only as a ternary test',
    code: [
      'function render(product) {',
      '  const box = document.getElementById("b");',
      '  box.innerHTML = `<td>${product.image_url ? `<img src="${esc(product.image_url)}">` : "<span>--</span>"}</td>`;',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    // `${quality.fields?.length ? ...}` is a length test, not an emission
    // (real case: analysis-live.js:284).
    name: 'field used only as a length test',
    code: [
      'function render(quality) {',
      '  const box = document.getElementById("b");',
      '  box.innerHTML = `${quality.missing_fields?.length ? `缺少：${escapeHtml(quality.missing_fields.join("、"))}` : "无"}`;',
      '}',
    ].join('\n'),
    expected: 0,
  },
  {
    // `||` forwards the raw value into the output, so this must still fail even
    // though a ternary also appears in the same interpolation.
    name: 'field forwarded by || into the output',
    code: [
      'function render(row) {',
      '  const box = document.getElementById("b");',
      '  box.innerHTML = `<td>${row.title || row.product_id}</td>`;',
      '}',
    ].join('\n'),
    expected: 1,
  },
];
for (const testCase of SINK_CASES) {
  const found = scanHtmlSinks(testCase.code);
  assert.equal(
    found.length,
    testCase.expected,
    `sink guard self-test "${testCase.name}": expected ${testCase.expected} finding(s), got ${found.length}` +
      (found.length ? ` (${found.map((hit) => hit.detail).join('; ')})` : ''),
  );
}

console.log('FRONTEND_RUNTIME_OK');
