# 六边形指挥塔 V1.1 - 功能补充完善规划

## 文档信息

- **版本**：V1.1
- **创建日期**：2026-05-02
- **规划周期**：8周（2个月）
- **目标**：从"能用"升级为"好用且能打"

---

## 一、功能补充总览

### 1.1 四大层级

| 层级 | 模块数 | 优先级 | 开发周期 |
|------|--------|--------|----------|
| 基础核心功能 | 4个 | P0 | 3周 |
| 体验优化功能 | 3个 | P1 | 1周 |
| 生产环境必备 | 3个 | P2 | 2周 |
| 高级扩展功能 | 2个 | P3 | 2周 |

### 1.2 开发优先级

```
Week 1: 数据导入中心 + 全局时间筛选器 + 数据导出
Week 2-3: 商品分析 + 流量分析 + 推广效果分析
Week 4-5: 用户权限 + 多店铺管理 + 数据备份
Week 6-8: AI智能分析 + 消息推送 + 高级功能
```

---

## 二、基础核心功能补充（P0 - 必须优先）

### 2.1 数据导入中心

#### 2.1.1 功能需求

**当前问题**：
- 没有专门的导入管理页面
- 只有后端API，用户无法自行导入数据
- 缺少导入历史和错误追踪

**目标功能**：
1. **拖拽上传**
   - 支持拖拽单个或多个Excel文件
   - 支持ZIP压缩包批量导入
   - 显示上传进度条

2. **模板自动识别**
   - 生意参谋交易报表
   - 生意参谋商品报表
   - 生意参谋流量报表
   - 生意参谋推广报表
   - 万相台投放报表
   - 达摩盘人群报表

3. **数据校验**
   - 格式检查：列名、数据类型
   - 重复检查：避免重复导入
   - 缺失检查：必填字段验证
   - 逻辑检查：数据合理性验证

4. **导入历史**
   - 记录每次导入的时间、文件名、数据量
   - 显示导入状态（成功/失败/部分成功）
   - 错误详情和错误报告下载
   - 支持回滚最近一次导入

5. **模板下载**
   - 提供标准Excel模板
   - 包含示例数据和填写说明
   - 支持自定义模板

#### 2.1.2 技术实现

**前端实现**：

文件路径：`frontend/src/views/ImportCenter.vue`

```vue
<template>
  <div class="import-center">
    <!-- 上传区域 -->
    <el-upload
      drag
      multiple
      :auto-upload="false"
      :on-change="handleFileChange"
      :before-upload="beforeUpload"
      accept=".xlsx,.xls,.csv,.zip"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽文件到此处，或<em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持 Excel (.xlsx, .xls)、CSV、ZIP 格式，单个文件不超过50MB
        </div>
      </template>
    </el-upload>

    <!-- 文件列表 -->
    <div class="file-list">
      <div v-for="file in fileList" :key="file.uid" class="file-item">
        <div class="file-info">
          <el-icon><document /></el-icon>
          <span class="file-name">{{ file.name }}</span>
          <el-tag size="small">{{ getFileType(file.name) }}</el-tag>
        </div>
        <div class="file-actions">
          <el-progress v-if="file.uploading" :percentage="file.progress" />
          <el-button v-else size="small" @click="importFile(file)">导入</el-button>
        </div>
      </div>
    </div>

    <!-- 导入历史 -->
    <div class="import-history">
      <h3>导入历史</h3>
      <el-table :data="importHistory">
        <el-table-column prop="import_time" label="导入时间" width="180" />
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="data_type" label="数据类型" width="120" />
        <el-table-column prop="record_count" label="记录数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="row.can_rollback" size="small" type="warning" @click="rollback(row)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>
```

**后端API增强**：

文件路径：`backend/app/api/imports.py`

```python
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传文件并自动识别类型"""
    # 1. 保存文件
    file_path = await save_upload_file(file)
    
    # 2. 识别文件类型
    file_type = detect_file_type(file_path)
    
    # 3. 解析数据
    data = parse_excel(file_path, file_type)
    
    # 4. 数据校验
    validation_result = validate_data(data, file_type)
    
    # 5. 返回预览
    return {
        "file_path": file_path,
        "file_type": file_type,
        "record_count": len(data),
        "preview": data[:10],
        "validation": validation_result
    }

@router.post("/confirm")
async def confirm_import(
    file_path: str,
    file_type: str,
    db: Session = Depends(get_db)
):
    """确认导入数据"""
    # 1. 解析数据
    data = parse_excel(file_path, file_type)
    
    # 2. 导入数据库
    import_result = await import_data(data, file_type, db)
    
    # 3. 记录导入历史
    history = create_import_history(
        file_path=file_path,
        file_type=file_type,
        record_count=import_result["count"],
        status="success"
    )
    
    return {
        "success": True,
        "imported_count": import_result["count"],
        "history_id": history.id
    }

@router.post("/rollback/{history_id}")
async def rollback_import(
    history_id: int,
    db: Session = Depends(get_db)
):
    """回滚导入"""
    # 1. 获取导入历史
    history = db.query(ImportHistory).filter_by(id=history_id).first()
    
    # 2. 删除相关数据
    rollback_data(history, db)
    
    # 3. 更新历史状态
    history.status = "rolled_back"
    db.commit()
    
    return {"success": True, "message": "回滚成功"}
```

**数据库表设计**：

```sql
CREATE TABLE import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_type VARCHAR(50),
    data_type VARCHAR(50),
    record_count INTEGER,
    success_count INTEGER,
    error_count INTEGER,
    status VARCHAR(20),  -- pending, success, failed, rolled_back
    error_details TEXT,  -- JSON格式错误详情
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    rolled_back_at DATETIME,
    can_rollback BOOLEAN DEFAULT TRUE
);

CREATE TABLE import_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(50),
    columns JSON,  -- 列定义
    required_columns JSON,  -- 必填列
    sample_file VARCHAR(500),  -- 示例文件路径
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.1.3 实现步骤

**Week 1 - Day 1-2**：
1. 创建导入中心前端页面
2. 实现拖拽上传功能
3. 创建文件类型识别逻辑

**Week 1 - Day 3-4**：
4. 实现数据校验功能
5. 创建导入历史记录
6. 实现回滚功能

**Week 1 - Day 5**：
7. 测试和优化
8. 编写使用文档

#### 2.1.4 验收标准

- [ ] 支持拖拽上传Excel、CSV、ZIP文件
- [ ] 自动识别至少6种常见报表类型
- [ ] 导入前显示数据预览
- [ ] 导入成功后显示导入统计
- [ ] 导入失败时显示详细错误信息
- [ ] 支持查看最近30天的导入历史
- [ ] 支持回滚最近一次导入
- [ ] 提供至少5种标准模板下载

---

### 2.2 商品分析模块

#### 2.2.1 功能需求

**当前问题**：
- 没有独立的商品分析页面
- 无法查看商品排行榜
- 缺少单品详情分析

**目标功能**：

1. **商品排行榜**
   - 按销售额排序
   - 按销量排序
   - 按转化率排序
   - 按收藏加购率排序
   - 按退款率排序

2. **单品详情页**
   - 销售趋势图（日/周/月）
   - 流量趋势图
   - 转化趋势图
   - 关键指标卡片

3. **SKU分析**
   - SKU销售占比
   - SKU库存情况
   - SKU利润贡献

4. **滞销商品预警**
   - 30天无销量商品
   - 销量低于阈值商品
   - 库存积压商品

5. **商品生命周期**
   - 新品期（0-30天）
   - 成长期（31-90天）
   - 成熟期（91-180天）
   - 衰退期（180+天）

#### 2.2.2 技术实现

**前端实现**：

文件路径：`frontend/src/views/ProductAnalysis.vue`

```vue
<template>
  <div class="product-analysis">
    <!-- 排行榜切换 -->
    <el-tabs v-model="activeRank">
      <el-tab-pane label="销售额排行" name="gmv" />
      <el-tab-pane label="销量排行" name="quantity" />
      <el-tab-pane label="转化率排行" name="conversion" />
      <el-tab-pane label="滞销预警" name="unsold" />
    </el-tabs>

    <!-- 商品列表 -->
    <el-table :data="products">
      <el-table-column prop="rank" label="排名" width="80" />
      <el-table-column prop="product_title" label="商品名称" min-width="200" />
      <el-table-column prop="gmv" label="销售额" width="120">
        <template #default="{ row }">¥{{ formatNumber(row.gmv) }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="销量" width="100" />
      <el-table-column prop="conversion_rate" label="转化率" width="100">
        <template #default="{ row }">{{ row.conversion_rate }}%</template>
      </el-table-column>
      <el-table-column label="生命周期" width="100">
        <template #default="{ row }">
          <el-tag :type="getLifecycleType(row.lifecycle_stage)">
            {{ row.lifecycle_stage }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row)">详情</el-button>
          <el-button size="small" @click="viewTrend(row)">趋势</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
```

**后端API**：

文件路径：`backend/app/api/product_analysis.py`

```python
@router.get("/rankings")
async def get_product_rankings(
    rank_type: str = "gmv",  # gmv, quantity, conversion
    time_range: str = "last_30_days",
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取商品排行榜"""
    query = db.query(Product)
    
    if rank_type == "gmv":
        query = query.order_by(Product.total_gmv.desc())
    elif rank_type == "quantity":
        query = query.order_by(Product.total_quantity.desc())
    elif rank_type == "conversion":
        query = query.order_by(Product.conversion_rate.desc())
    
    products = query.limit(limit).all()
    
    return {
        "products": [
            {
                "rank": idx + 1,
                "product_id": p.id,
                "product_title": p.title,
                "gmv": p.total_gmv,
                "quantity": p.total_quantity,
                "conversion_rate": p.conversion_rate,
                "lifecycle_stage": get_lifecycle_stage(p.created_at)
            }
            for idx, p in enumerate(products)
        ]
    }

@router.get("/unsold-alerts")
async def get_unsold_alerts(
    days: int = 30,
    threshold: int = 0,
    db: Session = Depends(get_db)
):
    """获取滞销商品预警"""
    # 查询N天无销量的商品
    unsold_products = db.query(Product).filter(
        Product.last_sale_date < datetime.now() - timedelta(days=days)
    ).all()
    
    return {
        "total": len(unsold_products),
        "products": [
            {
                "product_id": p.id,
                "product_title": p.title,
                "last_sale_date": p.last_sale_date,
                "stock": p.stock,
                "days_unsold": (datetime.now() - p.last_sale_date).days
            }
            for p in unsold_products
        ]
    }
```

#### 2.2.3 实现步骤

**Week 2 - Day 1-2**：
1. 创建商品分析前端页面
2. 实现排行榜功能
3. 创建后端API

**Week 2 - Day 3-4**：
4. 实现单品详情页
5. 实现SKU分析
6. 实现滞销预警

**Week 2 - Day 5**：
7. 测试和优化

---

### 2.3 流量分析模块

#### 2.3.1 功能需求

**目标功能**：

1. **流量概览**
   - 总UV、PV
   - 跳出率
   - 平均访问时长
   - 流量趋势图

2. **来源渠道分析**
   - 免费流量占比
   - 付费流量占比
   - 自主访问占比
   - 其他流量占比

3. **关键词分析**
   - 搜索关键词排行
   - 关键词流量
   - 关键词转化
   - 关键词排名变化

4. **页面分析**
   - 页面访问量排行
   - 页面跳出率
   - 页面转化贡献

#### 2.3.2 技术实现

**前端实现**：

文件路径：`frontend/src/views/TrafficAnalysis.vue`

```vue
<template>
  <div class="traffic-analysis">
    <!-- 流量概览卡片 -->
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">总UV</div>
            <div class="metric-value">{{ formatNumber(trafficOverview.uv) }}</div>
          </div>
        </el-card>
      </el-col>
      <!-- 更多卡片... -->
    </el-row>

    <!-- 流量趋势图 -->
    <el-card>
      <div ref="trafficTrendChart" style="height: 400px;"></div>
    </el-card>

    <!-- 来源渠道饼图 -->
    <el-card>
      <div ref="sourcePieChart" style="height: 400px;"></div>
    </el-card>

    <!-- 关键词排行 -->
    <el-card>
      <el-table :data="topKeywords">
        <el-table-column prop="keyword" label="关键词" />
        <el-table-column prop="pv" label="流量" />
        <el-table-column prop="conversion_rate" label="转化率" />
      </el-table>
    </el-card>
  </div>
</template>
```

**后端API**：

文件路径：`backend/app/api/traffic_analysis.py`

```python
@router.get("/overview")
async def get_traffic_overview(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
):
    """获取流量概览"""
    # 查询流量数据
    traffic_data = db.query(TrafficData).filter(
        TrafficData.date >= start_date,
        TrafficData.date <= end_date
    ).all()
    
    # 计算汇总指标
    total_uv = sum(t.uv for t in traffic_data)
    total_pv = sum(t.pv for t in traffic_data)
    avg_bounce_rate = sum(t.bounce_rate for t in traffic_data) / len(traffic_data)
    
    return {
        "uv": total_uv,
        "pv": total_pv,
        "bounce_rate": avg_bounce_rate,
        "avg_duration": calculate_avg_duration(traffic_data)
    }

@router.get("/source-analysis")
async def get_source_analysis(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
):
    """获取来源渠道分析"""
    traffic_data = db.query(TrafficData).filter(
        TrafficData.date >= start_date,
        TrafficData.date <= end_date
    ).all()
    
    # 按来源分组统计
    source_stats = {}
    for t in traffic_data:
        if t.source not in source_stats:
            source_stats[t.source] = {"uv": 0, "pv": 0}
        source_stats[t.source]["uv"] += t.uv
        source_stats[t.source]["pv"] += t.pv
    
    return {
        "sources": source_stats,
        "total_uv": sum(s["uv"] for s in source_stats.values())
    }
```

---

### 2.4 推广效果分析增强

#### 2.4.1 功能需求

**当前问题**：
- 只有万相台数据
- 缺少直通车、引力魔方、淘客数据

**目标功能**：

1. **推广总览**
   - 总花费、总点击、总成交
   - 整体ROI
   - 分渠道花费占比

2. **分渠道分析**
   - 直通车：计划、关键词、创意分析
   - 引力魔方：资源位、人群分析
   - 万相台：场景、人群分析
   - 淘客：佣金、效果分析

3. **关键词分析**
   - 关键词排名
   - 关键词花费
   - 关键词转化
   - 关键词ROI

4. **预算管理**
   - 每日预算设置
   - 花费进度监控
   - 超预算预警

---

## 三、体验优化功能（P1）

### 3.1 全局时间筛选器

#### 3.1.1 功能需求

**当前问题**：
- 每个页面单独设置时间
- 用户体验差
- 时间范围不统一

**目标功能**：

1. **全局时间选择器**
   - 放在页面顶部导航栏
   - 一次设置，所有页面生效
   - 使用Vuex/Pinia存储时间范围

2. **预设时间范围**
   - 今日
   - 昨日
   - 本周
   - 上周
   - 本月
   - 上月
   - 近7天
   - 近30天
   - 自定义

3. **时间记忆**
   - 保存到localStorage
   - 下次登录自动恢复

#### 3.1.2 技术实现

**前端实现**：

文件路径：`frontend/src/components/GlobalTimeFilter.vue`

```vue
<template>
  <div class="global-time-filter">
    <el-select v-model="selectedRange" @change="handleRangeChange">
      <el-option label="今日" value="today" />
      <el-option label="昨日" value="yesterday" />
      <el-option label="本周" value="this_week" />
      <el-option label="上周" value="last_week" />
      <el-option label="本月" value="this_month" />
      <el-option label="上月" value="last_month" />
      <el-option label="近7天" value="last_7_days" />
      <el-option label="近30天" value="last_30_days" />
      <el-option label="自定义" value="custom" />
    </el-select>
    
    <el-date-picker
      v-if="selectedRange === 'custom'"
      v-model="customRange"
      type="daterange"
      @change="handleCustomChange"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useTimeStore } from '@/stores/time'

const timeStore = useTimeStore()
const selectedRange = ref('last_30_days')
const customRange = ref([])

const handleRangeChange = (value) => {
  if (value !== 'custom') {
    const range = calculateDateRange(value)
    timeStore.setDateRange(range.start, range.end)
    saveToLocalStorage(range)
  }
}

const handleCustomChange = (value) => {
  const range = {
    start: value[0],
    end: value[1]
  }
  timeStore.setDateRange(range.start, range.end)
  saveToLocalStorage(range)
}

const calculateDateRange = (rangeType) => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  
  switch (rangeType) {
    case 'today':
      return { start: today, end: today }
    case 'yesterday':
      const yesterday = new Date(today)
      yesterday.setDate(yesterday.getDate() - 1)
      return { start: yesterday, end: yesterday }
    case 'last_7_days':
      const last7 = new Date(today)
      last7.setDate(last7.getDate() - 7)
      return { start: last7, end: today }
    // ... 其他时间范围
  }
}

onMounted(() => {
  // 从localStorage恢复时间范围
  const savedRange = loadFromLocalStorage()
  if (savedRange) {
    selectedRange.value = savedRange.type
    if (savedRange.type === 'custom') {
      customRange.value = [savedRange.start, savedRange.end]
    }
    timeStore.setDateRange(savedRange.start, savedRange.end)
  }
})
</script>
```

**Pinia Store**：

文件路径：`frontend/src/stores/time.js`

```javascript
import { defineStore } from 'pinia'

export const useTimeStore = defineStore('time', {
  state: () => ({
    startDate: null,
    endDate: null
  }),
  
  actions: {
    setDateRange(start, end) {
      this.startDate = start
      this.endDate = end
    }
  },
  
  getters: {
    dateRange: (state) => ({
      start: state.startDate,
      end: state.endDate
    })
  }
})
```

---

### 3.2 数据导出功能

#### 3.2.1 功能需求

**目标功能**：

1. **表格导出**
   - 所有表格支持导出为Excel
   - 支持自定义导出字段
   - 支持导出当前页或全部数据

2. **图表导出**
   - 所有图表支持导出为PNG
   - 支持自定义分辨率

3. **批量导出**
   - 支持同时导出多个报表
   - 打包为ZIP下载

#### 3.2.2 技术实现

**前端实现**：

```javascript
// 导出表格为Excel
const exportTableToExcel = (tableData, fileName) => {
  import('xlsx').then(xlsx => {
    const worksheet = xlsx.utils.json_to_sheet(tableData)
    const workbook = xlsx.utils.book_new()
    xlsx.utils.book_append_sheet(workbook, worksheet, 'Sheet1')
    xlsx.writeFile(workbook, `${fileName}.xlsx`)
  })
}

// 导出图表为PNG
const exportChartToPNG = (chartInstance, fileName) => {
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff'
  })
  const link = document.createElement('a')
  link.download = `${fileName}.png`
  link.href = url
  link.click()
}
```

---

### 3.3 Excel批量导入增强

#### 3.3.1 功能需求

1. **支持ZIP压缩包**
   - 批量上传多个Excel
   - 自动解压和识别

2. **自动合并**
   - 同类型报表自动合并
   - 智能去重

3. **增量导入**
   - 只导入新增数据
   - 避免重复导入

4. **导入预览**
   - 显示数据预览
   - 确认后提交

5. **错误报告**
   - 详细的错误信息
   - 指出具体行列

---

## 四、生产环境必备功能（P2）

### 4.1 用户管理与权限控制

#### 4.1.1 功能需求

1. **用户管理**
   - 添加/删除/禁用用户
   - 用户信息维护

2. **角色管理**
   - 预设角色：老板、运营、推广、客服、财务
   - 自定义角色

3. **权限控制**
   - 查看权限
   - 编辑权限
   - 删除权限
   - 导出权限

4. **操作日志**
   - 记录所有用户操作
   - 登录日志
   - 数据修改日志

#### 4.1.2 数据库设计

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'operator',
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
);

CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    permissions JSON,
    description TEXT
);

CREATE TABLE operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action VARCHAR(50),
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details TEXT,
    ip_address VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

### 4.2 多店铺管理

#### 4.2.1 功能需求

1. **店铺管理**
   - 添加/编辑/删除店铺
   - 店铺基本信息

2. **店铺切换**
   - 顶部快速切换
   - 当前店铺标识

3. **数据隔离**
   - 不同店铺数据独立
   - 店铺ID作为数据筛选条件

4. **跨店铺对比**
   - 多店铺指标对比
   - 排行榜

#### 4.2.2 数据库设计

```sql
CREATE TABLE shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_name VARCHAR(100) NOT NULL,
    shop_type VARCHAR(50),  -- tmall, taobao, jd
    shop_url VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 所有数据表添加 shop_id 字段
ALTER TABLE products ADD COLUMN shop_id INTEGER;
ALTER TABLE orders ADD COLUMN shop_id INTEGER;
-- ...
```

---

### 4.3 数据备份与恢复

#### 4.3.1 功能需求

1. **自动备份**
   - 每天自动备份
   - 保留最近30天备份

2. **手动备份**
   - 随时手动备份
   - 备份备注

3. **备份列表**
   - 查看所有历史备份
   - 备份大小、时间

4. **数据恢复**
   - 从备份恢复
   - 恢复确认

5. **备份下载**
   - 下载备份文件
   - 异地备份

#### 4.3.2 技术实现

```python
import shutil
from datetime import datetime

def create_backup(db_path: str, backup_dir: str):
    """创建数据库备份"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/dashboard_{timestamp}.db"
    
    shutil.copy2(db_path, backup_file)
    
    # 记录备份信息
    backup_record = {
        "file_name": f"dashboard_{timestamp}.db",
        "file_path": backup_file,
        "file_size": os.path.getsize(backup_file),
        "created_at": datetime.now()
    }
    
    return backup_record

def restore_backup(backup_file: str, db_path: str):
    """从备份恢复"""
    # 先备份当前数据库
    current_backup = f"{db_path}.before_restore"
    shutil.copy2(db_path, current_backup)
    
    # 恢复备份
    shutil.copy2(backup_file, db_path)
    
    return {"success": True, "message": "恢复成功"}
```

---

## 五、高级扩展功能（P3）

### 5.1 AI智能分析增强

#### 5.1.1 功能需求

1. **智能导入助手**
   - 自动识别非标准Excel
   - 智能字段映射

2. **自动生成报告**
   - 日报、周报、月报
   - 自动分析关键指标

3. **智能优化建议**
   - 商品优化建议
   - 流量优化建议
   - 推广优化建议

4. **自然语言查询**
   - "上周销售额最高的商品是什么"
   - "本月转化率趋势如何"

#### 5.1.2 技术实现

```python
from openai import OpenAI

class AIAnalysisService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def generate_report(self, data: dict, report_type: str):
        """生成分析报告"""
        prompt = f"""
        基于以下数据生成一份{report_type}报告：
        
        数据：
        {json.dumps(data, ensure_ascii=False, indent=2)}
        
        请包含以下内容：
        1. 核心指标概述
        2. 环比/同比分析
        3. 问题发现
        4. 优化建议
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是一位专业的电商数据分析师"},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def natural_language_query(self, question: str, db: Session):
        """自然语言查询"""
        # 1. 解析问题意图
        intent = self.parse_intent(question)
        
        # 2. 构建查询
        query = self.build_query(intent, db)
        
        # 3. 执行查询
        result = db.execute(query)
        
        # 4. 生成自然语言回答
        answer = self.generate_answer(question, result)
        
        return answer
```

---

### 5.2 消息推送集成

#### 5.2.1 功能需求

1. **钉钉推送**
   - 告警通知
   - 日报周报
   - 任务提醒

2. **企业微信推送**
   - 同钉钉

3. **邮件推送**
   - 重要告警
   - 定期报告

4. **推送配置**
   - 用户自定义接收方式
   - 推送时间设置

#### 5.2.2 技术实现

```python
import requests

class DingTalkNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_message(self, title: str, content: str):
        """发送钉钉消息"""
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }
        
        response = requests.post(
            self.webhook_url,
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        return response.json()

class WeChatNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_message(self, title: str, content: str):
        """发送企业微信消息"""
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"# {title}\n\n{content}"
            }
        }
        
        response = requests.post(
            self.webhook_url,
            json=data
        )
        
        return response.json()
```

---

## 六、开发计划

### 6.1 Week 1（5个工作日）

**目标**：完成第一优先级功能

| 任务 | 预计时间 | 负责人 | 状态 |
|------|----------|--------|------|
| 数据导入中心前端页面 | 2天 | - | 待开始 |
| 全局时间筛选器 | 1天 | - | 待开始 |
| 数据导出功能 | 1天 | - | 待开始 |
| 测试和文档 | 1天 | - | 待开始 |

### 6.2 Week 2-3（10个工作日）

**目标**：完成基础核心功能

| 任务 | 预计时间 | 负责人 | 状态 |
|------|----------|--------|------|
| 商品分析模块 | 3天 | - | 待开始 |
| 流量分析模块 | 3天 | - | 待开始 |
| 推广效果分析增强 | 3天 | - | 待开始 |
| 测试和文档 | 1天 | - | 待开始 |

### 6.3 Week 4-5（10个工作日）

**目标**：完成生产环境必备功能

| 任务 | 预计时间 | 负责人 | 状态 |
|------|----------|--------|------|
| 用户权限管理 | 4天 | - | 待开始 |
| 多店铺管理 | 3天 | - | 待开始 |
| 数据备份恢复 | 2天 | - | 待开始 |
| 测试和文档 | 1天 | - | 待开始 |

### 6.4 Week 6-8（15个工作日）

**目标**：完成高级扩展功能

| 任务 | 预计时间 | 负责人 | 状态 |
|------|----------|--------|------|
| AI智能分析 | 6天 | - | 待开始 |
| 消息推送集成 | 4天 | - | 待开始 |
| 性能优化 | 3天 | - | 待开始 |
| 全面测试 | 2天 | - | 待开始 |

---

## 七、验收标准

### 7.1 功能验收

- [ ] 所有P0功能100%完成
- [ ] 所有P1功能100%完成
- [ ] P2功能至少完成80%
- [ ] P3功能至少完成50%

### 7.2 性能验收

- [ ] API响应时间 < 200ms
- [ ] 页面加载时间 < 3s
- [ ] 支持100+并发用户
- [ ] 数据库查询优化

### 7.3 质量验收

- [ ] 单元测试覆盖率 > 60%
- [ ] 集成测试通过
- [ ] 无严重bug
- [ ] 代码审查通过

### 7.4 文档验收

- [ ] API文档完整
- [ ] 用户手册完整
- [ ] 部署文档完整
- [ ] 运维文档完整

---

## 八、风险评估

### 8.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 数据库性能瓶颈 | 高 | 中 | 优化查询、添加索引、考虑分库分表 |
| API接口不稳定 | 高 | 低 | 完善测试、添加监控 |
| 前端性能问题 | 中 | 中 | 优化加载、懒加载、CDN |

### 8.2 业务风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 需求变更 | 高 | 高 | 敏捷开发、快速迭代 |
| 数据质量问题 | 高 | 中 | 完善校验、数据清洗 |
| 用户接受度低 | 中 | 低 | 用户培训、优化体验 |

---

## 九、后续规划

### 9.1 V1.2 规划（3个月后）

- 移动端适配
- 小程序版本
- 数据大屏
- 高级分析模型

### 9.2 V2.0 规划（6个月后）

- 完整的ERP集成
- 供应链管理
- 财务管理
- CRM功能

---

**文档版本**：V1.1
**最后更新**：2026-05-02
**维护团队**：海贝海数据团队
