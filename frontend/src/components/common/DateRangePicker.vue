<template>
  <div class="date-range-picker">
    <el-date-picker
      v-model="dateRange"
      type="daterange"
      :shortcuts="shortcuts"
      range-separator="至"
      start-placeholder="开始日期"
      end-placeholder="结束日期"
      format="YYYY-MM-DD"
      value-format="YYYY-MM-DD"
      :clearable="clearable"
      @change="handleChange"
      class="date-range-picker-input"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  clearable: { type: Boolean, default: true },
  defaultDays: { type: Number, default: 30 },
})

const emit = defineEmits(['update:modelValue', 'change'])

const dateRange = ref(props.modelValue.length ? props.modelValue : getDefaultRange())

const shortcuts = [
  { text: '最近7天', value: () => { const end = new Date(); const start = new Date(); start.setTime(start.getTime() - 3600 * 1000 * 24 * 7); return [start, end] } },
  { text: '最近30天', value: () => { const end = new Date(); const start = new Date(); start.setTime(start.getTime() - 3600 * 1000 * 24 * 30); return [start, end] } },
  { text: '本月', value: () => { const end = new Date(); const start = new Date(); start.setDate(1); return [start, end] } },
  { text: '上月', value: () => { const end = new Date(); const start = new Date(); start.setMonth(start.getMonth() - 1); start.setDate(1); end.setDate(0); return [start, end] } },
  { text: '最近90天', value: () => { const end = new Date(); const start = new Date(); start.setTime(start.getTime() - 3600 * 1000 * 24 * 90); return [start, end] } },
]

function getDefaultRange() {
  const end = new Date()
  const start = new Date()
  start.setTime(start.getTime() - 3600 * 1000 * 24 * props.defaultDays)
  return [formatDate(start), formatDate(end)]
}

function formatDate(d) {
  return d.toISOString().slice(0, 10)
}

function handleChange(val) {
  emit('update:modelValue', val)
  emit('change', val)
}

watch(() => props.modelValue, (val) => {
  if (val && val.length) dateRange.value = val
})
</script>

<style scoped>
.date-range-picker-input {
  width: 280px;
}
</style>
