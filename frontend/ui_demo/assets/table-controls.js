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
    return table.closest('.data-table-wrap') || table.parentElement;
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
      controls: null,
      sticky: null,
      stickyFooter: null,
      bodyObserver: null,
      headObserver: null,
      sizeObserver: null,
      sizeObserverTargets: [],
      stickySyncFrame: 0,
      ignoreBodyMutation: false,
      ignoreHeadMutation: false,
      refreshQueued: false,
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
    });
    if (mutated) state.ignoreHeadMutation = true;
    if (mutated) window.lucide?.createIcons();
    syncStickyHeader(table, state);
  }

  function sortRows(table, state) {
    if (!state.sortKey || !state.sortDirection || !table.tBodies[0]) return;
    const row = currentHeaderRow(table);
    const index = row ? [...row.cells].findIndex((cell, cellIndex) => headerKey(cell, cellIndex) === state.sortKey) : -1;
    if (index < 0) return;
    const rows = rowsFor(table);
    const sorted = rows.map((item, originalIndex) => ({ item, originalIndex })).sort((first, second) => {
      const result = compareCells(cellSortValue(first.item.cells[index]), cellSortValue(second.item.cells[index]), state.sortDirection);
      return result || first.originalIndex - second.originalIndex;
    });
    if (sorted.length) state.ignoreBodyMutation = true;
    sorted.forEach(({ item }) => table.tBodies[0].appendChild(item));
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
    previous.className = 'button table-controls__button';
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
    next.className = 'button table-controls__button';
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
    const rows = rowsFor(table);
    const controls = state.controls;
    if (!controls) return;
    state.totalRows = rows.length;
    state.totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), state.totalPages);
    rows.forEach((row, index) => {
      row.hidden = index < (state.page - 1) * state.pageSize || index >= state.page * state.pageSize;
    });
    controls.root.hidden = rows.length === 0;
    controls.select.value = String(state.pageSize);
    controls.previous.disabled = state.page <= 1;
    controls.next.disabled = state.page >= state.totalPages;
    controls.summary.textContent = rows.length ? `第 ${state.page} / ${state.totalPages} 页，共 ${rows.length} 行` : '暂无可分页数据';
  }

  function getStickyViewport(table) {
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

  function makeStickyHeader(table, state) {
    if (state.sticky || !table.tHead) return;
    const root = document.createElement('div');
    root.className = 'table-sticky-head';
    root.setAttribute('aria-hidden', 'true');
    const cloneTable = document.createElement('table');
    cloneTable.className = 'table-sticky-head__table';
    root.appendChild(cloneTable);
    document.body.appendChild(root);
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

  function makeStickyFooter(table, state) {
    if (state.stickyFooter || !state.host) return;
    const root = document.createElement('div');
    root.className = 'table-sticky-scrollbar';
    const range = document.createElement('input');
    range.className = 'table-sticky-scrollbar__range';
    range.type = 'range';
    range.min = '0';
    range.step = '1';
    range.value = '0';
    const scroller = range;
    scroller.setAttribute('aria-label', '横向滚动表格');
    root.appendChild(range);
    document.body.appendChild(root);
    state.stickyFooter = { root, range, controls: null, controlsOffset: 0, syncing: false };
    state.host.addEventListener('scroll', () => {
      const footer = state.stickyFooter;
      if (!footer || footer.syncing) return;
      footer.syncing = true;
      footer.range.value = String(state.host.scrollLeft);
      footer.syncing = false;
    });
    range.addEventListener('input', () => {
      const footer = state.stickyFooter;
      if (!footer || footer.syncing) return;
      footer.syncing = true;
      state.host.scrollLeft = Number(footer.range.value);
      footer.syncing = false;
    });
  }

  function resetStickyFooter(footer) {
    footer.root.classList.remove('is-visible');
    footer.root.style.removeProperty('left');
    footer.root.style.removeProperty('width');
    footer.root.style.removeProperty('bottom');
    if (!footer.controls) return;
    footer.controls.classList.remove('is-table-sticky-footer');
    footer.controls.style.removeProperty('left');
    footer.controls.style.removeProperty('width');
    footer.controls.style.removeProperty('bottom');
  }

  function updateStickyFooter(table, state) {
    if (!state.host) return;
    makeStickyFooter(table, state);
    const footer = state.stickyFooter;
    if (!footer) return;
    const controls = findAssociatedControls(table, state.host);
    if (footer.controls && footer.controls !== controls) resetStickyFooter(footer);
    footer.controls = controls;
    const hostBox = state.host.getBoundingClientRect();
    const viewport = getStickyViewport(table);
    const tableInView = hostBox.top < viewport.bottom && hostBox.bottom > viewport.top;
    const viewportBottomOffset = Math.max(0, window.innerHeight - viewport.bottom);
    if (controls && !controls.classList.contains('is-table-sticky-footer')) {
      footer.controlsOffset = Math.max(0, controls.getBoundingClientRect().top - hostBox.bottom);
    }
    const controlsShouldFloat = Boolean(controls) && tableInView && hostBox.bottom + footer.controlsOffset > viewport.bottom;
    controls?.classList.toggle('is-table-sticky-footer', controlsShouldFloat);
    if (controlsShouldFloat) {
      controls.style.left = `${hostBox.left}px`;
      controls.style.width = `${hostBox.width}px`;
      controls.style.bottom = `${viewportBottomOffset}px`;
    } else if (controls) {
      controls.style.removeProperty('left');
      controls.style.removeProperty('width');
      controls.style.removeProperty('bottom');
    }
    const scrollbarShouldFloat = tableInView && state.host.scrollWidth > state.host.clientWidth && hostBox.bottom > viewport.bottom;
    footer.root.classList.toggle('is-visible', scrollbarShouldFloat);
    if (!scrollbarShouldFloat) return;
    footer.range.max = String(Math.max(0, state.host.scrollWidth - state.host.clientWidth));
    footer.range.value = String(Math.min(Number(footer.range.max), state.host.scrollLeft));
    footer.root.style.left = `${hostBox.left}px`;
    footer.root.style.width = `${hostBox.width}px`;
    footer.root.style.bottom = `${viewportBottomOffset + (controlsShouldFloat ? controls.getBoundingClientRect().height + 6 : 6)}px`;
    if (!footer.syncing) footer.range.value = String(state.host.scrollLeft);
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
      updateStickyFooter(table, state);
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
    if (!table.tHead) return;
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
    [...currentHeaderRow(table).cells].forEach(() => colgroup.appendChild(document.createElement('col')));
    state.sticky.table.replaceChildren(colgroup, clone);
    [...state.sticky.table.querySelectorAll('.table-sort-button')].forEach((button) => {
      const index = Number(button.closest('th')?.cellIndex);
      button.addEventListener('click', (event) => {
        event.preventDefault();
        const original = currentHeaderRow(table)?.cells[index]?.querySelector('.table-sort-button');
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
    updateStickyFooter(table, state);
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
    return table instanceof HTMLTableElement && (table.classList.contains('data-table') || table.dataset.tableControls === 'true');
  }

  function managedTablesWithin(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return [];
    return [
      ...(node.matches?.('table.data-table, table[data-table-controls="true"]') ? [node] : []),
      ...(node.querySelectorAll ? [...node.querySelectorAll('table.data-table, table[data-table-controls="true"]')] : []),
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
    if (state.stickyFooter) {
      resetStickyFooter(state.stickyFooter);
      state.stickyFooter.root.remove();
    }
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
    document.querySelectorAll('table.data-table, table[data-table-controls="true"]').forEach(enhanceTable);
    liveStates.forEach((state) => { updateStickyHeader(state.table, state); updateStickyFooter(state.table, state); });
  }

  window.addEventListener('scroll', () => {
    liveStates.forEach((state) => { updateStickyHeader(state.table, state); updateStickyFooter(state.table, state); });
  }, true);
  window.addEventListener('resize', () => {
    liveStates.forEach((state) => { syncStickyHeader(state.table, state); updateStickyHeader(state.table, state); updateStickyFooter(state.table, state); });
  });
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
