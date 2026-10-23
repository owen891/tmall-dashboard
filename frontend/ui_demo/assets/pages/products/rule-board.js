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
    let ruleDetailDrawer = null;

    // 详情面统一 NUI 抽屉：template 承载内容与 footer（关闭/应用到商品列表）
    function ensureRuleDetailDrawer() {
      if (ruleDetailDrawer) return ruleDetailDrawer;
      const template = $('[data-product-rule-detail-template]');
      if (!template || !window.TmallUI?.detailDrawer) return null;
      ruleDetailDrawer = window.TmallUI.detailDrawer({
        title: '经营规则详情',
        description: '查看规则定义、字段口径和当前周期命中证据',
        size: 'lg',
        onClose: () => { selectedRuleDetail = null; },
      });
      const content = template.content.cloneNode(true);
      const footerTemplate = content.querySelector('[data-product-rule-detail-footer]');
      let footer = null;
      if (footerTemplate) {
        footer = document.createElement('div');
        footer.append(...footerTemplate.content.cloneNode(true).childNodes);
        footerTemplate.remove();
      }
      ruleDetailDrawer.body.append(content);
      if (footer) ruleDetailDrawer.ensureFooter().append(...footer.childNodes);
      ruleDetailDrawer.node.querySelectorAll('[data-product-rule-detail-close]').forEach((button) => button.addEventListener('click', closeRuleDetail));
      ruleDetailDrawer.node.querySelector('[data-product-rule-detail-apply]')?.addEventListener('click', () => {
        if (!selectedRuleDetail) return;
        state.ruleKey = selectedRuleDetail.key;
        closeRuleDetail();
        refreshWithFilter();
      });
      return ruleDetailDrawer;
    }

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

    // 策略卡（对齐边界 BI 综合指标卡，2026-10-24 重构）：
    // 常显栅格 + 卡片自带口径说明 + 整卡可点筛选 + 「+ 新建卡」占位 + 展开更多。
    // 首张「全部有效商品」承担 BI「全部」卡职责：点击=清除分群筛选。
    const COLLAPSED_CARD_LIMIT = 5;

    function rulePeriodLabel(rule) {
      const period = String(rule.period || '');
      const month = period.match(/^\d{4}-(\d{2})$/);
      return month ? `${Number(month[1])}月` : period || '--';
    }

    function ruleConditionSummary(rule) {
      const conditions = Array.isArray(rule.conditions) ? rule.conditions : [];
      if (!conditions.length) return rule.description || '无额外条件';
      return conditions.map(ruleConditionText).join('，且');
    }

    function isRuleCardActive(rule) {
      if (rule.key === 'all_products') return !state.ruleKey || state.ruleKey === 'all_products';
      return state.ruleKey === rule.key;
    }

    function applyRuleCard(rule) {
      if (rule.key === 'all_products') state.ruleKey = '';
      else state.ruleKey = state.ruleKey === rule.key ? '' : rule.key;
      refreshWithFilter();
    }

    function buildStrategyCard(rule) {
      const card = document.createElement('article');
      card.className = `product-rule-card product-rule-card--${rule.severity || 'info'}`;
      card.classList.toggle('is-active', isRuleCardActive(rule));
      card.dataset.ruleKey = rule.key;
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-pressed', String(isRuleCardActive(rule)));
      const active = isRuleCardActive(rule);
      card.title = active ? '点击取消该分群筛选' : '点击筛选该分群商品';

      const head = document.createElement('div');
      head.className = 'product-rule-card__head';
      const tag = document.createElement('span');
      tag.className = 'product-rule-card__tag';
      tag.textContent = rule.group || '分群';
      const name = document.createElement('strong');
      name.className = 'product-rule-card__name';
      name.textContent = rule.name;
      const date = document.createElement('span');
      date.className = 'product-rule-card__date';
      date.textContent = rulePeriodLabel(rule);
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'product-rule-card__more';
      more.setAttribute('aria-label', `查看${rule.name}规则详情`);
      more.title = '规则详情';
      more.innerHTML = '<i data-lucide="file-search"></i>';
      more.addEventListener('click', (event) => {
        event.stopPropagation();
        openRuleDetail(rule);
      });
      head.append(tag, name, date, more);

      const ruleText = document.createElement('p');
      ruleText.className = 'product-rule-card__description';
      ruleText.textContent = ruleConditionSummary(rule);

      const meta = document.createElement('div');
      meta.className = 'product-rule-card__meta';
      const value = document.createElement('strong');
      value.className = 'product-rule-card__value';
      value.textContent = `${number(rule.matched_count)} 件`;
      const share = document.createElement('span');
      share.className = 'product-rule-card__share';
      share.textContent = rule.share == null ? '占比 --' : `占比 ${(Number(rule.share) * 100).toFixed(1)}%`;
      meta.append(value, share);

      card.addEventListener('click', () => applyRuleCard(rule));
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          applyRuleCard(rule);
        }
      });
      card.append(head, ruleText, meta);
      return card;
    }

    function buildStrategyPlaceholder() {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'product-rule-card product-rule-card--placeholder';
      card.disabled = true;
      card.title = '自定义分群规则配置入口规划中';
      card.textContent = '+ 新建卡';
      return card;
    }

    function renderRuleCards() {
      const root = $('[data-product-rule-groups]');
      const summary = $('[data-product-rule-summary]');
      const status = $('[data-product-rule-status]');
      const clear = $('[data-product-rule-clear]');
      if (!root) return;
      const toggle = $('[data-product-rule-toggle]');
      root.replaceChildren();
      // 策略卡常显（BI 形态）：折叠档只展示前 5 张，「展开更多」显示全部。
      // 命中筛选的卡始终可见：被折叠时自动展开。
      const activeIndex = state.rules.findIndex((rule) => isRuleCardActive(rule) && rule.key !== 'all_products');
      state.ruleBoardExpanded = state.ruleBoardExpanded || activeIndex >= COLLAPSED_CARD_LIMIT;
      const visibleRules = state.ruleBoardExpanded ? state.rules : state.rules.slice(0, COLLAPSED_CARD_LIMIT);
      visibleRules.forEach((rule) => root.appendChild(buildStrategyCard(rule)));
      if (state.rules.length > visibleRules.length || state.ruleBoardExpanded) root.appendChild(buildStrategyPlaceholder());
      if (!state.rules.length) root.innerHTML = '<p class="panel__hint">当前周期暂无可用经营分群</p>';
      if (toggle) {
        toggle.textContent = state.ruleBoardExpanded ? '点击收起' : '展开更多';
        toggle.setAttribute('aria-expanded', String(state.ruleBoardExpanded));
      }
      if (summary) summary.hidden = true;
      if (clear) clear.hidden = !state.ruleKey;
      const active = state.rules.find((rule) => rule.key === state.ruleKey);
      if (status) status.textContent = active ? `已应用分群：${active.name} · ${active.description}` : '口径即规则：点击卡片筛选商品列表，规则口径印在卡上';
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
      const drawer = ensureRuleDetailDrawer();
      if (!drawer) return;
      drawer.node.querySelector('.ui-drawer__copy h2').textContent = `${rule.name} · 规则详情`;
      const description = drawer.node.querySelector('.ui-drawer__copy p');
      if (description) description.textContent = rule.description || '查看规则定义、字段口径和当前周期命中证据';
      const summary = $('[data-product-rule-detail-summary]', drawer.node);
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
      const conditions = $('[data-product-rule-detail-conditions]', drawer.node);
      const conditionList = Array.isArray(rule.conditions) ? rule.conditions : [];
      conditions.replaceChildren(...(conditionList.length ? conditionList : [{ label: '规则条件', field: 'SQL', operator: '=', value: rule.condition || '--' }]).map((condition) => {
        const item = document.createElement('div'); item.className = 'product-rule-detail-dialog__condition';
        item.textContent = ruleConditionText(condition); return item;
      }));
      const evidence = $('[data-product-rule-detail-evidence]', drawer.node);
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
      $('[data-product-rule-detail-query]', drawer.node).textContent = JSON.stringify({
        rule_key: rule.key, period: rule.period, category_mode: state.categoryMode || null,
        status: $('[data-products-status-filter]')?.value || 'active', matched_product_ids: rule.matched_product_ids || [],
      }, null, 2);
      drawer.open();
      window.lucide?.createIcons();
    }

    function closeRuleDetail() {
      ruleDetailDrawer?.close();
      selectedRuleDetail = null;
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
      ensureRuleDetailDrawer();
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
