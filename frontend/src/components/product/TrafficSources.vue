<template>
  <div class="traffic-sources">
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="source-item">
          <span class="source-label">搜索访客</span>
          <div class="source-bar-wrap">
            <div class="source-bar" :style="{ width: getTrafficPercent('search') + '%' }"></div>
          </div>
          <span class="source-value">{{ formatNumber(data.search_ipv) }} ({{ getTrafficPercent('search') }}%)</span>
        </div>
        <div class="source-item">
          <span class="source-label">推荐访客</span>
          <div class="source-bar-wrap">
            <div class="source-bar bar-recommend" :style="{ width: getTrafficPercent('recommend') + '%' }"></div>
          </div>
          <span class="source-value">{{ formatNumber(data.recommend_ipv) }} ({{ getTrafficPercent('recommend') }}%)</span>
        </div>
        <div class="source-item">
          <span class="source-label">付费访客</span>
          <div class="source-bar-wrap">
            <div class="source-bar bar-paid" :style="{ width: getTrafficPercent('paid') + '%' }"></div>
          </div>
          <span class="source-value">{{ formatNumber(data.paid_ipv) }} ({{ getTrafficPercent('paid') }}%)</span>
        </div>
        <div class="source-item">
          <span class="source-label">自然访客</span>
          <div class="source-bar-wrap">
            <div class="source-bar bar-organic" :style="{ width: getTrafficPercent('organic') + '%' }"></div>
          </div>
          <span class="source-value">{{ formatNumber(data.organic_ipv) }} ({{ getTrafficPercent('organic') }}%)</span>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="funnel-container">
          <div class="funnel-item">
            <div class="funnel-bar funnel-visitors">
              <span>访客 {{ formatNumber(data.visitors) }}</span>
            </div>
          </div>
          <div class="funnel-item">
            <div class="funnel-bar funnel-cart">
              <span>加购 {{ formatNumber(data.cart_users || 0) }}</span>
            </div>
          </div>
          <div class="funnel-item">
            <div class="funnel-bar funnel-buyers">
              <span>购买 {{ formatNumber(data.buyers || 0) }}</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
defineProps({ data: Object })

const formatNumber = (val) => {
  if (!val) return '0'
  return Number(val).toLocaleString()
}

const getTrafficPercent = (type) => {
  const props = defineProps({ data: Object })
  const total = props.data.visitors || 1
  const values = {
    search: props.data.search_ipv || 0,
    recommend: props.data.recommend_ipv || 0,
    paid: props.data.paid_ipv || 0,
    organic: props.data.organic_ipv || 0
  }
  return ((values[type] / total) * 100).toFixed(1)
}
</script>

<style scoped>
.source-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}
.source-label {
  width: 80px;
  font-size: 14px;
}
.source-bar-wrap {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.source-bar {
  height: 100%;
  background: #409eff;
  transition: width 0.3s;
}
.bar-recommend { background: #67c23a; }
.bar-paid { background: #e6a23c; }
.bar-organic { background: #909399; }
.source-value {
  width: 120px;
  text-align: right;
  font-size: 14px;
}
.funnel-container {
  padding: 20px;
}
.funnel-item {
  margin-bottom: 10px;
}
.funnel-bar {
  padding: 10px 20px;
  color: white;
  text-align: center;
  border-radius: 4px;
}
.funnel-visitors { background: #409eff; }
.funnel-cart { background: #67c23a; }
.funnel-buyers { background: #e6a23c; }
</style>
