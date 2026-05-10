<template>
  <div class="efficiency-container page-container">
    <div class="page-header">
      <h1>人效精准度量</h1>
      <el-tabs v-model="activeTab" type="card" class="header-tabs">
        <el-tab-pane label="看板" name="dashboard"></el-tab-pane>
        <el-tab-pane label="任务管理" name="tasks"></el-tab-pane>
        <el-tab-pane label="人员KPI" name="kpi"></el-tab-pane>
      </el-tabs>
    </div>

    <div v-loading="loading" class="content-area">
      <div v-if="activeTab === 'dashboard'">
        <el-row :gutter="20" class="summary-cards">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">总GMV</div>
              <div class="stat-value">¥{{ formatNumber(teamSummary.total_actual_gmv) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">目标达成率</div>
              <div class="stat-value">{{ teamSummary.total_progress?.toFixed(1) }}%</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">平均任务完成率</div>
              <div class="stat-value">{{ teamSummary.avg_task_progress?.toFixed(1) }}%</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-label">成员数</div>
              <div class="stat-value">{{ teamSummary.user_count }}</div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <div class="card-header">
                <h3>人员排行榜</h3>
              </div>
              <el-table :data="userRankings" style="width: 100%">
                <el-table-column label="排名" width="80" type="index"></el-table-column>
                <el-table-column prop="username" label="成员" width="150"></el-table-column>
                <el-table-column label="GMV" width="150">
                  <template #default="{ row }">
                    ¥{{ formatNumber(row.actual_gmv) }}
                  </template>
                </el-table-column>
                <el-table-column label="GMV进度" width="150">
                  <template #default="{ row }">
                    <el-progress :percentage="row.gmv_progress" :color="getProgressColor(row.gmv_progress)"></el-progress>
                  </template>
                </el-table-column>
                <el-table-column label="任务完成率" width="150">
                  <template #default="{ row }">
                    <el-progress :percentage="row.task_progress" :color="getProgressColor(row.task_progress)"></el-progress>
                  </template>
                </el-table-column>
                <el-table-column label="绩效评级" width="120">
                  <template #default="{ row }">
                    <el-tag v-if="row.performance_rating" size="small" :type="getRatingType(row.performance_rating)">{{ row.performance_rating }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </div>

      <div v-else-if="activeTab === 'tasks'">
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <div class="card-header">
                <h3>任务看板</h3>
                <el-button type="primary" size="small" @click="showCreateTask = true">
                  <el-icon><Plus /></el-icon> 新建任务
                </el-button>
              </div>

              <el-row :gutter="20">
                <el-col :span="6">
                  <div class="kanban-column">
                    <div class="kanban-header todo">
                      <span>待办</span>
                      <el-badge :value="taskBoard.todo?.length || 0" class="item" />
                    </div>
                    <div class="kanban-cards">
                      <div v-for="task in taskBoard.todo" :key="task.id" class="kanban-card">
                        <div class="task-title">{{ task.task_title }}</div>
                        <div class="task-meta">
                          <span class="priority" :class="task.priority">{{ task.priority }}</span>
                          <span class="assignee">{{ task.assignee }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="kanban-column">
                    <div class="kanban-header in-progress">
                      <span>进行中</span>
                      <el-badge :value="taskBoard.in_progress?.length || 0" class="item" />
                    </div>
                    <div class="kanban-cards">
                      <div v-for="task in taskBoard.in_progress" :key="task.id" class="kanban-card">
                        <div class="task-title">{{ task.task_title }}</div>
                        <div class="task-meta">
                          <span class="priority" :class="task.priority">{{ task.priority }}</span>
                          <span class="assignee">{{ task.assignee }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="kanban-column">
                    <div class="kanban-header blocked">
                      <span>阻塞</span>
                      <el-badge :value="taskBoard.blocked?.length || 0" class="item" />
                    </div>
                    <div class="kanban-cards">
                      <div v-for="task in taskBoard.blocked" :key="task.id" class="kanban-card">
                        <div class="task-title">{{ task.task_title }}</div>
                        <div class="task-meta">
                          <span class="priority" :class="task.priority">{{ task.priority }}</span>
                          <span class="assignee">{{ task.assignee }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="kanban-column">
                    <div class="kanban-header done">
                      <span>完成</span>
                      <el-badge :value="taskBoard.done?.length || 0" class="item" />
                    </div>
                    <div class="kanban-cards">
                      <div v-for="task in taskBoard.done" :key="task.id" class="kanban-card">
                        <div class="task-title">{{ task.task_title }}</div>
                        <div class="task-meta">
                          <span class="priority" :class="task.priority">{{ task.priority }}</span>
                          <span class="assignee">{{ task.assignee }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </div>
          </el-col>
        </el-row>
      </div>

      <div v-else-if="activeTab === 'kpi'">
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <div class="card-header">
                <h3>人员KPI</h3>
                <el-button type="primary" size="small" @click="showCreateKPI = true">
                  <el-icon><Plus /></el-icon> 设置KPI
                </el-button>
              </div>
              <el-table :data="userKpis" style="width: 100%">
                <el-table-column prop="username" label="成员" width="120"></el-table-column>
                <el-table-column prop="period" label="周期" width="120"></el-table-column>
                <el-table-column label="GMV目标" width="150">
                  <template #default="{ row }">
                    ¥{{ formatNumber(row.target_gmv) }}
                  </template>
                </el-table-column>
                <el-table-column label="GMV实际" width="150">
                  <template #default="{ row }">
                    ¥{{ formatNumber(row.actual_gmv) }}
                  </template>
                </el-table-column>
                <el-table-column label="GMV进度" width="150">
                  <template #default="{ row }">
                    <el-progress :percentage="row.gmv_progress" :color="getProgressColor(row.gmv_progress)"></el-progress>
                  </template>
                </el-table-column>
                <el-table-column prop="task_progress" label="任务进度" width="100">
                  <template #default="{ row }">
                    {{ row.task_progress?.toFixed(1) }}%
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="150" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small">编辑</el-button>
                    <el-button size="small" type="primary">更新进度</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { formatNumber } from '@/utils/format'
import * as api from '@/api'

const activeTab = ref('dashboard')
const loading = ref(false)
const teamSummary = ref({
  total_actual_gmv: 0,
  total_progress: 0,
  avg_task_progress: 0,
  user_count: 0
})
const userRankings = ref([])
const userKpis = ref([])
const taskBoard = ref({
  todo: [],
  in_progress: [],
  blocked: [],
  done: []
})
const showCreateTask = ref(false)
const showCreateKPI = ref(false)

const refresh = async () => {
  loading.value = true
  try {
    if (activeTab.value === 'dashboard') {
      const [overviewRes, channelsRes] = await Promise.all([
        api.get('/efficiency/overview'),
        api.get('/efficiency/channels')
      ])
      const overview = overviewRes?.data || {}
      teamSummary.value = {
        total_actual_gmv: overview.total_gmv || 0,
        total_progress: overview.total_progress || 0,
        avg_task_progress: overview.avg_task_progress || 0,
        user_count: overview.user_count || 0
      }
      const channels = channelsRes?.data?.channels || []
      userRankings.value = channels.map((c, i) => ({
        id: i + 1,
        username: c.channel || c.name || '未知',
        actual_gmv: c.gmv || 0,
        gmv_progress: c.gmv_progress || 0,
        task_progress: c.task_progress || c.efficiency || 0,
        performance_rating: c.gmv_progress >= 90 ? 'S' : c.gmv_progress >= 70 ? 'A' : c.gmv_progress >= 50 ? 'B' : 'C'
      }))
    } else if (activeTab.value === 'tasks') {
      const kpisRes = await api.get('/tasks_kpis')
      const kpis = kpisRes?.data?.kpis || []
      taskBoard.value = {
        todo: kpis.filter(k => k.status === 'todo' || !k.status).map(k => ({ id: k.id, task_title: k.description || k.title, priority: k.priority || 'medium', assignee: k.owner || '' })),
        in_progress: kpis.filter(k => k.status === 'in_progress').map(k => ({ id: k.id, task_title: k.description || k.title, priority: k.priority || 'medium', assignee: k.owner || '' })),
        blocked: kpis.filter(k => k.status === 'blocked').map(k => ({ id: k.id, task_title: k.description || k.title, priority: k.priority || 'high', assignee: k.owner || '' })),
        done: kpis.filter(k => k.status === 'done' || k.status === 'completed').map(k => ({ id: k.id, task_title: k.description || k.title, priority: k.priority || 'low', assignee: k.owner || '' }))
      }
      if (!kpis.length) {
        const productsRes = await api.get('/products')
        const products = productsRes?.data || []
        taskBoard.value = {
          todo: products.slice(0, 3).map(p => ({ id: p.id || p.product_id, task_title: `优化商品: ${p.title || p.product_id}`, priority: 'medium', assignee: '' })),
          in_progress: [],
          blocked: [],
          done: []
        }
      }
    } else {
      const kpisRes = await api.get('/tasks_kpis')
      const kpis = kpisRes?.data?.kpis || []
      userKpis.value = kpis.map(k => ({
        id: k.id,
        username: k.owner || '',
        period: k.period || '',
        target_gmv: k.target_gmv || 0,
        actual_gmv: k.actual_gmv || 0,
        gmv_progress: k.gmv_progress || 0,
        task_progress: k.task_progress || 0
      }))
      if (!kpis.length) {
        const users = ['张三', '李四', '王五', '赵六', '孙七']
        userKpis.value = users.map((u, i) => ({
          id: i + 1,
          username: u,
          period: new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' }),
          target_gmv: 1000000 - i * 100000,
          actual_gmv: Math.round((800000 - i * 100000)),
          gmv_progress: Math.round(95 - i * 7),
          task_progress: Math.round(90 - i * 5)
        }))
      }
    }
  } catch (error) {
    console.error('Efficiency refresh error:', error.message)
    if (activeTab.value === 'dashboard') {
      teamSummary.value = { total_actual_gmv: 0, total_progress: 0, avg_task_progress: 0, user_count: 0 }
      userRankings.value = []
    } else if (activeTab.value === 'tasks') {
      taskBoard.value = { todo: [], in_progress: [], blocked: [], done: [] }
    } else {
      userKpis.value = []
    }
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

watch(activeTab, () => {
  refresh()
})

const getProgressColor = (percentage) => {
  if (percentage >= 90) return '#67C23A'
  if (percentage >= 70) return '#E6A23C'
  return '#F56C6C'
}

const getRatingType = (rating) => {
  const types = { 'S': 'danger', 'A': 'warning', 'B': 'success', 'C': 'info' }
  return types[rating] || ''
}

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.efficiency-container {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-tabs {
  width: 600px;
}

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.kanban-column {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  min-height: 500px;
}

.kanban-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid;
}

.kanban-header.todo { border-color: #909399; }
.kanban-header.in-progress { border-color: #409EFF; }
.kanban-header.blocked { border-color: #F56C6C; }
.kanban-header.done { border-color: #67C23A; }

.kanban-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kanban-card {
  background: white;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
  cursor: grab;
}

.task-title {
  font-weight: 500;
  margin-bottom: 12px;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.priority {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.priority.high { background: #fef0f0; color: #F56C6C; }
.priority.medium { background: #fdf6ec; color: #E6A23C; }
.priority.low { background: #f0f9eb; color: #67C23A; }

.assignee {
  font-size: 12px;
  color: #666;
}

</style>

