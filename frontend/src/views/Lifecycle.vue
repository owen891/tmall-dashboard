<template>
  <div class="lifecycle-analysis">
    <el-card class="filter-card">
      <div class="filter-row">
        <div class="filter-group">
          <span class="filter-label">选择周期:</span>
          <el-select v-model="selectedCycle" size="small" class="cycle-select">
            <el-option label="日" value="day" />
            <el-option label="周" value="week" />
            <el-option label="月" value="month" />
          </el-select>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">商品状态:</span>
          <el-select v-model="selectedStatus" size="small" class="status-select">
            <el-option label="全部" value="all" />
            <el-option label="新品" value="new" />
            <el-option label="成长" value="growing" />
            <el-option label="成熟" value="mature" />
            <el-option label="衰退" value="declining" />
          </el-select>
        </div>
        
        <div class="filter-group">
          <span class="filter-label">渠道:</span>
          <el-select v-model="selectedChannel" size="small" class="channel-select">
            <el-option label="全部" value="all" />
            <el-option label="淘系" value="taobao" />
            <el-option label="京东" value="jd" />
            <el-option label="拼多多" value="pinduoduo" />
          </el-select>
        </div>
        
        <div class="filter-group">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            size="small"
          />
        </div>
        
        <el-button type="primary" size="small" @click="refreshData">刷新数据</el-button>
      </div>
    </el-card>

    <div class="chart-row">
      <el-card class="chart-card">
        <template #header>生命周期分布</template>
        <div ref="distributionChartRef" class="chart-container"></div>
      </el-card>
      
      <el-card class="chart-card">
        <template #header>各阶段占比</template>
        <div ref="pieChartRef" class="chart-container"></div>
      </el-card>
    </div>

    <div class="stats-row">
      <el-card class="stat-card">
        <div class="stat-icon new-icon">
          <el-icon size="24"><Star /></el-icon>
        </div>
        <div class="stat-info">
          <p class="stat-value">{{ lifecycleStats.new }}</p>
          <p class="stat-label">新品数量</p>
        </div>
      </el-card>
      
      <el-card class="stat-card">
        <div class="stat-icon growing-icon">
          <el-icon size="24"><ArrowUp /></el-icon>
        </div>
        <div class="stat-info">
          <p class="stat-value">{{ lifecycleStats.growing }}</p>
          <p class="stat-label">成长中</p>
        </div>
      </el-card>
      
      <el-card class="stat-card">
        <div class="stat-icon mature-icon">
          <el-icon size="24"><Sunny /></el-icon>
        </div>
        <div class="stat-info">
          <p class="stat-value">{{ lifecycleStats.mature }}</p>
          <p class="stat-label">成熟期</p>
        </div>
      </el-card>
      
      <el-card class="stat-card">
        <div class="stat-icon declining-icon">
          <el-icon size="24"><ArrowDown /></el-icon>
        </div>
        <div class="stat-info">
          <p class="stat-value">{{ lifecycleStats.declining }}</p>
          <p class="stat-label">衰退期</p>
        </div>
      </el-card>
    </div>

    <el-card class="detail-card">
      <template #header>商品生命周期详情</template>
      <div class="detail-tabs">
        <el-tabs v-model="activeTab" type="card">
          <el-tab-pane label="新品" name="new">
            <el-table :data="newProducts" stripe size="small">
              <el-table-column prop="name" label="商品名称" min-width="200" />
              <el-table-column prop="category" label="类目" width="100" />
              <el-table-column prop="days" label="上架天数" width="100" align="center" />
              <el-table-column prop="sales" label="销量" width="100" align="right">
                <template #default="{ row }">{{ row.sales.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="growth" label="日增长" width="100" align="right">
                <template #default="{ row }">
                  <span :class="row.growth > 0 ? 'text-success' : 'text-danger'">
                    {{ row.growth > 0 ? '+' : '' }}{{ row.growth }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag type="primary">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          
          <el-tab-pane label="成长" name="growing">
            <el-table :data="growingProducts" stripe size="small">
              <el-table-column prop="name" label="商品名称" min-width="200" />
              <el-table-column prop="category" label="类目" width="100" />
              <el-table-column prop="days" label="上架天数" width="100" align="center" />
              <el-table-column prop="sales" label="销量" width="100" align="right">
                <template #default="{ row }">{{ row.sales.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="growth" label="日增长" width="100" align="right">
                <template #default="{ row }">
                  <span :class="row.growth > 0 ? 'text-success' : 'text-danger'">
                    {{ row.growth > 0 ? '+' : '' }}{{ row.growth }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag type="success">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          
          <el-tab-pane label="成熟" name="mature">
            <el-table :data="matureProducts" stripe size="small">
              <el-table-column prop="name" label="商品名称" min-width="200" />
              <el-table-column prop="category" label="类目" width="100" />
              <el-table-column prop="days" label="上架天数" width="100" align="center" />
              <el-table-column prop="sales" label="销量" width="100" align="right">
                <template #default="{ row }">{{ row.sales.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="growth" label="日增长" width="100" align="right">
                <template #default="{ row }">
                  <span :class="row.growth >= 0 ? 'text-success' : 'text-danger'">
                    {{ row.growth > 0 ? '+' : '' }}{{ row.growth }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag type="warning">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          
          <el-tab-pane label="衰退" name="declining">
            <el-table :data="decliningProducts" stripe size="small">
              <el-table-column prop="name" label="商品名称" min-width="200" />
              <el-table-column prop="category" label="类目" width="100" />
              <el-table-column prop="days" label="上架天数" width="100" align="center" />
              <el-table-column prop="sales" label="销量" width="100" align="right">
                <template #default="{ row }">{{ row.sales.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="growth" label="日增长" width="100" align="right">
                <template #default="{ row }">
                  <span :class="row.growth >= 0 ? 'text-success' : 'text-danger'">
                    {{ row.growth > 0 ? '+' : '' }}{{ row.growth }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag type="danger">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { Star, ArrowUp, Sunny, ArrowDown } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const selectedCycle = ref('week')
const selectedStatus = ref('all')
const selectedChannel = ref('all')
const dateRange = ref([])
const activeTab = ref('new')

const lifecycleStats = ref({
  new: 28,
  growing: 45,
  mature: 32,
  declining: 15
})

const newProducts = ref([
  { id: 1, name: '2024夏季新款连衣裙', category: '女装', days: 7, sales: 156, growth: 25.3, status: '新品' },
  { id: 2, name: '纯棉印花短袖T恤', category: '男装', days: 12, sales: 234, growth: 18.7, status: '新品' },
  { id: 3, name: '韩版宽松休闲裤', category: '女装', days: 5, sales: 89, growth: 32.1, status: '新品' },
  { id: 4, name: '透气网面运动鞋', category: '鞋靴', days: 15, sales: 312, growth: 15.4, status: '新品' }
])

const growingProducts = ref([
  { id: 5, name: '高腰阔腿牛仔裤', category: '女装', days: 35, sales: 856, growth: 12.5, status: '成长中' },
  { id: 6, name: '百搭小白鞋', category: '鞋靴', days: 42, sales: 1234, growth: 8.3, status: '成长中' },
  { id: 7, name: '简约双肩包', category: '箱包', days: 28, sales: 567, growth: 15.8, status: '成长中' },
  { id: 8, name: '防晒冰袖套装', category: '配饰', days: 38, sales: 987, growth: 9.6, status: '成长中' }
])

const matureProducts = ref([
  { id: 9, name: '经典POLO衫', category: '男装', days: 120, sales: 2580, growth: 2.1, status: '成熟期' },
  { id: 10, name: '商务休闲皮鞋', category: '鞋靴', days: 156, sales: 1890, growth: -1.2, status: '成熟期' },
  { id: 11, name: '纯棉四件套', category: '家纺', days: 98, sales: 1560, growth: 1.8, status: '成熟期' },
  { id: 12, name: '智能手表', category: '数码', days: 142, sales: 3250, growth: 0.5, status: '成熟期' }
])

const decliningProducts = ref([
  { id: 13, name: '冬季保暖羽绒服', category: '女装', days: 280, sales: 320, growth: -15.3, status: '衰退期' },
  { id: 14, name: '加绒保暖内衣', category: '内衣', days: 312, sales: 180, growth: -18.7, status: '衰退期' },
  { id: 15, name: '雪地靴', category: '鞋靴', days: 265, sales: 450, growth: -12.4, status: '衰退期' },
  { id: 16, name: '羊毛围巾', category: '配饰', days: 298, sales: 230, growth: -20.1, status: '衰退期' }
])

const distributionChartRef = ref(null)
const pieChartRef = ref(null)
let distributionChart = null
let pieChart = null

const refreshData = () => {
  console.log('Refreshing data...')
}

const initCharts = () => {
  if (distributionChartRef.value) {
    distributionChart = echarts.init(distributionChartRef.value)
    const distOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      legend: {
        data: ['新品', '成长', '成熟', '衰退']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['1月', '2月', '3月', '4月', '5月']
      },
      yAxis: {
        type: 'value'
      },
      series: [
        { name: '新品', type: 'bar', data: [15, 20, 18, 22, 28] },
        { name: '成长', type: 'bar', data: [35, 38, 40, 42, 45] },
        { name: '成熟', type: 'bar', data: [45, 42, 38, 35, 32] },
        { name: '衰退', type: 'bar', data: [12, 15, 18, 16, 15] }
      ]
    }
    distributionChart.setOption(distOption)
  }
  
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    const pieOption = {
      tooltip: {
        trigger: 'item'
      },
      legend: {
        orient: 'vertical',
        left: 'left'
      },
      series: [
        {
          name: '生命周期',
          type: 'pie',
          radius: '50%',
          data: [
            { value: lifecycleStats.value.new, name: '新品', itemStyle: { color: '#67c23a' } },
            { value: lifecycleStats.value.growing, name: '成长', itemStyle: { color: '#409eff' } },
            { value: lifecycleStats.value.mature, name: '成熟', itemStyle: { color: '#e6a23c' } },
            { value: lifecycleStats.value.declining, name: '衰退', itemStyle: { color: '#f56c6c' } }
          ],
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    }
    pieChart.setOption(pieOption)
  }
  
  window.addEventListener('resize', () => {
    distributionChart?.resize()
    pieChart?.resize()
  })
}

onMounted(() => {
  nextTick(() => initCharts())
})
</script>

<style scoped>
.lifecycle-analysis {
  padding-bottom: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: #606266;
}

.cycle-select, .status-select, .channel-select {
  width: 120px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-card {
  min-height: 350px;
}

.chart-container {
  height: 280px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.new-icon {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: #fff;
}

.growing-icon {
  background: linear-gradient(135deg, #409eff 0%, #67b8ff 100%);
  color: #fff;
}

.mature-icon {
  background: linear-gradient(135deg, #e6a23c 0%, #f0c78a 100%);
  color: #fff;
}

.declining-icon {
  background: linear-gradient(135deg, #f56c6c 0%, #f89898 100%);
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin: 0;
}

.detail-card {
  min-height: 400px;
}

.detail-tabs {
  padding-top: 16px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}
</style>
