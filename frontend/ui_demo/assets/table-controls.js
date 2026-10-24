(function () {
  const PAGE_SIZES = [20, 50, 100, 200];
  const tableStates = new WeakMap();
  const liveStates = new Set();
  let updateQueued = false;

  const $ = (selector, root = document) => root.querySelector(selector);
  const cleanText = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

  function isPlaceholderRow(row) {
    const cells = [...row.cells];
    return cells.length === 1 && Number(cells[0].colSpan || 1) > 1;
  }

  function rowsFor(table) {
    return table.tBodies[0] ? [...table.tBodies[0].rows].filter((row) => !isPlaceholderRow(row)) : [];
  }

  // 5-1：分页不再「全部行建 DOM 再用 hidden 藏起来」，只把「当前页 + 下一页」挂在 tbody 上。
  // 其余行仍保留在 state.allRows 里（detached），翻页时按需挂回。
  // 这样 data-center 那种 4 表 × 100 行的页面节点数从 2.4 万降到万级以内。
  const RENDER_WINDOW_FACTOR = 2;

  // 缓存是否仍然可信：tbody 里不能出现缓存不认识的行；缓存里「未被我们主动摘除」的行必须还在 tbody。
  // 页面脚本整体重渲染 tbody 时，这里会失配 → 丢弃缓存，以 tbody 为准。
  function cachedRowsValid(table, state) {
    const cached = state.allRows;
    const body = table.tBodies[0];
    if (!cached || !body) return false;
    const cachedSet = new Set(cached);
    for (const row of body.rows) {
      if (isPlaceholderRow(row)) continue;
      if (!cachedSet.has(row)) return false;
    }
    const parked = state.parked || new Set();
    for (const row of cached) {
      if (parked.has(row)) continue;
      if (row.parentNode !== body) return false;
    }
    return true;
  }

  function allRows(table, state) {
    if (state.allRows && cachedRowsValid(table, state)) return state.allRows;
    const rows = rowsFor(table);
    state.allRows = rows;
    state.parked = new Set();
    return rows;
  }

  function pageSizesFor(table, state) {
    const configured = String(table.dataset.pageSizes || '')
      .split(',')
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isInteger(value) && value > 0);
    return [...new Set([...(configured.length ? configured : PAGE_SIZES), state.pageSize])].sort((first, second) => first - second);
  }

  function headerLabel(cell) {
    return cleanText(cell.dataset.tableHeaderLabel || cell.textContent);
  }

  function headerKey(cell, index) {
    return cell.dataset.fieldKey || cell.dataset.tableSortKey || `${index}:${headerLabel(cell)}`;
  }

  function isSortableHeader(cell) {
    const key = cell.dataset.fieldKey || '';
    const label = headerLabel(cell);
    if (cell.dataset.sortable === 'false') return false;
    if (['select', 'star', 'action'].includes(key)) return false;
    if (/^(收藏|操作)$/.test(label)) return false;
    if (cell.querySelector('input, select, textarea')) return false;
    return Boolean(label);
  }

  function iconName(direction) {
    return direction === 'asc' ? 'chevron-up' : direction === 'desc' ? 'chevron-down' : 'chevrons-up-down';
  }

  function sortValue(value) {
    const text = cleanText(value);
    if (!text || /^--+$/.test(text) || text === '暂无' || text === '无') return { kind: 'empty', value: null };
    const dateText = text.replace(/[年月]/g, '-').replace(/日/g, '');
    if (/^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$/.test(dateText)) return { kind: 'date', value: Date.parse(dateText.replace(/\//g, '-')) };
    const normalized = text.replace(/[¥￥,%，\s]/g, '').replace(/万元?/g, '0000').replace(/万/g, '0000');
    if (/^-?\d+(\.\d+)?$/.test(normalized)) return { kind: 'number', value: Number(normalized) };
    return { kind: 'text', value: text };
  }

  function cellSortValue(cell) {
    if (!cell) return '';
    if (cell.dataset?.sortValue != null) return cell.dataset.sortValue;
    const select = cell.querySelector?.('select');
    if (select) {
      const selected = select.selectedOptions?.[0] || select.options?.[select.selectedIndex];
      return selected?.textContent ?? select.value ?? '';
    }
    const input = cell.querySelector?.('input:not([type="checkbox"]):not([type="radio"]), textarea');
    if (input) return input.value ?? input.textContent ?? '';
    return cell.textContent || '';
  }

  function compareCells(first, second, direction) {
    const a = sortValue(first);
    const b = sortValue(second);
    if (a.kind === 'empty' && b.kind !== 'empty') return 1;
    if (a.kind !== 'empty' && b.kind === 'empty') return -1;
    if (a.kind === b.kind && a.value === b.value) return 0;
    let result;
    if (a.kind === b.kind && (a.kind === 'number' || a.kind === 'date')) result = a.value - b.value;
    else result = String(a.value ?? '').localeCompare(String(b.value ?? ''), 'zh-CN', { numeric: true, sensitivity: 'base' });
    return direction === 'desc' ? -result : result;
  }

  function tableHost(table) {
    return table.closest('.ui-table-wrap') || table.parentElement;
  }

  function currentHeaderRow(table) {
    return table.tHead?.rows?.[0] || null;
  }

  function stateFor(table) {
    let state = tableStates.get(table);
    if (state) return state;
    state = {
      table,
      host: tableHost(table),
      sortKey: '',
      sortDirection: '',
      page: 1,
      pageSize: Number(table.dataset.pageSize) || 20,
      serverPagination: table.dataset.tablePagination === 'server',
      controls: null,
      controlsOffset: 0,
      sticky: null,
      bodyObserver: null,
      headObserver: null,
      sizeObserver: null,
      sizeObserverTargets: [],
      stickySyncFrame: 0,
      ignoreBodyMutation: false,
      ignoreHeadMutation: false,
      refreshQueued: false,
      allRows: null,
      parked: null,
    };
    tableStates.set(table, state);
    liveStates.add(state);
    return state;
  }

  function setSortIcon(button, direction) {
    const nextIcon = iconName(direction);
    if (button.dataset.tableSortIconName === nextIcon) return false;
    const icon = document.createElement('i');
    icon.className = 'table-sort-button__icon';
    icon.dataset.tableSortIcon = '';
    icon.dataset.lucide = nextIcon;
    button.querySelector('.table-sort-button__icon')?.replaceWith(icon);
    button.dataset.tableSortIconName = nextIcon;
    return true;
  }

  function syncHeaderState(table, state) {
    const row = currentHeaderRow(table);
    if (!row) return;
    let mutated = false;
    [...row.cells].forEach((cell, index) => {
      const key = headerKey(cell, index);
      const label = headerLabel(cell);
      const sortable = isSortableHeader(cell);
      cell.dataset.tableHeaderKey = key;
      if (!cell.dataset.tableHeaderLabel) cell.dataset.tableHeaderLabel = label;
      cell.classList.toggle('is-sortable', sortable);
      if (!sortable) {
        cell.removeAttribute('aria-sort');
        return;
      }
      let button = cell.querySelector(':scope > .table-sort-button');
      if (!button) {
        cell.replaceChildren();
        mutated = true;
        button = document.createElement('button');
        button.type = 'button';
        button.className = 'table-sort-button';
        // 行为契约用 data 属性承载：:458 的 sticky 表头克隆体要按它重新绑定点击，
        // 用 class 定位会让重命名样式时事件静默失效（DESIGN_SYSTEM.md 禁止事项 7）。
        button.dataset.tableSortButton = '';
        const text = document.createElement('span');
        text.className = 'table-sort-button__label';
        button.appendChild(text);
        const icon = document.createElement('i');
        icon.className = 'table-sort-button__icon';
        icon.dataset.tableSortIcon = '';
        icon.dataset.lucide = iconName('');
        button.appendChild(icon);
        button.addEventListener('click', () => {
          const nextDirection = state.sortKey === key && state.sortDirection === 'asc' ? 'desc' : 'asc';
          state.sortKey = key;
          state.sortDirection = nextDirection;
          state.page = 1;
          applyState(table, state);
        });
        cell.appendChild(button);
      }
      button.querySelector('.table-sort-button__label').textContent = label;
      const active = state.sortKey === key ? state.sortDirection : '';
      cell.setAttribute('aria-sort', active === 'asc' ? 'ascending' : active === 'desc' ? 'descending' : 'none');
      button.setAttribute('aria-label', `${label}，${active === 'asc' ? '当前升序，点击切换降序' : active === 'desc' ? '当前降序，点击切换升序' : '点击升序排序'}`);
      mutated = setSortIcon(button, active) || mutated;
      // 四合一表头浮层（对齐边界 BI：排序+区间筛选+清除/确定 合一个入口）。
      // 仅服务端分页表 + 数值列（th 带 .num）启用：区间筛选由服务端 min_/max_ 执行。
      if (state.serverPagination && cell.classList.contains('num') && !cell.querySelector(':scope > .table-filter-button')) {
        const filterButton = document.createElement('button');
        filterButton.type = 'button';
        filterButton.className = 'table-filter-button';
        filterButton.dataset.tableFilterButton = '';
        filterButton.setAttribute('aria-label', `${label}：排序与数值范围筛选`);
        filterButton.title = '排序 / 数值范围筛选';
        filterButton.innerHTML = '<i data-lucide="filter"></i>';
        filterButton.addEventListener('click', () => openRangeFilterPopover({ cell, key, label }));
        cell.appendChild(filterButton);
        mutated = true;
      }
    });
    if (mutated) state.ignoreHeadMutation = true;
    if (mutated) window.lucide?.createIcons();
    syncStickyHeader(table, state);
  }

  // 表头四合一筛选浮层：排序（升/降）+ 数值区间 + 清除/确定。
  // 结果通过 window 事件交付给页面（products-live 监听 tmall:table-range-filter /
  // tmall:table-header-sort），本模块保持与业务解耦。
  function readRangeBounds(key) {
    const url = new URL(window.location.href);
    const bounds = {};
    const min = url.searchParams.get(`min_${key}`);
    const max = url.searchParams.get(`max_${key}`);
    if (min != null) bounds.min = min;
    if (max != null) bounds.max = max;
    return bounds;
  }

  function openRangeFilterPopover({ cell, key, label }) {
    if (!window.TmallUI?.popover) return;
    const trigger = cell.querySelector(':scope > .table-filter-button');
    if (!trigger) return;
    const bounds = readRangeBounds(key);
    const panel = document.createElement('div');
    panel.className = 'table-range-filter';

    const sortRow = document.createElement('div');
    sortRow.className = 'table-range-filter__row';
    const sortLabel = document.createElement('span');
    sortLabel.className = 'table-range-filter__label';
    sortLabel.textContent = '排序';
    sortRow.appendChild(sortLabel);
    [['asc', '升序'], ['desc', '降序']].forEach(([order, text]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'table-range-filter__order';
      button.textContent = text;
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('tmall:table-header-sort', { detail: { field: key, order } }));
        popover?.close();
      });
      sortRow.appendChild(button);
    });

    const rangeRow = document.createElement('div');
    rangeRow.className = 'table-range-filter__row';
    const rangeLabel = document.createElement('span');
    rangeLabel.className = 'table-range-filter__label';
    rangeLabel.textContent = '筛选';
    const minInput = document.createElement('input');
    minInput.className = 'input';
    minInput.type = 'number';
    minInput.step = 'any';
    minInput.placeholder = '最小值';
    minInput.value = bounds.min ?? '';
    minInput.setAttribute('aria-label', `${label}最小值`);
    const dash = document.createElement('span');
    dash.className = 'table-range-filter__label';
    dash.textContent = '-';
    const maxInput = document.createElement('input');
    maxInput.className = 'input';
    maxInput.type = 'number';
    maxInput.step = 'any';
    maxInput.placeholder = '最大值';
    maxInput.value = bounds.max ?? '';
    maxInput.setAttribute('aria-label', `${label}最大值`);
    rangeRow.append(rangeLabel, minInput, dash, maxInput);

    const footer = document.createElement('div');
    footer.className = 'table-range-filter__row table-range-filter__footer';
    const clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.className = 'ui-button ui-button--ghost ui-button--small';
    clearButton.textContent = '清除';
    clearButton.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('tmall:table-range-filter', { detail: { field: key, min: '', max: '' } }));
      popover?.close();
    });
    const applyButton = document.createElement('button');
    applyButton.type = 'button';
    applyButton.className = 'ui-button ui-button--primary ui-button--small';
    applyButton.textContent = '确定';
    applyButton.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('tmall:table-range-filter', {
        detail: { field: key, min: minInput.value.trim(), max: maxInput.value.trim() },
      }));
      popover?.close();
    });
    footer.append(clearButton, applyButton);

    panel.append(sortRow, rangeRow, footer);
    const popover = window.TmallUI.popover({ anchor: trigger, content: panel, placement: 'bottom', className: 'table-range-filter-popover' });
    window.lucide?.createIcons();
  }

  function sortRows(table, state) {
    if (!state.sortKey || !state.sortDirection || !table.tBodies[0]) return;
    const row = currentHeaderRow(table);
    const index = row ? [...row.cells].findIndex((cell, cellIndex) => headerKey(cell, cellIndex) === state.sortKey) : -1;
    if (index < 0) return;
    const rows = allRows(table, state);
    const sorted = rows.map((item, originalIndex) => ({ item, originalIndex })).sort((first, second) => {
      const result = compareCells(cellSortValue(first.item.cells[index]), cellSortValue(second.item.cells[index]), state.sortDirection);
      return result || first.originalIndex - second.originalIndex;
    });
    state.allRows = sorted.map(({ item }) => item);
    // server 模式（products 等）没有客户端分页，也就没有 materialize 环节，这里直接按序回挂。
    if (!state.controls) {
      if (sorted.length) state.ignoreBodyMutation = true;
      sorted.forEach(({ item }) => table.tBodies[0].appendChild(item));
    }
  }

  // 只保证「当前页 + 下一页」在 DOM 里：窗口外的行 detach，窗口内第二页的行 hidden。
  function materializeRows(table, state, rows) {
    const body = table.tBodies[0];
    if (!body) return;
    const pageSize = state.pageSize;
    const start = (state.page - 1) * pageSize;
    const end = Math.min(rows.length, start + pageSize * RENDER_WINDOW_FACTOR);
    const window = rows.slice(start, end);

    const current = [...body.rows].filter((item) => !isPlaceholderRow(item));
    const windowSet = new Set(window);
    let mutated = false;
    current.forEach((item) => {
      if (!windowSet.has(item)) { item.remove(); mutated = true; }
    });
    const orderMatches = !mutated && current.length === window.length
      && current.every((item, index) => item === window[index]);
    if (!orderMatches) {
      const fragment = document.createDocumentFragment();
      window.forEach((item) => fragment.appendChild(item));
      body.appendChild(fragment);
      mutated = true;
    }
    window.forEach((item, index) => { item.hidden = index >= pageSize; });
    state.parked = new Set([...rows.slice(0, start), ...rows.slice(end)]);
    if (mutated) state.ignoreBodyMutation = true;
  }

  function ensureControls(table, state) {
    if (state.controls || table.dataset.tablePagination === 'server') return;
    const host = state.host;
    if (!host?.parentElement) return;
    const controls = document.createElement('div');
    controls.className = 'table-controls';
    controls.setAttribute('data-table-controls', '');
    const pageSizeLabel = document.createElement('label');
    pageSizeLabel.className = 'table-controls__page-size';
    pageSizeLabel.append(document.createTextNode('每页 '));
    const select = document.createElement('select');
    select.className = 'select';
    select.setAttribute('aria-label', '每页显示行数');
    pageSizesFor(table, state).forEach((size) => {
      const option = new Option(String(size), String(size));
      option.selected = size === state.pageSize;
      select.appendChild(option);
    });
    select.addEventListener('change', () => {
      state.pageSize = Number(select.value) || 20;
      state.page = 1;
      applyState(table, state);
    });
    pageSizeLabel.append(select, document.createTextNode(' 行'));
    const nav = document.createElement('div');
    nav.className = 'table-controls__nav';
    const previous = document.createElement('button');
    previous.type = 'button';
    previous.className = 'ui-button table-controls__button';
    previous.setAttribute('data-table-prev', '');
    previous.setAttribute('aria-label', '上一页');
    previous.append(document.createElement('i'));
    previous.firstChild.dataset.lucide = 'chevron-left';
    previous.append(document.createTextNode('上一页'));
    const summary = document.createElement('span');
    summary.className = 'table-controls__summary';
    summary.setAttribute('data-table-summary', '');
    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'ui-button table-controls__button';
    next.setAttribute('data-table-next', '');
    next.setAttribute('aria-label', '下一页');
    next.append(document.createTextNode('下一页'));
    const nextIcon = document.createElement('i');
    nextIcon.dataset.lucide = 'chevron-right';
    next.appendChild(nextIcon);
    previous.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; applyState(table, state); } });
    next.addEventListener('click', () => { if (state.page < state.totalPages) { state.page += 1; applyState(table, state); } });
    nav.append(previous, next);
    controls.append(summary, pageSizeLabel, nav);
    host.parentElement.insertBefore(controls, host.nextSibling);
    state.controls = { root: controls, select, previous, next, summary };
    window.lucide?.createIcons();
  }

  function updatePagination(table, state) {
    const controls = state.controls;
    if (!controls) return;
    const rows = allRows(table, state);
    state.totalRows = rows.length;
    state.totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), state.totalPages);
    materializeRows(table, state, rows);
    controls.root.hidden = rows.length === 0;
    controls.select.value = String(state.pageSize);
    controls.previous.disabled = state.page <= 1;
    controls.next.disabled = state.page >= state.totalPages;
    controls.summary.textContent = rows.length ? `第 ${state.page} / ${state.totalPages} 页，共 ${rows.length} 行` : '暂无可分页数据';
  }

  function getStickyViewport(table) {
    // Shared detail drawers are not native dialogs. Their body is the scrollport,
    // not the page viewport (a centered sheet leaves space above and below it).
    const drawerBody = table.closest('.ui-drawer__body');
    if (drawerBody) {
      const box = drawerBody.getBoundingClientRect();
      const tabs = [...drawerBody.querySelectorAll('[role="tablist"]')].filter((node) =>
        getComputedStyle(node).position === 'sticky'
        && Boolean(node.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING)
      );
      const top = Math.max(box.top, ...tabs.map((node) => node.getBoundingClientRect().bottom));
      return { top: Math.max(0, Math.min(box.bottom, top)), bottom: Math.min(window.innerHeight, box.bottom) };
    }
    const dialog = table.closest('dialog[open]');
    if (dialog) {
      const dialogBox = dialog.getBoundingClientRect();
      const header = dialog.querySelector('.modal-form__header, .lifecycle-detail__header, .promotion-detail-dialog__header');
      return {
        top: Math.max(dialogBox.top, header?.getBoundingClientRect().bottom || dialogBox.top),
        bottom: dialogBox.bottom,
      };
    }
    return {
      top: document.querySelector('.demo-topbar')?.getBoundingClientRect().bottom || 0,
      bottom: window.innerHeight,
    };
  }

  function getStickyBoundary(table) {
    return getStickyViewport(table).top;
  }

  function stickyActionBarBottomOffset(controls) {
    const bars = [...document.querySelectorAll('.ui-sticky-action-bar')]
      .filter((bar) => bar !== controls && !bar.contains(controls))
      .map((bar) => ({ bar, rect: bar.getBoundingClientRect(), style: getComputedStyle(bar) }))
      .filter(({ rect, style }) => style.display !== 'none'
        && (style.position === 'sticky' || style.position === 'fixed')
        && rect.bottom > 0 && rect.top < window.innerHeight);
    if (!bars.length) return 0;
    const top = Math.min(...bars.map(({ rect }) => rect.top));
    return Math.max(0, window.innerHeight - top + 12);
  }

  function alignFloatingControls(controls, hostBox) {
    const desiredLeft = Math.max(0, Math.min(hostBox.left, window.innerWidth));
    const desiredWidth = Math.min(hostBox.width, Math.max(0, window.innerWidth - desiredLeft));
    controls.style.left = `${hostBox.left}px`;
    controls.style.width = `${desiredWidth}px`;
    // A fixed control can inherit a containing-block offset from a nested
    // evidence/table surface. Read its actual rect and correct that offset so
    // the footer remains aligned with the table instead of escaping right.
    const actualLeft = controls.getBoundingClientRect().left;
    const correction = desiredLeft - actualLeft;
    if (Math.abs(correction) > 0.5) controls.style.left = `${hostBox.left + correction}px`;
    const rect = controls.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      controls.style.width = `${Math.max(0, rect.width - (rect.right - window.innerWidth))}px`;
    }
  }

  function makeStickyHeader(table, state) {
    if (state.sticky || !table.tHead) return;
    const root = document.createElement('div');
    root.className = 'table-sticky-head';
    root.setAttribute('aria-hidden', 'true');
    const cloneTable = document.createElement('table');
    cloneTable.className = 'table-sticky-head__table';
    root.appendChild(cloneTable);
    // Keep the clone in its owning drawer's stacking context. A clone
    // appended to body is hidden behind the drawer backdrop and outlives closing.
    const overlay = table.closest('.ui-drawer');
    (overlay || document.body).appendChild(root);
    state.sticky = { root, table: cloneTable };
  }

  function findAssociatedControls(table, host) {
    const generated = tableStates.get(table)?.controls?.root;
    if (generated) return generated;
    const direct = host?.nextElementSibling;
    if (direct?.matches('.table-controls')) return direct;
    return [...(host?.parentElement?.children || [])].find((element) =>
      element.matches?.('.table-controls') && Boolean(host.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING)
    ) || null;
  }

  function updateStickyPagination(table, state) {
    if (!state.host) return;
    const controls = findAssociatedControls(table, state.host);
    const hostBox = state.host.getBoundingClientRect();
    const viewport = getStickyViewport(table);
    // The product list owns a viewport-sized scroller; measure wrapped chrome,
    // rather than assuming that the topbar is always its one-row token height.
    if (controls && document.body.dataset.page === 'products'
      && document.body.dataset.productsDisplayMode === 'list'
      && state.host.closest('#products-list') && window.matchMedia('(min-width: 960px)').matches) {
      const gap = parseFloat(getComputedStyle(state.host).getPropertyValue('--space-6'));
      const offset = `${Math.ceil(viewport.top + controls.getBoundingClientRect().height + gap)}px`;
      if (state.host.style.getPropertyValue('--products-list-viewport-offset') !== offset) {
        state.host.style.setProperty('--products-list-viewport-offset', offset);
      }
    }
    const controlsHeight = controls?.getBoundingClientRect().height || 0;
    const tableInView = hostBox.top < viewport.bottom - controlsHeight && hostBox.bottom > viewport.top;
    const viewportBottomOffset = Math.max(0, window.innerHeight - viewport.bottom);
    if (controls && !controls.classList.contains('is-table-sticky-footer')) {
      state.controlsOffset = Math.max(0, controls.getBoundingClientRect().top - hostBox.bottom);
    }
    const controlsShouldFloat = Boolean(controls) && tableInView && hostBox.bottom + state.controlsOffset > viewport.bottom;
    controls?.classList.toggle('is-table-sticky-footer', controlsShouldFloat);
    if (controlsShouldFloat) {
      alignFloatingControls(controls, hostBox);
      controls.style.bottom = `${Math.max(viewportBottomOffset, stickyActionBarBottomOffset(controls))}px`;
    } else if (controls) {
      controls.style.removeProperty('left');
      controls.style.removeProperty('width');
      controls.style.removeProperty('bottom');
    }
  }

  function syncStickyColumnWidths(table, state) {
    const sourceCells = [...(currentHeaderRow(table)?.cells || [])];
    const colgroup = state.sticky?.table.querySelector(':scope > colgroup');
    sourceCells.forEach((cell, index) => {
      const width = `${cell.getBoundingClientRect().width}px`;
      const column = colgroup?.children[index];
      const cloneCell = state.sticky.table.tHead?.rows?.[0]?.cells?.[index];
      if (column) column.style.width = width;
      if (cloneCell) {
        cloneCell.style.width = width;
        cloneCell.style.minWidth = width;
        cloneCell.style.maxWidth = width;
      }
    });
    state.sticky.table.style.width = `${table.offsetWidth}px`;
  }

  function scheduleStickySizeSync(table, state) {
    if (state.stickySyncFrame) return;
    state.stickySyncFrame = requestAnimationFrame(() => {
      state.stickySyncFrame = 0;
      syncStickyHeader(table, state);
      updateStickyHeader(table, state);
      updateStickyPagination(table, state);
    });
  }

  function observeStickySizes(table, state) {
    if (!window.ResizeObserver) return;
    if (!state.sizeObserver) state.sizeObserver = new ResizeObserver(() => scheduleStickySizeSync(table, state));
    const headerCells = [...(currentHeaderRow(table)?.cells || [])];
    const targets = [state.host, table, ...headerCells].filter(Boolean);
    if (targets.length === state.sizeObserverTargets.length && targets.every((element, index) => element === state.sizeObserverTargets[index])) return;
    state.sizeObserver.disconnect();
    targets.forEach((element) => state.sizeObserver.observe(element));
    state.sizeObserverTargets = targets;
  }

  function syncStickyHeader(table, state) {
    const headerRow = currentHeaderRow(table);
    if (!headerRow) return;
    makeStickyHeader(table, state);
    if (!state.sticky) return;
    const clone = table.tHead.cloneNode(true);
    clone.removeAttribute('data-promotion-head');
    clone.removeAttribute('data-products-head');
    clone.removeAttribute('data-lifecycle-detail-head');
    // Page-specific head markers live on the row in these tables, not on thead.
    clone.querySelectorAll('[data-promotion-head], [data-products-head], [data-lifecycle-detail-head]').forEach((node) => {
      node.removeAttribute('data-promotion-head');
      node.removeAttribute('data-products-head');
      node.removeAttribute('data-lifecycle-detail-head');
    });
    clone.querySelectorAll('*').forEach((node) => {
      [...node.attributes].forEach((attribute) => {
        if (attribute.name.startsWith('data-') && !attribute.name.startsWith('data-table-')) node.removeAttribute(attribute.name);
      });
      if (node.matches('button, input, select, textarea, a')) node.tabIndex = -1;
    });
    const colgroup = document.createElement('colgroup');
    [...headerRow.cells].forEach(() => colgroup.appendChild(document.createElement('col')));
    state.sticky.table.replaceChildren(colgroup, clone);
    // 按 data 属性定位（见 :186 的创建处），避免把事件绑在样式类名上。
    // 兼容选择器保留 .table-sort-button：本文件 :180/:462 仍用它做样式性查询，
    // 且外部若有旧标记过的表头也应继续可用。
    [...state.sticky.table.querySelectorAll('[data-table-sort-button], .table-sort-button')].forEach((button) => {
      const index = Number(button.closest('th')?.cellIndex);
      button.addEventListener('click', (event) => {
        event.preventDefault();
        const original = currentHeaderRow(table)?.cells[index]?.querySelector('.table-sort-button');
        original?.click();
      });
    });
    // 吸顶克隆体上的筛选按钮同样转发回主表头（事件在克隆时丢失，按 data 属性重绑）
    [...state.sticky.table.querySelectorAll('[data-table-filter-button]')].forEach((button) => {
      const index = Number(button.closest('th')?.cellIndex);
      button.addEventListener('click', (event) => {
        event.preventDefault();
        const original = currentHeaderRow(table)?.cells[index]?.querySelector('[data-table-filter-button]');
        original?.click();
      });
    });
    syncStickyColumnWidths(table, state);
    observeStickySizes(table, state);
  }

  function updateStickyHeader(table, state) {
    if (!state.sticky || !state.host || !table.tHead) return;
    const hostBox = state.host.getBoundingClientRect();
    const headerBox = table.tHead.getBoundingClientRect();
    const boundary = getStickyBoundary(table);
    const visible = hostBox.top < boundary && hostBox.bottom > boundary + headerBox.height && headerBox.height > 0;
    state.sticky.root.classList.toggle('is-visible', visible);
    if (!visible) return;
    state.sticky.root.style.left = `${hostBox.left}px`;
    state.sticky.root.style.top = `${boundary}px`;
    state.sticky.root.style.width = `${hostBox.width}px`;
    state.sticky.root.style.height = `${headerBox.height}px`;
    state.sticky.table.style.transform = `translateX(-${state.host.scrollLeft || 0}px)`;
    syncStickyColumnWidths(table, state);
    updateStickyPagination(table, state);
  }

  function scheduleRefresh(table, state) {
    if (state.refreshQueued) return;
    state.refreshQueued = true;
    queueMicrotask(() => {
      state.refreshQueued = false;
      syncHeaderState(table, state);
      ensureControls(table, state);
      sortRows(table, state);
      updatePagination(table, state);
      updateStickyHeader(table, state);
    });
  }

  function applyState(table, state) {
    syncHeaderState(table, state);
    sortRows(table, state);
    updatePagination(table, state);
    updateStickyHeader(table, state);
  }

  function isManagedTable(table) {
    return table instanceof HTMLTableElement && (table.classList.contains('ui-data-table') || table.dataset.tableControls === 'true');
  }

  function managedTablesWithin(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return [];
    return [
      ...(node.matches?.('table.ui-data-table, table[data-table-controls="true"]') ? [node] : []),
      ...(node.querySelectorAll ? [...node.querySelectorAll('table.ui-data-table, table[data-table-controls="true"]')] : []),
    ];
  }

  function cleanupTable(table) {
    const state = tableStates.get(table);
    if (!state) return;
    state.bodyObserver?.disconnect();
    state.headObserver?.disconnect();
    state.sizeObserver?.disconnect();
    state.sizeObserverTargets = [];
    if (state.stickySyncFrame) cancelAnimationFrame(state.stickySyncFrame);
    state.sticky?.root.remove();
    state.controls?.root.remove();
    liveStates.delete(state);
    tableStates.delete(table);
  }

  function enhanceTable(table) {
    if (!isManagedTable(table)) return;
    const state = stateFor(table);
    ensureControls(table, state);
    if (!state.bodyObserver && table.tBodies[0]) {
      state.bodyObserver = new MutationObserver(() => {
        if (state.ignoreBodyMutation) { state.ignoreBodyMutation = false; return; }
        // 外部（页面脚本）重建了 tbody → 行缓存失效，以下一次 tbody 为准。
        state.allRows = null;
        state.parked = null;
        scheduleRefresh(table, state);
      });
      state.bodyObserver.observe(table.tBodies[0], { childList: true });
    }
    if (!state.headObserver && table.tHead) {
      const observeHead = () => state.headObserver?.observe(table.tHead, { childList: true, subtree: true });
      state.headObserver = new MutationObserver(() => {
        state.headObserver.disconnect();
        const selfMutation = state.ignoreHeadMutation;
        state.ignoreHeadMutation = false;
        if (!selfMutation) scheduleRefresh(table, state);
        queueMicrotask(observeHead);
      });
      observeHead();
    }
    observeStickySizes(table, state);
    scheduleRefresh(table, state);
  }

  function refreshAll() {
    document.querySelectorAll('table.ui-data-table, table[data-table-controls="true"]').forEach(enhanceTable);
    liveStates.forEach((state) => { updateStickyHeader(state.table, state); updateStickyPagination(state.table, state); });
  }

  let viewportFrame = 0;
  let viewportResize = false;
  const scheduleViewportSync = (resize = false) => {
    viewportResize = viewportResize || resize;
    if (viewportFrame) return;
    viewportFrame = requestAnimationFrame(() => {
      viewportFrame = 0;
      const shouldResync = viewportResize;
      viewportResize = false;
      liveStates.forEach((state) => {
        if (shouldResync) syncStickyHeader(state.table, state);
        updateStickyHeader(state.table, state);
        updateStickyPagination(state.table, state);
      });
    });
  };
  window.addEventListener('scroll', () => scheduleViewportSync(), { capture: true, passive: true });
  window.addEventListener('resize', () => scheduleViewportSync(true), { passive: true });
  const documentObserver = new MutationObserver((records) => {
    records.forEach((record) => {
      [...record.removedNodes].flatMap(managedTablesWithin).forEach(cleanupTable);
      [...record.addedNodes].flatMap(managedTablesWithin).forEach((table) => {
        if (!tableStates.has(table)) enhanceTable(table);
      });
    });
  });
  documentObserver.observe(document.documentElement, { childList: true, subtree: true });
  refreshAll();
  window.TmallTableControls = { refresh: refreshAll };
})();
