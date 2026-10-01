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
  const button = ({ label, icon: iconName, variant = 'secondary', size, type = 'button', disabled = false, className = '' } = {}) => {
    const node = create('button', ['ui-button', `ui-button--${variant}`, size ? `ui-button--${size}` : '', className].filter(Boolean).join(' '), label);
    node.type = type;
    node.disabled = disabled;
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
  const pageHeader = ({ title, description = '', actions = null } = {}) => {
    const node = create('header', 'ui-page-header');
    const copy = create('div', 'ui-page-header__copy');
    copy.append(create('h2', '', title));
    if (description) copy.append(create('p', '', description));
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
    root.dataset.state = state;
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
  const decisionCard = ({ eyebrow = '', title = '', detail = '', tone = 'default', action = null, className = '' } = {}) => {
    const node = create('article', ['ui-decision-card', `ui-decision-card--${tone}`, className].filter(Boolean).join(' '));
    const copy = create('div', 'ui-decision-card__copy');
    if (eyebrow) copy.append(create('span', 'ui-decision-card__eyebrow', eyebrow));
    if (title) copy.append(create('strong', 'ui-decision-card__title', title));
    if (detail) copy.append(create('span', 'ui-decision-card__detail', detail));
    node.append(copy);
    if (action) { const actionWrap = create('div', 'ui-decision-card__action'); appendContent(actionWrap, action); node.append(actionWrap); }
    return node;
  };
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
    backdrop.setAttribute('aria-label', '关闭详情');
    const sheet = create('section', 'ui-drawer__sheet');
    const header = create('header', 'ui-drawer__header');
    const copy = create('div', 'ui-drawer__copy');
    const heading = create('h2', '', title || '详情');
    heading.id = titleId;
    copy.append(heading);
    if (description) copy.append(create('p', '', description));
    const closeButton = button({ icon: 'x', variant: 'ghost', className: 'ui-drawer__close' });
    closeButton.setAttribute('aria-label', '关闭详情');
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
    const close = () => {
      if (node.hidden) return handle;
      node.hidden = true;
      node.classList.remove('is-open');
      document.body.classList.remove('has-ui-drawer');
      if (onClose) onClose();
      return handle;
    };
    handle.open = () => {
      node.hidden = false;
      node.classList.remove('is-hidden');
      node.classList.add('is-open');
      document.body.classList.add('has-ui-drawer');
      closeButton.focus({ preventScroll: true });
      return handle;
    };
    handle.close = close;
    handle.destroy = () => { close(); node.remove(); return handle; };
    closeButton.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    node.addEventListener('keydown', (event) => { if (event.key === 'Escape') { event.preventDefault(); close(); } });
    return handle;
  };
  const stickyActionBar = ({ content = null, actions = null, className = '' } = {}) => {
    const node = create('div', ['ui-sticky-action-bar', className].filter(Boolean).join(' '));
    if (content) { const contentWrap = create('div', 'ui-sticky-action-bar__content'); appendContent(contentWrap, content); node.append(contentWrap); }
    if (actions) { const actionWrap = create('div', 'ui-sticky-action-bar__actions'); appendContent(actionWrap, actions); node.append(actionWrap); }
    return node;
  };
  let modalSequence = 0;
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
    return issues;
  };
  const api = { text, create, clear, escape, formatDateTime, format, status, renderDataState, icon, button, badge, emptyState, dataState, metricCard, metricGrid, panel, pageHeader, filterToolbar, table, setState, contextBar, tableToolbar, decisionCard, detailDrawer, stickyActionBar, modal, confirm, fieldSelector, audit };
  window.TmallUI = Object.freeze(api);
})();
