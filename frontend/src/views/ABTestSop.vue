<template>
  <div class="abtest-sop-container page-container">
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
                <el-table-column prop="created_at" label="创建时间" width="150"></el-table-column>
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
                <el-table-column label="操作" width="220" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" @click="viewTest(row)" title="查看详情">
                      <el-icon><View /></el-icon>
                    </el-button>
                    <el-button v-if="row.status === 'running'" size="small" type="primary" @click="analyzeTest(row.id)" title="分析结果">
                      <el-icon><VideoPlay /></el-icon> 分析
                    </el-button>
                    <el-button v-if="row.status === 'finished'" size="small" type="success" title="复制结果">
                      <el-icon><CopyDocument /></el-icon>
                    </el-button>
                    <el-button v-if="row.status !== 'running'" size="small" type="danger" @click="deleteTest(row)" title="删除">
                      <el-icon><Delete /></el-icon>
                    </el-button>
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
                <el-table-column prop="updated_at" label="更新时间" width="150"></el-table-column>
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

    <el-dialog v-model="showCreateTest" title="创建A/B实验" width="600px">
      <el-form :model="createTestForm" label-width="100px">
        <el-form-item label="实验名称" prop="test_name">
          <el-input v-model="createTestForm.test_name" placeholder="请输入实验名称" />
        </el-form-item>
        <el-form-item label="实验类型" prop="test_type">
          <el-select v-model="createTestForm.test_type" placeholder="请选择实验类型">
            <el-option label="主图测试" value="主图测试" />
            <el-option label="标题测试" value="标题测试" />
            <el-option label="人群测试" value="人群测试" />
            <el-option label="价格测试" value="价格测试" />
            <el-option label="页面测试" value="页面测试" />
          </el-select>
        </el-form-item>
        <el-form-item label="实验描述" prop="description">
          <el-input v-model="createTestForm.description" type="textarea" placeholder="请输入实验描述" />
        </el-form-item>
        <el-form-item label="实验变体">
          <div class="variants-container">
            <div v-for="(variant, index) in createTestForm.variants" :key="index" class="variant-item">
              <el-input v-model="variant.name" :placeholder="`变体 ${index + 1} 名称`" style="width: 200px" />
              <el-input v-model="variant.weight" type="number" :placeholder="`权重 ${index + 1}`" style="width: 100px" />
              <el-button v-if="createTestForm.variants.length > 2" size="small" type="danger" @click="removeVariant(index)">删除</el-button>
            </div>
            <el-button v-if="createTestForm.variants.length < 5" size="small" @click="addVariant">+ 添加变体</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTest = false">取消</el-button>
        <el-button type="primary" @click="createTest">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, View, VideoPlay, CopyDocument, Delete } from '@element-plus/icons-vue'
import { formatNumber } from '@/utils/format'
import api from '@/api'

const activeTab = ref('abtest')
const loading = ref(false)
const tests = ref([])
const sopTemplates = ref([])
const campaigns = ref([])
const showCreateTest = ref(false)

const createTestForm = ref({
  test_name: '',
  test_type: '',
  description: '',
  variants: [{ name: 'A组', weight: 50 }, { name: 'B组', weight: 50 }]
})

const addVariant = () => {
  const index = createTestForm.value.variants.length + 1
  createTestForm.value.variants.push({ name: `${String.fromCharCode(64 + index)}组`, weight: Math.round(100 / (index + 1)) })
}

const removeVariant = (index) => {
  createTestForm.value.variants.splice(index, 1)
}

const refresh = async () => {
  loading.value = true
  try {
    if (activeTab.value === 'abtest') {
      const res = await api.abtestSopApi.getTests()
      tests.value = res.data?.tests || res?.tests || []
    } else if (activeTab.value === 'sop') {
      const res = await api.abtestSopApi.getSopTemplates()
      sopTemplates.value = res.data?.templates || res?.templates || []
    } else {
      const res = await api.abtestSopApi.getCampaignProjects()
      campaigns.value = res.data?.projects || res?.projects || []
    }
  } catch (error) {
    console.error('加载数据失败:', error)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const getStatusType = (status) => {
  const types = { 'draft': 'info', 'running': 'primary', 'finished': 'success', 'planned': 'info', 'paused': 'warning' }
  return types[status] || ''
}

const viewTest = (row) => {
  ElMessage.info(`查看实验: ${row.test_name}`)
}

const analyzeTest = async (testId) => {
  try {
    await api.abtestSopApi.analyzeTest(testId)
    ElMessage.success('分析完成')
    refresh()
  } catch (error) {
    ElMessage.error('分析失败')
  }
}

const createTest = async () => {
  try {
    await api.abtestSopApi.createTest(createTestForm.value)
    ElMessage.success('创建成功')
    showCreateTest.value = false
    createTestForm.value = { test_name: '', test_type: '', description: '', variants: [] }
    refresh()
  } catch (error) {
    ElMessage.error('创建失败')
  }
}

const deleteTest = async (test) => {
  try {
    await ElMessageBox.confirm(`确定删除实验"${test.test_name}"？`, '确认删除', { type: 'warning' })
    await api.request.delete(`/abtest-sop/tests/${test.id}`)
    ElMessage.success('删除成功')
    refresh()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
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

