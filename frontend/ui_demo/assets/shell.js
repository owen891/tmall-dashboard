(function () {
  const assetBase = new URL('.', document.currentScript?.src || window.location.href);
  const loadScript = (src) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });

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
  const route = (page) => {
    if (page === 'overview') return '/';
    return `/${page}`;
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
    <div class="demo-period" role="group" aria-label="统计时间">
      <select class="demo-period__select" data-date-preset aria-label="快捷时间范围">
        <option value="today">今日</option><option value="yesterday">昨日</option><option value="7d">近7天</option><option value="30d" selected>近30天</option><option value="90d">近90天</option><option value="custom">自定义</option>
      </select>
      <button type="button" class="demo-period__trigger tabular" data-date-trigger aria-expanded="false"><i data-lucide="calendar-days"></i><span data-period-range>数据库日期加载中</span></button>
      <select class="demo-period__select demo-period__compare" data-compare-mode aria-label="对比方式">
        <option value="none">不对比</option><option value="previous_period">环比</option><option value="year_over_year">同比</option>
      </select>
      <div class="demo-period__popover" data-period-popover hidden>
        <div class="demo-calendar__toolbar"><button type="button" data-calendar-nav="-1" aria-label="上两个月">‹</button><strong>自定义日期范围</strong><button type="button" data-calendar-nav="1" aria-label="下两个月">›</button></div>
        <div class="demo-calendar__months"><section data-calendar-month="0"></section><section data-calendar-month="1"></section></div>
        <div class="demo-calendar__footer"><span data-calendar-help>请选择开始日期</span><button class="button button--ghost" type="button" data-calendar-cancel>取消</button></div>
      </div>
    </div>
    <div class="demo-topbar__tools"><button class="demo-tool demo-mobile-nav" type="button" title="打开导航" aria-label="打开导航" aria-expanded="false" data-mobile-nav><i data-lucide="menu"></i></button><button class="demo-tool" type="button" title="刷新" aria-label="刷新" data-demo-refresh><i data-lucide="refresh-cw"></i></button><button class="demo-tool" type="button" title="导出" aria-label="导出当前表格" data-demo-export><i data-lucide="download"></i></button><button class="demo-tool" type="button" title="切换深色主题" aria-label="切换深色主题" data-demo-theme><i data-lucide="moon"></i></button></div>`;

  if (currentPage === 'lifecycle') header.querySelector('.demo-period').hidden = true;

  document.body.insertAdjacentHTML('beforeend', `
    <div class="demo-shell-status" data-demo-status role="status" aria-live="polite" aria-atomic="true"></div>
    <div class="demo-toast" data-demo-toast role="status" aria-live="polite" aria-atomic="true"></div>
    <div class="toolbox-overlay" data-toolbox-overlay></div>
    <aside class="toolbox-drawer" data-toolbox-drawer role="dialog" aria-modal="true" aria-labelledby="toolboxTitle" aria-hidden="true" inert tabindex="-1">
      <div class="toolbox-drawer__header"><div><h2 id="toolboxTitle">数据工具箱</h2><span class="panel__hint">数据导入与自动任务</span></div><button class="button button--ghost" type="button" data-close-toolbox aria-label="关闭"><i data-lucide="x"></i></button></div>
      <div class="toolbox-drawer__body">
        <div class="toolbox-tools" role="group" aria-label="选择工具">
          <button class="toolbox-tool" type="button" aria-pressed="true" data-tool="import"><strong>经营数据导入</strong><span>使用现有导入服务处理 Excel 工作簿</span></button>
          <button class="toolbox-tool" type="button" aria-pressed="false" data-tool="schedule"><strong>定时导入任务</strong><span>按文件规则自动执行数据同步</span></button>
        </div>
        <section class="plain-panel panel" data-tool-panel="import"><div class="panel__header"><div><h3 class="panel__title">导入经营数据</h3><p class="panel__hint">文件将交给项目现有导入服务解析并写入数据库</p></div><span class="badge badge--info">Excel</span></div><label class="upload-zone" for="demoImportFile"><span><i data-lucide="file-up"></i><strong data-import-file-name>选择 Excel 文件</strong><span>支持 .xlsx / .xls，ID 字段按文本保留</span></span></label><input class="sr-only" id="demoImportFile" data-import-file type="file" accept=".xlsx,.xls"><div class="section-toolbar" style="margin-top:10px"><button class="button button--primary" type="button" data-start-import><i data-lucide="upload"></i>开始导入</button></div><div class="import-progress" aria-hidden="true"><span data-import-progress></span></div><div class="import-result" data-import-result>等待选择文件</div></section>
        <section class="plain-panel panel" data-tool-panel="schedule" hidden><div class="panel__header"><div><h3 class="panel__title">定时导入任务</h3><p class="panel__hint">创建后写入数据库并由现有调度器执行</p></div></div><div class="modal-form__body"><label>任务名称<input class="input" data-schedule-name placeholder="例如：每日经营数据同步"></label><div class="filter-group"><select class="select" data-schedule-frequency aria-label="执行频率"><option value="daily">每天</option><option value="weekly">每周</option><option value="monthly">每月</option></select><input class="input" type="time" value="08:00" data-schedule-time aria-label="执行时间"></div><label>文件匹配模式<input class="input" data-schedule-pattern value="*.xlsx"></label><button class="button button--primary" type="button" data-add-schedule>添加任务</button><div class="import-result" data-schedule-result>等待创建任务</div></div><div class="data-table-wrap" style="margin-top:12px"><table class="data-table"><thead><tr><th>任务</th><th>计划</th><th>状态</th></tr></thead><tbody data-schedule-list><tr><td colspan="3">加载中</td></tr></tbody></table></div></section>
      </div>
    </aside>`);

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
  const visibleTables = () => Array.from(document.querySelectorAll('.data-table')).filter((table) => {
    if (table.closest('[hidden]')) return false;
    const toolboxParent = table.closest('[data-toolbox-drawer]');
    if (toolboxParent && !toolboxParent.classList.contains('is-open')) return false;
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
    setStoredTheme(theme);
    syncThemeButton();
    announce(theme === 'dark' ? '已切换深色主题' : '已切换浅色主题');
  };
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
    const end = preset === 'yesterday' ? shiftDays(anchorDate, -1) : new Date(anchorDate);
    return { start: shiftDays(end, -(offsets[preset] || 0)), end };
  };
  const dispatchRange = () => {
    range.textContent = `${state.startDate} ~ ${state.endDate}`;
    const url = new URL(window.location.href);
    url.searchParams.set('startDate', state.startDate);
    url.searchParams.set('endDate', state.endDate);
    url.searchParams.set('preset', state.preset);
    url.searchParams.set('compare', state.compareMode);
    history.replaceState(null, '', url);
    window.dispatchEvent(new CustomEvent('tmall:date-range-change', { detail: { ...state } }));
  };
  const applyRange = (start, end, preset = 'custom') => {
    state = { ...state, startDate: formatDate(start), endDate: formatDate(end), preset };
    presetSelect.value = preset;
    dispatchRange();
  };
  const renderCalendar = () => {
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
        const inRange = state.startDate && state.endDate && value >= state.startDate && value <= state.endDate;
        const selected = value === state.startDate || value === state.endDate;
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
  const resetDraftRange = () => {
    draftStart = null;
    popover.querySelector('[data-calendar-help]').textContent = '请选择开始日期';
  };
  const closePopover = (resetDraft = false) => {
    if (resetDraft) resetDraftRange();
    setPopover(false);
  };
  const selectPreset = (preset) => {
    if (preset === 'custom') { setPopover(true); return; }
    const next = rangeForPreset(preset);
    applyRange(next.start, next.end, preset);
  };
  trigger.addEventListener('click', () => setPopover(popover.hasAttribute('hidden')));
  presetSelect.addEventListener('change', () => selectPreset(presetSelect.value));
  compareSelect.addEventListener('change', () => { state.compareMode = compareSelect.value; dispatchRange(); });
  popover.querySelector('[data-calendar-cancel]').addEventListener('click', () => closePopover(true));
  popover.querySelectorAll('[data-calendar-nav]').forEach((button) => button.addEventListener('click', () => {
    calendarBase = new Date(calendarBase.getFullYear(), calendarBase.getMonth() + Number(button.dataset.calendarNav) * 2, 1);
    renderCalendar();
  }));
  popover.addEventListener('click', (event) => {
    const button = event.target.closest('[data-calendar-date]');
    if (!button) return;
    const chosen = parseDate(button.dataset.calendarDate);
    if (!draftStart) {
      draftStart = chosen;
      popover.querySelector('[data-calendar-help]').textContent = `${formatDate(chosen)}，请选择结束日期`;
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
  compareSelect.value = state.compareMode;
  window.TmallDateRange = { getState: () => ({ ...state }) };
  apiReady.then((DemoApi) => DemoApi.request('/api/periods?dim=daily')).then((rows) => {
      const available = Array.isArray(rows) ? rows : (Array.isArray(rows?.value) ? rows.value : []);
      const latest = available[0]?.period || '';
      if (latest) anchorDate = parseDate(latest);
      calendarBase = new Date(anchorDate.getFullYear(), anchorDate.getMonth() - 1, 1);
      const queryStart = params.get('startDate');
      const queryEnd = params.get('endDate');
      if (queryStart && queryEnd) applyRange(parseDate(queryStart), parseDate(queryEnd), state.preset);
      else selectPreset(state.preset);
    }).catch(() => { range.textContent = '数据库日期加载失败'; });
  header.querySelector('[data-demo-refresh]').addEventListener('click', (event) => {
    event.currentTarget.classList.add('is-spinning');
    window.dispatchEvent(new CustomEvent('tmall:refresh', { detail: { page: currentPage } }));
    showToast('正在刷新当前页面数据');
    window.setTimeout(() => event.currentTarget.classList.remove('is-spinning'), 500);
  });
  header.querySelector('[data-demo-export]').addEventListener('click', exportTables);
  themeButton.addEventListener('click', () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
    showToast(theme === 'dark' ? '已切换深色主题' : '已切换浅色主题');
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
  const toolboxTrigger = sidebar.querySelector('[data-open-toolbox]');
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
    if (!toolbox.classList.contains('is-open')) return;
    toolbox.classList.remove('is-open');
    toolboxOverlay.classList.remove('is-open');
    toolbox.setAttribute('aria-hidden', 'true');
    toolbox.setAttribute('inert', '');
    document.body.classList.remove('demo-scroll-lock');
    restoreToolboxFocus();
    toolboxReturnFocus = null;
  };
  const openToolbox = (triggerButton) => {
    toolboxReturnFocus = triggerButton || document.activeElement;
    toolbox.removeAttribute('inert');
    toolbox.setAttribute('aria-hidden', 'false');
    toolbox.classList.add('is-open');
    toolboxOverlay.classList.add('is-open');
    document.body.classList.add('demo-scroll-lock');
    sidebar.classList.remove('is-open');
    mobileNav.setAttribute('aria-expanded', 'false');
    window.setTimeout(() => (getToolboxFocusables()[0] || toolbox).focus(), 0);
  };
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
    if (event.key === 'Escape') closeToolbox();
  });
  toolboxTrigger.addEventListener('click', () => openToolbox(toolboxTrigger));
  document.querySelector('[data-close-toolbox]').addEventListener('click', closeToolbox);
  toolboxOverlay.addEventListener('click', closeToolbox);
  document.querySelectorAll('[data-tool]').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('[data-tool]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelectorAll('[data-tool-panel]').forEach((panel) => { panel.hidden = panel.dataset.toolPanel !== button.dataset.tool; });
  }));
  const importFile = document.querySelector('[data-import-file]');
  importFile.addEventListener('change', () => { document.querySelector('[data-import-file-name]').textContent = importFile.files[0]?.name || '选择 Excel 文件'; });
  const pollImport = async (taskId) => {
    const result = document.querySelector('[data-import-result]');
    const progress = document.querySelector('[data-import-progress]');
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const status = await requestApi(`/api/import_progress/${taskId}`);
      progress.style.width = `${Number(status.progress || 0)}%`;
      result.textContent = status.message || '导入处理中';
      if (status.status === 'completed' || status.status === 'error') return;
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    result.textContent = '导入仍在后台运行，请稍后查看数据库状态';
  };
  document.querySelector('[data-start-import]').addEventListener('click', async () => {
    const result = document.querySelector('[data-import-result]');
    const progress = document.querySelector('[data-import-progress]');
    if (!importFile.files[0]) { result.textContent = '请先选择 Excel 文件'; return; }
    const file = importFile.files[0];
    const form = new FormData();
    form.append('file', file);
    progress.style.width = '5%';
    result.textContent = '正在提交导入任务';
    try {
      const payload = await requestApi('/api/upload/data', { method: 'POST', body: form, headers: {} });
      await pollImport(payload.task_id);
    } catch (error) {
      progress.style.width = '0';
      result.textContent = error.message || '导入失败';
    }
  });
  const loadSchedules = async () => {
    const rows = await requestApi('/api/scheduled_tasks');
    const tbody = document.querySelector('[data-schedule-list]');
    tbody.replaceChildren();
    if (!rows.length) {
      const row = tbody.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 3;
      cell.textContent = '暂无定时任务';
      return;
    }
    rows.forEach((task) => {
      const row = tbody.insertRow();
      row.insertCell().textContent = task.task_name || '未命名任务';
      const scheduleCell = row.insertCell();
      scheduleCell.className = 'tabular';
      scheduleCell.textContent = task.cron_label || task.cron_expr || '--';
      const statusCell = row.insertCell();
      const badge = document.createElement('span');
      badge.className = `badge ${task.enabled ? 'badge--success' : ''}`.trim();
      badge.textContent = task.enabled ? '启用' : '停用';
      statusCell.appendChild(badge);
    });
  };
  document.querySelector('[data-add-schedule]').addEventListener('click', async () => {
    const result = document.querySelector('[data-schedule-result]');
    const name = document.querySelector('[data-schedule-name]').value.trim();
    const frequency = document.querySelector('[data-schedule-frequency]').value;
    const [hour, minute] = document.querySelector('[data-schedule-time]').value.split(':').map(Number);
    const cron = frequency === 'weekly' ? `${minute} ${hour} * * 1` : frequency === 'monthly' ? `${minute} ${hour} 1 * *` : `${minute} ${hour} * * *`;
    if (!name) { result.textContent = '请输入任务名称'; return; }
    try {
      await requestApi('/api/scheduled_tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task_name: name, cron_expr: cron, file_pattern: document.querySelector('[data-schedule-pattern]').value.trim() || '*.xlsx' }) });
      result.textContent = '任务已创建';
      await loadSchedules();
    } catch (error) { result.textContent = error.message || '创建失败'; }
  });
  loadSchedules().catch(() => { document.querySelector('[data-schedule-list]').innerHTML = '<tr><td colspan="3">定时任务加载失败</td></tr>'; });
  window.DemoShell = { nav, meta, getDateRange: () => ({ ...state }), showToast, setStatus: announce, setTheme, getTheme: () => theme };
  if (window.lucide) window.lucide.createIcons();
})();
