(function (global) {
  'use strict';

  /** 商品页「经营分群看板 / 规则详情」模块。
   *
   *  从 products-live.js 的单闭包中切出（闭包状态显式化第二步）：
   *  本模块拥有分群卡片渲染、规则详情弹窗与 rule-* 事件绑定的全部行为；
   *  rules/ruleKey/ruleBoardExpanded 仍存放在页面共享 state 上，
   *  对主闭包的依赖全部通过 deps 显式注入。
   *
   *  deps 契约（由 products-live.js 提供）：
   *  - state              页面共享状态（rules/ruleKey/ruleBoardExpanded/page/urlFilters）
   *  - $                  查询助手
   *  - number             数值格式化
   *  - currentMonthPeriod 当前月度周期（loadRuleCards 请求参数）
   *  - syncUrlState       筛选变化后同步地址栏
   *  - load               应用分群后重载商品列表
   */

  function createRuleBoard(deps) {
    const { state, $, number, currentMonthPeriod, syncUrlState, load } = deps;

    let selectedRuleDetail = null;

    // 规则筛选变化后的公共流程：ruleKey 由调用方先行写入
    function refreshWithFilter() {
      state.page = 1;
      state.urlFilters = null;
      syncUrlState();
      renderRuleCards();
      load();
    }

    function clearRuleFilter() {
      state.ruleKey = '';
      state.ruleBoardExpanded = false;
      refreshWithFilter();
    }

    function renderRuleCards() {
      const root = $('[data-product-rule-groups]');
      const summary = $('[data-product-rule-summary]');
      const status = $('[data-product-rule-status]');
      const clear = $('[data-product-rule-clear]');
      if (!root) return;
      const toggle = $('[data-product-rule-toggle]');
      state.ruleBoardExpanded = Boolean(state.ruleKey) || state.ruleBoardExpanded;
      root.replaceChildren();
      root.hidden = !state.ruleBoardExpanded;
      if (summary) {
        summary.replaceChildren();
        state.rules.slice(0, 5).forEach((rule) => {
          const item = document.createElement('span');
          item.className = `product-rule-summary-item product-rule-summary-item--${rule.severity || 'info'}`;
          item.textContent = `${rule.name} ${number(rule.matched_count)}件`;
          summary.appendChild(item);
        });
        summary.hidden = state.ruleBoardExpanded || !state.rules.length;
      }
      if (toggle) {
        toggle.textContent = state.ruleBoardExpanded ? '收起分群详情' : '展开分群详情';
        toggle.setAttribute('aria-expanded', String(state.ruleBoardExpanded));
      }
      const groups = new Map();
      state.rules.forEach((rule) => {
        if (!groups.has(rule.group)) groups.set(rule.group, []);
        groups.get(rule.group).push(rule);
      });
      groups.forEach((rules, groupName) => {
        const section = document.createElement('section');
        section.className = 'product-rule-group';
        const heading = document.createElement('h4');
        heading.textContent = groupName;
        const cards = document.createElement('div');
        cards.className = 'product-rule-group__cards';
        rules.forEach((rule) => {
          const card = document.createElement('article');
          card.className = `product-rule-card product-rule-card--${rule.severity || 'info'}`;
          card.classList.toggle('is-active', state.ruleKey === rule.key);
          const title = document.createElement('strong');
          title.textContent = rule.name;
          const desc = document.createElement('span');
          desc.className = 'product-rule-card__description';
          desc.textContent = rule.description;
          const meta = document.createElement('span');
          meta.className = 'product-rule-card__meta';
          const share = rule.share == null ? '--' : `${(Number(rule.share) * 100).toFixed(1)}%`;
          meta.textContent = `${number(rule.matched_count)} 件 · ${share}`;
          const actions = document.createElement('div');
          actions.className = 'product-rule-card__actions';
          const apply = document.createElement('button');
          apply.type = 'button';
          apply.className = 'ui-button ui-button--small';
          apply.textContent = state.ruleKey === rule.key ? '取消筛选' : '查看商品';
          apply.setAttribute('aria-pressed', String(state.ruleKey === rule.key));
          apply.addEventListener('click', () => {
            state.ruleKey = state.ruleKey === rule.key ? '' : rule.key;
            refreshWithFilter();
          });
          const inspect = document.createElement('button');
          inspect.type = 'button';
          inspect.className = 'ui-button ui-button--ghost ui-button--small';
          inspect.innerHTML = '<i data-lucide="file-search"></i><span>规则详情</span>';
          inspect.addEventListener('click', () => openRuleDetail(rule));
          actions.append(apply, inspect);
          card.append(title, desc, meta, actions);
          cards.appendChild(card);
        });
        section.append(heading, cards);
        root.appendChild(section);
      });
      if (!state.rules.length) root.innerHTML = '<p class="panel__hint">当前周期暂无可用经营分群</p>';
      if (clear) clear.hidden = !state.ruleKey;
      const active = state.rules.find((rule) => rule.key === state.ruleKey);
      if (status) status.textContent = active ? `已应用分群：${active.name} · ${active.description}` : '按当前周期经营事实识别需要关注的商品集合';
    }

    function ruleConditionText(condition) {
      if (!condition) return '无额外条件';
      const value = condition.value == null ? '--' : condition.value;
      const displayValue = condition.unit === '%' && typeof condition.value === 'number'
        ? `${(condition.value * 100).toFixed(condition.value * 100 % 1 ? 1 : 0)}%`
        : `${value}${condition.unit === '元' || condition.unit === '人' ? condition.unit : ''}`;
      return `${condition.label || condition.field} ${condition.operator} ${displayValue}`;
    }

    function openRuleDetail(rule) {
      selectedRuleDetail = rule;
      const dialog = $('[data-product-rule-detail-dialog]');
      if (!dialog) return;
      $('[data-product-rule-detail-title]').textContent = `${rule.name} · 规则详情`;
      $('[data-product-rule-detail-description]').textContent = rule.description || '查看规则定义、字段口径和当前周期命中证据';
      const summary = $('[data-product-rule-detail-summary]');
      summary.replaceChildren(...[
        ['规则类型', ({ segmentation: '分群规则', alert: '预警规则', diagnosis: '诊断规则', recommendation: '动作建议规则' }[rule.rule_type] || '--')],
        ['规则版本', rule.version || '--'], ['统计周期', rule.period || '--'],
        ['命中商品', `${number(rule.matched_count)} 件`], ['覆盖占比', rule.share == null ? '--' : `${(Number(rule.share) * 100).toFixed(1)}%`],
      ].map(([label, value]) => {
        const item = document.createElement('div'); item.className = 'product-rule-detail-dialog__summary-item';
        const name = document.createElement('span'); name.textContent = label;
        const val = document.createElement('strong'); val.textContent = value;
        item.append(name, val); return item;
      }));
      const conditions = $('[data-product-rule-detail-conditions]');
      const conditionList = Array.isArray(rule.conditions) ? rule.conditions : [];
      conditions.replaceChildren(...(conditionList.length ? conditionList : [{ label: '规则条件', field: 'SQL', operator: '=', value: rule.condition || '--' }]).map((condition) => {
        const item = document.createElement('div'); item.className = 'product-rule-detail-dialog__condition';
        item.textContent = ruleConditionText(condition); return item;
      }));
      const evidence = $('[data-product-rule-detail-evidence]');
      const evidenceSummary = rule.evidence_summary || {};
      evidence.replaceChildren(...[
        ['来源表', evidenceSummary.source || 'monthly_data'], ['数据粒度', evidenceSummary.grain || 'product-month'],
        ['覆盖商品', number(evidenceSummary.eligible_product_count ?? rule.eligible_count)],
        ['命中集合', number(evidenceSummary.matched_product_count ?? rule.matched_count)],
        ['覆盖状态', evidenceSummary.coverage || rule.availability || '--'],
      ].map(([label, value]) => {
        const item = document.createElement('div'); item.className = 'status-list__item';
        const left = document.createElement('span'); left.className = 'status-list__label'; left.textContent = label;
        const right = document.createElement('span'); right.className = 'status-list__value'; right.textContent = value;
        item.append(left, right); return item;
      }));
      $('[data-product-rule-detail-query]').textContent = JSON.stringify({
        rule_key: rule.key, period: rule.period, category_mode: state.categoryMode || null,
        status: $('[data-products-status-filter]')?.value || 'active', matched_product_ids: rule.matched_product_ids || [],
      }, null, 2);
      dialog.hidden = false;
      dialog.showModal?.();
      window.lucide?.createIcons();
    }

    function closeRuleDetail() {
      const dialog = $('[data-product-rule-detail-dialog]');
      if (!dialog) return;
      dialog.close?.(); dialog.hidden = true; selectedRuleDetail = null;
    }

    async function loadRuleCards() {
      try {
        const params = new URLSearchParams({ period: currentMonthPeriod(), status: $('[data-products-status-filter]')?.value || 'active' });
        try { params.set('category_mode', localStorage.getItem('dashboard.categoryMode') || 'sock'); } catch (_) { params.set('category_mode', 'sock'); }
        const response = await DemoApi.domainRequest(`/api/product-overview/rule-results?${params}`);
        state.rules = Array.isArray(response.data?.rules) ? response.data.rules : [];
        renderRuleCards();
      } catch (error) {
        state.rules = [];
        renderRuleCards();
        const status = $('[data-product-rule-status]');
        if (status) status.textContent = error.message || '经营分群加载失败';
      }
    }

    function bindRuleBoard() {
      $('[data-product-rule-clear]')?.addEventListener('click', clearRuleFilter);
      $('[data-product-rule-toggle]')?.addEventListener('click', () => {
        state.ruleBoardExpanded = !state.ruleBoardExpanded;
        renderRuleCards();
      });
      document.querySelectorAll('[data-product-rule-detail-close]').forEach((button) => button.addEventListener('click', closeRuleDetail));
      $('[data-product-rule-detail-apply]')?.addEventListener('click', () => {
        if (!selectedRuleDetail) return;
        state.ruleKey = selectedRuleDetail.key;
        closeRuleDetail();
        refreshWithFilter();
      });
    }

    return Object.freeze({
      renderRuleCards,
      loadRuleCards,
      openRuleDetail,
      closeRuleDetail,
      bindRuleBoard,
    });
  }

  global.TmallProducts = global.TmallProducts || {};
  global.TmallProducts.createRuleBoard = createRuleBoard;
})(window);
