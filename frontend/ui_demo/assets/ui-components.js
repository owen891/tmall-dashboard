(function () {
  const text = (node, value) => {
    if (node) node.textContent = value == null || value === '' ? '--' : String(value);
    return node;
  };
  const create = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) text(node, value);
    return node;
  };
  const clear = (node) => {
    if (node) node.replaceChildren();
    return node;
  };
  const formatDateTime = (value) => {
    if (!value) return '--';
    const normalized = String(value).replace('T', ' ').replace(/\.\d+Z?$/, '');
    return normalized.slice(0, 16);
  };
  const dataStateTitles = {
    loading: '加载中…', 'no-data': '暂无数据', 'insufficient-data': '数据积累中…',
    'missing-fields': '缺少必要字段', 'calculation-failed': '指标计算失败',
    'source-unavailable': '数据来源不可用', partial: '部分数据可用',
  };
  const dataStateDetails = {
    loading: '正在读取数据', 'no-data': '当前筛选条件没有可展示的数据', 'insufficient-data': '补充更多数据后才能计算',
    'missing-fields': '请检查导入字段', 'calculation-failed': '请稍后重试', 'source-unavailable': '请检查数据源连接',
    partial: '部分字段暂不可用',
  };
  const stateKey = (state) => (dataStateTitles[state] ? state : 'calculation-failed');
  const stateDetail = (state, details) => {
    if (state === 'missing-fields' && Array.isArray(details?.fields) && details.fields.length) return `缺少：${details.fields.join('、')}`;
    return details?.message || details?.reason || dataStateDetails[state] || '';
  };
  const retryButton = (handler) => {
    const node = create('button', 'ui-button ui-button--ghost', '重试');
    node.type = 'button';
    node.addEventListener('click', handler);
    return node;
  };
  // Inline variant for status slots: fills the given container (title + detail + optional retry).
  const renderDataState = (node, state, details = {}) => {
    if (!node) return node;
    const key = stateKey(state);
    node.replaceChildren();
    node.classList.add('data-state');
    node.dataset.state = key;
    node.setAttribute('role', 'status');
    node.setAttribute('aria-live', 'polite');
    node.append(create('strong', '', dataStateTitles[key]), create('span', '', stateDetail(key, details)));
    if (details?.retry) node.append(retryButton(details.retry));
    return node;
  };
  const status = renderDataState;
  const icon = (name, label) => {
    const node = create('i');
    node.dataset.lucide = name;
    if (label) node.setAttribute('aria-label', label);
    else node.setAttribute('aria-hidden', 'true');
    return node;
  };
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const isBlank = (value) => value == null || value === '';
  const formatNumber = (value, digits = 0) => {
    if (isBlank(value)) return '--';
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '--';
  };
  // unit 'auto' renders values from 1e4 as 万元 (123456 -> ¥12.35万); 'none' keeps the raw amount.
  const formatMoney = (value, options = {}) => {
    if (typeof options === 'number') options = { digits: options };
    const { digits = 2, unit = 'none', currency = '¥' } = options;
    if (isBlank(value)) return '--';
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    if (unit === 'auto' && Math.abs(number) >= 10000) {
      return `${currency}${(number / 10000).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}万`;
    }
    return `${currency}${number.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
  };
  // mode 'ratio' expects 0.15 -> 15%; mode 'percent' expects 15 -> 15%. No auto-scaling heuristic.
  const formatPercent = (value, options = {}) => {
    if (typeof options === 'number') options = { digits: options };
    const { digits = 1, mode = 'ratio' } = options;
    if (isBlank(value)) return '--';
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return `${(mode === 'percent' ? number : number * 100).toFixed(digits)}%`;
  };
  const format = Object.freeze({ number: formatNumber, money: formatMoney, percent: formatPercent, dateTime: formatDateTime });
  const isElement = (value) => Boolean(value && value.nodeType === 1);

  let iconScanQueued = false;
  const renderIcon = (node) => {
    // lucide-custom.min.js only supports full-document createIcons(), but factory-built
    // nodes are still detached when their factory runs — scan once the current task
    // has attached them.
    if (!node || !window.lucide?.createIcons || iconScanQueued) return node;
    iconScanQueued = true;
    Promise.resolve().then(() => {
      iconScanQueued = false;
      try { window.lucide.createIcons(); } catch (error) { /* a lucide failure must not break component creation */ }
    });
    return node;
  };
  const button = ({ label, icon: iconName, variant = 'secondary', size, type = 'button', disabled = false, className = '', ariaLabel = '' } = {}) => {
    const node = create('button', ['ui-button', `ui-button--${variant}`, size ? `ui-button--${size}` : '', className].filter(Boolean).join(' '), label);
    node.type = type;
    node.disabled = disabled;
    if (ariaLabel) node.setAttribute('aria-label', ariaLabel);
    if (iconName) { node.replaceChildren(icon(iconName), ...(label ? [document.createTextNode(label)] : [])); renderIcon(node); }
    return node;
  };
  const badge = (label, tone = 'muted') => create('span', `ui-badge ui-badge--${tone}`, label);
  const emptyState = (message = '暂无数据', detail = '') => {
    const node = create('div', 'ui-empty-state');
    node.append(create('strong', '', message));
    if (detail) node.append(create('span', '', detail));
    return node;
  };
  // Block variant for panels and setState: a standalone .ui-empty-state node.
  const dataState = (state = 'loading', details = {}) => {
    const key = stateKey(state);
    const node = emptyState(dataStateTitles[key], stateDetail(key, details));
    node.dataset.state = key;
    if (details?.retry) node.append(retryButton(details.retry));
    return node;
  };
  const metricCard = ({ label, value = '--', meta = '', tone = 'default', icon: iconName, interactive = false, target } = {}) => {
    const node = create(interactive ? 'button' : 'article', `ui-metric-card ui-metric-card--${tone}`);
    if (interactive) { node.type = 'button'; if (target) node.dataset.uiMetricTarget = target; }
    const top = create('div', 'ui-metric-card__top');
    top.append(create('span', 'ui-metric-card__label', label));
    if (iconName) { const iconWrap = create('span', 'ui-metric-card__icon'); iconWrap.append(icon(iconName)); top.append(iconWrap); }
    const valueNode = create('strong', 'ui-metric-card__value', value);
    const metaNode = create('span', 'ui-metric-card__meta', meta);
    node.append(top, valueNode, metaNode);
    renderIcon(node);
    return node;
  };
  const panel = ({ title, hint = '', tools = null, className = '', tag = 'section' } = {}) => {
    const node = create(tag, ['ui-panel', className].filter(Boolean).join(' '));
    const header = create('header', 'ui-panel__header');
    const copy = create('div', 'ui-panel__copy');
    copy.append(create('h3', 'ui-panel__title', title));
    if (hint) copy.append(create('p', 'ui-panel__hint', hint));
    header.append(copy);
    if (tools) header.append(tools);
    node.append(header, create('div', 'ui-panel__body'));
    return node;
  };
  const pageHeader = ({ title, description = '', scope = '', actions = null } = {}) => {
    const node = create('header', 'ui-page-header');
    const copy = create('div', 'ui-page-header__copy');
    // The page title is the document's single h1; section headings below it use
    // h2/h3. `components.css` styles `.ui-page-header :is(h1, h2)`.
    copy.append(create('h1', '', title));
    if (description) copy.append(create('p', '', description));
    // Which shop / period / dataset this page is showing — the one thing the
    // description cannot say and the old `.ui-context-bar` used to carry.
    if (scope) copy.append(create('p', 'ui-page-header__scope', scope));
    node.append(copy);
    if (actions) node.append(actions);
    return node;
  };
  const metricGrid = (cards = [], className = '') => {
    const node = create('section', ['ui-metric-grid', className].filter(Boolean).join(' '));
    cards.forEach((config) => node.append(isElement(config) ? config : metricCard(config)));
    return node;
  };
  const filterToolbar = (content, actions = null) => {
    const node = create('div', 'ui-filter-toolbar');
    if (content) node.append(isElement(content) ? content : create('div', 'ui-filter-toolbar__main', content));
    if (actions) node.append(actions);
    return node;
  };
  const table = ({ caption = '', columns = [], rows = [], className = '' } = {}) => {
    const wrap = create('div', ['ui-table-wrap', className].filter(Boolean).join(' '));
    const node = create('table', 'ui-data-table');
    if (caption) node.append(create('caption', 'sr-only', caption));
    const head = create('thead');
    const headRow = create('tr');
    columns.forEach((column) => headRow.append(create('th', column.numeric ? 'num' : '', column.label || column.key)));
    head.append(headRow);
    const body = create('tbody');
    rows.forEach((row) => {
      const tr = create('tr');
      columns.forEach((column) => tr.append(create('td', column.numeric ? 'num' : '', row[column.key])));
      body.append(tr);
    });
    node.append(head, body);
    wrap.append(node);
    return wrap;
  };
  const setState = (root, state, details = {}) => {
    if (!root) return;
    root.dataset.state = stateKey(state);
    root.replaceChildren(dataState(state, details));
  };
  const fieldSelector = (options = {}) => {
    if (!window.DemoFieldSelector?.create) throw new Error('字段选择器组件尚未加载');
    return window.DemoFieldSelector.create(options);
  };
  const appendContent = (parent, content, className = '') => {
    if (!content) return parent;
    if (isElement(content)) parent.append(content);
    else if (Array.isArray(content)) content.forEach((item) => appendContent(parent, item));
    else parent.append(create('div', className, String(content)));
    return parent;
  };
  // Compact page context: keep the current range/source visible without competing with the page title.
  const contextBar = ({ label = '当前范围', value = '', meta = '', actions = null, className = '' } = {}) => {
    const node = create('section', ['ui-context-bar', className].filter(Boolean).join(' '));
    const copy = create('div', 'ui-context-bar__copy');
    copy.append(create('span', 'ui-context-bar__label', label));
    if (value) copy.append(create('strong', 'ui-context-bar__value', value));
    if (meta) copy.append(create('span', 'ui-context-bar__meta', meta));
    node.append(copy);
    if (actions) { const actionWrap = create('div', 'ui-context-bar__actions'); appendContent(actionWrap, actions); node.append(actionWrap); }
    return node;
  };
  // Shared table/list toolbar: filters remain on the left, result context and actions on the right.
  const tableToolbar = ({ filters = null, summary = '', actions = null, className = '' } = {}) => {
    const node = create('div', ['ui-table-toolbar', className].filter(Boolean).join(' '));
    const main = create('div', 'ui-table-toolbar__main');
    appendContent(main, filters);
    node.append(main);
    const side = create('div', 'ui-table-toolbar__side');
    if (summary) side.append(create('span', 'ui-table-toolbar__summary', summary));
    appendContent(side, actions);
    if (side.childNodes.length) node.append(side);
    return node;
  };
  // 4-9：原 ui-decision-card 工厂在此删除。它自建出来就没有任何调用点（全仓库 grep
  // decisionCard / ui-decision-card 只有定义处与 export 列表），唯一“使用”是 promotion.html
  // 的 <article class="ui-decision-card promotion-decision-card">，而 promotion-views.css
  // 立刻用 `.promotion-decision-card.ui-decision-card { padding:0; border:0; background:transparent }`
  // 把组件样式全部覆盖掉 —— 等于挂了个类名却不用组件。按仓库自定标准
  // 「新组件必须 ≥2 页复用才能进 ui-components.js」，直接删掉。
  // A reusable side panel for evidence/details. It does not alter routing or page state.
  const detailDrawer = ({ title, description = '', body = null, footer = null, size = 'md', onClose = null } = {}) => {
    const node = create('aside', ['ui-drawer', `ui-drawer--${size}`, 'is-hidden'].join(' '));
    node.hidden = true;
    node.setAttribute('role', 'dialog');
    node.setAttribute('aria-modal', 'true');
    const titleId = `ui-drawer-title-${++modalSequence}`;
    node.setAttribute('aria-labelledby', titleId);
    const backdrop = create('button', 'ui-drawer__backdrop');
    backdrop.type = 'button';
    backdrop.tabIndex = -1;
    backdrop.setAttribute('aria-label', '关闭详情');
    const sheet = create('section', 'ui-drawer__sheet');
    const header = create('header', 'ui-drawer__header');
    const copy = create('div', 'ui-drawer__copy');
    const heading = create('h2', '', title || '详情');
    heading.id = titleId;
    copy.append(heading);
    if (description) copy.append(create('p', '', description));
    const closeButton = button({ icon: 'x', variant: 'ghost', className: 'ui-drawer__close', ariaLabel: '关闭详情' });
    header.append(copy, closeButton);
    const bodyNode = create('div', 'ui-drawer__body');
    appendContent(bodyNode, body);
    sheet.append(header, bodyNode);
    const handle = { node, body: bodyNode, footer: null, open: () => handle, close: () => handle, destroy: () => handle };
    if (footer) {
      const footerNode = create('footer', 'ui-drawer__footer');
      appendContent(footerNode, footer);
      sheet.append(footerNode);
      handle.footer = footerNode;
    }
    node.append(backdrop, sheet);
    document.body.append(node);
    let counted = false;
    let returnFocusNode = null;
    // Late-attach footer: creators that build their footer content after the drawer
    // (e.g. from a <template>) can call handle.ensureFooter() instead of pre-building it.
    handle.ensureFooter = () => {
      if (handle.footer) return handle.footer;
      const footerNode = create('footer', 'ui-drawer__footer');
      sheet.append(footerNode);
      handle.footer = footerNode;
      return footerNode;
    };
    const focusables = () => [...node.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')].filter((item) => item.getClientRects().length);
    const close = () => {
      if (node.hidden) return handle;
      node.hidden = true;
      node.classList.remove('is-open');
      if (counted) {
        counted = false;
        drawerOpenCount = Math.max(0, drawerOpenCount - 1);
        if (!drawerOpenCount) document.body.classList.remove('has-ui-drawer');
      }
      const restore = returnFocusNode;
      returnFocusNode = null;
      if (restore?.isConnected) restore.focus({ preventScroll: true });
      if (onClose) onClose();
      return handle;
    };
    handle.open = (trigger = null) => {
      if (!node.hidden) return handle;
      node.hidden = false;
      node.classList.remove('is-hidden');
      node.classList.add('is-open');
      if (!counted) {
        counted = true;
        if (!drawerOpenCount) document.body.classList.add('has-ui-drawer');
        drawerOpenCount += 1;
      }
      const active = document.activeElement;
      returnFocusNode = trigger || (active && active !== document.body && !node.contains(active) ? active : null);
      closeButton.focus({ preventScroll: true });
      return handle;
    };
    handle.close = close;
    handle.destroy = () => { close(); node.remove(); return handle; };
    closeButton.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    node.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { event.preventDefault(); close(); return; }
      if (event.key !== 'Tab') return;
      const items = focusables();
      if (!items.length) { event.preventDefault(); closeButton.focus(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !node.contains(active))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (active === last || !node.contains(active))) { event.preventDefault(); first.focus(); }
    });
    return handle;
  };
  const stickyActionBar = ({ content = null, actions = null, className = '' } = {}) => {
    const node = create('div', ['ui-sticky-action-bar', className].filter(Boolean).join(' '));
    if (content) { const contentWrap = create('div', 'ui-sticky-action-bar__content'); appendContent(contentWrap, content); node.append(contentWrap); }
    if (actions) { const actionWrap = create('div', 'ui-sticky-action-bar__actions'); appendContent(actionWrap, actions); node.append(actionWrap); }
    return node;
  };
  let modalSequence = 0;
  let drawerOpenCount = 0;
  let openModalCount = 0;
  let bodyOverflowBeforeModal = '';
  // Native <dialog> per DESIGN_SYSTEM.md §4.5: showModal() puts the dialog in the top layer,
  // so stacking across open modals is handled by the browser. ESC and backdrop clicks are
  // routed through close() so onClose fires exactly once per dismissal.
  const modal = ({ title, description = '', body = null, footer = null, size = 'md', dismissible = true, onClose = null } = {}) => {
    const node = create('dialog', ['ui-modal', size && size !== 'md' ? `ui-modal--${size}` : ''].filter(Boolean).join(' '));
    const titleId = `ui-modal-title-${++modalSequence}`;
    node.setAttribute('aria-labelledby', titleId);
    if (!dismissible) node.dataset.uiModalStatic = '';
    // showModal() requires the dialog to be in the document; keep it attached for its whole lifetime.
    document.body.append(node);
    const handle = { node, body: null, footer: null, open: () => handle, close: () => handle, destroy: () => handle };
    const header = create('header', 'ui-modal__header');
    const copy = create('div', 'ui-modal__copy');
    const heading = create('h3', '', title);
    heading.id = titleId;
    copy.append(heading);
    if (description) copy.append(create('p', '', description));
    header.append(copy);
    const closeButton = button({ icon: 'x', variant: 'ghost', className: 'ui-modal__close' });
    closeButton.setAttribute('aria-label', '关闭');
    closeButton.addEventListener('click', () => handle.close());
    header.append(closeButton);
    node.append(header);
    const bodyNode = create('div', 'ui-modal__body');
    if (isElement(body)) bodyNode.append(body);
    else if (body) bodyNode.append(create('p', '', String(body)));
    node.append(bodyNode);
    handle.body = bodyNode;
    if (footer) {
      const footerNode = create('footer', 'ui-modal__footer');
      (Array.isArray(footer) ? footer : [footer]).forEach((item) => footerNode.append(isElement(item) ? item : create('div', '', String(item))));
      node.append(footerNode);
      handle.footer = footerNode;
    }
    let counted = false;
    let finished = false;
    const acquire = () => {
      if (counted) return;
      counted = true;
      if (openModalCount === 0) { bodyOverflowBeforeModal = document.body.style.overflow; document.body.style.overflow = 'hidden'; }
      openModalCount += 1;
    };
    const release = () => {
      if (!counted) return;
      counted = false;
      openModalCount = Math.max(0, openModalCount - 1);
      if (openModalCount === 0) document.body.style.overflow = bodyOverflowBeforeModal;
    };
    // Some embedded Chromium builds never dispatch the dialog close event, so the
    // scroll-lock release and onClose must run synchronously in close()/destroy(),
    // with the close event only as a fallback for UA-initiated dismissal.
    const finish = () => {
      if (finished) return;
      finished = true;
      release();
      if (onClose) onClose();
    };
    handle.open = () => {
      if (node.open) return handle;
      finished = false;
      acquire();
      try {
        node.showModal();
      } catch (error) {
        release();
        throw error;
      }
      return handle;
    };
    handle.close = () => {
      if (node.open) {
        node.close();
        finish();
      }
      return handle;
    };
    handle.destroy = () => {
      if (node.open) {
        node.close();
        finish();
      }
      node.remove();
      return handle;
    };
    node.addEventListener('close', finish);
    node.addEventListener('cancel', (event) => { event.preventDefault(); if (dismissible) handle.close(); });
    node.addEventListener('keydown', (event) => { if (event.key === 'Escape' && dismissible && node.open) { event.preventDefault(); handle.close(); } });
    node.addEventListener('click', (event) => { if (dismissible && event.target === node) handle.close(); });
    return handle;
  };
  // 点击弹窗遮罩（backdrop）关闭：<dialog> 的遮罩点击事件 target 就是 dialog 本身。
  // 按下起点在内容里（拖拽选字后松在遮罩上）则不关，避免误关丢输入。
  // 先派发 cancel 事件，让弹窗既有的取消逻辑（回滚草稿、恢复焦点）接管；
  // 无人处理时再兜底 close()。dismissible:false 的弹窗会在 cancel 里
  // preventDefault，因此不会被关掉。
  const lightDismiss = (dialog) => {
    if (!dialog || !dialog.open) return false;
    const notPrevented = dialog.dispatchEvent(new Event('cancel', { cancelable: true }));
    if (notPrevented && dialog.open) dialog.close();
    return true;
  };
  const enableLightDismiss = (dialog) => {
    if (!dialog || dialog.dataset.lightDismiss === 'bound') return dialog;
    dialog.dataset.lightDismiss = 'bound';
    let pressedInside = false;
    dialog.addEventListener('pointerdown', (event) => { pressedInside = event.target !== dialog; });
    dialog.addEventListener('click', (event) => {
      if (event.target !== dialog || pressedInside) return;
      lightDismiss(dialog);
    });
    return dialog;
  };
  // 兜底：文档级事件委托，覆盖未显式绑定 enableLightDismiss 的 <dialog>，
  // 含运行时动态创建的弹窗（预警规则、动作详情等）。显式绑定过的带标记，这里跳过。
  // 本文件会被页面 HTML 与 shell.js 各加载一次，用标记保证只绑一次。
  if (!document.documentElement.hasAttribute('data-light-dismiss-ready')) {
    document.documentElement.setAttribute('data-light-dismiss-ready', '');
    let pressTarget = null;
    document.addEventListener('pointerdown', (event) => { pressTarget = event.target; }, true);
    document.addEventListener('click', (event) => {
      const dialog = event.target;
      if (!(dialog instanceof HTMLDialogElement) || !dialog.open) return;
      if (dialog.dataset.lightDismiss === 'bound') return;
      if (pressTarget !== dialog) return;
      lightDismiss(dialog);
    });
  }
  const confirm = ({ title, message = '', description = '', confirmLabel = '确认', cancelLabel = '取消', tone = 'primary' } = {}) => new Promise((resolve) => {
    const cancel = button({ label: cancelLabel });
    const ok = button({ label: confirmLabel, variant: tone === 'danger' ? 'danger' : 'primary' });
    const dialog = modal({ title, description, body: create('p', '', message), size: 'sm', dismissible: false, footer: [cancel, ok], onClose: () => resolve(false) });
    cancel.addEventListener('click', () => dialog.close());
    ok.addEventListener('click', () => { resolve(true); dialog.close(); });
    dialog.open();
  });
  const audit = (root = document) => {
    const issues = [];
    const legacyNames = new Set([
      'button', 'button--primary', 'button--ghost', 'button--danger', 'button--icon', 'button--sm',
      'badge', 'badge--brand', 'badge--success', 'badge--warning', 'badge--danger', 'badge--info', 'badge--purple', 'badge--muted',
      'panel', 'plain-panel', 'metric-card', 'metric-card--drillable', 'data-table-wrap', 'data-table-wrap--discoverable',
      'data-table', 'empty-state', 'section-toolbar', 'demo-page__intro', 'metric-grid',
    ]);
    const candidates = root.nodeType === 1 ? [root, ...root.querySelectorAll('[class]')] : [...root.querySelectorAll('[class]')];
    candidates.forEach((node) => {
      [...node.classList].filter((name) => legacyNames.has(name)).forEach((name) => {
        issues.push({ node, message: `发现 legacy class：${name}` });
      });
    });
    root.querySelectorAll('.ui-data-table').forEach((tableNode) => {
      if (!tableNode.closest('.ui-table-wrap') && tableNode.dataset.tableControls !== 'true') {
        issues.push({ node: tableNode, message: '数据表缺少 ui-table-wrap 容器' });
      }
    });
    root.querySelectorAll('.ui-empty-state[data-state]').forEach((node) => {
      if (!node.querySelector('strong')) issues.push({ node, message: '带状态的空态缺少标题节点' });
    });
    // A page has exactly one h1 — its title. Without this rule the heading level
    // drifts back as soon as someone copies a page skeleton.
    const ownerDocument = root.nodeType === 9 ? root : root.ownerDocument;
    if (ownerDocument) {
      const headings = ownerDocument.querySelectorAll('h1');
      if (headings.length !== 1) {
        issues.push({ node: ownerDocument.body, message: `页面应有且仅有一个 h1，当前 ${headings.length} 个` });
      }
    }
    return issues;
  };
  const api = { text, create, clear, escape, formatDateTime, format, status, renderDataState, icon, button, badge, emptyState, dataState, metricCard, metricGrid, panel, pageHeader, filterToolbar, table, setState, contextBar, tableToolbar, detailDrawer, stickyActionBar, modal, confirm, enableLightDismiss, fieldSelector, audit };
  window.TmallUI = Object.freeze(api);
})();
