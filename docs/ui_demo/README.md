# 天猫数据仪表盘 UI Demo

这是基于 `数据概览（标题最左+时间选择器）` 参考稿补齐的业务页面设计包。参考稿保持原文件不变；本目录只承载后续真实项目迁移前的视觉与交互 demo。

页面与真实 Tab 对照：

| Demo | 真实 Tab | 主要数据域 |
|---|---|---|
| `products.html` | 商品运营 | products / daily / weekly / monthly |
| `promotion.html` | 推广分析 | plan / promotion_product / keyword / audience / creative |
| `lifecycle.html` | 生命周期 | lifecycle / products |
| `compare.html` | 周期对比 | compare / targets |
| `manage.html` | 管理工作台 | tasks / user_kpis / scheduled_tasks |

设计约束来自 `docs/REFACTOR_PLAN.md`：页面按业务域组织，数据结构对齐 API 拆分方向，所有 demo 使用本地 mock 数据，不修改真实 Flask 模板或 API。推广页使用 `E:\bi\bi\取数源` 的报表口径：计划报表作为总盘，其他报表按粒度独立展示，避免重复相加。

直接打开 `index.html`，或启动静态预览：

```powershell
py -m http.server 4176 --directory docs/ui_demo
```

验证目标：桌面 `1440x900`、平板 `1024x768`、移动 `390x844`；检查导航、周期选择、图表非空、表格横向滚动、键盘焦点和无控制台错误。
