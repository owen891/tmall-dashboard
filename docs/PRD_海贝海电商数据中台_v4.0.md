# 海贝海电商数据中台 · 项目需求文档（PRD）

> 版本：v4.0 ｜ 最后更新：2026-05-12 ｜ 文档状态：完整终稿
> 项目代号：HaiBeiHai Data Platform ｜ 技术栈：Vue 3 + FastAPI + ECharts

---

## 目录

- [一、项目概述](#一项目概述)
- [二、数据中台三层架构](#二数据中台三层架构)
- [三、核心功能模块](#三核心功能模块)
- [四、补充模块（代码中已实现）](#四补充模块代码中已实现)
- [五、非功能性需求](#五非功能性需求)
- [六、技术架构](#六技术架构)
- [七、数据字典](#七数据字典)
- [八、接口规范](#八接口规范)
- [九、项目里程碑](#九项目里程碑)
- [十、成功标准](#十成功标准)
- [附录 A：需求来源对照表](#附录-a需求来源对照表)

---

## 一、项目概述

### 1.1 项目定位

构建**电商数据中台**，作为连接投放、销售、库存、物流、内容等多源数据的统一底座，将实时数据流与历史离线数据汇聚到同一仓库/服务层，面向多团队提供标准 API、报表、模型与可视化，支撑数据驱动决策。

### 1.2 核心价值

| 价值维度 | 说明 |
|---------|------|
| **统一数据底座** | 打通投放/销售/库存/物流/内容多源数据孤岛 |
| **实时 + 离线融合** | 将实时数据流与历史离线数据汇聚到统一仓库 |
| **标准化服务** | 面向多团队提供标准 API、报表、模型与可视化 |
| **数据驱动决策** | 决策靠数据，而非经验拍脑袋 |

### 1.3 适用范围

适用于天猫/淘宝电商运营团队，覆盖商品运营、广告投放、数据分析、供应链管理全链路。

---

## 二、数据中台三层架构

### 2.1 数据层

| 功能 | 说明 |
|------|------|
| **接口采集** | 对接天猫、淘宝、京东、抖音等多平台数据接口 |
| **数据清洗** | ETL 处理、去重、标准化、异常值检测 |
| **统一仓库** | 实时数据流 + 离线历史数据统一存储 |

**数据源清单：**

- 广告投放数据（直通车、引力魔方、万相台）
- 销售交易数据（订单、支付、退款）
- 库存物流数据（库存量、周转率、发货时效）
- 内容运营数据（短视频、直播、图文种草）
- 用户行为数据（浏览、收藏、加购、转化）

### 2.2 算法/模型层

| 模型 | 业务场景 |
|------|---------|
| **ROI 预测模型** | 预测投放 ROI，优化广告预算分配 |
| **人群漏斗模型** | AIPL（认知→兴趣→购买→忠诚）人群流转分析 |
| **内容带货模型** | 内容效果评估，选品与内容匹配 |
| **库存预测模型** | 销量预测、补货建议、滞销预警 |
| **商品评分模型** | 多维度综合评分（0-100），辅助分层决策 |

### 2.3 服务层

| 服务 | 说明 |
|------|------|
| **报表自动化** | 日/周/月自动化报表，定时推送 |
| **指标预警** | 自定义阈值，异常指标自动告警 |
| **BI 看板** | 多维度可视化大屏与交互式仪表板 |
| **API 输出** | 标准化 RESTful API，支持第三方系统集成 |

---

## 三、核心功能模块

### 3.1 运营指挥塔（驾驶舱） `/`

**功能清单：**
- 8 大核心 KPI 卡片（GMV、访客、转化率、ROI、客单价、退款率、广告占比、库存周转）
- 目标完成进度仪表盘（环形进度图，实际 vs 目标对比）
- GMV/流量趋势图（双 Y 轴）
- 流量结构分析（搜索/推荐/付费/免费占比）
- 热销 TOP10 商品排行
- 智能预警规则与告警记录
- 快捷入口（商品列表、生命周期、利润分析、广告投放）

**数据更新频率：** 5 分钟

---

### 3.2 商品总览（BI 看板） `/dashboard`

**三大 Tab 切换：渠道总览 | 商品总览 | 团队总览**

#### 3.2.1 商品总览 — 8 大分类指标卡片

| 序号 | 分类名称 | 标签 | 筛选条件（SQL） |
|------|---------|------|----------------|
| 1 | 高毛利盈利单品 | 利润 | `(payment_amount - ad_spend) / payment_amount >= 0.30 AND ad_spend / payment_amount <= 0.30` |
| 2 | 低毛利战略单品 | 利润 | `(payment_amount - ad_spend) / payment_amount >= 0.70 AND payment_qty >= 300` |
| 3 | 高付费高退款 | 款式 | `ad_spend / payment_amount >= 0.20 AND refund_amount / payment_amount >= 0.30` |
| 4 | 亏损链接 | 利润 | `payment_amount - ad_spend - refund_amount < 0` |
| 5 | 高转化亏损 | 定价 | `payment_amount - cost < 0 AND payment_conversion >= 0.10` |
| 6 | 高搜索亏损 | 定价 | `search_visitors / visitors >= 0.90 AND payment_amount - cost < 0` |
| 7 | 亏损 SKU | 亏损 | `payment_amount <= 500` |
| 8 | 盈利放大 | 亏损 | `(payment_amount - cost) / payment_amount >= 0.10 AND ad_spend / payment_amount <= 0.01` |

**每张卡片展示：** 商品数量、较上周期变化趋势（↑/↓ 百分比）、占比（%）

#### 3.2.2 团队总览

**统计维度切换：** 按经理统计 | 按负责人统计 | 按助理统计

**团队卡片信息：** 员工 ID、在职天数、链接数（管理商品数量）、支付金额、利润（支付预估）、详情按钮

#### 3.2.3 顶部筛选条件

| 筛选项 | 选项 |
|--------|------|
| 统计时间 | 日期范围选择 |
| 时间跨度 | 7 天 / 30 天 / 日 / 周 / 月 / 自定义 |
| 数据同步 | 手动触发数据同步按钮 |
| 商品总数 | 页面顶部显示总商品数 |

**数据更新频率：** 15 分钟

---

### 3.3 商品全生命周期管理 `/lifecycle`

**四大生命周期阶段：**

| 阶段 | 判定条件 | 核心策略 | 系统动作 |
|------|---------|---------|---------|
| **导入期** | 上架 < 30 天 OR 累计订单 < 100 | ROI < 1.5 停投 | 自动监测 ROI，低于阈值触发停投建议 |
| **成长期** | 近 7 天 GMV 环比增长 > 20% | 持续内容投放 | 推荐内容素材，监控流量增长趋势 |
| **成熟期** | 近 30 天 GMV 波动 < 15% AND 利润率 > 25% | 毛利最大化 | 利润监控、价格优化建议、竞品对比 |
| **衰退期** | 近 14 天 GMV 环比下降 > 20% OR 库存周转天数 > 90 | 打折 + 清仓 | 清仓建议、折扣力度测算、库存预警 |

**全周期评分机制：**
- 综合评分 >= 80 分 → 保留继续经营
- 综合评分 < 80 分 → 预警考虑优化或淘汰

**数据更新频率：** 6 小时

---

### 3.4 商品健康度分析 `/health`

**12 维度评分体系（0-100 分）：**

| 维度 | 权重 | 评分公式 | 行业基准值 |
|------|------|---------|-----------|
| 销售额 | 15% | `(实际GMV / 目标GMV) * 100` | 月 GMV 10 万 |
| 访客数 | 10% | `(实际访客 / 目标访客) * 100` | 月访客 5 万 |
| 转化率 | 12% | `(实际转化率 / 5%) * 100` | 5% |
| 客单价 | 8% | `MIN(100, 客单价 / 100 * 100)` | 100 元 |
| ROI | 12% | `MIN(100, ROI / 3.0 * 100)` | 3.0 |
| 退款率 | 10% | `MAX(0, 100 - 退款率/8% * 100)` | 8% |
| 评分 | 8% | `(商品评分 / 5.0) * 100` | 5.0 |
| 库存周转 | 8% | `MAX(0, 100 - 周转天数/60 * 100)` | 60 天 |
| 收藏加购 | 5% | `(加购率 / 15%) * 100` | 15% |
| 复购率 | 5% | `(复购率 / 20%) * 100` | 20% |
| 广告占比 | 4% | `MAX(0, 100 - 广告占比/30% * 100)` | 30% |
| 内容转化 | 3% | `(内容转化率 / 3%) * 100` | 3% |

**健康等级分布：**
- 优秀（85-100）/ 良好（70-84）/ 一般（50-69）/ 危险（0-49）

**数据更新频率：** 6 小时

---

### 3.5 商品分析（详细） `/products`

**功能清单：**
- 商品列表（搜索/筛选/排序/分页）
- 收藏功能、分层标签（引流款/利润款/潜力款/淘汰款）
- 内联编辑（分层、风格、负责人）、批量操作
- 数据导出（CSV/JSON）、列配置（自定义显示字段）
- 商品详情页（周度/月度数据趋势）
- 运营动作记录（标题优化、主图优化、价格调整等）
- 商品笔记、排行榜

**数据更新频率：** 日度

---

### 3.6 利润分析 `/profit`

**功能清单：**
- 利润概览（总毛利、毛利率、净利、净利率）
- 按商品/类目/负责人利润排行
- 成本结构分析（采购成本、物流成本、广告成本、平台佣金）
- 利润趋势（日/周/月）、利润率分层分析
- 盈亏平衡分析

**数据更新频率：** 1 小时

---

### 3.7 广告投放分析 `/ads`

**功能清单：**
- 万相台投放效果（消耗、点击、转化、ROI）
- DMP 人群分析（人群包效果、资产统计）
- AIPL 人群流转分析
- A/B 测试管理（实验创建、效果分析）
- 投放 SOP 模板、投放项目管理与任务分配
- 人效 KPI 与团队绩效
- 智能预警（消耗异常、ROI 跌破阈值）
- 供应链数据联动（库存不足自动暂停投放）

**数据更新频率：** 15 分钟

---

### 3.8 评价分析 `/reviews`

**功能清单：**
- 6 大统计卡片（总评价数、平均评分、好评率、差评数、中评数、关键词数）
- 情感分布（好评/差评/中评饼图）、评分分布（1-5 星柱状图）
- **好评维度分析**（质量/价格/服务/物流/外观/口感/功效/包装/性价比/推荐）
- **差评维度分析**（质量/价格/服务/物流/外观/口感/功效/包装/描述不符/退货）
- **典型场景分布**（回购意愿/送礼场景/囤货场景等）
- TOP20 热点关键词、评价列表

**数据更新频率：** 24 小时

---

### 3.9 市场分析 `/market`

**功能清单：**
- 市场概览（商品数量、总 GMV、平均价格、平均 ROI）
- 关键词分析（搜索量/竞争度/机会分/30 天趋势）
- 市场机会识别（蓝海关键词推荐）
- 类目分布分析（饼图 + 详情表）
- 竞品分析（排名/GMV/市场份额/价格区间）
- **需求分析 8 大维度**（搜索热度/转化率/退款率/广告 ROI/广告占比/客单价/竞争度/库存周转）
- 行业榜单（4 种视角：销量/增速/利润/综合）
- 价格分布分析、TOP 产品排行

**数据更新频率：** 24 小时

---

### 3.10 漏斗分析 `/funnel`

**5 步转化漏斗：** 曝光 → 点击 → 收藏/加购 → 下单 → 支付

**功能清单：** 整体漏斗、分渠道漏斗、转化路径分析、流失分析、商品级漏斗、漏斗趋势

**数据更新频率：** 日度

---

### 3.11 对比分析 `/compare`

**功能清单：** 双期对比、多期趋势叠加（3/6/12 个月）、同比/环比分析、指标对比、商品对比

---

### 3.12 库存分析 `/inventory`

**功能清单：** 库存预警列表（缺货/滞销）、库存汇总、库存周转分析、滞销商品识别、补货建议、供应链数据联动

**数据更新频率：** 6 小时

---

### 3.13 预测分析 `/prediction`

**功能清单：** GMV 预测（未来 7/30/90 天）、访客预测、库存需求预测、销量趋势预测、预测准确率评估

---

### 3.14 导入中心 `/import-center`

**功能清单：** 定时任务管理（Cron 表达式配置）、文件匹配规则配置、手动触发导入、任务启停控制、导入历史查询、导入模板下载、文件存储管理

---

### 3.15 智能预警系统 `/alerts` + `/smart-alert`

**功能清单：**
- 基础预警：预警规则管理、预警记录查询、预警统计
- 智能预警：AI 异常检测、自动根因分析、多渠道通知（站内信/邮件/钉钉/企业微信）

---

### 3.16 工具箱 `/toolbox`

**功能清单：** ROI 诊断、价格优化建议、关键词推荐、商品推荐（关联销售）、智能分析报告生成

---

### 3.17 系统设置 `/settings`

**功能清单：** 基础系统配置、全局参数设置

---

## 四、补充模块（代码中已实现）

以下模块在后端代码和前端路由中已有实现，但在原始 PRD 中未完整覆盖：

### 4.1 人群资产分析 `/crowd-asset`

| 项目 | 说明 |
|------|------|
| 对应后端 | `crowd_asset.py` |
| 对应前端 | `CrowdAsset.vue` |
| 数据模型 | `DMPAudience`、`DMPProductData`、`AIPLStats` |
| 功能描述 | AIPL 人群流转分析、人群包管理、资产统计 |

**功能清单：**
- AIPL 人群资产概览（认知/兴趣/购买/忠诚人群数量及占比）
- 人群流转率分析（A→I、I→P、P→L 转化率）
- 人群包效果评估（各人群包的 GMV、ROI、转化贡献）
- 人群标签管理（性别、年龄、消费力、偏好等维度）
- 人群资产趋势（7d/30d/90d 变化趋势）
- 蓄水能力与收割能力评分

**数据更新频率：** 日度

---

### 4.2 归因分析 `/attribution`

| 项目 | 说明 |
|------|------|
| 对应后端 | `attribution.py` |
| 对应前端 | `Attribution.vue` |
| 功能描述 | 多触点归因分析 |

**功能清单：**
- 最后点击归因（Last Click）
- 首次点击归因（First Click）
- 线性归因（Linear）
- 时间衰减归因（Time Decay）
- 位置归因（Position-based）
- 多渠道归因对比
- 触点路径可视化

**数据更新频率：** 日度

---

### 4.3 渠道详情 `/channel-detail`

| 项目 | 说明 |
|------|------|
| 对应前端 | `ChannelDetail.vue` |
| 数据模型 | `TrafficSource`、`ProductTrafficDetail`、`TrafficStructure` |
| 功能描述 | 各渠道流量明细、转化对比 |

**功能清单：**
- 渠道流量明细（搜索/推荐/付费/免费）
- 渠道转化对比（CTR、CVR、ROI）
- 渠道趋势分析
- 渠道贡献占比

**数据更新频率：** 日度

---

### 4.4 协同工作 `/collaboration`

| 项目 | 说明 |
|------|------|
| 对应后端 | `collaboration.py` |
| 对应前端 | `Collaboration.vue` |
| 数据模型 | `TaskItem`、`CampaignProject` |
| 功能描述 | 任务分配、进度跟踪、团队协作 |

**功能清单：**
- 任务看板（Todo / In Progress / Done / Blocked）
- 项目时间线
- 任务分配与跟踪
- 团队工作负载查看
- 项目进度报告

**数据更新频率：** 实时

---

### 4.5 A/B 测试 SOP `/abtest-sop`

| 项目 | 说明 |
|------|------|
| 对应后端 | `abtest_sop.py` |
| 对应前端 | `ABTestSop.vue` |
| 数据模型 | `ABTest`、`ABTestVariant`、`ABTestMetrics`、`ABTestAnalysis`、`SOPTemplate` |
| 功能描述 | A/B 测试全流程管理 |

**功能清单：**
- 实验创建（创意/标题/人群/出价/价格等类型）
- 变体配置（A/B/C 多组对比，流量分配）
- 效果监控（CTR、CVR、GMV、ROI 实时追踪）
- 显著性检验（置信度、提升百分比）
- SOP 模板库（大促/上新/优化/常规）
- SOP 效果反馈与评分

**数据更新频率：** 15 分钟

---

### 4.6 数据质量监控 `/data-quality`

| 项目 | 说明 |
|------|------|
| 对应后端 | `data_quality.py` |
| 对应前端 | `DataQuality.vue` |
| 数据模型 | `SystemSetting` |
| 功能描述 | 数据完整性检查、异常值检测、数据清洗规则 |

**功能清单：**
- 数据完整性检查（缺失字段统计）
- 异常值检测（超出合理范围的数据标记）
- 数据清洗规则管理
- 数据质量评分
- 数据同步状态监控

**数据更新频率：** 日度

---

### 4.7 数据可视化 `/data-visualization`

| 项目 | 说明 |
|------|------|
| 对应前端 | `DataVisualization.vue` |
| 功能描述 | 自定义看板、拖拽式布局 |

**功能清单：**
- 自定义看板创建
- 拖拽式布局
- 组件库（图表/表格/指标卡）
- 看板模板
- 看板分享

**数据更新频率：** 实时

---

### 4.8 智能导入 `/smart-import` + `/advanced-import-center`

| 项目 | 说明 |
|------|------|
| 对应后端 | `smart_import.py`、`imports.py` |
| 对应前端 | `SmartImport.vue`、`AdvancedImportCenter.vue` |
| 数据模型 | `ScheduledTask`、`ImportHistory`、`FileStorage` |
| 功能描述 | 智能字段匹配、数据预览、冲突解决 |

**功能清单：**
- 智能字段匹配（自动识别列名并映射）
- 数据预览（导入前预览并确认）
- 冲突解决（重复数据处理策略）
- 导入进度追踪
- 导入历史查询
- 模板下载与上传

**数据更新频率：** 按需

---

### 4.9 备份管理 `/backup` + `/backup-management`

| 项目 | 说明 |
|------|------|
| 对应后端 | `backup.py`、`backup_management.py` |
| 对应前端 | `Backup.vue`、`BackupManagement.vue` |
| 功能描述 | 备份策略配置、恢复演练、备份验证 |

**功能清单：**
- 自动备份（每日/每周/每月）
- 备份策略配置
- 备份文件管理
- 数据恢复
- 恢复演练
- 备份验证

**数据更新频率：** 按需

---

### 4.10 促销分析 `/promotion-analysis`

| 项目 | 说明 |
|------|------|
| 对应前端 | `PromotionAnalysis.vue` |
| 功能描述 | 促销效果深度分析 |

**功能清单：**
- 促销 ROI 分析
- 活动效果对比
- 促销归因分析
- 促销趋势分析
- 促销策略建议

**数据更新频率：** 日度

---

### 4.11 AI 分析 `/ai-analytics`

| 项目 | 说明 |
|------|------|
| 对应后端 | `ai_analytics.py` |
| 对应前端 | `AIAnalytics.vue` |
| 功能描述 | AI 驱动的智能分析 |

**功能清单：**
- 智能诊断（店铺/商品/流量诊断）
- 趋势预测（基于历史数据的智能预测）
- 异常检测（自动发现数据异常）
- 根因分析（自动分析异常原因）
- 智能建议（基于分析结果的行动建议）

**数据更新频率：** 6 小时

---

### 4.12 实时数据看板 `/realtime`（预留）

| 项目 | 说明 |
|------|------|
| 对应后端 | `realtime.py` |
| 功能描述 | 实时 GMV、实时访客、实时转化 |

**功能清单：**
- 实时 GMV 大屏
- 实时访客数
- 实时转化率
- 实时订单数
- 实时预警

**数据更新频率：** 实时（WebSocket）

---

### 4.13 诊断分析 `/diagnosis`

| 项目 | 说明 |
|------|------|
| 对应后端 | `diagnosis.py` |
| 功能描述 | 全方位诊断分析 |

**功能清单：**
- 店铺健康诊断
- 商品诊断
- 流量诊断
- 转化诊断
- 利润诊断
- 综合评分与建议

**数据更新频率：** 日度

---

### 4.14 运营日历 `/operation_calendar`

| 项目 | 说明 |
|------|------|
| 对应后端 | `operation_calendar.py` |
| 数据模型 | `OperationCalendar` |
| 功能描述 | 大促日历、活动排期、任务提醒 |

**功能清单：**
- 大促日历（双 11、618、年货节等）
- 活动排期
- 任务提醒
- 活动复盘模板
- 日历视图（月/周/日）

**数据更新频率：** 按需

---

### 4.15 自定义字段 `/custom_fields`

| 项目 | 说明 |
|------|------|
| 对应后端 | `custom_fields.py` |
| 数据模型 | `ProductCustomField` |
| 功能描述 | 自定义商品属性、动态表单 |

**功能清单：**
- 自定义字段创建（文本/数字/日期/选项）
- 字段分组管理
- 批量赋值
- 字段筛选
- 字段导出

**数据更新频率：** 实时

---

### 4.16 生意参谋对接 `/sycm`

| 项目 | 说明 |
|------|------|
| 对应后端 | `sycm.py` |
| 数据模型 | `StoreDailyData` |
| 功能描述 | 生意参谋数据同步、类目排名、竞品监控 |

**功能清单：**
- 生意参谋数据同步
- 类目排名监控
- 竞品数据对比
- 行业数据参考
- 店铺经营日报

**数据更新频率：** 日度

---

### 4.17 供应链数据 `/supply`

| 项目 | 说明 |
|------|------|
| 对应后端 | `supply_api.py` |
| 数据模型 | `SupplyChainData`、`InventoryAlert` |
| 功能描述 | 供应商管理、采购订单、物流跟踪 |

**功能清单：**
- 库存状态查询
- 安全库存预警
- 缺货预测
- 供应商信息
- 采购价格跟踪
- 周转率分析

**数据更新频率：** 6 小时

---

### 4.18 目标管理 `/targets`

| 项目 | 说明 |
|------|------|
| 对应后端 | `targets.py` |
| 对应前端 | `Targets.vue` |
| 数据模型 | `ShopTarget`、`ProductTarget` |
| 功能描述 | 店铺目标与商品目标管理 |

**功能清单：**
- 店铺目标设置（GMV、访客、转化、ROI、广告预算）
- 商品目标设置
- 目标进度追踪
- 实际 vs 目标对比
- 目标调整建议

**数据更新频率：** 日度

---

### 4.19 进度分析 `/pace`

| 项目 | 说明 |
|------|------|
| 对应后端 | `pace.py` |
| 对应前端 | `Pace.vue` |
| 功能描述 | 目标完成进度分析 |

**功能清单：**
- 目标完成进度概览
- 进度趋势分析
- 预计完成时间预测
- 进度偏差预警
- 进度排名

**数据更新频率：** 日度

---

### 4.20 效率分析 `/efficiency`

| 项目 | 说明 |
|------|------|
| 对应后端 | `efficiency.py` |
| 对应前端 | `Efficiency.vue` |
| 数据模型 | `UserKPI`、`UserDailyPerformance` |
| 功能描述 | 团队人效分析 |

**功能清单：**
- 团队绩效概览
- 个人绩效排行
- 任务完成效率
- 运营动作效率
- 时间投入产出比
- 绩效评级

**数据更新频率：** 日度

---

### 4.21 事件管理 `/events`

| 项目 | 说明 |
|------|------|
| 对应后端 | `events.py` |
| 功能描述 | 大促事件、营销活动、里程碑管理 |

**功能清单：**
- 大促事件创建
- 活动里程碑
- 事件时间线
- 事件效果评估
- 历史事件回顾

**数据更新频率：** 按需

---

### 4.22 KPI 管理 `/kpi`

| 项目 | 说明 |
|------|------|
| 对应后端 | `kpi.py` |
| 对应前端 | `KPI.vue` |
| 数据模型 | `UserKPI` |
| 功能描述 | 关键绩效指标管理 |

**功能清单：**
- KPI 指标定义
- KPI 进度追踪
- KPI 预警
- 绩效考核
- KPI 报表

**数据更新频率：** 日度

---

### 4.23 促销活动 `/promotion`

| 项目 | 说明 |
|------|------|
| 对应后端 | `promotion.py` |
| 对应前端 | `Promotion.vue` |
| 功能描述 | 促销活动管理 |

**功能清单：**
- 促销活动创建
- 活动效果监控
- 活动对比
- 活动报表
- 活动建议

**数据更新频率：** 实时

---

### 4.24 四象限分析 `/quadrant`

| 项目 | 说明 |
|------|------|
| 对应后端 | `dashboard_api.py` (quadrant endpoint) |
| 对应前端 | `Quadrant.vue` |
| 功能描述 | GMV-ROI 四象限分析 |

**功能清单：**
- GMV-ROI 四象限分布
- 商品象限定位
- 象限切换策略
- 象限趋势分析

**数据更新频率：** 日度

---

### 4.25 流量分析 `/traffic-analysis`

| 项目 | 说明 |
|------|------|
| 对应后端 | `traffic.py` |
| 对应前端 | `TrafficAnalysis.vue` |
| 数据模型 | `TrafficSource`、`ProductTrafficDetail`、`TrafficStructure` |
| 功能描述 | 流量来源分析、关键词分析 |

**功能清单：**
- 流量来源概览
- 关键词分析（搜索量/竞争度/机会分）
- 流量结构分析
- 流量趋势
- 关键词机会识别

**数据更新频率：** 日度

---

### 4.26 趋势分析 `/trends`

| 项目 | 说明 |
|------|------|
| 对应后端 | `trends.py` |
| 对应前端 | `Trends.vue` |
| 功能描述 | 多维度趋势分析 |

**功能清单：**
- GMV 趋势
- 访客趋势
- 转化趋势
- ROI 趋势
- 自定义指标趋势
- 多指标叠加对比

**数据更新频率：** 日度

---

### 4.27 退款分析 `/refunds`

| 项目 | 说明 |
|------|------|
| 对应后端 | `refunds.py` |
| 对应前端 | `Refunds.vue` |
| 数据模型 | `Refund` |
| 功能描述 | 退款数据深度分析 |

**功能清单：**
- 退款概览（退款金额、退款率、退款笔数）
- 退款趋势分析
- 退款原因分析
- 退款商品排行
- 退款预警

**数据更新频率：** 日度

---

### 4.28 报表中心 `/report`

| 项目 | 说明 |
|------|------|
| 对应后端 | `reports.py`、`reports_api.py` |
| 对应前端 | `Report.vue` |
| 功能描述 | 自动化报表生成与下载 |

**功能清单：**
- 日报/周报/月报自动生成
- 自定义报表模板
- 报表下载（PDF/Excel/CSV）
- 报表订阅与推送
- 报表历史

**数据更新频率：** 定时（日/周/月）

---

### 4.29 运营动作 `/operations`

| 项目 | 说明 |
|------|------|
| 对应后端 | `operations.py` |
| 对应前端 | `Operations.vue` |
| 数据模型 | `OperationAction`、`OperationLog` |
| 功能描述 | 运营动作记录与分析 |

**功能清单：**
- 运营动作记录（标题优化、主图优化、价格调整等）
- 动作效果分析
- 动作趋势
- 动作建议

**数据更新频率：** 实时

---

### 4.30 商品排行 `/product-ranking`

| 项目 | 说明 |
|------|------|
| 对应前端 | `ProductRanking.vue` |
| 数据模型 | `ProductRanking` |
| 功能描述 | 商品排行榜 |

**功能清单：**
- 销量排行
- GMV 排行
- 访客排行
- 转化排行
- ROI 排行
- 排行趋势

**数据更新频率：** 日度

---

### 4.31 推荐系统 `/recommendation`

| 项目 | 说明 |
|------|------|
| 对应后端 | `recommendation.py` |
| 对应前端 | `Recommendation.vue` |
| 功能描述 | 智能推荐 |

**功能清单：**
- 关联销售推荐
- 价格优化推荐
- 关键词推荐
- 内容素材推荐
- 投放策略推荐

**数据更新频率：** 6 小时

---

## 五、非功能性需求

### 5.1 性能要求

| 指标 | 要求 |
|------|------|
| 页面加载时间 | < 3 秒 |
| API 响应时间 | < 500ms（P95） |
| 并发用户数 | 支持 100+ 并发 |
| 数据刷新频率 | 见各模块定义 |

### 5.2 数据更新策略

| 数据类型 | 更新频率 | 实现方式 |
|---------|---------|---------|
| 实时数据 | 5 分钟 | 轮询（预留 WebSocket） |
| 日度数据 | 每日 06:00 | APScheduler 定时任务 |
| 周度数据 | 每周一 08:00 | APScheduler 定时任务 |
| 月度数据 | 每月 1 日 09:00 | APScheduler 定时任务 |

### 5.3 缓存策略

| 缓存层 | 用途 | 过期时间 |
|--------|------|---------|
| 查询缓存 | API 响应缓存 | 5-30 分钟 |
| 浏览器缓存 | 静态资源 | 1 年 |

### 5.4 错误处理规范

| 场景 | 前端处理 | 后端处理 |
|------|---------|---------|
| API 超时 | 显示"加载中..." + 重试按钮 | 设置 30s 超时 |
| 数据为空 | 显示空状态插画 | 返回空数组/对象 |
| 网络错误 | Toast 提示 + 降级展示 | 记录日志 |
| 接口异常 | 显示错误信息 | 返回标准错误格式 |

### 5.5 安全要求

- API 访问限流
- 数据加密存储
- 操作日志审计

### 5.6 可用性要求

- 系统可用性 >= 99.9%
- 数据备份（每日自动备份）
- 故障恢复时间 < 30 分钟

---

## 六、技术架构

### 6.1 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | 3.x | 核心框架 |
| Vite | 5.x | 构建工具 |
| Element Plus | 2.x | UI 组件库 |
| ECharts | 5.x | 数据可视化 |
| Pinia | 2.x | 状态管理 |
| Vue Router | 4.x | 路由管理 |
| Axios | 1.x | HTTP 请求 |
| NProgress | - | 页面加载进度条 |

### 6.2 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.x | Web 框架 |
| SQLAlchemy | 2.x | ORM |
| SQLite | - | 数据库 |
| Pydantic | 2.x | 数据验证 |
| APScheduler | - | 定时任务 |
| Uvicorn | - | ASGI 服务器 |

### 6.3 前端路由规划（完整版）

| 路由 | 组件 | 菜单分组 |
|------|------|---------|
| `/` | CommandTower | 指挥塔 |
| `/products` | Products | 商品运营 |
| `/product/:id` | ProductDetail | 商品运营 |
| `/product-ranking` | ProductRanking | 商品运营 |
| `/lifecycle` | Lifecycle | 商品运营 |
| `/profit` | Profit | 商品运营 |
| `/quadrant` | Quadrant | 商品运营 |
| `/traffic-analysis` | TrafficAnalysis | 数据分析 |
| `/ads` | Ads | 数据分析 |
| `/kpi` | KPI | 数据分析 |
| `/trends` | Trends | 数据分析 |
| `/funnel` | Funnel | 数据分析 |
| `/compare` | Compare | 数据分析 |
| `/prediction` | Prediction | 数据分析 |
| `/operations` | Operations | 运营管理 |
| `/targets` | Targets | 运营管理 |
| `/promotion` | Promotion | 运营管理 |
| `/alerts` | Alerts | 运营管理 |
| `/health` | Health | 运营管理 |
| `/import-center` | ImportCenter | 数据中心 |
| `/smart-import` | SmartImport | 数据中心 |
| `/advanced-import-center` | AdvancedImportCenter | 数据中心 |
| `/report` | Report | 数据中心 |
| `/backup` | Backup | 数据中心 |
| `/backup-management` | BackupManagement | 数据中心 |
| `/data-quality` | DataQuality | 数据中心 |
| `/settings` | Settings | 系统设置 |

### 6.4 部署架构

```
┌─────────────────────────────────────────────────────┐
│                    Nginx / CDN                      │
├─────────────────────────────────────────────────────┤
│              Vue 3 前端（静态资源）                    │
├─────────────────────────────────────────────────────┤
│              FastAPI 后端服务                          │
├─────────────────────────────────────────────────────┤
│              SQLite 数据库                             │
├─────────────────────────────────────────────────────┤
│              APScheduler 定时任务                      │
└─────────────────────────────────────────────────────┘
```

---

## 七、数据字典

### 7.1 核心数据表

#### Product（商品表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| product_id | String | 商品 ID（唯一） |
| title | String | 商品标题 |
| category | String | 类目 |
| tier | String | 分层（A/B/C/D） |
| style | String | 风格 |
| scene | String | 场景 |
| list_date | String | 上架日期 |
| status | String | 状态（active/inactive） |
| image_url | String | 商品图片 |
| manager | String | 负责人 |
| starred | Boolean | 是否收藏 |

#### DailyData（日度数据表）

| 字段 | 类型 | 说明 |
|------|------|------|
| product_id | String | 商品 ID |
| date | String | 日期（YYYY-MM-DD） |
| payment_amount | Float | 支付金额 |
| refund_amount | Float | 退款金额 |
| ipv | Integer | 访客数 |
| pv | Integer | 浏览量 |
| search_ipv | Integer | 搜索访客 |
| paid_ipv | Integer | 付费访客 |
| organic_ipv | Integer | 免费访客 |
| payment_conversion | Float | 支付转化率 |
| ad_spend | Float | 广告花费 |
| ad_roi | Float | 广告 ROI |
| avg_order_value | Float | 客单价 |

#### WeeklyData（周度数据表）

| 字段 | 类型 | 说明 |
|------|------|------|
| product_id | String | 商品 ID |
| week_start | String | 周起始日期 |
| payment_amount | Float | 支付金额 |
| ipv | Integer | 访客数 |
| payment_conversion | Float | 支付转化率 |
| ad_spend | Float | 广告花费 |
| ad_roi | Float | 广告 ROI |
| repurchase_rate | Float | 复购率 |
| avg_order_value | Float | 客单价 |

#### MonthlyData（月度数据表）

| 字段 | 类型 | 说明 |
|------|------|------|
| product_id | String | 商品 ID |
| month | String | 月份（YYYY-MM） |
| payment_amount | Float | 支付金额 |
| refund_amount | Float | 退款金额 |
| visitors | Integer | 访客数 |
| payment_conversion | Float | 支付转化率 |
| refund_rate | Float | 退款率 |
| ad_spend | Float | 广告花费 |
| ad_roi | Float | 广告 ROI |
| keyword_spend/sales/roi | Float | 直通车花费/销售额/ROI |
| crowd_spend/sales/roi | Float | 人群推广花费/销售额/ROI |
| score | Integer | 商品综合评分（0-100） |

#### ShopTarget（店铺目标表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| period | String | 周期（YYYY-MM） |
| target_gsv | Float | 目标 GMV |
| target_visitors | Integer | 目标访客数 |
| target_conversion | Float | 目标转化率 |
| target_ad_ratio | Float | 目标广告占比 |
| target_ad_spend | Float | 目标广告花费 |

#### Alert（告警表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| title | String | 告警标题 |
| detail | Text | 告警详情 |
| metric | String | 触发指标 |
| current_value | Float | 当前值 |
| threshold_value | Float | 阈值 |
| level | String | 告警级别（info/warning/critical） |
| status | String | 状态（pending/resolved/dismissed） |

#### OperationAction（运营动作表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| product_id | String | 商品 ID |
| action_type | String | 动作类型（title/image/price/sku/detail/promotion/ad/other） |
| action_date | String | 动作日期 |
| action_detail | Text | 动作详情 |
| created_at | DateTime | 创建时间 |

#### ProductHealth（商品健康度表）

| 字段 | 类型 | 说明 |
|------|------|------|
| product_id | String | 商品 ID |
| date | String | 日期 |
| total_score | Float | 综合评分（0-100） |
| grade | String | 健康等级（excellent/good/fair/poor） |

#### DMPAudience（人群资产表）

| 字段 | 类型 | 说明 |
|------|------|------|
| date | String | 日期 |
| audience_type | String | 人群类型（A/I/P/L） |
| audience_count | Integer | 人群数量 |
| audience_ratio | Float | 人群占比 |
| change_count | Integer | 变化数量 |
| change_ratio | Float | 变化比例 |

#### AIPLStats（AIPL 统计表）

| 字段 | 类型 | 说明 |
|------|------|------|
| date | String | 日期 |
| a_count | Integer | 认知人群数 |
| i_count | Integer | 兴趣人群数 |
| p_count | Integer | 购买人群数 |
| l_count | Integer | 忠诚人群数 |
| a_to_i | Float | A→I 转化率 |
| i_to_p | Float | I→P 转化率 |
| p_to_l | Float | P→L 转化率 |

#### WxtCampaign（万相台投放计划表）

| 字段 | 类型 | 说明 |
|------|------|------|
| campaign_name | String | 计划名称 |
| campaign_type | String | 计划类型 |
| budget | Float | 预算 |
| actual_spend | Float | 实际花费 |
| target_roi | Float | 目标 ROI |
| manager | String | 负责人 |

#### ABTest（A/B 测试表）

| 字段 | 类型 | 说明 |
|------|------|------|
| test_name | String | 实验名称 |
| test_type | String | 实验类型（creative/title/crowd/bid/price） |
| start_date / end_date | String | 起止日期 |
| status | String | 状态（draft/running/finished） |
| significance_level | Float | 显著性水平（默认 0.95） |

#### UserKPI（用户 KPI 表）

| 字段 | 类型 | 说明 |
|------|------|------|
| username | String | 用户名 |
| period | String | 周期（YYYY-MM） |
| target_gmv / actual_gmv | Float | 目标/实际 GMV |
| target_roi / actual_roi | Float | 目标/实际 ROI |
| gmv_progress / roi_progress | Float | 进度百分比 |
| performance_rating | String | 绩效评级 |

### 7.2 数据关系图

```
Product ──┬── DailyData (1:N)
          ├── WeeklyData (1:N)
          ├── MonthlyData (1:N)
          ├── ProductHealth (1:N)
          ├── OperationAction (1:N)
          ├── ProductTag (1:N)
          └── ProductNote (1:N)

ShopTarget ── Period (1:1)

WxtCampaign ──┬── WxtDailyMetrics (1:N)
              ├── DmpCampaignLink (1:N)
              └── CampaignProject (via used_sop_id)

DmpCrowd ─┬── DmpCampaignLink (1:N)
           └── CrowdAssetStats (1:N)

ABTest ──┬── ABTestVariant (1:N)
         ├── ABTestMetrics (1:N)
         └── ABTestAnalysis (1:1)

User ──┬── UserKPI (1:N)
       └── UserDailyPerformance (1:N)
```

---

## 八、接口规范

### 8.1 统一响应格式

**成功响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "key": "value"
  }
}
```

**错误响应：**
```json
{
  "code": 500,
  "message": "错误描述",
  "detail": "详细错误信息"
}
```

### 8.2 核心 API 清单

| 模块 | 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|------|
| **指挥塔** | `/api/dashboard/summary` | GET | KPI 汇总 | ✅ |
| | `/api/dashboard/trend` | GET | 趋势数据 | ✅ |
| | `/api/dashboard/top-products` | GET | 热销排行 | ✅ |
| | `/api/dashboard/quadrant` | GET | 四象限 | ✅ |
| | `/api/dashboard/alerts` | GET | 告警列表 | ✅ |
| **商品** | `/api/products` | GET | 商品列表 | ✅ |
| | `/api/products/{id}` | GET | 商品详情 | ✅ |
| | `/api/products/batch-update` | POST | 批量修改 | ✅ |
| | `/api/products/ranking` | GET | 商品排行 | ✅ |
| | `/api/export/products` | GET | 商品导出 | ✅ |
| **生命周期** | `/api/lifecycle/products` | GET | 生命周期列表 | ✅ |
| | `/api/lifecycle/{id}` | GET | 生命周期详情 | ✅ |
| **健康度** | `/api/health/score` | GET | 健康评分 | ✅ |
| | `/api/health/distribution` | GET | 等级分布 | ✅ |
| | `/api/health/warnings` | GET | 预警商品 | ✅ |
| **利润** | `/api/profit/overview` | GET | 利润概览 | ✅ |
| | `/api/profit/products` | GET | 商品利润 | ✅ |
| | `/api/profit/categories` | GET | 类目利润 | ✅ |
| **广告投放** | `/api/ads/overview` | GET | 投放概览 | ✅ |
| | `/api/ads/campaigns` | GET | 投放计划 | ✅ |
| | `/api/ads/dmp` | GET | DMP 人群 | ✅ |
| | `/api/ads/aipl` | GET | AIPL 分析 | ✅ |
| **评价分析** | `/api/reviews/summary` | GET | 评价汇总 | ✅ |
| | `/api/reviews/sentiment-distribution` | GET | 情感分布 | ✅ |
| | `/api/reviews/dimensions` | GET | 维度分析 | ✅ |
| | `/api/reviews/list` | GET | 评价列表 | ✅ |
| **市场分析** | `/api/market/overview` | GET | 市场概览 | ✅ |
| | `/api/market/keywords` | GET | 关键词分析 | ✅ |
| | `/api/market/demand` | GET | 需求分析 | ✅ |
| | `/api/market/competitors` | GET | 竞品分析 | ✅ |
| **漏斗分析** | `/api/funnel/overview` | GET | 漏斗概览 | ✅ |
| | `/api/funnel/by-source` | GET | 分渠道漏斗 | ✅ |
| **对比分析** | `/api/compare/summary` | GET | 对比汇总 | ✅ |
| | `/api/compare/trend` | GET | 趋势对比 | ✅ |
| **库存** | `/api/inventory/summary` | GET | 库存汇总 | ✅ |
| | `/api/inventory/warnings` | GET | 库存预警 | ✅ |
| **预测** | `/api/prediction/gmv` | GET | GMV 预测 | ✅ |
| | `/api/prediction/visitors` | GET | 访客预测 | ✅ |
| **目标** | `/api/targets/summary` | GET | 目标汇总 | ✅ |
| | `/api/targets/comparison` | GET | 实际 vs 目标 | ✅ |
| **告警** | `/api/alerts/rules` | GET/POST | 预警规则 | ✅ |
| | `/api/alerts/records` | GET | 预警记录 | ✅ |
| | `/api/smart-alerts/rules` | GET/POST | 智能规则 | ✅ |
| | `/api/smart-alerts/records` | GET | 智能记录 | ✅ |
| **运营动作** | `/api/operations` | GET/POST | 动作管理 | ✅ |
| **效率** | `/api/efficiency/overview` | GET | 效率概览 | ✅ |
| | `/api/efficiency/channels` | GET | 渠道效率 | ✅ |
| **导入** | `/api/imports/tasks` | GET | 导入任务 | ✅ |
| | `/api/imports/history` | GET | 导入历史 | ✅ |
| | `/api/smart-import/match` | POST | 智能匹配 | ✅ |
| **报表** | `/api/reports/list` | GET | 报表列表 | ✅ |
| | `/api/reports/generate` | POST | 生成报表 | ✅ |
| **系统** | `/api/system/settings` | GET | 系统设置 | ✅ |
| | `/api/system/health` | GET | 系统健康检查 | ✅ |

### 8.3 分页参数规范

所有列表接口统一支持分页参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | Integer | 1 | 页码 |
| page_size | Integer | 20 | 每页数量 |
| sort_by | String | - | 排序字段 |
| sort_order | String | desc | 排序方向（asc/desc） |

### 8.4 时间范围参数规范

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| period | String | 相对时间 | 7d / 30d / today / yesterday |
| start_date | String | 起始日期 | 2026-01-01 |
| end_date | String | 结束日期 | 2026-05-12 |
| dimension | String | 时间维度 | daily / weekly / monthly |

---

## 九、项目里程碑

| 阶段 | 内容 | 交付物 | 验收标准 |
|------|------|--------|---------|
| **M1** | 数据层搭建（数据接入/清洗/存储） | 数据仓库、ETL 管道 | 5+ 数据源接入成功，数据准确率 > 99% |
| **M2** | 核心看板开发（指挥塔/商品总览/商品分析/利润分析） | 4 大核心页面 | 页面加载 < 3 秒，8 大 KPI 数据准确 |
| **M3** | 进阶分析模块（评价/市场/漏斗/对比） | 4 大分析页面 | 所有图表响应式，无 JS 报错 |
| **M4** | 算法模型层（预测/评分/预警） | 5 大模型 | 预测准确率 > 80% |
| **M5** | 服务层完善（报表自动化/API 输出） | 自动化报表系统 | 报表生成成功率 > 95% |
| **M6** | 系统集成与优化（性能/安全/部署） | 生产环境部署 | 可用性 >= 99.9% |

---

## 十、成功标准

| 指标 | 目标值 |
|------|--------|
| 数据覆盖度 | 接入 >= 5 个数据源 |
| 报表自动化率 | >= 80% 报表自动生成 |
| 决策效率提升 | 数据获取时间缩短 70% |
| 用户满意度 | NPS >= 50 |
| 系统稳定性 | 可用性 >= 99.9% |
| API 响应速度 | P95 < 500ms |
| 预测准确率 | > 80% |

---

## 附录 A：需求来源对照表

| 需求编号 | 模块 | 对应来源 | 前端路由 | 后端 API | 状态 |
|---------|------|---------|---------|---------|------|
| 001 | 运营指挥塔 | 原始 PRD v2.0 | `/` | dashboard_api.py | ✅ |
| 002 | 商品总览 | 玺承教育演示 | `/dashboard` | 待开发 | 待开发 |
| 003 | 商品分析 | 原始 PRD v2.0 | `/products` | products.py | ✅ |
| 004 | 商品排行 | 原始 PRD v2.0 | `/product-ranking` | products_api.py | ✅ |
| 005 | 生命周期 | 玺承教育演示 | `/lifecycle` | lifecycle.py | ✅ |
| 006 | 商品健康度 | 原始 PRD v2.0 | `/health` | health.py | ✅ |
| 007 | 利润分析 | 原始 PRD v2.0 | `/profit` | profit.py | ✅ |
| 008 | 广告投放 | 原始 PRD v2.0 | `/ads` | ads.py | ✅ |
| 009 | 评价分析 | 原始 PRD v2.0 | `/reviews` | reviews.py | ✅ |
| 010 | 市场分析 | 原始 PRD v2.0 | `/market` | market.py | ✅ |
| 011 | 漏斗分析 | 原始 PRD v2.0 | `/funnel` | funnel.py | ✅ |
| 012 | 对比分析 | 原始 PRD v2.0 | `/compare` | compare.py | ✅ |
| 013 | 库存分析 | 原始 PRD v2.0 | `/inventory` | inventory.py | ✅ |
| 014 | 预测分析 | 原始 PRD v2.0 | `/prediction` | prediction.py | ✅ |
| 015 | 导入中心 | 原始 PRD v2.0 | `/import-center` | imports.py | ✅ |
| 016 | 智能预警 | 原始 PRD v2.0 | `/alerts` + `/smart-alert` | alerts.py + smart_alert.py | ✅ |
| 017 | 工具箱 | 原始 PRD v2.0 | `/toolbox` | toolbox.py | ✅ |
| 018 | 人群资产 | 补充需求 | `/crowd-asset` | crowd_asset.py | ✅ |
| 019 | 归因分析 | 补充需求 | `/attribution` | attribution.py | ✅ |
| 020 | A/B 测试 | 补充需求 | `/abtest-sop` | abtest_sop.py | ✅ |
| 021 | 数据质量 | 补充需求 | `/data-quality` | data_quality.py | ✅ |
| 022 | 智能导入 | 补充需求 | `/smart-import` | smart_import.py | ✅ |
| 023 | 备份管理 | 补充需求 | `/backup` + `/backup-management` | backup.py | ✅ |
| 024 | AI 分析 | 补充需求 | `/ai-analytics` | ai_analytics.py | ✅ |
| 025 | 运营日历 | 补充需求 | - | operation_calendar.py | ✅ |
| 026 | 自定义字段 | 补充需求 | - | custom_fields.py | ✅ |
| 027 | 生意参谋 | 补充需求 | - | sycm.py | ✅ |
| 028 | 供应链 | 补充需求 | - | supply_api.py | ✅ |
| 029 | 目标管理 | 补充需求 | `/targets` | targets.py | ✅ |
| 030 | 进度分析 | 补充需求 | `/pace` | pace.py | ✅ |
| 031 | 效率分析 | 补充需求 | `/efficiency` | efficiency.py | ✅ |
| 032 | 促销活动 | 补充需求 | `/promotion` | promotion.py | ✅ |
| 033 | 四象限 | 补充需求 | `/quadrant` | dashboard_api.py | ✅ |
| 034 | 流量分析 | 补充需求 | `/traffic-analysis` | traffic.py | ✅ |
| 035 | 趋势分析 | 补充需求 | `/trends` | trends.py | ✅ |
| 036 | 退款分析 | 补充需求 | `/refunds` | refunds.py | ✅ |
| 037 | 报表中心 | 补充需求 | `/report` | reports.py | ✅ |
| 038 | 运营动作 | 补充需求 | `/operations` | operations.py | ✅ |
| 039 | 推荐系统 | 补充需求 | `/recommendation` | recommendation.py | ✅ |
| 040 | 协同工作 | 补充需求 | `/collaboration` | collaboration.py | ✅ |
| 041 | KPI 管理 | 补充需求 | `/kpi` | kpi.py | ✅ |
| 042 | 系统设置 | 补充需求 | `/settings` | settings.py | ✅ |
| 043 | 渠道详情 | 补充需求 | `/channel-detail` | - | 前端已有 |
| 044 | 数据可视化 | 补充需求 | `/data-visualization` | - | 前端已有 |
| 045 | 促销分析 | 补充需求 | `/promotion-analysis` | - | 前端已有 |
| 046 | 事件管理 | 补充需求 | - | events.py | ✅ |
| 047 | 实时数据 | 补充需求 | - | realtime.py | ✅ |
| 048 | 诊断分析 | 补充需求 | - | diagnosis.py | ✅ |
| 049 | 上传管理 | 补充需求 | - | upload.py | ✅ |
| 050 | 系统管理 | 补充需求 | - | system.py | ✅ |

---

*本文档由 PRD 分析 + 代码逆向工程 + 现场演示截图综合生成，覆盖全部 50 个功能模块。*
