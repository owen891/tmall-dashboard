# 天猫数据仪表盘 — 产品需求文档 (PRD)

> **版本**: v2.0
> **更新日期**: 2026-05-01
> **技术栈**: Python Flask + SQLite + ECharts + 原生 JavaScript

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 技术架构](#2-技术架构)
- [3. 功能需求](#3-功能需求)
  - [3.1 总览](#31-总览)
  - [3.2 商品运营](#32-商品运营)
  - [3.3 健康度](#33-健康度)
  - [3.4 评价分析](#34-评价分析)
  - [3.5 市场分析](#35-市场分析)
  - [3.6 生命周期](#36-生命周期)
  - [3.7 周期对比](#37-周期对比)
  - [3.8 工具箱](#38-工具箱)
- [4. 数据模型](#4-数据模型)
- [5. API 接口](#5-api-接口)
- [6. 数据导入](#6-数据导入)
- [7. 非功能需求](#7-非功能需求)
- [8. 配置项](#8-配置项)

---

## 1. 项目概述

### 1.1 产品定位

天猫数据仪表盘是一款面向天猫店铺运营团队的全链路数据分析工具，整合生意参谋、付费推广、市场分析、评价数据等多源信息，提供商品运营全生命周期的数据洞察与决策支持。

### 1.2 核心价值

| 价值维度 | 说明 |
|---------|------|
| **数据整合** | 将生意参谋、付费报表、市场数据、评价数据统一到一个平台 |
| **多维分析** | 支持日/周/月三个时间维度，覆盖销售、流量、推广、售后等全链路 |
| **智能预警** | 自动检测异常指标，退款率/健康度/环比变化等多维度预警 |
| **运营赋能** | 运营动作记录与效果回算，商品分层管理，标签体系 |
| **市场洞察** | 关键词分析、需求维度拆解、蓝海机会词发现 |

### 1.3 用户角色

| 角色 | 使用场景 |
|------|---------|
| 店铺运营 | 日常数据监控、商品管理、运营动作记录 |
| 数据分析师 | 深度趋势分析、周期对比、市场研究 |
| 店铺负责人 | KPI总览、目标进度跟踪、报告生成 |

---

## 2. 技术架构

### 2.1 系统架构

```
┌─────────────────────────────────────────────────┐
│                   前端 (Browser)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ dashboard │ │  ECharts │ │ bundle.min.js    │  │
│  │  .html    │ │  5.5.0   │ │ (14 modules)     │  │
│  │  + CSS    │ │          │ │                  │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────┤
│                 Flask Web Server                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  app.py  │ │data_api  │ │  tool_api        │  │
│  │ (路由)    │ │(数据接口) │ │  (工具接口)      │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────┤
│                 数据层                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  db.py   │ │ SQLite   │ │ config.yaml      │  │
│  │(迁移+连接)│ │(20张表)  │ │ (配置)           │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 2.2 前端架构

| 模块 | 文件 | 职责 |
|------|------|------|
| 入口 | `dashboard.html` | 页面结构、侧边栏、顶部栏 |
| 样式 | `dashboard.css` | 暗色/亮色主题、响应式布局 |
| 工具函数 | `utils.js` | API调用、Tab切换、维度切换、通用工具 |
| KPI | `kpi.js` | KPI卡片渲染、环比计算、异常检测 |
| 趋势 | `trend.js` | 销售趋势图、事件标注 |
| 商品 | `products.js` | 商品表格、搜索筛选、分页排序 |
| 推广 | `ad.js` | 推广效果图表 |
| 退款 | `refund.js` | 退款趋势与预警 |
| 运营动作 | `actions.js` | 动作CRUD、效果统计 |
| 目标 | `target.js` | 店铺目标进度 |
| 健康度 | `health.js` | 健康等级分布、预警列表 |
| 评价 | `review.js` | 评价上传、统计、分析图表 |
| 市场 | `market.js` | 市场分析图表、关键词表格 |
| 生命周期 | `lifecycle.js` | 商品月度趋势缩略图 |
| 对比 | `compare.js` | 周期对比、多周期叠加 |
| 工具箱 | `toolbox.js` | 定时任务、工具执行 |

### 2.3 UI 设计规范

| 属性 | 暗色主题 | 亮色主题 |
|------|---------|---------|
| 背景色 | `#0B0F19` | `#F8FAFC` |
| 卡片背景 | `#111827` | `#FFFFFF` |
| 主色调 | `#06B6D4` (青色) | `#0891B2` |
| 成功色 | `#10B981` (绿色) | `#059669` |
| 警告色 | `#F59E0B` (琥珀) | `#D97706` |
| 危险色 | `#EF4444` (红色) | `#DC2626` |
| 字体 | DM Sans + JetBrains Mono | 同左 |
| 侧边栏宽度 | 200px (展开) / 60px (折叠) | 同左 |
| 顶栏高度 | 56px | 同左 |

---

## 3. 功能需求

### 3.1 总览

总览Tab是仪表盘的首页，提供店铺核心经营指标的快速概览。

#### 3.1.1 KPI 卡片

| 指标 | 数据来源 | 格式 |
|------|---------|------|
| 总GMV | `monthly_data.payment_amount` 汇总 | ¥金额 |
| 净销售额 | `monthly_data.net_sales` 汇总 | ¥金额 |
| 总访客 | `monthly_data.visitors` 汇总 | 数字 |
| 整体转化率 | 净销售额/GMV 计算或 `payment_conversion` | 百分比 |
| 推广花费 | `monthly_data.ad_spend` 汇总 | ¥金额 |
| 综合ROI | `monthly_data.overall_roi` 加权平均 | 数值 |
| 退款率 | `monthly_data.refund_rate` 加权平均 | 百分比 |
| 客单价 | `monthly_data.avg_order_value` 加权平均 | ¥金额 |

**交互功能：**
- 支持自定义排序（拖拽或配置）
- 支持显示/隐藏指定指标
- 环比变化显示（上升绿色↑ / 下降红色↓）
- 退款率特殊处理：下降为绿色（好事），上升为红色（坏事）
- 环比变化超过20%自动标红背景预警
- 点击KPI卡片可下钻到对应详细分析

#### 3.1.2 目标完成进度

- GSV进度仪表盘（实际/目标）
- 费用预算进度条
- 实际费比 vs 目标费比对比
- 时间进度条（已过天数/总天数）
- 智能预测：基于当前日均数据预测月末GSV

#### 3.1.3 预警通知面板

- 展示当前周期的自动预警信息
- 支持忽略/关闭单条预警
- 预警级别：danger（红色）/ warning（橙色）/ info（蓝色）

#### 3.1.4 销售趋势图

- 支持日/周/月维度切换
- 支持自定义起止日期筛选
- 多指标叠加（GMV + 净销售额）
- **事件标注**：支持在图表上添加/删除事件标记（如"双11大促"、"换主图"）

#### 3.1.5 流量与转化分析

- UV趋势折线图
- 转化率趋势折线图

#### 3.1.6 新老客分析

- 新客/老客统计卡片（买家数、占比、客单价）
- 近6期新老客趋势图

#### 3.1.7 加购→支付漏斗

- 转化漏斗图：访客 → 浏览 → 加购 → 收藏 → 下单 → 支付
- 每步转化率标注

#### 3.1.8 预警规则管理

- 支持添加自定义预警规则（指标 + 操作符 + 阈值 + 级别）
- 支持删除规则
- 自动检测规则触发情况

#### 3.1.9 一键报告

- 生成数据报告文本，包含KPI概览、趋势分析、异常指标
- 支持一键复制到剪贴板

---

### 3.2 商品运营

#### 3.2.1 商品分析表格

**数据列（三组视图）：**

| 基础信息 | 选款指标 | 成交与付费 |
|---------|---------|-----------|
| 商品图片 | UV价值 | 支付金额 |
| 商品标题 | 搜索占比 | 净销售额 |
| 商品ID | 加购率 | 支付件数 |
| 分层 | 收藏率 | 访客数 |
| 风格 | 跳失率 | 支付转化率 |
| 场景 | 平均停留时长 | 推广花费 |
| 负责人 | 综合评分 | 推广ROI |
| 状态 | 健康评分 | 退款金额 |
| 备注 | 月度环比变化 | 退款率 |
| 星标 | | 客单价 |
| 标签 | | 买家数 |

**交互功能：**
- 搜索：按商品名称或ID模糊搜索
- 筛选：按分层、风格、状态、星标筛选
- 排序：点击列头排序（支持多字段）
- 分页：服务端分页，每页20/50/100条
- 行内编辑：双击 tier/style/scene/manager/remark 可快速编辑
- 批量操作：批量收藏、批量改分层/风格、批量打标签
- 列配置：自定义显示列 + 模板保存/加载
- 导出：导出当前筛选结果为Excel
- 商品详情弹窗：点击商品查看完整信息

#### 3.2.2 推广分析

- 花费 vs ROI 气泡图（X轴花费，Y轴ROI，气泡大小GMV）
- 推广方式花费对比柱状图（关键词/人群/全站）

#### 3.2.3 退款售后

- 退款金额趋势折线图
- 退款率趋势折线图
- 高退款率商品预警列表（超过阈值标红）

#### 3.2.4 运营动作管理

**动作类型：** 加价、减价、换图、换标题、加SKU、其他

**记录字段：**
- 动作日期、动作类型、动作详情
- 动作前/后指标（支付金额、访客、转化率、ROI）
- 自动计算变化率和效果评分
- 导入数据后自动回算效果（查找下一周期数据对比）

#### 3.2.5 操作日志

- 展示最近的操作记录（导入、编辑、删除等）
- 按时间倒序排列

---

### 3.3 健康度

#### 3.3.1 健康评分算法

基于12维度加权百分位评分，每个维度满分100分：

| 维度 | 权重 | 数据来源 |
|------|------|---------|
| GSV环比变化 | 0.15 | `monthly_data.payment_amount` 环比 |
| 总推广花费环比 | 0.08 | `monthly_data.ad_spend` 环比 |
| 直接ROI环比 | 0.10 | `monthly_data.ad_roi` 环比 |
| 退款率 | 0.10 | `monthly_data.refund_rate` |
| 加购率 | 0.08 | `monthly_data.cart_rate` |
| 引潜比 | 0.07 | `monthly_data.search_ratio` |
| 拉新成本 | 0.07 | 计算值 |
| 直接加购成本 | 0.05 | `paid_detail` 计算 |
| 总加购成本 | 0.05 | `paid_detail` 计算 |
| 复购率 | 0.08 | `monthly_data.repurchase_rate` |
| 连带率 | 0.07 | `monthly_data.cross_sell_rate` |
| 搜索点击率vs行业 | 0.10 | `monthly_data` 对比 `industry_ctr` |

#### 3.3.2 健康等级

| 等级 | 分数范围 | 颜色 |
|------|---------|------|
| 优秀 | ≥ 80 | 绿色 |
| 良好 | 60 ~ 79 | 蓝色 |
| 关注 | 40 ~ 59 | 橙色 |
| 预警 | < 40 | 红色 |

#### 3.3.3 健康度界面

- 健康等级分布饼图（优秀/良好/关注/预警）
- 预警商品列表（展示健康评分及预警维度）
- 点击商品查看12维度详细评分雷达图

---

### 3.4 评价分析

#### 3.4.1 评价数据上传

- 支持拖拽上传 Excel (.xlsx/.xls) 和 CSV 文件
- 自动检测列名映射（评价内容、商品ID、评分、日期等）
- 后台异步导入，实时进度条

#### 3.4.2 自动分析能力

**情感分析（基于情感词典，无需外部API）：**
- 正面/中性/负面 自动分类
- 物流相关/品质相关 细分识别

**维度提取（8大维度）：**
外观颜值、容量收纳、材质品质、性价比、尺寸合适、安装方便、颜色准确、物流服务

**场景提取（20+场景）：**
玄关、客厅、卧室、厨房、卫生间、阳台、办公室、餐厅、书房、儿童房等

#### 3.4.3 统计卡片

总评价数、好评率、差评率、平均评分、带图评价数、有效评价率

#### 3.4.4 分析图表

| 图表 | 类型 | 说明 |
|------|------|------|
| 情感分布 | 饼图 | 正面/中性/负面比例 |
| 评分分布 | 柱状图 | 1~5星分布 |
| 好评维度 | 条形图 | 各正面维度频次 |
| 差评维度 | 条形图 | 各负面维度频次 |
| 高频词TOP20 | 词云 | 评价高频关键词 |
| 使用场景 | 标签云 | 用户使用场景分布 |

#### 3.4.5 评价列表

- 按商品筛选、按情感筛选
- 分页展示
- 支持导出为Excel

---

### 3.5 市场分析

#### 3.5.1 数据上传

需同时上传3个文件：
1. 30天搜索数据 Excel
2. 7天搜索数据 Excel
3. 趋势分析数据 Excel

#### 3.5.2 概览卡片

总关键词数、上升关键词数、下降关键词数、主要需求维度

#### 3.5.3 关键词洞察

- 搜索人气分布直方图
- 点击率分布直方图
- 支付转化率分布直方图
- 价格分布直方图
- 关键词数据表格（支持排序）

#### 3.5.4 需求分析

- 8大需求维度分布饼图：品类需求、适用场景需求、风格需求、属性需求、定制需求、人群需求、功能属性需求、品牌需求
- 维度详情列表

#### 3.5.5 行业榜单

| 榜单 | 排序逻辑 |
|------|---------|
| 增长潜力榜 | 搜索人气增长率 × 转化率 |
| 综合实力榜 | 搜索人气 × 点击率 × 转化率 |
| 头部精选榜 | 搜索人气TOP关键词 |
| 稳定表现榜 | 各指标波动最小的关键词 |

#### 3.5.6 蓝海机会词

基于搜索人气、点击率、转化率的综合评分，筛选出高机会低竞争的关键词。

---

### 3.6 生命周期

#### 3.6.1 商品搜索与筛选

- 按商品名称搜索
- 按分层筛选（利润款/引流款/爆款/潜力款等）

#### 3.6.2 生命周期卡片列表

- 每个商品展示月度GSV趋势缩略图（迷你折线图）
- 卡片显示商品名称、当前分层、最新月GMV

#### 3.6.3 商品详情

- 点击卡片展开完整月度趋势图
- 关键指标网格：最新月GMV、环比变化、峰值月份、谷值月份

---

### 3.7 周期对比

#### 3.7.1 双周期对比

- 选择任意两个周期（A vs B）
- KPI对比表格（GMV、访客、转化率、退款率等）
- 商品排名变化表（上升/下降/新进/退出）
- 趋势对比折线图

#### 3.7.2 多周期趋势叠加

- 选择多个周期
- 叠加展示 GMV / 访客 / 转化率 / 退款率 趋势
- 不同周期用不同颜色区分

---

### 3.8 工具箱

#### 3.8.1 定时任务管理

| 功能 | 说明 |
|------|------|
| 添加任务 | 设置任务名称、执行频率（每天/每周/每月）、执行时间、文件匹配模式 |
| 查看任务 | 列表展示所有定时任务及其状态 |
| 手动执行 | 立即触发一次任务执行 |
| 启用/禁用 | 切换任务状态 |

#### 3.8.2 工具列表

| 工具 | 状态 | 说明 |
|------|------|------|
| 数据导入 | ✅ 可用 | 上传生意参谋/付费报表/DMP等Excel数据文件 |
| 评价生成主图建议 | ✅ 可用 | 分析好评数据提取核心卖点，生成主图优化建议 |
| 评价仿写助手 | ✅ 可用 | 根据评价内容自动生成专业回复模板（3种风格×3个版本） |
| 商品详情页诊断 | ✅ 可用 | 综合分析商品数据，诊断详情页各维度优化机会 |
| 评价生成主图 | 🔜 即将推出 | 基于竞品评价洞察生成5张产品主图 |
| 爆款详情页复刻 | 🔜 即将推出 | 学习竞品详情页生成超越竞品的详情页 |
| 详情页优化对比 | 🔜 即将推出 | 原版vs AI优化版详情页左右对比 |
| 评价仿写 | 🔜 即将推出 | 竞品评价1:1仿写生成高质量评价 |
| 获取商品评价 | 🔜 即将推出 | 通过API获取商品评价数据 |
| 获取商品属性 | 🔜 即将推出 | 通过API获取商品销售属性 |
| 获取商品详情页 | 🔜 即将推出 | 通过API获取商品详情和图片 |

---

## 4. 数据模型

### 4.1 ER 关系概览

```
products (商品主表)
  ├── daily_data (日度数据)      1:N
  ├── weekly_data (周度数据)     1:N
  ├── monthly_data (月度数据)    1:N
  ├── paid_detail (付费推广明细)  1:N
  ├── product_health (健康度)    1:N
  ├── product_notes (商品备注)   1:N
  ├── product_tags (商品标签)    1:N
  ├── product_targets (商品目标)  1:N
  ├── reviews (评价数据)         1:N
  ├── review_summary (评价汇总)  1:N
  └── operation_actions (运营动作) 1:N

shop_targets (店铺目标)          独立表
alerts (预警)                    独立表
alert_rules (预警规则)           独立表
market_analysis (市场分析)       独立表
market_keyword_opportunities     独立表
chart_events (图表事件标注)      独立表
scheduled_tasks (定时任务)       独立表
operation_logs (操作日志)        独立表
```

### 4.2 核心表结构

#### products — 商品主表

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| product_id | TEXT UNIQUE | 商品ID |
| title | TEXT | 商品标题 |
| category | TEXT | 商品类目 |
| tier | TEXT | 分层（利润款/引流款/爆款等） |
| style | TEXT | 风格 |
| scene | TEXT | 场景 |
| list_date | TEXT | 上架时间 |
| status | TEXT | 状态（active/inactive） |
| remark | TEXT | 备注 |
| image_url | TEXT | 图片链接 |
| manager | TEXT | 负责人 |
| starred | INTEGER | 星标收藏 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### monthly_data — 月度数据

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| product_id | TEXT | 商品ID |
| month | TEXT | 月份（如 2026-04） |
| payment_amount | REAL | 支付金额 |
| refund_amount | REAL | 退款金额 |
| net_sales | REAL | 净销售额 |
| visitors | INTEGER | 访客数 |
| page_views | INTEGER | 浏览量 |
| uv_value | REAL | UV价值 |
| search_visitors | REAL | 搜索引导访客 |
| search_ratio | REAL | 搜索占比 |
| payment_conversion | REAL | 支付转化率 |
| search_conversion | REAL | 搜索转化率 |
| cart_rate | REAL | 加购率 |
| fav_rate | REAL | 收藏率 |
| bounce_rate | REAL | 跳失率 |
| avg_stay_duration | REAL | 平均停留时长 |
| ad_spend | REAL | 推广花费 |
| ad_roi | REAL | 推广ROI |
| overall_roi | REAL | 综合ROI |
| paid_ratio | REAL | 付费占比 |
| refund_paid_ratio | REAL | 退款费比 |
| keyword_spend/sales/roi/visitors/ppc | REAL | 关键词推广 |
| crowd_spend/sales/roi/visitors/ppc | REAL | 人群推广 |
| site_spend/sales/roi/visitors/ppc | REAL | 全站推广 |
| refund_rate | REAL | 退款率 |
| repurchase_rate | REAL | 复购率 |
| cross_sell_rate | REAL | 连带率 |
| buyers | INTEGER | 买家数 |
| avg_order_value | REAL | 客单价 |
| payment_qty | INTEGER | 支付件数 |
| cart_qty | INTEGER | 加购件数 |
| fav_users | INTEGER | 收藏人数 |
| click_rate | REAL | 点击率 |
| score | REAL | 综合评分 |
| paid_ipv/organic_ipv/search_ipv/recommend_ipv | INTEGER | 流量来源细分 |
| cart_users | INTEGER | 加购人数 |
| industry_ctr | REAL | 行业点击率 |
| cross_sell_qty | INTEGER | 连带购买量 |
| cross_sell_categories | INTEGER | 连带类目宽度 |
| repurchase_users | INTEGER | 复购用户数 |
| guide_visits/visitors/potential/potential_ratio | REAL | 引潜数据 |
| new_buyers | INTEGER | 新买家数 |
| new_buyer_ratio | REAL | 新客占比 |
| data_source | TEXT | 数据来源 |
| imported_at | TIMESTAMP | 导入时间 |

#### daily_data — 日度数据

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| product_id | TEXT | 商品ID |
| date | DATE | 日期 |
| payment_amount | REAL | 支付金额 |
| refund_amount | REAL | 退款金额 |
| net_sales | REAL | 净销售额 |
| payment_qty | INTEGER | 支付件数 |
| ipv | INTEGER | 访客数 |
| pv | INTEGER | 浏览量 |
| search_ipv | INTEGER | 搜索访客 |
| recommend_ipv | INTEGER | 推荐访客 |
| paid_ipv | INTEGER | 付费访客 |
| organic_ipv | INTEGER | 自然访客 |
| payment_conversion | REAL | 支付转化率 |
| cart_rate | REAL | 加购率 |
| fav_rate | REAL | 收藏率 |
| bounce_rate | REAL | 跳失率 |
| avg_stay_duration | REAL | 平均停留时长 |
| ad_spend | REAL | 推广花费 |
| ad_roi | REAL | 推广ROI |
| buyers | INTEGER | 买家数 |
| avg_order_value | REAL | 客单价 |
| uv_value | REAL | UV价值 |
| cart_qty | INTEGER | 加购件数 |
| fav_users | INTEGER | 收藏人数 |
| search_conversion | REAL | 搜索转化率 |
| search_visitors | INTEGER | 搜索引导访客 |
| cart_users | INTEGER | 加购人数 |
| data_source | TEXT | 数据来源 |
| imported_at | TIMESTAMP | 导入时间 |

#### weekly_data — 周度数据

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| product_id | TEXT | 商品ID |
| week_start | DATE | 周起始日期 |
| payment_amount | REAL | 支付金额 |
| refund_amount | REAL | 退款金额 |
| net_sales | REAL | 净销售额 |
| presale_amount | REAL | 预售金额 |
| presale_qty | INTEGER | 预售件数 |
| ipv | INTEGER | 访客数 |
| pv | INTEGER | 浏览量 |
| search_ipv/recommend_ipv/paid_ipv/organic_ipv | INTEGER | 流量来源细分 |
| payment_conversion | REAL | 支付转化率 |
| cart_rate/fav_rate/search_click_rate/bounce_rate | REAL | 各类率值 |
| avg_stay_duration | REAL | 平均停留时长 |
| ad_spend/ad_roi | REAL | 推广数据 |
| repurchase_rate | REAL | 复购率 |
| repurchase_users | INTEGER | 复购用户数 |
| cross_sell_qty | INTEGER | 连带购买量 |
| cross_sell_rate | REAL | 连带率 |
| avg_order_value | REAL | 客单价 |
| category_width | INTEGER | 连带购买叶子类目宽度 |
| action_1/action_2 | TEXT | 运营动作记录 |
| industry_ctr | REAL | 行业点击率 |
| data_source | TEXT | 数据来源 |
| imported_at | TIMESTAMP | 导入时间 |

#### paid_detail — 付费推广明细

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| product_id | TEXT | 商品ID |
| date_range | TEXT | 日期范围 |
| impressions | INTEGER | 展现量 |
| clicks | INTEGER | 点击量 |
| cost | REAL | 花费 |
| ctr | REAL | 点击率 |
| cpc | REAL | 点击成本 |
| cpm | REAL | 千次展现成本 |
| total_gmv | REAL | 总GMV |
| total_orders | INTEGER | 总订单数 |
| direct_gmv | REAL | 直接GMV |
| indirect_gmv | REAL | 间接GMV |
| roi | REAL | 投入产出比 |
| cart_adds | INTEGER | 加购数 |
| cart_rate | REAL | 加购率 |
| favs | INTEGER | 收藏数 |
| new_buyers | INTEGER | 新客数 |
| members_gmv | REAL | 会员GMV |
| direct_orders/indirect_orders | INTEGER | 直接/间接订单 |
| click_conversion | REAL | 点击转化率 |
| presale_roi | REAL | 预售ROI |
| total_cost | REAL | 总花费 |
| direct_cart_adds/indirect_cart_adds | INTEGER | 直接/间接加购 |
| store_favs/store_fav_cost | 各类型 | 店铺收藏 |
| total_fav_cart/total_fav_cost | 各类型 | 总收藏加购 |
| item_fav_cart/item_fav_cost/item_fav_rate | 各类型 | 商品收藏 |
| cart_cost | REAL | 加购成本 |
| imported_at | TIMESTAMP | 导入时间 |

#### product_health — 商品健康度

| 列名 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| product_id | TEXT | 商品ID |
| period | TEXT | 周期 |
| sales_score | REAL | GSV环比评分 |
| conversion_score | REAL | 转化率评分 |
| roi_score | REAL | ROI评分 |
| refund_score | REAL | 退款率评分 |
| growth_score | REAL | 增长评分 |
| review_score | REAL | 评价评分 |
| gmv_change_score | REAL | GSV环比变化评分 |
| ad_spend_change_score | REAL | 推广花费变化评分 |
| roi_change_score | REAL | ROI变化评分 |
| refund_rate_score | REAL | 退款率评分 |
| cart_rate_score | REAL | 加购率评分 |
| search_ratio_score | REAL | 引潜比评分 |
| new_customer_cost_score | REAL | 拉新成本评分 |
| direct_cart_cost_score | REAL | 直接加购成本评分 |
| total_cart_cost_score | REAL | 总加购成本评分 |
| repurchase_rate_score | REAL | 复购率评分 |
| cross_sell_rate_score | REAL | 连带率评分 |
| search_ctr_vs_industry_score | REAL | 搜索vs行业评分 |
| health_score | REAL | 综合健康评分 |
| health_level | TEXT | 健康等级 |
| alert_dimensions | TEXT(JSON) | 预警维度列表 |
| created_at | TIMESTAMP | 创建时间 |

#### 其他表

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| operation_actions | 运营动作 | product_id, action_date, action_type, action_detail, before/after指标, effectiveness_score |
| shop_targets | 店铺目标 | period, target_gsv, target_ad_spend, target_ad_ratio, target_conversion, target_refund_rate |
| product_targets | 商品目标 | product_id, tier, period, target_gsv, target_ad_spend, target_ad_ratio |
| alerts | 预警 | alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, dismissed |
| alert_rules | 预警规则 | metric, operator, threshold, level, enabled |
| reviews | 评价数据 | product_id, review_date, content, rating, sentiment, positive_dims, negative_dims, scenes |
| review_summary | 评价汇总 | product_id, total_reviews, positive_rate, negative_rate, top_positive_dims, top_negative_dims |
| product_notes | 商品备注 | product_id, note, created_by |
| product_tags | 商品标签 | product_id, tag, is_auto |
| market_analysis | 市场分析 | analysis_date, category_path, total_keywords, keywords_data, need_stats_data, rankings_data |
| market_keyword_opportunities | 关键词机会 | analysis_date, keyword, pop_30d, ctr_7d, cvr_30d, opportunity_score |
| chart_events | 图表事件标注 | event_date, title, description, color, chart_type |
| scheduled_tasks | 定时任务 | task_name, task_type, cron_expr, file_pattern, enabled, last_run, next_run |
| operation_logs | 操作日志 | action, detail, operator |

---

## 5. API 接口

### 5.1 数据接口

#### KPI 与概览

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/status` | - | 检查数据库是否有数据 |
| GET | `/api/kpi` | dim, period | KPI卡片数据（含环比和异常检测） |
| GET | `/api/trend` | dim, period, start, end, metrics | 趋势数据 |
| GET | `/api/multi_trend` | dim, periods, metrics | 多周期趋势叠加 |
| GET | `/api/anomalies` | dim, period | 异常指标检测 |
| GET | `/api/target_progress` | period | 店铺目标完成进度 |
| GET | `/api/customer_analysis` | dim, period | 新老客分析 |
| GET | `/api/funnel` | dim, period | 加购→支付漏斗 |
| GET | `/api/industry_benchmark` | dim, period | 行业基准对比 |
| GET | `/api/report` | dim, period | 生成数据报告 |

#### 商品

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/products` | dim, period, page, sort, order, search, filters | 商品列表（分页） |
| POST | `/api/star` | product_id | 切换星标 |
| PUT | `/api/products/<id>/field` | field, value | 行内编辑 |
| POST | `/api/batch_update` | product_ids, field, value | 批量更新 |
| GET | `/api/notes/<product_id>` | - | 获取商品备注 |
| POST | `/api/notes` | product_id, note | 添加备注 |
| DELETE | `/api/notes/<id>` | - | 删除备注 |
| GET | `/api/product_tags` | product_id | 获取商品标签 |
| POST | `/api/product_tags` | product_id, tag | 添加标签 |
| DELETE | `/api/product_tags/<id>` | - | 删除标签 |
| POST | `/api/batch_tags` | product_ids, tags | 批量添加标签 |
| DELETE | `/api/batch_tags` | product_ids, tags | 批量删除标签 |

#### 推广与退款

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/ad_performance` | dim, period | 推广效果数据 |
| GET | `/api/refund_alert` | dim, period | 退款预警列表 |

#### 运营动作

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/actions` | dim, period | 运营动作列表 |
| POST | `/api/actions` | action对象 | 新增动作 |
| PUT | `/api/actions/<id>` | action对象 | 更新动作 |
| DELETE | `/api/actions/<id>` | - | 删除动作 |
| GET | `/api/action_stats` | dim, period | 动作效果统计 |

#### 预警

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/alerts` | period | 预警列表 |
| POST | `/api/alerts/<id>/dismiss` | - | 忽略预警 |
| GET | `/api/alert_rules` | - | 预警规则列表 |
| POST | `/api/alert_rules` | metric, operator, threshold, level | 添加规则 |
| DELETE | `/api/alert_rules/<id>` | - | 删除规则 |
| GET | `/api/alert_checks` | dim, period | 检查规则触发 |

#### 健康度

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/health` | dim, period | 商品健康度数据 |

#### 评价

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/upload/reviews` | file | 上传评价文件 |
| GET | `/api/reviews/summary` | - | 评价汇总 |
| GET | `/api/reviews/list` | page, product_id, sentiment | 评价列表 |
| GET | `/api/reviews/products` | - | 有评价的商品列表 |

#### 市场分析

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/upload/market` | files(3个) | 上传市场数据 |
| GET | `/api/market/summary` | analysis_date | 市场摘要 |
| GET | `/api/market/keywords` | analysis_date | 关键词数据 |
| GET | `/api/market/need_stats` | analysis_date | 需求统计 |
| GET | `/api/market/rankings` | analysis_date | 行业榜单 |
| GET | `/api/market/histograms` | analysis_date | 分布直方图 |
| GET | `/api/market/opportunities` | analysis_date | 蓝海机会词 |
| GET | `/api/market/reports` | - | 报告列表 |

#### 对比

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/compare` | dim, period_a, period_b | 周期对比 |
| GET | `/api/lifecycle` | - | 生命周期数据 |

#### 数据导入与系统

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/periods` | dim | 可选周期列表 |
| POST | `/api/upload/data` | file | 上传业务数据 |
| GET | `/api/import_progress/<task_id>` | - | 导入进度 |
| POST | `/api/backup` | - | 手动备份 |
| POST | `/api/export` | type, dim, period | 导出Excel |
| GET | `/api/chart_events` | chart_type | 图表事件标注 |
| POST | `/api/chart_events` | event对象 | 添加标注 |
| DELETE | `/api/chart_events/<id>` | - | 删除标注 |
| GET | `/api/scheduled_tasks` | - | 定时任务列表 |
| POST | `/api/scheduled_tasks` | task对象 | 添加任务 |
| PUT | `/api/scheduled_tasks/<id>` | task对象 | 更新任务 |
| DELETE | `/api/scheduled_tasks/<id>` | - | 删除任务 |
| POST | `/api/scheduled_tasks/<id>/run` | - | 手动执行 |
| GET | `/api/logs` | - | 操作日志 |
| POST | `/api/logs` | action, detail | 记录日志 |

### 5.2 工具接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tools/list` | 获取工具列表 |
| POST | `/api/tools/execute` | 执行工具任务 |
| GET | `/api/tools/tasks` | 获取任务列表 |

---

## 6. 数据导入

### 6.1 核心业务数据导入

**支持文件格式：** Excel (.xlsx/.xls)

**自动Sheet识别规则：**

| Sheet名/特征 | 导入目标 | 说明 |
|-------------|---------|------|
| `单品总表` | monthly_data | 月度数据 |
| `DMP` | weekly_data | DMP周度数据（含流量来源细分） |
| `付费` | paid_detail | 付费推广明细 |
| `Sheet2`/`备注` | products | 更新商品备注 |
| `生意参谋` | daily_data | 日度数据 |
| `单品` | weekly_data | 周度数据 |
| `目标`/`target` | shop_targets/product_targets | 目标数据 |
| 文件名含`日` | daily_data | 日度数据 |
| 其他 | weekly_data | 默认周度数据 |

**自动功能：**
- 导入前自动备份数据库
- 导入后自动回算运营动作效果
- 记录导入日志
- 后台线程异步执行，前端轮询进度

### 6.2 智能选款导入

- **月度版** (`import_smart.py`)：从文件名提取月份，导入 monthly_data
- **日度版** (`import_smart_daily.py`)：从文件名提取日期，导入 daily_data

### 6.3 市场分析数据导入

需3个文件同时上传：
1. 30天搜索数据
2. 7天搜索数据
3. 趋势分析数据

自动执行8维度需求分析、关键词机会分类、行业榜单排名。

### 6.4 评价数据导入

- 支持 Excel 和 CSV
- 自动列名映射
- 自动情感分析（基于词典）
- 自动维度提取（8大维度）
- 自动场景提取（20+场景）
- 自动回写评价汇总

---

## 7. 非功能需求

### 7.1 安全性

| 措施 | 说明 |
|------|------|
| SQL注入防护 | DIMENSION_MAP 白名单限制表名/列名拼接 |
| 字段编辑白名单 | ALLOWED_FIELDS 仅允许修改 tier/style/scene/manager/remark |
| 排序字段白名单 | sort_whitelist 限制可排序字段 |
| 文件上传限制 | MAX_CONTENT_LENGTH = 50MB |

### 7.2 数据库迁移

- 自动检测并添加新列（多层迁移逻辑）
- 覆盖表：products, monthly_data, weekly_data, daily_data, paid_detail, product_health
- 确保平滑升级，不丢失已有数据

### 7.3 前端特性

| 特性 | 说明 |
|------|------|
| URL状态同步 | Tab、维度、周期等参数保存到URL，支持分享和刷新恢复 |
| 主题切换 | 暗色/亮色主题，CSS变量驱动 |
| 全屏模式 | 一键全屏，适合投屏展示 |
| 自动刷新 | 可开关，默认5分钟间隔 |
| 图表保存 | ECharts图表支持保存为PNG图片 |
| 响应式布局 | 适配桌面和平板（768px断点） |
| Toast通知 | 操作反馈通知 |
| 首次引导 | 新用户引导弹窗 |

### 7.4 性能

| 优化点 | 说明 |
|------|------|
| 服务端分页 | 商品列表服务端分页，避免一次加载大量数据 |
| 异步导入 | 数据导入后台线程执行，不阻塞主线程 |
| 图表懒加载 | Tab切换时才加载对应图表 |
| 数据库索引 | product_id + period/date 联合索引 |

---

## 8. 配置项

配置文件：`config.yaml`

```yaml
app:
  host: 0.0.0.0
  port: 5000
  debug: true

data:
  db_path: data/dashboard.db
  watch_folder: ~/Downloads/tmall_data/
  backup_folder: data/backups/
  backup_on_import: true
  max_backups: 30

thresholds:
  refund_warning: 0.20          # 退款率预警阈值
  refund_consecutive_weeks: 2   # 连续退款周数
  anomaly_decline: 0.20         # 异常下降阈值
  ppc_warning: null             # PPC预警阈值
  health_warning: 40            # 健康度预警阈值

health_score_weights:
  sales: 0.25       # 销售权重
  conversion: 0.20  # 转化权重
  roi: 0.15         # ROI权重
  refund: 0.15      # 退款权重
  growth: 0.10      # 增长权重
  review: 0.15      # 评价权重

refresh:
  auto_refresh_interval: 300    # 自动刷新间隔（秒）
```

---

## 附录

### A. 商品综合评分算法

```
基础分 = 50
+ 转化率加分（上限 +20）
+ ROI加分（上限 +15）
- 退款率扣分（上限 -20）
+ UV价值加分（上限 +10）
+ 搜索占比加分（上限 +5）
= 综合评分（0~100）
```

### B. 评价情感词典（本地）

- **正面词库**：好、不错、满意、喜欢、漂亮、实用、方便、质量好等
- **负面词库**：差、烂、失望、退货、破损、难用、掉色、异味等
- **物流相关**：快递、物流、包装、配送
- **品质相关**：质量、材质、做工、耐用

### C. 文件结构

```
tmall-dashboard/
├── app.py                    # Flask 入口
├── db.py                     # 数据库连接与迁移
├── config.yaml               # 配置文件
├── requirements.txt          # Python 依赖
├── api/
│   ├── __init__.py
│   ├── data_api.py           # 数据接口（70+ 端点）
│   └── tool_api.py           # 工具接口
├── templates/
│   ├── dashboard.html        # 主页面
│   ├── preview.html          # 预览页
│   └── partials/
│       ├── tab-overview.html
│       ├── tab-ops.html
│       ├── tab-health.html
│       ├── tab-review.html
│       ├── tab-market.html
│       ├── tab-lifecycle.html
│       ├── tab-compare.html
│       └── toolbox.html
├── static/
│   ├── css/dashboard.css     # 样式（暗色/亮色主题）
│   └── js/
│       ├── bundle.js         # 完整JS包
│       ├── bundle.min.js     # 压缩版
│       ├── utils.js          # 工具函数
│       ├── kpi.js            # KPI卡片
│       ├── trend.js          # 趋势图
│       ├── products.js       # 商品表格
│       ├── ad.js             # 推广分析
│       ├── refund.js         # 退款分析
│       ├── actions.js        # 运营动作
│       ├── target.js         # 目标进度
│       ├── health.js         # 健康度
│       ├── review.js         # 评价分析
│       ├── market.js         # 市场分析
│       ├── lifecycle.js      # 生命周期
│       ├── compare.js        # 周期对比
│       └── toolbox.js        # 工具箱
├── scripts/
│   ├── import_data.py        # 核心数据导入
│   ├── import_smart.py       # 智能选款（月度）
│   ├── import_smart_daily.py # 智能选款（日度）
│   ├── import_market.py      # 市场数据导入
│   ├── market_analyzer.py    # 市场数据分析器
│   ├── calc_health.py        # 健康度计算
│   └── utils.py              # 脚本工具
└── data/
    ├── dashboard.db          # SQLite 数据库
    ├── import_log.json       # 导入日志
    ├── raw/                  # 原始数据文件
    └── backups/              # 数据库备份
```
