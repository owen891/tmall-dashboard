# 月复盘页 · XMind 能力矩阵（2026-10-03）

> **目的**：把 XMind《月复盘框架》的每个叶子节点映射到「页面位置 → 真实接口/字段 → 当前状态 → 缺口 → 优先级 → 验收条件」，
> 作为后续 P0/P1/P2 开发的验收基线。
>
> **证据来源**（均为本轮实测，非推断）：
> 1. XMind 节点树：`.tmp/xmind_month_review_topics.txt`（192 行，权威需求源）
> 2. 真实接口抽样：`GET /api/period-reviews/month/2026-09/context`（本地 5000 端口，availability=available）
> 3. 部分覆盖场景抽样：`GET /api/period-reviews/week/2026-10-W1/context`（coverage=partial 2/3 天）
> 4. 代码级核对：`api/period_reviews_api.py`、`services/period_context.py`(2150 行)、`services/period_templates.py`、
>    `frontend/ui_demo/assets/period-review-live.js`(3120 行) 及各 `pages/period-review/*.js`
>
> **仓库状态提示**：仓库当前有 **58 处未提交改动**（含 `period-review-live.js`、`gap-attribution.js`、`target-cards.js` 等本页文件）。
> 本文档为**新增文件**，未修改、未覆盖任何现有改动；开发时请先 stash/备份现有工作区。

---

## 修订说明（2026-10-03 第四轮，市场分级接入 + 两个静默 bug）

第一版把若干「可补采 / 前端未接」误判为「缺数据源、成本高」。第二轮**逐表核库**后更正。第三轮关闭 P0 全部（#3/#4）。第四轮接入市场分级并修掉两个静默 bug。

| # | 第一版判断 | 第二轮实测更正 | 证据 |
|---|---|---|---|
| 1 | 三渠道（全站/关键词/人群）**后端无明细、取不到** ❌ | **库里有数据，接口也能出**：`category_mode=all` 下 `ads.channel_totals.groups` 完整返回 4 组；**按品类过滤时被代码主动屏蔽**（`missing_inputs=['promotion_category_scope']`），非缺源 | §6.1 |
| 2 | 商品×渠道明细缺失 | **已具备**：`promotion_creative_daily`（28,337 行，`product_id` 命中 99.8%）含 关键词/人群 × 商品 × 日 × 花费/成交；`promotion_campaign_items`（4,306 行，命中 99.0%）含 计划×商品×渠道。缺的是**前端未接 + `period_context` 未 UNION 该表 + 覆盖自 2026-08-20 起** | §6.2 |
| 3 | 市场（趋势/蓝海/词根/竞店商品级）数据未接入 | **数据在库、且采集器每日在跑**：`sycm_market_item_rank` 9000 行 / `search_rank` 25500 行 / `rival_shop` 847 行，**均为 2026-09-16 起**；9 月全月复盘属「周期覆盖不足」而非「无源」 | §6.3 |
| 4 | 部分覆盖仍输出极端同比（P0 #1） | **已修复**：新增基线可比性判定，周/进行中月的月度兜底基线一律标「不可比」；**并发现同类的「进行中月」错配**（`month/2026-10` 同比 -98%）一并修掉 | §2、§7 |
| 5 | 对比值分母 0/过小 → 不可比（P0 #6） | **已修复并统一**：指标卡与 KPI 区都显式渲染「xx 不可比」，不再静默丢弃 | §7 |
| 6 | 商品级「全站推广」缺源、品类模式「推广计划拆解」为空 | **已关闭**：用 `promotion_campaign_items` 做**计划→商品归因**，只对「计划只绑 1 个商品」做**精确**归因（**不做均摊**）。2026-09 精确归因覆盖花费 **73.9%**，其中货品全站推广 **89.3%**；品类模式计划拆解不再为空 | §7.8 |
| 7 | 顶部无统一「数据状态」、利润未标「部分口径」（P0 #3/#4） | **已修复**：新增 `data_status` 汇总 6 类判据 → 顶部「灯 + 原因清单」折叠面板（`影响可信度` / `口径边界` 分组）；净利润卡与利润瀑布块加「部分口径」徽标。**`level`（覆盖完整性）与 `usable`（数字可用性）分离**，避免「永远是黄的」 | §7.9 |
| 8 | 市场「趋势/蓝海/词根」未接入、竞品商品级空表 | **已接入**：市场分级算法**早已投产**于市场排行页（`market_monitor_service`），月复盘此前只是**没复用** → 现已接入（8大归类 / 词根需求 / 趋势节点 / 趋势市场 / 蓝海市场 / 竞店爆品）。**并修掉一个静默 bug**：`aggregate()` 查了 `sycm_market_item_rank` 不存在的 `detail_url` 列、异常被 except 吞掉 → `competitor_items` 长期空表（**0 → 10 条**）。另修掉蓝海 `cover=0 → 高潜蓝海` 的误判（改记「待核」） | §7.10 |

> **口径结论**：XMind 缺口分三类，性质完全不同，开发策略也不同 ——
> ① **纯前端未接**（广告 7 类字段、三渠道展开、20 条）→ 低成本，先做；
> ② **后端未取但数据在库**（商品×渠道、渠道级三渠道按品类）→ 中成本，改 `period_context` 查询即可；
> ③ **真需补采**（2026-08-20 前的商品×渠道日粒度、2026-09-16 前的市场表）→ 用现成采集器回溯，见 §6.4。

---

## 0. 结论摘要

| 维度 | 判断 |
|---|---|
| 业务框架覆盖度 | **约 70%**：复盘骨架、目标完成情况、三因子拆因、货品/广告基础分析、市场承接、动作与导出均已在线 |
| 后端字段就绪度 | **高于页面呈现**：多个 XMind 必需字段后端**已返回**（加购率、单次付费访客成本、直接投产、加购成本、拉新成本），前端未完全露出 |
| 最大硬缺口 | ① 市场表**历史覆盖不足**（`sycm_market_*` 均自 2026-09-16 起）→ 需补采 ② 竞品男女款维度、市场价格/毛利/评价仍无源 ③ 利润恒等式根因（补采窗口 155 行费用列缺失，见 §7.9） |
| 已消除 | ~~覆盖不足仍输出极端同比且无保护~~ → **已修复**（周 + 进行中月双场景，见 §2、§7）；~~拆因无对账~~ → **已补「三因子贡献合计 / 变化额 / 未解释差额」对账**（见 §7.6）；~~广告三渠道/商品×渠道/推广渠道拆解无数据~~ → **已全部接入**（含修掉「渠道视图查错粒度恒空」的既有 bug，见 §7.7）；~~商品级「全站推广」缺源、品类模式「推广计划拆解」为空~~ → **已关闭**（计划→商品精确归因，不做均摊，见 §7.8）；~~顶部无统一数据状态、利润未标部分口径~~ → **已修复**（P0 #3/#4，见 §7.9）；~~市场趋势/蓝海/词根未接入、竞品商品级空表~~ → **已接入**（复用已投产分级算法；并修掉 `detail_url` 不存在导致的静默空表，见 §7.10） |
| 最优先动作 | ① **补采 2026-08-20 前的商品×渠道 / 2026-09-16 前的市场**（用现成采集器回溯）② **补采利润窗口 155 行费用列**（让顶部状态灯转绿）③ 竞品男女款维度 |

**关键纠偏**：原方案文档列出的文件路径中，`assets/period-review/metric-cards.js` 路径有误（实际在 `assets/pages/period-review/`）；
且**未提及真正的重逻辑文件 `services/period_context.py`（2150 行）**——所有 `context` 字段都在此组装，改字段必须从这里入手。

---

## 1. 主能力矩阵

状态图例：✅ 已满足 ｜ 🟡 部分满足 ｜ ❌ 缺口 ｜ ⚪ 未接入

### 1.1 本月复盘 › 品类汇总

| XMind 节点 | 页面位置 | 真实接口/字段 | 状态 | 缺口 | 优先级 | 验收条件 |
|---|---|---|---|---|---|---|
| 销售指标 · 月维度（表格对比） | 品类汇总段证据「本期核心指标」+「目标 vs 实际」表 | `metrics.items[]`（13 项：gsv / net_sales / visitors / conversion / buyers / aov / ad_spend / ad_ratio / roi / refund_amount / refund_ratio / cart_rate / paid_cpc）；`target_path.targets[]` | ✅ | 表格化对比已在目标表；13 项指标以卡片网格呈现，非表格 | P2 | 品类汇总段可直接看到 13 项指标含环比/同比，且支持表格对比 |
| 销售指标 · 周维度（**增加加购率、单次付费访客成本**） | 品类汇总段证据「月内分周指标」（`breakdown` material） | `breakdown.rows[].metrics` = { gsv, net_sales, visitors, conversion, aov, ad_ratio, ad_spend, roi, **cart_rate**, **paid_cpc**, profit } | ✅ **已补齐** | 无（周维度含加购率与单次付费访客成本） | 已完成 | 月内分周表列含「加购率」「单次付费访客成本」 |
| 利润指标 · 月维度 | 驾驶舱「净利润」卡 + 货品汇总利润瀑布 | `metrics.current.profit`、`target_path.targets[key=profit]`、`profit_structure.rows[]`（6 行：sales_cost / custom_cost / product_cost / logistics_cost / other_cost / operating_profit） | ✅ | `profit` **未进 `metrics.items` 头部 13 项**，不进 KPI 网格 | P2 | 净利润出现在核心指标区（不只在卡） |
| 利润指标 · 周维度 | 月内分周指标表 | `breakdown.rows[].metrics.profit` | ✅ | 无 | 已完成 | 分周表含利润列 |
| 完成情况分析 · 三大指标 | 驾驶舱 4 张指标卡（`metric-cards.js`） | `target_path.targets`：net_sales / profit / ad_spend / net_expense_ratio | 🟡 | XMind 要 **GSV 完成率**，卡用的是 **net_sales**（无 `target_gsv` 目标行）；卡名「账单花费」≠ 输入名「推广费目标」 | P1 | 三大指标口径与 XMind 对齐（或明确标注用净销售额替代） |
| 完成情况分析 · 基础数据（访客/转化/客单/加购率） | KPI 网格（`renderKpiGrid`） | `metrics.items`：visitors / conversion / aov / cart_rate | ✅ | 无 | — | 四项均在核心指标区 |
| 完成情况分析 · 付费（单次付费访客成本） | KPI 网格 | `metrics.items.paid_cpc`（source=`promotion_clicks`） | ✅ | `paid_cpc.yoy_value` 为 null（同比缺失） | P2 | 单次付费访客成本含环比；同比缺失时显式标「不可比」 |
| 根因（访客↓→推广费↓→单次付费成本↑→头部链接…） | 品类汇总段证据「目标差距归因」（`gap-attribution.js`）+「流量来源拆解」 | `gap_attribution`、`dimensions.traffic`（4 items：search 等，含 share_of_visitors / change_rate） | 🟡 | 拆因仅「流量 × 转化 × 净销售客单」三因子；**无各因素贡献之和与总变化对账**；XMind 根因树涉及的「推广花费/调价/头部链接/费比/其他费用」未结构化 | P1 | 各因素贡献之和可与总变化对账，未解释差额显式显示 |
| 下一步规划（提升费比/产品分层/调整付费渠道） | `next_plan` 段三段式 + 待执行动作 | `actions_planned`（当前为空） | 🟡 | 结构化动作可创建，但「产品分层（引流/利润/动销款）」无字段承载 | P2 | 规划可转成带负责人/截止/验收的动作 |

### 1.2 本月复盘 › 货品

| XMind 节点 | 页面位置 | 真实接口/字段 | 状态 | 缺口 | 优先级 | 验收条件 |
|---|---|---|---|---|---|---|
| 汇总 | 货品段「货品汇总」面板 | `products.summary`：category_structure（5 类目 net_sales/share）、listed_count(1131)、new_sold_count(64)、segment_stats、sell_through_rate、sold_count；`profit_structure` | ✅ | 无 | — | 汇总含类目结构占比与售罄率 |
| 品类 · 男款 / 女款 | 类目结构（按 `category`：中筒袜/长筒袜/短袜/船袜/连裤袜） | `products.summary.category_structure[].category`；各商品行含 `category` | 🟡 | **无男女款分组**（需「适用人群」维度）；矩阵地图（产品分层四象限）在货品矩阵页，未接入复盘 | P1/P2 | 可按男女款分组；矩阵地图结论可引用到复盘 |
| top单品 · 净销售 TOP10（GSV/退款率/净利润/推广费/费比/访客/转化/件数/客单） | 货品段「净销售额 TOP10」（`product-columns.js`） | `products.top[]`：gsv、refund_rate、**operating_profit**（净利润）、ad_spend、ad_ratio、visitors、conversion、payment_qty、aov、net_sales、share_of_gsv、gross_profit、anomaly_tags、system_facts | ✅ | XMind 列全部有对应字段 | — | TOP10 表列与 XMind 字段一一对应 |
| 付费单品 TOP10 / 盈利 TOP / 亏损 TOP | 货品段「其他货品榜」折叠区 | `products.paid` / `products.profit` / `products.loss` | ✅ | XMind 要求「**每个榜单字段不同**」——需确认 `product-columns.js` 是否按榜定制列（当前疑似共用列集） | P1 | 各榜按定义展示专属列，非一套列打天下 |
| 下滑商品 TOP10 | 货品段「下滑商品 TOP10」 | `products.decline[]`（含 change_rate / delta / prev_*） | ✅ | 无 | — | — |
| 点击字段指标 → 周维度折线预览 | 榜单行内趋势弹窗 | `GET /api/period-reviews/product-trend/<product_id>?grain=week` | ✅ | 无 | — | 点指标出周维度折线 |
| 问题单品分析 | 货品段「问题商品」面板（`problemItemsPanel`） | `products.problem_items[]`（19 条；含 anomaly_tags / system_facts / unknowns） | ✅ | 无（XMind 此处仅写「细分主题 1」） | — | 问题清单含异常标签与系统事实 |
| 新品 · 定义（最近 60 天） | 货品段「新品 · 净销售额 TOP10」 | `products.new[]`（最近 60 天上架） | ✅ | 无 | — | 新品口径 = 60 天 |
| 新品 · 净销售 TOP / 付费 TOP10 | 货品段「新品 · 付费 TOP10」 | `products.new` / `products.new_paid` | ✅ | 无 | — | 两榜均在 |
| 总结 · 分析/根因/下一步规划 | 货品段三段式（`analysis/root_cause/next_step`） | `sections.goods.subsections`（`period_templates.py` v3） | ✅ | 无 | — | 三段可写可存 |

### 1.3 本月复盘 › 广告

| XMind 节点 | 页面位置 | 真实接口/字段 | 状态 | 缺口 | 优先级 | 验收条件 |
|---|---|---|---|---|---|---|
| 汇总 · **增加直接 ROI 字段** | 广告段「推广效率」（`renderAds`） | `ads.direct_roi`(本期 1.54) / `ads.prev_direct_roi`(上期 0.51)、`ads.delta.direct_roi_delta` | ✅ | 无 | — | 汇总同时展示总投产与直接投产 |
| 汇总 · **推广成交金额增加三渠道金额（全站/关键词/人群）** | 广告段「推广成交金额 · 渠道拆分」 | `ads.channel_totals.groups`：**全店口径**（`category_mode=all`）返回 4 组完整数据 + 成交占比（全站 35.7万/165.8万/ROI4.65/**84.9%**；关键词 13.4万/25.6万/1.90/13.1%；人群 1.5万/3.5万/2.28/1.8%；其他 0.2万/0.5万/2.52/0.26%）；**按品类口径**改从商品×渠道明细聚合，返回 关键词/人群（`partial=True`、`missing_inputs=['promotion_channel_all_site_scope']`、**不给成交占比**） | ✅ **已接入** | 按品类缺 全站推广（无商品级明细）→ 已显式标注「成交占比不适用」，不伪造 0 | 已完成 | 广告汇总显示 全站/关键词/人群 三渠道成交金额；口径边界有说明 |
| 单品 · TOP20 消耗商品 · 花费 | 广告段「广告单品 TOP20 消耗」表格 | `promotion_items.items[].totals.ad_spend` | ✅ | **已改为表格展示 20 条**（原摘要只渲染 10 条） | 已完成 | 展示满 20 条 |
| 单品 · 费比 | 同上 | `totals.ad_ratio` | ✅ | **已补列** | 已完成 | 表内含费比列 |
| 单品 · 总投产 | 同上 | `totals.roi` + 渠道子表 `channels[].roi` | ✅ | **可按渠道展开**（关键词/人群） | 已完成 | 总投产可展开三渠道 |
| 单品 · 直接投产 | 同上 | `totals.direct_roi` + `channels[].direct_roi` | ✅ | **可按渠道展开** | 已完成 | 直接投产可展开三渠道 |
| 单品 · 加购成本 | 同上 | `totals.cart_cost` | ✅ | **已补列** | 已完成 | 表内含加购成本列 |
| 单品 · 拉新成本（=花费/成交新客） | 同上 | `totals.new_cost`（公式已按 花费/成交新客） | ✅ | **已补列 + 可按渠道展开** | 已完成 | 拉新成本可展开三渠道 |
| 单品 · 加购率 | 同上 | `totals.cart_rate` | ✅ | **已补列** | 已完成 | 表内含加购率列 |
| 单品 · **商品×渠道明细** | 同上「渠道展开行」 | `promotion_items.items[].channels` **已有数据**（三选一装配）：`{人群: {花费,成交,费比,总投产,直接投产,加购成本,拉新成本,加购率}, **全站**: {...}, 关键词: {...}}`；逐组 `channel_sources` 标明来源（`creative` / `campaign_exact` / `product_grain`）；块级 `channels_partial` / `channels_note` 标注部分口径 | ✅ **已接入（含全站）** | 全站推广只覆盖「计划只绑 1 个商品」的计划（占全站花费 89.3%），多商品计划无商品级明细 → 渠道之和 ≠ 商品合计（已显式标注） | 已完成 | 单品行可展开渠道明细（花费/成交/投产/加购/拉新），并标明每组来源 |
| 计划 · **推广计划拆解（计划 → 商品归因）** | 广告段「推广计划拆解（计划 → 商品归因）」新块 | `campaign_attribution.items[]`：计划/渠道/花费/归因成交/ROI/商品数/**归因方式（精确\|多商品）**/归因商品；`exact_share` + `attribution_note`；`dimensions.promotion.campaigns` 品类模式已可用 | ✅ **已接入** | 多商品计划（占 2026-09 花费 26.1%）只在计划级展示，**不摊**；映射表是当前快照，仅 2026-08-20 后有效 | 已完成 | 计划级花费/成交可见，且标明哪些是精确归因、哪些是多商品不拆分 |
| 总结 · 分析/根因/下一步规划 | 广告段三段式 | `sections.ads.subsections` | ✅ | 无 | — | 三段可写可存 |

> **广告段核心结论（第四轮：已全部接入）**：XMind 广告段要求已**全部满足** —— 7 类字段 × 20 条、渠道展开行（含成交金额）、渠道级三渠道成交金额（含按品类口径）、推广渠道拆解、**计划→商品归因**。
> 三渠道数据来源：**渠道级** = `promotion_daily_facts` 的 `grain='campaign'` 行（按渠道分组）；**商品级** = `promotion_creative_daily`（`product_id` 命中 99.8%）+ **计划 1:1 精确归因**（补全站推广，见 §7.8）。
> 剩余：**(a) 多商品计划无法拆到商品（占 26.1% 花费，不摊以免造数）**、**(b) 映射表为快照、仅 2026-08-20 后有效**、**(c) 更早周期需回溯补采**。

### 1.4 市场监控

| XMind 节点 | 页面位置 | 真实接口/字段 | 状态 | 缺口 | 优先级 | 验收条件 |
|---|---|---|---|---|---|---|
| 行业 · 商品排行（趋势市场 / 蓝海市场） | 市场段「市场事实：商品榜监控」+「**商品排行 · 趋势市场**」+「**蓝海市场 · 低供给词根**」 | `market.market_signals[]`（category / avg_uv / avg_pay_buyer_count）；`market.categories[]`（trend_up/down/new、concentration_top10）；**`market.trend_items`**（窗口首尾排名对比：上升/新进榜 TOP，296/226 个）；**`market.blue_ocean_supply`**（词根级每万覆盖分级）；底表 `sycm_market_item_rank` 9000 行 | ✅ | 已接入（见 §7.10）；`avg_uv_change_rate` 为 null（对比期落在 2026-09-16 前 → 覆盖不足，可补采） | — | 有趋势/蓝海分级；变化率缺失时显式标不可比 |
| 行业 · 关键词排行（8 大归类 / 词根需求分析 / 趋势节点分析） | 市场段「**关键词洞察 · 8 大归类**」+「**趋势节点分析**」+「**蓝海市场 · 低供给词根**」 | **`market.keyword_insights`**（`categories[]` 8 大归类含词数/热度占比/TOP词根；`trend_nodes.rising/cooling` 带归类标注；`blue_ocean[]` 近似口径）；底表 `sycm_market_search_rank` 25500 行 | ✅ | 已接入（**复用市场排行页已投产算法**，见 §7.10）；`search_heat_change_rate` 为 null（同覆盖不足） | — | 关键词含词根归类与趋势节点 |
| 行业 · 总结 | 市场段三段式 | `sections.market.subsections` | 🟡 | 市场段 `required=false`，可空 | P2 | 结论可引用到品类策略与下期计划 |
| 竞店（蕉内/有棵树/SW/棉竹屋/棉芝士/妮轻/竹久）· 整体数据 | 市场段「竞店动态」 | `market.rivals[]`（shop_name / uv / pay_buyer_count / pay_rate / daily_trend / status）；底表 `sycm_market_rival_shop` 847 行 | ✅ | 无（整体数据齐；变化率受覆盖起点限制） | — | 竞店整体可对比 |
| 竞店 · 爆品排名变化 / 趋势品 | 市场段「**竞店爆品排名变化**」 | **`market.rival_moves`**（每店 上升/下降/新进榜/退出 计数 + 变动最大 TOP；`shop_count=601` 家，展示前 15） | ✅ | 已接入（见 §7.10）；「趋势品」以 `trend_items`（全市场商品级）承接 | — | 可看竞店爆品排名变化与趋势品 |
| 竞品 · 男款 / 女款 / 总结 | 市场段「竞品商品对标」 | **`market.competitor_items` 从 `[]` → 10 条**（含 `market_rank` / `market_shop` / `market_title`） | ✅ | **修掉一个静默 bug**（SQL 查了 `sycm_market_item_rank` 不存在的 `detail_url` 列，异常被 except 吞掉 → 长期空表，见 §7.10）；男女款维度仍缺 | — | 有竞品数据时按男女款对标 |
| 数据状态透明 | 市场段「数据状态」块 | `market.missing_inputs` = [market_margin, market_price, market_reviews, sycm_market_item_rank, …]；`run_alignment=partial`；`run.source=店透视市场排行`、`analysis_date=2026-09-27` | ✅ | 无（已显式提示待验证项） | — | 每条市场结论标来源与采集时间 |

### 1.5 下月规划

| XMind 节点 | 页面位置 | 真实接口/字段 | 状态 | 缺口 | 优先级 | 验收条件 |
|---|---|---|---|---|---|---|
| 目标规划 · 目标 / 基于目标怎么达成 | `next_plan` 段三段式（目标 / 达成路径 / 任务排期） | `sections.next_plan.subsections`（`period_templates.py` plan 定义）+ `target_path` | ✅ | 无 | — | 目标可验收 |
| 复盘规划 · 复盘分析规划汇总 | `next_plan` 段「周复盘汇入」 | `linked_summaries`（kind=weekly，当前空，带 missing_hint「本月还没有已保存的周复盘」） | 🟡 | 机制已建、本月无周复盘数据可汇入 | P2 | 周复盘写完后自动汇入月复盘 |
| 任务时间节点排期 | `next_plan` 段「任务排期」+ 排期时间轴 | `actions_planned`（当前为空） | ✅ | 无（有动作时渲染时间轴） | — | 动作含负责人/截止/验收 |

---

## 2. P0 数据可信度问题 · 实测复现

原方案称「曾出现环比 -2870%、同比 -9800%、目标净费比单位异常、覆盖 2/3 天仍输出确定性判断」。本轮逐项实测：

| # | 问题 | 实测结果 | 判定 |
|---|---|---|---|
| 1 | **覆盖不足仍输出极端同比** | `week/2026-10-W1`：`coverage={expected_days:3, missing_days:1, observed_days:2, status:"partial"}`，同比曾直接给出 **gsv -98.0% / net_sales -98.0% / visitors -96.2% / buyers -97.9% / ad_spend -92.9%**（`yoy_value` 206 万，明显窗口不对齐）。**第二轮追加发现同类错配：`month/2026-10`（进行中，仅过 3 天）同比 gsv 也是 -98%**（基线回退 2025-10 整月 206.7 万） | ✅ **已修复**（见 §7） |
| 2 | 目标净费比单位异常（2370%） | `target_path.targets[net_expense_ratio]` 实测 `format=percent, target=0.237`（=23.7%，数据正确）；前端 `target-cards.js` / `metric-cards.js` 均已加 `isSuspiciousRatioTarget`（target>1 → 显示「疑似单位异常 / 待核查」），且输入按 ÷100 换算 | ✅ **已缓解**（仅展示层兜底，历史脏值未迁移） |
| 3 | 数据覆盖/更新时间/口径提示 | **已修复**：后端新增 `data_status`（`_data_status()` 汇总 6 类判据），驾驶舱顶部渲染统一 `.pr-data-status` 折叠面板（灯 + `影响可信度`/`口径边界` 两组清单 + 数据区间/进行中天数）；**`level`（覆盖完整性）与 `usable`（数字可用性）分离**，避免「永远是黄的」 | ✅ **已修复**（见 §7.9） |
| 4 | 费用/成本缺失 → 利润标「部分口径」 | **已修复**：净利润指标卡 + 「利润结构（利润瀑布）」块标题各加 `部分口径` 徽标（`.pr-caliber-badge.is-warning`），hint 明写未回填行数与恒等残差。实测四种口径下利润恒等式**均不平衡** → 该标不是「锦上添花」而是「本该有」 | ✅ **已修复**（见 §7.9） |
| 5 | 拆因贡献之和与总变化对账 | **已补对账**：`gap-attribution.js` 三因子表下新增「三因子贡献合计 / 净销售额变化额（对账）/ 未解释差额」三行；差额显著（>0.5% 或 >0.5 元）时高亮并提示「口径差异、结论降级使用」。实测 `month/2026-09`：合计 -¥16,039.35 = 变化额 -¥16,039.35，差额 0（已对齐） | ✅ **已修复**（见 §7） |
| 6 | 对比值分母为 0/过小 → 显示「不可比」 | **已统一**：`metric-cards.js` 与 `period-review-live.js` 对 `comparability.comparable===false` 均显式渲染「环比/同比 不可比」（弱化样式 `.pr-delta--na`），不再静默丢弃或输出极端百分比；分母为 0/null 仍走「对比周期无数据」 | ✅ **已修复**（见 §7） |

> **P0 现状**：#1–#6 **全部已修复**。#3（顶部统一数据状态）、#4（利润「部分口径」）已于第三轮落地（见 §7.9）。剩余工作重心转向 §6 的补采与市场分级算法。

---

## 3. 后端字段清单（实测快照，供开发对照）

`GET /api/period-reviews/month/2026-09/context` → `data.context` 顶层键：

```
actions_blocked  actions_done  actions_planned  actions_review  actions_to_verify
ads  alerts  anomalies  breakdown  category  compare  compare_options  dimensions
linked_summaries  market  metrics  missing_inputs  period  products
profit_structure  promotion_items  target_path
```

| 块 | 关键字段（实测） |
|---|---|
| `metrics` | `coverage{expected_days,observed_days,missing_days,status}`；`current`/`prev`/`yoy` 各 21 个标量（gsv, net_sales, visitors, conversion, buyers, aov, ad_spend, ad_ratio, roi, refund_amount, refund_ratio, **cart_rate**, **paid_cpc**, profit, net_expense_ratio, fav_rate, bounce_rate, …）；`items[]` 13 项（**不含 profit**） |
| `target_path` | `targets[]` 4 行：net_sales / profit / ad_spend / net_expense_ratio（含 target, actual, gap, achieved_rate, rate_better, reverse_rate, format, target_source） |
| `breakdown` | `grain="week"`，`rows[]` 5 行（W1…W5），每行 `metrics` 含 gsv/net_sales/visitors/conversion/aov/ad_ratio/ad_spend/roi/**cart_rate**/**paid_cpc**/profit |
| `products` | `top`/`decline`/`paid`/`profit`/`loss`/`new`/`new_paid` 各 10 条，`problem_items` 19 条，`summary`（category_structure/listed_count/new_sold_count/segment_stats/sell_through_rate/sold_count）。行内含 `gross_profit`、`operating_profit`、`profit_rate`、`refund_rate`、`share_of_gsv`、`anomaly_tags`、`system_facts`、`unknowns` |
| `promotion_items` | `items[]` 20 条，`totals` = {ad_spend, ad_ratio, roi, direct_roi, cart_cost, new_cost, cart_rate, attributed_payment, direct_payment, cart_adds, clicks, new_buyers}；**`channels` = {}**；`channel_groups` = [全站, 关键词, 人群, 其他]；`missing_inputs` = [promotion_product_channel_scope] |
| `ads` | `current{ad_ratio,ad_spend,roi}`、`prev`、`delta{ad_ratio_delta_pt,ad_spend_change,roi_delta,direct_roi_delta}`、**`direct_roi`**、`prev_direct_roi`、`channel_totals{groups:[], missing_inputs:[promotion_category_scope], source, sample_days}` |
| `market` | `market_signals`(5)、`keyword_signals`(20)、`rivals`(10)、`categories`(3)、**`competitor_items`([])**、**`decision_hints`([])**、`run{source:店透视市场排行, analysis_date:2026-09-27}`、`run_alignment="partial"`、`missing_inputs`(6) |
| `profit_structure` | `rows[]` 6 行（sales_cost/custom_cost/product_cost/logistics_cost/other_cost/operating_profit）、`identity{ok,gap,note}`、`caliber{formula,custom_cost_note}`、`net_sales`、`row_count` |
| `dimensions` | `traffic{items(4), totals, sample_days, period_days, missing_inputs}`；`promotion{channels{available:false,items:[]}, campaigns{available:false,items:[]}}` |
| `linked_summaries` | `kind="weekly"`、`items`([])、`missing_hint` |

---

## 4. 原方案文件路径勘误

| 原方案写的路径 | 实际路径 | 说明 |
|---|---|---|
| `frontend/ui_demo/assets/period-review/metric-cards.js` | `frontend/ui_demo/assets/**pages**/period-review/metric-cards.js` | ❌ 路径错误，少一层 `pages/` |
| `services/period_review_service.py` | 存在（仅 61 行，薄封装） | ⚠️ **真正的重逻辑在 `services/period_context.py`（2150 行）**，原方案未列 |
| — | `services/period_templates.py`（183 行） | ⚠️ 六段模板定义在此，改段落结构必改此文件，原方案未列 |
| `api/period_reviews_api.py` / `period-review-live.js` / `pages/period-review.html` / `gap-attribution.js` / `target-cards.js` | 一致 | ✅ |

---

## 5. 建议实施顺序（对齐原方案 5 阶段）

| 阶段 | 范围 | 本矩阵对应缺口 | 验收 |
|---|---|---|---|
| **阶段 1 · 可信度治理** | 部分覆盖降级、极端同比拦截、拆因对账、覆盖率顶部统一展示 | §2 的 #1、#3、#5 | 0/空/负/小分母/部分覆盖均不产生误导性百分比或强因果 |
| **阶段 2 · 广告字段与分渠道** | 前端补 7 类字段 + 20 条；后端补商品×渠道明细 | §1.3 全部 🟡/❌ | TOP20 表字段与 XMind 一一对应；三渠道有数据时可展开 |
| **阶段 3 · 货品与榜单细化** | 分榜定制列、男女款分组、GSV 完成率口径对齐 | §1.1（三大指标）、§1.2（榜单列/男女款） | 每榜字段按定义；口径与 XMind 一致 |
| **阶段 4 · 市场与竞店闭环** | 趋势/蓝海分级、词根归类、趋势节点、竞店商品级、竞品男女款 | §1.4 全部 🟡/❌/⚪ | 每条市场洞察有来源、更新时间、可追踪动作 |
| **阶段 5 · 连续复盘与自动化** | 周复盘自动汇入月复盘、跨周期动作追踪、候选动作推荐 | §1.5 linked_summaries、动作闭环 | 提示与候选由人确认，不自动认定根因 |

> **开发前置约束**：仓库现有 58 处未提交改动，开工前先保护工作区（stash / 分支 / 备份），避免覆盖。

---

## 6. 补采可行性与数据源清单（回应「缺的数据可以补采」）

结论：**XMind 里被判为「缺口」的项，绝大多数是「数据在库但没接」或「可用现成采集器回溯」，真正的「无源」只有 1 项**（万相台已停用的 v3 粒度，且已有 v4 替代）。

### 6.1 三渠道（渠道级）——数据在库，按品类时被代码屏蔽

| 项 | 实测 |
|---|---|
| 表 | `promotion_daily_facts`，`grain='channel'`（渠道级汇总） |
| 规模 | 54,916 行 / 2,907 商品 / 7 个 channel 值：全部(43,958)、关键词推广(4,899)、货品全站推广(4,882)、全站推广(749)、人群推广(360)、店铺直达(49)、超级短视频(19) |
| 接口表现 | 全店口径走 `grain='campaign'`（自带渠道名）→ 4 组完整；**按品类口径**改从 `promotion_creative_daily` JOIN products 聚合 → 关键词/人群 两组 + `partial=True` |
| 判定 | **已接入**（见 §7.7）；按品类缺 全站推广 → 显式标注「成交占比不适用」而非补 0 |

### 6.2 商品×渠道——数据已具备，后端未取

| 表 | 行数 | 覆盖 | 渠道 | `product_id` 命中 `products` |
|---|---|---|---|---|
| `promotion_creative_daily` | 28,337 | 2026-08-20 ~ 2026-10-02（43 天） | 关键词推广(26,960)、人群推广(1,333)、店铺直达(44) | **99.8%**（28,293/28,337） |
| `promotion_campaign_items` | 4,306 | — | 关键词推广(3,142)、货品全站推广(972)、人群推广(149)、超级短视频(41)、店铺直达(2) | **99.0%**（4,263/4,306） |
| `promotion_creative_daily` 2026-09 聚合示例 | — | 2026-09 全月 | 关键词推广 565 商品/花费 11.6万/成交 22.7万；人群推广 103 商品/1.5万/3.5万 | — |

- **已落地（§7.7）**：`period_context._promotion_items_block` 已 UNION `promotion_creative_daily`（按 `product_id` + `date` + `channel`），产出 `promotion_items.items[].channels`；`_ads_channel_totals` 按品类时也改走该表
- **仍需补采**：2026-08-20 之前的历史（v4 采集器支持 `--start/--end` 回溯）
- **口径注意**：全站推广在商品级需从 campaign 报表补（creative 表不含）；渠道名有「全站推广」vs「货品全站推广」两种写法，需归一

### 6.3 市场数据——在库且在采，只是起点晚

| 表 | 行数 | `stat_date` 覆盖 |
|---|---|---|
| `sycm_market_item_rank` | 9,000 | 2026-09-16 ~ 2026-10-02 |
| `sycm_market_search_rank` | 25,500 | 2026-09-16 ~ 2026-10-02 |
| `sycm_market_rival_shop` | 847 | 2026-09-16 ~ 2026-10-02 |

- 9 月全月复盘的市场同比/变化率取不到，是因为**对比期落在 2026-09-16 之前**（覆盖不足），不是没有数据源
- 采集器 `sycm_market` 每日在跑（`collector_runs` 最近成功 2026-10-03 04:05）
- 另一个禁用源：`dts_market`（店透视-市场榜单）当前 disabled

### 6.4 采集器现状（决定「能不能补采」）

`collector_runs` 最近一次全量（2026-10-03 04:00 前后）：`bi_daily` ✅、`sycm_item_flow` ✅、`sycm_market` ✅、`sycm_flow` ✅、`wanxiangtai` ✅（`dts_market` 禁用）。

`E:/www/BI采集/collectors/` 可用脚本：

| 脚本 | 用途 | 补采能力 |
|---|---|---|
| `collect_wanxiangtai_dims_v4.py` | 万相台维度报表（campaign / item_promotion / creative） | **支持 `--start/--end` 回溯**；POST 到 `/api/wanxiangtai/import`，由 `wanxiangtai_service` 统一映射粒度/渠道（`item_promotion→grain=product`、`campaign→grain=campaign` + 计划×商品映射） |
| `collect_wanxiangtai_dims_v3.py.disabled` | 旧版 | ⛔ 2026-09-19 停用：把 `campaignId/creativeId` 写进 `product_id`、加购写 `paid_detail`、`scene` 缺失默认「全站推广」，且 DELETE 有 AND/OR 优先级 bug |
| `collect_sycm_market.py` / `collect_sycm_flow.py` / `collect_sycm_item_flow_v6.py` | 生意参谋市场/流量/商品流量 | 按日期窗口采集 |
| `collect_overview_daily.py` / `collect_overview_full.py` / `backfill_overview_history.py` | 概览日度 | 含历史回填 |

> **补采可行性结论**：**「缺的数据可以补采」成立**。真正无解的只有「万相台 v3 口径的旧数据」（已被 v4 取代，且 v3 数据本身是脏的，不该回填）。
> 其余缺口均可通过 ①改查询接入在库数据 ②用 v4/生意参谋采集器回溯 解决。

---

## 7. 本轮已完成的改动（2026-10-03）

### 7.1 后端 · 基线可比性治理（`services/period_context.py`）

- 新增 `_baseline_grain_comparable(baseline_grain, current_full_month)`：**月度兜底基线（`data_grain='monthly'`）只有当前周期本身是完整月时才可比**
- `_comparability(...)` / `_metric_items(...)` 增加 `current_full_month` 参数；`build_context` 计算 `current_full_month = (period_type == 'month' and not period['is_ongoing'])`
- 基线不可比时不输出 `mom_change`/`yoy_change`，改输出 `mom_unavailable`/`yoy_unavailable = 'baseline_grain_mismatch'`，并带 `mom_comparable`/`yoy_comparable`
- `metrics.comparability = {mom: {...}, yoy: {...}}` 供前端消费

**判据为何从「周期类型」改为「是否完整月」**：第一版写成 `period_type in ('week','day')`，只挡了周/日，**漏掉「进行中的月」**——实测 `month/2026-10`（仅过 3 天）同比 gsv 也是 -98%（基线回退 2025-10 整月 206.7 万）。而**已完结的月**（`month/2026-09`，30 天）即便基线走月表兜底，双方都是整月，量纲一致，必须保留正常对比（实测 yoy gsv -19.3% 正确保留）。

### 7.2 后端 · 推广 bug 修复（`_promotion_items_block`）

- `has_channel_data` 原在**商品循环内被反复重置**（真 bug）→ 提到循环外初始化 + 跨商品累积
- 渠道聚合只查 `grain='product'`（`campaign_month`/`unit_month` 的 `product_id` 命中率 **0%**，是 campaignId 混写，已停用），并注释说明原因
- 新增 `merge_rows` 合并同组多渠道

### 7.3 前端 · 不可比展示统一

| 文件 | 改动 |
|---|---|
| `assets/pages/period-review/metric-cards.js` | `changeNode` 在 `comparable===false` 时显式渲染「环比/同比 不可比」（不再静默丢弃）；清理已成死分支的 `fallbackText` 判断 |
| `assets/period-review-live.js` | `deltaNode` 的不可比节点加 `pr-delta--na` 弱化类；`materialFor('promotion_items')` 由 ul 摘要改为**表格 20 条 × 7 字段**（花费/费比/总投产/直接投产/加购成本/拉新成本/加购率）+ 渠道展开行 |
| `assets/period-review.css` | 新增 `.pr-delta--na`（弱化）、`.pr-promo-item__channels.is-collapsed`、`.pr-table-wrap` |
| `pages/period-review.html` | 资源版本号 bump；抽屉补 `data-modal-kind="detail"`（修既有失败测试） |

### 7.4 验收证据（浏览器实测，CDP 9223）

| 场景 | 环比 | 同比 | 结论 |
|---|---|---|---|
| 周 `2026-10-W1`（进行中 4 天） | -28.7% | **不可比** | ✅ |
| 月 `2026-10`（进行中 3 天） | -31.4% | **不可比**（修复前 **-98%**） | ✅ |
| 月 `2026-09`（已完结 30 天） | +7.4% | **-16.4%**（正常保留） | ✅ |

后端复验：`week/2026-10-W1`、`month/2026-10` 的 `yoy.comparable=false / reason=baseline_grain_mismatch`；`month/2026-09` 的 `mom/yoy` 均 `comparable=true`。
`tests/test_period_reviews_api.py` + `test_category_analysis_api.py` + `test_category_mode.py`：**80 passed, 11 subtests passed**。

### 7.5 遗留与下一步

| 项 | 状态 | 下一步 |
|---|---|---|
| 拆因「贡献之和 = 总变化」对账（P0 #5） | ✅ 已完成（见 §7.6） | — |
| 商品×渠道接入（后端 UNION `promotion_creative_daily`） | ✅ 已完成（见 §7.7） | 补 商品级全站推广 |
| 渠道级三渠道按品类打通 | ✅ 已完成（见 §7.7） | — |
| 推广渠道拆解「查错粒度恒空」既有 bug | ✅ 已修（见 §7.7 改动 3） | — |
| 品类模式下「推广计划拆解」仍空 | 🟡 未做 | 用 `promotion_campaign_items` 做计划→商品归因 |
| 2026-08-20 前 / 2026-09-16 前的历史 | 🟡 需补采 | 用 `collect_wanxiangtai_dims_v4.py --start/--end` 等回溯 |
| 顶部统一「数据状态」标识（P0 #3）、利润「部分口径」（P0 #4） | ✅ 已完成（见 §7.9） | — |
| 利润恒等式不平（P0 #4 徽标背后的根因） | 🟡 需补采 | 补采窗口「利润未回填」155 行费用列（`all/2026-09` 缺 155 行，残差 68.3 万） |
| 市场趋势/蓝海/词根/竞店爆品/竞品商品级 | ✅ 已完成（见 §7.10） | — |
| 市场表历史覆盖（2026-09-16 前） | 🟡 需补采 | `sycm_market_*` 四表均自 2026-09-16 起；更早周期需采集器回溯 |
| 竞品「男款 / 女款」维度 | 🟡 未做 | `sycm_market_item_rank` 无性别字段，需从 title 解析或换源 |
| 深链能力弱：`?period_key=` 对月周期不生效（被覆盖为当前月）；品类模式**不走 URL**、只认 `localStorage` + 下拉 | 🟡 观察项 | 与本轮无关，单独排查 |

### 7.6 拆因对账（P0 #5，已完成）

**改动**：`assets/pages/period-review/gap-attribution.js` 的三因子表新增 3 行 —— 「三因子贡献合计」「净销售额变化额（对账）」「未解释差额」。

**为什么必须显式对账**：连环替代法在「净销售额 = 访客 × 转化率 × 客单价」严格成立时，贡献之和**恒等于**变化额。所以原注释「加总恒等于变化额」在多数情况下为真，但它是**推导结论而非数据事实** —— 一旦 `conversion` 与 `buyers/visitors` 不同源、或买家数缺失走回退，差额就会非 0。把差额摆出来，才能让「不平」可见。

**阈值**：`|差额| < 0.5 元` 或 `< 总变化 0.5%` → 显示「0（已对齐）」；否则高亮为下跌色 + 追加提示「差额来自口径差异（转化率/买家数与净销售额非同源），非计算错误；对账不平的结论请降级使用」。

**实测**（`month/2026-09`，`category_mode=sock`）：访客贡献 -¥14,101.35 ｜ 转化率 -¥1,077.09 ｜ 客单价 -¥860.91 → 合计 **-¥16,039.35** = 变化额 **-¥16,039.35**，未解释差额 **0**。

**样式**：`.pr-gap__sum td` 加上边框 + 加粗，与普通因子行区分。版本号 `gap-attribution.js → 20261003b`、`period-review.css → 20261003r`。

### 7.7 商品×渠道接入 + 按品类渠道汇总（已完成）

**背景**：XMind 要求「推广成交金额增加三渠道金额」，且单品可按渠道展开。第一版判定「后端无商品×渠道明细」，实测**数据已在库**（`promotion_creative_daily`，28,337 行，`product_id` 命中 99.8%）。

**改动 1 · `_promotion_items_block`（商品×渠道）**
- 新增 `promotion_creative_daily` 聚合（`GROUP BY channel, product_id`，JOIN `products` 支持品类过滤）
- 装配规则：**优先取 creative 表，取不到才回退** `promotion_daily_facts` 的历史具名渠道行（全站推广）。二选一而非相加，避免两表重叠时重复计数
- 块级新增 `channels_partial` / `channels_groups_present` / `channels_note`，显式声明「全站推广无商品级明细，渠道之和 ≠ 商品合计」
- 实测：`month/2026-09` `category_mode=sock` → **20/20 条**有渠道数据；`all` → 18/20；`missing_inputs` 清空（原为 `promotion_product_channel_scope`）

**改动 2 · `_ads_channel_totals`（按品类渠道汇总）**
- 原逻辑：`category_label` 存在时直接返回空 + `promotion_category_scope`（因为 campaign 行无商品映射）
- 现逻辑：按品类时改从 `promotion_creative_daily` JOIN products 聚合 → 返回 关键词/人群，标 `partial=True` + `missing_inputs=['promotion_channel_all_site_scope']`，且 **`payment_share=None`**（分母不含全站，给占比会把「全站=0」变成事实）
- 全店口径保持原 `grain='campaign'`（4 组 + 占比），不受影响

**改动 3 · `_promotion_dimension`（推广渠道拆解）—— 顺带修既有 bug**
- **发现既有 bug**：`dimensions.promotion.channels` **两种口径下都永远为空**。原因：它查 `grain='channel'`，但实测 `promotion_daily_facts` 的 grain 只有 `campaign / campaign_month / product / unit_month`，**根本没有 `channel` 粒度**（渠道名挂在 `campaign` 行上）
- 修复：渠道维度改查 `grain='campaign'` 按 `channel` 分组（全店口径）；品类口径改走 `promotion_creative_daily`（同 §7.7 改动 2），标 `partial`
- 实测：`all` → 5 个渠道（货品全站推广/关键词推广/人群推广/超级短视频/店铺直达，含 CTR）；`sock` → 2 个渠道 + `partial=True`
- 同时更正了 `PROMOTION_CHANNEL_GROUPS` 上方那段已过时的注释（原写「具名渠道行 product_id 全为空…不能用来拆商品×渠道」，现已被 `promotion_creative_daily` 方案取代）

**改动 4 · 前端（`period-review-live.js`）**
- `channelsTable` 补「**成交**」列（XMind 明确要三渠道成交金额）→ 渠道子表 9 列
- `materialFor('promotion_items')` 的 hint 改用 `block.channels_note`
- 渠道拆分块新增 `channelPartial` 分支：显示表格 + 「按品类口径，覆盖 关键词 / 人群；全站推广无商品级明细，成交占比不适用（切「全部品类」看全店口径）。」
- 推广渠道拆解的 hint 新增 `view.partial` 分支
- 版本号 `period-review-live.js → 20261003x`

**验收证据**
- 接口：`sock` → 渠道拆分 `{source: promotion_creative_daily, partial: true, groups: [关键词 花费 51,201/成交 96,745/ROI 1.89, 人群 8,325/16,796/2.02], payment_share: null}`；渠道拆解 `{available: true, partial: true, items: 2}`。`all` → 渠道拆分 4 组含占比（全站 84.9%）；渠道拆解 5 项含 CTR
- 浏览器：单品表 9 列（商品+7 字段+渠道）× 20 行，每行带收起态渠道子表（内层 9 列，含成交）；「推广渠道拆解」`sock` 2 行 / `all` 5 行；「推广成交金额 · 渠道拆分」分别渲染 2 组（`--` 占比 + 说明）与 4 组（含占比）；无控制台错误
- 测试：相关 6 个测试文件 **216 passed / 32 subtests**

**遗留**：① 按品类的渠道口径仍缺 全站推广（需 v4 补商品级全站场景，或用 `promotion_campaign_items` 做计划→商品归因）；② 「推广计划拆解」在品类模式下仍为空（同上，需计划→商品映射）；③ 2026-08-20 前的历史需回溯补采。


### 7.8 计划 → 商品归因（已完成，关闭 §7.7 的两条遗留）

**结论先行**：`promotion_campaign_items` **足以**同时解决 §7.7 遗留①②，且**不需要均摊、不需要补采**。

**实测数据边界（2026-10-03，勿臆改）**

| 项 | 实测值 |
|---|---|
| `promotion_campaign_items` 行数 | 4,306 行 / **562 计划** / **1,210 商品** |
| 它是历史还是快照 | **当前快照**（`updated_at` 仅 2026-09-18 ~ 10-03），**无历史版本** → 只对 2026-08-20 之后成立 |
| `campaign` 粒度事实覆盖 | `promotion_daily_facts.grain='campaign'` 8,970 行 / 2026-08-20 ~ 10-02 |
| 计划 ↔ 事实关联率 | **562 / 562 = 100%**（计划花费里「无映射」占比 **0%**） |
| 商品命中 `products` | 1,168 / 1,210 = **96.5%** |
| 每计划商品数分布 | 1 个 → 382 计划（67.9%）；最大 **759 个**（计划 `77311432010`，货品全站推广） |
| 按渠道的 1:1 占比 | **货品全站推广 210/212 = 99.1%**；关键词 157/318 = 49.4%；人群 13/27 = 48.1%；店铺直达 2/2 |
| 1:1 精确归因覆盖花费 | 2026-09 全店 **73.9%**；其中货品全站推广 **89.3%**（318,618 / 356,955） |

**关键判断：不做均摊。** 按商品数把计划花费摊到商品＝凭空造数——759 商品的计划摊完每商品只剩零头，且无任何依据。归因只分两档：

- `exact`：计划只绑 **1** 个商品 → 计划花费/成交**全额**归到该商品（精确）
- `shared`：计划绑多个商品 → 只在计划级展示，**不拆到商品**

**改动 1 · 新增 `_campaign_attribution()`（`services/period_context.py`）**
- 计划级列表（花费/成交/ROI/商品数/归因方式/归因商品）+ `exact_share` + `first_fact_date` + `attribution_note`
- `include_product_rows=True` 时额外返回 `{(channel, product_id): row}`，**只含 1:1 计划**，供商品级渠道补全
- ⚠️ **`product_rows` 的 key 是元组，不可 JSON 序列化** → 默认**不返回**，否则接口 500（被新增测试当场抓到，见下）
- ⚠️ **分母必须与分子同口径**：只累加通过品类过滤的计划，否则品类模式下 `exact_share` 会变成「品类内精确 ÷ 全店总花费」（首版即此缺陷，`sock` 误报 18.3%，修正后 49.8%）
- 补采 `cart_adds` / `new_buyers`（8,970/8,970 行均有值）→ 全站行的加购成本/拉新成本/加购率不再空白

**改动 2 · `_promotion_items_block` 渠道补全（关闭遗留①：商品级全站推广）**
- 渠道来源由「二选一」扩到「**三选一**」（绝不相加）：① `promotion_creative_daily`（创意级，当前权威）→ ② **计划 1:1 exact 行** → ③ `promotion_daily_facts` product 粒度历史行（仅全站推广，止于 2026-07-31）
- **根因**：`promotion_creative_daily` 实测**完全没有全站推广**（只有 人群/关键词/店铺直达），而 product 粒度具名行只有 `全站推广` 且止于 2026-07-31 → **2026-08-20 后「商品级全站推广」零来源**，这就是缺口本身
- 新增逐组 `channel_sources`（`creative` / `campaign_exact` / `product_grain` / `mixed`）供审计

**改动 3 · `_promotion_dimension` 计划视图支持品类（关闭遗留②：品类模式计划拆解恒空）**
- 原逻辑：`category_label` 存在且非 product/creative-channel → 直接返回空
- 现逻辑：新增 `campaign_by_category` 分支，走 `_campaign_attribution` 按品类过滤。1:1 计划**精确**过滤；多商品计划花费含品类外商品 → `partial=True`

**改动 4 · 前端（`period-review-live.js` / `period-review.css`）**
- 新增 `campaignAttributionTable()`：「推广计划拆解（计划 → 商品归因）」8 列（计划/渠道/花费/归因成交/ROI/商品数/**归因**/**归因商品**），归因列渲染 `精确`（info）/`多商品`（warning）chip，多商品行「归因商品」列显示「不拆分」
- hint 明写口径：**「仅对『计划只绑 1 个商品』的计划做商品级归因（精确，非均摊）；多商品计划只在计划级展示。映射表为当前快照，仅 2026-08-20 之后有效。」** + 本期精确归因占比
- `channelsTable` 新增「**来源**」列（创意级 / 计划精确归因 / 商品级历史）
- CSS 新增 `.pr-table td .pr-chip` 紧凑规则（否则行高被 chip 撑开）；版本号 `period-review-live.js → 20261003y`、`period-review.css → 20261003s`

**改动 5 · 新增回归测试（`tests/test_period_reviews_api.py`）**
`test_campaign_attribution_is_exact_only_and_fills_all_site_channel` —— 一条测试同时锁住三件事：① 商品级全站推广被补上且 `channel_sources='campaign_exact'`；② 多商品计划**不摊到任何商品**（`B-1.channels == {}`）；③ 品类模式下计划拆解非空、品类外计划被精确排除、`exact_share` 分母同口径。
> 该测试**当场抓到 `product_rows` 元组 key 导致接口 500** 的真 bug——这是只跑单测拿不到的（单测直接调函数，不过 JSON 序列化）。

**验收证据（实测）**

| 口径 | `exact_share` | 计划视图 | `promotion_items.channels_groups_present` |
|---|---|---|---|
| `month/2026-09` `all` | **73.9%** | 20 项 | `['人群','全站','关键词']` |
| `month/2026-09` `sock` | **49.8%** | 20 项 `partial=True` | `['人群','全站','关键词']` |
| `month/2026-08` `all` | 75.8% | 20 项 | 同上 |
| `month/2026-08` `sock` | 60.8% | 20 项 `partial=True` | `['全站','关键词']` |
| `month/2026-10` `all` / `sock` | 65.9% / 36.0% | 20 项 | 同上 |

- 浏览器（CDP 9223，`/period-review`，月复盘 2026-10）：归因块 **20 行 × 8 列**，chips `{精确:17, 多商品:3}`（`all`）/ `{精确:10, 多商品:10}`（`sock`）；首行 `全店模式_通投 | 货品全站推广 | ¥2,954.76 | ¥14,020.93 | 4.75 | 759 | 多商品 | 不拆分`；渠道子表出现 **全站** 组 + 来源列「计划精确归因」；**无控制台错误**
- 测试：相关 5 文件 **88 passed**；全量 **897 passed / 1 failed**（唯一失败为既有 `test_web_update_checker_is_loaded_by_the_common_shell`，`shell.js` mtime 17:16 未变，非本轮引入）

**剩余边界（诚实标注，非缺陷）**
1. 映射表是**快照**，无历史版本 → 2026-08-20 之前的月份不得回填（UI 已写「仅 2026-08-20 之后有效」）
2. 多商品计划（占 2026-09 花费 26.1%）无商品级明细 → 只在计划级展示，不拆
3. `promotion_creative_daily` 与 `campaign` 事实均自 2026-08-20 起 → 更早周期需 `collect_wanxiangtai_dims_v4.py --start/--end` 回溯补采（见 §6.4）

### 7.9 顶部统一「数据状态」+ 利润「部分口径」（P0 #3 / #4，已完成）

**背景**：原方案要求顶部有统一「数据状态：完整 / 部分 / 待补齐 / 不可比」标识，且费用缺失时利润须标「部分口径」。此前**页面顶部是一句裸文案**「数据已就绪 · 覆盖 n/m 天」——只说覆盖、不说别的；利润卡则**完全不标**。

**设计原则：只显示「部分数据」是不可操作的，必须说清哪块降级、为什么、影响什么。** 故做成「灯 + 原因清单」，每条原因带 severity 与一句人话。

**改动 1 · 后端新增 `_data_status(period, metrics, blocks)`（`services/period_context.py`）**
- **只汇总、不重查库**：6 类判据全部从已算好的块里取，避免二次查询与口径漂移
  ① 周期覆盖（`coverage.status`）② 可比性（`comparability[kind].comparable===false` → 翻人话）③ 利润恒等式（`profit_structure.identity.ok===false`，带 `sentinel_rows`）④ 市场 `run_alignment==='partial'` ⑤ **口径边界（info）**：`ads.channel_totals.partial` / `promotion_items.channels_partial` / `campaign_attribution.exact_share<0.9999` / `dimensions.promotion.*.partial` ⑥ 顶层 `missing_inputs`
- severity 两档：`warning`＝**数字不可全信**（覆盖不足 / 不可比 / 恒等式不平）；`info`＝**口径有边界**（不影响结论，但读者该知道）
- ⚠️ **`level` 与 `usable` 必须分离**（本轮最关键的设计决定）
  - `level` 只表达**周期覆盖完整性**（`complete` / `partial` / `no-data`）
  - `usable` 才表达**数字能不能直接用**（`has_data and warning_count==0`）
  - **踩坑**：首版只有 `level`，结果连 `month/2026-09`（覆盖 30/30 天）都因结构性 warning（利润不平 + 市场未对齐）而变 `partial` → **「永远是黄的」**，读者会直接忽略这盏灯。分离后 `2026-09` 是「灯绿但标注 2 项影响可信度」，语义才正确
- label 由 `warning_count` / `info_count` 动态生成：`数据完整` / `数据可用（n 项口径边界）` / `部分数据（n 项影响可信度）` / `暂无数据`

**改动 2 · 前端 `dataStatusNode(context)`（`period-review-live.js`）**
- 驾驶舱顶部渲染 `.pr-data-status`（`<details>` 折叠面板，默认收起）
- `<summary>` = 状态灯（`is-good` 绿 / `is-warning` 黄 / `is-empty` 灰）+ label + 「详情 ▾」
- 展开体 = ① `freshness`（「数据区间 2026-10-01 ~ 2026-10-02（本期进行中，已过 3/31 天）」）② 一句话 summary ③ 按 `影响可信度` / `口径边界` 分组的原因清单（**warning 在前**），每条 `<strong>label</strong>：detail`
- 替换原裸文案；`.pr-caliber-badge` 与 `caliberBadge()` 供徽标复用
- 版本号：`period-review-live.js → 20261003z`、`period-review.css → 20261003t`、`metric-cards.js → 20261003c`

**改动 3 · 利润「部分口径」徽标（P0 #4）**
- 判据 `profitIsPartial(structure)` = `structure.available && structure.identity.ok === false`
- 落两处：① 净利润指标卡（`metric-cards.js`）② 「利润结构（利润瀑布）」块标题（`materialBlock` 新增 `badges` 参数）
- hint 明写：`利润为部分口径：{n} 行利润未回填：恒等残差 {gap}，该值仅供参考。详见「利润结构（利润瀑布）」。`
- ⚠️ **实测：四种口径下利润恒等式全部不平衡**（`all/2026-09` gap 68.3 万 / `all/2026-10` 19.6 万 / `sock/2026-09` 10.8 万 / `sock/2026-10` 3.3 万；`sentinel_rows` 155/24/10/1）→ 这标不是「锦上添花」，而是**本该有而一直缺**。根因是补采窗口 155 行费用列缺失（`sentinel` 行），已列入补采待办

**改动 4 · 新增回归测试（`tests/test_period_reviews_api.py`）**
- `test_data_status_separates_coverage_level_from_metric_usability` —— 4 个场景锁死 `level`/`usable` 分离：完整月 + warning → `level='complete'` 且 `usable=False`；仅 info → `usable=True`；覆盖不足 → `level='partial'`；无数据 → `level='no-data'`
- `test_context_exposes_data_status_payload` —— API 级，断言 `data_status` 11 个必需键齐备
- > 写测试时自身踩坑：② 场景误复用了带同比不可比的 metrics → `usable` 断言失败；改用独立的 `clean_metrics`（`comparability` 全 `comparable=True`）才通过。**说明判据之间会互相污染，测试必须用干净输入**

**验收证据（实测，CDP 9223 / `/period-review`）**

| 口径 | `level` | `usable` | warning | info |
|---|---|---|---|---|
| `all` 2026-09 | complete | **False** | 2（利润不平 / 市场未对齐） | 2 |
| `all` 2026-10 | partial | False | 4（+ 覆盖不足 / 同比不可比） | 2 |
| `sock` 2026-09 | complete | False | 2 | 5 |
| `sock` 2026-10 | partial | False | 4 | 5 |

- 浏览器（月复盘 `2026-10` `all`）：`.pr-data-status` **`present=true`**、`classes="pr-data-status is-warning"`、`hasDetails=true`、**`totalCopies=1`**（抽屉隐藏副本未重复命中）；展开后 `groups=["影响可信度","口径边界"]`、6 条明细顺序正确；净利润卡 `badge="部分口径"` + hint；利润瀑布块 `badge="部分口径"`；**`consoleErrors=[]`**
- `sock` 品类模式多出 3 条 info（品类渠道拆解 / 计划拆解 / 推广渠道拆解的部分口径边界），符合预期
- 截图存证：`docs/archive/verify-data-status-20261003.png`（顶部面板展开）、`docs/archive/verify-profit-caliber-20261003.png`（利润瀑布徽标 + 残差说明行）
- 验证脚本：`scripts/verify-period-review-data-status.cjs`（断言 5 项，`--json` 出报告）、`scripts/shot-period-review-data-status.cjs`（`--target status|profit` 截图）

**踩坑（截图四坑，第二次复用仍要小心）**
1. `page.screenshot({clip})` 的 `clip` 是**文档坐标**，而 `getBoundingClientRect()` 是**视口坐标** → 不混用
2. 页面有 **sticky header** → 目标要滚到视口中上部再截
3. 证据块在**折叠的** `<details class="pr-evidence">` 内 → 先 `details.open = true`
4. 抽屉 `.pr-drawer__body`（默认 `visibility:hidden`）里有**同一份副本** → `querySelectorAll` 会重复命中
   → **结论：`details.open=true` + `window.scrollTo` + 截视口（不带 `clip`）**。验证脚本里对应 `totalCopies` 断言（应为 1）
5. 顶部数据状态浮层展开时会**遮住指标卡** → 截利润块时必须先把它收起来（脚本用 `--target` 区分）

**剩余边界（诚实标注）**
- `usable=False` 在**当前所有口径**下都成立（因利润恒等式不平是结构性的）→ 面板会一直是黄灯。这不是 bug，是**如实反映**；要变绿必须补采 155 行费用列


### 7.10 市场分级接入（8大归类 / 词根需求 / 趋势节点 / 趋势市场 / 蓝海市场 / 竞店爆品）+ 修掉一个静默空表 bug

**结论先行**：市场分级**不需要新写算法** —— `services/market_monitor_service.py` 已投产于「市场排行」页（8大归类 / 蓝海 / 趋势节点 / 竞店爆品）。月复盘页此前**没复用**，这才是缺口本身。本轮把它接进 `_market_block`，两页共用同一份口径。

**改动 1 · `_market_block` 复用已投产算法（`services/period_context.py`）**
- 新增 `keyword_insights`（8大归类 + 蓝海近似 + 趋势节点）、`blue_ocean_supply`（词根级每万覆盖分级）、`rival_moves`（竞店爆品排名变化）、`trend_items`（商品级趋势）
- ⚠️ **窗口取「复盘周期 ∩ 数据实际覆盖」**，不是复盘周期本身。市场表只从 2026-09-16 起；若按整月算，`keyword_insights` 的「近 7 天 + 前置基线」两段会落在无数据区 → 趋势节点恒空。交集窗口 + 显式回报窗口天数才诚实
- 新增 `grading`（`keyword_window` / `item_window` / `trend_node_threshold` / `trend_node_available` / `limitations`）—— 窗口与口径边界**集中声明一处**，前端不再各自拼「有效期」文案
- 市场分级是增强项，整体包在 try 里：任何异常都不拖垮复盘上下文

**改动 2 · `market_monitor_service` 补两个同源能力**
- `trend_items()` —— 商品排行·趋势市场。与 `rival_item_moves` **同源**（窗口首尾排名对比），差别只在聚合维度（商品 vs 店）；两个函数必须一起改，否则口径分叉
- `classify_keyword()` —— 公开包装 `(key, label)`，让月复盘标注趋势词时复用同一套 8 大归类词典，不各写一份

**改动 3 · ⛔ 修掉一个静默空表 bug（本轮最值钱的发现）**

`_market_block` 的 `aggregate()` 原实现对非 `sycm_market_rival_shop` 的表统一 `MAX(detail_url)`。但：

| 表 | 有 `detail_url`？ |
|---|---|
| `sycm_market_item_rank` | **没有**（只有 `pic_url` / `shop_name`） |
| `sycm_market_rival_item` | 有 |

→ `sqlite3.OperationalError: no such column: detail_url` → 被外层 `except Exception: missing.append('sycm_market_item_rank')` **吞掉** → **`competitor_items` 长期为空**，且 `missing_inputs` 里挂着一个误导性的 `sycm_market_item_rank`（读者会以为「没数据」，其实是「SQL 写错了」）。

- 文档 §1.4 原写「竞品商品级数据未接入、前端逻辑空转」——**判断错了**，真相是 SQL 查了不存在的列
- 修法：`aggregate()` 改为**按 `PRAGMA table_info` 实测列存在性拼装**，从根上杜绝这类「查不存在的列」的静默失败
- 效果：`competitor_items` **0 → 10 条**（含 `market_rank` / `market_shop` / `market_title`），`missing_inputs` 里的误导项消失

**改动 4 · ⛔ 修掉蓝海分级「一档到底」的误判（`blue_ocean_words`）**

`cover_per_10k = 覆盖 ÷ (日均热度/万)`，`cover=0 → per10k=0 → <5 → 判「高潜蓝海」`。但在榜样本只有**最新日 600 款**（5 类目 × top120），词根与标题用词不一致时覆盖也是 0：

| 词根 | 600 在榜 title 命中 |
|---|---|
| 毛巾袜 / 小白袜 / 脚尖加固 / 长腿袜 / 半腿袜 | **0** |
| 压力袜 | 13 |
| 堆堆袜 | 64 |
| 中筒 | 151 |

实测 12 个词根里 **8 个覆盖为 0、全判「高潜蓝海」** → 分级塌成一档，对运营是误导（会去追一个并不存在的蓝海）。

- 修法：`cover == 0` 单列 **「待核」**（附 `note` 说明「可能是真蓝海，也可能是词根与标题用词不一致，需人工核」），不给分级结论；`cover_per_10k` 仍保留 0 以不破坏市场排行页的数字渲染
- 排序：`GRADE_ORDER = {高潜蓝海:0, 中等:1, 供给偏多:2, 待核:3}` —— **待核排最后**，它不是结论，不该占榜首
- 保留可见：`graded[:12] + pending[:6]`，并回报 `graded_count` / `pending_count`。若把待核一并截断，遇到「已分级词 ≥12」时它们会整体消失，而待核恰恰需要人工看一眼
- 同步更新市场排行页 hint 文案（`market-ranking-live.js`）
- **修正后的真实结论**：袜子类目样本内**所有能匹配上的词根都是「供给偏多」**（per10k 6.33 ~ 126.36），即样本层面已饱和；真正需人工看的是 6 个「待核」词根

**改动 5 · 前端（`period-review-live.js`）新增 6 块**
「关键词洞察 · 8 大归类」「趋势节点分析」「蓝海市场 · 低供给词根」「商品排行 · 趋势市场」「竞店爆品排名变化」「市场分级口径边界」。版本号 `period-review-live.js → 20261003za`、`market-ranking-live.js → 20261003a`

**改动 6 · 测试**
- `tests/test_market_monitor_service.py`：**改写 2 条把旧缺陷写死的测试**（`test_zero_cover_is_high_potential` → `test_zero_cover_is_pending_not_blue_ocean`），新增 `trend_items` ×2、`classify_keyword` ×2、`graded` 排序 ×1
- `tests/test_period_reviews_api.py`：新增 `test_market_block_exposes_grading_and_is_json_serializable` —— 走 API 层，**并显式 `json.dumps(payload)`**（元组 key / datetime 这类不可序列化对象只有走到 API 层才暴露）

**验收证据（实测）**

| 项 | 实测 |
|---|---|
| 8 大归类（2026-09，15 天窗口） | 9 类：类目 721 词 / 42.3%、人群 944 / 27.9%、属性 470 / 10.9%、品牌 148 / 5.8%、风格 133 / 4.8%、功能 186 / 3.9%、其他 380 / 2.1%、场景 143 / 1.7%、价格 20 / 0.5% |
| 趋势节点 | 起势 10 / 退势 10（`trend_node_available=true`，阈值 ±50%） |
| 蓝海词根分级 | 18 行 = 已分级 12（中等 1 / 供给偏多 11）+ 待核 6；`graded_count=16`、`pending_count=8`（截断前） |
| 商品排行 · 趋势市场 | 窗口 13 天：上升 **296** 个 / 新进榜 **226** 个（在榜 1474 商品） |
| 竞店爆品排名变化 | 全市场 **601** 家，展示前 15；首行 `Bananain蕉内旗舰店` |
| 竞品商品对标 | **10 条**（修复前 0），首行 `第1名 · 有棵树官方旗舰店` |
| 浏览器（CDP 9223，月复盘 2026-09） | 6 个新块全部渲染，`consoleErrors=[]` |
| 截图 | `docs/archive/verify-market-keyword-8class-20261003.png`、`verify-market-grading-20261003.png`、`verify-competitor-items-fix-20261003.png` |
| 脚本 | `scripts/verify-period-review-market-grading.cjs`、`scripts/shot-period-review-market-grading.cjs` |
| 测试 | 相关 5 文件 **72 passed**；全量见下 |

**剩余边界（诚实标注，非缺陷）**
1. 市场表**只从 2026-09-16 起** → 2026-09 的 15 天窗口已是上限；更早周期需采集器回溯补采
2. **周复盘（7 天窗口）趋势节点恒不可判** —— `keyword_insights` 需要「近 7 天 + 前置基线」两段。UI 会显式显示「基线数据不足」，不是静默空白
3. 竞店↔商品榜**不能按 `shop_id` 关联**（两套 ID 命名空间，646 vs 50 家 **0 交集**）；只有 `shop_name` 能对上 **23/647 家**。故竞店爆品榜是**按店名聚合**、覆盖不全 → `rival_moves` 走的是「商品榜内所有店」而非「已登记竞店」
4. 竞品**男女款**维度缺字段（`sycm_market_item_rank` 无性别），需从 title 解析或换源
5. 趋势节点用「近 7 天 vs 前置窗口」，**小基数词会给出夸张增速**（实测 `艺术袜` 基线日均 35 → 近 7 天 360 = +928.6%）。这是既有算法行为，本轮未改（避免扩大改动面）；若要收敛需加基线热度下限
6. 蓝海「待核」是**待人工核**，不是结论 —— 需要在页面上被当作待办处理，不能当机会

---

## 7.11 市场表历史补采：能力边界与阻塞（第六轮，2026-10-03）

**为什么要补**：复盘页可选周期 = 2025-09 全月 + **2026-08 全月** + 2026-09 全月 + 2026-10-W1。
而市场表只从 2026-09-16 起 → **2026-08 的市场分级全空**
（`market.available=false`、`missing_inputs=['market_source_facts']`）。

### 各表覆盖与缺口（补采前实测）

| 表 | 覆盖 | 缺口 |
|---|---|---|
| `daily_data` / `promotion_daily_facts` / `store_daily_facts` | **2025-09-01 ~ 今** | ✅ 完整（一整年） |
| `sycm_market_item_rank` | 2026-09-16 起（15 天，另缺 9-20/9-21） | 8 月全月 + 9 月上半月 |
| `sycm_market_search_rank` | 2026-09-16 起（17 天） | 同上 |
| `sycm_market_rival_shop` / `_rival_item` | 2026-09-16 起（17 天） | 同上 |
| `sycm_flow_source_daily` / `_item_flow_source_daily` | 2026-09-10 起 | 8 月 + 9 月上旬（**复盘页不消费**，优先级低） |
| `bi_product_daily_raw` | 2026-09-14 起 | 8 月 + 9 月上旬 |
| `promotion_creative_daily` | 2026-08-20 起 | 8-20 前 |

### 能力验证：接口可回溯，且是「真回溯」

- 采集器 `collectors/collect_sycm_market.py` **早已支持日期参数**
  （`python collect_sycm_market.py 2026-09-10`；注释写明「原先硬编码昨天，导致历史日期无法回补」）
- 实测 **2026-06-01 仍返回 120 条真实历史榜**；各日期指纹与 UV 合计**各不相同**
  （6-01 `fp=0f9eed0535` uv=1027952 / 9-15 `fp=e08a689116` uv=504592）
  → 排除「忽略 dateRange 返回当日榜」的假回溯
- 补 2026-09-15 一天后，落库指纹 = `e08a689116`，与探测值**完全一致** → 落库即真实历史

### ⛔ 采集器缺陷：`item_rank` 整表空仍报成功（解释 9-20/9-21 静默丢）

`collector_runs` 显示 9-21/9-22 运行 `status=succeeded`、`quality_gate=passed`、
`coverage.succeeded_units=5`（**硬编码 = expected_units**），但 `row_count=1560` ≠ 2160。
`1560 = 1500+50+10` → **item_rank = 0**。
⇒ 补采与验收**一律按落库实际行数判**，不看采集器自报状态。

### ⛔ 阻塞：x5sec 账号级风控（需人工过滑块）

- 触发条件：约 126 个请求、间隔 0.2s（探测 10 个日期 + 补采 1 天）
- 判据：`{"ret":["FAIL_SYS_USER_VALIDATE","RGV587_ERROR::SM::哎哟喂,被挤爆啦"]}`
  + 跳 `/punish?x5secdata=` + `punishTextFetch` 返回
  `{"ncLanguagePack":{...,"SLIDE":"向右滑动验证"}}`
- **页面通道同样被拦**（页面内 fetch 被 hook 挂住）→ 账号级，非「直调 vs 页面」问题
- ⚠️ 高频探测**延长封禁** → 探测间隔放到 3 分钟；恢复需人工在浏览器过滑块

### 产出

- `E:/www/BI采集/collectors/backfill_sycm_market.py` —— 补采编排
  （fail-closed：行数不达标**不写库**；单日重试；连续失败即停；`--skip-existing`）
- `scripts/verify_market_backfill.py` —— 三层校验
  （落库层覆盖与缺口 / 上下文层 `available` 与窗口天数 / 边界层 9-16 后数据未被动）
- `.tmp_wait_then_backfill.py` —— 低频等风控恢复 → 自动补采
