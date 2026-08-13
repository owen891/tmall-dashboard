# TM 1.0 经营闭环实施计划

> **供执行型 Agent 使用：** 必须逐项推进并使用复选框跟踪；实现遵循测试先行，每项完成后执行对应验证。

**目标：** 在保留现有架构的前提下，交付“报表导入、真实经营总览、目标拆解、商品运营动作、结果回算、动作复盘”的 TM 1.0 闭环。

**架构：** 保留一个 Flask 应用、SQLite 和原生 HTML/CSS/JavaScript 工作台。新增业务能力按 Blueprint、service、repository 拆分，`api/data_api.py` 只保留兼容入口；不引入 Vue、React、第二套页面壳或第二个数据库。字段字典是数据口径的唯一来源，所有写操作走事务，数据不可用时必须如实表达。

**技术栈：** Windows 上使用 `py -3`、Flask 3.1、Flask-SQLAlchemy/Alembic、SQLite、pandas/openpyxl、原生 HTML/CSS/JavaScript、现有 Chart.js/ECharts、Node 静态校验、unittest。

---

## 当前基线与发布决策

按 PRD，首发工作台固定为七个一级区域：店铺总览、商品经营、推广分析、生命周期、经营复盘、数据中心、设置。`compare` 降为复盘的辅助能力；`manage` 中的导入、配置和目标分别迁回数据中心、设置和目标页。旧 URL 可保留重定向或兼容提示，但不能继续出现在主导航。

当前事实（2026-08-12）：

- `app.py` 现有六个主页面：`/`、`/products`、`/promotion`、`/lifecycle`、`/compare`、`/manage`，旧版入口为 `/legacy/`。
- `frontend/ui_demo/assets/shell.js` 硬编码了六项导航，并把上传/调度放在全局工具抽屉。
- `api/data_api.py` 仍是约 3,600 行的兼容单体，`frontend/ui_demo/assets/api.js` 直接消费旧响应。
- `db.py` 已有旧 `operation_actions`、`shop_targets`、`product_targets`，但没有 PRD 所需的版本化目标、动作、导入批次实体。
- `py -3 -m unittest discover -s tests -v` 当前通过 107 项；但工厂测试仍可能触碰默认数据库，且页面测试有未关闭响应的 `ResourceWarning`。测试必须改为完全使用临时数据库。

## 目标文件边界

| 文件/目录 | 职责 |
| --- | --- |
| `app.py` | 注册页面路由、旧路由重定向、Blueprint；不承载业务逻辑。 |
| `api/data_api.py` | 兼容旧接口；新 TM 1.0 接口不继续堆在这里。 |
| `api/overview_api.py`、`goals_api.py`、`actions_api.py`、`imports_api.py`、`settings_api.py` | HTTP 参数、状态码、统一响应 envelope。 |
| `services/` | 指标聚合、目标拆解和锁定、动作状态机/回算、分阶段导入编排。 |
| `repos/` | 参数化 SQLite 访问；不访问 Flask request。 |
| `migrations/versions/` | 对现有库的顺序、可追踪迁移。 |
| `docs/FIELD_DICTIONARY.md` | 标准字段、公式、来源、粒度、必填和 R1/R2 状态的唯一权威。 |
| `frontend/ui_demo/assets/api.js` | 唯一 API 客户端；统一解包、错误和可用性处理。 |
| `frontend/ui_demo/assets/shell.js` | 七项导航、共享日期/筛选、共享状态渲染；不嵌入数据中心工作流。 |
| `frontend/ui_demo/pages/`、`assets/*-live.js` | 原生页面及其业务适配器；页面不得直接 `fetch`。 |
| `tests/` | 临时数据库上的契约、领域不变量和兼容冒烟测试。 |

## 任务 1：建立可重复、无副作用的测试基线

**修改：** `app.py`、`db.py`、`tests/test_app_factory.py`、`tests/test_smoke.py`、`README.md`。

- [ ] 为 `create_app({'TESTING': True, 'DATABASE_PATH': ...})` 写失败测试：数据库路径必须只绑定到该 app，不能改变全局 `TMALL_DB_PATH`。
- [ ] 为页面响应写关闭测试，消除 `ResourceWarning`；所有测试在临时目录建立/销毁数据库，不能写入 `data/dashboard.db` 或 `data/backups/`。
- [ ] 在 `db.py` 优先从当前 Flask app 的 `DATABASE_PATH` 解析连接路径；`init_db()` 接受显式路径；生产默认路径继续兼容。
- [ ] README 改为 `py -3 -m pip install -r requirements.txt`、`py -3 app.py`、`py -3 -m unittest discover -s tests -v`，不再宣传裸 `python`。
- [ ] 验证：`py -3 -m unittest discover -s tests -v` 全绿、无 `ResourceWarning`、没有测试副作用。

## 任务 2：收敛为 PRD 的七个一级入口

**修改/新增：** `app.py`、`frontend/ui_demo/assets/shell.js`、`frontend/ui_demo/index.html`、`pages/reviews.html`、`pages/data-center.html`、`pages/settings.html`、`tests/test_app_factory.py`、`scripts/validate_ui_demos.cjs`。

- [ ] 先写路由/manifest/导航失败测试，要求 `/`、`/products`、`/promotion`、`/lifecycle`、`/reviews`、`/data-center`、`/settings` 返回 200；`/compare`、`/manage` 返回兼容重定向。
- [ ] 主导航仅展示七项；`/legacy/` 不进主导航。复盘页承接周期对比辅助能力；数据中心承接导入和调度；设置只承接可编辑系统配置。
- [ ] 生命周期仅在有足够输入时展示算法结论，否则显示“数据积累中”；推广下钻只在相应粒度已导入时开放。不得展示伪造指标。
- [ ] 验证：`node scripts/validate_ui_demos.cjs` 和 `py -3 -m unittest tests.test_app_factory -v`。

## 任务 3：先建立字段、指标和新 API 契约

**新增：** `api/api_response.py`、`api/overview_api.py`、`services/metrics_service.py`、`repos/metrics_repo.py`、`tests/test_api_contract.py`；**修改：** `docs/FIELD_DICTIONARY.md`、`app.py`、`api/__init__.py`、`frontend/ui_demo/assets/api.js`。

- [ ] 先对 `/api/overview` 写契约测试，覆盖 `net_sales`、退款率、费比的 `sum_then_derive`，禁止平均日比例。
- [ ] 完成核心指标的标准键、来源类型、列别名、粒度、必填性、公式、展示格式和无数据行为。
- [ ] 新接口统一返回 `{ok,data,availability,requestId}`；可用性只能是 `available`、`no-data`、`insufficient-data`、`missing-fields`、`calculation-failed`、`source-unavailable` 之一。
- [ ] 实现 `GET /api/overview` 和 `/api/overview/daily-matrix`；旧 `/api/kpi`、`/api/trend` 先兼容不破坏。
- [ ] 验证：契约测试和既有旧接口冒烟测试同时通过。

## 任务 4：实现数据中心的“预览 -> 映射 -> 校验 -> 确认”导入

**新增：** `api/imports_api.py`、`services/import_service.py`、`repos/import_repo.py`、导入迁移、`pages/data-center.html`、`assets/data-center-live.js`、`tests/test_import_workflow.py`；**修改：** `db.py`、`scripts/import_data.py`。

- [ ] 先用临时 `.xlsx` 写导入失败测试：缺必填映射不可确认、预览不写库、错误确认全回滚、同一文件重复确认不重复事实。
- [ ] 增加 `import_batches`、映射模板、`source_type`、source hash、质量摘要和审计字段；按 PRD 的业务唯一键建立/核对约束。
- [ ] 预览返回原列、标准字段、样例、类型、匹配状态、有效/无效行、日期范围、商品数、重复键、预计新增/更新及异常值。
- [ ] 确认导入使用一次事务 upsert，失败不留半成品；1.2 前不实现撤销。
- [ ] 数据中心页面用统一客户端完成完整流程；导入后总览显示新的截至日期和指标。

## 任务 5：实现年度到每日的目标拆解与锁定

**新增：** `api/goals_api.py`、`services/goals_service.py`、`repos/goals_repo.py`、目标迁移、`pages/goals.html`、`assets/goals-live.js`、`tests/test_goals_service.py`；**修改：** `overview.html`、`app.py`。

- [ ] 先测试年度拆解、历史权重为零时的均摊、闰日、分级总额守恒、版本冲突、月锁定和跨月周锁定冲突。
- [ ] 每日目标是原子值；年/季/月/周只按日期集合聚合。保存推荐值、人工值、原因、操作者、时间、版本和锁定状态。
- [ ] 实现 `/api/goals`、`/api/goals/:year`、`/api/goals/:year/periods`，写入必须携带版本号，过期返回 409。
- [ ] 总览显示年/季/月/周/日完成率；目标详情显示重分配预览和冲突原因。

## 任务 6：将泛任务替换为商品运营动作闭环

**新增：** `api/actions_api.py`、`services/actions_service.py`、`repos/actions_repo.py`、动作迁移、`tests/test_action_workflow.py`；**修改：** 商品页、总览页和各自 adapter。

- [ ] 先测试状态机：草稿、待执行、执行中、待观察、待复盘、已完成，以及阻塞/取消/计算失败分支；阻塞必填原因和预计恢复时间；没有复盘结论禁止完成。
- [ ] 一次动作只关联一个商品；批量创建生成多条并共享 `action_group_id`。
- [ ] 保存目的、目标指标、期望变化、观察窗口、动作详情、执行人、计划/完成时间、结果版本、前后指标、计算说明和复盘版本。
- [ ] 成功导入后或每日命令回算观察窗口：数据不全时保持待观察并说明原因；覆盖完整时转待复盘；异常不可伪造零值。
- [ ] 商品抽屉能创建/查看历史动作；总览待办只列动作，排序为逾期、待复盘、执行中、待执行。

## 任务 7：完成经营复盘和真实总览

**修改/新增：** `pages/reviews.html`、`assets/reviews-live.js`、总览页面/adaptor、`tests/test_overview_contract.py`。

- [ ] 复盘默认展示待复盘动作，同屏展示目的、动作、前后指标、系统结果、数据覆盖和干扰因素；复盘必填有效性、原因、结论、后续动作、复盘人、时间。
- [ ] 总览显示数据截至日、覆盖范围、最近成功导入、质量状态、核心指标、五级目标、动作待办、净销售/支付/投放趋势、日度经营矩阵。
- [ ] 执行端到端验收：预览导入 -> 确认导入 -> 总览 -> 生成年度目标 -> 锁定月目标 -> 商品动作 -> 观察期回算 -> 动作复盘。

## 任务 8：设置、兼容整理与发布验收

**新增：** 设置 API/service/repo/迁移及页面 adapter；**修改：** 静态校验、应用工厂测试、README、PRD 实施状态。

- [ ] 设置仅包含店铺名、时区 `Asia/Shanghai`、货币、周起始日、年度目标默认值、生命周期阈值、字段映射和商品视图模板；核心指标公式只读。
- [ ] 每个触及的旧接口先补兼容测试，再委托到新 service 或保持冻结；不在本版本整体重写 `data_api.py`。
- [ ] 发布前运行 `git diff --check`、`node scripts/validate_ui_demos.cjs`、完整 unittest，并在 1366/1920/1024/390 四种视口完成七个主路由和端到端闭环验收。
- [ ] 交接文档说明支持报表、缺失字段、迁移方式、备份恢复和延期项。

## 发布门禁与延期项

1. 任务 3 的字段/指标/可用性契约通过前，不进入导入实现。
2. 导入事实按业务键幂等、目标不变量通过前，不进入动作回算。
3. 临时数据库端到端闭环未通过、或存在伪造数据展示时，不发布。
4. 延期到 1.1/1.2：没有数据来源的推广计划/单元下钻、生命周期/季节算法、导入撤销、多店/权限、泛任务系统、市场/评价/关键词一级模块、Vue/React 迁移。

## 风险检查

当前导入和表结构可能没有独立店铺日度事实，也可能没有可去重的支付买家/新老客来源。发生这种情况时，页面必须显示“字段缺失”或“不可计算”，而不是以零值补齐。这个约束比视觉上的“数据完整”更重要。
