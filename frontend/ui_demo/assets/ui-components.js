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
  /**
   * @param {{ label?: string, icon?: string, variant?: string, size?: string, type?: string, disabled?: boolean, className?: string, ariaLabel?: string }} [options]
   * @returns {HTMLButtonElement}
   */
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
  /**
   * @param {{ label?: string, value?: any, meta?: string, tone?: string, icon?: string, interactive?: boolean, target?: any }} [options]
   * @returns {HTMLElement}
   */
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
  /**
   * @param {{ title?: string, hint?: string, tools?: any, className?: string, tag?: string }} [options]
   * @returns {HTMLElement}
   */
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
  /**
   * @param {{ title?: string, description?: string, scope?: string, actions?: any }} [options]
   * @returns {HTMLElement}
   */
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
  const appendTableValue = (cell, value) => {
    if (value == null) return cell;
    if (value.nodeType) cell.append(value);
    else if (Array.isArray(value)) value.forEach((item) => appendTableValue(cell, item));
    else cell.textContent = String(value);
    return cell;
  };
  /**
   * @param {{ caption?: string, columns?: Array<{ key?: string, label?: string, numeric?: boolean, rowHeader?: boolean, scope?: string, className?: string, headerClassName?: string, render?: Function, renderHeader?: Function }>, rows?: any[], footerRows?: any[], className?: string, tableClass?: string, wrapClass?: string, emptyMessage?: string, rowClassName?: string | Function, renderRow?: Function, tableControls?: boolean }} [options]
   */
  const table = ({ caption = '', columns = [], rows = [], footerRows = [], className = '', tableClass = '', wrapClass = '', emptyMessage = '', rowClassName = '', renderRow = null, tableControls = false } = {}) => {
    const wrap = create('div', ['ui-table-wrap', className, wrapClass].filter(Boolean).join(' '));
    const node = create('table', ['ui-data-table', tableClass].filter(Boolean).join(' '));
    if (tableControls) node.dataset.tableControls = 'true';
    if (caption) node.append(create('caption', 'sr-only', caption));
    const head = create('thead');
    const headRow = create('tr');
    columns.forEach((column, index) => {
      const cell = create('th', [column.numeric ? 'num' : '', column.headerClassName || ''].filter(Boolean).join(' '));
      appendTableValue(cell, column.renderHeader ? column.renderHeader(column, index) : (column.label || column.key));
      if (column.scope) cell.scope = column.scope;
      headRow.append(cell);
    });
    head.append(headRow);
    const makeRows = (items, section, isFooter = false) => {
      items.forEach((row, rowIndex) => {
        if (!isFooter && typeof renderRow === 'function') {
          const customRow = renderRow(row, rowIndex);
          if (customRow?.nodeType === 1 && customRow.tagName === 'TR') {
            if (typeof rowClassName === 'function') customRow.classList.add(...String(rowClassName(row, rowIndex, isFooter) || '').split(/\s+/).filter(Boolean));
            else if (rowClassName) customRow.classList.add(...String(rowClassName).split(/\s+/).filter(Boolean));
            section.append(customRow);
            return;
          }
        }
        const tr = create('tr', typeof rowClassName === 'function' ? rowClassName(row, rowIndex, isFooter) : rowClassName);
        columns.forEach((column, columnIndex) => {
          const tag = column.rowHeader && !isFooter ? 'th' : 'td';
          const cell = create(tag, [column.numeric ? 'num' : '', column.className || ''].filter(Boolean).join(' '));
          if (tag === 'th') cell.scope = 'row';
          appendTableValue(cell, column.render ? column.render(row?.[column.key], row, rowIndex, columnIndex, isFooter) : row?.[column.key]);
          tr.append(cell);
        });
        section.append(tr);
      });
    };
    const body = create('tbody');
    if (rows.length) makeRows(rows, body);
    else if (emptyMessage) {
      const tr = create('tr');
      const cell = create('td', 'ui-table-empty', emptyMessage);
      cell.colSpan = Math.max(columns.length, 1);
      tr.append(cell);
      body.append(tr);
    }
    node.append(head, body);
    if (footerRows.length) {
      const foot = create('tfoot');
      makeRows(footerRows, foot, true);
      node.append(foot);
    }
    wrap.append(node);
    return wrap;
  };
  /**
   * Render a shared table into an existing table or tbody while preserving the
   * host table's class modifiers and data attributes.
   * @param {HTMLTableElement | HTMLTableSectionElement | string} target
   * @param {Parameters<typeof table>[0]} [options]
   * @returns {HTMLTableElement|null}
   */
  table.mount = (target, options = {}) => {
    const targetNode = typeof target === 'string' ? document.querySelector(target) : target;
    const currentTable = targetNode?.tagName === 'TABLE' ? targetNode : targetNode?.closest?.('table');
    if (!currentTable) return null;
    const copyAttributes = (source, destination, mergeClass = false) => {
      [...source.attributes].forEach((attribute) => {
        if (mergeClass && attribute.name === 'class') {
          const classes = new Set(`${destination.getAttribute('class') || ''} ${attribute.value}`.split(/\s+/).filter(Boolean));
          destination.setAttribute('class', [...classes].join(' '));
        } else {
          destination.setAttribute(attribute.name, attribute.value);
        }
      });
    };
    const classNames = [...currentTable.classList].filter((name) => name !== 'ui-data-table');
    const generated = table({ ...options, tableClass: [classNames.join(' '), options.tableClass || ''].filter(Boolean).join(' ') });
    const nextTable = generated.querySelector('table');
    const currentBody = targetNode?.tagName === 'TBODY' ? targetNode : currentTable.querySelector('tbody');
    const currentHead = currentTable.querySelector('thead');
    const nextBody = nextTable?.querySelector('tbody');
    const nextHead = nextTable?.querySelector('thead');
    if (!nextTable || !nextBody) return null;
    [...currentTable.attributes].forEach((attribute) => {
      if (attribute.name !== 'class') nextTable.setAttribute(attribute.name, attribute.value);
    });
    if (currentHead && nextHead) {
      copyAttributes(currentHead, nextHead);
      const currentHeadRow = currentHead.querySelector('tr');
      const nextHeadRow = nextHead.querySelector('tr');
      if (currentHeadRow && nextHeadRow) {
        copyAttributes(currentHeadRow, nextHeadRow, true);
        const currentCells = [...currentHeadRow.children];
        [...nextHeadRow.children].forEach((cell, index) => {
          const currentCell = currentCells[index];
          if (currentCell) copyAttributes(currentCell, cell, true);
        });
      }
    }
    if (currentBody) [...currentBody.attributes].forEach((attribute) => nextBody.setAttribute(attribute.name, attribute.value));
    currentTable.replaceWith(nextTable);
    return nextTable;
  };
  const productIdentity = ({
    title = '', id = '', imageUrl = '', showThumbnail = true, showId = true, maxTitleChars = 8,
    className = '', titleClassName = '', onTitleClick = null, metaItems = [], metaText = '',
  } = {}) => {
    const fullTitle = String(title || id || '未命名商品');
    const productId = String(id || '--');
    const visibleTitle = Array.from(fullTitle).slice(0, Math.max(0, Number(maxTitleChars) || 0)).join('');
    const root = create('div', ['product-identity', 'ui-product-identity', showThumbnail ? '' : 'ui-product-identity--no-image', className].filter(Boolean).join(' '));
    if (showThumbnail) {
      const thumbnail = create(imageUrl ? 'img' : 'span', imageUrl ? 'product-thumb ui-product-identity__image' : 'product-thumb product-thumb--placeholder ui-product-identity__image');
      if (imageUrl) {
        thumbnail.src = String(imageUrl);
        thumbnail.alt = '';
        thumbnail.loading = 'lazy';
        thumbnail.referrerPolicy = 'no-referrer';
        thumbnail.addEventListener('error', () => {
          const placeholder = create('span', 'product-thumb product-thumb--placeholder ui-product-identity__image');
          placeholder.setAttribute('aria-hidden', 'true');
          placeholder.textContent = Array.from(fullTitle.trim())[0] || '商';
          thumbnail.replaceWith(placeholder);
        }, { once: true });
      } else {
        thumbnail.setAttribute('aria-hidden', 'true');
        thumbnail.textContent = Array.from(fullTitle.trim())[0] || '商';
      }
      root.append(thumbnail);
    }
    const copy = create('div', 'product-title ui-product-identity__copy');
    const titleNode = create(onTitleClick ? 'button' : 'strong', titleClassName || (onTitleClick ? 'product-title__link' : 'ui-product-identity__title'));
    if (onTitleClick) {
      titleNode.type = 'button';
      titleNode.addEventListener('click', onTitleClick);
      titleNode.setAttribute('aria-label', `查看商品详情：${fullTitle}`);
    }
    titleNode.textContent = visibleTitle;
    titleNode.title = fullTitle;
    copy.append(titleNode);
    const meta = create('div', 'product-title__meta ui-product-identity__meta');
    (Array.isArray(metaItems) ? metaItems : [metaItems]).filter(isElement).forEach((item) => meta.append(item));
    if (showId && productId !== '--') meta.append(create('span', 'product-title__id ui-product-identity__id', productId));
    if (metaText) meta.append(create('span', 'ui-product-identity__extra', metaText));
    if (meta.childNodes.length) copy.append(meta);
    root.append(copy);
    return root;
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
  /**
   * @param {{ title?: string, description?: string, body?: any, footer?: any, size?: string, onClose?: (() => void) | null }} [options]
   */
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
    const focusables = () => [...node.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')].filter((item) => item.getClientRects().length && item.tabIndex >= 0);
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
  // ============ 浮层原语（popover） ============
  // 为什么需要它：本仓库此前没有任何浮层原语，每个下拉/选择器都自己写定位与关闭逻辑。
  // 真实事故：时间选择器浮层因一个 CSS 解析错误丢掉 position:fixed，被渲染到文档流底部
  // （top 2211px，视口 800px），表现为「点了没反应」，console 无报错。
  // 把定位、视口约束、点外关闭、Esc、焦点返回、滚动跟随统一收在这里，
  // 页面不再各自实现，同类失效就不再可能。
  let openPopover = null;
  const POPOVER_VIEWPORT_GAP = 8;
  const popoverPlacement = (anchorRect, panelRect, placement) => {
    const gap = POPOVER_VIEWPORT_GAP;
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    const preferBelow = placement !== 'top';
    const spaceBelow = vh - anchorRect.bottom;
    const spaceAbove = anchorRect.top;
    // 空间不足时自动翻转到另一侧，而不是硬贴边导致被裁切。
    const below = preferBelow
      ? (spaceBelow >= panelRect.height + gap || spaceBelow >= spaceAbove)
      : !(spaceAbove >= panelRect.height + gap || spaceAbove >= spaceBelow);
    let top = below ? anchorRect.bottom + gap : anchorRect.top - panelRect.height - gap;
    let left = anchorRect.left;
    // 视口约束：左右夹紧、上下夹紧，保证浮层永远完整可见。
    left = Math.min(Math.max(gap, left), Math.max(gap, vw - panelRect.width - gap));
    top = Math.min(Math.max(gap, top), Math.max(gap, vh - panelRect.height - gap));
    return { top, left, below };
  };
  const popover = ({
    anchor = null, content = null, placement = 'bottom', className = '',
    matchAnchorWidth = false, closeOnOutside = true, onClose = null,
  } = {}) => {
    const node = create('div', ['ui-popover', className].filter(Boolean).join(' '));
    node.setAttribute('role', 'dialog');
    const panel = create('div', 'ui-popover__panel');
    appendContent(panel, content);
    node.append(panel);
    // 首帧不能走过渡：元素先以 CSS 默认的 top:0/left:0 挂载，紧接着 reposition() 才写入
    // 真实坐标；而 shell.css 的 `@media (prefers-reduced-motion: reduce)` 规则
    // （`*, *::before, *::after { transition-duration: .01ms !important }`）给每个元素都留了
    // 一次 0.01ms 过渡，transition-property 默认又是 all，于是这次坐标变化被当成一次过渡，
    // 首帧按过渡起点（0,0）绘制 —— 用户看到的就是「残留弹窗在左上角闪过」。
    // 这里在挂载前用 inline !important 把过渡时长压成 0s（`*` 规则也是 !important，
    // 只有 inline !important 能赢），等两次 rAF 定位稳定后再撤掉。
    node.style.setProperty('transition-duration', '0s', 'important');
    // 浮层必须挂到 body 并使用 fixed 定位：挂到局部容器会被祖先的
    // overflow/transform/层叠上下文裁切，这正是此前弹窗「看不见」的根因。
    document.body.append(node);

    let returnFocusNode = null;
    let closed = false;
    const anchorNode = isElement(anchor) ? anchor : null;
    const reposition = () => {
      if (closed || !anchorNode) return;
      const anchorRect = anchorNode.getBoundingClientRect();
      if (matchAnchorWidth) node.style.minWidth = `${Math.round(anchorRect.width)}px`;
      const panelRect = node.getBoundingClientRect();
      const spot = popoverPlacement(anchorRect, panelRect, placement);
      node.style.top = `${Math.round(spot.top)}px`;
      node.style.left = `${Math.round(spot.left)}px`;
      node.dataset.placement = spot.below ? 'bottom' : 'top';
    };
    const close = (options = {}) => {
      if (closed) return handle;
      closed = true;
      if (openPopover === handle) openPopover = null;
      document.removeEventListener('pointerdown', onDocumentPointerDown, true);
      document.removeEventListener('keydown', onDocumentKeyDown, true);
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
      node.remove();
      if (anchorNode && anchorNode.getAttribute('aria-expanded') === 'true') anchorNode.setAttribute('aria-expanded', 'false');
      if (options.restoreFocus !== false && returnFocusNode && document.contains(returnFocusNode)) {
        returnFocusNode.focus({ preventScroll: true });
      }
      if (onClose) onClose();
      return handle;
    };
    function onDocumentPointerDown(event) {
      if (!closeOnOutside) return;
      if (node.contains(event.target) || (anchorNode && anchorNode.contains(event.target))) return;
      close();
    }
    function onDocumentKeyDown(event) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      close();
    }
    const handle = {
      node,
      panel,
      reposition,
      close,
      destroy: () => close({ restoreFocus: false }),
      isOpen: () => !closed,
    };
    // 同一时刻只允许一个浮层，避免层叠错乱与焦点争抢。
    if (openPopover) openPopover.close({ restoreFocus: false });
    openPopover = handle;
    const active = document.activeElement;
    returnFocusNode = anchorNode || (active && active !== document.body ? active : null);
    if (anchorNode) anchorNode.setAttribute('aria-expanded', 'true');
    // 先渲染再测量，否则首次定位拿到的是 0 高度。
    // 第一次 rAF 再定位一次（面板高度/字体就绪后宽度可能变），第二次 rAF 才撤掉过渡压制，
    // 这样同步定位、rAF 定位两次坐标变化都不带动画，不会有「跳一下」的观感。
    requestAnimationFrame(() => {
      reposition();
      requestAnimationFrame(() => { node.style.removeProperty('transition-duration'); });
    });
    reposition();
    document.addEventListener('pointerdown', onDocumentPointerDown, true);
    document.addEventListener('keydown', onDocumentKeyDown, true);
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
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
  /**
   * @param {{ title?: string, description?: string, body?: any, footer?: any, size?: string, dismissible?: boolean, onClose?: (() => void) | null }} [options]
   */
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
  /**
   * @param {{ title?: string, message?: string, description?: string, confirmLabel?: string, cancelLabel?: string, tone?: string }} [options]
   * @returns {Promise<boolean>}
   */
  const confirm = ({ title, message = '', description = '', confirmLabel = '确认', cancelLabel = '取消', tone = 'primary' } = {}) => new Promise((resolve) => {
    const cancel = button({ label: cancelLabel });
    const ok = button({ label: confirmLabel, variant: tone === 'danger' ? 'danger' : 'primary' });
    const dialog = modal({ title, description, body: create('p', '', message), size: 'sm', dismissible: false, footer: [cancel, ok], onClose: () => resolve(false) });
    cancel.addEventListener('click', () => dialog.close());
    ok.addEventListener('click', () => { resolve(true); dialog.close(); });
    dialog.open();
  });
  /**
   * @param {Element | Document} [root]
   * @returns {{ node: any, message: string }[]}
   */
  const audit = (root = document) => {
    const issues = [];
    const legacyNames = new Set([
      'button', 'button--primary', 'button--ghost', 'button--danger', 'button--icon', 'button--sm',
      'badge', 'badge--brand', 'badge--success', 'badge--warning', 'badge--danger', 'badge--info', 'badge--purple', 'badge--muted',
      'panel', 'plain-panel', 'metric-card', 'metric-card--drillable', 'data-table-wrap', 'data-table-wrap--discoverable',
      'data-table', 'empty-state', 'section-toolbar', 'demo-page__intro', 'metric-grid',
    ]);
    const candidates = root.nodeType === 1
      ? [/** @type {Element} */ (root), ...root.querySelectorAll('[class]')]
      : [...root.querySelectorAll('[class]')];
    candidates.forEach((node) => {
      [.../** @type {Element} */ (node).classList].filter((name) => legacyNames.has(name)).forEach((name) => {
        issues.push({ node, message: `发现 legacy class：${name}` });
      });
    });
    root.querySelectorAll('.ui-data-table').forEach((tableNode) => {
      if (!tableNode.closest('.ui-table-wrap') && /** @type {HTMLElement} */ (tableNode).dataset.tableControls !== 'true') {
        issues.push({ node: tableNode, message: '数据表缺少 ui-table-wrap 容器' });
      }
    });
    root.querySelectorAll('.ui-empty-state[data-state]').forEach((node) => {
      if (!node.querySelector('strong')) issues.push({ node, message: '带状态的空态缺少标题节点' });
    });
    // A page has exactly one h1 — its title. Without this rule the heading level
    // drifts back as soon as someone copies a page skeleton.
    const ownerDocument = /** @type {Document | null} */ (root.nodeType === 9 ? root : root.ownerDocument);
    if (ownerDocument) {
      const headings = ownerDocument.querySelectorAll('h1');
      if (headings.length !== 1) {
        issues.push({ node: ownerDocument.body, message: `页面应有且仅有一个 h1，当前 ${headings.length} 个` });
      }
    }
    return issues;
  };
  // PC canvas text needs explicit colors: CSS inheritance stops at the canvas.
  // Use ECharts' public preprocessor; never wrap init/setOption or recreate charts.
  function installChartTheme() {
    if (!window.echarts?.registerPreprocessor) return;
    const chartThemeInstalled = Symbol.for('tmall.chart-theme-installed');
    if (window[chartThemeInstalled]) return;
    window[chartThemeInstalled] = true;
    const each = (value, apply) => (Array.isArray(value) ? value : value ? [value] : []).forEach(apply);
    const isPC = () => window.matchMedia('(min-width: 960px)').matches;
    function themeChartOption(option) {
      if (!isPC()) return;
      const styles = getComputedStyle(document.documentElement);
      const token = (name) => styles.getPropertyValue(name).trim();
      const color = token('--text-secondary');
      const fontFamily = token('--font-sans');
      const textStyle = (existing) => ({ ...existing, color, fontFamily });
      option.textStyle = textStyle(option.textStyle);
      each(option.legend, (legend) => {
        legend.textStyle = textStyle(legend.textStyle);
        legend.pageTextStyle = textStyle(legend.pageTextStyle);
      });
      each(option.title, (title) => {
        title.textStyle = textStyle(title.textStyle);
        title.subtextStyle = textStyle(title.subtextStyle);
      });
      ['xAxis', 'yAxis'].forEach((key) => each(option[key], (axis) => {
        axis.axisLabel = textStyle(axis.axisLabel);
        axis.nameTextStyle = textStyle(axis.nameTextStyle);
        if (axis.name) {
          // Keep end-of-axis captions inside compact PC canvases; preserve
          // explicitly chosen gaps and non-default caption placement/rotation.
          axis.nameGap ??= Number.parseFloat(token('--space-2'));
          if (key === 'xAxis' && (!axis.nameLocation || axis.nameLocation === 'end') && !axis.nameRotate) {
            axis.nameTextStyle.align = 'right';
          }
        }
        axis.axisLine = { ...axis.axisLine, lineStyle: { ...axis.axisLine?.lineStyle, color: token('--border-default') } };
        axis.splitLine = { ...axis.splitLine, lineStyle: { ...axis.splitLine?.lineStyle, color: token('--border-default') } };
      }));
      each(option.tooltip, (tooltip) => {
        tooltip.backgroundColor = token('--surface-base');
        tooltip.borderColor = token('--border-default');
        tooltip.textStyle = { ...tooltip.textStyle, color: token('--text-primary'), fontFamily };
      });
      each(option.series, (series) => {
        series.label = textStyle(series.label);
        series.emphasis = { ...series.emphasis, label: textStyle(series.emphasis?.label) };
        if (series.endLabel) series.endLabel = textStyle(series.endLabel);
      });
    }
    window.echarts.registerPreprocessor(themeChartOption);
    new MutationObserver(() => {
      if (!isPC()) return;
      document.querySelectorAll('[_echarts_instance_]').forEach((node) => {
        const chart = window.echarts.getInstanceByDom(node);
        if (!chart || chart.isDisposed()) return;
        const current = chart.getOption() || {};
        // Merge presentation-only patches by component index. In particular do not
        // round-trip getOption(), which can reset selections, dataZoom or datasets.
        const patch = {};
        ['legend', 'title', 'xAxis', 'yAxis', 'tooltip'].forEach((key) => {
          if (current[key]?.length) patch[key] = current[key].map(() => ({}));
        });
        if (current.series?.length) patch.series = current.series.map(() => ({}));
        themeChartOption(patch);
        chart.setOption(patch, { silent: true });
      });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    // Respect the OS motion setting without rebuilding charts or resetting data.
    // Observe creation before the next paint, then coalesce later rendered events
    // so data refreshes using notMerge also keep the user's reduced-motion choice.
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const pausedMotion = new WeakMap();
    const observedMotion = new WeakSet();
    let motionQueued = false;
    const scheduleMotion = () => {
      if (motionQueued) return;
      motionQueued = true;
      queueMicrotask(() => { motionQueued = false; syncChartMotion(); });
    };
    function syncChartMotion() {
      if (!isPC()) return;
      document.querySelectorAll('[_echarts_instance_]').forEach((node) => {
        const chart = window.echarts.getInstanceByDom(node);
        if (!chart || chart.isDisposed()) return;
        if (!observedMotion.has(chart)) {
          observedMotion.add(chart);
          chart.on('rendered', () => { if (motionPreference.matches && isPC()) scheduleMotion(); });
        }
        const current = chart.getOption();
        if (!current?.series?.length) return;
        if (motionPreference.matches) {
          if (!pausedMotion.has(chart)) pausedMotion.set(chart, {
            animation: current.animation,
            series: current.series.map((series) => series.animation ?? null)
          });
          if (current.animation !== false || current.series.some((series) => series.animation !== false)) {
            chart.setOption({ animation: false, series: current.series.map(() => ({ animation: false })) }, { silent: true });
          }
        } else if (pausedMotion.has(chart)) {
          const previous = pausedMotion.get(chart);
          pausedMotion.delete(chart);
          chart.setOption({ animation: previous.animation, series: current.series.map((series, index) => ({ animation: previous.series[index] ?? null })) }, { silent: true });
        }
      });
    }
    motionPreference.addEventListener('change', syncChartMotion);
    new MutationObserver(scheduleMotion).observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ['_echarts_instance_'] });
    syncChartMotion();

  }
  installChartTheme();

  const api = { text, create, clear, escape, formatDateTime, format, status, renderDataState, icon, button, badge, emptyState, dataState, metricCard, metricGrid, panel, pageHeader, filterToolbar, table, productIdentity, setState, contextBar, tableToolbar, detailDrawer, stickyActionBar, modal, confirm, popover, enableLightDismiss, fieldSelector, audit };
  window.TmallUI = Object.freeze(api);
})();
