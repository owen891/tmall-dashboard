# Promotion Alerts and Field Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build five isolated promotion field-template workspaces, a recursive AND/OR alert builder with recommended templates, and product-image lookup by product ID.

**Architecture:** Keep semantic page structure and mock rows in `promotion.html`, move promotion interaction state into a focused `promotion.js`, and keep shared responsive presentation in `components.css`. Model alert rules as recursive groups and field templates as a map keyed by promotion view so view changes cannot leak template state.

**Tech Stack:** Static HTML5, shared CSS tokens, vanilla JavaScript, Lucide icons, Node.js structural validator, in-app browser smoke testing.

---

### Task 1: Lock the new structure with failing validation

**Files:**
- Modify: `scripts/validate_ui_demos.cjs`
- Test: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: Add structural assertions for the approved behavior**

Add promotion-only assertions that require the dedicated script, five template scopes, recursive group controls, recommended templates, and image states:

```js
assert(html.includes('../assets/promotion.js'), `${relative}: missing promotion interaction module`);
for (const scope of ['products', 'keywords', 'audience', 'creative', 'content']) {
  assert(html.includes(`data-promotion-template-scope="${scope}"`), `${relative}: missing ${scope} field-template scope`);
}
assert(html.includes('data-rule-builder') && html.includes('data-rule-group'), `${relative}: missing nested alert rule builder`);
assert(html.includes('data-add-rule-condition') && html.includes('data-add-rule-group'), `${relative}: missing rule group controls`);
for (const preset of ['低效消耗', '高点击低转化', '高花费零成交', '曝光不足', '点击异常']) {
  assert(html.includes(preset), `${relative}: missing alert preset ${preset}`);
}
assert(html.includes('data-product-image-id="985897754523"'), `${relative}: missing first linked product image`);
assert(html.includes('data-product-image-id="1011889511510"'), `${relative}: missing second linked product image`);
assert(html.includes('data-product-unlinked="971290805262"'), `${relative}: missing explicit unlinked product state`);
```

- [ ] **Step 2: Run the validator and confirm it fails for the missing feature**

Run: `node scripts/validate_ui_demos.cjs`

Expected: FAIL with missing promotion module/template/rule-builder assertions.

- [ ] **Step 3: Commit the failing test**

```bash
git add scripts/validate_ui_demos.cjs
git commit -m "test: define promotion template and alert structure"
```

### Task 2: Add five view-specific field-template surfaces and product identity

**Files:**
- Modify: `docs/ui_demo/pages/promotion.html`
- Create: `docs/ui_demo/assets/promotion.js`
- Modify: `docs/ui_demo/assets/components.css`
- Test: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: Add one field-template toolbar to every promotion view**

Each view receives the same semantic shell with its own scope:

```html
<div class="promotion-template-bar" data-promotion-template-scope="products">
  <div class="promotion-template-bar__status">
    <span>字段模板</span>
    <strong data-active-field-template>商品诊断</strong>
    <span data-visible-field-count>5 个字段</span>
  </div>
  <div class="promotion-template-bar__actions">
    <select class="select" data-field-template-select aria-label="选择推广商品字段模板"></select>
    <button class="button" type="button" data-manage-field-template>
      <i data-lucide="columns-3"></i>选择字段
    </button>
  </div>
</div>
```

Repeat with scopes `keywords`, `audience`, `creative`, and `content`. Give every table header and cell a `data-field="..."` key so template application can hide and show complete columns.

- [ ] **Step 2: Add a single reusable field manager dialog**

```html
<dialog class="modal-form panel promotion-field-dialog" data-promotion-field-dialog aria-labelledby="promotionFieldTitle">
  <div class="modal-form__header">
    <div><h3 id="promotionFieldTitle">选择字段</h3><p class="panel__hint" data-field-dialog-scope-label></p></div>
    <button class="button button--ghost" type="button" data-close-field-dialog aria-label="关闭"><i data-lucide="x"></i></button>
  </div>
  <div class="field-group-grid" data-promotion-field-options></div>
  <div class="promotion-template-save">
    <input class="input" data-promotion-template-name placeholder="输入自定义模板名称">
    <button class="button" type="button" data-save-promotion-template>另存模板</button>
  </div>
  <div class="saved-template-list" data-promotion-saved-templates></div>
  <div class="modal-form__footer">
    <button class="button" type="button" data-close-field-dialog>取消</button>
    <button class="button button--primary" type="button" data-apply-promotion-fields>应用字段</button>
  </div>
</dialog>
```

- [ ] **Step 3: Render linked and unlinked product identities**

Use the exact product-operation image URLs for `985897754523` and `1011889511510`. Render the third row as an explicit non-image placeholder:

```html
<div class="product-identity" data-product-image-id="985897754523">
  <img class="product-thumb" src="..." alt="中古风玄关装饰摆件商品主图">
  <div class="product-title"><strong>中古风玄关装饰摆件放钥匙收纳</strong><span>商品主体 985897754523</span></div>
</div>
<div class="product-identity" data-product-unlinked="971290805262">
  <span class="product-thumb product-thumb--placeholder"><i data-lucide="image-off"></i></span>
  <div class="product-title"><strong>中古风仿藤编桌面抽屉收纳盒</strong><span>未关联商品运营 · 971290805262</span></div>
</div>
```

- [ ] **Step 4: Implement isolated field-template state in `promotion.js`**

Define `fieldCatalogs`, `systemTemplates`, and `customTemplates` keyed by view. The central application function only queries the active view:

```js
const promotionViews = ['products', 'keywords', 'audience', 'creative', 'content'];
const state = {
  activeView: 'products',
  activeTemplate: Object.fromEntries(promotionViews.map((view) => [view, 'default'])),
  customTemplates: Object.fromEntries(promotionViews.map((view) => [view, []])),
};

function applyFields(view, fieldKeys) {
  const panel = document.querySelector(`[data-promotion-view="${view}"]`);
  panel.querySelectorAll('[data-field]').forEach((cell) => {
    cell.hidden = !fieldKeys.includes(cell.dataset.field);
  });
}
```

Implement system-template selection, checkbox synchronization, unique custom-template names within the current view, custom-template deletion confirmation, current-name/count feedback, and an `aria-live` toast.

- [ ] **Step 5: Run structural validation**

Run: `node scripts/validate_ui_demos.cjs`

Expected: promotion module, five scopes, and product-image assertions pass; rule-builder assertions may still fail until Task 3.

- [ ] **Step 6: Commit field-template and product identity work**

```bash
git add docs/ui_demo/pages/promotion.html docs/ui_demo/assets/promotion.js docs/ui_demo/assets/components.css scripts/validate_ui_demos.cjs
git commit -m "feat: add promotion field templates and product images"
```

### Task 3: Replace the fixed ROI form with a recursive alert builder

**Files:**
- Modify: `docs/ui_demo/pages/promotion.html`
- Modify: `docs/ui_demo/assets/promotion.js`
- Modify: `docs/ui_demo/assets/components.css`
- Test: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: Replace the drawer body with template, rule, and execution sections**

```html
<section class="promotion-alert-presets" aria-labelledby="alertPresetTitle">
  <h4 id="alertPresetTitle">推荐预警模板</h4>
  <div class="promotion-alert-presets__list" data-alert-presets>
    <button type="button" class="template-option" data-alert-preset="low-efficiency">低效消耗</button>
    <button type="button" class="template-option" data-alert-preset="click-no-conversion">高点击低转化</button>
    <button type="button" class="template-option" data-alert-preset="spend-no-order">高花费零成交</button>
    <button type="button" class="template-option" data-alert-preset="low-impression">曝光不足</button>
    <button type="button" class="template-option" data-alert-preset="click-anomaly">点击异常</button>
  </div>
</section>
<section class="rule-builder" data-rule-builder aria-label="预警条件">
  <div data-rule-group></div>
</section>
```

Add alert name, observation days, severity, suggested action, enabled checkbox, custom-template name, save-template action, and final save button.

- [ ] **Step 2: Define typed fields, operators, and recursive rule state**

```js
const alertFields = {
  roi: { label: 'ROI', type: 'number', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  spend: { label: '花费', type: 'currency', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  impressions: { label: '展现量', type: 'integer', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  clicks: { label: '点击量', type: 'integer', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  ctr: { label: 'CTR', type: 'percent', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  cpc: { label: 'CPC', type: 'currency', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  transactionAmount: { label: '成交金额', type: 'currency', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  transactionCount: { label: '成交笔数', type: 'integer', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
  conversionRate: { label: '转化率', type: 'percent', operators: ['lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between'] },
};

const createCondition = (field = 'roi', operator = 'lt', value = '') => ({
  id: crypto.randomUUID(), type: 'condition', field, operator, value, secondValue: '',
});
const createGroup = (logic = 'and', children = [createCondition()]) => ({
  id: crypto.randomUUID(), type: 'group', logic, children,
});
```

- [ ] **Step 3: Implement recursive rendering and mutation**

Render every group with an AND/OR segmented control, child conditions, child groups, `data-add-rule-condition`, `data-add-rule-group`, and delete buttons. Mutations locate nodes recursively by ID, then rerender. Deleting the final root condition replaces it with `createCondition()`.

- [ ] **Step 4: Add presets, summaries, validation, and custom alert templates**

Preset `low-efficiency` must load:

```js
createGroup('and', [
  createCondition('spend', 'gt', 1000),
  createCondition('roi', 'lt', 3),
]);
```

The example scenario must be constructible as:

```js
createGroup('and', [
  createCondition('roi', 'lt', 3),
  createGroup('or', [
    createCondition('clicks', 'gt', 500),
    createCondition('spend', 'gt', 1000),
  ]),
]);
```

Build a readable summary after every mutation. Disable final save while any condition lacks a numeric value, while a `between` condition lacks its second value, or while the alert name is empty. On save failure focus the first invalid input; on success show the toast and close the drawer.

- [ ] **Step 5: Run the validator and confirm all structural assertions pass**

Run: `node scripts/validate_ui_demos.cjs`

Expected: `UI demo validation passed for 5 pages.`

- [ ] **Step 6: Commit the alert builder**

```bash
git add docs/ui_demo/pages/promotion.html docs/ui_demo/assets/promotion.js docs/ui_demo/assets/components.css scripts/validate_ui_demos.cjs
git commit -m "feat: add nested promotion alert rules"
```

### Task 4: Responsive styling and interaction verification

**Files:**
- Modify: `docs/ui_demo/assets/components.css`
- Test: `docs/ui_demo/pages/promotion.html`

- [ ] **Step 1: Add stable desktop and mobile dimensions**

Style the field bars, field dialog, preset list, group nesting, condition grid, product placeholder, summary, and toast. Use bounded grid tracks and convert every condition row to a one-column stack below 620px. Keep the drawer width within the viewport and make its body vertically scrollable.

- [ ] **Step 2: Run static checks**

Run: `node scripts/validate_ui_demos.cjs`

Expected: `UI demo validation passed for 5 pages.`

Run: `git diff --check`

Expected: no output.

- [ ] **Step 3: Verify field-template isolation in the browser**

At `http://127.0.0.1:4177/pages/promotion.html`, apply a product template, switch to keywords, save a keyword-only custom template, then return to products. Confirm product template name and columns are unchanged and the keyword custom template does not appear in product templates.

- [ ] **Step 4: Verify recursive alert behavior in the browser**

Create `ROI < 3 AND (点击量 > 500 OR 花费 > 1000)`. Confirm the summary matches, field changes update operators, invalid rules disable save, each recommended preset loads, and a custom alert template can be saved and reapplied.

- [ ] **Step 5: Verify product images and responsive rendering**

Confirm the first two product images load, the third row says `未关联商品运营`, and no fake image request is made for `971290805262`. Capture desktop and mobile screenshots and check for clipped text, overlapping controls, horizontal viewport overflow, and blank images.

- [ ] **Step 6: Check console output**

Expected: no uncaught JavaScript errors and no missing local asset requests.

- [ ] **Step 7: Commit final responsive fixes**

```bash
git add docs/ui_demo/pages/promotion.html docs/ui_demo/assets/promotion.js docs/ui_demo/assets/components.css scripts/validate_ui_demos.cjs
git commit -m "fix: harden promotion controls across viewports"
```
