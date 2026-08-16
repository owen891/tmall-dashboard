# 字段预览与排序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将商品运营和推广分析字段弹窗统一改为“左侧选择字段、右侧预览并调整顺序”。

**Architecture:** 新增共享的 `field-selector.js` 原生组件，在组件内部维护一份有序字段 key 数组作为唯一草稿状态。左侧复选框只修改成员关系，右侧有序列表只修改顺序；商品运营与推广分析只传字段定义、初始顺序和变更回调，应用字段和保存模板均读取组件状态。

**Tech Stack:** 原生 HTML、CSS、JavaScript、Python `unittest` 契约测试、Playwright 浏览器门禁。

**Workspace constraint:** 当前工作区包含大量用户改动，本计划不创建提交；每个任务用定向测试和 `git diff` 代替 commit。

---

### Task 1: 锁定字段预览交互契约

**Files:**
- Modify: `tests/test_frontend_prd_contract.py`
- Modify: `scripts/browser_prd_gates.cjs`

- [x] **Step 1: 写失败的静态契约测试**

在 `FrontendPrdContractTests` 中新增两项测试，要求商品和推广弹窗都包含预览容器，脚本包含有序预览渲染函数，并且左侧字段渲染不再追加排序按钮。

```python
def test_products_field_selection_uses_a_separate_order_preview(self):
    page = self.read('frontend/ui_demo/pages/products.html')
    script = self.read('frontend/ui_demo/assets/products-live.js')
    self.assertIn('data-products-column-preview', page)
    self.assertIn('function renderColumnPreview', script)
    self.assertIn('data-products-preview-key', script)

def test_promotion_field_selection_uses_a_separate_order_preview(self):
    page = self.read('frontend/ui_demo/pages/promotion.html')
    script = self.read('frontend/ui_demo/assets/promotion-live.js')
    self.assertIn('data-promotion-field-preview', page)
    self.assertIn('function renderFieldPreview', script)
    self.assertIn('data-promotion-preview-key', script)
```

- [x] **Step 2: 运行测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTests.test_products_field_selection_uses_a_separate_order_preview tests.test_frontend_prd_contract.FrontendPrdContractTests.test_promotion_field_selection_uses_a_separate_order_preview -v
```

Expected: 两项均因缺少预览 DOM 和渲染函数而失败。

- [x] **Step 3: 扩展真实浏览器门禁**

在现有商品字段弹窗流程中断言：左侧无排序按钮、预览数量等于选中数量、新勾选字段追加到末尾、预览排序会改变应用后的表头顺序。推广字段弹窗执行同样断言，并增加 `TMALL_FIELD_PREVIEW_ONLY=1` 使相关流程可独立结束。

- [x] **Step 4: 运行浏览器门禁并确认 RED**

Run:

```powershell
$env:TMALL_SMOKE_BASE='http://127.0.0.1:8774'
$env:TMALL_FIELD_PREVIEW_ONLY='1'
node scripts/browser_prd_gates.cjs
```

Expected: 因预览容器不存在而失败。

### Task 2: 商品运营字段预览

**Files:**
- Create: `frontend/ui_demo/assets/field-selector.js`
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/components.css`

- [x] **Step 1: 增加双区域 DOM**

将字段分组容器与预览容器包进统一布局：

```html
<div class="field-selection-layout products-field-selection-layout">
  <section class="field-selection-pane" aria-labelledby="productsAvailableFieldsTitle">
    <div class="field-selection-pane__heading">
      <strong id="productsAvailableFieldsTitle">可选字段</strong>
      <span>勾选要展示的字段</span>
    </div>
    <div class="field-group-grid" data-products-column-options></div>
  </section>
  <section class="field-preview-pane" aria-labelledby="productsFieldPreviewTitle">
    <div class="field-selection-pane__heading">
      <strong id="productsFieldPreviewTitle">字段预览</strong>
      <span>按表格列顺序展示</span>
    </div>
    <ol class="field-order-preview" data-products-column-preview></ol>
  </section>
</div>
```

- [x] **Step 2: 使用数组维护弹窗草稿**

创建 `DemoFieldSelector.create()` 共享组件，由组件维护有序数组。商品页的 `selectedDialogColumns()` 调用组件 `getSelected()`，打开弹窗、套用模板、全选和清空调用组件 `setSelected()`。

```javascript
let columnDialogOrder = [];

function selectedDialogColumns() {
  return [...columnDialogOrder];
}
```

- [x] **Step 3: 实现预览渲染和排序**

新增 `renderColumnPreview()`，每一项写入 `data-products-preview-key`，显示序号、字段名、上移和下移按钮。按钮交换数组相邻元素后重新渲染预览；首尾按钮正确禁用。

- [x] **Step 4: 简化左侧字段渲染**

删除 `renderColumnOptions()` 中把箭头追加到 label 的逻辑。checkbox 变更时：选中则追加 key，取消则移除 key，然后渲染预览和状态。

- [x] **Step 5: 运行商品定向测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTests.test_products_field_selection_uses_a_separate_order_preview tests.test_frontend_prd_contract.FrontendPrdContractTests.test_products_column_dialog_supports_full_selection_and_custom_templates -v
```

Expected: PASS。

### Task 3: 推广分析字段预览

**Files:**
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/components.css`

- [x] **Step 1: 增加推广双区域 DOM**

复用 `field-selection-layout`、`field-selection-pane`、`field-preview-pane` 和 `field-order-preview`，预览容器使用 `data-promotion-field-preview`。

- [x] **Step 2: 使用数组维护当前 TAB 弹窗草稿**

复用 `DemoFieldSelector.create()`。打开弹窗时传入当前 TAB 字段分组并复制当前已选字段；套用内置或自定义模板时调用组件 `setSelected()`；`selectedDialogFields()` 调用组件 `getSelected()`。

```javascript
let fieldDialogOrder = [];

function selectedDialogFields() {
  return [...fieldDialogOrder];
}
```

- [x] **Step 3: 实现推广预览渲染和排序**

新增 `renderFieldPreview()`，写入 `data-promotion-preview-key`，按钮调整 `fieldDialogOrder`，并保持字段名称来自当前 TAB 定义。

- [x] **Step 4: 同步所有选择入口**

checkbox、全选、清空、内置模板和自定义模板均同时更新 `fieldDialogOrder`、左侧勾选状态、右侧预览和按钮禁用状态。

- [x] **Step 5: 运行推广定向测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTests.test_promotion_field_selection_uses_a_separate_order_preview tests.test_frontend_prd_contract.FrontendPrdContractTests.test_promotion_tabs_support_complete_field_settings_and_custom_templates -v
```

Expected: PASS。

### Task 4: 响应式布局与完整验证

**Files:**
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `scripts/browser_prd_gates.cjs`

- [x] **Step 1: 实现桌面双列和移动端单列**

桌面使用 `grid-template-columns: minmax(0, 1.45fr) minmax(220px, .55fr)`；预览列表独立滚动。`max-width: 700px` 时切换为一列，限制两个区域的最小/最大高度，确保底部操作区始终在弹窗内。

- [x] **Step 2: 运行真实浏览器字段门禁**

Run:

```powershell
$env:TMALL_SMOKE_BASE='http://127.0.0.1:8774'
$env:TMALL_FIELD_PREVIEW_ONLY='1'
node scripts/browser_prd_gates.cjs
```

Expected: 商品和推广预览交互通过，390x844 无横向溢出。

- [x] **Step 3: 运行完整相关测试和静态检查**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_promotion_api tests.test_frontend_prd_contract -v
node --check frontend/ui_demo/assets/products-live.js
node --check frontend/ui_demo/assets/promotion-live.js
```

Expected: 所有测试通过，两个脚本语法检查退出码为 0。

- [x] **Step 4: 浏览器人工验收**

在 `http://127.0.0.1:8774/products` 与 `http://127.0.0.1:8774/promotion` 检查桌面和 390x844：弹窗无横向溢出、左右/上下区域完整、排序后表头一致、控制台无错误。

- [x] **Step 5: 检查最终差异**

Run:

```powershell
git diff -- frontend/ui_demo/pages/products.html frontend/ui_demo/pages/promotion.html frontend/ui_demo/assets/products-live.js frontend/ui_demo/assets/promotion-live.js frontend/ui_demo/assets/components.css tests/test_frontend_prd_contract.py scripts/browser_prd_gates.cjs
```

Expected: 仅包含字段预览、排序状态、响应式样式和对应测试改动。
