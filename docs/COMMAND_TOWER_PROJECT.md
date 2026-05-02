# 六边形指挥塔 - 电商运营作战系统

## 项目概述

**项目名称**：海贝海数据仪表盘 2.0 - 六边形指挥塔

**项目定位**：从"数据看板"升级为"运营作战系统"，实现数据驱动决策的完整闭环。

**核心价值**：
- 🔄 **导表离线**：多平台数据统一导入与清洗
- 🎯 **目标闭环**：从目标设定到执行追踪的完整闭环
- 📊 **动作监控**：运营动作记录与效果分析
- 👥 **人群资产**：跨平台人群资产归因与ROI分析
- 🧪 **策略实验**：A/B测试与SOP沉淀
- 👤 **人效度量**：个人KPI与任务追踪
- 🚨 **智能预警**：异常自动发现与处理建议
- 🔗 **供应链协同**：前后端联动预警

---

## 技术架构

### 后端技术栈
- **框架**：FastAPI 0.136+
- **数据库**：SQLite + SQLAlchemy 2.0
- **任务调度**：APScheduler 3.11+
- **数据处理**：Pandas 3.0+
- **AI集成**：OpenAI API（智能导入）

### 前端技术栈
- **框架**：Vue 3 + Vite 5
- **UI组件**：Element Plus 2.5+
- **图表库**：ECharts 5.5+
- **路由**：Vue Router 4.2+
- **HTTP客户端**：Axios 1.6+

### 数据库架构
- **ORM**：SQLAlchemy 2.0+
- **连接池**：aiosqlite 0.22+
- **迁移方式**：Python脚本迁移

---

## 功能模块详细说明

### 一、人群资产归因系统

#### 1.1 万相台投放管理
- **功能**：管理万相台广告投放计划
- **数据项**：
  - 计划名称、预算、出价
  - 每日消耗、点击、转化数据
  - ROI、CPA等效果指标
- **API路由**：`/api/crowd-asset/wxt-campaigns`

#### 1.2 达摩盘人群管理
- **功能**：管理达摩盘人群包数据
- **数据项**：
  - 人群名称、分层等级（S/A/B/C）
  - 人群规模、覆盖人数
  - 自定义出价系数
- **API路由**：`/api/crowd-asset/dmp-crowds`

#### 1.3 AIPL人群资产分析
- **功能**：追踪用户从认知到忠诚的全链路
- **指标**：
  - A（认知）人群增量
  - I（兴趣）人群增量
  - P（购买）人群增量
  - L（忠诚）人群增量
- **API路由**：`/api/crowd-asset/dashboard`

#### 1.4 效率矩阵
- **功能**：人群×出价效率可视化
- **分析维度**：
  - ROI vs 出价系数
  - 人群价值评估
  - 最优出价建议
- **图表类型**：散点图 + 气泡图

### 二、策略实验与SOP系统

#### 2.1 A/B测试管理
- **功能**：创建和管理A/B测试实验
- **实验类型**：
  - 主图测试
  - 人群包测试
  - 标题关键词测试
  - 投放策略测试
- **统计指标**：
  - CTR（点击率）
  - 转化率
  - ROI
  - 显著性检验
- **API路由**：`/api/abtest-sop/tests`

#### 2.2 实验结果分析
- **功能**：自动分析实验结果
- **分析内容**：
  - 变异组对比
  - 统计显著性计算
  - 胜出方案推荐
- **API路由**：`/api/abtest-sop/tests/{id}/analysis`

#### 2.3 SOP模板库
- **功能**：沉淀和复用运营方法论
- **模板类型**：
  - 大促活动SOP
  - 新品推广SOP
  - 日常运营SOP
- **元数据**：
  - 使用次数
  - 平均效果评分
  - 适用场景标签
- **API路由**：`/api/abtest-sop/sop-templates`

#### 2.4 营销活动管理
- **功能**：管理营销活动全生命周期
- **活动阶段**：
  - 计划中（planned）
  - 进行中（running）
  - 已结束（finished）
- **关联数据**：
  - 目标GMV
  - 实际GMV
  - 完成率
  - 关联SOP模板
- **API路由**：`/api/abtest-sop/campaign-projects`

### 三、人效精准度量系统

#### 3.1 用户KPI管理
- **功能**：设置个人级绩效指标
- **KPI维度**：
  - GMV目标与实际
  - 任务完成率
  - 动作执行频次
  - 效果提升指标
- **API路由**：`/api/efficiency/user-kpis`

#### 3.2 任务看板
- **功能**：可视化任务追踪
- **看板列**：
  - 待办（todo）
  - 进行中（in_progress）
  - 阻塞（blocked）
  - 完成（done）
- **任务属性**：
  - 标题、描述
  - 优先级（high/medium/low）
  - 负责人
  - 截止时间
- **API路由**：`/api/efficiency/kanban`

#### 3.3 人效排行榜
- **功能**：团队人效横向对比
- **排行指标**：
  - GMV产出
  - 目标达成率
  - 任务完成率
  - 综合绩效评级（S/A/B/C）
- **API路由**：`/api/efficiency/dashboard`

### 四、智能告警系统

#### 4.1 告警规则引擎
- **功能**：配置自定义告警规则
- **规则类型**：
  - 指标异动监控
  - 阈值告警
  - 趋势告警
  - 连续天数监控
- **告警级别**：
  - 严重（critical）
  - 警告（warning）
  - 提示（info）
- **API路由**：`/api/smart-alert/rules`

#### 4.2 告警处理流程
- **功能**：告警接收、处理、追踪
- **处理动作**：
  - 忽略（dismissed）
  - 解决（resolved）
  - 升级处理
- **处理建议**：
  - 自动生成处理建议
  - 关联分析入口
  - 一键跳转处理
- **API路由**：`/api/smart-alert/alerts`

#### 4.3 供应链协同预警
- **功能**：前后端数据联动
- **预警类型**：
  - 库存告急预警
  - 滞销清理提醒
  - 补货建议
  - 超卖风险预警
- **数据来源**：
  - 生意参谋实时销量
  - ERP库存数据
  - 预测模型
- **API路由**：`/api/smart-alert/supply-chain`

---

## 数据库表结构

### 一、人群资产相关表

#### 1. wxt_campaigns（万相台投放计划表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| campaign_name | String(200) | 计划名称 |
| budget | Float | 预算 |
| bid_strategy | String(50) | 出价策略 |
| status | String(20) | 状态 |
| start_date | Date | 开始日期 |
| end_date | Date | 结束日期 |
| created_at | DateTime | 创建时间 |

#### 2. wxt_daily_metrics（万相台每日指标表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| campaign_id | Integer | 关联计划ID |
| metric_date | Date | 统计日期 |
| cost | Float | 消耗 |
| click | Integer | 点击 |
| conversion | Integer | 转化 |
| gmv | Float | GMV |
| roi | Float | ROI |
| cpa | Float | CPA |

#### 3. dmp_crowds（达摩盘人群表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| crowd_name | String(200) | 人群名称 |
| crowd_type | String(50) | 人群类型 |
| tier | String(10) | 分层等级 |
| crowd_size | Integer | 人群规模 |
| bid_coefficient | Float | 出价系数 |
| status | String(20) | 状态 |

#### 4. crowd_asset_stats（人群资产统计表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| stat_date | Date | 统计日期 |
| awareness_count | Integer | A人群数 |
| interest_count | Integer | I人群数 |
| purchase_count | Integer | P人群数 |
| loyalty_count | Integer | L人群数 |
| asset_roi | Float | 资产ROI |

### 二、策略实验相关表

#### 5. ab_tests（A/B测试表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| test_name | String(200) | 实验名称 |
| test_type | String(50) | 实验类型 |
| hypothesis | Text | 实验假设 |
| status | String(20) | 状态 |
| start_date | Date | 开始日期 |
| end_date | Date | 结束日期 |
| is_significant | Boolean | 是否显著 |
| winner_variant | String(50) | 胜出方案 |

#### 6. ab_test_variants（实验变体表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| test_id | Integer | 关联实验ID |
| variant_name | String(50) | 变体名称 |
| description | Text | 变体描述 |
| traffic_allocation | Float | 流量分配 |

#### 7. sop_templates（SOP模板表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| template_name | String(200) | 模板名称 |
| template_type | String(50) | 模板类型 |
| category | String(50) | 分类 |
| content | JSON | 模板内容 |
| use_count | Integer | 使用次数 |
| avg_effectiveness | Float | 平均效果 |

#### 8. campaign_projects（营销活动表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| project_name | String(200) | 项目名称 |
| project_type | String(50) | 项目类型 |
| status | String(20) | 状态 |
| target_gmv | Float | 目标GMV |
| actual_gmv | Float | 实际GMV |
| budget | Float | 预算 |
| start_date | Date | 开始日期 |
| end_date | Date | 结束日期 |

### 三、人效度量相关表

#### 9. user_kpis（用户KPI表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户ID |
| username | String(100) | 用户名 |
| period | String(20) | 考核周期 |
| target_gmv | Float | GMV目标 |
| actual_gmv | Float | GMV实际 |
| task_progress | Float | 任务进度 |
| performance_rating | String(10) | 绩效评级 |

#### 10. task_items（任务表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| task_title | String(200) | 任务标题 |
| description | Text | 任务描述 |
| status | String(20) | 状态 |
| priority | String(20) | 优先级 |
| assignee | String(100) | 负责人 |
| due_date | Date | 截止日期 |
| project_id | Integer | 关联项目ID |

### 四、智能告警相关表

#### 11. smart_alert_rules（告警规则表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| rule_name | String(200) | 规则名称 |
| metric | String(50) | 监控指标 |
| operator | String(10) | 操作符 |
| threshold | Float | 阈值 |
| window_size | Integer | 监控窗口 |
| level | String(20) | 告警级别 |
| enabled | Boolean | 是否启用 |

#### 12. smart_alerts（告警记录表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| rule_id | Integer | 关联规则ID |
| title | String(200) | 告警标题 |
| detail | Text | 告警详情 |
| level | String(20) | 告警级别 |
| metric | String(50) | 触发指标 |
| current_value | Float | 当前值 |
| threshold_value | Float | 阈值 |
| status | String(20) | 状态 |
| resolved | Boolean | 是否解决 |
| dismissed | Boolean | 是否忽略 |

#### 13. supply_chain_data（供应链数据表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| product_id | String(50) | 产品ID |
| product_title | String(200) | 产品名称 |
| current_stock | Integer | 当前库存 |
| safety_stock | Integer | 安全库存 |
| daily_sales | Float | 日均销量 |
| days_of_stock | Float | 库存天数 |
| updated_at | DateTime | 更新时间 |

#### 14. inventory_alerts（库存告警表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| supply_data_id | Integer | 关联供应链数据ID |
| alert_type | String(50) | 告警类型 |
| current_stock | Integer | 当前库存 |
| days_until_stockout | Float | 断货天数 |
| status | String(20) | 状态 |

---

## API接口文档

### 一、人群资产API

#### 1.1 获取人群资产仪表盘
```
GET /api/crowd-asset/dashboard
响应：
{
  "summary": {
    "total_cost": 250000,
    "total_gmv": 850000,
    "asset_roi": 3.4,
    "aipl_increase": 15600
  },
  "top_crowds": [...]
}
```

#### 1.2 万相台计划管理
```
GET    /api/crowd-asset/wxt-campaigns    # 获取计划列表
POST   /api/crowd-asset/wxt-campaigns    # 创建计划
GET    /api/crowd-asset/wxt-campaigns/{id}  # 获取详情
PUT    /api/crowd-asset/wxt-campaigns/{id}  # 更新计划
DELETE /api/crowd-asset/wxt-campaigns/{id}  # 删除计划
```

#### 1.3 达摩盘人群管理
```
GET    /api/crowd-asset/dmp-crowds    # 获取人群列表
POST   /api/crowd-asset/dmp-crowds    # 创建人群包
PUT    /api/crowd-asset/dmp-crowds/{id}  # 更新人群包
DELETE /api/crowd-asset/dmp-crowds/{id}  # 删除人群包
```

#### 1.4 效率矩阵分析
```
GET /api/crowd-asset/efficiency-matrix
响应：
{
  "matrix_data": [
    {
      "crowd_name": "高潜女性用户",
      "roi": 4.2,
      "bid_coefficient": 1.5,
      "crowd_size": 10000
    }
  ]
}
```

### 二、策略实验API

#### 2.1 A/B测试管理
```
GET    /api/abtest-sop/tests              # 获取实验列表
POST   /api/abtest-sop/tests              # 创建实验
GET    /api/abtest-sop/tests/{id}         # 获取实验详情
PUT    /api/abtest-sop/tests/{id}         # 更新实验
DELETE /api/abtest-sop/tests/{id}         # 删除实验
POST   /api/abtest-sop/tests/{id}/start   # 启动实验
POST   /api/abtest-sop/tests/{id}/stop    # 停止实验
POST   /api/abtest-sop/tests/{id}/analysis # 分析结果
```

#### 2.2 SOP模板管理
```
GET    /api/abtest-sop/sop-templates      # 获取模板列表
POST   /api/abtest-sop/sop-templates      # 创建模板
GET    /api/abtest-sop/sop-templates/{id} # 获取模板详情
PUT    /api/abtest-sop/sop-templates/{id} # 更新模板
DELETE /api/abtest-sop/sop-templates/{id} # 删除模板
POST   /api/abtest-sop/sop-templates/{id}/use  # 使用模板
```

#### 2.3 营销活动管理
```
GET    /api/abtest-sop/campaign-projects   # 获取活动列表
POST   /api/abtest-sop/campaign-projects  # 创建活动
GET    /api/abtest-sop/campaign-projects/{id}  # 获取活动详情
PUT    /api/abtest-sop/campaign-projects/{id}  # 更新活动
DELETE /api/abtest-sop/campaign-projects/{id}  # 删除活动
POST   /api/abtest-sop/campaign-projects/{id}/review  # 生成复盘
```

### 三、人效度量API

#### 3.1 仪表盘数据
```
GET /api/efficiency/dashboard
响应：
{
  "team_summary": {
    "total_actual_gmv": 2850000,
    "total_progress": 85.2,
    "avg_task_progress": 88.5,
    "user_count": 5
  },
  "user_rankings": [...]
}
```

#### 3.2 任务看板
```
GET /api/efficiency/kanban
响应：
{
  "kanban": {
    "todo": [...],
    "in_progress": [...],
    "blocked": [...],
    "done": [...]
  }
}
```

#### 3.3 用户KPI管理
```
GET    /api/efficiency/user-kpis          # 获取KPI列表
POST   /api/efficiency/user-kpis          # 创建KPI
PUT    /api/efficiency/user-kpis/{id}     # 更新KPI
DELETE /api/efficiency/user-kpis/{id}     # 删除KPI
```

### 四、智能告警API

#### 4.1 告警规则管理
```
GET    /api/smart-alert/rules             # 获取规则列表
POST   /api/smart-alert/rules             # 创建规则
PUT    /api/smart-alert/rules/{id}        # 更新规则
DELETE /api/smart-alert/rules/{id}        # 删除规则
POST   /api/smart-alert/rules/{id}/toggle # 启用/禁用规则
```

#### 4.2 告警处理
```
GET    /api/smart-alert/alerts            # 获取告警列表
POST   /api/smart-alert/alerts/{id}/resolve  # 解决告警
POST   /api/smart-alert/alerts/{id}/dismiss  # 忽略告警
POST   /api/smart-alert/check            # 手动触发检查
```

#### 4.3 供应链告警
```
GET /api/smart-alert/supply-chain
响应：
{
  "alerts": [
    {
      "id": 1,
      "product_id": "P001",
      "title": "热销产品C",
      "alert_type": "库存告急",
      "current_stock": 50,
      "status": "pending",
      "detail": "库存只够销售3天"
    }
  ]
}
```

---

## 文件结构

### 后端文件
```
backend/
├── app/
│   ├── api/
│   │   ├── crowd_asset.py      # 人群资产API
│   │   ├── abtest_sop.py       # A/B测试与SOP API
│   │   ├── efficiency.py       # 人效度量API
│   │   └── smart_alert.py       # 智能告警API
│   ├── models/
│   │   └── command_tower.py     # 六边形指挥塔数据模型
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── scheduler.py
│   │   └── logger.py
│   └── main.py                  # 应用入口
├── migrate_command_tower.py     # 数据库迁移脚本
└── requirements.txt
```

### 前端文件
```
frontend/
├── src/
│   ├── views/
│   │   ├── CrowdAsset.vue      # 人群资产页面
│   │   ├── ABTestSop.vue       # 策略实验页面
│   │   ├── Efficiency.vue      # 人效度量页面
│   │   └── SmartAlert.vue       # 智能告警页面
│   ├── router/
│   │   └── index.js             # 路由配置
│   └── App.vue                  # 主应用组件
└── package.json
```

---

## 部署指南

### 环境要求
- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 后端部署
```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 运行数据库迁移
python migrate_command_tower.py

# 3. 启动服务
python -m app.main
# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端部署
```bash
# 1. 安装依赖
cd frontend
npm install

# 2. 开发模式
npm run dev

# 3. 生产构建
npm run build

# 构建产物在 dist/ 目录
```

### Docker部署
```bash
# 使用 docker-compose
docker-compose up -d
```

---

## 使用指南

### 1. 人群资产归因使用流程
1. 导入万相台消耗数据
2. 导入达摩盘人群数据
3. 配置人群分层和出价系数
4. 查看人群资产仪表盘
5. 分析效率矩阵
6. 优化投放策略

### 2. 策略实验使用流程
1. 制定实验假设
2. 创建A/B测试实验
3. 设计实验变体
4. 启动实验并监控
5. 实验结束后分析结果
6. 将有效策略沉淀为SOP模板

### 3. 人效度量使用流程
1. 为团队成员设置KPI目标
2. 创建和分配任务
3. 追踪任务执行进度
4. 查看人效排行榜
5. 绩效评估与反馈

### 4. 智能告警使用流程
1. 配置告警规则
2. 设置告警阈值和监控窗口
3. 启用规则监控
4. 接收告警通知
5. 处理告警并记录
6. 查看处理建议

---

## 演进路径

### 第一阶段（1个月）：决策指挥舱
- 完成生意参谋核心指标导表与清洗
- 目标拆解与双进度预警
- 简单的动作日志打点

### 第二阶段（2个月）：资产与实验体系
- 接入万相台、达摩盘导表
- 建成人群资产看板和出价分析
- 上线A/B测试标记
- 活动SOP基础模板

### 第三阶段（3个月）：人效与预警闭环
- 落地个人KPI追踪
- 任务矩阵
- 配置关键指标的自动化预警

### 持续运营（季度迭代）
- 每季度开运营评审会
- 用仪表盘复盘
- 调整KPI权重
- 年度产出数据资产白皮书

---

## 附录

### A. 术语表
- **AIPL**：认知(Awareness)、兴趣(Interest)、购买(Purchase)、忠诚(Loyalty)
- **CPA**：Cost Per Acquisition，每次获取成本
- **ROI**：Return on Investment，投资回报率
- **SOP**：Standard Operating Procedure，标准作业程序
- **A/B Test**：对比测试，通过分组实验验证假设

### B. 性能指标
- API响应时间：< 200ms
- 页面加载时间：< 3s
- 数据库查询：< 100ms
- 并发支持：100+ 用户

### C. 监控指标
- 系统健康度
- API可用性
- 数据库性能
- 错误率
- 用户活跃度

---

**文档版本**：1.0.0
**最后更新**：2026-05-02
**维护团队**：海贝海数据团队
