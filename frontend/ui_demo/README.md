# 天猫数据仪表盘 UI Demo

这是当前 Flask 应用使用的七页业务工作台。页面通过共享 shell 和 live adapter 调用正式 API，不依赖静态 mock 数据作为业务结果。

页面与真实 Tab 对照：

| Demo | 真实 Tab | 主要数据域 |
|---|---|---|
| `products.html` | 商品运营 | products / daily / weekly / monthly |
| `promotion.html` | 推广分析 | plan / promotion_product / keyword / audience / creative |
| `lifecycle.html` | 生命周期 | lifecycle / products |
| `compare.html` | 周期对比 | compare / targets |
| `manage.html` | 管理工作台 | tasks / user_kpis / scheduled_tasks |

页面按业务域组织，直接复用现有 Flask API、SQLite 数据、导入和分析逻辑，不包含虚拟业务数据。推广页在旧 API 缺少明细时展示空态，不伪造归因数据。

通过 Flask 启动后访问 `/`，或使用 Waitress 生产入口。验证目标：桌面 `1440x900`、平板 `1024x768`、移动 `390x844`；检查导航、周期选择、图表非空、表格横向滚动、键盘焦点和无控制台错误。
