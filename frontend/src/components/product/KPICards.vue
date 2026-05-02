<template>
  <el-row :gutter="20" style="margin-top: 20px">
    <el-col :span="6" v-for="kpi in kpis" :key="kpi.key">
      <el-card class="kpi-card">
        <div class="kpi-label">{{ kpi.label }}</div>
        <div class="kpi-value-row">
          <span class="kpi-value">{{ kpi.value }}</span>
          <span v-if="kpi.trend" :class="['kpi-trend', kpi.trend > 0 ? 'trend-up' : 'trend-down']">
            <el-icon v-if="kpi.trend > 0"><CaretTop /></el-icon>
            <el-icon v-else><CaretBottom /></el-icon>
            {{ Math.abs(kpi.trend).toFixed(1) }}%
          </span>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({ kpis: Array })
</script>

<style scoped>
.kpi-card {
  text-align: center;
}
.kpi-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}
.kpi-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}
.kpi-value-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.kpi-trend {
  font-size: 12px;
  display: flex;
  align-items: center;
}
.trend-up {
  color: #67c23a;
}
.trend-down {
  color: #f56c6c;
}
</style>
