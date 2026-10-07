(function () {

  // 全局 HTML 转义函数，防止 XSS
  window.escapeHtml = function (value) {
    return String(value ?? '').replace(/[&<>"']/g, function (char) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
    });
  };

  // 全局前端错误上报
  (function setupErrorReporting() {
    var errorBuffer = [];
    var isSending = false;

    function sendErrors() {
      if (isSending || errorBuffer.length === 0) return;
      isSending = true;
      var errors = errorBuffer.splice(0, errorBuffer.length);
      try {
        fetch('/api/frontend-errors', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ errors: errors, url: location.href, userAgent: navigator.userAgent }),
        }).catch(function () { /* 上报失败静默 */ });
      } catch (e) { /* 静默 */ }
      finally { isSending = false; }
    }

    function reportError(type, message, source, lineno, colno, error) {
      var entry = {
        type: type,
        message: String(message || '').slice(0, 500),
        source: source || '',
        lineno: lineno || 0,
        colno: colno || 0,
        stack: error && error.stack ? String(error.stack).slice(0, 1000) : '',
        timestamp: new Date().toISOString(),
      };
      errorBuffer.push(entry);
      // 批量上报，最多每5秒一次
      setTimeout(sendErrors, 1000);
    }

    window.addEventListener('error', function (e) {
      reportError('js_error', e.message, e.filename, e.lineno, e.colno, e.error);
    }, true);

    window.addEventListener('unhandledrejection', function (e) {
      var reason = e.reason;
      reportError('unhandled_promise', reason && reason.message ? reason.message : String(reason), '', 0, 0, reason);
    });

    // 资源加载错误
    window.addEventListener('error', function (e) {
      if (e.target && (e.target.tagName === 'SCRIPT' || e.target.tagName === 'LINK' || e.target.tagName === 'IMG')) {
        reportError('resource_error', e.target.src || e.target.href, '', 0, 0, null);
      }
    }, true);

    window.TmallFrontendErrors = { report: reportError };
  })();

  const assetBase = new URL('.', document.currentScript?.src || window.location.href);
  const pendingScripts = new Map();
  const loadScriptOnce = (src) => {
    const href = new URL(src, assetBase).href;
    if (pendingScripts.has(href)) return pendingScripts.get(href);
    const existing = [...document.scripts].find((script) => {
      try { return new URL(script.src, document.baseURI).href === href; } catch (_) { return false; }
    });
    if (existing) return Promise.resolve(existing);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = href;
      script.dataset.tmallRuntimeAsset = 'true';
      script.onload = () => resolve(script);
      script.onerror = () => reject(new Error(`前端资源加载失败: ${href}`));
      document.head.appendChild(script);
    }).catch((error) => {
      pendingScripts.delete(href);
      window.TmallFrontendErrors?.report('resource_load_failed', error.message, href, 0, 0, error);
      throw error;
    });
    pendingScripts.set(href, promise);
    return promise;
  };
  const loadOptionalScript = (name) => loadScriptOnce(new URL(name, assetBase).href).catch((error) => {
    console.error(`[tmall] optional asset unavailable: ${name}`, error);
    return null;
  });

  // 本文件动态加载的脚本必须带 ?v= 才能穿透 7 天静态缓存，否则改了文件用户也一直拿旧版本。
  // 改这些文件后同步 bump 这里，并 bump 各页面 HTML 里 shell.js 自己的 ?v=。
  const RUNTIME_ASSET_V = '20261003a';
  // table-controls.js / version.js / version-check.js / desktop-integration.js
  // 不在任何页面的 HTML 里，只由这里动态加载；ui-components.js 两者都有（版本号需保持一致）。
  loadOptionalScript(`table-controls.js?v=${RUNTIME_ASSET_V}`);
  loadOptionalScript(`ui-components.js?v=${RUNTIME_ASSET_V}`);
  loadScriptOnce(new URL(`version.js?v=${RUNTIME_ASSET_V}`, assetBase).href)
    .then(() => loadScriptOnce(new URL(`version-check.js?v=${RUNTIME_ASSET_V}`, assetBase).href))
    .catch((error) => {
      window.TmallFrontendErrors?.report('runtime_bootstrap_failed', error.message, error.stack || '', 0, 0, error);
      console.error('[tmall] version check unavailable', error);
    });
  loadOptionalScript(`desktop-integration.js?v=${RUNTIME_ASSET_V}`);

  const liveAdapters = { 'core-product-analysis': 'core-product-analysis-live.js', overview: 'overview-live.js', products: 'products-live.js', promotion: 'promotion-live.js', 'keyword-promotion': 'keyword-promotion-live.js', 'market-ranking': 'market-ranking-live.js', 'flow-source': 'flow-source-live.js', 'rival-analysis': 'rival-analysis-live.js' };
  const liveAdapter = liveAdapters[document.body.dataset.page];
  const apiReady = window.DemoApi
    ? Promise.resolve(window.DemoApi)
    : loadScriptOnce(new URL(`api.js?v=${RUNTIME_ASSET_V}`, assetBase).href).then(() => window.DemoApi);
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
  const scanErrorMessage = (error) => {
    const code = error?.code;
    if (code === 'SCAN_FOLDER_NOT_ALLOWED' || error?.message?.includes('outside IMPORT_SCAN_ALLOWED_ROOTS')) return '该文件夹不在允许扫描目录中。请配置 IMPORT_SCAN_ALLOWED_ROOTS 后重启服务，或使用桌面端选择文件夹。';
    if (code === 'SCAN_FOLDER_NOT_FOUND' || error?.message?.includes('must be an existing directory')) return '文件夹不存在。请确认本机绝对路径存在且服务进程有访问权限。';
    if (code === 'SCAN_FOLDER_LOCAL_ONLY') return '仅支持本机磁盘目录，不支持网络共享路径。';
    if (code === 'SCAN_FOLDER_SYMLINK_UNSUPPORTED') return '不支持符号链接目录，请选择真实本地目录。';
    if (code === 'SCAN_FOLDER_TRAVERSAL') return '文件夹路径不能包含 ..。';
    if (code === 'SCAN_DISABLED') return '扫描任务已停用，请先启用后再运行。';
    if (code === 'SCAN_RUNNING') return '扫描任务正在运行，请稍后刷新记录。';
    return error?.message || '扫描任务操作失败';
  };
  window.TmallScanUi = { errorMessage: scanErrorMessage };
  const DATA_STATES = ['loading', 'no-data', 'insufficient-data', 'missing-fields', 'calculation-failed', 'source-unavailable', 'partial'];
  window.TmallDataStates = Object.freeze(DATA_STATES.slice());
  if (liveAdapter && !window.DemoApi) {
    apiReady
      .then(() => loadScriptOnce(new URL(`${liveAdapter}?v=${RUNTIME_ASSET_V}`, assetBase).href))
      .catch((error) => {
        window.TmallFrontendErrors?.report('page_bootstrap_failed', error.message, liveAdapter, 0, 0, error);
        console.error(`[tmall] page adapter unavailable: ${liveAdapter}`, error);
      });
  }
  const navGroups = [
    {
      label: '店铺',
      items: [
        ['overview', '数据概览', 'layout-dashboard', 'overview'],
        ['category-dashboard', '品类经营看板', 'pie-chart', 'category-dashboard'],
        ['goals', '经营目标', 'target', 'goals'],
        ['reviews', '经营复盘', 'clipboard-check', 'reviews'],
        ['period-review', '周期复盘', 'file-text', 'period-review'],
      ],
    },
    {
      label: '商品',
      items: [
        ['products', '商品运营', 'package', 'products'],
        ['lifecycle', '生命周期', 'refresh-cw', 'lifecycle'],
        ['keyword-promotion', '关键词选品', 'filter', 'keyword-promotion'],
        ['core-product-analysis', '核心单品九维', 'layers', 'core-product-analysis'],
      ],
    },
    {
      label: '付费',
      items: [
        ['promotion', '推广分析', 'megaphone', 'promotion'],
        ['new-products', '新品推广', 'sparkles', 'new-products'],
        ['creative-board', '素材点击率', 'image', 'creative-board'],
        ['flow-source', '流量来源', 'git-branch', 'flow-source'],
      ],
    },
    {
      label: '市场',
      items: [
        ['rival-analysis', '竞店竞品', 'users', 'rival-analysis'],
        ['market-ranking', '市场分析', 'trending-up', 'market-ranking'],
      ],
    },
    {
      label: '工具',
      items: [
        ['analysis', '自定义分析', 'bar-chart-3', 'analysis'],
        ['data-collection', '数据采集', 'download', 'data-collection'],
        ['data-center', '数据中心', 'database', 'data-center'],
        ['settings', '设置', 'settings', 'settings'],
      ],
    },
  ];
  const nav = navGroups.flatMap((group) => group.items);
  const meta = {
    products: ['商品运营', '商品经营表现与选款效率'],
    'flow-source': ['流量来源', '生意参谋第一次访问来源，渠道结构与转化分析'],
    'rival-analysis': ['竞店竞品', '竞店核心指标对比与竞品商品分析'],
    promotion: ['推广分析', '按投放粒度解释花费、成交与投产效率'],
    'new-products': ['新品推广', '按上架节奏分析新品投放效率与销售联动'],
    'creative-board': ['素材点击率', '按单品沉淀素材历史点击质量'],
    'core-product-analysis': ['核心单品九维', '月度复盘沉淀：核心单品在九个经营维度的完整分析'],
    'keyword-promotion': ['关键词选品', '按属性标签筛选推广效果好的标品商品'],
    'market-ranking': ['市场分析', '生意参谋市场排行，类目对比与热卖趋势洞察'],
    lifecycle: ['生命周期', '按商品查看跨月经营表现与累计贡献'],
    analysis: ['自定义分析', '自由选择指标、维度与时间范围生成分析图表'],
    'category-dashboard': ['品类经营看板', '按日、周、月和自定义周期跟踪品类经营表现'],
    'data-collection': ['数据采集', '各数据源采集状态管理与手动触发'],
    reviews: ['经营复盘', '查看待复盘动作与经营周期差异'],
    'period-review': ['周期复盘', '系统汇总业绩、目标差距、市场与动作素材，人工补结论与卡点'],
    'data-center': ['数据中心', '导入、校验和管理经营数据'],
    settings: ['设置', '维护店铺与业务默认配置'],
    goals: ['经营目标', '按年、季、月、周、日跟踪净销售额目标'],
    catalog: ['Demo 目录', '按业务域浏览全部页面设计'],
    overview: ['数据概览', '店铺经营核心指标与趋势']
  };
  const currentPage = document.body.dataset.page || 'products';
  const activePageMap = { 'product-detail': 'products' };
  const activePage = activePageMap[currentPage] || currentPage;
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
    const path = page === 'overview' ? '/' : (page === 'catalog' ? '/component-catalog' : `/${page}`);
    return window.DemoNavigation?.fromCurrent ? window.DemoNavigation.fromCurrent(path) : path;
  };
  const sidebar = document.querySelector('[data-shell-sidebar]');
  const header = document.querySelector('[data-shell-header]');
  if (!sidebar || !header) return;
  sidebar.id = sidebar.id || 'demo-sidebar';

  // Lucide's public helper scans the whole document on every call. Most page
  // updates only add a few icons, so skip the scan when no unprocessed icons
  // exist and keep repeated renders from blocking the main thread.
  if (window.lucide?.createIcons) {
    const createIcons = window.lucide.createIcons.bind(window.lucide);
    window.lucide.createIcons = (...args) => {
      const pendingIcons = document.querySelectorAll('[data-lucide]:not([data-lucide-rendered])');
      if (!pendingIcons.length) return;
      pendingIcons.forEach(icon => {
        icon.setAttribute('data-lucide-rendered', 'true');
        if (!icon.hasAttribute('aria-label')) icon.setAttribute('aria-hidden', 'true');
      });
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
    <nav class="demo-nav" aria-label="主导航">${navGroups.map((group, groupIndex) => `<section class="demo-nav__section${groupIndex === 0 ? ' demo-nav__section--primary' : ''}"><span class="demo-nav__label">${group.label}</span><div class="demo-nav__group">${group.items.map(([id, label, iconName, page]) => `<a class="demo-nav__item" data-page-link="${id}" href="${route(page)}" aria-label="${label}" title="${label}"><i data-lucide="${iconName}"></i><span>${label}</span>${id === 'reviews' ? '<b class="demo-nav__badge" data-nav-action-count hidden aria-label="待处理动作数量"></b>' : ''}</a>`).join('')}</div></section>`).join('')}</nav>
    <div class="demo-sidebar__footer">
      <div class="demo-sidebar__meta" data-sidebar-meta role="group" aria-label="版本与项目链接">
        <div class="demo-sidebar__utility-row">
          <div class="demo-sidebar__version-group">
            <span class="status-dot" aria-label="系统正常" title="系统正常"></span>
            <span class="demo-sidebar__version" data-sidebar-version>加载中…</span>
            <span class="demo-sidebar__update-status" data-sidebar-update-status role="status" aria-live="polite"></span>
          </div>
          <div class="demo-sidebar__utility-actions">
            <button class="demo-sidebar__meta-action" type="button" data-open-toolbox aria-label="导入数据" title="导入数据"><i data-lucide="upload" aria-hidden="true"></i><span class="demo-sidebar__meta-action-label">导入数据</span></button>
            <button class="demo-sidebar__meta-action" type="button" data-demo-theme aria-label="切换深色主题" title="切换深色主题"><i data-lucide="moon" aria-hidden="true"></i><span class="demo-sidebar__meta-action-label">主题</span></button>
          </div>
          <div class="demo-sidebar__meta-actions">
            <button class="demo-sidebar__meta-action" type="button" data-sidebar-version-trigger aria-label="查看版本与更新" title="查看版本与更新"><svg class="demo-sidebar__github-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.043-1.61-4.043-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.084-.73.084-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.292-1.552 3.297-1.23 3.297-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg><span class="demo-sidebar__meta-action-label">版本更新</span></button>
            <a class="demo-sidebar__meta-action" href="https://github.com/owen891/tmall-dashboard" target="_blank" rel="noreferrer" aria-label="GitHub 仓库" title="GitHub 仓库"><svg class="demo-sidebar__github-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.043-1.61-4.043-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.084-.73.084-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg><span class="demo-sidebar__meta-action-label">GitHub</span></a>
            <a class="demo-sidebar__meta-action" href="https://github.com/owen891/tmall-dashboard/releases" target="_blank" rel="noreferrer" aria-label="更新说明" title="更新说明"><i data-lucide="file-text" aria-hidden="true"></i><span class="demo-sidebar__meta-action-label">更新说明</span></a>
          </div>
        </div>
      </div>
    </div>`;
  sidebar.querySelectorAll('.demo-sidebar__meta-actions > a').forEach((link) => link.remove());
  sidebar.insertAdjacentHTML('beforeend', `
    <dialog class="demo-version-dialog" data-sidebar-version-dialog aria-labelledby="demoVersionDialogTitle">
      <div class="demo-version-dialog__header">
        <div>
          <span class="demo-version-dialog__eyebrow">当前版本</span>
          <h2 id="demoVersionDialogTitle" data-sidebar-dialog-version>加载中…</h2>
          <p data-sidebar-dialog-status>可检查最新版本</p>
        </div>
        <button class="demo-version-dialog__refresh" type="button" data-sidebar-check-update aria-label="检查更新" title="检查更新"><i data-lucide="refresh-cw" aria-hidden="true"></i></button>
      </div>
      <div class="demo-version-dialog__actions">
        <a class="demo-version-dialog__notes" href="https://github.com/owen891/tmall-dashboard/releases" target="_blank" rel="noreferrer"><i data-lucide="file-text" aria-hidden="true"></i><span>查看更新日志</span><i data-lucide="external-link" aria-hidden="true"></i></a>
        <div class="demo-version-dialog__repo-list" aria-label="代码仓库">
          <a class="demo-version-dialog__repo" href="https://github.com/owen891/tmall-dashboard" target="_blank" rel="noreferrer" aria-label="打开 GitHub 仓库"><svg class="demo-sidebar__github-icon demo-version-dialog__repo-mark" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.043-1.61-4.043-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.084-.73.084-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.292-1.552 3.297-1.23 3.297-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg><span class="demo-version-dialog__repo-copy"><strong>GitHub</strong><code>owen891/tmall-dashboard</code></span><i data-lucide="external-link" aria-hidden="true"></i></a>
          <a class="demo-version-dialog__repo" href="https://gitcode.com/owen891/tmall-dashboard" target="_blank" rel="noreferrer" aria-label="打开 GitCode 仓库"><i class="demo-version-dialog__repo-mark" data-lucide="git-branch" aria-hidden="true"></i><span class="demo-version-dialog__repo-copy"><strong>GitCode</strong><code>owen891/tmall-dashboard</code></span><i data-lucide="external-link" aria-hidden="true"></i></a>
        </div>
        <button class="demo-version-dialog__reload" type="button" data-sidebar-dialog-reload><i data-lucide="download" aria-hidden="true"></i><span>立即刷新</span></button>
      </div>
      <button class="demo-version-dialog__close" type="button" data-sidebar-dialog-close>关闭</button>
    </dialog>`);

  const hideCategoryPages = new Set(['data-center', 'settings', 'manage', 'catalog']);
  const categoryMarkup = hideCategoryPages.has(currentPage) ? '' : `
    <div class="demo-category" role="group" aria-label="品类模式">
      <select class="demo-period__select demo-category__select" data-category-mode aria-label="品类模式">
        <option value="sock">标品袜子</option><option value="all">全部品类</option>
      </select>
    </div>`;
  const periodReviewControls = currentPage === 'period-review' ? `
    <div class="demo-period demo-period--review" role="group" aria-label="复盘粒度与对比">
      <div class="pr-mode-tabs" role="tablist" aria-label="复盘周期">
        <button type="button" data-pr-mode="day" role="tab" aria-selected="false">日复盘</button>
        <button type="button" class="is-active" data-pr-mode="week" role="tab" aria-selected="true">周复盘</button>
        <button type="button" data-pr-mode="month" role="tab" aria-selected="false">月复盘</button>
      </div>
      <label class="pr-compact-field pr-review-period"><span>复盘周期</span><select data-pr-period aria-label="选择复盘周期"><option>加载中…</option></select></label>
      <label class="pr-compact-field"><span>对比</span><select data-pr-compare aria-label="对比方式">
        <option value="previous">环比上期</option><option value="yoy">同比去年同期</option><option value="custom">自定义对比周期</option><option value="none">不对比</option>
      </select></label>
      <label class="pr-compact-field" data-pr-compare-period-field hidden><span>周期</span><select data-pr-compare-period aria-label="对比周期"></select></label>
    </div>` : '';
  header.innerHTML = `
    <button class="demo-tool demo-sidebar-toggle" type="button" title="收起导航" aria-label="收起导航" aria-controls="demo-sidebar" aria-expanded="true" data-sidebar-toggle><i data-lucide="chevron-left"></i></button>
    <div class="demo-topbar__filters">
      ${categoryMarkup}
      <div class="demo-period" role="group" aria-label="统计时间">
      <select class="demo-period__select" data-date-preset aria-label="快捷时间范围">
        <option value="today">今日</option><option value="yesterday">昨日</option><option value="7d">近7天</option><option value="30d" selected>近30天</option><option value="90d">近90天</option><option value="this_week">本周</option><option value="last_week">上周</option><option value="this_month">本月</option><option value="last_month">上月</option><option value="custom">自定义</option>
      </select>
      <button type="button" class="demo-period__trigger tabular" data-date-trigger aria-expanded="false"><i data-lucide="calendar-days" aria-hidden="true"></i><span data-period-range>数据库日期加载中…</span></button>
      ${currentPage === 'overview' ? '<select class="demo-period__select demo-period__compare" data-compare-mode aria-label="对比方式"><option value="none">不对比</option><option value="previous_period">环比</option><option value="year_over_year">同比</option></select>' : ''}
      <div class="demo-period__popover" data-period-popover hidden>
        <div class="demo-calendar__toolbar"><button type="button" data-calendar-nav="-1" aria-label="上两个月">‹</button><strong>自定义日期范围</strong><button type="button" data-calendar-nav="1" aria-label="下两个月">›</button></div>
        <div class="demo-calendar__months"><section data-calendar-month="0"></section><section data-calendar-month="1"></section></div>
        <div class="demo-calendar__footer"><span data-calendar-help>请选择开始日期</span><button class="ui-button ui-button--ghost" type="button" data-calendar-cancel>取消</button></div>
      </div>
      </div>
      ${periodReviewControls}
    </div>
    <div class="demo-topbar__tools"><button class="demo-tool demo-mobile-nav" type="button" title="打开导航" aria-label="打开导航" aria-expanded="false" data-mobile-nav><i data-lucide="menu"></i></button><button class="demo-tool" type="button" title="刷新" aria-label="刷新" data-demo-refresh><i data-lucide="refresh-cw"></i></button><button class="demo-tool" type="button" title="导出" aria-label="导出当前表格" data-demo-export><i data-lucide="download"></i></button></div>`;

  const categorySelect = header.querySelector('[data-category-mode]');
  const CATEGORY_STORAGE_KEY = 'dashboard.categoryMode';
  const readCategoryMode = () => { try { const v = localStorage.getItem(CATEGORY_STORAGE_KEY); if (v) return v; } catch (_) {} return 'sock'; };
  const hasStoredCategoryMode = () => { try { return Boolean(localStorage.getItem(CATEGORY_STORAGE_KEY)); } catch (_) { return false; } };
  const storeCategoryMode = (v) => { try { localStorage.setItem(CATEGORY_STORAGE_KEY, v); } catch (_) {} };
  if (categorySelect) {
    let categoryChangedByUser = false;
    categorySelect.value = readCategoryMode();
    categorySelect.addEventListener('change', () => {
      categoryChangedByUser = true;
      storeCategoryMode(categorySelect.value);
      if (currentPage !== 'period-review') window.location.reload();
    });
    requestApi('/api/settings').then((payload) => {
      const modes = payload?.data?.category_modes || payload?.category_modes || [];
      if (!Array.isArray(modes) || !modes.length) return;
      categorySelect.innerHTML = modes.filter((m) => m && m.enabled !== false).map((m) => `<option value="${String(m.value)}">${String(m.label)}</option>`).join('');
      if (!categoryChangedByUser && !hasStoredCategoryMode() && payload?.data?.category_mode_default) {
        storeCategoryMode(payload.data.category_mode_default);
      }
      if (!categoryChangedByUser) categorySelect.value = readCategoryMode();
      if (!categorySelect.value && !categoryChangedByUser && payload?.data?.category_mode_default) {
        categorySelect.value = payload.data.category_mode_default;
        storeCategoryMode(categorySelect.value);
      }
    }).catch(() => {});
  }

  const pagesWithoutDateRange = new Set(['data-center', 'data-collection', 'settings', 'goals', 'creative-board']);
  if (currentPage === 'lifecycle' || pagesWithoutDateRange.has(currentPage)) header.querySelector('.demo-period').hidden = true;
  if (currentPage === 'overview') {
    header.querySelector('.demo-topbar__tools').insertAdjacentHTML('beforeend', `
      <button class="ui-button ui-button--primary demo-overview-action" type="button" aria-label="新增运营动作" title="新增运营动作" data-capability-key="overview.create_action" data-overview-action-open><i data-lucide="plus"></i><span>新增运营动作</span></button>`);
    apiReady.then((api) => api?.loadPageCapabilities?.('overview')).catch(() => {});
  }

  document.body.insertAdjacentHTML('beforeend', `
    <div class="demo-shell-status" data-demo-status role="status" aria-live="polite" aria-atomic="true"></div>
    <div class="demo-toast" data-demo-toast role="status" aria-live="polite" aria-atomic="true"></div>
    <dialog class="toolbox-dialog" data-toolbox-dialog data-modal-kind="flow" aria-labelledby="toolboxTitle">
      <div class="toolbox-dialog__header"><div><h2 id="toolboxTitle">数据工具箱</h2><span class="panel__hint">数据导入与自动任务</span><span class="panel__hint" data-flow-impact>\u5f71\u54cd\u8303\u56f4\uff1a\u4ec5\u5f53\u524d\u5bfc\u5165\u6279\u6b21\u53ca\u5176\u5bfc\u5165\u8bb0\u5f55</span></div><button class="ui-button ui-button--ghost" type="button" data-close-toolbox aria-label="关闭"><i data-lucide="x"></i></button></div>
      <div class="toolbox-dialog__body">
        <div class="toolbox-tools" role="tablist" aria-label="选择工具">
          <button class="toolbox-tool" id="toolbox-tab-import" role="tab" type="button" aria-selected="true" aria-pressed="true" aria-controls="toolbox-panel-import" data-tool="import"><strong>经营数据导入</strong><span>使用现有导入服务处理 Excel 工作簿</span></button>
          <button class="toolbox-tool" id="toolbox-tab-scan" role="tab" type="button" aria-selected="false" aria-pressed="false" aria-controls="toolbox-panel-scan" data-tool="scan"><strong>文件夹扫描任务</strong><span>扫描指定文件夹并自动导入新报表</span></button>
        </div>
        <section class="ui-panel" id="toolbox-panel-import" role="tabpanel" aria-labelledby="toolbox-tab-import" data-tool-panel="import"><div class="panel__header"><div><h3 class="panel__title">导入经营数据</h3><p class="panel__hint">先预览文件、确认字段映射和质量，再写入数据库</p></div><span class="ui-badge ui-badge--info">表格</span></div><label class="upload-zone" for="demoImportFile"><span><i data-lucide="file-up"></i><strong data-import-file-name>选择表格文件</strong><span>支持 .xlsx / .xls / .csv / .zip；可多选，文件选择器内可按 Ctrl+A 全选</span></span></label><input class="sr-only" id="demoImportFile" data-import-file type="file" accept=".xlsx,.xls,.csv,.zip" multiple><div class="ui-filter-toolbar toolbox-import-actions"><button class="ui-button ui-button--primary" type="button" data-import-preview><i data-lucide="scan-search"></i>预览并校验</button><button class="ui-button ui-button--primary" type="button" data-import-confirm disabled><i data-lucide="database"></i>确认导入</button></div><div class="import-progress" aria-hidden="true"><span data-import-progress></span></div><div class="import-result" data-import-result role="status" aria-live="polite">等待选择文件</div><section class="import-preview-panel" data-import-preview-panel hidden><div class="import-preview-panel__summary"><div class="toolbox-import-tabs" data-import-preview-tabs role="tablist" aria-label="预览文件"></div><p class="panel__hint" data-import-quality>选择文件后查看质量摘要</p><p class="panel__hint" data-import-quality-detail>未发现异常行</p></div><div class="ui-table-wrap"><table class="ui-data-table import-preview-table"><thead><tr><th>原始列</th><th>推断类型</th><th>标准字段映射</th><th>匹配状态</th><th>样例</th></tr></thead><tbody data-import-fields></tbody></table></div></section></section>
        <section class="ui-panel" id="toolbox-panel-scan" role="tabpanel" aria-labelledby="toolbox-tab-scan" data-tool-panel="scan" hidden><div class="panel__header"><div><h3 class="panel__title">文件夹扫描任务</h3><p class="panel__hint">定期检查指定文件夹，新文件会复用导入校验和批次审计</p></div><button class="ui-button ui-button--ghost" type="button" data-refresh-scans aria-label="刷新扫描任务"><i data-lucide="refresh-cw"></i>刷新</button></div><div class="modal-form__body toolbox-scan-form"><label>任务名称<input class="input" name="scan_name" data-scan-name placeholder="例如：每日经营数据扫描" autocomplete="off"></label><label>扫描文件夹<span class="toolbox-scan-folder"><input class="input" name="scan_folder" data-scan-folder placeholder="请选择或输入本机文件夹绝对路径" autocomplete="off"><button class="ui-button" type="button" data-select-scan-folder hidden><i data-lucide="folder-open"></i>选择文件夹</button></span></label><div class="filter-group"><label>文件匹配规则<input class="input" name="scan_pattern" data-scan-pattern value="*.xlsx;*.xls;*.csv;*.zip" autocomplete="off"></label><label>报表来源<select class="select" name="scan_source" data-scan-source><option value="auto">自动识别</option><option value="product_day">商品日度</option><option value="dmp_product_day">DMP 商品日度</option><option value="store_day">店铺日度</option><option value="refund_day">退款日度</option><option value="customer_day">客户日度</option><option value="product_week">商品周度</option><option value="product_month">商品月度</option><option value="promotion_channel_day">推广渠道日度</option><option value="promotion_campaign_day">推广计划日度</option><option value="promotion_unit_day">推广单元日度</option><option value="promotion_product_day">推广商品日度</option></select></label></div><div class="filter-group"><label>扫描频率<select class="select" name="scan_frequency" data-scan-frequency><option value="daily">每天</option><option value="weekly">每周一</option><option value="monthly">每月 1 日</option></select></label><label>扫描时间<input class="input" name="scan_time" data-scan-time type="time" value="08:00" autocomplete="off"></label></div><label class="toolbox-scan-enabled"><input type="checkbox" name="scan_enabled" data-scan-enabled checked> 创建后立即启用</label><button class="ui-button ui-button--primary" type="button" data-add-scan><i data-lucide="folder-plus"></i>添加扫描任务</button><div class="import-result" data-scan-result role="status" aria-live="polite">等待创建任务</div></div><div class="ui-table-wrap toolbox-scan-table"><table class="ui-data-table"><thead><tr><th>任务与文件夹</th><th>计划</th><th>状态</th><th>最近运行</th><th>操作</th></tr></thead><tbody data-scan-list><tr><td colspan="5">加载中…</td></tr></tbody></table></div></section>
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
  const visibleTables = () => Array.from(document.querySelectorAll('.ui-data-table')).filter((table) => {
    if (table.closest('[hidden]')) return false;
    const toolboxParent = table.closest('[data-toolbox-dialog]');
    if (toolboxParent && !toolboxParent.open) return false;
    const style = window.getComputedStyle(table);
    const rect = table.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  });
  const csvCell = (value) => `"${String(value ?? '').replace(/\s+/g, ' ').trim().replace(/"/g, '""')}"`;
  const tableToCsv = (table, index) => {
    const title = table.closest('.ui-panel')?.querySelector('.panel__title')?.textContent?.trim() || `表格 ${index + 1}`;
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
  const themeButton = document.querySelector('[data-demo-theme]');
  const versionTrigger = document.querySelector('[data-sidebar-version-trigger]');
  const versionLabel = document.querySelector('[data-sidebar-version]');
  const versionStatus = document.querySelector('[data-sidebar-update-status]');
  const versionDialog = document.querySelector('[data-sidebar-version-dialog]');
  const dialogVersion = document.querySelector('[data-sidebar-dialog-version]');
  const dialogStatus = document.querySelector('[data-sidebar-dialog-status]');
  const syncVersionDialog = () => {
    if (dialogVersion) dialogVersion.textContent = versionLabel?.textContent?.trim() || '加载中…';
    if (dialogStatus) dialogStatus.textContent = versionStatus?.textContent?.trim() || '可检查最新版本';
  };
  const openVersionDialog = () => {
    if (!versionDialog) return;
    syncVersionDialog();
    if (!versionDialog.open) versionDialog.showModal();
  };
  versionTrigger?.addEventListener('click', openVersionDialog);
  document.querySelector('[data-sidebar-dialog-close]')?.addEventListener('click', () => versionDialog?.close());
  document.querySelector('[data-sidebar-dialog-reload]')?.addEventListener('click', () => window.location.reload());
  if (versionStatus) new MutationObserver(syncVersionDialog).observe(versionStatus, { childList: true, characterData: true, subtree: true });
  const syncThemeButton = () => {
    const dark = theme === 'dark';
    themeButton.setAttribute('aria-label', dark ? '切换浅色主题' : '切换深色主题');
    themeButton.setAttribute('title', dark ? '切换浅色主题' : '切换深色主题');
    themeButton.innerHTML = `<i data-lucide="${dark ? 'lightbulb' : 'moon'}" aria-hidden="true"></i><span class="demo-sidebar__meta-action-label">主题</span>`;
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

  // 日期范围状态仓已拆至 runtime/date-range-store.js；本文件只负责装配。
  // 与其他 runtime 模块（date-range-scope 等）一致：由 shell 在初始化时
  // 加载，页面适配器经 window.TmallDateRange 消费。
  loadScriptOnce(new URL(`runtime/date-range-store.js?v=${RUNTIME_ASSET_V}`, assetBase).href).then(() => {
    if (!window.TmallRuntime?.createDateRangeStore) throw new Error('date-range-store 模块未导出 createDateRangeStore');
    window.TmallDateRange = window.TmallRuntime.createDateRangeStore({
      header,
      currentPage,
      apiReady,
      pagesWithoutDateRange,
    });
  }).catch((error) => {
    window.TmallFrontendErrors?.report('runtime_bootstrap_failed', error.message, 'runtime/date-range-store.js', 0, 0, error);
    console.error('[tmall] date-range-store unavailable', error);
  });
  const getDateRangeState = () => window.TmallDateRange?.getState?.() || {};

  header.querySelector('[data-demo-refresh]').addEventListener('click', (event) => {
    const refreshButton = event.currentTarget;
    refreshButton.classList.add('is-spinning');
    window.dispatchEvent(new CustomEvent('tmall:refresh', { detail: { page: currentPage } }));
    showToast('正在刷新当前页面数据');
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
    const targetPage = link.dataset.pageLink === 'component-catalog' ? 'catalog' : link.dataset.pageLink;
    if (targetPage === activePage) link.setAttribute('aria-current', 'page');
    link.addEventListener('click', () => closeMobileNavigation(false));
  });
  const mobileNav = header.querySelector('[data-mobile-nav]');
  const sidebarToggle = header.querySelector('[data-sidebar-toggle]');
  const sidebarStorageKey = 'tmall-demo-sidebar-collapsed';
  const isDesktopSidebar = () => window.matchMedia('(min-width: 761px)').matches;
  const readSidebarCollapsed = () => {
    try { return localStorage.getItem(sidebarStorageKey) === 'true'; } catch (_) { return false; }
  };
  const storeSidebarCollapsed = (collapsed) => {
    try { localStorage.setItem(sidebarStorageKey, String(collapsed)); } catch (_) {}
  };
  const setSidebarCollapsed = (collapsed, persist = true) => {
    const active = Boolean(collapsed) && isDesktopSidebar();
    document.body.classList.toggle('demo-sidebar-collapsed', active);
    sidebar.classList.toggle('is-collapsed', active);
    sidebarToggle?.setAttribute('aria-expanded', String(!active));
    sidebarToggle?.setAttribute('aria-label', active ? '展开导航' : '收起导航');
    sidebarToggle?.setAttribute('title', active ? '展开导航' : '收起导航');
    const icon = sidebarToggle?.querySelector('[data-lucide], .lucide');
    if (icon) {
      icon.setAttribute('data-lucide', active ? 'chevron-right' : 'chevron-left');
      icon.removeAttribute('data-lucide-rendered');
      window.lucide?.createIcons?.();
    }
    if (persist && isDesktopSidebar()) storeSidebarCollapsed(active);
  };
  sidebarToggle?.addEventListener('click', () => setSidebarCollapsed(!document.body.classList.contains('demo-sidebar-collapsed')));
  const mobileNavBackdrop = document.createElement('button');
  mobileNavBackdrop.className = 'demo-nav-backdrop';
  mobileNavBackdrop.type = 'button';
  mobileNavBackdrop.setAttribute('aria-label', '关闭导航');
  // 不参与 Tab 序列：遮罩铺满视口，焦点环画在视口之外＝用户看不见焦点在哪（WCAG 2.4.7）。
  // 与 TmallUI.detailDrawer 的遮罩一致（那边也是 tabIndex = -1）。键盘关闭走 Esc。
  mobileNavBackdrop.tabIndex = -1;
  mobileNavBackdrop.hidden = true;
  document.body.appendChild(mobileNavBackdrop);
  let mobileNavReturnFocus = null;
  const isMobileDrawer = () => window.matchMedia('(max-width: 760px)').matches;
  // 抽屉打开时把「侧栏与遮罩以外的所有 body 子元素」设为 inert —— 遮罩已经把它们盖住了，
  // 键盘 / 读屏不该还能走到看不见的内容上（WCAG 2.4.3 焦点顺序）。这与 <dialog showModal()>
  // 的原生行为一致。实测修复前：抽屉里 20 个导航项走完后，焦点会逃逸到遮罩后的日期选择器、
  // 汉堡按钮、KPI 卡片；只 inert .demo-main 还会漏掉 body 级的 skip-link。
  // 只撤自己加过的（drawerInerted 记录），避免把别处设的 inert 一起撤掉。
  // 用「读当前状态重算」而不是在开/关两处各写一遍 —— openToolbox 是直接改 class 的
  // 另一条路径，漏了会把 inert 永久留在页面上。
  let drawerInerted = [];
  const syncPageInert = () => {
    drawerInerted.forEach((el) => el.removeAttribute('inert'));
    drawerInerted = [];
    if (!(isMobileDrawer() && sidebar.classList.contains('is-open'))) return;
    // 只把抽屉真正盖住的两块设为 inert，**不要**图省事去 inert「除侧栏外的一切」：
    // body 层级还有 toolbox-dialog（inert 后 showModal() 打不开）和 aria-live 状态区
    // （inert 后 toast / 播报会被静音），一刀切会误伤。
    //   .demo-main  = 顶栏 + 主内容（遮罩底下的全部页面内容）
    //   skip-link   = body 级插入的「跳到主要内容」，不处理会漏出来
    [document.querySelector('.demo-main'), document.querySelector('[data-skip-link]')].forEach((el) => {
      if (el && !el.hasAttribute('inert')) { el.setAttribute('inert', ''); drawerInerted.push(el); }
    });
  };
  const setSidebarState = (open) => {
    sidebar.classList.toggle('is-open', open);
    const drawerMode = isMobileDrawer();
    const hidden = drawerMode && !open;
    sidebar.toggleAttribute('inert', hidden);
    sidebar.setAttribute('aria-hidden', String(hidden));
    mobileNavBackdrop.hidden = !(drawerMode && open);
    mobileNavBackdrop.classList.toggle('is-visible', drawerMode && open);
    syncPageInert();
  };
  const closeMobileNavigation = (restoreFocus = true) => {
    if (!sidebar.classList.contains('is-open')) return;
    setSidebarState(false);
    mobileNav.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('demo-scroll-lock');
    if (restoreFocus) (mobileNavReturnFocus || mobileNav).focus();
    mobileNavReturnFocus = null;
  };
  mobileNav.addEventListener('click', () => {
    if (sidebar.classList.contains('is-open')) { closeMobileNavigation(); return; }
    mobileNavReturnFocus = mobileNav;
    setSidebarState(true);
    mobileNav.setAttribute('aria-expanded', 'true');
    document.body.classList.add('demo-scroll-lock');
    window.setTimeout(() => sidebar.querySelector('[data-page-link]')?.focus(), 0);
  });
  mobileNavBackdrop.addEventListener('click', () => closeMobileNavigation());
  window.addEventListener('resize', () => {
    setSidebarState(sidebar.classList.contains('is-open'));
    setSidebarCollapsed(readSidebarCollapsed(), false);
  });
  setSidebarState(false);
  setSidebarCollapsed(readSidebarCollapsed(), false);
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
    // 用 setSidebarState(false) 而不是手改 class：它同时会收起遮罩、撤掉外壳 inert。
    // 原先只 remove('is-open')，从移动端抽屉点「导入数据」后遮罩会留在页面上
    // （铺满视口且拦截指针事件），整页点不动。
    setSidebarState(false);
    mobileNav.setAttribute('aria-expanded', 'false');
    toolbox.showModal();
    document.body.classList.add('demo-scroll-lock');
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
  const normalizeImportPreview = (value) => {
    const preview = value && typeof value === 'object' ? value : {};
    return {
      ...preview,
      mapping: preview.mapping && typeof preview.mapping === 'object' ? preview.mapping : {},
      mapping_schema: preview.mapping_schema && typeof preview.mapping_schema === 'object' ? preview.mapping_schema : {},
      fields: Array.isArray(preview.fields) ? preview.fields.filter((field) => field && typeof field === 'object') : [],
      invalid_details: Array.isArray(preview.invalid_details) ? preview.invalid_details : [],
      field_warnings: Array.isArray(preview.field_warnings) ? preview.field_warnings : [],
    };
  };
  const requiredMappings = (preview) => (preview?.mapping_schema?.required || []).filter((key) => !preview.mapping?.[key]);
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
    preview = normalizeImportPreview(preview);
    importPreviewPanel.hidden = false;
    document.querySelector('[data-import-preview-tabs]')?.replaceChildren(...importPreviewQueue.map((item, index) => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'ui-button ui-button--ghost toolbox-import-tab';
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
  if (currentPage !== 'data-center') {
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
          importPreviewQueue.push(normalizeImportPreview(payload.data));
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
  }
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
    button.className = 'ui-button ui-button--ghost';
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
    tbody.innerHTML = '<tr><td colspan="5">正在加载扫描任务…</td></tr>';
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
      badge.className = `ui-badge ${isRunning || job.enabled ? 'ui-badge--success' : ''}`.trim();
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
            catch (error) { scanResult.textContent = window.TmallScanUi?.errorMessage?.(error) || error.message || '扫描失败'; }
        }),
        scanAction(job.enabled ? 'pause' : 'play-circle', job.enabled ? '停用任务' : '启用任务', async () => {
          try {
            await requestDomainApi(`/api/import-scans/${Number(job.id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !job.enabled }) });
            scanResult.textContent = job.enabled ? '任务已停用' : '任务已启用';
            await loadScanJobs();
          } catch (error) { scanResult.textContent = window.TmallScanUi?.errorMessage?.(error) || error.message || '更新任务失败'; }
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
    } catch (error) { scanResult.textContent = window.TmallScanUi?.errorMessage?.(error) || error.message || '创建扫描任务失败'; }
    finally { addScanButton.disabled = false; }
  });
  document.querySelector('[data-refresh-scans]').addEventListener('click', () => loadScanJobs().catch((error) => { scanResult.textContent = window.TmallScanUi?.errorMessage?.(error) || error.message || '扫描任务加载失败'; }));
  loadScanJobs().catch((error) => { document.querySelector('[data-scan-list]').innerHTML = '<tr><td colspan="5">扫描任务加载失败</td></tr>'; scanResult.textContent = window.TmallScanUi?.errorMessage?.(error) || error.message || '扫描任务加载失败'; });
  async function syncActionCount() {
    const badge = sidebar.querySelector('[data-nav-action-count]');
    if (!badge) return;
    try {
      const payload = await requestDomainApi('/api/actions?limit=200');
      const rows = Array.isArray(payload?.data) ? payload.data : [];
      const count = rows.filter((action) => ['pending_review', 'blocked', 'pending_execution', 'executing'].includes(action.status)).length;
      badge.textContent = String(count);
      badge.hidden = count === 0;
      badge.setAttribute('aria-label', `待处理动作 ${count} 项`);
    } catch (_) {
      badge.hidden = true;
    }
  }
  syncActionCount();
  window.addEventListener('tmall:refresh', syncActionCount);
  window.DemoShell = { nav, meta, getDateRange: getDateRangeState, showToast, setStatus: announce, setTheme, getTheme: () => theme };
  if (window.lucide) window.lucide.createIcons();
})();
