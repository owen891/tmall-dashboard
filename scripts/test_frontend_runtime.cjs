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

console.log('FRONTEND_RUNTIME_OK');
