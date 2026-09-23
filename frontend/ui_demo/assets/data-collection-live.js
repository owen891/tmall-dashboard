(function() {
  'use strict';

  const grid = document.querySelector('[data-collect-grid]');
  const logPanel = document.querySelector('[data-log-panel]');
  const logTitle = document.querySelector('[data-log-title]');
  const logContent = document.querySelector('[data-log-content]');
  const logClose = document.querySelector('[data-log-close]');
  const credentialsForm = document.querySelector('[data-collect-credentials-form]');
  const credentialsStatus = document.querySelector('[data-collect-credentials-status]');
  const credentialsMessage = document.querySelector('[data-collect-credentials-message]');
  const credentialsDialog = document.querySelector('[data-collect-credentials-dialog]');
  const integrationGrid = document.querySelector('[data-integration-grid]');
  const integrationDomain = document.querySelector('[data-integration-domain]');
  const integrationReadiness = document.querySelector('[data-integration-readiness]');
  let credentialState = {};
  let integrationCatalog = null;

  const integrationDomainLabels = {
    'tmall-dashboard': '天猫看板',
    'ad-ctr-dashboard': '广告素材点击率',
    inventory: '库存与补货',
    'product-analysis': '商品与评价',
    market: '市场与竞品',
    review: '月度复盘',
  };

  const freshnessLabels = {
    'today': '今日已更新',
    'yesterday': '昨日更新',
    'recent': '近3天更新',
    'stale': '数据过期',
    'unknown': '未知'
  };

  const statusLabels = {
    'idle': '空闲',
    'queued': '排队中',
    'running': '采集中',
    'completed': '已完成',
    'partial': '部分成功',
    'failed': '失败'
  };

  const statusColors = {
    'idle': '#6b7280',
    'queued': '#2563eb',
    'running': '#2563eb',
    'completed': '#16a34a',
    'partial': '#d97706',
    'failed': '#dc2626',
    'timed_out': '#dc2626'
  };

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  // 计算数据新鲜度，支持YYYY-MM和YYYY-MM-DD格式
  function calcFreshness(latestDate) {
    if (!latestDate) return 'unknown';
    try {
      let dateStr = String(latestDate).trim();
      // 处理YYYY-MM格式
      if (/^\d{4}-\d{2}$/.test(dateStr)) {
        const [year, month] = dateStr.split('-').map(Number);
        const now = new Date();
        // 如果是当前月，视为今日更新
        if (year === now.getFullYear() && month === now.getMonth() + 1) {
          return 'today';
        }
        // 上个月
        const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        if (year === lastMonth.getFullYear() && month === lastMonth.getMonth() + 1) {
          return 'yesterday';
        }
        return 'stale';
      }
      // 处理YYYY-MM-DD格式
      const latest = new Date(dateStr + 'T00:00:00');
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const diffDays = Math.floor((today - latest) / (1000 * 60 * 60 * 24));
      if (diffDays <= 0) return 'today';
      if (diffDays === 1) return 'yesterday';
      if (diffDays <= 3) return 'recent';
      return 'stale';
    } catch (e) {
      return 'unknown';
    }
  }

  async function loadStatus() {
    try {
      const resp = await fetch('/api/collect/status');
      const result = await resp.json();
      if (result.ok) {
        // 使用前端计算的新鲜度
        result.data.sources.forEach(s => {
          s.freshness = calcFreshness(s.latest_date);
        });
        renderSources(result.data.sources);
        renderSummary(result.data.sources);
      } else {
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:#ef4444;padding:48px;">加载失败: ${result.message || '未知错误'}</div>`;
      }
    } catch (e) {
      grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:#ef4444;padding:48px;">加载失败: ${e.message}</div>`;
    }
  }

  async function loadCredentials() {
    if (!credentialsForm) return;
    try {
      const response = await fetch('/api/settings');
      const result = await response.json();
      if (!result.ok) throw new Error(result.message || '读取失败');
      const credentials = result.data?.collector_credentials || {};
      credentialState = credentials;
      for (const key of ['bi', 'sycm', 'wanxiangtai']) { const item = credentials[key] || {}; credentialsForm.elements[`${key}_username`].value = item.username || ''; credentialsForm.elements[`${key}_password`].value = ''; }
      credentialsStatus.textContent = ['bi', 'sycm', 'wanxiangtai'].every(key => credentials[key]?.password_set) ? '全部已配置' : '部分未配置';
      credentialsMessage.textContent = '密码已配置的账号，留空密码提交可保持原密码。';
    } catch (error) {
      credentialsStatus.textContent = '读取失败';
      credentialsMessage.textContent = error.message || '采集账号读取失败';
    }
  }

  async function saveCredentials(event) {
    event.preventDefault();
    const button = credentialsForm.querySelector('button[type="submit"]');
    const credentials = {};
    for (const key of ['bi', 'sycm', 'wanxiangtai']) credentials[key] = { username: credentialsForm.elements[`${key}_username`].value.trim(), password: credentialsForm.elements[`${key}_password`].value };
    if (Object.entries(credentials).some(([key, item]) => item.username && !item.password && !credentialState[key]?.password_set)) { credentialsMessage.textContent = '新填写账号时必须同时填写密码；已有账号可留空密码。'; return; }
    button.disabled = true;
    credentialsMessage.textContent = '保存中…';
    try {
      const response = await fetch('/api/settings', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collector_credentials: credentials })
      });
      const result = await response.json();
      if (!result.ok) throw new Error(result.message || '保存失败');
      for (const key of ['bi', 'sycm', 'wanxiangtai']) credentialsForm.elements[`${key}_password`].value = '';
      credentialsStatus.textContent = '已保存';
      credentialsMessage.textContent = '采集账号已保存。';
      credentialState = result.data?.collector_credentials || credentialState;
      setTimeout(() => credentialsDialog?.close(), 350);
    } catch (error) {
      credentialsMessage.textContent = error.message || '采集账号保存失败';
    } finally {
      button.disabled = false;
    }
  }

  async function loadHealth() {
    const statusNode = document.querySelector('[data-collect-health-status]');
    try {
      const resp = await fetch('/api/collect/health');
      const result = await resp.json();
      if (!result.ok) throw new Error(result.message || '健康检查失败');
      const data = result.data;
      const failed = data.sources.reduce((sum, source) => sum + (source.failed_runs_7d || 0), 0);
      const staging = data.staging_7d || {};
      document.querySelector('[data-collect-health="unhealthy"]').textContent = data.unhealthy_count ?? '--';
      document.querySelector('[data-collect-health="failed"]').textContent = failed;
      document.querySelector('[data-collect-health="published"]').textContent = staging.published || 0;
      document.querySelector('[data-collect-health="rejected"]').textContent = staging.rejected || 0;
      statusNode.textContent = data.status === 'healthy' ? '健康' : '需要关注';
      statusNode.className = `collect-health-status collect-health-status--${data.status}`;
    } catch (error) {
      statusNode.textContent = '检查失败';
      statusNode.className = 'collect-health-status collect-health-status--degraded';
    }
  }

  function renderIntegrationCatalog() {
    if (!integrationGrid || !integrationCatalog) return;
    const domain = integrationDomain?.value || '';
    const readiness = integrationReadiness?.value || '';
    const sources = integrationCatalog.sources.filter((item) => (!domain || item.domain === domain) && (!readiness || item.readiness === readiness));
    integrationGrid.innerHTML = sources.length ? sources.map((item) => {
      const live = item.runtime_status && item.runtime_status !== 'manual' && item.runtime_status !== 'not_connected';
      const freshness = item.freshness && item.freshness !== 'unknown' ? `<span class="integration-badge integration-badge--fresh">${escapeHtml(item.latest_date || item.freshness)}</span>` : '';
      const issue = item.blocker || item.operational_issue;
      return `<article class="integration-card"><div class="integration-card__header"><div><h4 class="integration-card__title">${escapeHtml(item.name)}</h4><p class="integration-card__meta">${escapeHtml(integrationDomainLabels[item.domain] || item.domain)} · ${escapeHtml(item.frequency)}</p></div><div class="integration-card__badges"><span class="integration-badge integration-badge--${escapeHtml(item.readiness)}">${escapeHtml(item.readiness_label)}</span>${freshness}</div></div><p class="integration-card__content">${escapeHtml(item.content)}</p><p class="integration-card__meta"><strong>依赖：</strong>${escapeHtml(item.dependency)}</p>${live ? `<p class="integration-card__meta"><strong>运行：</strong>${escapeHtml(item.runtime_status)} · ${escapeHtml(item.record_count ?? 0)} 条</p>` : ''}${issue ? `<p class="integration-card__issue"><strong>说明：</strong>${escapeHtml(issue)}</p>` : ''}</article>`;
    }).join('') : '<div class="integration-empty">没有符合筛选条件的数据源</div>';
    if (window.lucide) lucide.createIcons();
  }

  async function loadIntegrationCatalog() {
    if (!integrationGrid) return;
    try {
      const response = await fetch('/api/data-integration/catalog');
      const result = await response.json();
      if (!result.ok) throw new Error(result.message || '整合目录加载失败');
      integrationCatalog = result.data;
      const current = integrationDomain?.value || '';
      if (integrationDomain) {
        integrationDomain.innerHTML = '<option value="">全部业务域</option>' + (result.data.domains || []).map((domain) => `<option value="${escapeHtml(domain)}">${escapeHtml(integrationDomainLabels[domain] || domain)}</option>`).join('');
        integrationDomain.value = current;
      }
      for (const key of ['total', 'connected', 'planned', 'blocked']) {
        const node = document.querySelector(`[data-integration-count="${key}"]`);
        if (node) node.textContent = result.data.summary?.[key] ?? 0;
      }
      renderIntegrationCatalog();
    } catch (error) {
      integrationGrid.innerHTML = `<div class="integration-empty">加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  function renderSummary(sources) {
    const total = sources.length;
    const today = sources.filter(s => s.freshness === 'today').length;
    const stale = sources.filter(s => s.freshness === 'stale' || s.freshness === 'yesterday' || s.freshness === 'recent').length;
    const running = sources.filter(s => s.status === 'running' || s.status === 'queued').length;

    document.querySelector('[data-collect-summary="total"]').textContent = total;
    document.querySelector('[data-collect-summary="today"]').textContent = today;
    document.querySelector('[data-collect-summary="stale"]').textContent = stale;
    document.querySelector('[data-collect-summary="running"]').textContent = running;
  }

  function renderSources(sources) {
    if (!sources || sources.length === 0) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-secondary);padding:48px;">暂无数据源</div>';
      return;
    }

    grid.innerHTML = sources.map(source => {
      const freshness = source.freshness || 'unknown';
      const isRunning = source.status === 'running' || source.status === 'queued';
      const recordCount = source.record_count ? source.record_count.toLocaleString('zh-CN') : '0';

      return `
        <article class="ui-panel collect-source-card" data-source="${escapeHtml(source.key)}">
          <div class="collect-source-card__header">
            <div>
              <h4 class="collect-source-card__title">${escapeHtml(source.name)}</h4>
              <p class="collect-source-card__desc">${escapeHtml(source.description || '')}</p>
            </div>
            <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end;">
              <span class="freshness-badge freshness-${escapeHtml(freshness)}">${escapeHtml(freshnessLabels[freshness] || freshness)}</span>
              ${source.status && source.status !== 'idle' ? `
                <span style="padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500;background:${statusColors[source.status] || '#6b7280'}20;color:${statusColors[source.status] || '#6b7280'};">
                  ${escapeHtml(statusLabels[source.status] || source.status)}
                </span>
              ` : ''}
            </div>
          </div>
          <div class="collect-source-card__metrics">
            <div class="collect-source-card__metric">
              <div class="collect-source-card__metric-label">最新数据日期</div>
              <div class="collect-source-card__metric-value">${escapeHtml(source.latest_date || '--')}</div>
            </div>
            <div class="collect-source-card__metric">
              <div class="collect-source-card__metric-label">记录总数</div>
              <div class="collect-source-card__metric-value">${recordCount}</div>
            </div>
          </div>
          ${source.last_run ? `
            <div style="font-size:12px;color:var(--text-secondary);margin-top:-4px;">
              最后运行: ${escapeHtml(source.last_run.replace('T', ' ').substring(0, 19))}
            </div>
          ` : ''}
          ${isRunning ? `
            <div class="collect-running">
              <span class="collect-running__dot"></span>
              <span>采集中...</span>
            </div>
          ` : ''}
          <div class="collect-source-card__actions">
            <button class="ui-button ui-button--primary" type="button" data-action="trigger" data-source="${escapeHtml(source.key)}" ${isRunning ? 'disabled' : ''}>
              <i data-lucide="play"></i><span>${isRunning ? '采集中' : '立即采集'}</span>
            </button>
            <button class="ui-button" type="button" data-action="view-log" data-source="${source.key}">
              <i data-lucide="file-text"></i><span>查看日志</span>
            </button>
          </div>
        </article>
      `;
    }).join('');

    // 初始化lucide图标
    if (window.lucide) lucide.createIcons();

    // 绑定事件
    grid.querySelectorAll('[data-action="trigger"]').forEach(btn => {
      btn.addEventListener('click', () => triggerCollect(btn.dataset.source));
    });
    grid.querySelectorAll('[data-action="view-log"]').forEach(btn => {
      btn.addEventListener('click', () => viewLog(btn.dataset.source));
    });
  }

  async function triggerCollect(sourceKey) {
    const btn = grid.querySelector(`[data-action="trigger"][data-source="${sourceKey}"]`);
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i data-lucide="loader-2"></i><span>触发中...</span>';
      if (window.lucide) lucide.createIcons();
    }

    try {
      const prepare = await fetch('/api/collect/prepare', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sources: [sourceKey] })
      });
      const prepared = await prepare.json();
      if (!prepared.ok) throw new Error(prepared.message || '页面准备失败');
      const resp = await fetch('/api/collect/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: sourceKey })
      });
      const result = await resp.json();
      if (result.ok) {
        // 开始轮询状态
        startPolling(sourceKey);
      } else {
        alert(result.message || '触发失败');
        if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="play"></i><span>立即采集</span>'; if (window.lucide) lucide.createIcons(); }
      }
    } catch (e) {
      alert('触发失败: ' + e.message);
      if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="play"></i><span>立即采集</span>'; if (window.lucide) lucide.createIcons(); }
    }
  }

  // 一键采集全部
  async function collectAll() {
    const btn = document.querySelector('[data-collect-all]');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i data-lucide="loader-2"></i><span>采集中...</span>';
      if (window.lucide) lucide.createIcons();
    }

    try {
      const resp = await fetch('/api/collect/status');
      const result = await resp.json();
      if (result.ok) {
        const sources = result.data.sources.filter(s => s.status !== 'running');
        const prepare = await fetch('/api/collect/prepare', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sources: sources.map(source => source.key) })
        });
        const prepared = await prepare.json();
        if (!prepared.ok) throw new Error(prepared.message || '页面准备失败');
        for (const source of sources) {
          await fetch('/api/collect/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: source.key })
          });
        }
        alert(`已触发 ${sources.length} 个采集任务`);
        startPollingAll();
      }
    } catch (e) {
      alert('触发失败: ' + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="play"></i><span>一键采集全部</span>';
        if (window.lucide) lucide.createIcons();
      }
    }
  }

  let pollingTimer = null;
  function startPolling(sourceKey) {
    if (pollingTimer) clearInterval(pollingTimer);
    let count = 0;
    pollingTimer = setInterval(async () => {
      count++;
      await loadStatus();
      const card = grid.querySelector(`[data-source="${sourceKey}"]`);
      if (card && !card.querySelector('.collect-running')) {
        clearInterval(pollingTimer);
        pollingTimer = null;
        viewLog(sourceKey);
      }
      if (count > 60) {
        clearInterval(pollingTimer);
        pollingTimer = null;
      }
    }, 3000);
  }

  function startPollingAll() {
    if (pollingTimer) clearInterval(pollingTimer);
    let count = 0;
    pollingTimer = setInterval(async () => {
      count++;
      await loadStatus();
      const running = grid.querySelectorAll('.collect-running').length;
      if (running === 0) {
        clearInterval(pollingTimer);
        pollingTimer = null;
      }
      if (count > 120) {
        clearInterval(pollingTimer);
        pollingTimer = null;
      }
    }, 3000);
  }

  async function viewLog(sourceKey) {
    try {
      const resp = await fetch(`/api/collect/log/${sourceKey}`);
      const result = await resp.json();
      if (result.ok) {
        const sourceName = document.querySelector(`[data-source="${sourceKey}"] .collect-source-card__title`)?.textContent || sourceKey;
        logTitle.textContent = `${sourceName} - 采集日志`;
        const output = result.data.output || [];
        if (output.length > 0) {
          logContent.textContent = output.join('\n');
        } else if (result.data.error) {
          logContent.textContent = '错误: ' + result.data.error;
        } else {
          logContent.innerHTML = '<div class="collect-log-empty">暂无日志记录</div>';
        }
        logPanel.hidden = false;
        logPanel.scrollIntoView({ behavior: 'smooth' });
      }
    } catch (e) {
      alert('获取日志失败: ' + e.message);
    }
  }

  // 事件绑定
  if (logClose) {
    logClose.addEventListener('click', () => { logPanel.hidden = true; });
  }

  const refreshBtn = document.querySelector('[data-collect-refresh]');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => { loadStatus(); loadHealth(); loadIntegrationCatalog(); });
  }
  integrationDomain?.addEventListener('change', renderIntegrationCatalog);
  integrationReadiness?.addEventListener('change', renderIntegrationCatalog);
  document.querySelector('[data-integration-refresh]')?.addEventListener('click', loadIntegrationCatalog);

  const collectAllBtn = document.querySelector('[data-collect-all]');
  if (collectAllBtn) {
    collectAllBtn.addEventListener('click', collectAll);
  }
  if (credentialsForm) {
    credentialsForm.addEventListener('submit', saveCredentials);
  }
  document.querySelector('[data-collect-credentials-open]')?.addEventListener('click', () => {
    loadCredentials();
    credentialsDialog?.showModal();
  });
  document.querySelectorAll('[data-collect-credentials-close]').forEach((button) => {
    button.addEventListener('click', () => credentialsDialog?.close());
  });

  // 初始化
  loadStatus();
  loadHealth();
  loadIntegrationCatalog();
  loadCredentials();
  // 每30秒自动刷新状态（页面不可见时暂停，节省资源）
  let statusTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      loadStatus();
      loadHealth();
    }
  }, 30000);
  // 页面从后台切回前台时立即刷新一次
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      loadStatus();
    }
  });
})();
