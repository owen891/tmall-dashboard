# 天猫数据仪表盘 — 重构方案

> **策略**: 混合增强重构（Flask + SQLAlchemy + Alembic + Vite + 原生JS）
> **目标**: 可维护性 + 性能优化 + 数据库可迁移性
> **日期**: 2026-08-11

---

## 一、现状诊断

### 1.1 代码规模与核心问题

| 文件 | 行数 | 问题严重度 | 核心问题 |
|------|------|-----------|---------|
| `api/data_api.py` | 3638 | 🔴 严重 | 84 个路由 + 业务逻辑 + 工具函数全混在一个文件 |
| `static/js/bundle.js` | 7059 | 🔴 严重 | 14 个 JS 手动拼接，无构建系统、无模块化 |
| `static/js/products.js` | 1915 | 🟡 中等 | 单文件过大，表格渲染+交互+筛选耦合 |
| `static/css/dashboard.css` | 1579 | 🟡 中等 | 暗/亮主题、所有组件样式混写 |
| `db.py` | 634 | 🔴 严重 | schema 定义 + 手写 ALTER TABLE 迁移全在 `init_db()` |
| `scripts/market_analyzer.py` | 1152 | 🟡 中等 | 分析逻辑单文件巨石 |
| `scripts/import_data.py` | 896 | 🟡 中等 | 导入逻辑臃肿，Sheet 识别+清洗+入库耦合 |
| `scripts/generate_report.py` | 534 | 🟢 轻微 | 可接受 |

### 1.2 架构层面问题

**后端 — 无分层架构**
```
当前:  Route → 直接写 SQL → 返回 JSON
       (data_api.py 里每个函数都自己拼 SQL、处理业务逻辑、格式化输出)
```
- 路由层、业务逻辑层、数据访问层完全混在一起
- 84 个路由函数中，约 60% 包含内联 SQL 查询
- 工具函数（`get_prev_period`、`_fmt_wan`、`calc_score` 等）散落在路由文件中

**数据库 — 无迁移框架**
- `db.py` 的 `init_db()` 函数 630 行，用 `try/except` 吞错误的方式做 `ALTER TABLE`
- 新增字段需要手写迁移代码，无法回滚、无法追踪版本
- 存在 2 份数据库文件：根目录 `dashboard.db` + `data/dashboard.db`，职责不清

**前端 — 无构建系统**
- 没有 `package.json`，`.vite/` 目录是缓存残留，从未真正配置 Vite
- `bundle.js`（7059 行）是 14 个源文件手动拼接的产物
- 同时存在 `bundle.js` 和 `bundle.min.js`，维护时需同步两份
- 无模块系统（无 import/export），全局函数挂载到 window

**工程 — 目录混乱**
- 5 份重复的 output 目录：`output/` `output_core/` `output_focus/` `output_real/` `output_time/`
- `incoming/` 目录堆积未处理的 `.xls` 文件
- `.superpowers/` 和 `docs/superpowers/` 是工具残留
- 无 `.gitignore` 管理不当（db 文件、缓存等）

**测试 — 几乎为零**
- 仅 `tests/test_report_generator.py` 一个文件
- 核心导入逻辑、健康度计算、API 端点均无测试

### 1.3 性能瓶颈

| 瓶颈 | 位置 | 影响 |
|------|------|------|
| 无查询缓存 | KPI/趋势/商品列表每次全量查询 | 重复计算浪费 |
| 商品列表全字段返回 | `get_products()` 返回所有列 | 大数据量时传输慢 |
| 无连接池 | 每次请求新建 SQLite 连接 | 连接开销 |
| JS 全量加载 | `bundle.min.js` 329KB 一次性加载 | 首屏慢 |
| 无懒加载 | 所有 Tab 的 JS 代码都在 bundle 中 | 初始解析慢 |

---

## 二、重构策略

### 2.1 为什么不换技术栈

| 考虑因素 | 结论 |
|---------|------|
| 使用场景 | 本地单用户工具（127.0.0.1:5000），无并发压力 |
| Flask 适配性 | 轻量、够用，FastAPI 的异步优势在此场景无收益 |
| SQLite 适配性 | 单文件、零运维，适合本地工具 |
| 迁移成本 | 全栈重写需 2-3 周，渐进式重构可边上线边改 |
| 风险 | 全栈重写需同时迁移前后端，回归测试面积大 |

**结论**: 技术选型没问题，问题在代码组织。保持 Flask + SQLite，重构架构和工程结构。

### 2.2 重构原则

1. **小步快跑** — 每个 Phase 产出可独立验证的成果，不做大爆炸式重构
2. **先分层后优化** — 先建立分层架构，再在此基础上做性能优化
3. **测试先行** — 重构前先补关键路径测试，确保重构不引入回归
4. **向后兼容** — API 路径保持不变，前端可逐步迁移

---

## 三、目标架构

### 3.1 后端分层架构

```
Route 层 (api/)          — 只负责 HTTP 请求/响应、参数校验
    ↓
Service 层 (services/)    — 业务逻辑、数据聚合、计算
    ↓
Repository 层 (repos/)    — 数据访问（基于 SQLAlchemy ORM 查询）
    ↓
Model 层 (models/)         — SQLAlchemy ORM 模型定义
    ↓
Database (SQLite → 将来可无缝切换 PostgreSQL/MySQL)
```

**关键设计**: 数据访问层基于 SQLAlchemy ORM，当前连接 SQLite。将来换数据库只需改一行连接字符串，ORM 模型和 repo 代码零改动。

### 3.2 目标目录结构

```
tmall-dashboard/
├── app.py                      # Flask 入口（精简，只做 app 创建和蓝图注册）
├── config.py                   # 配置加载（从 config.yaml 读取）
├── config.yaml                 # 配置文件（保留）
├── requirements.txt
│
├── api/                        # 路由层 — 按业务域拆分
│   ├── __init__.py
│   ├── kpi_api.py              # KPI 与概览 (~10 路由)
│   ├── product_api.py          # 商品管理 (~12 路由)
│   ├── ad_api.py               # 推广分析 (~4 路由)
│   ├── refund_api.py           # 退款预警 (~1 路由)
│   ├── action_api.py           # 运营动作 (~5 路由)
│   ├── alert_api.py            # 预警系统 (~6 路由)
│   ├── health_api.py           # 健康度 (~1 路由)
│   ├── review_api.py           # 评价分析 (~4 路由)
│   ├── market_api.py           # 市场分析 (~9 路由)
│   ├── compare_api.py          # 周期对比 (~2 路由)
│   ├── import_api.py           # 数据导入 (~3 路由)
│   ├── system_api.py           # 系统/日志/备份/导出 (~8 路由)
│   ├── chart_event_api.py      # 图表事件标注 (~3 路由)
│   ├── task_api.py             # 定时任务 + 任务看板 (~10 路由)
│   └── tool_api.py             # 工具箱 (~3 路由)
│
├── services/                   # 业务逻辑层
│   ├── __init__.py
│   ├── kpi_service.py          # KPI 计算、环比、异常检测
│   ├── product_service.py      # 商品评分、筛选、排序逻辑
│   ├── health_service.py       # 健康度 12 维度评分算法
│   ├── alert_service.py        # 预警规则引擎
│   ├── market_service.py       # 市场分析、蓝海词算法
│   ├── review_service.py       # 情感分析、维度提取
│   ├── compare_service.py      # 周期对比逻辑
│   ├── report_service.py       # 报告生成
│   ├── import_service.py       # 导入编排（Sheet 识别 → 清洗 → 入库）
│   └── scheduler_service.py    # 定时任务调度
│
├── repos/                      # 数据访问层
│   ├── __init__.py
│   ├── base_repo.py            # 基类：通用 CRUD、分页查询（基于 SQLAlchemy session）
│   ├── product_repo.py         # products 表操作
│   ├── data_repo.py            # daily/weekly/monthly_data 表操作
│   ├── paid_repo.py            # paid_detail 表操作
│   ├── health_repo.py          # product_health 表操作
│   ├── review_repo.py          # reviews / review_summary 表操作
│   ├── market_repo.py          # market_analysis 表操作
│   ├── action_repo.py          # operation_actions 表操作
│   ├── alert_repo.py           # alerts / alert_rules 表操作
│   └── system_repo.py          # logs / chart_events / scheduled_tasks
│
├── models/                     # SQLAlchemy ORM 模型
│   ├── __init__.py             # db = SQLAlchemy() 实例
│   ├── product.py              # Product 模型
│   ├── data.py                 # DailyData / WeeklyData / MonthlyData 模型
│   ├── paid.py                 # PaidDetail 模型
│   ├── health.py               # ProductHealth 模型
│   ├── review.py               # Review / ReviewSummary 模型
│   ├── market.py               # MarketAnalysis / MarketKeywordOpportunity 模型
│   ├── action.py               # OperationAction 模型
│   ├── alert.py                # Alert / AlertRule 模型
│   └── system.py               # ChartEvent / ScheduledTask / OperationLog / TaskItem / UserKpi / ProductNote / ProductTag / KeywordMetric / ShopTarget / ProductTarget
│
├── migrations/                 # Alembic 数据库迁移
│   ├── env.py                  # Alembic 环境配置（读取 models 自动检测变更）
│   ├── alembic.ini             # Alembic 配置
│   └── versions/               # 迁移脚本目录
│       ├── 001_initial_schema.py   # 从现有 db.py 的 CREATE TABLE 生成
│       ├── 002_health_dims.py      # 健康度维度字段
│       ├── 003_product_cols.py     # 商品扩展字段
│       └── ...                     # 后续新增字段用 alembic revision 自动生成
│
├── utils/                      # 通用工具函数
│   ├── __init__.py
│   ├── format.py               # _fmt_wan 等格式化函数
│   ├── period.py               # get_prev_period 等周期计算
│   ├── security.py             # 白名单校验、输入验证
│   └── cache.py                # 简易内存缓存（TTL）
│
├── scripts/                    # 独立运行脚本（保留）
│   ├── import_data.py          # 精简后：调用 import_service
│   ├── import_smart.py
│   ├── import_smart_daily.py
│   ├── import_market.py
│   ├── market_analyzer.py      # 精简后：调用 market_service
│   ├── calc_health.py          # 精简后：调用 health_service
│   ├── generate_report.py      # 精简后：调用 report_service
│   └── utils.py
│
├── frontend/                   # 前端（引入 Vite 构建）
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js             # 入口
│   │   ├── modules/
│   │   │   ├── kpi.js
│   │   │   ├── trend.js
│   │   │   ├── products.js     # 可进一步拆分
│   │   │   ├── ad.js
│   │   │   ├── refund.js
│   │   │   ├── actions.js
│   │   │   ├── target.js
│   │   │   ├── health.js
│   │   │   ├── review.js
│   │   │   ├── market.js
│   │   │   ├── lifecycle.js
│   │   │   ├── compare.js
│   │   │   └── toolbox.js
│   │   ├── core/
│   │   │   ├── api.js          # 统一 API 调用封装
│   │   │   ├── router.js       # Tab 路由
│   │   │   ├── theme.js        # 主题切换
│   │   │   └── utils.js        # 前端工具函数
│   │   └── styles/
│   │       ├── base.css        # 变量、重置
│   │       ├── layout.css      # 侧边栏、顶栏、布局
│   │       ├── components.css  # 卡片、表格、按钮
│   │       ├── charts.css      # 图表相关
│   │       └── themes.css      # 暗/亮主题变量
│   └── dist/                   # 构建产物（由 Vite 生成）
│
├── templates/                  # Jinja2 模板（保留，逐步精简）
│   ├── dashboard.html
│   ├── preview.html
│   └── partials/
│
├── data/                       # 数据目录（统一管理）
│   ├── dashboard.db            # 唯一数据库文件
│   ├── backups/
│   ├── raw/
│   └── uploads/
│
├── tests/                      # 测试
│   ├── conftest.py             # pytest fixtures
│   ├── test_import.py          # 导入逻辑测试
│   ├── test_health.py          # 健康度算法测试
│   ├── test_api.py             # API 端点测试
│   └── test_report.py          # 报告生成测试（已有）
│
└── docs/
    ├── PRD.md
    └── REFACTOR_PLAN.md        # 本文件
```

---

## 四、分阶段重构计划

### Phase 0: 准备工作（1 天）

**目标**: 建立安全网，确保重构可回退

| 序号 | 任务 | 产出 |
|------|------|------|
| 0.1 | 清理无用目录和文件 | 删除 `.superpowers/`、`docs/superpowers/`、`.vite/` 缓存、5 份重复 output 目录中的 4 份 |
| 0.2 | 统一数据库文件 | 确认 `data/dashboard.db` 为唯一数据库，删除根目录 `dashboard.db`（或建软链） |
| 0.3 | 整理 `.gitignore` | 排除 `*.db`、`data/backups/`、`data/raw/`、`data/uploads/`、`incoming/`、`output*/`、`__pycache__/` |
| 0.4 | 为关键路径补充冒烟测试 | `tests/test_smoke.py`：启动 app、访问 `/`、`/api/status`、`/api/kpi` 等核心端点 |
| 0.5 | 全量备份当前代码 | Git tag `v-before-refactor` |

### Phase 1: 后端分层拆分 + ORM 引入（4-5 天）

**目标**: 将 3638 行的 `data_api.py` 拆为分层架构，引入 SQLAlchemy ORM 和 Alembic 迁移

#### Step 1.0: 安装依赖 + 初始化 ORM（0.5 天）

```txt
# requirements.txt 新增
flask-sqlalchemy==3.1.1
alembic==1.13.3
```

```python
# models/__init__.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
```

```python
# app.py 改造
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/dashboard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
```

初始化 Alembic：
```bash
# 在项目根目录执行
flask db init          # 生成 migrations/ 目录
flask db migrate -m "initial schema"   # 自动检测模型生成迁移
flask db upgrade        # 执行迁移
```

#### Step 1.1: 提取工具函数 → `utils/`（0.5 天）

从 `data_api.py` 中提取：
- `get_prev_period()` → `utils/period.py`
- `_fmt_wan()` → `utils/format.py`
- `calc_score()` → `utils/scoring.py`
- `DIMENSION_MAP`、`ALLOWED_FIELDS`、`sort_whitelist` → `models/constants.py`（保留为普通常量，不依赖 ORM）
- `_parse_cron_expr()`、`_cron_to_label()` → `utils/cron.py`

#### Step 1.2: 定义 ORM 模型 → `models/`（1 天）

将 `db.py` 中的 20 张表定义为 SQLAlchemy 模型：

```python
# models/product.py
from models import db

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, unique=True, nullable=False)
    title = db.Column(db.Text)
    category = db.Column(db.Text)
    tier = db.Column(db.Text)
    style = db.Column(db.Text)
    scene = db.Column(db.Text)
    status = db.Column(db.Text, default='active')
    remark = db.Column(db.Text)
    image_url = db.Column(db.Text)
    manager = db.Column(db.Text, default='')
    starred = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # 关系定义
    daily_records = db.relationship('DailyData', backref='product', lazy='dynamic')
    weekly_records = db.relationship('WeeklyData', backref='product', lazy='dynamic')
    monthly_records = db.relationship('MonthlyData', backref='product', lazy='dynamic')
```

```python
# models/data.py
class MonthlyData(db.Model):
    __tablename__ = 'monthly_data'
    __table_args__ = (db.UniqueConstraint('product_id', 'month'),)
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text, db.ForeignKey('products.product_id'), nullable=False)
    month = db.Column(db.Text, nullable=False)
    payment_amount = db.Column(db.Float, default=0)
    # ... 其余字段按 db.py schema 逐一映射
```

**注意事项**：
- 模型字段必须与现有数据库完全对齐，否则 `alembic migrate` 会生成多余迁移
- 先定义模型，再跑 `alembic stamp head`（标记当前数据库已处于最新状态，不实际执行迁移）
- 之后再新增字段时用 `alembic revision --autogenerate` 自动生成迁移

#### Step 1.3: 提取数据访问层 → `repos/`（1 天）

将所有 SQL 查询从路由函数提取到 Repository，用 ORM 查询替代手写 SQL：

```python
# repos/product_repo.py
from models import db
from models.product import Product
from models.data import MonthlyData

class ProductRepo:
    @staticmethod
    def get_by_id(product_id):
        return Product.query.filter_by(product_id=product_id).first()

    @staticmethod
    def list_products(dim, period, page=1, per_page=20, sort='payment_amount', order='desc'):
        table_map = {'monthly': MonthlyData, 'weekly': WeeklyData, 'daily': DailyData}
        model = table_map[dim]
        query = db.session.query(Product, model).join(
            model, Product.product_id == model.product_id
        ).filter(model.month == period)  # 或 week_start / date

        # 排序
        sort_col = getattr(model, sort, None) or getattr(Product, sort)
        query = query.order_by(sort_col.desc() if order == 'desc' else sort_col.asc())

        # 分页
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def update_field(product_id, field, value):
        Product.query.filter_by(product_id=product_id).update({field: value})
        db.session.commit()
```

**收益**: 告别手写 SQL 字符串拼接，SQL 注入风险从架构层面消除；查询逻辑可读性大幅提升。

#### Step 1.4: 提取业务逻辑层 → `services/`（1 天）

将路由中的计算逻辑提取到 Service（与原方案一致）：
- `kpi_service.py` — KPI 聚合、环比计算、异常检测
- `health_service.py` — 12 维度评分算法（从 `calc_health.py` 和路由中合并）
- `alert_service.py` — 预警规则引擎、`generate_alerts()`
- `import_service.py` — Sheet 识别、清洗编排
- `market_service.py` — 市场分析算法

Service 层调用 repo 层，不直接接触 db.session（除了需要事务控制的场景）。

#### Step 1.5: 按业务域拆分路由 → `api/*.py`（1 天）

将 84 个路由按业务域拆分到 15 个文件，每个文件 50-300 行。

每个路由函数精简为：参数提取 → 调 service → 返回 JSON。

#### Step 1.6: 废弃旧 db.py + 验证迁移（0.5 天）

| 任务 | 做法 |
|------|------|
| 确认 ORM 模型与现有数据库对齐 | `alembic stamp head` 标记当前状态，不执行迁移 |
| 测试迁移流程 | 新增一个测试字段 → `alembic revision --autogenerate` → `alembic upgrade head` → 验证 |
| 废弃 `db.py` 的 `init_db()` | 改为 `db.create_all()`（仅用于全新建库场景），迁移统一走 Alembic |
| 保留 `get_db()` 兼容 | 过渡期内 `get_db()` 返回 `db.session`，让未迁移的 scripts 仍能工作 |

**迁移安全性保障**：
```bash
# 重构前：备份现有数据库
cp data/dashboard.db data/backups/dashboard_pre_refactor.db

# 首次切换到 Alembic 时
flask db stamp head    # 告诉 Alembic "当前数据库已是最新"，不执行任何 SQL
# 之后每次新增字段
flask db migrate -m "add xxx field"
flask db upgrade       # 只执行新生成的迁移
```

将来换数据库时：
```python
# 只需改 app.py 一行
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/dashboard'
# 然后
flask db upgrade     # Alembic 自动在新数据库上创建所有表
```

### Phase 2: 前端工程化（2-3 天）

**目标**: 引入 Vite 构建，解决 7000 行 bundle 问题

#### Step 2.1: 初始化 Vite 项目（0.5 天）

```json
// frontend/package.json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "vite": "^5.0.0"
  }
}
```

配置 Vite：
- 开发模式 proxy 到 Flask `:5000`
- 构建产物输出到 `static/dist/`
- Flask 的 `dashboard.html` 引用 `/static/dist/main.js`

#### Step 2.2: 迁移 JS 到 ES 模块（1 天）

- 将 `static/js/*.js` 复制到 `frontend/src/modules/*.js`
- 将全局函数改为 `export function`
- `main.js` 作为入口，统一 import 所有模块
- 删除 `bundle.js` 和 `bundle.min.js`（由 Vite 构建替代）

#### Step 2.3: 拆分 CSS（0.5 天）

将 1579 行的 `dashboard.css` 拆为：
- `base.css` — CSS 变量、reset、字体
- `layout.css` — 侧边栏、顶栏、网格布局
- `components.css` — 卡片、表格、按钮、弹窗
- `themes.css` — 暗色/亮色主题变量

#### Step 2.4: 统一 API 调用封装（0.5 天）

```javascript
// frontend/src/core/api.js
export async function fetchAPI(path, params = {}) {
  const url = new URL(`/api/${path}`, location.origin);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}
```

替换各模块中散落的 `fetch()` 调用。

### Phase 3: 性能优化（2 天）

**目标**: 解决查询慢、加载慢问题

#### Step 3.1: 后端查询优化（1 天）

| 优化项 | 做法 | 预期收益 |
|--------|------|---------|
| 内存缓存 | `utils/cache.py` 实现 TTL 缓存，缓存 KPI/趋势结果 60s | 重复请求 0ms |
| 商品列表字段裁剪 | 前端列配置驱动后端 SELECT，不再全字段返回 | 响应体积减 40% |
| 复合索引补全 | 为 `monthly_data(product_id, month)` 等加联合索引 | 查询提速 5-10x |
| 预计算健康度 | 导入数据后异步计算并持久化，查询时直接读取 | 健康度查询 0ms |

#### Step 3.2: 前端加载优化（0.5 天）

| 优化项 | 做法 | 预期收益 |
|--------|------|---------|
| 代码分割 | Vite 自动按 Tab 懒加载 | 首屏 JS 减 60% |
| 图表按需加载 | ECharts 按需引入模块（仅 import 用到的图表类型） | ECharts 体积减 50% |
| 请求合并 | Tab 切换时并行请求该 Tab 所有数据 | 减少 RTT |

#### Step 3.3: 数据库维护（0.5 天）

- 编写 `scripts/vacuum_db.py` 定期 VACUUM 压缩数据库
- 清理 `data/raw/` 中 4 月的旧 xlsx 文件（已导入）
- 配置 `PRAGMA cache_size` 提升 SQLite 内存缓存

### Phase 4: 测试与质量（1-2 天）

**目标**: 建立测试基线，防止回归

#### Step 4.1: 单元测试（1 天）

```
tests/
├── conftest.py              # Flask test client fixture、临时 DB fixture
├── test_smoke.py            # 冒烟测试：核心端点可达
├── test_import.py           # 导入逻辑：Sheet 识别、数据清洗
├── test_health.py           # 健康度算法：12 维度评分正确性
├── test_kpi_service.py      # KPI 计算：环比、异常检测
├── test_period_utils.py     # 周期计算工具函数
└── test_api/                # API 集成测试
    ├── test_product_api.py
    ├── test_kpi_api.py
    └── test_import_api.py
```

优先覆盖：导入逻辑、健康度算法、KPI 计算（最容易出错且影响最大）。

#### Step 4.2: 代码规范（0.5 天）

- 添加 `.flake8` 或 `pyproject.toml` 配置 ruff
- 添加 `frontend/.eslintrc.js`
- Python 文件添加类型注解（逐步补充，先补 service 层）

---

## 五、重构前后对比

### 5.1 文件规模对比

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 最大单文件行数 | 3638 行 (`data_api.py`) | ~300 行 |
| API 路由文件数 | 1 | 15 |
| 后端分层 | 0 层 | 3 层 (Route/Service/Repo) |
| 数据访问方式 | 手写 SQL 字符串拼接 | SQLAlchemy ORM |
| 数据库迁移 | 手写 ALTER TABLE (try/except) | Alembic 自动迁移 (可回滚) |
| 换数据库成本 | 重写 200+ 处 SQL | 改 1 行连接字符串 |
| JS 构建方式 | 手动拼接 | Vite 自动构建 |
| CSS 文件数 | 1 (1579 行) | 5 (各 200-400 行) |
| 测试文件数 | 1 | 8+ |

### 5.2 开发体验对比

| 场景 | 重构前 | 重构后 |
|------|--------|--------|
| 新增一个 API | 在 3638 行文件中找位置，写 SQL+逻辑+路由 | 新建路由文件，调用 service，50 行搞定 |
| 修改健康度算法 | 在 `calc_health.py` 和路由中各改一份 | 只改 `health_service.py` |
| 修改前端某 Tab | 改源文件 → 手动拼 bundle → 压缩 | 改模块文件 → `vite build` 自动完成 |
| 新增数据库字段 | 在 `init_db()` 里加 ALTER TABLE | 定义模型字段 → `alembic migrate` 自动生成迁移 |
| 排查 bug | 全文搜索 3638 行 | 定位到对应 service/repo 文件 |
| 换数据库 | 重写所有 SQL 查询 | 改 `SQLALCHEMY_DATABASE_URI` 一行 |

---

## 六、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| 拆分路由时遗漏端点 | 中 | 高 | Phase 0 先建冒烟测试覆盖所有 84 个路由；拆分后逐个验证 |
| 数据库迁移破坏现有数据 | 低 | 高 | 迁移前自动备份；`alembic stamp head` 标记现有库；迁移脚本幂等设计 |
| ORM 模型与现有 schema 不对齐 | 中 | 中 | 逐表核对 `db.py` 的 CREATE TABLE；用 `alembic stamp head` 避免首次迁移执行 |
| 前端 Vite 迁移引入 bug | 中 | 中 | 保留 `bundle.min.js` 作为 fallback；新旧并行运行一周 |
| 重构周期过长影响业务 | 中 | 中 | 每个 Phase 独立可交付；Phase 1 完成后即可上线 |
| Service/Repo 拆分过度 | 低 | 低 | 以业务域为边界，不过度拆分；单文件超 300 行才考虑再拆 |
| ORM 查询性能不如手写 SQL | 低 | 低 | 对复杂查询用 `db.session.execute(text())` 保留原生 SQL；其余用 ORM |

---

## 七、执行优先级排序

按「投入产出比」排序，建议按以下顺序执行：

```
Phase 0 (1天)  ──→  Phase 1 (4-5天)  ──→  Phase 3.1 (1天)  ──→  Phase 2 (2-3天)  ──→  Phase 4 (1-2天)
   准备              后端拆分+ORM           后端性能              前端工程化            测试质量
  (安全网)          (最大收益)             (快速见效)            (中期收益)           (长期保障)
```

**建议先做 Phase 0 + Phase 1**，这两步完成后，可维护性已有质的提升，且数据库已具备可迁移性。Phase 2-4 可根据实际精力逐步推进。

### 架构演进路线

```
现在 ─────────────────── Phase 1 完成 ─────────────────── 将来需要时
  │                         │                         │
  │  Flask + raw SQL        │  Flask + SQLAlchemy     │  Flask (或 FastAPI)
  │  + SQLite               │  + Alembic              │  + PostgreSQL/MySQL
  │  + 手写 ALTER TABLE     │  + SQLite (不变)        │  + 同一套 ORM 模型
  │  + 无构建               │  + Vite 构建            │  + 同一套 Alembic 迁移
  │                         │  + 分层架构              │  + 改连接字符串即完成迁移
  └── 分层拆分 ────────────→└── 引入 ORM 工具链 ──────→└── 只改连接配置
```

---

## 八、附：路由拆分映射表

`data_api.py` 84 个路由 → 15 个文件的完整映射：

| 目标文件 | 路由 | 数量 |
|---------|------|------|
| `kpi_api.py` | `/api/status`, `/api/kpi`, `/api/trend`, `/api/multi_trend`, `/api/anomalies`, `/api/target_progress`, `/api/customer_analysis`, `/api/funnel`, `/api/industry_benchmark`, `/api/report` | 10 |
| `product_api.py` | `/api/products`, `/api/star`, `/api/products/<id>/field`, `/api/batch_update`, `/api/notes/*`, `/api/product_tags`, `/api/batch_tags` | 12 |
| `ad_api.py` | `/api/ad_performance`, `/api/ad_alerts`, `/api/ad_trend` | 3 |
| `refund_api.py` | `/api/refund_alert` | 1 |
| `action_api.py` | `/api/actions`, `/api/action_stats` | 5 |
| `alert_api.py` | `/api/alerts`, `/api/alert_rules`, `/api/alert_checks` | 6 |
| `health_api.py` | `/api/health` | 1 |
| `review_api.py` | `/api/upload/reviews`, `/api/reviews/*` | 4 |
| `market_api.py` | `/api/upload/market`, `/api/market/*` | 9 |
| `compare_api.py` | `/api/compare`, `/api/lifecycle` | 2 |
| `import_api.py` | `/api/upload/data`, `/api/import_progress`, `/api/upload/keywords` | 3 |
| `system_api.py` | `/api/periods`, `/api/backup`, `/api/export`, `/api/logs` | 8 |
| `chart_event_api.py` | `/api/chart_events` | 3 |
| `task_api.py` | `/api/scheduled_tasks/*`, `/api/tasks`, `/api/user_kpis` | 10 |
| `tool_api.py` | `/api/tools/*`（已存在） | 3 |

**合计**: 84 路由，平均每文件 5.6 个路由。
