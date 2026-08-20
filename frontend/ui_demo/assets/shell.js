(function () {
  const assetBase = new URL('.', document.currentScript?.src || window.location.href);
  const loadScript = (src) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });

  loadScript(new URL('table-controls.js', assetBase).href).catch(() => {});
  loadScript(new URL('version.js', assetBase).href)
    .then(() => loadScript(new URL('version-check.js', assetBase).href))
    .catch(() => {});

  const liveAdapters = { overview: 'overview-live.js', products: 'products-live.js', promotion: 'promotion-live.js' };
  const liveAdapter = liveAdapters[document.body.dataset.page];
  const apiReady = window.DemoApi
    ? Promise.resolve(window.DemoApi)
    : loadScript(new URL('api.js', assetBase).href).then(() => window.DemoApi);
  const requestApi = async (path, options) => {
    const api = await apiReady;
    if (!api?.request) throw new Error('API 客户端不可用');
    return api.request(path, options);
  };
  const requestDomainApi = async (path, options) => {
    const api = await apiReady;
    if (!api?.domainRequest) throw new Error('域 API 客户端不可用');
    return api.domainRequest(path, options);
  };
  const DATA_STATES = ['loading', 'no-data', 'insufficient-data', 'missing-fields', 'calculation-failed', 'source-unavailable', 'partial'];
  window.TmallDataStates = Object.freeze(DATA_STATES.slice());
  if (liveAdapter && !window.DemoApi) apiReady.then(() => loadScript(new URL(liveAdapter, assetBase).href)).catch(() => {});
  const nav = [
    ['overview', '数据概览', 'layout-dashboard', 'overview'],
    ['products', '商品运营', 'package', 'products'],
    ['promotion', '推广分析', 'megaphone', 'promotion'],
    ['lifecycle', '生命周期', 'refresh-cw', 'lifecycle'],
    ['reviews', '经营复盘', 'clipboard-check', 'reviews'],
    ['data-center', '数据中心', 'database', 'data-center'],
    ['settings', '设置', 'settings', 'settings']
  ];
  const meta = {
    products: ['商品运营', '商品经营表现与选款效率'],
    promotion: ['推广分析', '按投放粒度解释花费、成交与投产效率'],
    lifecycle: ['生命周期', '按商品查看跨月经营表现与累计贡献'],
    reviews: ['经营复盘', '查看待复盘动作与经营周期差异'],
    'data-center': ['数据中心', '导入、校验和管理经营数据'],
    settings: ['设置', '维护店铺与业务默认配置'],
    goals: ['经营目标', '按年、季、月、周、日跟踪净销售目标'],
    catalog: ['Demo 目录', '按业务域浏览全部页面设计'],
    overview: ['数据概览', '店铺经营核心指标与趋势']
  };
  const currentPage = document.body.dataset.page || 'products';
  const currentMeta = meta[currentPage] || meta.products;
  const isCatalog = currentPage === 'catalog';
  const storageKey = 'tmall-demo-theme';
  const getStoredTheme = () => {
    try { return localStorage.getItem(storageKey); } catch { return null; }
  };
  const setStoredTheme = (theme) => {
    try { localStorage.setItem(storageKey, theme); } catch {}
  };
  let theme = getStoredTheme() === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  const themeColorMeta = document.head.querySelector('meta[name="theme-color"]') || document.head.appendChild(Object.assign(document.createElement('meta'), { name: 'theme-color' }));
  const route = (page) => {
    const path = page === 'overview' ? '/' : `/${page}`;
    return window.DemoNavigation?.fromCurrent ? window.DemoNavigation.fromCurrent(path) : path;
  };
  const sidebar = document.querySelector('[data-shell-sidebar]');
  const header = document.querySelector('[data-shell-header]');
  if (!sidebar || !header) return;

  // Lucide's public helper scans the whole document on every call. Most page
  // updates only add a few icons, so skip the scan when no unprocessed icons
  // exist and keep repeated renders from blocking the main thread.
  if (window.lucide?.createIcons) {
    const createIcons = window.lucide.createIcons.bind(window.lucide);
    window.lucide.createIcons = (...args) => {
      const pendingIcons = document.querySelectorAll('[data-lucide]:not([data-lucide-rendered])');
      if (!pendingIcons.length) return;
      pendingIcons.forEach(icon => icon.setAttribute('data-lucide-rendered', 'true'));
      return createIcons(...args);
    };
  }
  const main = document.querySelector('main.demo-page');
  if (main && !main.id) main.id = 'main-content';
  document.body.insertAdjacentHTML('afterbegin', '<a class="skip-link" data-skip-link href="#main-content">跳到主要内容</a>');

  sidebar.innerHTML = `
    <div class="demo-brand">
      <div class="demo-brand__mark" aria-hidden="true">TM</div>
      <div class="demo-brand__name"><strong>天猫数据</strong><strong>仪表盘</strong></div>
    </div>
    <nav class="demo-nav" aria-label="主导航"><div class="demo-nav__group">
      ${nav.map(([id, label, icon, page]) => `<a class="demo-nav__item" data-page-link="${id}" href="${route(page)}" aria-label="${label}" title="${label}"><i data-lucide="${icon}"></i><span>${label}</span></a>`).join('')}
    </div></nav>
    <div class="demo-sidebar__status"><span class="status-dot"></span><span>系统正常</span></div>`;

  header.innerHTML = `
    <div class="demo-topbar__heading"><h1 class="demo-topbar__title">${currentMeta[0]}</h1><span class="demo-topbar__eyebrow">${currentMeta[1]}</span></div>
    <div class="demo-period" role="group" aria-label="统计时间">
      <select class="demo-period__select" data-date-preset aria-label="快捷时间范围">
        <option value="today">今日</option><option value="yesterday">昨日</option><option value="7d">近7天</option><option value="30d" selected>近30天</option><option value="90d">近90天</option><option value="this_week">本周</option><option value="last_week">上周</option><option value="this_month">本月</option><option value="last_month">上月</option><option value="custom">自定义</option>
      </select>
      <button type="button" class="demo-period__trigger tabular" data-date-trigger aria-expanded="false"><i data-lucide="calendar-days"></i><span data-period-range>数据库日期加载中</span></button>
      ${currentPage === 'overview' ? '<select class="demo-period__select demo-period__compare" data-compare-mode aria-label="对比方式"><option value="none">不对比</option><option value="previous_period">环比</option><option value="year_over_year">同比</option></select>' : ''}
      <div class="demo-period__popover" data-period-popover hidden>
        <div class="demo-calendar__toolbar"><button type="button" data-calendar-nav="-1" aria-label="上两个月">‹</button><strong>自定义日期范围</strong><button type="button" data-calendar-nav="1" aria-label="下两个月">›</button></div>
        <div class="demo-calendar__months"><section data-calendar-month="0"></section><section data-calendar-month="1"></section></div>
        <div class="demo-calendar__footer"><span data-calendar-help>请选择开始日期</span><button class="button button--ghost" type="button" data-calendar-cancel>取消</button></div>
      </div>
    </div>
    <div class="demo-topbar__tools"><button class="button demo-import-trigger" type="button" data-open-toolbox title="导入数据"><i data-lucide="upload"></i><span>导入数据</span></button><button class="demo-tool demo-mobile-nav" type="button" title="打开导航" aria-label="打开导航" aria-expanded="false" data-mobile-nav><i data-lucide="menu"></i></button><button class="demo-tool" type="button" title="刷新" aria-label="刷新" data-demo-refresh><i data-lucide="refresh-cw"></i></button><button class="demo-tool" type="button" title="导出" aria-label="导出当前表格" data-demo-export><i data-lucide="download"></i></button><button class="demo-tool" type="button" title="切换深色主题" aria-label="切换深色主题" data-demo-theme><i data-lucide="moon"></i></button></div>`;

  if (currentPage === 'lifecycle') header.querySelector('.demo-period').hidden = true;
  if (currentPage === 'overview') {
    header.querySelector('.demo-topbar__tools').insertAdjacentHTML('beforeend', `
      <button class="button demo-overview-action" type="button" aria-label="刷新报告" title="刷新报告" data-capability-key="overview.view_kpis" data-overview-report-refresh><i data-lucide="refresh-cw"></i><span>刷新报告</span></button>
      <button class="button button--primary demo-overview-action" type="button" aria-label="新增事件" title="新增事件" data-capability-key="overview.event_edit" data-overview-event-open><i data-lucide="plus"></i><span>新增事件</span></button>`);
  }

  document.body.insertAdjacentHTML('beforeend', `
    <div class="demo-shell-status" data-demo-status role="status" aria-live="polite" aria-atomic="true"></div>
    <div class="demo-toast" data-demo-toast role="status" aria-live="polite" aria-atomic="true"></div>
    <dialog class="toolbox-dialog" data-toolbox-dialog data-modal-kind="flow" aria-labelledby="toolboxTitle">
      <div class="toolbox-dialog__header"><div><h2 id="toolboxTitle">数据工具箱</h2><span class="panel__hint">数据导入与自动任务</span><span class="panel__hint" data-flow-impact>\u5f71\u54cd\u8303\u56f4\uff1a\u4ec5\u5f53\u524d\u5bfc\u5165\u6279\u6b21\u53ca\u5176\u5bfc\u5165\u8bb0\u5f55</span></div><button class="button button--ghost" type="button" data-close-toolbox aria-label="关闭"><i data-lucide="x"></i></button></div>
      <div class="toolbox-dialog__body">
        <div class="toolbox-tools" role="tablist" aria-label="选择工具">
          <button class="toolbox-tool" id="toolbox-tab-import" role="tab" type="button" aria-selected="true" aria-pressed="true" aria-controls="toolbox-panel-import" data-tool="import"><strong>经营数据导入</strong><span>使用现有导入服务处理 Excel 工作簿</span></button>
          <button class="toolbox-tool" id="toolbox-tab-scan" role="tab" type="button" aria-selected="false" aria-pressed="false" aria-controls="toolbox-panel-scan" data-tool="scan"><strong>文件夹扫描任务</strong><span>扫描指定文件夹并自动导入新报表</span></button>
        </div>
        <section class="plain-panel panel" id="toolbox-panel-import" role="tabpanel" aria-labelledby="toolbox-tab-import" data-tool-panel="import"><div class="panel__header"><div><h3 class="panel__title">导入经营数据</h3><p class="panel__hint">先预览文件、确认字段映射和质量，再写入数据库</p></div><span class="badge badge--info">表格</span></div><label class="upload-zone" for="demoImportFile"><span><i data-lucide="file-up"></i><strong data-import-file-name>选择表格文件</strong><span>支持 .xlsx / .xls / .csv / .zip；可多选，文件选择器内可按 Ctrl+A 全选</span></span></label><input class="sr-only" id="demoImportFile" data-import-file type="file" accept=".xlsx,.xls,.csv,.zip" multiple><div class="section-toolbar toolbox-import-actions"><button class="button button--primary" type="button" data-import-preview><i data-lucide="scan-search"></i>预览并校验</button><button class="button button--primary" type="button" data-import-confirm disabled><i data-lucide="database"></i>确认导入</button></div><div class="import-progress" aria-hidden="true"><span data-import-progress></span></div><div class="import-result" data-import-result role="status" aria-live="polite">等待选择文件</div><section class="import-preview-panel" data-import-preview-panel hidden><div class="import-preview-panel__summary"><div class="toolbox-import-tabs" data-import-preview-tabs role="tablist" aria-label="预览文件"></div><p class="panel__hint" data-import-quality>选择文件后查看质量摘要</p><p class="panel__hint" data-import-quality-detail>未发现异常行</p></div><div class="data-table-wrap"><table class="data-table import-preview-table"><thead><tr><th>原始列</th><th>推断类型</th><th>标准字段映射</th><th>匹配状态</th><th>样例</th></tr></thead><tbody data-import-fields></tbody></table></div></section></section>
        <section class="plain-panel panel" id="toolbox-panel-scan" role="tabpanel" aria-labelledby="toolbox-tab-scan" data-tool-panel="scan" hidden><div class="panel__header"><div><h3 class="panel__title">文件夹扫描任务</h3><p class="panel__hint">定期检查指定文件夹，新文件会复用导入校验和批次审计</p></div><button class="button button--ghost" type="button" data-refresh-scans aria-label="刷新扫描任务"><i data-lucide="refresh-cw"></i>刷新</button></div><div class="modal-form__body toolbox-scan-form"><label>任务名称<input class="input" name="scan_name" data-scan-name placeholder="例如：每日经营数据扫描" autocomplete="off"></label><label>扫描文件夹<span class="toolbox-scan-folder"><input class="input" name="scan_folder" data-scan-folder placeholder="请选择或输入本机文件夹绝对路径" autocomplete="off"><button class="button" type="button" data-select-scan-folder hidden><i data-lucide="folder-open"></i>选择文件夹</button></span></label><div class="filter-group"><label>文件匹配规则<input class="input" name="scan_pattern" data-scan-pattern value="*.xlsx;*.xls;*.csv;*.zip" autocomplete="off"></label><label>报表来源<select class="select" name="scan_source" data-scan-source><option value="auto">自动识别</option><option value="product_day">商品日度</option><option value="dmp_product_day">DMP 商品日度</option><option value="store_day">店铺日度</option><option value="refund_day">退款日度</option><option value="customer_day">客户日度</option><option value="product_week">商品周度</option><option value="product_month">商品月度</option><option value="promotion_channel_day">推广渠道日度</option><option value="promotion_campaign_day">推广计划日度</option><option value="promotion_unit_day">推广单元日度</option><option value="promotion_product_day">推广商品日度</option></select></label></div><div class="filter-group"><label>扫描频率<select class="select" name="scan_frequency" data-scan-frequency><option value="daily">每天</option><option value="weekly">每周一</option><option value="monthly">每月 1 日</option></select></label><label>扫描时间<input class="input" name="scan_time" data-scan-time type="time" value="08:00" autocomplete="off"></label></div><label class="toolbox-scan-enabled"><input type="checkbox" name="scan_enabled" data-scan-enabled checked> 创建后立即启用</label><button class="button button--primary" type="button" data-add-scan><i data-lucide="folder-plus"></i>添加扫描任务</button><div class="import-result" data-scan-result role="status" aria-live="polite">等待创建任务</div></div><div class="data-table-wrap toolbox-scan-table"><table class="data-table"><thead><tr><th>任务与文件夹</th><th>计划</th><th>状态</th><th>最近运行</th><th>操作</th></tr></thead><tbody data-scan-list><tr><td colspan="5">加载中</td></tr></tbody></table></div></section>
      </div>
    </dialog>`);

  // Dynamic file input retains semantic attributes.
  [['[data-import-file]', 'name', 'import_files'], ['[data-import-file]', 'autocomplete', 'off']].forEach(([selector, attribute, value]) => {
    document.querySelector(selector)?.setAttribute(attribute, value);
  });

  const statusRegion = document.querySelector('[data-demo-status]');
  const toast = document.querySelector('[data-demo-toast]');
  let toastTimer = null;
  const announce = (message) => {
    if (!message) return;
    statusRegion.textContent = message;
  };
  const showToast = (message, options = {}) => {
    announce(message);
    toast.textContent = message;
    toast.classList.add('is-visible');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), options.duration || 2200);
  };
  const unsupportedFiltersByPage = {
    goals: ['promotion_channel'],
  };
  const filterLabels = { promotion_channel: '推广渠道' };
  const discloseUnsupportedFilters = () => {
    const unsupported = new Set(unsupportedFiltersByPage[currentPage] || []);
    const active = [...new URLSearchParams(window.location.search).keys()]
      .filter((key) => unsupported.has(key));
    if (!active.length) return;
    const labels = [...new Set(active.map((key) => filterLabels[key] || key))].join('、');
    showToast(`当前页面不支持${labels}筛选，已保留在地址中`, { duration: 5000 });
  };
  discloseUnsupportedFilters();
  const visibleTables = () => Array.from(document.querySelectorAll('.data-table')).filter((table) => {
    if (table.closest('[hidden]')) return false;
    const toolboxParent = table.closest('[data-toolbox-dialog]');
    if (toolboxParent && !toolboxParent.open) return false;
    const style = window.getComputedStyle(table);
    const rect = table.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  });
  const csvCell = (value) => `"${String(value ?? '').replace(/\s+/g, ' ').trim().replace(/"/g, '""')}"`;
  const tableToCsv = (table, index) => {
    const title = table.closest('.panel')?.querySelector('.panel__title')?.textContent?.trim() || `表格 ${index + 1}`;
    const rows = Array.from(table.querySelectorAll('tr')).filter((row) => {
      const style = window.getComputedStyle(row);
      return style.display !== 'none' && style.visibility !== 'hidden';
    }).map((row) => Array.from(row.children).filter((cell) => {
      const style = window.getComputedStyle(cell);
      return style.display !== 'none' && style.visibility !== 'hidden';
    }).map((cell) => csvCell(cell.textContent)).join(','));
    return [`# ${title}`, ...rows].join('\r\n');
  };
  const exportTables = () => {
    const tables = visibleTables();
    if (!tables.length) {
      showToast('当前页面没有可导出的可见表格');
      return;
    }
    const csv = `\ufeff${tables.map(tableToCsv).join('\r\n\r\n')}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    const stamp = new Date().toISOString().slice(0, 10);
    link.href = URL.createObjectURL(blob);
    link.download = `tmall-${currentPage}-${stamp}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
    showToast(`已导出 ${tables.length} 个表格`);
  };
  const themeButton = header.querySelector('[data-demo-theme]');
  const syncThemeButton = () => {
    const dark = theme === 'dark';
    themeButton.setAttribute('aria-label', dark ? '切换浅色主题' : '切换深色主题');
    themeButton.setAttribute('title', dark ? '切换浅色主题' : '切换深色主题');
    themeButton.innerHTML = `<i data-lucide="${dark ? 'sun' : 'moon'}"></i>`;
    if (window.lucide) window.lucide.createIcons();
  };
  const setTheme = (nextTheme) => {
    theme = nextTheme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    themeColorMeta.content = getComputedStyle(document.documentElement).getPropertyValue('--surface-page').trim();
    setStoredTheme(theme);
    syncThemeButton();
    announce(theme === 'dark' ? '已切换深色主题' : '已切换浅色主题');
  };
  themeColorMeta.content = getComputedStyle(document.documentElement).getPropertyValue('--surface-page').trim();
  syncThemeButton();

  const range = header.querySelector('[data-period-range]');
  const presetSelect = header.querySelector('[data-date-preset]');
  const compareSelect = header.querySelector('[data-compare-mode]');
  const trigger = header.querySelector('[data-date-trigger]');
  const popover = header.querySelector('[data-period-popover]');
  const parseDate = (value) => { const [year, month, day] = value.split('-').map(Number); return new Date(year, month - 1, day); };
  const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const shiftDays = (date, amount) => { const next = new Date(date); next.setDate(next.getDate() + amount); return next; };
  const params = new URLSearchParams(window.location.search);
  let anchorDate = new Date();
  let calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
  let draftStart = null;
  let state = { startDate: '', endDate: '', preset: params.get('preset') || '30d', compareMode: params.get('compare') || 'none' };

  const rangeForPreset = (preset) => {
    const offsets = { today: 0, yesterday: 1, '7d': 6, '30d': 29, '90d': 89 };
    const startOfWeek = (date) => shiftDays(date, -((date.getDay() + 6) % 7));
    if (preset === 'this_week') return { start: startOfWeek(anchorDate), end: new Date(anchorDate) };
    if (preset === 'last_week') {
      const end = shiftDays(startOfWeek(anchorDate), -1);
      return { start: shiftDays(end, -6), end };
    }
    if (preset === 'this_month') return { start: new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1), end: new Date(anchorDate) };
    if (preset === 'last_month') return { start: new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1), end: new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 0) };
    const end = preset === 'yesterday' ? shiftDays(anchorDate, -1) : new Date(anchorDate);
    return { start: shiftDays(end, -(offsets[preset] || 0)), end };
  };
  const dispatchRange = (writeHistory = true) => {
    range.textContent = `${state.startDate} ~ ${state.endDate}`;
    const url = new URL(window.location.href);
    if (['data-center', 'settings'].includes(currentPage)) {
      url.searchParams.delete('start');
      url.searchParams.delete('end');
    } else {
      url.searchParams.set('start', state.startDate);
      url.searchParams.set('end', state.endDate);
    }
    url.searchParams.set('preset', state.preset);
    url.searchParams.set('compare', state.compareMode);
    if (writeHistory) history.pushState(null, '', url);
    window.dispatchEvent(new CustomEvent('tmall:date-range-change', { detail: { ...state } }));
  };
  const applyRange = (start, end, preset = 'custom') => {
    state = { ...state, startDate: formatDate(start), endDate: formatDate(end), preset };
    presetSelect.value = preset;
    dispatchRange();
  };
  const renderCalendar = () => {
    const startValue = draftStart ? formatDate(draftStart) : state.startDate;
    const endValue = draftStart ? '' : state.endDate;
    [0, 1].forEach((offset) => {
      const month = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + offset, 1);
      const year = month.getFullYear();
      const monthIndex = month.getMonth();
      const firstDay = new Date(year, monthIndex, 1).getDay();
      const total = new Date(year, monthIndex + 1, 0).getDate();
      const cells = Array(firstDay).fill('<span class="demo-calendar__blank"></span>');
      for (let day = 1; day <= total; day += 1) {
        const date = new Date(year, monthIndex, day);
        const value = formatDate(date);
        const inRange = startValue && endValue && value >= startValue && value <= endValue;
        const selected = value === startValue || value === endValue;
        cells.push(`<button type="button" data-calendar-date="${value}" class="${inRange ? 'is-in-range' : ''} ${selected ? 'is-selected' : ''}" ${date > anchorDate ? 'disabled' : ''}>${day}</button>`);
      }
      popover.querySelector(`[data-calendar-month="${offset}"]`).innerHTML = `<h3>${year}年${monthIndex + 1}月</h3><div class="demo-calendar__week"><span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span></div><div class="demo-calendar__grid">${cells.join('')}</div>`;
    });
  };
  const setPopover = (open) => {
    popover.toggleAttribute('hidden', !open);
    trigger.setAttribute('aria-expanded', String(open));
    if (open) renderCalendar();
  };
  const setCalendarHelp = () => {
    popover.querySelector('[data-calendar-help]').textContent = state.startDate && state.endDate
      ? `当前范围：${state.startDate} ~ ${state.endDate}；点击任意日期重新选择`
      : '请选择开始日期';
  };
  const resetDraftRange = () => {
    draftStart = null;
    setCalendarHelp();
  };
  const closePopover = (resetDraft = false) => {
    if (resetDraft) {
      resetDraftRange();
      presetSelect.value = state.preset;
    }
    setPopover(false);
  };
  const openPopover = () => {
    resetDraftRange();
    setPopover(true);
  };
  const selectPreset = (preset) => {
    if (preset === 'custom') { openPopover(); return; }
    closePopover(true);
    const next = rangeForPreset(preset);
    applyRange(next.start, next.end, preset);
  };
  trigger.addEventListener('click', () => {
    if (popover.hasAttribute('hidden')) openPopover();
    else closePopover(true);
  });
  presetSelect.addEventListener('change', () => selectPreset(presetSelect.value));
  compareSelect?.addEventListener('change', () => { state.compareMode = compareSelect.value; dispatchRange(); });
  popover.querySelector('[data-calendar-cancel]').addEventListener('click', () => closePopover(true));
  popover.querySelectorAll('[data-calendar-nav]').forEach((button) => button.addEventListener('click', () => {
    calendarBase = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + Number(button.dataset.calendarNav) * 2, 1);
    renderCalendar();
  }));
  popover.addEventListener('click', (event) => {
    const button = event.target.closest('[data-calendar-date]');
    if (!button) return;
    event.stopPropagation();
    const chosen = parseDate(button.dataset.calendarDate);
    if (!draftStart) {
      draftStart = chosen;
      popover.querySelector('[data-calendar-help]').textContent = `${formatDate(chosen)}，请选择结束日期`;
      renderCalendar();
      return;
    }
    const start = chosen < draftStart ? chosen : draftStart;
    const end = chosen < draftStart ? draftStart : chosen;
    draftStart = null;
    applyRange(start, end, 'custom');
    closePopover(false);
  });
  document.addEventListener('click', (event) => {
    if (!popover.hasAttribute('hidden') && !popover.contains(event.target) && !trigger.contains(event.target) && event.target !== presetSelect) closePopover(true);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || popover.hasAttribute('hidden')) return;
    event.preventDefault();
    event.stopPropagation();
    closePopover(true);
    trigger.focus();
  });
  if (compareSelect) compareSelect.value = state.compareMode;
  window.TmallDateRange = { getState: () => ({ ...state }) };
  const restoreRangeFromUrl = () => {
    const currentParams = new URLSearchParams(window.location.search);
    const preset = currentParams.get('preset') || '30d';
    const start = currentParams.get('start');
    const end = currentParams.get('end');
    state = { ...state, preset, compareMode: currentParams.get('compare') || 'none' };
    if (start && end) {
      state.startDate = start;
      state.endDate = end;
    } else {
      const next = rangeForPreset(preset);
      state.startDate = formatDate(next.start);
      state.endDate = formatDate(next.end);
    }
    presetSelect.value = state.preset;
    if (compareSelect) compareSelect.value = state.compareMode;
    dispatchRange(false);
  };
  window.addEventListener('popstate', restoreRangeFromUrl);
  apiReady.then((DemoApi) => DemoApi.request('/api/periods?dim=daily')).then(async () => {
      calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
      restoreRangeFromUrl();
    }).catch(() => { range.textContent = '数据库日期加载失败'; });
  header.querySelector('[data-demo-refresh]').addEventListener('click', (event) => {
    const refreshButton = event.currentTarget;
    refreshButton.classList.add('is-spinning');
    window.dispatchEvent(new CustomEvent('tmall:refresh', { detail: { page: currentPage } }));
    showToast('正在刷新当前页面数据');
    window.setTimeout(() => refreshButton.classList.remove('is-spinning'), 500);
  });
  header.querySelector('[data-overview-report-refresh]')?.addEventListener('click', (event) => {
    const refreshButton = event.currentTarget;
    refreshButton.classList.add('is-spinning');
    window.dispatchEvent(new CustomEvent('tmall:refresh', { detail: { page: currentPage, source: 'report' } }));
    showToast('正在刷新经营报告');
    window.setTimeout(() => refreshButton.classList.remove('is-spinning'), 500);
  });
  header.querySelector('[data-demo-export]').addEventListener('click', () => {
    if (!window.dispatchEvent(new CustomEvent('tmall:export', { cancelable: true, detail: { page: currentPage } }))) return;
    exportTables();
  });
  themeButton.addEventListener('click', () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
    showToast(theme === 'dark' ? '已切换深色主题' : '已切换浅色主题');
  });
  document.querySelectorAll('[data-page-link]').forEach((link) => {
    if (link.dataset.pageLink === currentPage) link.setAttribute('aria-current', 'page');
    link.addEventListener('click', () => closeMobileNavigation(false));
  });
  const mobileNav = header.querySelector('[data-mobile-nav]');
  let mobileNavReturnFocus = null;
  const closeMobileNavigation = (restoreFocus = true) => {
    if (!sidebar.classList.contains('is-open')) return;
    sidebar.classList.remove('is-open');
    mobileNav.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('demo-scroll-lock');
    if (restoreFocus) (mobileNavReturnFocus || mobileNav).focus();
    mobileNavReturnFocus = null;
  };
  mobileNav.addEventListener('click', () => {
    if (sidebar.classList.contains('is-open')) { closeMobileNavigation(); return; }
    mobileNavReturnFocus = mobileNav;
    sidebar.classList.add('is-open');
    mobileNav.setAttribute('aria-expanded', 'true');
    document.body.classList.add('demo-scroll-lock');
    window.setTimeout(() => sidebar.querySelector('[data-page-link]')?.focus(), 0);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
      event.preventDefault();
      closeMobileNavigation();
    }
  });
  document.querySelectorAll('.segmented button').forEach((button) => button.addEventListener('click', () => {
    const group = button.closest('.segmented');
    group?.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
  }));
  const toolbox = document.querySelector('[data-toolbox-dialog]');
  const toolboxTriggers = [...document.querySelectorAll('[data-open-toolbox]')];
  let toolboxReturnFocus = null;
  const focusableSelector = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const isVisible = (element) => {
    if (!element || !document.contains(element)) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const getToolboxFocusables = () => Array.from(toolbox.querySelectorAll(focusableSelector)).filter((element) => {
    if (element.closest('[hidden]')) return false;
    return isVisible(element);
  });
  const restoreToolboxFocus = () => {
    const returnTargetInClosedSidebar = toolboxReturnFocus && sidebar.contains(toolboxReturnFocus) && !sidebar.classList.contains('is-open');
    const target = !returnTargetInClosedSidebar && isVisible(toolboxReturnFocus) ? toolboxReturnFocus : (isVisible(mobileNav) ? mobileNav : header.querySelector('[data-demo-refresh]'));
    if (target && typeof target.focus === 'function') target.focus();
  };
  const closeToolbox = () => {
    if (toolbox?.open) toolbox.close();
  };
  const openToolbox = (triggerButton) => {
    toolboxReturnFocus = triggerButton || document.activeElement;
    toolbox.showModal();
    document.body.classList.add('demo-scroll-lock');
    sidebar.classList.remove('is-open');
    mobileNav.setAttribute('aria-expanded', 'false');
    window.setTimeout(() => (getToolboxFocusables()[0] || toolbox).focus(), 0);
  };
  toolbox.addEventListener('close', () => {
    document.body.classList.remove('demo-scroll-lock');
    restoreToolboxFocus();
    toolboxReturnFocus = null;
  });
  toolbox.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeToolbox();
  });
  toolbox.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeToolbox();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusables = getToolboxFocusables();
    if (!focusables.length) {
      event.preventDefault();
      toolbox.focus();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && toolbox.open) closeToolbox();
  });
  toolboxTriggers.forEach((trigger) => trigger.addEventListener('click', () => openToolbox(trigger)));
  document.querySelector('[data-close-toolbox]').addEventListener('click', closeToolbox);
  toolbox.addEventListener('click', (event) => { if (event.target === toolbox) closeToolbox(); });
  document.querySelectorAll('[data-tool]').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('[data-tool]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelectorAll('[data-tool]').forEach((item) => item.setAttribute('aria-selected', String(item === button)));
    document.querySelectorAll('[data-tool-panel]').forEach((panel) => { panel.hidden = panel.dataset.toolPanel !== button.dataset.tool; });
  }));
  const importFile = document.querySelector('[data-import-file]');
  const importPreviewButton = document.querySelector('[data-import-preview]');
  const importConfirmButton = document.querySelector('[data-import-confirm]');
  const importPreviewPanel = document.querySelector('[data-import-preview-panel]');
  const importResult = document.querySelector('[data-import-result]');
  const importProgress = document.querySelector('[data-import-progress]');
  const importQuality = document.querySelector('[data-import-quality]');
  const importQualityDetail = document.querySelector('[data-import-quality-detail]');
  const importFields = document.querySelector('[data-import-fields]');
  const setImportProgress = (value) => importProgress.style.setProperty('--progress', String(Math.max(0, Math.min(100, Number(value) || 0)) / 100));
  let importPreviewQueue = [];
  let importPreviewErrors = [];
  let activeImportPreviewIndex = 0;
  let importCapabilities = {};
  const importSourceLabels = {
    product_day: '商品日度', dmp_product_day: 'DMP商品日度', store_day: '店铺日度', product_week: '商品周度',
    product_month: '商品月度', promotion_channel_day: '推广渠道日度',
    promotion_campaign_day: '推广计划日度', promotion_unit_day: '推广单元日度',
    promotion_product_day: '推广商品日度', refund_day: '退款日度', customer_day: '新老客日度',
  };
  const importFieldLabel = (key) => window.DemoLabels?.label?.('field', key, key) || key;
  const importMatchLabel = (key) => window.DemoLabels?.label?.('match', key, key) || key;
  const setImportStatus = (message) => { importResult.textContent = message; };
  const requiredMappings = (preview) => (preview.mapping_schema?.required || []).filter((key) => !preview.mapping?.[key]);
  const importQualityMessage = (preview) => {
    const source = importSourceLabels[preview.source_type] || preview.source_type || '未知报表';
    const range = preview.date_range?.start ? `；日期 ${preview.date_range.start} 至 ${preview.date_range.end}` : '';
    const estimate = preview.estimated_changes?.available
      ? `；预计新增 ${preview.estimated_changes.inserted} / 更新 ${preview.estimated_changes.updated}`
      : '';
    const excluded = preview.excluded_summary_rows ? `；剔除汇总行 ${preview.excluded_summary_rows}` : '';
    const governance = preview.source_resolution
      ? `；字段治理：主源重叠 ${preview.source_resolution.primary_overlap_fields?.length || 0}，DMP独有 ${preview.source_resolution.dmp_unique_fields?.length || 0}`
      : '';
    return `已识别为${source}；有效 ${preview.valid_rows}/${preview.total_rows} 行；重复业务键 ${preview.duplicate_keys} 个${excluded}${range}${estimate}${governance}`;
  };
  const renderImportPreview = (preview) => {
    if (!preview) {
      importPreviewPanel.hidden = true;
      importConfirmButton.disabled = true;
      return;
    }
    importPreviewPanel.hidden = false;
    document.querySelector('[data-import-preview-tabs]')?.replaceChildren(...importPreviewQueue.map((item, index) => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'button button--ghost toolbox-import-tab';
      tab.role = 'tab';
      tab.dataset.importPreviewFile = String(index);
      tab.setAttribute('aria-selected', String(index === activeImportPreviewIndex));
      tab.setAttribute('aria-controls', 'toolbox-panel-import');
      tab.tabIndex = index === activeImportPreviewIndex ? 0 : -1;
      tab.textContent = item.source_filename || `文件 ${index + 1}`;
      tab.addEventListener('click', () => {
        activeImportPreviewIndex = index;
        renderImportPreview(importPreviewQueue[index]);
      });
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const tabs = [...document.querySelectorAll('[data-import-preview-file]')];
        const current = tabs.indexOf(event.currentTarget);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next]?.focus();
        tabs[next]?.click();
      });
      return tab;
    }));
    importQuality.textContent = importQualityMessage(preview);
    if (preview.invalid_field_count) {
      importQuality.title = `${preview.invalid_field_count} field warnings; valid fields can still be imported`;
      const warningDetailNode = document.querySelector('[data-import-quality-detail]');
      if (warningDetailNode && !(preview.invalid_details || []).length) {
        warningDetailNode.textContent = (preview.field_warnings || []).slice(0, 10)
          .map((item) => `row ${item.row_number || '--'} / ${item.standard_field || '--'} / ${item.reason || 'invalid field'}`)
          .join('; ');
      }
    } else {
      importQuality.removeAttribute('title');
    }
    const invalidDetails = (preview.invalid_details || []).slice(0, 10)
      .map((item) => `第 ${item.row_number || '--'} 行 · ${item.standard_field || '--'} · ${item.reason || item.message || '数据无效'}`)
      .join('；');
    importQualityDetail.textContent = invalidDetails || '未发现异常行';
    importFields.replaceChildren(...(preview.fields || []).map((field) => {
      const row = document.createElement('tr');
      const sourceCell = document.createElement('td');
      sourceCell.textContent = field.source_column;
      row.appendChild(sourceCell);
      const typeCell = document.createElement('td');
      typeCell.textContent = importMatchLabel(field.inferred_type || 'empty');
      row.appendChild(typeCell);
      const mappingCell = document.createElement('td');
      const select = document.createElement('select');
      select.className = 'select';
      select.dataset.importMapping = field.source_column;
      select.setAttribute('aria-label', `字段映射：${field.source_column}`);
      const currentKey = Object.entries(preview.mapping || {}).find(([, source]) => source === field.source_column)?.[0] || '';
      ['', ...(preview.mapping_schema?.allowed || [])].forEach((key) => select.add(new Option(key ? importFieldLabel(key) : '未映射', key)));
      select.value = currentKey;
      select.addEventListener('change', () => {
        Object.entries(preview.mapping || {}).forEach(([key, source]) => {
          if (source === field.source_column || key === select.value) delete preview.mapping[key];
        });
        if (select.value) preview.mapping[select.value] = field.source_column;
        preview.required_unmapped = requiredMappings(preview);
        renderImportPreview(preview);
      });
      mappingCell.appendChild(select);
      row.appendChild(mappingCell);
      const matchCell = document.createElement('td');
      matchCell.textContent = select.value ? (field.match_status === 'manual' ? '手动' : importMatchLabel(field.match_status || 'matched')) : '未匹配';
      row.appendChild(matchCell);
      const sampleCell = document.createElement('td');
      sampleCell.textContent = field.sample_value || '--';
      row.appendChild(sampleCell);
      return row;
    }));
    const missing = requiredMappings(preview);
    importConfirmButton.disabled = Boolean(missing.length || preview.invalid_rows || preview.duplicate_keys);
    if (missing.length) setImportStatus(`缺少必填映射：${missing.map(importFieldLabel).join('、')}`);
    else if (preview.invalid_rows || preview.duplicate_keys) setImportStatus('质量校验未通过，请修正文件后重新预览');
    else setImportStatus('预览通过，可以确认导入');
  };
  importFile.addEventListener('change', () => {
    const files = Array.from(importFile.files || []);
    document.querySelector('[data-import-file-name]').textContent = files.length ? `已选择 ${files.length} 个表格文件` : '选择表格文件';
    importPreviewQueue = [];
    importPreviewErrors = [];
    activeImportPreviewIndex = 0;
    renderImportPreview(null);
    setImportProgress(0);
    setImportStatus(files.length ? `已选择 ${files.length} 个表格文件，请先预览并校验` : '等待选择文件');
  });
  importPreviewButton.addEventListener('click', async () => {
    const files = Array.from(importFile.files || []);
    if (!files.length) { setImportStatus('请先选择表格文件'); return; }
    importPreviewButton.disabled = true;
    importConfirmButton.disabled = true;
    importPreviewQueue = [];
    importPreviewErrors = [];
    activeImportPreviewIndex = 0;
    try {
      for (const [index, file] of files.entries()) {
        setImportProgress(Math.max(5, Math.round((index / files.length) * 80)));
        setImportStatus(`正在预览 ${index + 1}/${files.length}：${file.name}`);
        const form = new FormData();
        form.append('file', file);
        try {
          const payload = await DemoApi.domainRequest('/api/imports/preview?source_type=auto', { method: 'POST', body: form });
          importCapabilities = payload.capabilities || importCapabilities;
          importPreviewQueue.push(payload.data);
        } catch (error) {
          importPreviewErrors.push(`${file.name}：${error.message || '预览失败'}`);
        }
      }
      renderImportPreview(importPreviewQueue[0]);
      setImportProgress(100);
      const summary = `已预览 ${importPreviewQueue.length}/${files.length} 个文件`;
      setImportStatus(importPreviewErrors.length ? `${summary}；失败：${importPreviewErrors.join('；')}` : `${summary}，请检查映射后确认导入`);
    } catch (error) {
      setImportProgress(0);
      setImportStatus(error.message || '预览失败');
    } finally {
      importPreviewButton.disabled = false;
    }
  });
  importConfirmButton.addEventListener('click', async () => {
    const pending = importPreviewQueue.slice();
    if (!pending.length) { setImportStatus('请先预览文件'); return; }
    if (Object.keys(importCapabilities).length && !DemoApi.can({ capabilities: importCapabilities }, 'can_import')) { setImportStatus('当前数据源不允许导入'); return; }
    if (pending.some((preview) => requiredMappings(preview).length || preview.invalid_rows || preview.duplicate_keys)) {
      setImportStatus('请先完成必填映射并通过质量校验');
      return;
    }
    importConfirmButton.disabled = true;
    const failures = [];
    const results = [];
    const completedPreviewIds = new Set();
    try {
      for (const [index, preview] of pending.entries()) {
        setImportProgress(Math.max(5, Math.round((index / pending.length) * 95)));
        setImportStatus(`正在导入 ${index + 1}/${pending.length}：${preview.source_filename || '表格文件'}`);
        try {
          const payload = await DemoApi.domainRequest('/api/imports', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preview_id: preview.id, mapping: preview.mapping }),
          });
          results.push(payload.data);
          completedPreviewIds.add(preview.id);
        } catch (error) {
          failures.push(`${preview.source_filename || '表格文件'}：${error.message || '导入失败'}`);
        }
      }
      const inserted = results.reduce((sum, item) => sum + Number(item.inserted_count || 0), 0);
      const updated = results.reduce((sum, item) => sum + Number(item.updated_count || 0), 0);
      const resolution = results.reduce((sum, item) => {
        const current = item.source_resolution || {};
        return { fallback_filled: sum.fallback_filled + Number(current.fallback_filled || 0), reference_only: sum.reference_only + Number(current.reference_only || 0), conflicts: sum.conflicts + Number(current.conflicts || 0) };
      }, { fallback_filled: 0, reference_only: 0, conflicts: 0 });
      const resolutionSummary = `；DMP补齐 ${resolution.fallback_filled}，参考 ${resolution.reference_only}，冲突 ${resolution.conflicts}${resolution.conflicts ? '（按主源保留，DMP值留痕）' : ''}`;
      importPreviewQueue = failures.length ? pending.filter((preview) => !completedPreviewIds.has(preview.id)) : [];
      activeImportPreviewIndex = Math.min(activeImportPreviewIndex, Math.max(0, importPreviewQueue.length - 1));
      setImportProgress(failures.length ? 0 : 100);
      setImportStatus(failures.length
        ? `已导入 ${results.length}/${pending.length} 个文件；新增 ${inserted}，更新 ${updated}${resolutionSummary}；失败：${failures.join('；')}`
        : `已导入 ${results.length} 个文件；新增 ${inserted}，更新 ${updated}${resolutionSummary}`);
      if (!failures.length) renderImportPreview(null);
    } catch (error) {
      setImportProgress(0);
      setImportStatus(error.message || '导入失败');
    } finally {
      importConfirmButton.disabled = !failures.length;
    }
  });
  const scanResult = document.querySelector('[data-scan-result]');
  const scanFolder = document.querySelector('[data-scan-folder]');
  const selectScanFolderButton = document.querySelector('[data-select-scan-folder]');
  const addScanButton = document.querySelector('[data-add-scan]');
  const scanCron = () => {
    const frequency = document.querySelector('[data-scan-frequency]').value;
    const [hour, minute] = document.querySelector('[data-scan-time]').value.split(':').map(Number);
    if (frequency === 'weekly') return `${minute} ${hour} * * 1`;
    if (frequency === 'monthly') return `${minute} ${hour} 1 * *`;
    return `${minute} ${hour} * * *`;
  };
  const scanPlanLabel = (cron) => {
    const [minute, hour, day, , weekday] = String(cron || '').split(' ');
    const time = `${String(hour || '0').padStart(2, '0')}:${String(minute || '0').padStart(2, '0')}`;
    if (weekday === '1') return `每周一 ${time}`;
    if (day === '1') return `每月 1 日 ${time}`;
    return `每天 ${time}`;
  };
  const formatScanTime = (value) => value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short', hour12: false }).format(new Date(value)) : '--';
  const scanAction = (icon, label, handler) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'button button--ghost';
    button.title = label;
    button.setAttribute('aria-label', label);
    button.innerHTML = `<i data-lucide="${icon}"></i>`;
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      try { await handler(); } finally { if (button.isConnected) button.disabled = false; }
    });
    return button;
  };
  const scanRunSummary = (payload) => {
    const result = payload?.data || payload || {};
    const discovered = Number(result.discovered_count || 0);
    const imported = Number(result.imported_count || 0);
    const blocked = Number(result.blocked_count || 0);
    const failed = Number(result.failed_count || 0);
    if (!discovered && !imported && !blocked && !failed) {
      return '扫描完成：未发现可导入的新文件，请检查文件夹路径和匹配规则。';
    }
    return `扫描完成：发现 ${discovered} 个文件，导入 ${imported} 个，阻断 ${blocked} 个，失败 ${failed} 个。`;
  };
  const loadScanJobs = async () => {
    const tbody = document.querySelector('[data-scan-list]');
    tbody.innerHTML = '<tr><td colspan="5">正在加载扫描任务</td></tr>';
    const payload = await requestDomainApi('/api/import-scans');
    const rows = payload.data || [];
    tbody.replaceChildren();
    if (!rows.length) {
      const row = tbody.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 5;
      cell.textContent = '暂无文件夹扫描任务';
      return;
    }
    rows.forEach((job) => {
      const row = tbody.insertRow();
      const taskCell = row.insertCell();
      const taskName = document.createElement('strong');
      const folderPath = document.createElement('span');
      taskName.textContent = job.task_name || '未命名任务';
      folderPath.className = 'panel__hint toolbox-scan-path';
      folderPath.textContent = job.folder_path || '--';
      taskCell.append(taskName, folderPath);
      row.insertCell().textContent = scanPlanLabel(job.cron_expr);
      const statusCell = row.insertCell();
      const badge = document.createElement('span');
      const isRunning = job.status === 'running';
      badge.className = `badge ${isRunning || job.enabled ? 'badge--success' : ''}`.trim();
      badge.textContent = job.enabled ? '已启用' : '已停用';
      badge.textContent = isRunning ? '正在扫描' : (job.enabled ? '已启用' : '已停用');
      statusCell.appendChild(badge);
      row.insertCell().textContent = formatScanTime(job.last_run);
      const actions = row.insertCell();
      actions.className = 'table-actions';
      actions.append(
        scanAction('play', '立即扫描', async () => {
          scanResult.textContent = `正在扫描 ${job.task_name || '任务'}…`;
          try {
            const result = await requestDomainApi(`/api/import-scans/${Number(job.id)}/run`, {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: true }),
            });
            scanResult.textContent = scanRunSummary(result);
            await loadScanJobs();
          }
          catch (error) { scanResult.textContent = error.message || '扫描失败'; }
        }),
        scanAction(job.enabled ? 'pause' : 'play-circle', job.enabled ? '停用任务' : '启用任务', async () => {
          try {
            await requestDomainApi(`/api/import-scans/${Number(job.id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !job.enabled }) });
            scanResult.textContent = job.enabled ? '任务已停用' : '任务已启用';
            await loadScanJobs();
          } catch (error) { scanResult.textContent = error.message || '更新任务失败'; }
        }),
      );
      if (isRunning) actions.firstElementChild.disabled = true;
    });
    window.lucide?.createIcons();
  };
  if (window.tmallDesktop?.selectScanFolder) {
    selectScanFolderButton.hidden = false;
    scanFolder.readOnly = true;
    selectScanFolderButton.addEventListener('click', async () => {
      const selected = await window.tmallDesktop.selectScanFolder();
      if (selected) scanFolder.value = selected;
    });
  }
  addScanButton.addEventListener('click', async () => {
    const name = document.querySelector('[data-scan-name]').value.trim();
    if (!name) { scanResult.textContent = '请输入任务名称'; return; }
    if (!scanFolder.value.trim()) { scanResult.textContent = '请选择扫描文件夹'; return; }
    if (addScanButton.disabled) return;
    addScanButton.disabled = true;
    scanResult.textContent = '正在创建扫描任务…';
    try {
      await requestDomainApi('/api/import-scans', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task_name: name, folder_path: scanFolder.value.trim(), file_pattern: document.querySelector('[data-scan-pattern]').value.trim() || '*.xlsx;*.xls;*.csv;*.zip', source_type: document.querySelector('[data-scan-source]').value, cron_expr: scanCron(), enabled: document.querySelector('[data-scan-enabled]').checked }) });
      scanResult.textContent = '扫描任务已创建';
      document.querySelector('[data-scan-name]').value = '';
      await loadScanJobs();
    } catch (error) { scanResult.textContent = error.message || '创建扫描任务失败'; }
    finally { addScanButton.disabled = false; }
  });
  document.querySelector('[data-refresh-scans]').addEventListener('click', () => loadScanJobs().catch((error) => { scanResult.textContent = error.message || '扫描任务加载失败'; }));
  loadScanJobs().catch((error) => { document.querySelector('[data-scan-list]').innerHTML = '<tr><td colspan="5">扫描任务加载失败</td></tr>'; scanResult.textContent = error.message || '扫描任务加载失败'; });
  window.DemoShell = { nav, meta, getDateRange: () => ({ ...state }), showToast, setStatus: announce, setTheme, getTheme: () => theme };
  if (window.lucide) window.lucide.createIcons();
})();
