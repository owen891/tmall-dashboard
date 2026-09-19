(function () {
  const id = decodeURIComponent(location.pathname.split('/').pop());
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const setText = (selector, value) => $$(selector).forEach((node) => { node.textContent = value ?? '--'; });
  const money = (value) => value == null ? '--' : `¥${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
  const percent = (value) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`;
  const pct = (value) => value == null ? '--' : `${Number(value).toFixed(1)}%`;
  const actionStatusLabels = { draft: '草稿', pending_execution: '待执行', executing: '执行中', observing: '观察中', pending_review: '待复盘', blocked: '阻塞', calculation_failed: '计算失败', completed: '已完成', cancelled: '已取消' };
  const actionStatus = (value) => actionStatusLabels[value] || value || '--';
  const mutationError = (error, fallback = '操作失败，请重试') => {
    const status = $('[data-product-detail-action-status]') || $('[data-product-detail-status]');
    if (status) status.textContent = error?.message || fallback;
  };
  const detailMetricKeys = new Set(['payment_qty', 'search_visitors', 'paid_ipv', 'organic_ipv', 'presale_amount', 'presale_qty', 'data_source']);
  const row = (label, value) => { const node = document.createElement('div'); node.className = 'status-list__item'; const left = document.createElement('span'); left.className = 'status-list__label'; left.textContent = label; const right = document.createElement('span'); right.className = 'status-list__value'; right.textContent = value ?? '--'; node.append(left, right); return node; };
  const transitions = { draft: ['pending_execution', 'cancelled'], pending_execution: ['executing', 'blocked', 'cancelled'], executing: ['observing', 'blocked', 'cancelled'], observing: ['pending_review', 'blocked', 'calculation_failed'], pending_review: ['blocked'], blocked: ['pending_execution', 'cancelled'], calculation_failed: ['observing', 'blocked'], completed: ['pending_review'] };
  let detailPayload = null;
  let selectedRange = {};
  const detailTabs = new Set(['overview', 'trend', 'flow-source', 'lifecycle', 'actions', 'evidence']);

  // 单品流量来源树形展开状态
  const itemFlowExpanded = new Set();

  function selectDetailTab(tab, { updateHash = true, focus = false } = {}) {
    const active = detailTabs.has(tab) ? tab : 'overview';
    $$('[data-product-detail-tab]').forEach((button) => {
      const selected = button.dataset.productDetailTab === active;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
      if (selected && focus) button.focus();
    });
    $$('[data-product-detail-panel]').forEach((panel) => {
      panel.hidden = panel.dataset.productDetailPanel !== active;
    });
    if (updateHash) history.replaceState(null, '', `${location.pathname}${location.search}#${active}`);
  }

  function bindWorkbenchNavigation() {
    $$('[data-product-detail-tab]').forEach((button) => {
      button.addEventListener('click', () => selectDetailTab(button.dataset.productDetailTab));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        const tabs = $$('[data-product-detail-tab]');
        const index = tabs.indexOf(button);
        const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault();
        selectDetailTab(tabs[nextIndex].dataset.productDetailTab, { focus: true });
      });
    });
    const back = $('[data-product-detail-back]');
    const referrer = document.referrer;
    let cameFromProducts = false;
    try { cameFromProducts = referrer && new URL(referrer).origin === window.location.origin && new URL(referrer).pathname === '/products'; } catch (_) { cameFromProducts = false; }
    back?.addEventListener('click', (event) => {
      if (!cameFromProducts) return;
      event.preventDefault();
      window.history.back();
    });
    selectDetailTab(location.hash.slice(1), { updateHash: false });
    window.addEventListener('hashchange', () => selectDetailTab(location.hash.slice(1), { updateHash: false }));
  }
  const requestAction = (action, suffix, body) => DemoApi.domainRequest(`/api/actions/${encodeURIComponent(action.id)}${suffix}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  function actionCard(action) {
    const card = document.createElement('div'); card.className = 'status-list__item';
    const content = document.createElement('div'); content.className = 'status-list__value';
    const title = document.createElement('strong'); title.textContent = `${action.planned_at || '--'} · ${action.action_type || '--'} · ${actionStatus(action.status)}`;
    const detail = document.createElement('div'); detail.textContent = `目的：${action.purpose_note || '--'}；动作：${action.action_detail || '--'}；结果：${action.calculation_note || '--'}；复盘：${action.review_conclusion || '--'}；历史：${(action.history || []).length} 条`;
    content.append(title, detail);
    const controls = document.createElement('div'); controls.className = 'button-row';
    (transitions[action.status] || []).forEach((target) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.textContent = `转为${actionStatus(target)}`;
      button.addEventListener('click', async () => {
        const body = { capability_key: 'product-detail.review_action', status: target, version: action.version };
        if (target === 'blocked') { body.blocked_reason = window.prompt('请输入阻塞原因') || ''; body.expected_recovery_at = window.prompt('请输入预计恢复日期（YYYY-MM-DD）') || ''; if (!body.blocked_reason || !body.expected_recovery_at) return; }
        button.disabled = true;
        try { await requestAction(action, '/transition', body); await load(); } catch (error) { mutationError(error, '更新运营动作状态失败，请重试'); } finally { if (button.isConnected) button.disabled = false; }
      }); controls.appendChild(button);
    });
    if (action.status === 'observing') {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'ui-button ui-button--ghost'; button.textContent = '重新计算观察窗口';
      button.addEventListener('click', async () => { button.disabled = true; try { await DemoApi.domainRequest('/api/actions/recalculate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capability_key: 'product-detail.review_action' }) }); await load(); } catch (error) { mutationError(error, '重新计算观察窗口失败，请重试'); } finally { if (button.isConnected) button.disabled = false; } }); controls.appendChild(button);
    }
    if (action.status === 'pending_review') {
      const form = document.createElement('form'); form.className = 'modal-form__body';
      form.innerHTML = '<label>是否有效<select class="select" name="effective" aria-label="复盘结论是否有效"><option value="true">有效</option><option value="false">无效</option></select></label><label>变更原因<input class="input" name="reason" required></label><label>复盘结论<input class="input" name="conclusion" required></label><label>后续动作<input class="input" name="next_action" required></label><label>复盘人<input class="input" name="reviewer" value="运营人员" required></label><button class="ui-button ui-button--primary" type="submit">提交复盘</button>';
      form.addEventListener('submit', async (event) => { event.preventDefault(); const values = Object.fromEntries(new FormData(form)); const submit = form.querySelector('button[type="submit"]'); if (submit) submit.disabled = true; try { await requestAction(action, '/review', { ...values, capability_key: 'product-detail.review_action', effective: values.effective === 'true', version: action.version }); await load(); } catch (error) { mutationError(error, '提交复盘失败，请重试'); } finally { if (submit?.isConnected) submit.disabled = false; } }); content.appendChild(form);
    }
    card.append(content, controls); return card;
  }
  function renderHistory(rows) { const target = $('[data-product-detail-lifecycle-history]'); if (!target) return; target.replaceChildren(...(rows || []).map((item) => { const tr = document.createElement('tr'); [item.created_at, item.recommended_stage, item.manual_stage, item.reason, item.operator, item.version].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value == null || value === '' ? '--' : String(value); if (index === 5) td.className = 'num'; tr.appendChild(td); }); return tr; })); if (!rows?.length) target.innerHTML = '<tr><td colspan="6">暂无生命周期历史</td></tr>'; }
  function renderComparison(rows, contributions) { const target = $('[data-product-detail-period-comparison]'); if (target) { target.replaceChildren(...(rows || []).map((item) => { const tr = document.createElement('tr'); const metrics = item.metrics || {}; [item.month, metrics.net_sales?.current, pct(metrics.net_sales?.change_pct), pct(metrics.product_visitors?.change_pct), item.anomalies?.join('、') || '无明显变化'].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value == null ? '--' : (index === 1 ? money(value) : String(value)); if (index > 0 && index < 4) td.className = 'num'; tr.appendChild(td); }); return tr; })); if (!rows?.length) target.innerHTML = '<tr><td colspan="5">暂无周期对比数据</td></tr>'; } const summary = $('[data-product-detail-contribution]'); if (summary) { const latest = (contributions || []).at(-1); summary.replaceChildren(latest ? row('贡献分析（非因果）', latest.drivers.map((driver) => `${driver.metric}: ${driver.delta == null ? '--' : Number(driver.delta).toFixed(2)}`).join('、')) : row('贡献分析', '暂无可比较周期')); } }
  function renderEvidence(summary) { const target = $('[data-product-detail-evidence]'); if (!target) return; const coverage = summary?.coverage || {}; target.replaceChildren(row('证据等级', summary?.level || '--'), row('覆盖范围', `${coverage.start || '--'} 至 ${coverage.end || '--'}（${coverage.days || 0} 天）`), row('数据来源', (summary?.sources || []).map((source) => `${source.source}: ${source.row_count}`).join('、') || '--'), row('缺失字段', (summary?.missing_fields || []).join('、') || '无'), row('限制说明', (summary?.unknowns || []).join('、') || '暂不支持严格因果归因')); }
  function formatDetailMetric(metric) {
    if (metric?.value == null || metric.value === '') return '--';
    if (metric.unit === 'currency') return money(metric.value);
    if (metric.unit === 'ratio') return percent(metric.value);
    if (metric.unit === 'number') return Number(metric.value).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
    return String(metric.value);
  }
  function renderDetailMetrics(metrics) {
    const target = $('[data-product-detail-detail-metrics]');
    if (!target) return;
    target.replaceChildren(...(metrics || []).filter((metric) => metric?.key && (detailMetricKeys.has(metric.key) || metric.value !== undefined)).map((metric) => {
      const card = document.createElement('article');
      card.className = `product-detail-metric${metric.value == null ? ' is-missing' : ''}`;
      const label = document.createElement('span'); label.className = 'product-detail-metric__label'; label.textContent = metric.label || metric.key;
      const value = document.createElement('strong'); value.className = 'product-detail-metric__value'; value.textContent = formatDetailMetric(metric);
      const source = document.createElement('small'); source.className = 'product-detail-metric__source'; source.textContent = metric.value == null ? '字段缺失' : '当前日期范围';
      card.append(label, value, source); return card;
    }));
  }

  // 加载单品流量来源数据（树形折叠展开）
  async function loadItemFlowSource(itemId) {
    try {
      const r = await fetch(`/api/sycm/item-flow/summary?item_id=${encodeURIComponent(itemId)}`);
      const d = await r.json();
      if (!d.ok) {
        const tbody = document.querySelector('[data-item-flow-table]');
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--text-tertiary);padding:24px">${d.message || '暂无流量来源数据'}</td></tr>`;
        return;
      }
      const data = d.data;
      const channels = data.channels || [];
      const totalUv = data.total_uv || 0;
      const totalPay = data.total_pay_amount || 0;

      // 构建树形结构：level=0 → level=1 → level=2
      const level0 = channels.filter(ch => ch.level === 0);
      const childrenMap = {};
      channels.forEach(ch => {
        const parent = ch.parent_channel || '';
        if (parent && ch.level > 0) {
          if (!childrenMap[parent]) childrenMap[parent] = [];
          childrenMap[parent].push(ch);
        }
      });

      function buildTree(node, level) {
        const treeNode = { ...node, level: level, children: [] };
        const children = childrenMap[node.channel_name] || [];
        children.forEach(child => {
          treeNode.children.push(buildTree(child, level + 1));
        });
        treeNode.children.sort((a, b) => (b.uv || 0) - (a.uv || 0));
        return treeNode;
      }

      const tree = level0.map(ch => buildTree(ch, 1));
      tree.sort((a, b) => (b.uv || 0) - (a.uv || 0));
      tree.forEach(node => itemFlowExpanded.add(node.channel_name));

      // 统计
      let totalBuyers = 0;
      let channelCount = 0;
      function countChannels(nodes) {
        nodes.forEach(node => {
          channelCount++;
          totalBuyers += node.pay_buyer_count || 0;
          if (node.children.length) countChannels(node.children);
        });
      }
      countChannels(tree);

      const setText2 = (sel, val) => { const el = document.querySelector(sel); if (el) el.textContent = val; };
      setText2('[data-item-flow-date]', data.stat_date || '--');
      setText2('[data-item-flow-total-uv]', totalUv.toLocaleString('zh-CN'));
      setText2('[data-item-flow-total-pay]', '¥' + (totalPay >= 10000 ? (totalPay/10000).toFixed(1) + '万' : totalPay.toFixed(0)));
      setText2('[data-item-flow-total-buyers]', totalBuyers.toLocaleString('zh-CN'));
      setText2('[data-item-flow-channel-count]', channelCount);

      const tbody = document.querySelector('[data-item-flow-table]');
      if (!tbody) return;
      if (!tree.length) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无流量来源数据</td></tr>';
        return;
      }

      // 渲染树形表格
      function renderNode(node) {
        const isExpanded = itemFlowExpanded.has(node.channel_name);
        const hasChildren = node.children.length > 0;
        const indent = (node.level - 1) * 20;

        const toggleBtn = hasChildren
          ? `<span class="toggle-btn" data-item-flow-toggle="${node.channel_name}">${isExpanded ? '−' : '+'}</span>`
          : `<span class="toggle-btn toggle-btn--empty">·</span>`;

        const uvPct = totalUv > 0 ? (node.uv / totalUv * 100).toFixed(1) + '%' : '--';
        const rate = node.pay_rate != null ? (node.pay_rate * 100).toFixed(2) + '%' : '--';
        const uvValue = node.uv > 0 && node.pay_amount != null ? '¥' + (node.pay_amount / node.uv).toFixed(2) : '--';

        let html = `<tr class="level-${node.level}">
          <td>
            <div class="channel-cell" style="padding-left:${indent}px">
              ${toggleBtn}
              <span class="channel-name ${hasChildren ? 'channel-name--clickable' : ''}" data-item-flow-channel="${node.channel_name}">${node.channel_name}</span>
            </div>
          </td>
          <td class="num">${(node.uv || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${uvPct}</td>
          <td class="num">¥${node.pay_amount != null ? (node.pay_amount >= 10000 ? (node.pay_amount/10000).toFixed(1) + '万' : node.pay_amount.toFixed(0)) : '--'}</td>
          <td class="num">${(node.pay_buyer_count || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${rate}</td>
          <td class="num">${uvValue}</td>
          <td class="num">${(node.cart_buyer_count || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${node.uv > 0 && node.cart_buyer_count != null ? (node.cart_buyer_count / node.uv * 100).toFixed(2) + '%' : '--'}</td>
          <td class="num">${(node.collect_item_count || 0).toLocaleString('zh-CN')}</td>
          <td class="num">${(node.new_uv || 0).toLocaleString('zh-CN')}</td>
        </tr>`;

        if (isExpanded && hasChildren) {
          node.children.forEach(child => {
            html += renderNode(child);
          });
        }
        return html;
      }

      function renderTable() {
        let html = '';
        tree.forEach(node => { html += renderNode(node); });
        tbody.innerHTML = html;
        bindEvents();
      }

      function bindEvents() {
        tbody.querySelectorAll('[data-item-flow-toggle]').forEach(el => {
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            const name = el.dataset.itemFlowToggle;
            if (itemFlowExpanded.has(name)) {
              itemFlowExpanded.delete(name);
            } else {
              itemFlowExpanded.add(name);
            }
            renderTable();
          });
        });
        tbody.querySelectorAll('.channel-name--clickable').forEach(el => {
          el.addEventListener('click', () => {
            const name = el.dataset.itemFlowChannel;
            if (itemFlowExpanded.has(name)) {
              itemFlowExpanded.delete(name);
            } else {
              itemFlowExpanded.add(name);
            }
            renderTable();
          });
        });
      }

      renderTable();

      // 渲染图表（用一级渠道）
      if (window.echarts && tree.length) {
        // 饼图
        const pieEl = document.getElementById('itemFlowPieChart');
        if (pieEl) {
          const pieChart = echarts.init(pieEl);
          const pieData = tree.slice(0, 8).map(ch => ({ name: ch.channel_name, value: ch.uv || 0 }));
          if (tree.length > 8) {
            const otherUv = tree.slice(8).reduce((s, ch) => s + (ch.uv || 0), 0);
            pieData.push({ name: '其他', value: otherUv });
          }
          pieChart.setOption({
            tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
            legend: { bottom: 0, textStyle: { fontSize: 10 } },
            series: [{
              type: 'pie',
              radius: ['35%', '65%'],
              center: ['50%', '42%'],
              itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
              label: { show: false },
              emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } },
              data: pieData,
            }],
            color: ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#94a3b8'],
          });
        }

        // 柱状图
        const barEl = document.getElementById('itemFlowBarChart');
        if (barEl) {
          const barChart = echarts.init(barEl);
          const top10 = [...tree].sort((a, b) => (b.pay_amount || 0) - (a.pay_amount || 0)).slice(0, 10);
          const names = top10.map(ch => ch.channel_name.length > 5 ? ch.channel_name.slice(0, 5) + '...' : ch.channel_name);
          const barData = top10.map(ch => ch.pay_amount || 0);
          barChart.setOption({
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
            xAxis: { type: 'category', data: names, axisLabel: { fontSize: 9, rotate: 30 } },
            yAxis: { type: 'value', axisLabel: { formatter: function(v) { return v >= 10000 ? (v/10000).toFixed(0) + '万' : v; } } },
            series: [{
              type: 'bar',
              data: barData,
              itemStyle: { color: '#22c55e', borderRadius: [3, 3, 0, 0] },
              barWidth: '50%',
            }],
          });
        }
      }
    } catch (err) {
      console.error('加载单品流量来源失败:', err);
    }
  }

  async function load(range) {
    try {
      selectedRange = range || window.TmallDateRange?.getState?.() || selectedRange || {};
      const query = new URLSearchParams(); if (selectedRange.startDate) query.set('start', selectedRange.startDate); if (selectedRange.endDate) query.set('end', selectedRange.endDate);
      const payload = await DemoApi.domainRequest(`/api/products/${encodeURIComponent(id)}/detail${query.toString() ? `?${query}` : ''}`); detailPayload = payload; const data = payload.data;
      setText('[data-product-detail-title]', data.product.title || id);
      // 设置商品主图
      const productImg = document.querySelector('[data-product-detail-image]');
      if (productImg && data.product.image_url) {
        productImg.src = data.product.image_url;
        productImg.style.display = 'block';
      }
      setText('[data-product-detail-meta]', `商品 ${id} · 数据截止 ${data.summary.data_cutoff_date || '--'}`);
      setText('[data-product-detail-breadcrumb]', `商品经营 / 商品列表 / ${data.product.title || id}`);
      $('[data-product-detail-meta]').textContent = `商品 ${id} · 数据截止 ${data.summary.data_cutoff_date || '--'}`;
      $('[data-product-detail-status]').textContent = `${DemoLabels.label('status', data.product.status, data.product.status || '--')} · ${data.product.manager || '未分配'}`;
      if (payload.availability === 'no-data') $('[data-product-detail-status]').textContent = '当前日期范围无商品日度数据 · 请调整日期范围或检查导入';
      $('[data-product-detail-info]').replaceChildren(row('分层 / 风格', `${DemoLabels.classification('tiers', data.product.tier, '--')} / ${DemoLabels.classification('styles', data.product.style, '--')}`), row('类目 / 场景', `${DemoLabels.clean(data.product.category, '--')} / ${DemoLabels.clean(data.product.scene, '--')}`), row('上架日期', DemoLabels.clean(data.product.list_date, '--')), row('商品负责人', DemoLabels.clean(data.product.manager, '--')), row('商品状态', DemoLabels.label('status', data.product.status, '--')), row('数据来源', data.summary.data_source || '--'), row('最后导入', data.summary.imported_at || '--'), row('数据截止', data.summary.data_cutoff_date || '--'));
      renderDetailMetrics(data.detail_metrics);
      [['payment_amount', money], ['net_sales', money], ['payment_conversion_rate', percent], ['expense_ratio', percent], ['average_order_value', money]].forEach(([key, format]) => { setText(`[data-product-detail-kpi="${key}"]`, format(data.summary[key])); });
      setText('[data-product-detail-stage]', data.lifecycle?.stage_label || data.lifecycle?.stage || '--');
      setText('[data-product-detail-days]', data.lifecycle?.continuous_valid_days ?? '--');
      setText('[data-product-detail-confidence]', `置信度：${DemoLabels.label('confidence', data.lifecycle?.confidence)} · ${data.lifecycle?.locked ? '人工' : '系统'}`);
      setText('[data-product-detail-rationale]', data.lifecycle?.rationale || '暂无判断依据');
      const workbenchExportQuery = new URLSearchParams({ capability_key: 'product-detail.export' });
      if (selectedRange.startDate) workbenchExportQuery.set('start', selectedRange.startDate);
      if (selectedRange.endDate) workbenchExportQuery.set('end', selectedRange.endDate);
      $$('[data-product-detail-export]').forEach((link) => { link.href = `/api/products/${encodeURIComponent(id)}/detail/export?${workbenchExportQuery}`; });
      $('[data-product-detail-stage]').textContent = data.lifecycle?.stage_label || data.lifecycle?.stage || '--'; $('[data-product-detail-days]').textContent = data.lifecycle?.continuous_valid_days ?? '--'; $('[data-product-detail-confidence]').textContent = `置信度：${DemoLabels.label('confidence', data.lifecycle?.confidence)} · ${data.lifecycle?.locked ? '人工' : '系统'}`; $('[data-product-detail-rationale]').textContent = data.lifecycle?.rationale || '暂无判断依据';
      const trendRows = Array.isArray(data.daily_trend) ? data.daily_trend : [];
      const trend = $('[data-product-detail-trend]');
      trend.replaceChildren(...trendRows.map((item) => { const tr = document.createElement('tr'); [item.date, money(item.payment_amount), money(item.net_sales), item.product_visitors ?? '--', money(item.ad_spend)].forEach((value, index) => { const td = document.createElement('td'); td.textContent = value; if (index) td.className = 'num'; tr.appendChild(td); }); return tr; })); if (!trendRows.length) trend.innerHTML = '<tr><td colspan="5">暂无日度数据</td></tr>';
      const actions = $('[data-product-detail-actions]'); const actionRows = Array.isArray(data.actions) ? data.actions : []; actions.replaceChildren(...actionRows.map(actionCard)); if (!actionRows.length) actions.textContent = '暂无运营动作'; renderHistory(data.lifecycle_history); renderComparison(data.period_comparison, data.contribution_analysis); renderEvidence(data.evidence_summary);
      const exportLink = $('[data-product-detail-export]'); if (exportLink) { const exportQuery = new URLSearchParams({ capability_key: 'product-detail.export' }); if (selectedRange.startDate) exportQuery.set('start', selectedRange.startDate); if (selectedRange.endDate) exportQuery.set('end', selectedRange.endDate); exportLink.href = `/api/products/${encodeURIComponent(id)}/detail/export?${exportQuery}`; }
      loadItemFlowSource(id);
    } catch (error) { DemoApi.renderDataState($('[data-product-detail-status]'), 'calculation-failed', { message: error.message, retry: load }); }
  }
  $('[data-product-detail-action-form]').addEventListener('submit', async (event) => { event.preventDefault(); if (Object.keys(detailPayload?.capabilities || {}).length && !DemoApi.can(detailPayload, 'can_create_action')) { $('[data-product-detail-action-status]').textContent = '当前数据条件不满足创建运营动作'; return; } const formElement = event.currentTarget; const form = new FormData(formElement); const submit = formElement.querySelector('button[type="submit"]'); if (submit) { submit.disabled = true; submit.setAttribute('aria-busy', 'true'); } try { await DemoApi.domainRequest('/api/actions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ capability_key: 'product-detail.create_action', product_id: id, purpose_type: 'increase_sales', purpose_note: form.get('purpose_note'), action_type: form.get('action_type'), action_detail: form.get('action_detail'), target_metric: 'payment_amount', planned_at: form.get('planned_at'), observer_window_days: 7, assigned_to: 'operator' }) }); $('[data-product-detail-action-status]').textContent = '运营动作草稿已创建'; await load(); } catch (error) { mutationError(error, '创建运营动作失败，请重试'); } finally { if (submit?.isConnected) { submit.disabled = false; submit.removeAttribute('aria-busy'); } } });
  bindWorkbenchNavigation();
  window.addEventListener('tmall:date-range-change', (event) => load(event.detail));
  DemoLabels.load().finally(load);

  // ========== KPI 数据下钻 ==========
  const drillMetricLabels = { net_sales: '净销售额', payment_amount: '支付金额', payment_conversion_rate: '支付转化率', expense_ratio: '费比', average_order_value: '客单价' };
  const drillMetricFormat = { net_sales: money, payment_amount: money, payment_conversion_rate: percent, expense_ratio: percent, average_order_value: money };
  let drillCurrentMetric = null, drillCurrentPeriod = 'daily', drillChart = null;

  function getDrillValue(item, metric) {
    if (metric === 'net_sales') return item.net_sales;
    if (metric === 'payment_amount') return item.payment_amount;
    if (metric === 'payment_conversion_rate') { const v = item.product_visitors || item.paid_ipv || 0; const b = item.payment_qty || item.paid_buyers || 0; return v > 0 ? b / v : null; }
    if (metric === 'expense_ratio') { const p = item.payment_amount || 0; const s = item.ad_spend || 0; return p > 0 ? s / p : null; }
    if (metric === 'average_order_value') { const q = item.payment_qty || item.paid_buyers || 0; const p = item.payment_amount || 0; return q > 0 ? p / q : null; }
    return item[metric];
  }

  function aggregateDrillData(rows, period) {
    if (period === 'daily') return rows;
    const groups = {};
    rows.forEach((item) => {
      const d = new Date(item.date);
      let key = period === 'weekly' ? (() => { const w = new Date(d); w.setDate(d.getDate() - d.getDay()); return w.toISOString().slice(0, 10); })() : item.date.slice(0, 7);
      if (!groups[key]) groups[key] = { date: key, payment_amount: 0, net_sales: 0, product_visitors: 0, ad_spend: 0, payment_qty: 0 };
      groups[key].payment_amount += Number(item.payment_amount) || 0;
      groups[key].net_sales += Number(item.net_sales) || 0;
      groups[key].product_visitors += Number(item.product_visitors) || 0;
      groups[key].ad_spend += Number(item.ad_spend) || 0;
      groups[key].payment_qty += Number(item.payment_qty) || 0;
    });
    return Object.values(groups).sort((a, b) => a.date.localeCompare(b.date));
  }

  function renderDrillContent() {
    const metric = drillCurrentMetric, period = drillCurrentPeriod;
    const trendRows = Array.isArray(detailPayload && detailPayload.daily_trend) ? detailPayload.daily_trend : [];
    const data = aggregateDrillData(trendRows, period);
    const format = drillMetricFormat[metric] || ((v) => v == null ? '--' : v);
    const values = data.map((item) => getDrillValue(item, metric)).filter((v) => v != null && !isNaN(v));
    const stats = document.querySelector('[data-drill-stats]');
    if (values.length) {
      const avg = values.reduce((a, b) => a + b, 0) / values.length, max = Math.max(...values), min = Math.min(...values), latest = values[values.length - 1];
      stats.innerHTML = '<div class="drill-modal__stat"><div class="drill-modal__stat-label">最新值</div><div class="drill-modal__stat-value">' + format(latest) + '</div></div><div class="drill-modal__stat"><div class="drill-modal__stat-label">平均值</div><div class="drill-modal__stat-value">' + format(avg) + '</div></div><div class="drill-modal__stat"><div class="drill-modal__stat-label">最高值</div><div class="drill-modal__stat-value">' + format(max) + '</div></div><div class="drill-modal__stat"><div class="drill-modal__stat-label">最低值</div><div class="drill-modal__stat-value">' + format(min) + '</div></div>';
    } else {
      stats.innerHTML = '<div class="drill-modal__stat" style="grid-column:1/-1;text-align:center;color:var(--text-tertiary);">暂无数据</div>';
    }
    const chartEl = document.querySelector('[data-drill-chart]');
    if (drillChart) { drillChart.dispose(); drillChart = null; }
    if (window.echarts && data.length) {
      drillChart = echarts.init(chartEl);
      drillChart.setOption({
        tooltip: { trigger: 'axis', formatter: function(params) { var p = params[0]; return p.name + '<br/>' + drillMetricLabels[metric] + ': ' + format(p.value); } },
        grid: { left: 50, right: 20, top: 20, bottom: 40 },
        xAxis: { type: 'category', data: data.map(function(d) { return d.date; }), axisLabel: { rotate: data.length > 14 ? 45 : 0, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { formatter: function(v) { return (metric === 'payment_conversion_rate' || metric === 'expense_ratio') ? (v * 100).toFixed(1) + '%' : (v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toFixed(0)); } } },
        series: [{ name: drillMetricLabels[metric], type: 'line', smooth: true, data: data.map(function(d) { return getDrillValue(d, metric); }), areaStyle: { opacity: 0.1 }, lineStyle: { width: 2 }, itemStyle: { color: '#3b82f6' } }],
      });
    } else {
      chartEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary);">暂无趋势数据</div>';
    }
    const table = document.querySelector('[data-drill-table]');
    if (data.length) {
      var rows = data.map(function(item, idx) {
        var tr = document.createElement('tr');
        var val = getDrillValue(item, metric);
        var prev = idx > 0 ? getDrillValue(data[idx - 1], metric) : null;
        var change = (prev != null && prev != 0 && val != null) ? ((val - prev) / prev * 100) : null;
        [item.date, format(val), (change != null ? (change > 0 ? '+' : '') + change.toFixed(1) + '%' : '--')].forEach(function(value, index) {
          var td = document.createElement('td'); td.textContent = value;
          if (index > 0) td.className = 'num';
          if (index === 2 && change != null) td.style.color = change > 0 ? '#10b981' : '#ef4444';
          tr.appendChild(td);
        });
        return tr;
      });
      table.replaceChildren.apply(table, rows);
    } else {
      table.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--text-tertiary);padding:24px;">暂无数据</td></tr>';
    }
  }

  function renderDrillModal(metric) {
    drillCurrentMetric = metric;
    document.querySelector('[data-drill-title]').textContent = (drillMetricLabels[metric] || metric) + ' · 趋势下钻';
    document.querySelector('[data-drill-modal]').hidden = false;
    renderDrillContent();
  }
  function closeDrillModal() { document.querySelector('[data-drill-modal]').hidden = true; if (drillChart) { drillChart.dispose(); drillChart = null; } }

  document.querySelectorAll('[data-drill-metric]').forEach(function(card) { card.addEventListener('click', function() { renderDrillModal(card.dataset.drillMetric); }); });
  var closeBtn = document.querySelector('[data-drill-close]'); if (closeBtn) closeBtn.addEventListener('click', closeDrillModal);
  var modal = document.querySelector('[data-drill-modal]'); if (modal) modal.addEventListener('click', function(e) { if (e.target.dataset.drillModal !== undefined) closeDrillModal(); });
  document.addEventListener('keydown', function(e) { if (e.key === 'Escape' && !document.querySelector('[data-drill-modal]').hidden) closeDrillModal(); });
  document.querySelectorAll('[data-drill-period]').forEach(function(tab) { tab.addEventListener('click', function() {
    document.querySelectorAll('[data-drill-period]').forEach(function(t) { t.classList.remove('drill-modal__tab--active'); });
    tab.classList.add('drill-modal__tab--active');
    drillCurrentPeriod = tab.dataset.drillPeriod;
    renderDrillContent();
  }); });
  window.addEventListener('resize', function() { if (drillChart) drillChart.resize(); });
})();
