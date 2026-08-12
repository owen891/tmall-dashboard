(function () {
  const nav = [
    ['overview', '数据概览', 'layout-dashboard', 'overview'],
    ['products', '商品运营', 'package', 'products'],
    ['promotion', '推广分析', 'megaphone', 'promotion'],
    ['lifecycle', '生命周期', 'refresh-cw', 'lifecycle'],
    ['compare', '周期对比', 'git-compare', 'compare'],
    ['manage', '管理工作台', 'kanban-square', 'manage']
  ];
  const meta = {
    products: ['商品运营', '商品经营表现与选款效率'],
    promotion: ['推广分析', '按投放粒度解释花费、成交与投产效率'],
    lifecycle: ['生命周期', '按商品查看跨月经营表现与累计贡献'],
    compare: ['周期对比', '解释不同经营周期的结果差异'],
    manage: ['管理工作台', '目标、任务、日志集中处理'],
    catalog: ['Demo 目录', '按业务域浏览全部页面设计']
  };
  const currentPage = document.body.dataset.page || 'products';
  const currentMeta = meta[currentPage] || meta.products;
  const isCatalog = currentPage === 'catalog';
  const route = (page) => {
    if (page === 'overview') return `${isCatalog ? '../../' : '../../../'}数据概览（标题最左+时间选择器）/pages/数据概览（标题最左+时间选择器）.html`;
    return isCatalog ? `pages/${page}.html` : `${page}.html`;
  };
  const sidebar = document.querySelector('[data-shell-sidebar]');
  const header = document.querySelector('[data-shell-header]');
  if (!sidebar || !header) return;

  sidebar.innerHTML = `
    <div class="demo-brand">
      <div class="demo-brand__mark"><i data-lucide="bar-chart-3"></i></div>
      <div class="demo-brand__name"><strong>天猫数据</strong><strong>仪表盘</strong></div>
    </div>
    <nav class="demo-nav" aria-label="主导航"><div class="demo-nav__group">
      ${nav.map(([id, label, icon, page]) => `<a class="demo-nav__item" data-page-link="${id}" href="${route(page)}"><i data-lucide="${icon}"></i><span>${label}</span></a>`).join('')}
    </div></nav>
    <button class="demo-sidebar__toolbox" type="button" data-open-toolbox><i data-lucide="wrench"></i><span>数据工具箱</span></button>
    <div class="demo-sidebar__status"><span class="status-dot"></span><span>系统正常</span></div>`;

  header.innerHTML = `
    <div class="demo-topbar__heading"><h1 class="demo-topbar__title">${currentMeta[0]}</h1><span class="demo-topbar__eyebrow">${currentMeta[1]}</span></div>
    <div class="demo-period" role="group" aria-label="统计周期">
      <span>统计时间</span><span class="demo-period__range tabular" data-period-range>2026-07-01 ~ 2026-07-31</span>
      <span class="demo-period__divider" aria-hidden="true"></span>
      <div class="demo-period__presets" role="group" aria-label="快捷时间范围">
        <button type="button" data-period="1d" aria-pressed="false">昨天</button><button type="button" data-period="7d" aria-pressed="false">7天</button><button type="button" data-period="30d" aria-pressed="true">30天</button><button type="button" data-period="60d" aria-pressed="false">60天</button>
      </div>
      <span class="demo-period__divider" aria-hidden="true"></span>
      <div class="demo-period__dims" role="group" aria-label="时间粒度">
        <button type="button" data-dim="day" aria-pressed="false">日</button><button type="button" data-dim="week" aria-pressed="false">周</button><button type="button" data-dim="month" aria-pressed="true">月</button>
      </div>
      <button type="button" class="demo-period__custom" data-custom-period aria-expanded="false"><i data-lucide="calendar"></i>自定义</button>
      <form class="demo-period__popover" data-period-popover hidden><label>开始日期<input type="date" data-period-start value="2026-07-01"></label><label>结束日期<input type="date" data-period-end value="2026-07-31"></label><button class="button button--primary" type="submit">应用</button></form>
      <div class="demo-period__nav" aria-label="切换统计周期"><button type="button" data-shift="-1" aria-label="上一个统计周期">‹</button><button type="button" data-shift="1" aria-label="下一个统计周期">›</button></div>
    </div>
    <div class="demo-topbar__tools"><button class="demo-tool demo-mobile-nav" type="button" title="打开导航" aria-label="打开导航" aria-expanded="false" data-mobile-nav><i data-lucide="menu"></i></button><button class="demo-tool" type="button" title="刷新" aria-label="刷新" data-demo-refresh><i data-lucide="refresh-cw"></i></button><button class="demo-tool" type="button" title="导出" aria-label="导出"><i data-lucide="download"></i></button><button class="demo-tool" type="button" title="切换主题" aria-label="切换主题"><i data-lucide="sun"></i></button></div>`;

  document.body.insertAdjacentHTML('beforeend', `
    <div class="toolbox-overlay" data-toolbox-overlay></div>
    <aside class="toolbox-drawer" data-toolbox-drawer aria-label="数据工具箱">
      <div class="toolbox-drawer__header"><div><h2>数据工具箱</h2><span class="panel__hint">数据导入与自动任务</span></div><button class="button button--ghost" type="button" data-close-toolbox aria-label="关闭"><i data-lucide="x"></i></button></div>
      <div class="toolbox-drawer__body">
        <div class="toolbox-tools" role="group" aria-label="选择工具">
          <button class="toolbox-tool" type="button" aria-pressed="true" data-tool="import"><strong>多源数据导入</strong><span>按表头识别 Excel、ZIP、CSV 与数据域</span></button>
          <button class="toolbox-tool" type="button" aria-pressed="false" data-tool="schedule"><strong>定时导入任务</strong><span>按文件规则自动执行数据同步</span></button>
        </div>
        <section class="plain-panel panel" data-tool-panel="import"><div class="panel__header"><div><h3 class="panel__title">导入经营数据</h3><p class="panel__hint">按表头识别数据类型；ZIP 内 CSV 会先解包再校验字段</p></div><span class="badge badge--info">最大 50MB</span></div><label class="upload-zone" for="demoImportFile"><span><i data-lucide="file-up"></i><strong data-import-file-name>选择 Excel、ZIP 或 CSV 文件</strong><span>支持 .xlsx / .xls / .zip / .csv，ID 字段按文本保留</span></span></label><input class="sr-only" id="demoImportFile" data-import-file type="file" accept=".xlsx,.xls,.zip,.csv"><div class="section-toolbar" style="margin-top:10px"><select class="select" data-import-type aria-label="导入数据类型"><option value="auto">按表头自动识别</option><option value="store_daily">店铺日数据</option><option value="product_daily">商品日数据</option><option value="product_source">商品来源</option><option value="plan">计划报表</option><option value="promotion_product">推广商品</option><option value="keyword">投放关键词</option><option value="audience">人群</option><option value="creative">创意</option><option value="content">内容</option><option value="region">地域</option></select><button class="button button--primary" type="button" data-start-import><i data-lucide="upload"></i>开始导入</button></div><div class="import-progress" aria-hidden="true"><span data-import-progress></span></div><div class="import-result" data-import-result>等待选择文件</div></section>
        <section class="plain-panel panel" data-tool-panel="schedule" hidden><div class="panel__header"><div><h3 class="panel__title">定时导入任务</h3><p class="panel__hint">按计划扫描指定文件模式</p></div></div><div class="modal-form__body"><label>任务名称<input class="input" value="每日经营数据同步"></label><div class="filter-group"><select class="select" aria-label="执行频率"><option>每天</option><option>每周</option><option>每月</option></select><input class="input" type="time" value="08:00" aria-label="执行时间"></div><label>文件匹配模式<input class="input" value="*.xlsx"></label><button class="button button--primary" type="button" data-add-schedule>添加任务</button></div><div class="data-table-wrap" style="margin-top:12px"><table class="data-table"><thead><tr><th>任务</th><th>计划</th><th>状态</th></tr></thead><tbody data-schedule-list><tr><td>日经营数据同步</td><td class="tabular">每天 02:00</td><td><span class="badge badge--success">启用</span></td></tr></tbody></table></div></section>
        <section class="plain-panel panel"><div class="panel__header"><div><h3 class="panel__title">最近导入</h3><p class="panel__hint">保留批次、来源、数据域、日期和处理结果</p></div></div><div class="status-list" data-import-history><div class="status-list__item"><span class="status-list__label">计划报表_20260503.zip · 计划报表 · 2026-04</span><span class="badge badge--success">1,203 行</span></div><div class="status-list__item"><span class="status-list__label">商品报表_20260503.zip · 推广商品 · 2026-04</span><span class="badge badge--success">1,506 行</span></div><div class="status-list__item"><span class="status-list__label">地域报表_20260503.zip · 地域 · 2026-05-01~02</span><span class="badge badge--warning">729 行 · 观察期过短</span></div></div></section>
      </div>
    </aside>`);

  const range = header.querySelector('[data-period-range]');
  let state = { start: new Date('2026-07-01T00:00:00'), end: new Date('2026-07-31T00:00:00'), days: 31 };
  const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const shift = (date, amount) => { const next = new Date(date); next.setDate(next.getDate() + amount); return next; };
  const sync = () => { range.textContent = `${formatDate(state.start)} ~ ${formatDate(state.end)}`; };
  header.querySelectorAll('[data-period]').forEach((button) => button.addEventListener('click', () => {
    const days = Number(button.dataset.period.replace('d', ''));
    state = { start: shift(state.end, -(days - 1)), end: state.end, days };
    header.querySelectorAll('[data-period]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    sync();
  }));
  header.querySelectorAll('[data-dim]').forEach((button) => button.addEventListener('click', () => {
    header.querySelectorAll('[data-dim]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
  }));
  header.querySelectorAll('[data-shift]').forEach((button) => button.addEventListener('click', () => {
    const offset = Number(button.dataset.shift) * state.days;
    state.start = shift(state.start, offset); state.end = shift(state.end, offset); sync();
  }));
  const customButton = header.querySelector('[data-custom-period]');
  const popover = header.querySelector('[data-period-popover]');
  customButton.addEventListener('click', () => {
    const open = popover.hasAttribute('hidden');
    popover.toggleAttribute('hidden', !open);
    customButton.setAttribute('aria-expanded', String(open));
  });
  popover.addEventListener('submit', (event) => {
    event.preventDefault();
    const start = new Date(popover.querySelector('[data-period-start]').value);
    const end = new Date(popover.querySelector('[data-period-end]').value);
    if (Number.isNaN(start.valueOf()) || Number.isNaN(end.valueOf()) || start > end) return;
    state = { start, end, days: Math.max(1, Math.round((end - start) / 86400000) + 1) };
    header.querySelectorAll('[data-period]').forEach((item) => item.setAttribute('aria-pressed', 'false'));
    sync();
    popover.toggleAttribute('hidden', true);
    customButton.setAttribute('aria-expanded', 'false');
  });
  header.querySelector('[data-demo-refresh]').addEventListener('click', (event) => {
    event.currentTarget.classList.add('is-spinning');
    window.setTimeout(() => event.currentTarget.classList.remove('is-spinning'), 500);
  });
  document.querySelectorAll('[data-page-link]').forEach((link) => {
    if (link.dataset.pageLink === currentPage) link.setAttribute('aria-current', 'page');
    link.addEventListener('click', () => sidebar.classList.remove('is-open'));
  });
  const mobileNav = header.querySelector('[data-mobile-nav]');
  mobileNav.addEventListener('click', () => {
    const open = sidebar.classList.toggle('is-open');
    mobileNav.setAttribute('aria-expanded', String(open));
  });
  document.querySelectorAll('.segmented button').forEach((button) => button.addEventListener('click', () => {
    const group = button.closest('.segmented');
    group?.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
  }));
  const toolbox = document.querySelector('[data-toolbox-drawer]');
  const toolboxOverlay = document.querySelector('[data-toolbox-overlay]');
  const closeToolbox = () => { toolbox.classList.remove('is-open'); toolboxOverlay.classList.remove('is-open'); };
  sidebar.querySelector('[data-open-toolbox]').addEventListener('click', () => { toolbox.classList.add('is-open'); toolboxOverlay.classList.add('is-open'); sidebar.classList.remove('is-open'); });
  document.querySelector('[data-close-toolbox]').addEventListener('click', closeToolbox);
  toolboxOverlay.addEventListener('click', closeToolbox);
  document.querySelectorAll('[data-tool]').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('[data-tool]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelectorAll('[data-tool-panel]').forEach((panel) => { panel.hidden = panel.dataset.toolPanel !== button.dataset.tool; });
  }));
  const importSignatures = [
    { value: 'plan', label: '计划报表', fields: ['计划ID', '计划名字', '场景名字'] },
    { value: 'keyword', label: '投放关键词', fields: ['词ID/词包ID', '词名字/词包名字', '场景名字'] },
    { value: 'audience', label: '人群', fields: ['人群名字', '展现量', '花费'] },
    { value: 'creative', label: '创意', fields: ['创意ID', '创意名字', '主体ID'] },
    { value: 'region', label: '地域', fields: ['省', '市', '花费'] },
    { value: 'product_source', label: '商品来源', fields: ['商品ID', '来源', '访客数'] },
    { value: 'product_daily', label: '商品日数据', fields: ['商品ID', '日期', '支付金额'] },
    { value: 'store_daily', label: '店铺日数据', fields: ['日期', '访客数', '支付金额'] }
  ];
  const parseCsvRow = (line) => { const cells = []; let cell = ''; let quoted = false; for (let index = 0; index < line.length; index += 1) { const char = line[index]; if (char === '"' && quoted && line[index + 1] === '"') { cell += '"'; index += 1; } else if (char === '"') { quoted = !quoted; } else if (char === ',' && !quoted) { cells.push(cell.trim()); cell = ''; } else { cell += char; } } cells.push(cell.trim()); return cells; };
  const detectImportDomain = (headers, sampleRows = []) => {
    const normalized = new Set(headers.map((field) => String(field).replace(/^\ufeff/, '').trim()));
    const direct = importSignatures.find((signature) => signature.fields.every((field) => normalized.has(field)));
    if (direct) return direct;
    if (['主体ID', '主体类型', '主体名称'].every((field) => normalized.has(field))) {
      const sampleText = sampleRows.flat().join(' ');
      return /短视频|图文|直播/.test(sampleText) ? { value: 'content', label: '内容', fields: ['主体ID', '主体类型', '主体名称'] } : { value: 'promotion_product', label: '推广商品', fields: ['主体ID', '主体类型', '主体名称'] };
    }
    return { value: 'unknown', label: '未识别数据', fields: [] };
  };
  const decodeCsv = async (file) => { const bytes = await file.arrayBuffer(); const utf8 = new TextDecoder('utf-8').decode(bytes); const replacementCount = (utf8.match(/\ufffd/g) || []).length; return replacementCount > 3 ? new TextDecoder('gb18030').decode(bytes) : utf8; };
  const inspectCsv = async (file) => { const text = await decodeCsv(file); const lines = text.split(/\r?\n/).filter(Boolean).slice(0, 4); return detectImportDomain(parseCsvRow(lines[0] || ''), lines.slice(1).map(parseCsvRow)); };
  const importFile = document.querySelector('[data-import-file]');
  importFile.addEventListener('change', () => { document.querySelector('[data-import-file-name]').textContent = importFile.files[0]?.name || '选择 Excel、ZIP 或 CSV 文件'; });
  document.querySelector('[data-start-import]').addEventListener('click', async () => {
    const result = document.querySelector('[data-import-result]');
    const progress = document.querySelector('[data-import-progress]');
    if (!importFile.files[0]) { result.textContent = '请先选择 Excel、ZIP 或 CSV 文件'; return; }
    const file = importFile.files[0];
    const type = document.querySelector('[data-import-type]').value;
    const sourceLabel = file.name.toLowerCase().endsWith('.zip') ? '解包 ZIP 内 CSV' : file.name.toLowerCase().endsWith('.csv') ? '读取 CSV 表头' : '读取工作簿结构';
    let detected = null;
    if (type === 'auto' && file.name.toLowerCase().endsWith('.csv')) { try { detected = await inspectCsv(file); } catch { detected = { value: 'unknown', label: 'CSV 读取失败' }; } }
    const typeLabel = type === 'auto' ? detected ? `按表头识别为：${detected.label}` : '容器解包/工作簿读取后按表头识别' : document.querySelector('[data-import-type] option:checked').textContent;
    const stages = [[20, sourceLabel], [48, `${typeLabel}，保留 ID 文本格式`], [76, '校验字段、日期与重复批次'], [100, `导入完成：${typeLabel}；记录批次、来源、日期与结果`]];
    stages.forEach(([value, label], index) => window.setTimeout(() => { progress.style.width = `${value}%`; result.textContent = label; }, index * 450));
  });
  document.querySelector('[data-add-schedule]').addEventListener('click', () => {
    document.querySelector('[data-schedule-list]').insertAdjacentHTML('beforeend', '<tr><td>新建导入任务</td><td class="tabular">每天 08:00</td><td><span class="badge badge--success">启用</span></td></tr>');
  });
  window.DemoImportDetector = { detectImportDomain, parseCsvRow, signatures: importSignatures };
  window.DemoShell = { nav, meta, sync };
  if (window.lucide) window.lucide.createIcons();
})();
