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
  const status = (node, state, details = {}) => {
    if (!node || !window.DemoApi?.renderDataState) return;
    window.DemoApi.renderDataState(node, state, details);
  };
  const icon = (name, label) => {
    const node = create('i');
    node.dataset.lucide = name;
    if (label) node.setAttribute('aria-label', label);
    else node.setAttribute('aria-hidden', 'true');
    return node;
  };
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const formatNumber = (value, digits = 0) => {
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '--';
  };
  const formatMoney = (value, digits = 0) => formatNumber(value, digits);
  const formatPercent = (value, digits = 1) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return `${(Math.abs(number) <= 1 ? number * 100 : number).toFixed(digits)}%`;
  };
  const format = Object.freeze({ number: formatNumber, money: formatMoney, percent: formatPercent, dateTime: formatDateTime });
  const isElement = (value) => Boolean(value && value.nodeType === 1);

  const renderIcon = (node) => {
    if (node && window.lucide?.createIcons) {
      try {
        window.lucide.createIcons({ nodes: [node] });
      } catch (error) {
        window.lucide.createIcons();
      }
    }
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
  const dataState = (state = 'loading', details = {}) => {
    const labels = {
      loading: ['加载中…', '正在读取数据'],
      'no-data': ['暂无数据', '当前筛选条件没有可展示的数据'],
      'insufficient-data': ['数据不足', '补充更多数据后才能计算'],
      'missing-fields': ['字段缺失', details.fields ? `缺少：${details.fields.join('、')}` : '请检查导入字段'],
      'calculation-failed': ['计算失败', details.message || '请稍后重试'],
      'source-unavailable': ['数据源不可用', details.message || '请检查数据源连接'],
      partial: ['部分数据可用', details.message || '部分字段暂不可用'],
    };
    const [message, detail] = labels[state] || labels['no-data'];
    const node = emptyState(message, detail);
    node.dataset.state = state;
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
  const legacyMap = Object.freeze({
    button: 'ui-button',
    'metric-card': 'ui-metric-card',
    badge: 'ui-badge',
    panel: 'ui-panel',
    'plain-panel': 'ui-panel',
    'empty-state': 'ui-empty-state',
    'demo-page__intro': 'ui-page-header',
    'section-toolbar': 'ui-filter-toolbar',
    'data-table-wrap': 'ui-table-wrap',
    'data-table': 'ui-data-table',
  });
  const upgradeLegacy = (root = document) => {
    Object.entries(legacyMap).forEach(([legacy, canonical]) => {
      if (root.nodeType === 1 && root.classList.contains(legacy)) root.classList.add(canonical);
      root.querySelectorAll(`.${legacy}`).forEach((node) => node.classList.add(canonical));
    });
    const candidates = root.nodeType === 1 ? [root, ...root.querySelectorAll('*')] : [...root.querySelectorAll('*')];
    candidates.filter((node) => node.matches?.('.badge--success, .badge--warning, .badge--danger, .badge--info, .badge--brand, .badge--purple, .badge--muted')).forEach((node) => {
      const tone = [...node.classList].find((name) => name.startsWith('badge--'))?.replace('badge--', '');
      if (tone) node.classList.add(`ui-badge--${tone}`);
    });
    candidates.filter((node) => node.matches?.('.button--primary, .button--danger, .button--ghost')).forEach((node) => {
      const variant = [...node.classList].find((name) => name.startsWith('button--'))?.replace('button--', '');
      if (variant) node.classList.add(`ui-button--${variant}`);
    });
    return root;
  };
  const api = { text, create, clear, escape, formatDateTime, format, status, icon, button, badge, emptyState, dataState, metricCard, metricGrid, panel, pageHeader, filterToolbar, table, setState, fieldSelector, upgradeLegacy };
  const audit = (root = document) => {
    const issues = [];
    root.querySelectorAll('.metric-card, .panel, .plain-panel, .button, .badge, .empty-state, .section-toolbar, .data-table-wrap, .data-table').forEach((node) => {
      const canonical = [...node.classList].some((name) => name.startsWith('ui-'));
      if (!canonical) issues.push({ node, message: '公共组件缺少 ui-* canonical class' });
    });
    return issues;
  };
  api.audit = audit;
  window.TmallUI = Object.freeze(api);
  const startLegacyUpgrade = () => {
    upgradeLegacy();
    if (window.MutationObserver && document.body) {
      const observer = new MutationObserver((records) => {
        records.forEach((record) => record.addedNodes.forEach((node) => {
          if (isElement(node)) upgradeLegacy(node);
        }));
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', startLegacyUpgrade, { once: true });
  else startLegacyUpgrade();
})();
