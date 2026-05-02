<template>
  <div class="abtest-sop-container">
    <div class="page-header">
      <h1>策略实验场与SOP资产</h1>
      <el-tabs v-model="activeTab" type="card" class="header-tabs">
        <el-tab-pane label="A/B测试" name="abtest"></el-tab-pane>
        <el-tab-pane label="SOP模板" name="sop"></el-tab-pane>
        <el-tab-pane label="营销活动" name="campaign"></el-tab-pane>
      </el-tabs>
    </div>

    <div v-loading="loading" class="content-area">
      <div v-if="activeTab === 'abtest'">
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <div class="card-header">
                <h3>实验列表</h3>
                <el-button type="primary" size="small" @click="showCreateTest = true">
                  <el-icon><Plus /></el-icon> 创建实验
                </el-button>
              </div>
              <el-table :data="tests" style="width: 100%">
                <el-table-column prop="test_name" label="实验名称"></el-table-column>
                <el-table-column prop="test_type" label="实验类型" width="120">
                  <template #default="{ row }">
                    <el-tag size="small">{{ row.test_type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag size="small" :type="getStatusType(row.status)">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="进度" width="250">
                  <template #default="{ row }">
                    <div v-if="row.status === 'finished'">
                      <div v-if="row.has_winner">
                        <el-tag type="success" size="small">胜出: {{ row.winner_variant }}</el-tag>
                        <span style="margin-left: 8px">
                          <el-tag :type="row.is_significant ? 'success' : 'info'" size="small">
                            {{ row.is_significant ? '显著' : '不显著' }}
                          </el-tag>
                        </span>
                      </div>
                    </div>
                    <div v-else>
                      <el-progress :percentage="row.progress || 50" :stroke-width="8" />
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="200" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" @click="viewTest(row)">查看</el-button>
                    <el-button v-if="row.status === 'running'" size="small" type="primary" @click="analyzeTest(row.id)">分析</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </div>
      <div v-else-if="activeTab === 'sop'">
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <div class="card-header">
                <h3>SOP模板库</h3>
                <el-button type="primary" size="small">
                  <el-icon><Plus /></el-icon> 创建SOP
                </el-button>
              </div>
              <el-table :data="sopTemplates" style="width: 100%">
                <el-table-column prop="template_name" label="模板名称" width="200"></el-table-column>
                <el-table-column prop="template_type" label="类型" width="120"></el-table-column>
                <el-table-column prop="category" label="分类" width="120"></el-table-column>
                <el-table-column prop="use_count" label="使用次数" width="100"></el-table-column>
                <el-table-column prop="avg_effectiveness" label="平均效果" width="120">
                  <template #default="{ row }">
                    <el-progress :percentage="row.avg_effectiveness || 0" :color="'#409eff'" style="width: 100px;" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="150" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small">查看</el-button>
                    <el-button size="small" type="primary">使用</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
        </el-row>
      </div>
      <div v-else-if="activeTab === 'campaign'">
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="table-card">
              <div class="card-header">
                <h3>营销活动</h3>
                <el-button type="primary" size="small">
                  <el-icon><Plus /></el-icon> 新建活动
                </el-button>
              </div>
              <el-table :data="campaigns" style="width: 100%">
                <el-table-column prop="project_name" label="活动名称" width="200"></el-table-column>
                <el-table-column prop="project_type" label="类型" width="120"></el-table-column>
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag size="small" :type="getStatusType(row.status)">{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="target_gmv" label="目标GMV" width="150">
                  <template #default="{ row }">¥{{ formatNumber(row.target_gmv) }}</template>
                </el-table-column>
                <el-table-column prop="actual_gmv" label="实际GMV" width="150">
                  <template #default="{ row }">¥{{ formatNumber(row.actual_gmv) }}</template>
                </el-table-column>
                <el-table-column label="完成率" width="120">
                  <template #default="{ row }">
                    <el-progress :percentage="row.completion_rate || 0" :stroke-width="8" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="150" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small">查看</el-button>
                    <el-button size="small" type="primary">复盘</el-button>
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
import { Refresh, Plus from '@element-plus/icons-vue'

const activeTab = ref('abtest')
const loading = ref(false)
const tests = ref([])
const sopTemplates = ref([])
const campaigns = ref([])
const showCreateTest = ref(false)

const refresh = async () => {
  loading.value = true
  try {
    if (activeTab.value === 'abtest') {
      const response = await fetch('/api/abtest-sop/tests')
      if (response.ok) {
        const data = await response.json()
        tests.value = data.tests || []
      } else {
        // 使用模拟数据
        tests.value = [
          { id: 1, test_name: '首图优化测试', test_type: '主图测试', status: 'running', progress: 75, has_winner: false },
          { id: 2, test_name: '人群包测试', test_type: '人群测试', status: 'finished', has_winner: true, winner_variant: 'B组', is_significant: true },
          { id: 3, test_name: '标题关键词测试', test_type: '标题测试', status: 'paused', progress: 40 }
        ]
      }
    } else if (activeTab.value === 'sop') {
      const response = await fetch('/api/abtest-sop/sop-templates')
      if (response.ok) {
        const data = await response.json()
        sopTemplates.value = data.templates || []
      } else {
        sopTemplates.value = [
          { id: 1, template_name: '618大促SOP', template_type: '活动', category: '大促', use_count: 5, avg_effectiveness: 85 },
          { id: 2, template_name: '新品上市SOP', template_type: '推广', category: '新品', use_count: 8, avg_effectiveness: 78 },
          { id: 3, template_name: '日常维护SOP', template_type: '运营', category: '日常', use_count: 20, avg_effectiveness: 90 }
        ]
      }
    } else {
      const response = await fetch('/api/abtest-sop/campaign-projects')
      if (response.ok) {
        const data = await response.json()
        campaigns.value = data.projects || []
      } else {
        campaigns.value = [
          { id: 1, project_name: '55大促', project_type: '大促活动', status: 'finished', target_gmv: 500000, actual_gmv: 480000, completion_rate: 96 },
          { id: 2, project_name: '夏季新品推广', project_type: '推广活动', status: 'running', target_gmv: 300000, actual_gmv: 180000, completion_rate: 60 },
          { id: 3, project_name: '周年庆活动', project_type: '大促活动', status: 'planned', target_gmv: 800000, actual_gmv: 0, completion_rate: 0 }
        ]
      }
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const getStatusType = (status) => {
  const types = { 'draft': 'info', 'running': 'primary', 'finished': 'success', 'planned': 'info', 'paused': 'warning' }
  return types[status] || ''
}

const formatNumber = (num) => {
  if (!num) return '0'
  return num.toLocaleString()
}

const viewTest = (row) => {
  ElMessage.info('查看实验详情')
}

const analyzeTest = (testId) => {
  ElMessage.success('开始分析实验结果')
}

watch(activeTab, () => {
  refresh()
})

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.abtest-sop-container {
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

.el-tabs__header {
  margin: 0;
}

</style>

