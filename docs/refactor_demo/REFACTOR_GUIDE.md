# 重构执行指南 — 给 Codex 的操作手册

> 本文档是 `docs/refactor_demo/` 中所有 demo 代码的使用说明。
> Codex 按此文档逐步执行重构，每步可独立验证。

---

## 一、概览

### 1.1 当前状态

- Phase 0 已完成：目录清理、数据库统一、.gitignore、冒烟测试（87 个通过）、Git tag `v-before-refactor`
- 重构方案文档：`docs/REFACTOR_PLAN.md`
- Demo 代码模板：`docs/refactor_demo/`（本目录）

### 1.2 Demo 目录结构

```
docs/refactor_demo/
├── REFACTOR_GUIDE.md          ← 本文件（执行指南）
│
├── models/                     ← ORM 模型模板（已按 db.py schema 完整定义）
│   ├── __init__.py             ← db = SQLAlchemy()
│   ├── constants.py            ← 安全白名单常量
│   ├── product.py              ← Product 模型
│   ├── data.py                 ← DailyData / WeeklyData / MonthlyData
│   ├── paid.py                 ← PaidDetail
│   ├── health.py               ← ProductHealth
│   ├── review.py               ← Review / ReviewSummary
│   ├── market.py               ← MarketAnalysis / MarketKeywordOpportunity
│   ├── action.py               ← OperationAction
│   ├── alert.py                ← Alert / AlertRule
│   └── system.py               ← ChartEvent / ScheduledTask / OperationLog / TaskItem / UserKpi / ProductNote / ProductTag / KeywordMetric / ShopTarget / ProductTarget
│
├── repos/                      ← Repository 层模板
│   ├── __init__.py
│   ├── base_repo.py            ← BaseRepo: 通用 CRUD + 分页
│   ├── product_repo.py         ← 商品列表查询、字段更新、星标
│   ├── data_repo.py            ← KPI 聚合、趋势查询、推广数据
│   └── alert_repo.py           ← 预警记录和规则 CRUD
│
├── services/                   ← Service 层模板
│   ├── __init__.py
│   ├── kpi_service.py          ← KPI 概览、环比、异常检测
│   ├── health_service.py       ← 12 维度健康度评分算法
│   ├── alert_service.py        ← 预警规则引擎
│   └── import_service.py       ← 数据导入编排
│
├── api/                        ← API 路由拆分示例（2 个示范，其余照此模式）
│   ├── __init__.py
│   ├── kpi_api.py              ← KPI/趋势/异常 模块（4 个路由示范）
│   └── product_api.py          ← 商品列表/编辑/星标/批量更新（4 个路由示范）
│
├── utils/                      ← 工具函数
│   ├── __init__.py
│   ├── format.py               ← fmt_wan / fmt_percent / calc_change_rate
│   ├── period.py               ← get_prev_period / get_period_range
│   └── cache.py                ← SimpleCache（TTL 内存缓存）
│
├── migrations/                 ← Alembic 迁移配置
│   ├── alembic.ini
│   └── env.py
│
├── frontend/                   ← 前端 Vite 结构
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js             ← 入口（ES Module import）
│       └── core/
│           └── api.js          ← 统一 API 封装
│
├── app.py                      ← Flask 应用入口（工厂模式）
└── config.py                   ← 配置加载
```

### 1.3 重构策略回顾

保持 Flask + SQLite 技术栈，重构代码组织：
- 后端：Route → Service → Repository → Model（4 层分离）
- 数据库：手写 SQL → SQLAlchemy ORM + Alembic 迁移
- 前端：手动拼接 bundle.js → Vite 构建 + ES Module
- 工具函数：散落在路由中 → 集中到 utils/

---

## 二、执行步骤

### Step 1: 安装依赖（0.5 天）

```bash
pip install flask-sqlalchemy==3.1.1 alembic==1.13.3 python-dateutil
```

更新 `requirements.txt`，新增以上依赖。

### Step 2: 创建目录结构

```bash
mkdir -p models repos services utils migrations/versions
```

将 `docs/refactor_demo/models/` 下的所有 `.py` 文件复制到项目根目录的 `models/`。
对 `repos/`、`services/`、`utils/` 做同样操作。

**注意**：`__init__.py` 文件也要复制，确保包能正确导入。

### Step 3: 改造 app.py

1. 备份当前 `app.py` 为 `app_legacy.py`
2. 将 `docs/refactor_demo/app.py` 复制为新的 `app.py`
3. 将 `docs/refactor_demo/config.py` 复制到项目根目录

**验证**：
```bash
python -c "from app import app; print('App created successfully')"
```

### Step 4: 初始化 ORM + Alembic

```bash
# 1. 初始化 Alembic（如果 migrations/ 已有 env.py 则跳过）
flask db init

# 2. 标记当前数据库为最新状态（不执行实际迁移）
#    因为模型已与现有数据库 schema 对齐
flask db stamp head

# 3. 验证：生成一个空迁移（应该没有变更）
flask db migrate -m "verify initial state"
# 如果输出 "No changes in schema detected" 则模型与数据库对齐
```

**关键点**：
- 模型字段已按 `db.py` 的 `init_db()` 完整定义，包括所有 ALTER TABLE 迁移新增的字段
- `flask db stamp head` 告诉 Alembic 当前数据库已是最新，不需要执行迁移
- 之后新增字段时，用 `flask db migrate -m "add xxx"` 自动生成迁移

### Step 5: 提取工具函数（0.5 天）

从 `api/data_api.py` 中提取以下函数到对应文件：

| 原始位置（data_api.py） | 目标文件 | 函数 |
|------------------------|---------|------|
| ~第 45-60 行 | `utils/format.py` | `_fmt_wan()`, `_fmt_percent()` 等 |
| ~第 60-75 行 | `utils/period.py` | `get_prev_period()` |
| ~第 75-78 行 | `utils/cron.py`（新建） | `_parse_cron_expr()`, `_cron_to_label()` |
| 各路由中 | `utils/format.py` | `calc_change_rate()` |

**操作方式**：
1. 在 `data_api.py` 中搜索函数定义
2. 将函数体复制到对应 utils 文件
3. 在 `data_api.py` 中替换为 `from utils.format import fmt_wan` 等导入
4. 运行测试验证功能不变

**验证**：
```bash
python -m pytest tests/test_smoke.py -v
```

### Step 6: 迁移路由到新 API 文件（2-3 天）

这是最大的工作量。将 `data_api.py` 的 61+ 路由按业务域拆分。

#### 6.1 路由分组对照表

| 新文件 | 蓝图名 | 原始路由 | 路由数 |
|--------|--------|---------|--------|
| `api/kpi_api.py` | kpi_bp | `/api/status`, `/api/kpi`, `/api/trend`, `/api/anomalies`, `/api/multi_trend`, `/api/customer_analysis`, `/api/funnel` | ~7 |
| `api/product_api.py` | product_bp | `/api/products`, `/api/products/<id>/field`, `/api/star`, `/api/batch_update`, `/api/product_tags` (GET/POST/DELETE), `/api/batch_tags` (POST/DELETE) | ~8 |
| `api/ad_api.py` | ad_bp | `/api/ad_performance`, `/api/ad_alerts`, `/api/ad_trend`, `/api/traffic_structure` | ~4 |
| `api/refund_api.py` | refund_bp | `/api/refund_alert` | ~1 |
| `api/action_api.py` | action_bp | `/api/actions` (GET/POST), `/api/actions/<id>` (PUT/DELETE), `/api/action_stats` | ~5 |
| `api/alert_api.py` | alert_bp | `/api/alerts`, `/api/alerts/<id>/dismiss`, `/api/alert_rules` (GET/POST/DELETE), `/api/alert_checks` | ~7 |
| `api/health_api.py` | health_bp | `/api/health` | ~1 |
| `api/review_api.py` | review_bp | `/api/upload/reviews`, `/api/reviews/summary`, `/api/reviews/list`, `/api/reviews/products`, `/api/review` | ~5 |
| `api/market_api.py` | market_bp | `/api/upload/market`, `/api/market/summary`, `/api/market/keywords`, `/api/market/need_stats`, `/api/market/rankings`, `/api/market/histograms`, `/api/market/opportunities`, `/api/market/reports` | ~8 |
| `api/compare_api.py` | compare_bp | `/api/compare`, `/api/target_progress`, `/api/product_target_progress` | ~3 |
| `api/import_api.py` | import_bp | `/api/upload/data`, `/api/upload/keywords`, `/api/import_progress/<id>` | ~3 |
| `api/system_api.py` | system_bp | `/api/periods`, `/api/backup`, `/api/logs` (GET/POST), `/api/export`, `/api/industry_benchmark` | ~6 |
| `api/chart_event_api.py` | chart_event_bp | `/api/chart_events` (GET/POST/DELETE) | ~3 |
| `api/task_api.py` | task_bp | `/api/tasks`, `/api/tasks/<id>` (DELETE), `/api/user_kpis` (GET/POST), `/api/user_kpis/<id>` (PUT/DELETE), `/api/scheduled_tasks` (GET/POST), `/api/scheduled_tasks/<id>` (PUT/DELETE), `/api/scheduled_tasks/<id>/run`, `/api/notes` (GET/POST/DELETE) | ~12 |
| `api/tool_api.py` | tool_bp | `/api/report` | ~1 |

#### 6.2 每个路由的迁移步骤

以 `/api/kpi` 为例：

1. **阅读原始代码**：在 `data_api.py` 中找到 `@data_bp.route('/api/kpi')` 函数
2. **提取业务逻辑**：将 SQL 查询和计算逻辑移到对应的 Service/Repo
3. **精简路由**：路由函数只保留参数提取 + 调用 service + 返回 JSON
4. **在新文件中创建**：复制到 `api/kpi_api.py`，改用 `kpi_bp`
5. **在 `app.py` 中注册蓝图**
6. **运行测试**

**参照 `api/kpi_api.py` 和 `api/product_api.py` 的写法**——它们展示了完整的模式。

#### 6.3 迁移验证清单

每个路由迁移后验证：
- [ ] API 路径不变（前端零改动）
- [ ] 返回 JSON 结构不变
- [ ] 冒烟测试通过
- [ ] 手动访问该端点返回正确数据

```bash
# 每迁移一批路由后运行
python -m pytest tests/test_smoke.py -v
```

### Step 7: 废弃旧 data_api.py

1. 确认所有路由已迁移完毕
2. 在 `app.py` 中注释掉 `data_bp` 注册
3. 运行完整测试
4. 将 `data_api.py` 重命名为 `data_api_legacy.py`（不立即删除，保留参考）

### Step 8: 前端 Vite 改造（2-3 天）

#### 8.1 初始化

```bash
# 在项目根目录
cd frontend
npm install
```

#### 8.2 迁移 JS 模块

1. 将 `static/js/` 下的每个文件改为 ES Module
2. 添加 `export` 到需要被其他模块调用的函数
3. 在 `main.js` 中 `import` 各模块
4. 删除 `bundle.js` 和 `bundle.min.js`

**参照 `frontend/src/main.js` 和 `frontend/src/core/api.js` 的模式。**

#### 8.3 迁移 CSS

将 `static/css/dashboard.css`（1579 行）拆分为：
- `styles/base.css` — CSS 变量、reset
- `styles/layout.css` — 侧边栏、顶栏、布局
- `styles/components.css` — 卡片、表格、按钮
- `styles/charts.css` — 图表样式
- `styles/themes.css` — 暗/亮主题变量

#### 8.4 构建

```bash
npm run build  # 产物输出到 static/dist/
```

在 `templates/dashboard.html` 中将 script 引用从 `bundle.min.js` 改为 Vite 产物。

### Step 9: 数据库迁移框架上线

此后新增字段的标准流程：

```bash
# 1. 在 models/ 中修改模型（添加字段）
# 2. 自动生成迁移
flask db migrate -m "add new_field to products"

# 3. 检查生成的迁移脚本
cat migrations/versions/xxx_add_new_field_to_products.py

# 4. 执行迁移
flask db upgrade

# 5. 如需回滚
flask db downgrade -1
```

**不再需要**在 `db.py` 中手写 `ALTER TABLE` 和 `try/except`。

---

## 三、关键注意事项

### 3.1 模型与数据库对齐

Demo 中的 ORM 模型已按 `db.py` 的完整 schema 定义（包括所有 ALTER TABLE 迁移字段）。迁移到项目根目录后：

1. 运行 `flask db stamp head` 标记当前状态
2. 运行 `flask db migrate` 验证无差异（输出 "No changes"）
3. 如果有差异，检查模型字段是否与数据库实际列完全对齐

```bash
# 检查数据库实际列
sqlite3 data/dashboard.db "PRAGMA table_info(products);"
```

### 3.2 API 向后兼容

- 所有 API 路径**保持不变**（如 `/api/kpi` 仍是 `/api/kpi`）
- 返回 JSON 结构**保持不变**
- 前端在 Phase 2 才迁移，Phase 1 期间前端零改动

### 3.3 安全设计保留

Demo 中保留了原有的安全设计：
- `ALLOWED_FIELDS` — 行内编辑字段白名单
- `SORT_WHITELIST` — 排序字段白名单
- `DIMENSION_MAP` — 维度参数白名单（防止 SQL 注入）

重构后这些常量在 `models/constants.py` 中集中管理。

### 3.4 渐进式迁移

不要一次性迁移所有路由。建议顺序：
1. 先迁移 KPI/Products（最高频使用，有 demo 参考）
2. 运行测试验证
3. 再迁移 Alert/Health/Action
4. 最后迁移 Market/Review/Import

### 3.5 测试策略

```bash
# Phase 1 期间持续运行
python -m pytest tests/test_smoke.py -v

# Phase 1 完成后补充
python -m pytest tests/ -v --tb=short
```

每迁移一个路由模块，手动验证对应的前端页面功能正常。

---

## 四、文件复制清单

执行时按此清单将 demo 文件复制到项目对应位置：

| Demo 路径 | 目标路径 | 操作 |
|-----------|---------|------|
| `models/__init__.py` | `models/__init__.py` | 新建 |
| `models/constants.py` | `models/constants.py` | 新建 |
| `models/product.py` | `models/product.py` | 新建 |
| `models/data.py` | `models/data.py` | 新建 |
| `models/paid.py` | `models/paid.py` | 新建 |
| `models/health.py` | `models/health.py` | 新建 |
| `models/review.py` | `models/review.py` | 新建 |
| `models/market.py` | `models/market.py` | 新建 |
| `models/action.py` | `models/action.py` | 新建 |
| `models/alert.py` | `models/alert.py` | 新建 |
| `models/system.py` | `models/system.py` | 新建 |
| `repos/__init__.py` | `repos/__init__.py` | 新建 |
| `repos/base_repo.py` | `repos/base_repo.py` | 新建 |
| `repos/product_repo.py` | `repos/product_repo.py` | 新建 |
| `repos/data_repo.py` | `repos/data_repo.py` | 新建 |
| `repos/alert_repo.py` | `repos/alert_repo.py` | 新建 |
| `services/__init__.py` | `services/__init__.py` | 新建 |
| `services/kpi_service.py` | `services/kpi_service.py` | 新建 |
| `services/health_service.py` | `services/health_service.py` | 新建 |
| `services/alert_service.py` | `services/alert_service.py` | 新建 |
| `services/import_service.py` | `services/import_service.py` | 新建 |
| `utils/__init__.py` | `utils/__init__.py` | 新建 |
| `utils/format.py` | `utils/format.py` | 新建 |
| `utils/period.py` | `utils/period.py` | 新建 |
| `utils/cache.py` | `utils/cache.py` | 新建 |
| `api/__init__.py` | `api/__init__.py` | 新建 |
| `api/kpi_api.py` | `api/kpi_api.py` | 新建（示范） |
| `api/product_api.py` | `api/product_api.py` | 新建（示范） |
| `app.py` | `app.py` | 替换（先备份原文件） |
| `config.py` | `config.py` | 新建 |
| `migrations/env.py` | `migrations/env.py` | 新建 |
| `migrations/alembic.ini` | `migrations/alembic.ini` | 新建 |
| `frontend/package.json` | `frontend/package.json` | 新建 |
| `frontend/vite.config.js` | `frontend/vite.config.js` | 新建 |
| `frontend/src/main.js` | `frontend/src/main.js` | 新建 |
| `frontend/src/core/api.js` | `frontend/src/core/api.js` | 新建 |

---

## 五、时间估算

| 步骤 | 预估时间 | 产出 |
|------|---------|------|
| Step 1-2: 依赖 + 目录 | 0.5 天 | 目录结构就绪 |
| Step 3-4: app.py + ORM + Alembic | 0.5 天 | 后端框架就绪 |
| Step 5: 提取工具函数 | 0.5 天 | utils/ 完成 |
| Step 6: 迁移 61 个路由 | 2-3 天 | api/ 完成 |
| Step 7: 废弃旧代码 | 0.5 天 | data_api.py 退役 |
| Step 8: 前端 Vite 改造 | 2-3 天 | 前端模块化 |
| Step 9: 迁移框架上线 | 0.5 天 | 后续新增字段用 Alembic |
| **合计** | **6-8 天** | |

---

## 六、验收标准

### Phase 1 验收（后端重构）

- [ ] `data_api.py` 不再被引用（已重命名为 legacy）
- [ ] 所有 API 路径不变，返回结构不变
- [ ] `tests/test_smoke.py` 全部通过
- [ ] 前端页面功能正常（前端未改动）
- [ ] `flask db migrate` 输出 "No changes"（模型与数据库对齐）
- [ ] 新增一个测试字段，`flask db migrate && flask db upgrade` 成功

### Phase 2 验收（前端重构）

- [ ] `bundle.js` 和 `bundle.min.js` 已删除
- [ ] `frontend/` 目录有完整的 Vite 项目
- [ ] `npm run build` 成功，产物在 `static/dist/`
- [ ] 所有页面功能正常
- [ ] 首屏加载 < 2 秒（本地）
- [ ] JS 按模块分 chunk 加载
