          <el-sub-menu index="system">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>系统管理</span>
            </template>
            <el-menu-item index="/import">
              <el-icon><Upload /></el-icon>
              <span>数据导入</span>
            </el-menu-item>
            <el-menu-item index="/smart-import">
              <el-icon><MagicStick /></el-icon>
              <span>智能导入</span>
            </el-menu-item>
            <el-menu-item index="/backup">
              <el-icon><FolderOpened /></el-icon>
              <span>数据备份</span>
            </el-menu-item>
            <el-menu-item index="/settings">
              <el-icon><Tools /></el-icon>
              <span>系统设置</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-left">
          <el-button 
            :icon="isCollapsed ? 'Expand' : 'Fold'" 
            @click="isCollapsed = !isCollapsed"
            text
            class="collapse-btn"
          />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="pageTitle !== '数据概览'">{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <div class="date-selector">
            <el-select v-model="dateRangeType" size="small" style="width: 90px;" @change="handleDateRangeChange">
              <el-option label="今日" value="day" />
              <el-option label="本周" value="week" />
              <el-option label="本月" value="month" />
              <el-option label="自定义" value="custom" />
            </el-select>
            
            <el-date-picker
              v-if="dateRangeType === 'custom'"