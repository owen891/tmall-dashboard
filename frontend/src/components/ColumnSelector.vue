<template>
  <div class="column-selector">
    <el-drawer
      v-model="visible"
      title="字段设置"
      size="550px"
      direction="rtl"
    >
      <div class="drawer-content">
        <div class="search-section">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索字段..."
            clearable
            size="default"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="template-section">
          <div class="section-header">
            <span>模板</span>
            <el-button size="small" @click="showSaveTemplate = true">保存当前</el-button>
          </div>
          <div class="template-list">
            <el-select v-model="currentTemplate" placeholder="选择模板" size="default" @change="applyTemplate">
              <el-option
                v-for="tpl in templates"
                :key="tpl.id"
                :label="tpl.name"
                :value="tpl.id"
              />
            </el-select>
            <el-button
              v-if="currentTemplate && !isDefaultTemplate"
              size="small"
              type="danger"
              @click="deleteTemplate"
            >
              删除
            </el-button>
          </div>
        </div>

        <el-divider />

        <div class="fields-section">
          <div class="section-header">
            <span>字段列表 ({{ filteredFieldCount }} / {{ totalFieldCount }})</span>
            <div class="header-actions">
              <el-select v-model="sortMode" size="small" style="width: 120px">
                <el-option label="默认顺序" value="default" />
                <el-option label="按名称排序" value="name" />
                <el-option label="按分类折叠" value="category" />
              </el-select>
              <el-button size="small" @click="checkAll">全选</el-button>
              <el-button size="small" @click="uncheckAll">取消全选</el-button>
            </div>
          </div>

          <div v-for="category in sortedCategories" :key="category.key" class="category-group">
            <div class="category-header" @click="toggleCategory(category.key)">
              <el-checkbox
                :model-value="isCategoryAllSelected(category)"
                :indeterminate="isCategoryPartiallySelected(category)"
                @change="(val) => toggleCategoryAll(category, val)"
                @click.stop
              >
                {{ category.label }} ({{ getFilteredFields(category).length }})
              </el-checkbox>
              <el-icon class="toggle-icon">
                <ArrowDown v-if="expandedCategories[category.key]" />
                <ArrowRight v-else />
              </el-icon>
            </div>

            <div v-show="expandedCategories[category.key]" class="category-fields">
              <el-checkbox
                v-for="field in getFilteredFields(category)"
                :key="field.key"
                v-model="selectedFields"
                :label="field.key"
                :value="field.key"
                @change="updateConfig"
              >
                {{ field.label }}
                <span class="field-key">{{ field.key }}</span>
              </el-checkbox>
            </div>
          </div>
        </div>
      </div>

      <div class="drawer-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="confirmSelection">确定</el-button>
      </div>
    </el-drawer>

    <el-dialog v-model="showSaveTemplate" title="保存模板" width="400px">
      <el-form>
        <el-form-item label="模板名称">
          <el-input v-model="newTemplateName" placeholder="请输入模板名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveTemplate = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowRight, Search } from '@element-plus/icons-vue'
import {
  fieldCategories,
  defaultTemplates,
  loadTemplates,
  saveCustomTemplate,
  deleteCustomTemplate as deleteTemplateFromStorage,
  saveColumnConfig,
  loadColumnConfig,
  getFieldConfig
} from '@/config/columns'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const visible = ref(false)
const selectedFields = ref([...props.modelValue])
const expandedCategories = ref({})
const templates = ref([])
const currentTemplate = ref(null)
const showSaveTemplate = ref(false)
const newTemplateName = ref('')
const searchKeyword = ref('')
const sortMode = ref('default')

const totalFieldCount = computed(() => {
  return fieldCategories.reduce((sum, cat) => sum + cat.fields.length, 0)
})

const filteredFieldCount = computed(() => {
  return fieldCategories.reduce((sum, cat) => sum + getFilteredFields(cat).length, 0)
})

const isDefaultTemplate = computed(() => {
  return defaultTemplates.some(t => t.id === currentTemplate.value)
})

const sortedCategories = computed(() => {
  let cats = [...fieldCategories]
  
  if (sortMode.value === 'name') {
    cats = cats.sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'))
  } else if (sortMode.value === 'category') {
    cats = cats.sort((a, b) => {
      const aCount = getFilteredFields(a).length
      const bCount = getFilteredFields(b).length
      if (aCount === 0) return 1
      if (bCount === 0) return -1
      return bCount - aCount
    })
  }
  
  return cats
})

function getFilteredFields(category) {
  if (!searchKeyword.value.trim()) {
    return category.fields
  }
  const keyword = searchKeyword.value.toLowerCase()
  return category.fields.filter(f => 
    f.label.toLowerCase().includes(keyword) || 
    f.key.toLowerCase().includes(keyword)
  )
}

watch(() => props.modelValue, (newVal) => {
  selectedFields.value = [...newVal]
})

watch(visible, (val) => {
  if (val) {
    loadData()
  }
})

watch(searchKeyword, () => {
  fieldCategories.forEach(cat => {
    const filtered = getFilteredFields(cat)
    if (filtered.length > 0 && !expandedCategories.value[cat.key]) {
      expandedCategories.value[cat.key] = true
    }
  })
})

function loadData() {
  selectedFields.value = [...props.modelValue]
  templates.value = loadTemplates()
  const config = loadColumnConfig()
  if (config.template) {
    currentTemplate.value = config.template
  }
  expandedCategories.value = {}
  fieldCategories.forEach(cat => {
    expandedCategories.value[cat.key] = true
  })
}

function toggleCategory(key) {
  expandedCategories.value[key] = !expandedCategories.value[key]
}

function isCategoryAllSelected(category) {
  const filteredFields = getFilteredFields(category)
  return filteredFields.every(f => selectedFields.value.includes(f.key))
}

function isCategoryPartiallySelected(category) {
  const filteredFields = getFilteredFields(category)
  const selected = filteredFields.filter(f => selectedFields.value.includes(f.key))
  return selected.length > 0 && selected.length < filteredFields.length
}

function toggleCategoryAll(category, checked) {
  const filteredFields = getFilteredFields(category)
  if (checked) {
    filteredFields.forEach(f => {
      if (!selectedFields.value.includes(f.key)) {
        selectedFields.value.push(f.key)
      }
    })
  } else {
    selectedFields.value = selectedFields.value.filter(
      key => !filteredFields.some(f => f.key === key)
    )
  }
}

function checkAll() {
  selectedFields.value = fieldCategories.flatMap(cat => cat.fields.map(f => f.key))
}

function uncheckAll() {
  selectedFields.value = []
}

function applyTemplate(templateId) {
  const tpl = templates.value.find(t => t.id === templateId)
  if (tpl) {
    selectedFields.value = [...tpl.fields]
    currentTemplate.value = templateId
  }
}

function saveTemplate() {
  if (!newTemplateName.value.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }
  const templateId = `custom_${Date.now()}`
  const template = {
    id: templateId,
    name: newTemplateName.value.trim(),
    fields: [...selectedFields.value]
  }
  const success = saveCustomTemplate(template)
  if (success) {
    templates.value = loadTemplates()
    currentTemplate.value = templateId
    showSaveTemplate.value = false
    newTemplateName.value = ''
    ElMessage.success('模板保存成功')
  } else {
    ElMessage.error('模板保存失败')
  }
}

function deleteTemplate() {
  if (currentTemplate.value && !isDefaultTemplate.value) {
    deleteTemplateFromStorage(currentTemplate.value)
    templates.value = loadTemplates()
    currentTemplate.value = null
    ElMessage.success('模板删除成功')
  }
}

function updateConfig() {
  emit('update:modelValue', [...selectedFields.value])
}

function confirmSelection() {
  const config = {
    visibleFields: [...selectedFields.value],
    template: currentTemplate.value
  }
  saveColumnConfig(config)
  emit('update:modelValue', [...selectedFields.value])
  emit('change', [...selectedFields.value])
  visible.value = false
  ElMessage.success('字段配置已更新')
}

function open() {
  visible.value = true
}

defineExpose({ open })
</script>

<style scoped>
.drawer-content {
  padding: 0 20px;
  height: calc(100vh - 140px);
  overflow-y: auto;
}

.search-section {
  margin-bottom: 20px;
}

.template-section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.template-list {
  display: flex;
  gap: 10px;
}

.template-list .el-select {
  flex: 1;
}

.fields-section {
  margin-top: 20px;
}

.category-group {
  margin-bottom: 15px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background: #f5f7fa;
  cursor: pointer;
  user-select: none;
}

.category-header:hover {
  background: #ecf5ff;
}

.toggle-icon {
  font-size: 14px;
  color: #909399;
}

.category-fields {
  padding: 15px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.category-fields .el-checkbox {
  margin-right: 0;
}

.field-key {
  margin-left: 8px;
  font-size: 11px;
  color: #909399;
  font-family: monospace;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #e4e7ed;
}
</style>
