# 天猫数据仪表盘 — 设计系统总规则

> 本文档是看板所有新增页面、功能、组件的统一设计规范。后续开发必须严格遵循，确保视觉、交互、数据结构的一致性。



***

## 一、技术栈与项目架构

### 1.1 技术栈



* **后端**：Python 3.14 + Flask + SQLite

* **前端**：原生 HTML/CSS/JavaScript（无框架）

* **图标**：Lucide（`lucide-1.8.0.min.js`）

* **图表**：ECharts 5.5.1（按需加载）

### 1.2 目录结构



```
tmall-dashboard/

├── app.py                    # Flask入口，create\_app()

├── wsgi.py                   # WSGI入口（生产用）

├── config.py                 # 配置

├── db.py                     # 数据库连接

├── api/                      # API层（每个模块一个文件，Blueprint）

│   ├── api\_response.py       # 统一返回格式（success/failure）

│   ├── products\_api.py

│   └── {module}\_api.py

├── services/                 # 业务逻辑层（import\_service、metrics\_service等）

├── repos/                    # 数据访问层（继承BaseRepo）

│   ├── base\_repo.py

│   └── {module}\_repo.py

├── models/                   # 常量与枚举（constants.py）

├── utils/                    # 工具函数

├── migrations/               # 数据库迁移脚本

├── scripts/                  # 构建/部署脚本

├── tests/                    # 单元测试

├── desktop/                  # Electron桌面端

├── packaging/                # 打包配置

├── data/                     # 数据文件

│   └── dashboard.db          # 主数据库

├── instance/                 # Flask实例目录

├── logs/                     # 日志

└── frontend/ui\_demo/

&#x20;   ├── pages/                # 页面HTML（每个页面一个文件）

&#x20;   │   ├── products.html

&#x20;   │   └── {page}.html

&#x20;   └── assets/               # 公共资源

&#x20;       ├── tokens.css        # 设计令牌（颜色/字体/间距）

&#x20;       ├── shell.css         # 布局（侧边栏/顶栏）

&#x20;       ├── components.css    # 组件样式

&#x20;       ├── api.js            # API客户端（DemoApi）

&#x20;       ├── navigation.js     # URL构建工具（DemoNavigation）

&#x20;       ├── labels.js         # 标签字典

&#x20;       ├── charts.js         # 图表封装

&#x20;       ├── shell.js          # 布局渲染+导航菜单+自动加载

&#x20;       ├── field-selector.js # 列选择器公共组件（DemoFieldSelector）

&#x20;       ├── field-template-manager.js # 字段模板管理

&#x20;       ├── product-detail-dialog.js  # 商品详情弹窗

&#x20;       ├── table-controls.js # 表格控件（shell.js自动加载）

&#x20;       ├── ui-components.js  # UI组件（shell.js自动加载）

&#x20;       └── {page}-live.js    # 页面逻辑（每个页面对应一个）
```

### 1.3 页面路由



* 前端页面：`/{page}`（如 `/products`、`/keyword-promotion`）

* API 接口：`/api/{module}/{action}`（如 `/api/products/list`）



***

## 二、设计令牌（Design Tokens）

所有颜色、字体、间距必须使用 CSS 变量，禁止硬编码。

### 2.1 颜色系统

**原色（Primitives）**



```
\--color-white: #ffffff

\--color-gray-50: #f5f5f5

\--color-gray-100: #f3f4f6

\--color-gray-200: #e5e7eb

\--color-gray-300: #d1d5db

\--color-gray-400: #9ca3af

\--color-gray-500: #6b7280

\--color-gray-700: #374151

\--color-gray-900: #111827
```

**语义色（Semantics）**



```
\--surface-page: var(--color-gray-50)       /\* 页面背景 \*/

\--surface-base: var(--color-white)         /\* 卡片/面板背景 \*/

\--surface-muted: var(--color-gray-100)     /\* 弱化背景 \*/

\--text-primary: var(--color-gray-900)      /\* 主文字 \*/

\--text-secondary: var(--color-gray-500)    /\* 次要文字 \*/

\--text-tertiary: var(--color-gray-400)     /\* 辅助文字 \*/

\--border-default: var(--color-gray-200)    /\* 边框 \*/

\--brand: #4f46e5                           /\* 品牌色（靛蓝） \*/

\--success: #10b981                         /\* 成功/好 \*/

\--warning: #f59e0b                         /\* 警告 \*/

\--danger: #ef4444                          /\* 危险/差 \*/

\--info: #3b82f6                            /\* 信息 \*/
```

**业务色使用规则**



* ROI ≥ 1 / 正向指标好 → `--success`（绿色）

* ROI < 1 / 负向指标差 → `--danger`（红色）

* 评级 S → 绿底深绿字，A → 蓝底深蓝字，B → 黄底深黄字，C → 红底深红字

* 标签 / 徽章 → `--surface-muted` 灰底灰字

### 2.2 字体系统



```
\--font-sans: "DM Sans", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui

\--font-display: "Space Grotesk", "Noto Sans SC", system-ui  /\* 标题/数字 \*/

\--font-mono: "JetBrains Mono", Consolas, monospace          /\* 代码/ID \*/

\--font-size-meta: 12px       /\* 辅助信息 \*/

\--font-size-secondary: 13px  /\* 次要文字 \*/

\--font-size-body: 14px       /\* 正文 \*/

\--font-size-label: 14px      /\* 标签/按钮 \*/

\--font-size-section: 17px    /\* 区块标题 \*/

\--font-size-title: 22px      /\* 页面标题 \*/

\--font-size-kpi: 26px        /\* KPI大数字 \*/
```

**使用规则**



* KPI 数值、金额、比率 → `--font-display` + `font-variant-numeric: tabular-nums`

* 商品 ID、编码 → `--font-mono`

* 正文 → `--font-sans`

### 2.3 间距系统



```
\--space-1: 4px

\--space-2: 8px

\--space-3: 12px

\--space-4: 16px

\--space-5: 20px

\--space-6: 24px

\--space-8: 32px
```

**使用规则**：元素内边距用 `--space-3/4`，元素间距用 `--space-2/3`，区块间距用 `--space-4/6`。

### 2.4 圆角与阴影



```
\--radius-sm: 8px      /\* 按钮/输入框/徽章 \*/

\--radius-md: 12px     /\* 面板/卡片 \*/

\--radius-lg: 16px     /\* 大卡片 \*/

\--radius-full: 999px  /\* 胶囊形 \*/

\--shadow-sm: 0 1px 2px rgb(17 24 39 / 0.04)

\--shadow-md: 0 2px 4px rgb(17 24 39 / 0.05)

\--shadow-lg: 0 8px 24px rgb(17 24 39 / 0.16)  /\* 弹窗 \*/
```



***

## 三、布局规范

### 3.1 页面标准结构

所有页面必须使用以下骨架：



```
\<body data-page="{page-name}">

&#x20; \<div class="demo-app">

&#x20;   \<aside class="demo-sidebar" data-shell-sidebar>\</aside>

&#x20;   \<div class="demo-main">

&#x20;     \<header class="demo-topbar" data-shell-header>\</header>

&#x20;     \<main class="demo-page">

&#x20;       \<!-- 页面内容 -->

&#x20;     \</main>

&#x20;   \</div>

&#x20; \</div>

\</body>
```



* `data-page` 属性必须填写，用于 shell.js 识别当前页面、加载对应的 live adapter

* 侧边栏和顶栏由 `shell.js` 自动渲染，不需要手动写内容

### 3.2 页面头部



```
\<div class="demo-page\_\_intro">

&#x20; \<div>

&#x20;   \<h2>页面标题\</h2>

&#x20;   \<p>页面副标题/说明\</p>

&#x20; \</div>

&#x20; \<div class="demo-page\_\_actions">

&#x20;   \<button class="button">操作按钮\</button>

&#x20; \</div>

\</div>
```

### 3.3 指标卡片（KPI 区）



```
\<section class="metric-grid">

&#x20; \<article class="metric-card">

&#x20;   \<div class="metric-card\_\_label">指标名称\</div>

&#x20;   \<div class="metric-card\_\_value">--\</div>

&#x20; \</article>

&#x20; \<!-- 4-6个卡片 -->

\</section>
```



* 默认 4 列网格，响应式自动收缩

* 数值用 `--font-size-kpi` + `--font-display`

### 3.4 面板（内容区）



```
\<section class="plain-panel panel">

&#x20; \<div class="panel\_\_header">

&#x20;   \<div>

&#x20;     \<h3 class="panel\_\_title">面板标题\</h3>

&#x20;     \<p class="panel\_\_hint">辅助说明\</p>

&#x20;   \</div>

&#x20;   \<div class="panel\_\_tools">

&#x20;     \<!-- 工具按钮 -->

&#x20;   \</div>

&#x20; \</div>

&#x20; \<!-- 面板内容 -->

\</section>
```



***

## 四、组件规范

### 4.1 按钮



```
\<button class="button">默认按钮\</button>

\<button class="button button--primary">主要按钮\</button>

\<button class="button button--ghost">幽灵按钮\</button>
```



* 主要操作（应用 / 保存 / 确认）→ `button--primary`

* 次要操作（重置 / 取消 / 关闭）→ `button`

* 图标按钮 → `button--ghost`

* 按钮内图标用 Lucide，文字与图标间距 `--space-2`

### 4.2 筛选器

**标准布局**：



```
\<div class="section-toolbar product-filters">

&#x20; \<div class="product-filters\_\_main">

&#x20;   \<label class="product-filters\_\_search">

&#x20;     \<i data-lucide="search">\</i>

&#x20;     \<input class="input" placeholder="搜索…">

&#x20;   \</label>

&#x20;   \<div class="product-filters\_\_core">

&#x20;     \<select class="select">\<option>筛选1\</option>\</select>

&#x20;     \<select class="select">\<option>筛选2\</option>\</select>

&#x20;   \</div>

&#x20;   \<div class="product-filters\_\_sort">

&#x20;     \<select class="select">\<option>排序字段\</option>\</select>

&#x20;     \<select class="select">\<option>降序\</option>\</select>

&#x20;   \</div>

&#x20; \</div>

&#x20; \<div class="product-filters\_\_actions">

&#x20;   \<button class="button" data-more-toggle>更多筛选\</button>

&#x20; \</div>

&#x20; \<div class="product-filters\_\_advanced" hidden>

&#x20;   \<!-- 更多筛选条件，3列网格 -->

&#x20; \</div>

\</div>
```

**规则**：



* 搜索框永远在最左

* 核心筛选（3-4 个）在中间

* 排序在右侧

* 不常用筛选放 "更多筛选" 展开区，默认隐藏

* 筛选变化**即时生效**，不需要 "查询" 按钮

* 搜索框回车触发

### 4.3 表格



```
\<div class="data-table-wrap data-table-wrap--discoverable">

&#x20; \<table class="data-table product-table">

&#x20;   \<thead>\<tr>\<!-- 表头 -->\</tr>\</thead>

&#x20;   \<tbody>\<!-- 数据行 -->\</tbody>

&#x20; \</table>

\</div>
```

**规则**：



* 表头可点击排序的列加 `data-sort="{field}"`

* 数值列右对齐，文字列左对齐

* 长文本用 `-webkit-line-clamp: 2` 截断

* 空数据显示 "加载中…"→"没有符合条件的数据"

* 加载失败显示错误信息（红色）

### 4.4 分页（服务端）



```
\<div class="section-toolbar table-controls table-controls--server">

&#x20; \<span class="panel\_\_hint table-controls\_\_summary">第 1 / 10 页，共 500 条\</span>

&#x20; \<label class="table-controls\_\_page-size">每页

&#x20;   \<select class="select">\<option>20\</option>\<option>50\</option>\</select>

&#x20;   行

&#x20; \</label>

&#x20; \<div class="table-controls\_\_nav">

&#x20;   \<button class="button table-controls\_\_button">上一页\</button>

&#x20;   \<button class="button table-controls\_\_button">下一页\</button>

&#x20; \</div>

\</div>
```



* 分页参数：`page`（从 1 开始）、`page_size`（默认 50）

* 首页禁用 "上一页"，末页禁用 "下一页"

### 4.5 弹窗（Modal）



```
\<dialog class="modal-form panel" data-dialog hidden>

&#x20; \<div class="modal-form\_\_header">

&#x20;   \<div>

&#x20;     \<h3>弹窗标题\</h3>

&#x20;     \<p class="panel\_\_hint">说明\</p>

&#x20;   \</div>

&#x20;   \<button class="button button--ghost" data-close>\<i data-lucide="x">\</i>\</button>

&#x20; \</div>

&#x20; \<div class="modal-form\_\_body">

&#x20;   \<!-- 内容 -->

&#x20; \</div>

&#x20; \<div class="modal-form\_\_footer">

&#x20;   \<button class="button" data-close>取消\</button>

&#x20;   \<button class="button button--primary" data-apply>应用\</button>

&#x20; \</div>

\</dialog>
```



* 使用原生 `<dialog>` 元素，`.showModal()` / `.close()`

* 必须有 `modal-form__footer`，取消在左、主要操作在右

* 点击遮罩或按 ESC 关闭（需阻止默认 cancel 事件）

### 4.6 徽章 / 标签



```
\<span class="badge badge--success">S\</span>

\<span class="badge badge--brand">A\</span>

\<span class="badge badge--warning">B\</span>

\<span class="badge badge--danger">C\</span>

\<span class="badge badge--muted">标签\</span>
```

### 4.7 分段控制器（字段模板切换）



```
\<div class="segmented" role="group">

&#x20; \<button type="button" aria-pressed="true">模板1\</button>

&#x20; \<button type="button" aria-pressed="false">模板2\</button>

\</div>
```



***

## 五、列设置与字段模板（核心交互）

所有数据列表页面**必须**实现列设置功能，使用公共组件 `DemoFieldSelector`。

### 5.1 字段定义



```
const FIELD\_GROUPS = \[

&#x20; {

&#x20;   label: '分组名称',

&#x20;   columns: \[

&#x20;     { key: 'field\_name', label: '显示名称', sortable: true, width: '80px' },

&#x20;   ],

&#x20; },

];
```



* 字段必须分组（基础信息 / 商品属性 / 推广效果 / 自然流量等）

* 每个字段有 `key`（数据库字段名）、`label`（显示名）、`sortable`（是否可排序）、`width`（建议宽度）

### 5.2 预设模板



```
const TEMPLATES = {

&#x20; template1: \['field1', 'field2', 'field3'],

&#x20; template2: \['field1', 'field4'],

&#x20; full: ALL\_COLUMNS.map(c => c.key),

};
```



* 至少提供 2-3 个预设模板 + 1 个 "全字段"

* 顶部用 `segmented` 组件切换模板

### 5.3 列设置弹窗



* 使用 `DemoFieldSelector.create()` 渲染字段选择器（支持拖拽排序）

* 提供：模板选择下拉、使用模板、全选、清空、恢复默认

* 支持**自定义模板保存**（存 localStorage，键名 `tmall-{page}-custom-templates`）

* 已保存模板列表，支持应用 / 删除

* 用户当前列选择存 localStorage，键名 `tmall-{page}-visible-columns`

### 5.4 列设置弹窗 HTML 结构



```
\<dialog class="modal-form panel products-columns-dialog">

&#x20; \<div class="modal-form\_\_header">...\</div>

&#x20; \<div class="products-columns-dialog\_\_body">

&#x20;   \<div class="field-template-bar">

&#x20;     \<div class="field-template-bar\_\_current">当前显示 \<strong>X\</strong> 个字段\</div>

&#x20;     \<div class="field-template-bar\_\_controls">

&#x20;       \<select class="select">模板选择\</select>

&#x20;       \<button>使用模板\</button>

&#x20;       \<button>全选\</button>

&#x20;       \<button>清空\</button>

&#x20;       \<button>恢复默认\</button>

&#x20;     \</div>

&#x20;   \</div>

&#x20;   \<div data-field-selector>\</div>

&#x20;   \<div class="products-template-save">

&#x20;     \<input class="input" placeholder="自定义模板名称">

&#x20;     \<button>保存为模板\</button>

&#x20;   \</div>

&#x20;   \<div class="saved-template-list field-template-manager">\</div>

&#x20;   \<p class="products-columns-dialog\_\_status">\</p>

&#x20; \</div>

&#x20; \<div class="modal-form\_\_footer">

&#x20;   \<button>取消\</button>

&#x20;   \<button class="button--primary">应用字段\</button>

&#x20; \</div>

\</dialog>
```



***

## 六、数据模型规范

### 6.1 数据库表命名



* 表名：`snake_case`，如 `products`、`daily_data`、`keyword_promotion_products`

* 主键：`id INTEGER PRIMARY KEY AUTOINCREMENT`

* 业务键：`product_id TEXT`（商品 ID，字符串，因为可能有前导零）

* 店铺隔离：`shop_id TEXT`（所有业务表必须有，用于多店铺隔离）

### 6.2 字段命名



* 英文字段名：`snake_case`，如 `ad_spend`、`payment_amount`、`ctr`

* 时间字段：`created_at TIMESTAMP`、`updated_at TIMESTAMP`

* 日期字段：`date DATE`（YYYY-MM-DD）

* 金额字段：`REAL`（元，保留 2 位小数）

* 比率字段：`REAL`（0-1 小数，如 0.035 表示 3.5%）

* 计数字段：`INTEGER`

### 6.3 关联规则



* 商品维度统一用 `product_id` 关联

* 不做物理外键，用逻辑关联（查询时 JOIN）

* 关联不上的数据保留，字段置 NULL，**不用 0 填充**

### 6.4 数据来源标记



* 导入数据必须记录来源：`source_type`、`import_batch_id`

* 缺失数据展示为 "--" 或 "无数据"，**禁止用 0 或推测值填充**



***

## 七、API 规范

### 7.1 统一返回格式

所有 API 必须使用 `api/api_response.py` 中的 `success()` 和 `failure()` 函数。

**成功响应：**



```
{

&#x20; "ok": true,

&#x20; "data": { ... },

&#x20; "availability": "available",

&#x20; "capabilities": {},

&#x20; "filters": {},

&#x20; "missing\_fields": \[],

&#x20; "missing\_ranges": \[],

&#x20; "source\_batches": \[],

&#x20; "evidence\_level": "full",

&#x20; "missing\_inputs": \[],

&#x20; "limitations": \[],

&#x20; "freshness": {},

&#x20; "evidence": \[],

&#x20; "assumptions": \[],

&#x20; "unknowns": \[],

&#x20; "requestId": "uuid-hex"

}
```

**失败响应：**



```
{

&#x20; "ok": false,

&#x20; "code": "ERROR\_CODE",

&#x20; "message": "错误描述",

&#x20; "details": {},

&#x20; "availability": "calculation-failed",

&#x20; "limitations": \["错误描述"],

&#x20; "requestId": "uuid-hex"

}
```

**availability 可选值（7 种）：**

`available` / `no-data` / `insufficient-data` / `missing-fields` / `calculation-failed` / `source-unavailable` / `partial`

**evidence\_level 可选值：** `full` / `partial` / `insufficient`

**使用规则：**



* 缺失数据用 `missing_fields` / `missing_ranges` 声明，不用 0 填充

* 数据来源用 `source_batches` 记录批次

* 计算假设用 `assumptions` 声明，未知项用 `unknowns`

* 前端用 `DemoApi.domainRequest()` 会自动检查 `ok===true`，失败时抛错

### 7.2 路由规范



* 列表：`GET /api/{module}/products?page=1&page_size=50&{filters}`

* 汇总：`GET /api/{module}/summary?{filters}`

* 筛选选项：`GET /api/{module}/filters`

* 导入：`POST /api/{module}/import`

### 7.3 分页参数



* `page`：从 1 开始，默认 1

* `page_size`：默认 50，可选 20/50/100/200

* 返回：`{ rows: [...], total: 总数, page: 当前页, page_size: 每页条数 }`

### 7.4 筛选参数



* 直接用字段名作为 query 参数，如 `?category=堆堆袜&gender=女&min_spend=5`

* 范围筛选：`min_{field}` / `max_{field}`

* 关键词搜索：`keyword`（模糊匹配标题）

### 7.5 排序参数



* `sort_by`：字段名（必须在白名单内，防注入）

* `sort_order`：`desc` / `asc`



***

## 八、前端代码规范

### 8.1 文件命名



* 页面 HTML：`{page}.html`（kebab-case）

* 页面 JS：`{page}-live.js`

* 页面 CSS：`{page}.css`（仅当组件样式不够用时）

### 8.2 JS 结构



```
(async function () {

&#x20; 'use strict';

&#x20; const API\_BASE = '/api/{module}';

&#x20; const STORAGE\_KEY = 'tmall-{page}-visible-columns';

&#x20; // 1. 字段定义

&#x20; const FIELD\_GROUPS = \[...];

&#x20; const ALL\_COLUMNS = \[...];

&#x20; const COLUMN\_MAP = new Map(...);

&#x20; const TEMPLATES = {...};

&#x20; // 2. 状态

&#x20; const state = {

&#x20;   filters: {},

&#x20;   sortBy: 'default\_field',

&#x20;   sortOrder: 'desc',

&#x20;   page: 1,

&#x20;   pageSize: 50,

&#x20;   total: 0,

&#x20;   visibleColumns: loadVisibleColumns(),

&#x20; };

&#x20; // 3. 工具函数

&#x20; function fmtMoney(v) {...}

&#x20; function fmtPct(v) {...}

&#x20; function fmtNum(v, digits=2) {...}

&#x20; function fmtInt(v) {...}

&#x20; // 4. 渲染函数

&#x20; function renderHead() {...}

&#x20; function renderCell(row, key) {...}

&#x20; function renderTable(rows) {...}

&#x20; // 5. 数据加载

&#x20; async function loadFilterOptions() {...}

&#x20; async function loadSummary() {...}

&#x20; async function loadProducts() {...}

&#x20; // 6. 列设置

&#x20; function openColumnsDialog(e) {...}

&#x20; function closeColumnsDialog() {...}

&#x20; function applyColumns() {...}

&#x20; // 7. 事件绑定

&#x20; function bindEvents() {...}

&#x20; // 8. 初始化

&#x20; async function init() {...}

&#x20; if (document.readyState === 'loading') {

&#x20;   document.addEventListener('DOMContentLoaded', init);

&#x20; } else { init(); }

})();
```

### 8.3 数据属性命名



* 所有交互元素用 `data-{page}-*`，如 `data-kp-search`、`data-kp-apply`

* 禁止用 class 选择器做事件绑定，必须用 data 属性

### 8.4 格式化函数统一



* 金额：`fmtMoney(v)` → 千分位整数，如 "1,234"

* 百分比：`fmtPct(v)` → 0-1 小数转 "3.5%"

* 数字：`fmtNum(v, digits)` → 指定小数位

* 整数：`fmtInt(v)` → 千分位整数

* 空值：所有格式化函数对 `null/undefined/NaN` 返回 "--"

### 8.5 公共组件与 API



* **列选择器**：`DemoFieldSelector.create({ root, groups, selected, onChange, className, availableTitleId, previewTitleId, optionDataAttribute, previewDataAttribute })`，返回 `{ getSelected(), setConfig(config) }`

* **API 客户端**：`DemoApi.request(path, options)`（原始请求）、`DemoApi.domainRequest(path, options)`（自动校验 ok，失败抛错）

* **能力系统**：`DemoApi.can(capabilityKey)`、`DemoApi.canPage(pageKey)`、`DemoApi.loadPageCapabilities()`，按钮用 `data-capability-key` 控制权限

* **数据状态渲染**：`DemoApi.renderDataState(element, state)`，标准状态见第十章

* **导航工具**：`DemoNavigation.build(path, values)`、`DemoNavigation.fromCurrent(path, extra)`（白名单参数：start/end/preset/compare/product\_id/tier/lifecycle\_stage/promotion\_channel/action\_id）

* **图标**：`window.lucide.createIcons()`（动态内容后必须调用）

### 8.6 shell.js 自动加载机制

`shell.js` 会自动加载以下公共 JS，**不需要手动引用**：



* `table-controls.js`（表格控件）

* `ui-components.js`（UI 组件）

* `version.js` + `version-check.js`（版本检查）

* `desktop-integration.js`（桌面端集成）

`shell.js` 会根据 `document.body.dataset.page` 自动加载 `{page}-live.js`，但**前提是 api.js 未先加载**。由于标准页面都先加载 api.js，`window.DemoApi`已存在，所以**必须手动引用&#x20;**`{page}-live.js`。

### 8.7 HTML 引用顺序（标准）



```
\<link rel="stylesheet" href="../assets/tokens.css">

\<link rel="stylesheet" href="../assets/shell.css">

\<link rel="stylesheet" href="../assets/components.css">

\<link rel="stylesheet" href="../assets/{page}.css">  \<!-- 可选 -->

\<script src="../assets/lucide-1.8.0.min.js">\</script>

\<script src="../assets/api.js">\</script>

\<script src="../assets/navigation.js">\</script>

\<script src="../assets/labels.js">\</script>        \<!-- 标签字典 -->

\<script src="../assets/charts.js">\</script>        \<!-- 图表封装 -->

\<script src="../assets/shell.js">\</script>

\<script src="../assets/field-selector.js">\</script>  \<!-- 需要列设置时 -->

\<script src="../assets/field-template-manager.js">\</script>  \<!-- 需要模板管理时 -->

\<script src="../assets/product-detail-dialog.js">\</script>  \<!-- 需要商品详情时 -->

\<script src="../assets/{page}-live.js">\</script>
```

### 8.8 标准数据状态（7 种）

所有数据加载区域必须支持以下状态，用 `data-state` 属性标记：



```
const DATA\_STATES = \['loading', 'no-data', 'insufficient-data', 'missing-fields', 'calculation-failed', 'source-unavailable', 'partial'];
```



* `loading`：加载中，显示骨架屏或 "加载中…"

* `no-data`：没有数据，显示空状态插画 +"没有符合条件的数据"

* `insufficient-data`：数据不足，显示 "数据不足，无法计算"

* `missing-fields`：字段缺失，显示缺失字段列表

* `calculation-failed`：计算失败，显示错误信息

* `source-unavailable`：数据源不可用

* `partial`：部分数据可用，显示警告提示

用 `DemoApi.renderDataState(element, state)` 统一渲染。

### 8.9 主题系统



* 支持 `light` / `dark` 两种主题，存在 `localStorage` 的 `tmall-demo-theme`

* 通过 `document.documentElement.dataset.theme` 切换

* 所有颜色必须用 CSS 变量，禁止硬编码颜色值（深色模式会自动覆盖）

* shell.js 提供主题切换按钮，页面不需要自己实现



***

## 九、新增页面标准流程

### 9.1 后端（3 步）



1. **Repo 层**：`repos/{module}_repo.py`，继承 `BaseRepo`，实现 `list_products`、`summary`、`filter_options`

2. **API 层**：`api/{module}_api.py`，定义 Blueprint，注册路由

3. **注册路由**：在 `app.py` 的 `create_app()` 中 `app.register_blueprint({module}_bp)`

### 9.2 数据库（2 步）



1. 建表：在 `models/` 或直接用 `CREATE TABLE IF NOT EXISTS`

2. 数据导入：写导入脚本，支持增量（按批次去重）

### 9.3 前端（5 步）



1. **HTML**：复制标准页面骨架，改 `data-page`、标题、筛选器、表格容器

2. **CSS**：优先用公共组件样式，特殊样式写 `{page}.css`

3. **JS**：按标准结构写 `{page}-live.js`，实现字段定义、渲染、加载、列设置

4. **注册 shell.js**：在 `shell.js` 的 `liveAdapters` 中添加 `'{page}': '{page}-live.js'`

5. **注册导航**：在 `shell.js` 的 `navGroups` 中添加菜单项 `['{page}', '显示名', '图标名', '{page}']`，并在 `meta` 中添加页面标题和副标题

> 注意：导航菜单和 liveAdapters 都在 
>
> `shell.js`
>
>  中硬编码，
>
> `navigation.js`
>
>  只是 URL 构建工具（DemoNavigation），不负责菜单。

### 9.4 验收清单



* [ ] 页面布局与其他页面一致（侧边栏 / 顶栏 / 面板 / 筛选器）

* [ ] 指标卡片正常显示

* [ ] 筛选器即时生效，更多筛选可展开

* [ ] 排序正常（表头点击 + 下拉）

* [ ] 服务端分页正常

* [ ] 列设置弹窗正常（DemoFieldSelector）

* [ ] 字段模板切换正常

* [ ] 自定义模板保存 / 删除正常

* [ ] 列选择持久化（localStorage）

* [ ] 空数据 / 加载中 / 错误状态处理

* [ ] 响应式（窄屏可横向滚动表格）

* [ ] 所有数值格式化正确（金额 / 百分比 / 空值）



***

## 十、命名约定速查表



| 对象             | 规则                       | 示例                                |
| -------------- | ------------------------ | --------------------------------- |
| 页面名            | kebab-case               | `keyword-promotion`               |
| HTML 文件        | `{page}.html`            | `keyword-promotion.html`          |
| JS 文件          | `{page}-live.js`         | `keyword-promotion-live.js`       |
| CSS 类          | BEM                      | `product-filters__main`           |
| 数据属性           | `data-{page}-*`          | `data-kp-search`                  |
| 数据库表           | snake\_case              | `keyword_promotion_products`      |
| 数据库字段          | snake\_case              | `ad_spend`                        |
| API 路由         | `/api/{module}/{action}` | `/api/keyword-promotion/products` |
| localStorage 键 | `tmall-{page}-*`         | `tmall-kp-visible-columns`        |
| JS 常量          | UPPER\_SNAKE             | `FIELD_GROUPS`、`TEMPLATES`        |
| JS 变量          | camelCase                | `visibleColumns`                  |



***

## 十一、禁止事项



1. **禁止硬编码颜色 / 字体 / 间距** — 必须用 CSS 变量

2. **禁止用 0 填充缺失数据** — 缺失显示 "--" 或 "无数据"

3. **禁止删改已有页面的公共组件** — 新增页面复用，不修改公共文件

4. **禁止前端硬编码筛选选项** — 从 `/api/{module}/filters` 动态获取

5. **禁止 SQL 拼接** — 所有查询用参数化，排序字段用白名单校验

6. **禁止跳过列设置功能** — 所有数据列表页面必须实现

7. **禁止用 class 做事件绑定** — 必须用 data 属性

8. **禁止不同页面用不同的金额 / 百分比格式** — 统一用格式化函数



***

*文档版本：v1.1 | 最后更新：2026-09-17*

*基于 tmall-dashboard v1.0.13 实际实现总结*

*v1.1 修正：API 返回格式、shell.js 自动加载机制、导航注册位置、标准数据状态、主题系统、目录结构、DemoApi 接口*