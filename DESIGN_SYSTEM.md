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

* 图标和进度条颜色按指标类型语义映射，同一类指标必须同色，禁止逐卡挑选装饰色：
  * 金额类（净销售额、支付金额、客单价、推广花费）→ `--brand`（`overview-v2-kpi--brand` / `ui-metric-card--brand`）
  * 比率类（转化率、退款率、费用比）→ `--info`
  * 人群类（访客数、老买家占比）→ `--purple`
  * 效率/成果类（ROI 等正向效率指标）→ `--success`

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

* 动态弹窗统一使用 `TmallUI.modal({ title, description, body, footer, size, dismissible, onClose })`，返回 `{ node, body, footer, open(), close(), destroy() }`；组件自带标题栏、关闭按钮、`aria-labelledby`、焦点还原和 body 滚动锁定

* 确认流使用 `TmallUI.confirm({ title, message, confirmLabel, cancelLabel, tone })`，返回 `Promise<boolean>`；`tone: 'danger'` 渲染红色主要按钮

* `size` 枚举：`sm`(420px) / `md`(560px，默认) / `lg`(820px) / `xl`(960px)；`dismissible: false` 时 ESC 与遮罩点击无效，只允许页脚按钮关闭

* 新增弹窗功能不得手写 `<dialog>` 结构；存量 `.modal-form` 系列弹窗在对应页面迁移时替换为组件

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



* 直接用字段名作为 query 参数，如 `?category=款式词&gender=女&min_spend=5`

* 范围筛选：`min_{field}` / `max_{field}`

* 关键词搜索：`keyword`（模糊匹配标题）

### 7.5 排序参数



* `sort_by`：字段名（必须在白名单内，防注入）

* `sort_order`：`desc` / `asc`



***

## 八、前端代码规范

### 8.0 CSS 分层约定（新代码必须遵守）

19 个 CSS 文件是全局级联，一旦没有分层约定，选择器互相覆盖、错误波及范围无法静态推断。新代码按下表分层；老代码遇到再顺手收，**不要求一次性重写**。

| 层 | 文件 | 职责 | 允许 | 禁止 |
|---|---|---|---|---|
| L0 令牌 | `tokens.css` | 唯一颜色/间距/字体来源 | 定义 `--token`、裸色值 | 写选择器样式 |
| L1 基础 | `components.css` 的 `Canonical UI component contract` 段 | `.ui-*` 组件契约 | 组件类名、浮层定位 | 引用具体页面 |
| L2 外壳 | `shell.js`/`shell.css` | 顶栏、侧栏、全局工具 | `demo-*` 外壳类名 | 页面业务样式 |
| L3 页面 | `{page}.css`、`themes/{domain}-domain.css` | 单个页面/域的样式 | 必须限定在 `body[data-page="x"]` 或页面根类下 | 改 `.ui-*` 组件；自写 `position:fixed` 浮层 |
| L4 工具 | `scripts/`、测试 | 校验与门禁 | — | 参与运行时样式 |

三条硬规则（由 `scripts/check_design_system.py` 强制）：

1. **颜色必须走 token**：除 `tokens.css` 外不得新增裸 `#hex` / `rgb()` / `hsl()`。历史违规记录在门禁的 `RAW_COLOR_BASELINE`，只允许减少。
2. **浮层必须走原语**：页面级 CSS 不得自写 `position:fixed`。下拉、选择器、提示一律用 `TmallUI.popover`，由它统一负责 fixed 定位、视口夹紧、空间不足翻转、点外关闭、ESC、焦点返回、单例。
3. **组件目录必须覆盖**：新增组件要同步补 `pages/component-catalog.html`，否则 `check_design_system.py` 报 R3。
4. **复合组件不得在 HTML 里手写拼装**：`ui-panel`、`ui-metric-card`、`ui-table-wrap`、`ui-data-table`、`ui-empty-state`、`ui-page-header`、`ui-filter-toolbar`、`ui-table-toolbar`、`ui-context-bar`、`ui-metric-grid`、`ui-sticky-action-bar`、`ui-modal`、`ui-popover`、`ui-drawer`、`ui-field-selector` 一律走 `TmallUI.*` 工厂，否则报 R5。

   **原子类（`ui-button`、`ui-badge`）允许在 HTML 里手写**。这是刻意的：原子类没有内部结构约定，静态标记手写合理；强制它们走 JS 工厂会破坏服务端渲染、增加无谓 JS 依赖，收益为负。门禁只针对"内部有 header/body/tools 结构约定、手写易与工厂输出漂移"的复合组件。

   每页的允许量记录在 `scripts/check_design_system.py` 的 `UI_HANDWRITE_BASELINE`（引入时实测 **378 处**，集中在 `ui-panel` 104 / `ui-metric-card` 104）。**只允许下降**：收敛某页后请同步下调该页数字，把进展固化下来。

> 为什么要硬性规定浮层：曾经因为没有浮层原语，时间选择器自己写定位；一次 CSS 解析错误（孤立声明块）吞掉了 `position:fixed`，弹窗以 `static` 渲染到文档流底部（top 2211px / 视口 800px），页面表现是「点了没反应」——console 无报错、单元测试全绿，只有真实浏览器点击才能发现。

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

### 11.1 UI 组件系统入口（现行规则）

公共 UI 的唯一运行时入口是 `window.TmallUI`，实现位于 `frontend/ui_demo/assets/ui-components.js`。基础组件和页面组合必须优先使用以下 API：

```js
TmallUI.button(options)
TmallUI.badge(label, tone)
TmallUI.metricCard(options)
TmallUI.metricGrid(cards)
TmallUI.panel(options)
TmallUI.pageHeader(options)
TmallUI.filterToolbar(content, actions)
TmallUI.table(options)
TmallUI.dataState(state, details)
TmallUI.fieldSelector(options)
```

字段选择器是跨商品、生命周期、经营概览和推广页面复用的公共组件。实现位于 `frontend/ui_demo/assets/field-selector.js`，统一入口为 `TmallUI.fieldSelector(options)`；`DemoFieldSelector.create(options)` 仅作为历史页面兼容调用。组件根节点和子节点使用 `ui-field-selector*` canonical class，支持字段分组、必选字段、勾选、顺序调整和预览。

历史页面中的 `.button`、`.panel`、`.metric-card`、`.badge`、`.empty-state`、`.data-table` 等 class **没有自动迁移兜底**：`TmallUI.upgradeLegacy()` 已被有意移除（`tests/test_ui_system_contract.py` 断言其不存在），历史 class 只保留为兼容别名，不会再被自动映射。新代码必须直接使用 `ui-*` canonical class 或 `TmallUI.*` 工厂，不得再新增历史 class 的独立实现。

组件契约目录位于 `/component-catalog`。提交前运行：

```text
python scripts/check_ui_contract.py
python scripts/check_css_syntax.py --strict
python scripts/check_design_system.py --strict
python scripts/check_css_tokens.py --strict
python scripts/check_event_binding.py --strict
node desktop/node_modules/typescript/bin/tsc -p tsconfig.json --noEmit
pytest -q tests/test_ui_system_contract.py
```

前五项中的后四项（`check_css_syntax` / `check_design_system` / `check_css_tokens` / `check_event_binding`）
同时由 `.github/workflows/quality-gate.yml` 的 "Run static design-system gates" 步骤
和本地入口 `scripts/test_all.ps1` 执行。**两处清单必须保持一致**：只写进本文档而不进这两处，
门禁等于不存在——历史上 `check_event_binding` 对应的「禁止事项 7」就是因为没有检查脚本，
被违反了三处而无人发现。

类型检查范围由 `tsconfig.json` 的 `include` 白名单控制，只覆盖已标注的核心模块（`ui-components.js`、`runtime/*`、纯函数模块），不产出运行时代码。新增标注文件时同步加入清单；`tests/test_ui_system_contract.py` 会断言清单「只增不减」，防止覆盖范围被悄悄缩小。

`TmallUI.audit()` 可在浏览器开发工具中检查当前页面是否存在未接入公共组件契约的节点。



1. **禁止硬编码颜色 / 字体 / 间距** — 必须用 CSS 变量

2. **禁止用 0 填充缺失数据** — 缺失显示 "--" 或 "无数据"

3. **禁止删改已有页面的公共组件** — 新增页面复用，不修改公共文件

4. **禁止前端硬编码筛选选项** — 从 `/api/{module}/filters` 动态获取

5. **禁止 SQL 拼接** — 所有查询用参数化，排序字段用白名单校验

6. **禁止跳过列设置功能** — 所有数据列表页面必须实现

7. **禁止用 class 做事件绑定** — 必须用 data 属性

   由 `scripts/check_event_binding.py --strict` 强制。判据：`querySelector*('.x…')`
   的结果在同一语句内被 `addEventListener` / `on<事件>=` 绑定时判为违规，
   修法是改用 `[data-*]` 选择器并在元素上补对应属性。豁免仅限于组件层
   （`ui-components.js`、`field-selector.js`）定位自己创建的子节点。

8. **禁止不同页面用不同的金额 / 百分比格式** — 统一用格式化函数

   唯一契约来源是 `frontend/ui_demo/assets/format.js`（`DemoFormat.money` /
   `percent` / `moneyWan`）。注意它按设计**不拼接货币符号**，只负责千分位与小数位。
   **本条目前没有静态门禁**，靠评审发现：仓库里曾有 13 份各自实现的 `money()`，
   `¥` / `￥` 与小数位（0/1/2）互不一致。



***

*文档版本：v1.1 | 最后更新：2026-10-11*

*基于 tmall-dashboard v1.0.13 实际实现总结*

*v1.1 修正：API 返回格式、shell.js 自动加载机制、导航注册位置、标准数据状态、主题系统、目录结构、DemoApi 接口*

*2026-10-11 补充：提交前门禁清单加入 `check_event_binding.py`；明确禁止事项 7 的检查脚本与豁免范围；*
*说明禁止事项 8 的格式化契约现状（`format.js` 不拼符号，且尚无静态门禁）。*


### 2026-10-17 增补：首页 U01–U03 周期与质量展示契约
- 所选日期区间与月度诊断分开标注；只在范围、来源、指标定义和当前值均可核验一致时展示月度比较。不匹配显示“暂无同范围比较”，不补0%。
- 月目标进度独立于上期比较是否存在；仅有匹配月目标时显示，不把日期范围KPI冒充月目标实绩。
- 历史首末日期是跨度，不是当前范围覆盖天数；缺日读取响应envelope missing_ranges，无完整性合同则标待核验。缺失详情使用可键盘展开的原生details。
- 首页状态色由语义modifier决定；loading/unknown/no-data为中性，warning为警告色，failure为危险色，available为成功色。
- 首页筛选与操作区允许换行，自定义日期控件不得以overflow:hidden裁掉。保持其他页面shell规则不变。
- 复现命令：node scripts/test_overview_ux_runtime.cjs；pytest tests/test_overview_kpi_ui.py会运行真实JS行为测试。

### 2026-10-17 增补：桌面首页克制视觉
- 仅 >=960px 首页样式增补；保留现有品牌与状态色 token，未做手机端改版。统一KPI面板，核心指标先于摘要，细分隔代替嵌套小卡片阴影；保留选中和focus反馈。
- 960–1199px顶部为两行：品类与动作、日期；新增动作弹窗仅正文滚动。不得改变数据口径。
- 专项静态契约 node scripts/test_apple_desktop.cjs；实际桌面几何需结合浏览器证据，不以正则测试替代视觉验收。

### 2026-10-17 桌面首页高亮收敛
- 主/次指标 is-selected 使用既有brand-tint浅底、brand底线、brand-text标签；数值与涨跌语义色不变。未选中hover为surface-muted；focus-visible独立2px内圈。只作用于>=960px首页，不改选中业务逻辑。

2026-10-17 | Codex | 首页桌面高亮 | 【已作废】此前“细底线”要求，按用户最新要求取消选中底线；保留浅紫底、标签强调、焦点可见及原单元格尺寸 | 用户要求更收敛 | 仅首页桌面主次指标

2026-10-17 | Codex | macOS桌面外壳与选中态 | 全站桌面导航侧条（展开/收起）、日期快捷入口底线、品类页签及旧页签兼容样式改为底色识别；224px侧栏、32px导航行、系统字体、8px圆角、取消悬停位移；保留原配色、分隔线、焦点及业务语义色 | 用户选择macOS紧凑原生应用方向 | >=960px，不改数据与移动端

2026-10-17 | Codex | 全页面桌面主体 | 21个模板末尾加载macos-content.css（首页主体排除）；指标分组统一、静态面板去漂浮、紧凑控件/表格/筛选与弹窗，覆盖分析/品类/复盘/设置/九维旧类；九维生成器同步引用 | 用户要求其他页面统一macOS风格 | >=960px，颜色和业务行为不变

2026-10-17 | Codex | 逐页结构改造第一批 | 商品列表真实前移至分群/矩阵之前，字段模板/列设置归列表；推广KPI前移、范围来源合并、诊断平面化；设置摘要/6分区移为工作区侧导航，右侧分组表单。全部原data/name、ID、控件与脚本守恒 | 修正此前仅共享外观而未逐页整理结构的不足 | 本批仅商品/推广/设置3页，另16页结构改造待办；保留配色、数据口径与交互，无手机端适配工作


### 2026-10-18 增补：PC 自定义分析工作区
- 延续 macOS 紧凑原生应用方向及原配色，只做 PC（>=960px）。`analysis-workspace.css` 在共享主题之后加载；左侧模板与配置检查器，右侧统一结果面，减少嵌套边框/圆角，不改 API 参数、统计口径、保存格式。
- 六个模板为原生 button，aria-pressed 跟随当前选中态；六个原配置标签显式关联输入。原有 ID/data hooks 保留。
- `createChartCard` 在下一帧且 canvas 仍已挂载时初始化 ECharts，避免脱离 DOM 的 0×0 画布；保留 resize/dispose 登记。
- 定向静态契约：`node scripts/test_analysis_workspace.cjs`。960/1024/1440 PC 浏览器夹具验证及原始/修改/回滚证据：`E:/tmp/tmall-apple-desktop-20261017/VERIFICATION.txt`。夹具不等于生产业务数据验证；不开展手机端改版。


### 2026-10-18 增补：PC 推广总览数值 / 状态 / 证据分层
- `promotion-live.js` 增加纯展示接口 valueText/statusLabel/compact；renderKpis 与 renderCommandBoard 的大号字段仅展示值，部分/未提供/不可计算放短状态，覆盖行数与来源保存在原生 details 数据完整度。原 format/exportValue/summarize/chartValue 不变；缺失不补0，部分比率仍为不可用。
- >=960px 仅调整展示间距、信号列与窄PC金额布局；960–1199px 前四核心指标两列，避免金额断行。未进行手机端设计。
- 原有 ID/data/name/控件/脚本保留；macOS 结构 fixture 仅增补新状态/证据 hooks。`node scripts/test_promotion_presentation.cjs` 与既有 promotion_missingness 契约共同回归；浏览器同一冻结输入做原版/修改/回滚验证，证据沿用 E:/tmp/tmall-apple-desktop-20261017 四角色。本批仅修推广首屏，不代表首页/商品深改完成。


### 2026-10-18 增补：PC 时间选择器视觉收敛
- 仅 shell.css 的 >=960px 增补：顶栏时间文字/按钮减轻字重；日期弹层标题14px，统一radius-md与elevation-md；月份/年份选中改浅品牌底，保留日期起止实心小圆点、区间带与独立键盘焦点；取消按钮去描边。原有尺寸、锚定、DOM、事件、日期范围与应用逻辑不变。不新建选择器组件，不改手机端。
- 原版/修改/回滚同一浏览器输入验证日/周/月/年、双月范围选择及应用、Esc与焦点返回、960/1024/1440视口包含。沿用 E:/tmp/tmall-apple-desktop-20261017 四角色，不以静态检查替代画面核对。


### 2026-10-18 增补：PC全站克制型苹果风收敛（不改配色/业务）
- 先统一共享组件，再逐页减噪：21模板同协议截图，18个CSS文件收敛。按钮/输入/分段/指标/面板/工具区/表格/空态状态/浮层/键盘禁用共10类检查；主题token只读，不增裸色或!important、不改HTML/JS/指标计算与日期逻辑。仅>=960px。
- 真实差异：首页辅助摘要gap12→8px；商品详情标题34→22px；新品漏斗重复边框1→0px；类目判断竖线3→0px；创意工具条及九维维度边框1→0px。已合格的分析/推广工作区保留，不为凑数量重写。
- 验收：21页PARENT/候选/执行step回滚均HTTP200、0pageerror/hidden泄漏；37场代表PC状态检查；深浅弹层/焦点/禁用/日期应用；四项strict、UI静态、TypeScript及既有6组工作区/结构契约通过。不是完整CI或全部业务流程验收。
- 既有P2：首页已发布legacy趋势菜单底部超视口、Esc无效，新旧同现且候选未恶化；其未发布配套JS未夹带本轮。需后续独立迁移popover。
- 证据及逐页说明：E:/tmp/tmall-apple-desktop-20261017/site-refinement/comparison.html、coverage.txt、independent-review.txt。沿用四角色；ROLLBACK.sh TARGET_COPY --step site-refinement恢复本轮PARENT，默认恢复累计原版；旧发布保留。

2026-10-18 | Codex补验 | 商品详情真实长文本 | 补测真实商品后发现既有3列信息区挤压标签；仅详情CSS收敛为清晰信息行、完整标签和正常换行值，保留全部8字段与顺序；独立960/1024/1440复验 | 避免只验收空态而漏掉真实内容 | 仅PC详情；同一实际GET快照三态数据一致，完整21页候选重跑，证据site-refinement/independent-readability-review.txt


### 2026-10-18 增补：商品详情主图
- 复用现有product.image_url，补齐模板data-product-detail-image节点；PC商品名左侧96×96主图，contain完整展示，沿用radius-md/surface-base，未增加图库或新弹窗。
- renderProductImage仅在图片成功加载后显示；缺少URL/加载失败收起且清除旧src；同图日期刷新不重复闪烁；alt使用商品名纯文本。无API/指标变更，不增加手机端展示。
- 真实商品固定GET快照的960/1024/1440有图/缺图/坏图九场三态验证；6项原生JS回归、四strict/UI/结构/类型门禁与精确补丁/回滚验证见E:/tmp/tmall-apple-desktop-20261017/VERIFICATION.txt。ROLLBACK.sh TARGET_COPY --step product-image只恢复本轮，旧step与累计回滚保留。

2026-10-18 | Codex | PC异常提醒去装饰竖线 | operations-center__item左侧3px状态色粗线改为1px中性细边，高风险/异常提醒标签及全文保留 | 用户截图框出左侧红色竖线，继续收敛 | 仅>=960px，真实提醒三宽原版/修改/回滚及精确哈希验证；不改HTML/JS/风险判断，沿用四角色；--step alert-stripe恢复本轮


### 2026-10-18 增补：PC真实任务路径与文字收敛
- 商品筛选保留所有控件/字段/ID与查询逻辑：DOM先搜索，再把呈现方式/日周月和更多筛选/收藏/重置合为次级行，冗余说明仅改sr-only而非删除。1440表头Y520→430、1024Y639→549、960Y757→715；不靠隐藏业务字段达成。
- PC正文与展示字统一系统UI字体；status-list与明细值从代码等宽字改为同一UI字重500/表格数字等宽，代码/商品ID规则不动，配色token不变。
- 真实商品入口是列表→快速查看抽屉→完整工作台：抽屉open即显示已知商品名/ID/主图，不等8个请求才填身份，不闪旧商品；复用原图片渲染，旧图片迟到error不可清空新图。只加可选imageUrl展示参数，不改API/指标。
- 【已修复】旧发布首页趋势菜单越界/Esc旧P2：源码原有popover迁移此前未发布，本批检查原节点/8checkbox/最多3指标、视口夹紧、Esc/外点/焦点与重复开关后发布；仅在restoreTrendMenu增补RAF条件归焦：空白外点回触发器，点击新控件不抢焦点；共享popover不改。原LIVE与PARENT基线在VERIFICATION中分开。
- 源码PARENT/修改/执行step回滚同协议的文字、表头、同步反馈与实际GET数据；严格门禁、21模板和独立复核的最终证据沿用E:/tmp/tmall-apple-desktop-20261017四角色。ROLLBACK.sh TARGET_COPY --step workflow-refinement恢复本批源码PARENT；保留历史step与完整累计回滚。未宣称全业务流程/全CI/手机验收。
