(function (global) {
  'use strict';

  /** 商品页「表格渲染 / 时间线视图 / 移动端摘要 / 分页选择」模块。
   *
   *  从 products-live.js 的单闭包中切出（闭包状态显式化第三步）：
   *  本模块拥有列表表格、时间线表格、移动端卡片摘要、分页与选择控件的全部渲染行为；
   *  rows/selected/visibleColumns/timelineRows 等仍存放在页面共享 state 上，
   *  对主闭包的依赖全部通过 deps 显式注入。
   *
   *  deps 契约（由 products-live.js 提供）：
   *  - state               页面共享状态
   *  - $                    查询助手
   *  - number/money/percent/decimal   数值格式化
   *  - field                数值取值助手
   *  - productId/salesOf/spendOf      行级取值助手
   *  - columnsByKey         列定义索引 Map
   *  - makeProductPlaceholder        图片占位生成器
   *  - openProductDetail   打开商品详情
   *  - toggleStar          切换收藏
   *  - updateField/rememberClassification  分层/风格编辑回写
   *  - classificationValues        分类候选值
   *  - setStatus           页面状态文案
   *  - asArray/currentRange       API 响应/日期范围助手
   */

  function createTableRender(deps) {
    const {
      state, $, number, money, percent, decimal, field,
      productId, salesOf, spendOf, columnsByKey, makeProductPlaceholder,
      openProductDetail, toggleStar, updateField, rememberClassification,
      classificationValues, setStatus, asArray, currentRange,
    } = deps;

    function setRowStatus(message) {
      const body = $('[data-products-body]');
      body.replaceChildren();
      const row = document.createElement('tr');
      const cell = row.insertCell();
      cell.colSpan = state.visibleColumns.length + 3;
      cell.textContent = message;
      row.appendChild(cell);
      body.appendChild(row);
    }

    function visibleRows() {
      return state.starredOnly ? state.rows.filter((item) => Number(item.starred || 0) === 1) : state.rows;
    }

    function updateKpis(rows) {
      const sales = rows.reduce((sum, item) => sum + salesOf(item), 0);
      const spend = rows.reduce((sum, item) => sum + spendOf(item), 0);
      $('[data-products-kpi="total"]').textContent = number(state.total);
      $('[data-products-kpi="sales"]').textContent = money(sales);
      $('[data-products-kpi="spend"]').textContent = money(spend);
      $('[data-products-kpi="roi"]').textContent = spend ? (sales / spend).toFixed(2) : '--';
    }

    function metricBarValue(item, key) {
      const value = key === 'payment_amount' ? salesOf(item) : key === 'ad_spend' ? spendOf(item) : field(item, key);
      return Number.isFinite(value) && value > 0 ? value : 0;
    }

    function badge(value, fallback) {
      const item = document.createElement('span');
      item.className = 'ui-badge ui-badge--muted';
      item.textContent = value || fallback || '--';
      return item;
    }

    function editableSelect(item, key) {
      const wrap = document.createElement('div'); wrap.className = 'editable-classification';
      const input = document.createElement('input');
      const listId = `product-${key}-options-${productId(item).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
      input.className = 'input'; input.setAttribute('list', listId);
      input.disabled = Object.keys(state.capabilities).length > 0 && !DemoApi.can({ capabilities: state.capabilities }, 'can_edit');
      input.setAttribute('aria-label', key === 'tier' ? '修改分层' : '修改风格');
      const current = DemoLabels.clean(item[key], '');
      input.value = current; input.placeholder = key === 'tier' ? '未分层' : '未分类';
      const list = document.createElement('datalist'); list.id = listId;
      const dictionaryGroup = key === 'tier' ? 'tiers' : 'styles';
      const values = [...new Set([current, ...classificationValues(key)])].filter(Boolean);
      values.forEach((value) => {
        const option = document.createElement('option');
        option.value = value;
        list.appendChild(option);
      });
      input.addEventListener('change', async () => {
        const updated = await updateField(productId(item), key, input.value.trim());
        if (updated) await rememberClassification(dictionaryGroup, input.value.trim());
      });
      input.addEventListener('input', () => {
        const cell = wrap.closest('td');
        if (cell) cell.dataset.sortValue = input.value.trim();
      });
      wrap.dataset.sortValue = current;
      wrap.append(input, list); return wrap;
    }

    function addCell(row, content, className, fieldKey) {
      const cell = row.insertCell();
      if (className) cell.className = className;
      if (fieldKey) cell.dataset.fieldKey = fieldKey;
      if (content instanceof Node) cell.appendChild(content);
      else cell.textContent = content;
      return cell;
    }

    function formatColumnValue(item, column) {
      const value = column.key === 'payment_amount' ? salesOf(item) : column.key === 'ad_spend' ? spendOf(item) : field(item, column.key);
      if (column.format === 'profit') return profitBlock(value);
      if (column.format === 'money') return money(value);
      if (column.format === 'number') return number(value);
      if (column.format === 'percent') return percent(value);
      if (column.format === 'decimal') return decimal(value);
      return String(item[column.key] || '--');
    }

    // 利润色块（对齐边界 BI .slot-color-block）：红=盈利/涨、绿=亏损/跌（中国电商惯例，
    // 方向语义与 --trend-up-text 一致）；0 是盈亏平衡真值用中性灰，空值灰块 `--`。
    function profitBlock(value) {
      const block = document.createElement('span');
      block.className = 'profit-block';
      const num = Number(value);
      if (value === null || value === undefined || value === '' || !Number.isFinite(num)) {
        block.classList.add('profit-block--empty');
        block.textContent = '--';
        return block;
      }
      if (num > 0) block.classList.add('profit-block--positive');
      else if (num < 0) block.classList.add('profit-block--negative');
      else block.classList.add('profit-block--zero');
      // BI 色块内是整数金额：小数在 28px 高的色块里只添噪
      block.textContent = `${num > 0 ? '+' : ''}${number(Math.round(num))}`;
      return block;
    }

    function isProfitColumn(column) {
      return Boolean(column && column.format === 'profit');
    }

    // 行 hover 动作浮层（对齐边界 BI 行级操作不占列宽）：商品格 hover 弹出，
    // 详情/跟进/打标走详情工作台（那里已有完整表单），收藏就地切换，
    // 目标/警戒为 BI 式「功能先占位」——后端商品级 API 未建，disabled+说明。
    function attachRowActions(anchor, item) {
      if (!window.TmallUI?.popover) return;
      let popover = null;
      let closeTimer = null;
      const cancelClose = () => { if (closeTimer) { window.clearTimeout(closeTimer); closeTimer = null; } };
      const scheduleClose = () => {
        cancelClose();
        closeTimer = window.setTimeout(() => { popover?.close(); popover = null; }, 260);
      };
      const open = () => {
        cancelClose();
        if (popover?.isOpen()) return;
        const canEdit = !Object.keys(state.capabilities).length || DemoApi.can({ capabilities: state.capabilities }, 'can_edit');
        const panel = document.createElement('div');
        panel.className = 'product-row-actions';
        const actions = [
          ['eye', '详情', () => openProductDetail(item, anchor)],
          ['square-pen', '跟进', () => openProductDetail(item, anchor)],
          ['tag', '打标', () => openProductDetail(item, anchor)],
          ['star', Number(item.starred || 0) === 1 ? '取消收藏' : '收藏', (button) => { popover?.close({ restoreFocus: false }); popover = null; toggleStar(item, button); }, !canEdit],
          ['target', '目标', null],
          ['triangle-alert', '警戒', null],
        ];
        actions.forEach(([icon, label, handler, disabled]) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'product-row-actions__item';
          if (!handler || disabled) {
            button.disabled = true;
            button.title = !handler ? '商品级目标/警戒值 API 规划中' : '当前角色无编辑权限';
          }
          button.innerHTML = `<i data-lucide="${icon}"></i><span>${label}</span>`;
          button.addEventListener('click', () => handler?.(button));
          panel.appendChild(button);
        });
        popover = window.TmallUI.popover({ anchor, content: panel, placement: 'bottom', className: 'product-row-actions-popover' });
        popover.node.addEventListener('mouseenter', cancelClose);
        popover.node.addEventListener('mouseleave', scheduleClose);
        window.lucide?.createIcons();
      };
      anchor.addEventListener('mouseenter', open);
      anchor.addEventListener('mouseleave', scheduleClose);
      anchor.addEventListener('focusin', open);
    }

    function renderHeader() {
      const head = $('[data-products-head]');
      head.replaceChildren();
      const fixed = [
        ['select', ''], ['title', '商品']
      ];
      fixed.forEach(([key, label]) => {
        const th = document.createElement('th');
        th.dataset.fieldKey = key;
        if (key === 'select') {
          const check = document.createElement('input');
          check.type = 'checkbox';
          check.setAttribute('data-products-select-all', '');
          check.setAttribute('aria-label', '选择当前页商品');
          check.addEventListener('change', toggleSelectAll);
          th.appendChild(check);
        } else th.textContent = label;
        head.appendChild(th);
      });
      if (state.displayMode === 'timeline') {
        const period = document.createElement('th');
        period.dataset.fieldKey = 'period';
        period.textContent = state.periodDimension === 'daily' ? '日期' : state.periodDimension === 'weekly' ? '周起始' : '月份';
        head.appendChild(period);
        const trend = document.createElement('th');
        trend.dataset.fieldKey = 'timeline-trend';
        trend.textContent = '环比';
        trend.className = 'num';
        head.appendChild(trend);
      }
      const displayColumns = state.displayMode === 'timeline' ? timelineColumns() : state.visibleColumns;
      displayColumns.forEach((key) => {
        if (state.displayMode === 'timeline' && key === 'trend_change') return;
        const column = columnsByKey.get(key);
        if (!column) return;
        const th = document.createElement('th');
        th.dataset.fieldKey = key;
        th.textContent = column.label;
        if (column.format) th.className = 'num';
        head.appendChild(th);
      });
    }

    function toggleSelectAll(event) {
      visibleRows().forEach((item) => {
        const id = productId(item);
        if (event.currentTarget.checked) state.selected.add(id);
        else state.selected.delete(id);
      });
      renderTable();
    }

    // ===== 汇总行（对齐边界 BI「汇总：全部｜当前页」）=====
    // 「全部」档用后端 summary（按全部筛选条件聚合，不含分页）；
    // 「当前页」档前端对本页行现算。率类指标两侧都是"先聚合再相除"。
    const SUMMARY_SUM_KEYS = ['payment_amount', 'net_sales', 'refund_amount', 'ad_spend', 'operating_profit', 'product_cost', 'buyers', 'visitors', 'payment_count'];
    function summarySums(rows) {
      const sums = {};
      SUMMARY_SUM_KEYS.forEach((key) => { sums[key] = rows.reduce((acc, item) => acc + (Number(item[key]) || 0), 0); });
      return sums;
    }

    function summaryValue(key, scope, pageSums) {
      const src = scope === 'page' ? pageSums : state.summary;
      if (!src) return '--';
      const sum = (name) => Number(src[name]) || 0;
      const ratio = (num, den) => (den > 0 ? num / den : null);
      switch (key) {
        case 'payment_amount': case 'net_sales': case 'refund_amount':
        case 'ad_spend': case 'operating_profit': case 'product_cost':
        case 'buyers': case 'visitors': case 'payment_count': {
          const value = Number(src[key]);
          return Number.isFinite(value) ? value : null;
        }
        case 'refund_rate': return ratio(sum('refund_amount'), sum('payment_amount'));
        case 'expense_ratio': return ratio(sum('ad_spend'), sum('net_sales'));
        case 'profit_rate': return ratio(sum('operating_profit'), sum('net_sales'));
        case 'conversion': return ratio(sum('buyers'), sum('visitors'));
        case 'roi': return ratio(sum('net_sales'), sum('ad_spend'));
        default: return null;
      }
    }

    function renderSummaryCell(cell, key, value) {
      const column = columnsByKey.get(key);
      if (!column || !column.format) { cell.textContent = ''; return; }
      if (isProfitColumn(column)) {
        cell.classList.add('num--profit');
        cell.appendChild(profitBlock(value));
        return;
      }
      if (column.format === 'money') cell.textContent = money(value);
      else if (column.format === 'number') cell.textContent = number(value);
      else if (column.format === 'percent') cell.textContent = percent(value);
      else if (column.format === 'decimal') cell.textContent = decimal(value);
      else cell.textContent = '--';
    }

    function buildSummaryRow(rows) {
      const row = document.createElement('tr');
      row.className = 'ui-summary-row';
      const pageSums = summarySums(rows);
      const labelCell = row.insertCell();
      labelCell.colSpan = 2;
      labelCell.className = 'ui-summary-row__label';
      const label = document.createElement('span');
      label.textContent = '汇总：';
      labelCell.appendChild(label);
      [['all', '全部'], ['page', '当前页']].forEach(([scope, text]) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'ui-summary-row__scope';
        button.textContent = text;
        button.setAttribute('aria-pressed', String(state.summaryScope === scope));
        button.addEventListener('click', () => {
          state.summaryScope = scope;
          const body = $('[data-products-body]');
          const current = body?.querySelector('.ui-summary-row');
          if (current) current.replaceWith(buildSummaryRow(visibleRows()));
        });
        labelCell.appendChild(button);
      });
      state.visibleColumns.forEach((key) => {
        const cell = row.insertCell();
        cell.dataset.fieldKey = key;
        if (columnsByKey.get(key)?.format) cell.classList.add('num');
        renderSummaryCell(cell, key, summaryValue(key, state.summaryScope, pageSums));
      });
      return row;
    }

    function updateTimelineControls() {
      document.body.dataset.productsDisplayMode = state.displayMode;
      const tools = $('[data-products-timeline-tools]');
      const fieldControls = document.querySelector('.product-control-group--fields');
      const columnsButton = $('[data-products-columns-open]');
      if (!tools) return;
      tools.hidden = state.displayMode !== 'timeline';
      if (fieldControls) fieldControls.hidden = state.displayMode === 'timeline';
      // Column settings apply to both list and timeline metrics.
      if (columnsButton) columnsButton.hidden = false;
      document.querySelectorAll('[data-products-timeline-limit]').forEach((button) => {
        button.setAttribute('aria-pressed', String(Number(button.dataset.productsTimelineLimit) === state.timelineLimit));
      });
    }

    function renderTable() {
      updateTimelineControls();
      if (state.displayMode === 'timeline') return renderTimelineTable();
      renderHeader();
      const body = $('[data-products-body]');
      body.replaceChildren();
      const rows = visibleRows();
      const metricMax = {};
      state.visibleColumns.forEach((key) => {
        const column = columnsByKey.get(key);
        if (column?.format && !isProfitColumn(column)) metricMax[key] = Math.max(...rows.map((item) => metricBarValue(item, key)), 0);
      });
      updateKpis(rows);
      if (!rows.length) {
        setRowStatus(state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品');
        renderMobileSummary(rows);
        applyFieldView();
        updatePagination();
        updateSelection();
        return;
      }
      body.appendChild(buildSummaryRow(rows));
      rows.forEach((item) => {
        const id = productId(item);
        const row = document.createElement('tr');
        row.dataset.productId = id;

        const check = document.createElement('input');
        check.type = 'checkbox';
        check.value = id;
        check.checked = state.selected.has(id);
        check.setAttribute('aria-label', `选择商品 ${id}`);
        check.addEventListener('change', () => {
          if (check.checked) state.selected.add(id);
          else state.selected.delete(id);
          updateSelection();
        });
        addCell(row, check, '', 'select');

        const star = document.createElement('button');
        star.type = 'button';
        star.className = 'star-button';
        star.dataset.capabilityKey = 'products.catalog_edit';
        star.disabled = Object.keys(state.capabilities).length > 0 && !DemoApi.can({ capabilities: state.capabilities }, 'can_edit');
        star.classList.toggle('is-active', Number(item.starred || 0) === 1);
        star.innerHTML = '<i data-lucide="star"></i>';
        star.setAttribute('aria-label', Number(item.starred || 0) === 1 ? '取消收藏' : '收藏');
        star.setAttribute('aria-pressed', String(Number(item.starred || 0) === 1));
        star.addEventListener('click', async () => toggleStar(item, star));
        const identity = TmallUI.productIdentity({
          title: item.title, id, imageUrl: item.image_url,
          maxTitleChars: 8, titleClassName: 'product-title__link',
          onTitleClick: (event) => openProductDetail(item, event.currentTarget),
          metaItems: [star],
        });
        attachRowActions(identity, item);
        addCell(row, identity, '', 'title');

       state.visibleColumns.forEach((key) => {
        const column = columnsByKey.get(key);
        if (!column) return;
         if (key === 'tier' || key === 'style') {
           const classificationCell = addCell(row, editableSelect(item, key), '', key);
           classificationCell.dataset.sortValue = DemoLabels.clean(item[key], '');
         }
        else if (key === 'product_type') addCell(row, badge(item.product_type || '待复核', item.product_type || '待复核'), '', key);
         else if (key === 'product_growth_stage') addCell(row, item.product_growth_stage || '--', '', key);
         else if (key === 'product_time_node') addCell(row, item.product_time_node || '--', '', key);
         else if (key === 'status') addCell(row, badge(DemoLabels.label('status', item.status, item.status), '未知'), '', key);
        else if (key === 'lifecycle_stage') addCell(row, DemoLabels.classification('lifecycle_stages', item.lifecycle_stage, item.lifecycle_stage || '--'), '', key);
        else if (key === 'seasonality') addCell(row, DemoLabels.classification('seasonal_attributes', item.seasonality, item.seasonality || '--'), '', key);
        else if (key === 'has_pending_action') addCell(row, badge(item.has_pending_action ? '有待办' : '无待办', '无待办'), '', key);
        else {
          const cell = addCell(row, formatColumnValue(item, column), column.format ? (isProfitColumn(column) ? 'num num--profit' : 'num metric-bar-cell') : '', key);
          if (column.format && !isProfitColumn(column) && metricMax[key] > 0) {
            cell.style.setProperty('--metric-fill', `${Math.round((metricBarValue(item, key) / metricMax[key]) * 100)}%`);
          }
        }
      });

        body.appendChild(row);
      });
      renderMobileSummary(rows);
      applyFieldView();
      updatePagination();
      updateSelection();
      window.lucide?.createIcons();
    }

    function timelineColumns() {
      const monthlyUnsupported = new Set(['paid_ipv', 'organic_ipv', 'search_ipv', 'recommend_ipv']);
      const selectedMetrics = state.visibleColumns.filter((key) => {
        const column = columnsByKey.get(key);
        return key !== 'trend_change'
          && Boolean(column?.format)
          && !(state.periodDimension === 'monthly' && monthlyUnsupported.has(key));
      });
      const fallback = ['payment_amount', 'net_sales', 'operating_profit', 'visitors', 'conversion', 'refund_rate', 'expense_ratio', 'ad_spend', 'roi', 'buyers', 'avg_order_value', 'repurchase_rate'];
      return [...new Set(selectedMetrics.length ? selectedMetrics : fallback)].filter((key) => columnsByKey.has(key));
    }

    function renderTimelineProductCells(row, item, rowSpan) {
      const id = productId(item);
      const check = document.createElement('input');
      check.type = 'checkbox';
      check.value = id;
      check.checked = state.selected.has(id);
      check.setAttribute('aria-label', `选择商品 ${id}`);
      check.addEventListener('change', () => {
        if (check.checked) state.selected.add(id);
        else state.selected.delete(id);
        updateSelection();
      });
      const selectCell = addCell(row, check, '', 'select');
      if (rowSpan > 1) selectCell.rowSpan = rowSpan;

      const star = document.createElement('button');
      star.type = 'button';
      star.className = 'star-button';
      star.dataset.capabilityKey = 'products.catalog_edit';
      star.disabled = Object.keys(state.capabilities).length > 0 && !DemoApi.can({ capabilities: state.capabilities }, 'can_edit');
      star.classList.toggle('is-active', Number(item.starred || 0) === 1);
      star.innerHTML = '<i data-lucide="star"></i>';
      star.setAttribute('aria-label', Number(item.starred || 0) === 1 ? '取消收藏' : '收藏');
      star.setAttribute('aria-pressed', String(Number(item.starred || 0) === 1));
      star.addEventListener('click', async () => toggleStar(item, star));
      const identity = TmallUI.productIdentity({
        title: item.title, id, imageUrl: item.image_url,
        maxTitleChars: 8, titleClassName: 'product-title__link',
        onTitleClick: (event) => openProductDetail(item, event.currentTarget),
        metaItems: [star],
      });
      const titleCell = addCell(row, identity, '', 'title');
      if (rowSpan > 1) titleCell.rowSpan = rowSpan;
    }

    function appendTimelineMetrics(row, item, detail, metricMax) {
      addCell(row, detail.period || '--', 'product-timeline-period', 'period');
      const trendCell = addCell(row, '', 'num product-timeline-trend', 'timeline-trend');
      const trend = detail.trend_change;
      if (trend == null || !Number.isFinite(Number(trend))) {
        trendCell.textContent = '--';
      } else {
        const value = Number(trend);
        const tone = value > 0 ? 'up' : value < 0 ? 'down' : 'flat';
        trendCell.classList.add(`product-timeline-trend--${tone}`);
        trendCell.innerHTML = `<i data-lucide="${tone === 'up' ? 'trending-up' : tone === 'down' ? 'trending-down' : 'minus'}"></i><span>${percent(value)}</span>`;
      }
      timelineColumns().forEach((key) => {
        const column = columnsByKey.get(key);
        if (!column || key === 'trend_change') return;
        const valueItem = { ...item, ...detail };
        const cell = addCell(row, formatColumnValue(valueItem, column), column.format ? (isProfitColumn(column) ? 'num num--profit' : 'num metric-bar-cell') : '', key);
        if (column.format && !isProfitColumn(column) && metricMax[key] > 0) {
          cell.style.setProperty('--metric-fill', `${Math.round((metricBarValue(valueItem, key) / metricMax[key]) * 100)}%`);
        }
      });
    }

    function renderTimelineTable() {
      renderHeader();
      const body = $('[data-products-body]');
      body.replaceChildren();
      const rows = visibleRows();
      const columns = timelineColumns();
      updateTimelineControls();
      updateKpis(rows);
      if (!rows.length) {
        setRowStatus(state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品');
        renderMobileSummary(rows);
        applyFieldView();
        updatePagination();
        updateSelection();
        return;
      }
      const metricMax = {};
      columns.forEach((key) => {
        const column = columnsByKey.get(key);
        if (column?.format) {
          metricMax[key] = Math.max(...rows.flatMap((item) => state.timelineRows.get(productId(item)) || []).map((item) => metricBarValue(item, key)), 0);
        }
      });
      rows.forEach((item) => {
        const id = productId(item);
        const details = state.timelineRows.get(id) || [];
        const periods = details.length ? details : [{ product_id: id, period: '--' }];
        periods.forEach((detail, index) => {
          const row = document.createElement('tr');
          row.className = `product-timeline-row ${index === 0 ? 'product-timeline-row--first' : 'product-timeline-row--continuation'}`;
          row.dataset.productId = id;
          if (index === 0) renderTimelineProductCells(row, item, periods.length);
          appendTimelineMetrics(row, item, detail, metricMax);
          body.appendChild(row);
        });
      });
      renderMobileSummary(rows);
      applyFieldView();
      updatePagination();
      updateSelection();
      window.lucide?.createIcons();
    }

    async function loadTimelineRows(renderAfter = true) {
      const token = ++state.timelineToken;
      const ids = visibleRows().map(productId).filter(Boolean);
      state.timelineRows = new Map();
      if (!ids.length) return;
      const range = currentRange();
      const params = new URLSearchParams({
        dim: state.periodDimension,
        product_ids: ids.join(','),
        limit_periods: String(state.timelineLimit),
      });
      if (state.periodDimension !== 'monthly' && range.startDate) params.set('start', range.startDate);
      if (range.endDate) params.set('end', range.endDate);
      try {
        const response = await DemoApi.domainRequest(`/api/products/timeline?${params.toString()}`);
        if (token !== state.timelineToken) return;
        const grouped = new Map();
        asArray(response.data, 'rows').forEach((row) => {
          if (!grouped.has(String(row.product_id))) grouped.set(String(row.product_id), []);
          grouped.get(String(row.product_id)).push(row);
        });
        const maxPeriods = state.timelineLimit;
        grouped.forEach((items, id) => grouped.set(id, items.slice(0, maxPeriods)));
        state.timelineRows = grouped;
        if (renderAfter) renderTable();
      } catch (error) {
        if (token !== state.timelineToken) return;
        setStatus(error.message || '周期明细加载失败');
        if (renderAfter) renderTable();
      }
    }

    function updatePagination() {
      const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
      $('[data-products-page-size]').value = String(state.pageSize);
      $('[data-products-page-summary]').textContent = `第 ${state.page} / ${totalPages} 页，共 ${number(state.total)} 件；每页 ${state.pageSize} 件${state.starredOnly ? '；当前页收藏过滤' : ''}`;
      $('[data-products-prev]').disabled = state.page <= 1;
      $('[data-products-next]').disabled = state.page >= totalPages;
    }

    function updateSelection() {
      const visibleIds = visibleRows().map(productId);
      const selectedVisible = visibleIds.filter((id) => state.selected.has(id));
      const all = $('[data-products-select-all]');
      all.checked = visibleIds.length > 0 && selectedVisible.length === visibleIds.length;
      all.indeterminate = selectedVisible.length > 0 && selectedVisible.length < visibleIds.length;
      $('[data-products-selected]').textContent = `已选 ${state.selected.size} 件`;
      $('[data-products-batch]').classList.toggle('is-active', state.selected.size > 0);
      const copyButton = $('[data-products-batch-copy]');
      if (copyButton) copyButton.disabled = state.selected.size === 0 || state.copyingIds;
    }

    function renderMobileSummary(rows) {
      const root = $('[data-products-mobile-summary]');
      if (!root) return;
      root.hidden = false;
      root.replaceChildren();
      if (!rows.length) {
        const empty = document.createElement('p');
        empty.className = 'panel__hint';
        empty.textContent = state.starredOnly ? '当前页没有收藏商品' : '当前条件暂无商品';
        root.appendChild(empty);
        return;
      }
      rows.forEach((item) => {
        const id = productId(item);
        const card = document.createElement('article');
        card.className = 'products-mobile-summary__item';
        const header = document.createElement('div');
        header.className = 'products-mobile-summary__header';
        const identity = document.createElement('div');
        identity.className = 'products-mobile-summary__identity';
        const title = document.createElement('strong');
        title.textContent = item.title || '未命名商品';
        const code = document.createElement('span');
        code.textContent = id || '--';
        identity.append(title, code);
        const detail = document.createElement('button');
        detail.type = 'button';
        detail.className = 'ui-button ui-button--ghost';
        detail.textContent = '详情';
        detail.addEventListener('click', () => openProductDetail(item, detail));
        header.append(identity, detail);
        const metrics = document.createElement('dl');
        metrics.className = 'products-mobile-summary__metrics';
        [['payment_amount', '支付金额', money(item.payment_amount)], ['net_sales', '净销售额', money(item.net_sales)], ['roi', '推广 ROI', decimal(item.roi)], ['has_pending_action', '待办', item.has_pending_action ? '有待办' : '无待办']].forEach(([key, label, value]) => {
          const term = document.createElement('dt');
          term.textContent = label;
          term.dataset.fieldKey = key;
          const valueNode = document.createElement('dd');
          valueNode.textContent = value;
          metrics.append(term, valueNode);
        });
        card.append(header, metrics);
        root.appendChild(card);
      });
    }

    function applyFieldView() {
      const view = state.view;
      document.querySelectorAll('[data-products-view]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.productsView === view));
      });
      renderHeader();
    }

    return Object.freeze({
      renderTable,
      renderHeader,
      renderTimelineTable,
      loadTimelineRows,
      updateTimelineControls,
      applyFieldView,
      updatePagination,
      updateSelection,
      renderMobileSummary,
      toggleSelectAll,
      setRowStatus,
      visibleRows,
      updateKpis,
    });
  }

  global.TmallProducts = global.TmallProducts || {};
  global.TmallProducts.createTableRender = createTableRender;
})(window);
