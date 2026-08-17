# TM Dashboard 1.0.0 发布记录

本版本发布号：`1.0.0`

## Phase 1 数据能力与页面体系（2026-08-14）

本阶段已完成：

- 统一净销售、退款率、转化率、客单价、费用率、ROI、老客占比等指标定义，并由 API 输出能力、筛选、缺失区间和来源批次。
- 页面按“可取得数据 → 可二次加工指标 → 页面能力”组织；推广下钻、生命周期编辑、导出和跨页上下文均受能力门控。
- 旧 `/api/legacy/actions` 写入口改为只读兼容，新动作统一归属 `product_actions`。
- 导航和弹窗按 `detail`、`edit`、`config`、`flow` 分类，flow 弹窗明确影响范围。

本阶段暂不纳入：利润、库存、用户 cohort、严格因果归因、完整市场机会分析。这些能力需要额外数据源或方法论验证，不能由现有销售、推广和生命周期数据直接推出。

验证日期：2026-08-14

## 已验证

- 商品接口支持生命周期、季节属性、待办筛选；分页总数复用相同过滤条件。
- 商品接口提供 `expense_ratio`、生命周期和待办派生字段，并对未知排序字段安全回退。
- 设置服务提供五个 GA 商品视图模板，并校验模板列白名单。
- 导入预览逐字段返回 `inferred_type` 与 `match_status`。
- 总览日度矩阵返回老客占比、逐日环比、缺失日期范围和 `source_batch_id`。
- 七个正式页面保留 `data-right-rail`，静态 UI 门禁通过。
- ECharts 与 Lucide 已本地化，正式页面不再依赖外部 CDN。
- 浏览器行为门禁通过：前进后退、筛选清理提示、模板刷新恢复和七种 availability 状态均已验证。
- Playwright 已覆盖 8 个正式路由的 1366x768、1920x1080、1024x768、390x844，共 32 个组合：HTTP 200、无页面/API 错误、无横向溢出，图表 Canvas 非空。
- 完整 `unittest` 回归 388 项通过；独立代码复核未发现遗留问题。
- 恢复演练以只读复制真实库完成；源库与副本 SHA-256 均为 `f48886ca89f6ee0675a43b2069120719ba19a26a284f184f2937988f5cb70d49`，迁移前后 integrity 均为 `ok`，40 张表完整。

## Phase 2 数据能力目录（2026-08-14）

- 新增只读 `/api/data-capabilities`，将代码中的业务语义与 SQLite 实时覆盖证据合并，统一展示数据域、粒度、日期范围、来源批次、原始字段、派生指标、消费页面和限制。
- Data Center 新增数据能力地图、状态筛选和详情弹窗；页面不再把空表、缺失字段或未接入来源展示为可用能力。
- 目录只用于设计和治理，不替代各业务 API 的请求级能力门控，也不提供公式或目录编辑。
- 本阶段不新增利润、库存、用户 cohort、严格因果归因或完整市场机会分析；这些边界持续显示其缺失前提。

## 验证命令

```powershell
py -3 -m unittest discover -s tests -v
Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }
node scripts/validate_ui_demos.cjs
node scripts/browser_prd_gates.cjs
py -3 scripts/production_preflight.py
py -3 scripts/production_preflight.py --recovery-source data/dashboard.db
node scripts/smoke_core_pages.cjs
```

## 剩余边界

- 当前定位是单店、本机或受信内网部署，不承诺公网多租户安全。
- 推广下钻只展示已导入粒度，不生成不存在的计划、单元或创意事实。
- `/legacy/` 继续保留历史能力兼容入口，但不属于七个一级页面主导航。

## 2026-08-14 PRD 收口补充

- `/api/industry_benchmark` 已迁移到统一 evidence envelope；无行业基准行或导入零值不会再被渲染成虚假 0，前台按 `availability` 显示数据状态。
- 能力注册表补充 `promotion.contribution_analysis=conditional`，并保持 `promotion.causal_attribution=unsupported`，严格归因不因相关字段存在而提前开放。
- 所有 dialog/drawer（含 refactor demo 导入流）均声明 `data-modal-kind`；浏览器门禁脚本对双工具箱触发器使用明确定位。
- 当前完整回归为 388 项；浏览器 PRD gates、32 视口 smoke、UI 静态校验和生产预检均通过。
- 页面能力注册项补齐 owner、目标文件、验收 selector、跳转参数和弹层影响范围；总览矩阵、目标进度、客户构成、漏斗和周期比较均纳入正式能力注册。
- 当前完整回归为 388 项；新增注册元数据和总览能力后浏览器 PRD gates、32 视口 smoke、UI 静态校验和生产预检仍通过。
