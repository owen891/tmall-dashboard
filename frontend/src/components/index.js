import PageLoading from './common/PageLoading.vue'
import PageEmpty from './common/PageEmpty.vue'
import PageBreadcrumb from './common/PageBreadcrumb.vue'
import StatCard from './common/StatCard.vue'
import DateRangePicker from './common/DateRangePicker.vue'
import SmartTable from './common/SmartTable.vue'
import ChartContainer from './common/ChartContainer.vue'

export {
  PageLoading,
  PageEmpty,
  PageBreadcrumb,
  StatCard,
  DateRangePicker,
  SmartTable,
  ChartContainer,
}

export default {
  install(app) {
    app.component('PageLoading', PageLoading)
    app.component('PageEmpty', PageEmpty)
    app.component('PageBreadcrumb', PageBreadcrumb)
    app.component('StatCard', StatCard)
    app.component('DateRangePicker', DateRangePicker)
    app.component('SmartTable', SmartTable)
    app.component('ChartContainer', ChartContainer)
  }
}
