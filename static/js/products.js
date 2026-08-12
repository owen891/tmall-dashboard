/* ================================================================
   模块4: 商品分析
================================================================ */

// All available columns definition
const ALL_COLUMNS = [
    // 基础信息
    { key: 'image', label: '商品图', type: 'image', group: '基础信息', defaultVisible: true },
    { key: 'title', label: '商品标题', type: 'text', group: '基础信息', defaultVisible: true },
    { key: 'product_id', label: '商品ID', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'category', label: '商品类目', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'tier', label: '分层', type: 'text', group: '基础信息', defaultVisible: true },
    { key: 'style', label: '风格', type: 'text', group: '基础信息', defaultVisible: true },
    { key: 'scene', label: '场景', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'status', label: '商品状态', type: 'status', group: '基础信息', defaultVisible: true },
    { key: 'list_date', label: '上架时间', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'manager', label: '负责人', type: 'text', group: '基础信息', defaultVisible: false },
    { key: 'action', label: '运营动作', type: 'action', group: '基础信息', defaultVisible: true },
    // 流量指标
    { key: 'visitors', label: '访客数', type: 'number', group: '流量指标', defaultVisible: true },
    { key: 'page_views', label: '浏览量', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'search_visitors', label: '搜索访客', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'search_ratio', label: '搜索占比', type: 'percent', group: '流量指标', defaultVisible: false },
    { key: 'search_ipv', label: '搜索IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'recommend_ipv', label: '推荐IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'paid_ipv', label: '营销推广IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'organic_ipv', label: '非推广IPV', type: 'number', group: '流量指标', defaultVisible: false },
    { key: 'uv_value', label: '客单价值', type: 'money', group: '流量指标', defaultVisible: false },
    { key: 'avg_stay_duration', label: '平均停留时长', type: 'decimal', group: '流量指标', defaultVisible: false },
    { key: 'bounce_rate', label: '跳出率', type: 'percent', group: '流量指标', defaultVisible: false },
    // 转化指标
    { key: 'conversion', label: '支付转化率', type: 'percent', group: '转化指标', defaultVisible: true },
    { key: 'search_conversion', label: '搜索转化率', type: 'percent', group: '转化指标', defaultVisible: false },
    { key: 'cart_rate', label: '加购率', type: 'percent', group: '转化指标', defaultVisible: false },
    { key: 'fav_rate', label: '收藏率', type: 'percent', group: '转化指标', defaultVisible: false },
    { key: 'click_rate', label: '点击率', type: 'percent', group: '转化指标', defaultVisible: false },
    // 交易指标
    { key: 'payment_amount', label: '支付金额', type: 'money', group: '交易指标', defaultVisible: true },
    { key: 'payment_count', label: '支付件数', type: 'number', group: '交易指标', defaultVisible: true },
    { key: 'buyers', label: '支付买家数', type: 'number', group: '交易指标', defaultVisible: false },
    { key: 'avg_order_value', label: '笔单价', type: 'money', group: '交易指标', defaultVisible: false },
    { key: 'net_sales', label: '净销售额', type: 'money', group: '交易指标', defaultVisible: false },
    { key: 'cart_qty', label: '加购件数', type: 'number', group: '交易指标', defaultVisible: false },
    { key: 'cart_users', label: '商品加购人数', type: 'number', group: '交易指标', defaultVisible: false },
    { key: 'fav_users', label: '收藏人数', type: 'number', group: '交易指标', defaultVisible: false },
    // 退款指标
    { key: 'refund_amount', label: '退款金额', type: 'money', group: '退款指标', defaultVisible: false },
    { key: 'refund_rate', label: '退款率', type: 'percent', group: '退款指标', defaultVisible: true },
    { key: 'refund_paid_ratio', label: '退款退货率', type: 'percent', group: '退款指标', defaultVisible: false },
    // 推广指标
    { key: 'ad_spend', label: '推广花费', type: 'money', group: '推广指标', defaultVisible: true },
    { key: 'roi', label: '推广ROI', type: 'decimal', group: '推广指标', defaultVisible: true },
    { key: 'overall_roi', label: '全店ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'paid_ratio', label: '付费占比', type: 'percent', group: '推广指标', defaultVisible: false },
    { key: 'keyword_spend', label: '直通车花费', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'keyword_sales', label: '直通车成交', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'keyword_roi', label: '直通车ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'keyword_visitors', label: '直通车访客', type: 'number', group: '推广指标', defaultVisible: false },
    { key: 'keyword_ppc', label: '直通车PPC', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'crowd_spend', label: '人群推广花费', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'crowd_sales', label: '人群推广成交', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'crowd_roi', label: '人群推广ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'crowd_visitors', label: '人群推广访客', type: 'number', group: '推广指标', defaultVisible: false },
    { key: 'crowd_ppc', label: '人群推广PPC', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'site_spend', label: '定向推广花费', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'site_sales', label: '定向推广成交', type: 'money', group: '推广指标', defaultVisible: false },
    { key: 'site_roi', label: '定向推广ROI', type: 'decimal', group: '推广指标', defaultVisible: false },
    { key: 'site_visitors', label: '定向推广访客', type: 'number', group: '推广指标', defaultVisible: false },
    { key: 'site_ppc', label: '定向推广PPC', type: 'money', group: '推广指标', defaultVisible: false },
    // 付费报表
    { key: 'impressions', label: '展现量', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'clicks', label: '点击量', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'cost', label: '花费', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'ctr', label: '点击率', type: 'percent', group: '付费报表', defaultVisible: false },
    { key: 'cpc', label: '平均点击花费', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'cpm', label: '千次展现花费', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'direct_gmv', label: '直接成交金额', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'indirect_gmv', label: '间接成交金额', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_gmv', label: '总成交金额', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_orders', label: '总成交笔数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'direct_orders', label: '直接成交笔数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'indirect_orders', label: '间接成交笔数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'click_conversion', label: '点击转化率', type: 'percent', group: '付费报表', defaultVisible: false },
    { key: 'presale_roi', label: '含预售投产比', type: 'decimal', group: '付费报表', defaultVisible: false },
    { key: 'total_cost', label: '总成交成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'cart_adds', label: '总购物车数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'direct_cart_adds', label: '直接购物车数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'indirect_cart_adds', label: '间接购物车数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'favs', label: '收藏宝贝数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'store_favs', label: '收藏店铺数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'store_fav_cost', label: '店铺收藏成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_fav_cart', label: '总收藏加购数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'total_fav_cart_cost', label: '总收藏加购成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_cart', label: '宝贝收藏加购数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_cart_cost', label: '宝贝收藏加购成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'total_favs', label: '总收藏数', type: 'number', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_cost', label: '宝贝收藏成本', type: 'money', group: '付费报表', defaultVisible: false },
    { key: 'item_fav_rate', label: '宝贝收藏率', type: 'percent', group: '付费报表', defaultVisible: false },
    { key: 'cart_cost', label: '加购成本', type: 'money', group: '付费报表', defaultVisible: false },
    // 客户指标
    { key: 'repurchase_rate', label: '复购率', type: 'percent', group: '客户指标', defaultVisible: false },
    { key: 'cross_sell_rate', label: '连带购买率', type: 'percent', group: '客户指标', defaultVisible: false },
    { key: 'cross_sell_qty', label: '连带购买量', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'cross_sell_categories', label: '连带购买叶子类目宽度', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'repurchase_users', label: '复购用户数', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'new_buyers', label: '成交新客数', type: 'number', group: '客户指标', defaultVisible: false },
    { key: 'new_buyer_ratio', label: '成交新客占比', type: 'percent', group: '客户指标', defaultVisible: false },
    // 引潜指标
    { key: 'guide_visits', label: '引导访问量', type: 'number', group: '引潜指标', defaultVisible: false },
    { key: 'guide_visitors', label: '引导访问人数', type: 'number', group: '引潜指标', defaultVisible: false },
    { key: 'guide_potential', label: '引导访问潜客数', type: 'number', group: '引潜指标', defaultVisible: false },
    { key: 'guide_potential_ratio', label: '引导访问潜客占比', type: 'percent', group: '引潜指标', defaultVisible: false },
    // 评分
    { key: 'score', label: '综合评分', type: 'decimal', group: '评分', defaultVisible: false },
];

// Current column config (loaded from localStorage or defaults)
let columnConfig = {
    visible: ALL_COLUMNS.filter(c => c.defaultVisible).map(c => c.key),
    sortKey: 'payment_amount',
    sortOrder: 'desc',
};

// 指标分组视图定义
const METRIC_VIEWS = {
    basic: {
        label: '基础信息',
        groups: ['基础信息', '流量指标', '交易指标', '转化指标', '退款指标', '推广指标'],
        columns: ['image', 'title', 'action', 'tier', 'style', 'status', 'list_date',
                  'visitors', 'uv_value', 'search_visitors', 'search_ratio', 'bounce_rate', 'avg_stay_duration',
                  'payment_amount', 'payment_count', 'net_sales',
                  'conversion', 'cart_rate',
                  'refund_rate',
                  'ad_spend', 'roi']
    },
    selection: {
        label: '选款指标',
        groups: ['转化指标', '交易指标', '退款指标', '评分'],
        columns: ['image', 'title', 'action', 'conversion', 'search_conversion', 'cart_rate', 'fav_rate',
                  'payment_amount', 'payment_count', 'buyers', 'avg_order_value', 'net_sales',
                  'refund_amount', 'refund_rate', 'score']
    },
    transaction: {
        label: '成交与付费',
        groups: ['推广指标', '付费报表'],
        columns: ['image', 'title', 'action', 'ad_spend', 'roi', 'paid_ratio',
                  'keyword_spend', 'keyword_roi', 'keyword_visitors',
                  'crowd_spend', 'crowd_roi', 'crowd_visitors',
                  'site_spend', 'site_roi', 'site_visitors',
                  'impressions', 'clicks', 'ctr', 'cpc', 'direct_gmv', 'indirect_gmv']
    }
};

let currentMetricView = 'basic';

// Load config from localStorage
const COL_CONFIG_VERSION = 4;
function loadColumnConfig() {
    const saved = localStorage.getItem('product_col_config');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            // Version check: reset if schema changed
            if (parsed.version === COL_CONFIG_VERSION) {
                columnConfig = parsed;
            }
        } catch(e) {}
    }
    // Sync sort config to STATE
    STATE.sortKey = columnConfig.sortKey || 'payment_amount';
    STATE.sortOrder = columnConfig.sortOrder || 'desc';
}

// Save config to localStorage
function saveColumnConfig() {
    columnConfig.version = COL_CONFIG_VERSION;
    localStorage.setItem('product_col_config', JSON.stringify(columnConfig));
}

// Toggle column config panel
function toggleColConfig() {
    const panel = document.getElementById('colConfigPanel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        renderColConfigList();
    }
}

// Render column checkboxes grouped by category
function renderColConfigList() {
    const groups = {};
    ALL_COLUMNS.forEach(col => {
        if (!groups[col.group]) groups[col.group] = [];
        groups[col.group].push(col);
    });

    let html = '';
    for (const [groupName, cols] of Object.entries(groups)) {
        html += `<div class="col-config-group-title">${groupName}</div>`;
        cols.forEach(col => {
            html += `<label class="col-config-item">
                <input type="checkbox" ${columnConfig.visible.includes(col.key) ? 'checked' : ''}
                       onchange="toggleColumn('${col.key}')">
                <span>${col.label}</span>
            </label>`;
        });
    }
    document.getElementById('colConfigList').innerHTML = html;
}

// Toggle column visibility
function toggleColumn(key) {
    const idx = columnConfig.visible.indexOf(key);
    if (idx >= 0) columnConfig.visible.splice(idx, 1);
    else columnConfig.visible.push(key);
    saveColumnConfig();
    // Re-render table with current STATE.productData
    if (STATE.productData && STATE.productData.length > 0) {
        renderProductTable();
    }
}

// Save template
function saveTemplate() {
    document.getElementById('templateSaveForm').style.display = 'flex';
    document.getElementById('templateMenu').style.display = 'none';
    document.getElementById('templateName').value = '';
    document.getElementById('templateName').focus();
}

function confirmSaveTemplate() {
    const name = document.getElementById('templateName').value.trim();
    if (!name) return;
    const templates = getTemplates();
    templates[name] = {
        visible: [...columnConfig.visible],
        sortKey: columnConfig.sortKey,
        sortOrder: columnConfig.sortOrder,
    };
    localStorage.setItem('product_templates', JSON.stringify(templates));
    document.getElementById('templateSaveForm').style.display = 'none';
    showToast(`模板"${name}"已保存`, 'success');
}

function cancelSaveTemplate() {
    document.getElementById('templateSaveForm').style.display = 'none';
}

// Load template menu
function loadTemplateMenu() {
    const menu = document.getElementById('templateMenu');
    const templates = getTemplates();
    if (Object.keys(templates).length === 0) {
        menu.innerHTML = '<div style="padding:12px;color:#64748B;font-size:0.82rem;">暂无保存的模板</div>';
    } else {
        menu.innerHTML = Object.entries(templates).map(([name, config]) => `
            <div class="template-item">
                <span onclick="applyTemplate('${name.replace(/'/g, "\\'")}')">${name}</span>
                <button onclick="deleteTemplate('${name.replace(/'/g, "\\'")}')">✕</button>
            </div>
        `).join('');
    }
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    document.getElementById('templateSaveForm').style.display = 'none';
}

function getTemplates() {
    try { return JSON.parse(localStorage.getItem('product_templates') || '{}'); }
    catch(e) { return {}; }
}

function applyTemplate(name) {
    const templates = getTemplates();
    const config = templates[name];
    if (!config) return;
    columnConfig = { ...config };
    saveColumnConfig();
    STATE.sortKey = config.sortKey || 'payment_amount';
    STATE.sortOrder = config.sortOrder || 'desc';
    renderColConfigList();
    if (STATE.productData && STATE.productData.length > 0) {
        renderProductTable();
    }
    document.getElementById('templateMenu').style.display = 'none';
    showToast(`已应用模板"${name}"`, 'success');
}

function deleteTemplate(name) {
    const templates = getTemplates();
    delete templates[name];
    localStorage.setItem('product_templates', JSON.stringify(templates));
    loadTemplateMenu();
    showToast(`模板"${name}"已删除`, 'info');
}

// Get visible columns array
function getVisibleColumns() {
    // 如果当前有指标视图，使用视图定义的列
    const view = METRIC_VIEWS[currentMetricView];
    if (view) {
        return view.columns
            .map(key => ALL_COLUMNS.find(c => c.key === key))
            .filter(Boolean);
    }
    return ALL_COLUMNS.filter(col => columnConfig.visible.includes(col.key));
}

// 切换指标分组视图
function switchMetricView(viewName) {
    currentMetricView = viewName;
    // 更新Tab样式
    document.querySelectorAll('.metric-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });
    STATE.page = 1;
    renderProductTable();
}

// Format cell value based on column type
function formatCellValue(col, product) {
    const val = product[col.key];
    switch (col.type) {
        case 'image':
            if (!val) return '';
            const safeUrl = String(val).replace(/["<>]/g, '');
            return `<img src="${safeUrl}" alt="" loading="lazy" onerror="this.style.display='none'">`;
        case 'money':
            if (val === 0) return '-';
            return fmtWan(val);
        case 'number':
            if (val === 0) return '-';
            return fmtNum(val);
        case 'percent':
            return fmtPct(val);
        case 'decimal':
            if (val == null || isNaN(val)) return '--';
            return Number(val).toFixed(2);
        case 'status':
            const statusMap = {'active': '在售', 'inactive': '下架', 'draft': '草稿'};
            const cls = val === 'active' ? 'status-active' : val === 'inactive' ? 'status-inactive' : 'status-draft';
            return `<span class="status-badge ${cls}">${statusMap[val] || val || '--'}</span>`;
        case 'text':
        default:
            if (val === 'nan' || val === 'null' || val === 'None') return '--';
            return val || '--';
    }
}

// Get cell style based on column type and value
function getCellStyle(col, product) {
    const raw = product[col.key];
    if (col.key === 'bounce_rate' && raw != null && Number(raw) > 0.8) return 'color:var(--danger);font-weight:600';
    if (col.key === 'conversion' && raw != null && Number(raw) < 0.03) return 'color:var(--danger);font-weight:600';
    if (col.key === 'search_ratio' && raw != null && Number(raw) < 0.2) return 'color:var(--warning)';
    if (col.key === 'refund_rate' && raw != null && Number(raw) > 0.2) return 'color:var(--danger);font-weight:600';
    return '';
}

async function loadProducts(dim, period) {
    setLoading('loading-table', true);
    const sort = STATE.sortKey || 'payment_amount';
    const order = STATE.sortOrder || 'desc';
    const offset = (STATE.page - 1) * STATE.pageSize;
    const res = await apiFetch(`/api/products?dim=${dim}&period=${period}&limit=${STATE.pageSize}&offset=${offset}&sort=${sort}&order=${order}`);
    setLoading('loading-table', false);
    // 兼容新旧响应格式：旧格式为数组，新格式为 {data, total}
    const data = Array.isArray(res) ? res : (res.data || []);
    const total = res.total || data.length;
    STATE.totalProducts = total;
    if (!data || data.length === 0) { return; }

    STATE.productData = data;

    // 填充风格筛选下拉
    populateStyleFilter(data);

    // 预加载每个商品的最近运营动作
    loadProductActions(data);

    // --- 商品表格 ---
    renderProductTable();
    syncURL();

    // 加载商品画像标签
    loadProductTags();
}

// 预加载商品运营动作（批量获取）
async function loadProductActions(products) {
    const data = await apiFetch(`/api/actions?dim=${STATE.dim}&period=${STATE.period}&limit=200`);
    if (!data || !Array.isArray(data)) return;

    // 按 product_id 分组，取每个商品最近一条
    const actionMap = {};
    data.forEach(a => {
        const pid = a.product_id;
        if (!pid) return;
        if (!actionMap[pid] || (a.action_date || '') > (actionMap[pid].date || '')) {
            actionMap[pid] = {
                type: a.action_type || '--',
                date: a.action_date || '--',
                detail: a.action_detail || '',
                score: a.effectiveness_score,
                id: a.id,
            };
        }
    });

    // 将最近动作附加到商品数据
    products.forEach(p => {
        p._last_action = actionMap[p.product_id] || null;
    });
}

// 点击"添加动作"→ 变成下拉（预设+自定义），选中即保存
// 点击"✎"→ 编辑已有动作（可改类型、备注、删除）
function startEditAction(productId, isEdit) {
    const tr = document.querySelector(`#productTableBody tr[data-pid="${productId}"]`);
    if (!tr) return;
    const td = tr.querySelector('.td-action');
    if (!td) return;
    const div = td.querySelector('.inline-action');
    if (!div) return;

    const product = (STATE.productData || []).find(p => p.product_id === productId);
    const lastAction = product ? product._last_action : null;
    const editType = (isEdit && lastAction) ? lastAction.type : '';
    const editDetail = (isEdit && lastAction) ? (lastAction.detail || '') : '';

    div.innerHTML = `
        <div class="action-edit-row">
            <select class="action-quick-select" id="aq-sel-${productId}" onchange="onActionSelect('${productId}')">
                <option value="">选择动作...</option>
                <option value="加价" ${editType==='加价'?'selected':''}>加价</option>
                <option value="减价" ${editType==='减价'?'selected':''}>减价</option>
                <option value="换图" ${editType==='换图'?'selected':''}>换图</option>
                <option value="换标题" ${editType==='换标题'?'selected':''}>换标题</option>
                <option value="加SKU" ${editType==='加SKU'?'selected':''}>加SKU</option>
                <option value="优化主图" ${editType==='优化主图'?'selected':''}>优化主图</option>
                <option value="优化详情" ${editType==='优化详情'?'selected':''}>优化详情</option>
                <option value="报名活动" ${editType==='报名活动'?'selected':''}>报名活动</option>
                <option value="__custom__" ${editType && !['加价','减价','换图','换标题','加SKU','优化主图','优化详情','报名活动'].includes(editType)?'selected':''}>自定义...</option>
            </select>
            <input type="text" class="action-custom-input" id="aq-custom-${productId}"
                placeholder="输入自定义动作"
                value="${editType && !['加价','减价','换图','换标题','加SKU','优化主图','优化详情','报名活动'].includes(editType) ? editType : ''}"
                style="display:${editType && !['加价','减价','换图','换标题','加SKU','优化主图','优化详情','报名活动'].includes(editType) ? 'inline-block' : 'none'}">
        </div>
        <div class="action-edit-row" style="margin-top:4px;">
            <input type="text" class="action-detail-input" id="aq-detail-${productId}"
                placeholder="备注（可选）" value="${editDetail}">
            <button class="action-btn save" onclick="saveActionEdit('${productId}')">保存</button>
            <button class="action-btn cancel" onclick="cancelEditAction('${productId}')">取消</button>
            ${isEdit && lastAction && lastAction.id ? `<button class="action-btn del" onclick="deleteAction('${productId}', ${lastAction.id})" title="删除">删除</button>` : ''}
        </div>
    `;
    div.querySelector('.action-quick-select').focus();
}

// 选"自定义..."时显示输入框
function onActionSelect(productId) {
    const sel = document.getElementById(`aq-sel-${productId}`);
    const custom = document.getElementById(`aq-custom-${productId}`);
    if (sel.value === '__custom__') {
        custom.style.display = 'inline-block';
        custom.focus();
    } else {
        custom.style.display = 'none';
    }
}

// 保存动作
async function saveActionEdit(productId) {
    const sel = document.getElementById(`aq-sel-${productId}`);
    const custom = document.getElementById(`aq-custom-${productId}`);
    const detail = document.getElementById(`aq-detail-${productId}`);

    let type = sel.value;
    if (type === '__custom__') {
        type = (custom.value || '').trim();
        if (!type) { showToast('请输入自定义动作', 'error'); custom.focus(); return; }
    }
    if (!type) { showToast('请选择动作类型', 'error'); sel.focus(); return; }

    const payload = {
        product_id: productId,
        action_date: new Date().toISOString().split('T')[0],
        action_type: type,
        action_detail: (detail.value || '').trim() || null,
    };

    try {
        const resp = await fetch('/api/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        showToast(`${type} 已记录`, 'success');
        // 局部更新：只更新该商品的_last_action，不重建整个表格
        const product = (STATE.productData || []).find(p => p.product_id === productId);
        if (product) {
            product._last_action = {
                type: type,
                date: payload.action_date,
                detail: payload.action_detail || '',
                score: null,
                id: result.id,
            };
        }
        updateActionCell(productId);
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

// 删除动作
async function deleteAction(productId, actionId) {
    try {
        const resp = await fetch(`/api/actions/${actionId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        showToast('动作已删除', 'success');
        // 局部更新：清除该商品的_last_action
        const product = (STATE.productData || []).find(p => p.product_id === productId);
        if (product) product._last_action = null;
        updateActionCell(productId);
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    }
}

// 局部更新单个商品的动作单元格（不重建整个表格）
function updateActionCell(productId) {
    const product = (STATE.productData || []).find(p => p.product_id === productId);
    if (!product) return;
    const lastAction = product._last_action;
    const tr = document.querySelector(`#productTableBody tr[data-pid="${productId}"]`);
    if (!tr) return;
    const td = tr.querySelector('.td-action');
    if (!td) return;
    const div = td.querySelector('.inline-action');
    if (!div) return;

    if (lastAction) {
        const scoreBadge = lastAction.score != null
            ? `<span class="action-score ${lastAction.score > 60 ? 'high' : lastAction.score >= 30 ? 'medium' : 'low'}">${lastAction.score.toFixed(0)}</span>`
            : '';
        div.innerHTML = `<div class="inline-action-summary">
            <span class="action-type-tag">${lastAction.type}</span>
            <span class="action-date">${lastAction.date}</span>
            ${scoreBadge}
            <span class="action-change" onclick="event.stopPropagation();startEditAction('${productId}', true)" title="编辑动作">✎</span>
        </div>`;
    } else {
        div.innerHTML = `<div class="inline-action-empty" onclick="startEditAction('${productId}')">
            <span class="action-add-icon">＋</span> 添加动作
        </div>`;
    }
}

// 合计行
function renderSummaryRow(pageData, visibleCols) {
    const existing = document.querySelector('.tfoot-summary');
    if (existing) existing.remove();
    if (!pageData || pageData.length === 0) return;

    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');
    const sums = {};
    metricCols.forEach(col => {
        if (col.type === 'number' || col.type === 'money') {
            sums[col.key] = pageData.reduce((s, p) => s + (Number(p[col.key]) || 0), 0);
        }
    });

    const fmt = (v) => {
        if (v == null || isNaN(v)) return '--';
        if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + '万';
        return v.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
    };

    let cells = '<td></td><td>合计 (' + pageData.length + '款)</td>';
    metricCols.forEach(col => {
        if (sums[col.key] !== undefined) {
            cells += `<td class="text-right">${fmt(sums[col.key])}</td>`;
        } else {
            cells += '<td></td>';
        }
    });

    const tbody = document.getElementById('productTableBody');
    const tfoot = document.createElement('tfoot');
    tfoot.className = 'tfoot-summary';
    tfoot.innerHTML = `<tr>${cells}</tr>`;
    tbody.parentNode.appendChild(tfoot);
}

// 重置筛选
function resetFilters() {
    document.getElementById('productSearch').value = '';
    document.getElementById('productTierFilter').value = '';
    document.getElementById('productStyleFilter').value = '';
    document.getElementById('productStatusFilter').value = '';
    STATE.searchText = '';
    STATE.tierFilter = '';
    STATE.styleFilter = '';
    STATE.statusFilter = '';
    updateFilterChips();
    applyTableFilters();
}

// 筛选条件Chips
function updateFilterChips() {
    const container = document.getElementById('filterChips');
    if (!container) return;
    const chips = [];
    const search = document.getElementById('productSearch').value.trim();
    const tier = document.getElementById('productTierFilter').value;
    const style = document.getElementById('productStyleFilter').value;
    const status = document.getElementById('productStatusFilter').value;

    if (search) chips.push({ label: '搜索:' + search, clear: () => { document.getElementById('productSearch').value = ''; STATE.searchText = ''; } });
    if (tier) chips.push({ label: '分层:' + tier, clear: () => { document.getElementById('productTierFilter').value = ''; STATE.tierFilter = ''; } });
    if (style) chips.push({ label: '风格:' + style, clear: () => { document.getElementById('productStyleFilter').value = ''; STATE.styleFilter = ''; } });
    if (status) {
        const statusLabel = status === 'active' ? '在售' : '下架';
        chips.push({ label: '状态:' + statusLabel, clear: () => { document.getElementById('productStatusFilter').value = ''; STATE.statusFilter = ''; } });
    }

    if (chips.length === 0) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';
    container.innerHTML = chips.map((c, i) =>
        `<span class="filter-chip">${c.label}<span class="chip-remove" onclick="clearFilterChip(${i})">x</span></span>`
    ).join('');
    // 存储clear函数
    container._chips = chips;
}

function clearFilterChip(idx) {
    const container = document.getElementById('filterChips');
    if (container && container._chips && container._chips[idx]) {
        container._chips[idx].clear();
        updateFilterChips();
        applyTableFilters();
    }
}

// 星标收藏
async function toggleStar(productId, el) {
    const res = await apiFetch('/api/star', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
    });
    if (res && res.starred !== undefined) {
        if (res.starred) {
            el.className = 'star-btn starred';
            el.innerHTML = '&#9733;';
            el.title = '取消收藏';
            showToast('已收藏', 'success', 1500);
        } else {
            el.className = 'star-btn';
            el.innerHTML = '&#9734;';
            el.title = '收藏';
            showToast('已取消收藏', 'info', 1500);
        }
        if (STATE.productData) {
            const item = STATE.productData.find(p => p.product_id === productId);
            if (item) item.starred = res.starred;
        }
    }
}

// 空数据列自动隐藏
function autoHideEmptyColumns(pageData, visibleCols) {
    if (!pageData || pageData.length === 0) return;
    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title' && c.key !== 'rank' && c.key !== 'action');
    metricCols.forEach(col => {
        const allEmpty = pageData.every(p => {
            const v = p[col.key];
            return v === null || v === undefined || v === 0 || v === '0' || v === '--' || v === 'nan';
        });
        const ths = document.querySelectorAll(`th[data-col="${col.key}"]`);
        ths.forEach(th => th.style.display = allEmpty ? 'none' : '');
        const tds = document.querySelectorAll(`td[data-col="${col.key}"]`);
        tds.forEach(td => td.style.display = allEmpty ? 'none' : '');
    });
}

// 批量勾选
function toggleSelectAll(checked) {
    document.querySelectorAll('.row-check').forEach(cb => cb.checked = checked);
    updateBatchBar();
}

function updateSelectAll() {
    const all = document.querySelectorAll('.row-check');
    const checked = document.querySelectorAll('.row-check:checked');
    const selectAll = document.getElementById('selectAll');
    if (selectAll) selectAll.checked = all.length > 0 && all.length === checked.length;
    updateBatchBar();
}

function getSelectedIds() {
    return Array.from(document.querySelectorAll('.row-check:checked')).map(cb => cb.value);
}

function updateBatchBar() {
    const ids = getSelectedIds();
    const bar = document.getElementById('batchBar');
    if (!bar) return;
    if (ids.length === 0) {
        bar.style.display = 'none';
    } else {
        bar.style.display = 'flex';
        bar.querySelector('.batch-count').textContent = `已选 ${ids.length} 项`;
    }
}

function batchStar() {
    const ids = getSelectedIds();
    if (ids.length === 0) return;
    Promise.all(ids.map(pid =>
        apiFetch('/api/star', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: pid })
        })
    )).then(() => {
        if (STATE.productData) {
            STATE.productData.forEach(p => {
                if (ids.includes(p.product_id)) p.starred = 1;
            });
        }
        applyTableFilters();
        document.querySelectorAll('.row-check').forEach(cb => cb.checked = false);
        updateBatchBar();
        showToast(`已收藏 ${ids.length} 件商品`, 'success', 2000);
    }).catch(function(e) {
        showToast('批量收藏失败: ' + (e.message || '未知错误'), 'error');
    });
}

function batchEditField(field) {
    const ids = getSelectedIds();
    if (ids.length === 0) { showToast('请先勾选商品', 'warning'); return; }
    const options = field === 'tier'
        ? ['利润款', '引流款', '新品', '新品主推']
        : ['中古风', 'IP', '乔迁', '奶油', '轻奢'];
    const label = field === 'tier' ? '分层' : '风格';
    // 创建内联选择弹窗
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.style.display = 'flex';
    overlay.innerHTML = `
        <div style="background:var(--bg-card);border-radius:12px;padding:24px;min-width:300px;box-shadow:0 8px 32px rgba(0,0,0,0.4);">
            <h3 style="margin-bottom:16px;color:var(--text-primary);">批量修改${label}（${ids.length}件）</h3>
            <select id="batchEditSelect" style="width:100%;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);font-size:0.9rem;margin-bottom:16px;">
                <option value="">请选择${label}</option>
                ${options.map(o => `<option value="${o}">${o}</option>`).join('')}
            </select>
            <div style="display:flex;gap:8px;justify-content:flex-end;">
                <button onclick="this.closest('.modal-overlay').remove()" style="padding:6px 16px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);cursor:pointer;">取消</button>
                <button onclick="confirmBatchEdit('${field}', ${JSON.stringify(ids)})" style="padding:6px 16px;border-radius:6px;border:none;background:var(--accent);color:#fff;cursor:pointer;">确认</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
}

async function confirmBatchEdit(field, ids) {
    const val = document.getElementById('batchEditSelect').value;
    if (!val) { showToast('请选择一个值', 'warning'); return; }
    const res = await apiFetch('/api/batch_update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field, value: val, product_ids: ids })
    });
    if (res && res.success) {
        showToast(`已更新 ${ids.length} 件商品`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        loadProducts(STATE.dim, STATE.period);
    } else {
        showToast('更新失败', 'error');
    }
}

// 只看收藏筛选
function toggleStarFilter() {
    STATE.starFilter = !STATE.starFilter;
    const btn = document.getElementById('starFilterBtn');
    if (STATE.starFilter) {
        btn.classList.add('active');
        btn.innerHTML = '&#9733; 只看收藏';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '&#9734; 只看收藏';
    }
    applyTableFilters();
}

// 取消编辑
function cancelEditAction(productId) {
    const product = (STATE.productData || []).find(p => p.product_id === productId);
    const lastAction = product ? product._last_action : null;
    const div = document.querySelector(`#productTableBody tr .td-action .inline-action`);
    if (!div) return;

    if (lastAction) {
        const scoreBadge = lastAction.score != null
            ? `<span class="action-score ${lastAction.score > 60 ? 'high' : lastAction.score >= 30 ? 'medium' : 'low'}">${lastAction.score.toFixed(0)}</span>`
            : '';
        div.innerHTML = `<div class="inline-action-summary">
            <span class="action-type-tag">${lastAction.type}</span>
            <span class="action-date">${lastAction.date}</span>
            ${scoreBadge}
            <span class="action-change" onclick="event.stopPropagation();startEditAction('${productId}', true)" title="编辑动作">✎</span>
        </div>`;
    } else {
        div.innerHTML = `<div class="inline-action-empty" onclick="startEditAction('${productId}')">
            <span class="action-add-icon">＋</span> 添加动作
        </div>`;
    }
}

// 行展开详情
function toggleRowDetail(pid, tr) {
    const detail = document.getElementById('detail-' + pid);
    if (!detail) return;
    const isVisible = detail.style.display !== 'none';
    // 关闭所有其他详情行
    document.querySelectorAll('.detail-row').forEach(r => r.style.display = 'none');
    if (!isVisible) {
        detail.style.display = 'table-row';
        // 加载备注
        loadProductNotes(pid);
    }
}

async function loadProductNotes(productId) {
    const listEl = document.getElementById('notes-list-' + productId);
    if (!listEl) return;
    try {
        const notes = await apiFetch(`/api/notes/${productId}`);
        if (!notes || !Array.isArray(notes)) {
            listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">暂无备注</div>';
            return;
        }
        if (notes.length === 0) {
            listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">暂无备注</div>';
            return;
        }
        listEl.innerHTML = notes.map(n => `
            <div class="note-item">
                <span class="note-text">${escapeHtml(n.note)}</span>
                <span class="note-time">${n.created_at || ''}</span>
                <span class="note-delete" onclick="event.stopPropagation();deleteProductNote(${n.id},'${productId}')" title="删除">&times;</span>
            </div>
        `).join('');
    } catch (e) {
        listEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">加载失败</div>';
    }
}

async function addProductNote(productId) {
    const input = document.getElementById('note-input-' + productId);
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    const res = await apiFetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, note: text })
    });
    if (res && res.success) {
        input.value = '';
        loadProductNotes(productId);
    } else {
        showToast('添加备注失败', 'error');
    }
}

async function deleteProductNote(noteId, productId) {
    const res = await apiFetch(`/api/notes/${noteId}`, { method: 'DELETE' });
    if (res && res.success) {
        loadProductNotes(productId);
    } else {
        showToast('删除备注失败', 'error');
    }
}

function buildRowDetailContent(p) {
    const items = [
        { label: '支付金额', value: fmtWan(p.payment_amount) },
        { label: '支付件数', value: fmtNum(p.payment_count) },
        { label: '访客数', value: fmtNum(p.visitors) },
        { label: '转化率', value: fmtPct(p.conversion) },
        { label: '客单价', value: fmtWan(p.avg_order_value) },
        { label: 'ROI', value: p.roi != null ? Number(p.roi).toFixed(2) : '--' },
        { label: '推广花费', value: fmtWan(p.ad_spend) },
        { label: '退款率', value: fmtPct(p.refund_rate) },
        { label: '退款金额', value: fmtWan(p.refund_amount) },
        { label: '加购率', value: fmtPct(p.cart_rate) },
        { label: '收藏率', value: fmtPct(p.fav_rate) },
        { label: '搜索占比', value: fmtPct(p.search_ratio) },
        { label: '浏览量', value: fmtNum(p.page_views) },
        { label: '净销售额', value: fmtWan(p.net_sales) },
        { label: '分层', value: p.tier || '--' },
        { label: '风格', value: p.style || '--' },
    ];
    const metricsHtml = items.map(item =>
        `<div class="row-detail-item"><span class="row-detail-label">${item.label}</span><span class="row-detail-value">${item.value}</span></div>`
    ).join('');

    // 备注区域
    const notesHtml = `
        <div class="product-notes-section" style="grid-column: 1 / -1; border-top: 1px solid var(--border); padding-top: 12px; margin-top: 4px;">
            <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">商品备注</div>
            <div id="notes-list-${p.product_id}" class="notes-list">
                <div style="color:var(--text-muted);font-size:0.8rem;">加载中...</div>
            </div>
            <div class="note-input-row">
                <input type="text" id="note-input-${p.product_id}" aria-label="为${title}添加备注" placeholder="添加备注..." onkeydown="if(event.key==='Enter')addProductNote('${p.product_id}')">
                <button onclick="addProductNote('${p.product_id}')" style="padding:4px 12px;border-radius:4px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-size:0.8rem;">添加</button>
            </div>
        </div>
    `;

    return metricsHtml + notesHtml;
}

/**
 * 构建单行商品表格行 HTML
 * @param {Object} p - 商品数据对象
 * @param {number} rank - 当前排名序号
 * @param {Array} metricCols - 指标列配置数组
 * @param {Array} visibleCols - 可见列配置数组（保留参数，便于扩展）
 * @returns {string} <tr>...</tr> HTML 字符串
 */
function buildProductRow(p, rank, metricCols, visibleCols) {
    // Top3色标
    let rankHtml;
    if (rank === 1) rankHtml = '<span class="rank-badge rank-1">1</span>';
    else if (rank === 2) rankHtml = '<span class="rank-badge rank-2">2</span>';
    else if (rank === 3) rankHtml = '<span class="rank-badge rank-3">3</span>';
    else rankHtml = `<span class="rank-badge rank-normal">${rank}</span>`;

    const imgUrl = p.image_url || '';
    const title = escapeHtml(p.title || '--');
    const shortTitle = title.length > 14 ? title.substring(0, 14) + '...' : title;
    const pid = (p.product_id || '').replace(/'/g, "\\'");
    const isStarred = p.starred == 1;
    const starIcon = isStarred ? '<span class="star-btn starred" onclick="event.stopPropagation();toggleStar(\'' + pid + '\',this)" title="取消收藏">&#9733;</span>' : '<span class="star-btn" onclick="event.stopPropagation();toggleStar(\'' + pid + '\',this)" title="收藏">&#9734;</span>';
    // 商品画像标签
    const tagColors = {'爆款':'#EF4444','潜力款':'#3B82F6','衰退款':'#F59E0B','滞销款':'#6B7280','高退款':'#DC2626','高ROI':'#10B981'};
    const tags = p._tags || [];
    const tagBadges = tags.map(t => {
        const c = tagColors[t] || '#8B5CF6';
        return `<span class="tag-badge" style="background:${c}">${t}</span>`;
    }).join('');
    const addTagBtn = `<span class="tag-add-btn" onclick="event.stopPropagation();showAddTagDialog('${pid}')" title="添加标签">+</span>`;
    const tagsHtml = tagBadges ? `<div class="tag-badges-row">${tagBadges}${addTagBtn}</div>` : `<div class="tag-badges-row">${addTagBtn}</div>`;
    const productCell = `<td class="td-product"><div class="product-cell-inner">${starIcon}${imgUrl ? `<img src="${imgUrl}" alt="${title}" loading="lazy" onerror="this.style.display='none'">` : '<div class="product-img-placeholder" aria-hidden="true">📦</div>'}<div class="product-info"><span class="product-title-text" title="${title}">${shortTitle}</span><span class="product-id-text">${escapeHtml(p.product_id || '--')}</span>${tagsHtml}</div></div></td>`;

    const cells = metricCols.map(col => {
        const style = getCellStyle(col, p);
        const value = formatCellValue(col, p);
        const rawVal = p[col.key];
        const alignCls = (col.type === 'money' || col.type === 'number' || col.type === 'percent' || col.type === 'decimal') ? ' text-right' : '';
        // 运营动作列：点击即编辑，一步保存
        if (col.key === 'action') {
            const lastAction = p._last_action || null;
            let actionHtml = '<td class="td-action" data-col="action"><div class="inline-action">';
            if (lastAction) {
                const scoreBadge = lastAction.score != null
                    ? `<span class="action-score ${lastAction.score > 60 ? 'high' : lastAction.score >= 30 ? 'medium' : 'low'}">${lastAction.score.toFixed(0)}</span>`
                    : '';
                actionHtml += `<div class="inline-action-summary">
                    <span class="action-type-tag">${lastAction.type}</span>
                    <span class="action-date">${lastAction.date}</span>
                    ${scoreBadge}
                    <span class="action-change" onclick="event.stopPropagation();startEditAction('${pid}')" title="更换动作">✎</span>
                </div>`;
            } else {
                actionHtml += `<div class="inline-action-empty" onclick="event.stopPropagation();startEditAction('${pid}')">
                    <span class="action-add-icon">＋</span> 添加动作
                </div>`;
            }
            actionHtml += '</div></td>';
            return actionHtml;
        }
        // 评分列用圆形徽章（综合评分0-100）
        if (col.key === 'score' && rawVal != null && !isNaN(rawVal)) {
            const scoreVal = Number(rawVal);
            const badgeColor = scoreVal >= 80 ? '#22C55E' : scoreVal >= 60 ? '#3B82F6' : scoreVal >= 40 ? '#F59E0B' : '#EF4444';
            return `<td class="text-right" data-col="${col.key}"><span class="score-badge-circle" style="background:${badgeColor}">${scoreVal}</span></td>`;
        }
        // 百分比列用迷你进度条
        if (col.type === 'percent' && rawVal != null && !isNaN(rawVal)) {
            const pctVal = Number(rawVal) * 100;
            const barColor = pctVal > 10 ? '#22C55E' : pctVal > 3 ? '#3B82F6' : pctVal > 0 ? '#F59E0B' : '#475569';
            let cellHtml = `<td class="text-right" data-col="${col.key}"><div class="cell-with-bar"><span>${value}</span><div class="mini-bar"><div class="mini-bar-fill" style="width:${Math.min(pctVal, 100)}%;background:${barColor}"></div></div></div>`;
            // 月度维度下显示环比变化
            if (STATE.dim === 'monthly' && p.changes) {
                const changeKeyMap = { 'payment_amount': 'payment_amount', 'visitors': 'visitors', 'conversion': 'payment_conversion', 'refund_rate': 'refund_rate', 'uv_value': 'uv_value' };
                const changeKey = changeKeyMap[col.key];
                if (changeKey) {
                    const changeVal = p.changes[changeKey];
                    if (changeVal !== null && changeVal !== undefined) {
                        const cls = changeVal > 0 ? 'change-up' : changeVal < 0 ? 'change-down' : 'change-flat';
                        const arrow = changeVal > 0 ? '\u2191' : changeVal < 0 ? '\u2193' : '\u2192';
                        cellHtml += `<span class="change-tag ${cls}">${arrow}${Math.abs(changeVal)}%</span>`;
                    }
                }
            }
            cellHtml += '</div></td>';
            return cellHtml;
        }
        // 通用单元格：月度维度下为关键指标添加环比变化
        let cellContent = value;
        if (STATE.dim === 'monthly' && p.changes) {
            const changeKeyMap = { 'payment_amount': 'payment_amount', 'visitors': 'visitors', 'conversion': 'payment_conversion', 'refund_rate': 'refund_rate', 'uv_value': 'uv_value' };
            const changeKey = changeKeyMap[col.key];
            if (changeKey) {
                const changeVal = p.changes[changeKey];
                if (changeVal !== null && changeVal !== undefined) {
                    const cls = changeVal > 0 ? 'change-up' : changeVal < 0 ? 'change-down' : 'change-flat';
                    const arrow = changeVal > 0 ? '\u2191' : changeVal < 0 ? '\u2193' : '\u2192';
                    cellContent += `<span class="change-tag ${cls}">${arrow}${Math.abs(changeVal)}%</span>`;
                }
            }
        }
        return `<td class="${alignCls}" data-col="${col.key}" style="${style}">${cellContent}</td>`;
    }).join('');

    return `<tr data-pid="${p.product_id}" role="button" tabindex="0" aria-label="查看${title}商品详情" onclick="toggleRowDetail('${p.product_id}', this)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleRowDetail('${p.product_id}', this)}" style="cursor:pointer"><td class="td-rank">${rankHtml}<input type="checkbox" class="row-check" aria-label="选择${title}" value="${p.product_id}" onchange="updateSelectAll()" onclick="event.stopPropagation()"></td>${productCell}${cells}</tr>` +
        `<tr class="detail-row" id="detail-${p.product_id}" style="display:none"><td colspan="99"><div class="row-detail-content">${buildRowDetailContent(p)}</div></td></tr>`;
}

function normalizeProductTableHeader(visibleCols) {
    const table = document.getElementById('productTable');
    const thead = document.getElementById('productTableHead');
    if (!table || !thead) return;

    const rows = thead.querySelectorAll('tr');
    if (rows.length < 2) return;
    const groupRow = rows[0];
    const headerRow = rows[1];
    const frozenGroupCells = Array.from(groupRow.children).slice(0, 2);
    const frozenHeaderCells = Array.from(headerRow.children).slice(0, 2);

    // The first two cells are structural columns, so they must span both rows.
    frozenGroupCells.forEach((cell, index) => {
        cell.rowSpan = 2;
        cell.dataset.col = index === 0 ? 'rank' : 'product';
        if (frozenHeaderCells[index]) {
            const checkbox = frozenHeaderCells[index].querySelector('input');
            if (checkbox && index === 0 && !cell.querySelector('input')) cell.appendChild(checkbox);
            frozenHeaderCells[index].remove();
        }
    });

    const metricCols = visibleCols.filter(col => col.key !== 'image' && col.key !== 'title');
    const oldColgroup = table.querySelector(':scope > colgroup');
    if (oldColgroup) oldColgroup.remove();
    const colgroup = document.createElement('colgroup');
    const rankCol = document.createElement('col');
    rankCol.className = 'col-rank';
    rankCol.style.width = 'var(--product-rank-width)';
    const productCol = document.createElement('col');
    productCol.className = 'col-product';
    productCol.style.width = 'var(--product-info-width)';
    colgroup.append(rankCol, productCol);
    metricCols.forEach(col => {
        const metricCol = document.createElement('col');
        metricCol.dataset.col = col.key;
        metricCol.style.width = col.key === 'action' ? '190px' : '108px';
        colgroup.appendChild(metricCol);
    });
    table.insertBefore(colgroup, thead);
}

function renderProductTable() {
    const { productData, sortKey, sortOrder, page, pageSize } = STATE;
    const visibleCols = getVisibleColumns();

    // 服务端分页：数据已经是当前页的数据，无需客户端排序/切片
    const total = STATE.totalProducts || productData.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const startIdx = (page - 1) * pageSize;
    const pageData = productData;

    // ---- 双层表头 ----
    const thead = document.getElementById('productTableHead');
    if (thead) {
        // 分组色带行 + 列头行
        const groupColors = {
            '基础信息': 'rgba(148,163,184,0.08)',
            '流量指标': 'rgba(236,72,153,0.08)',
            '转化指标': 'rgba(236,72,153,0.12)',
            '交易指标': 'rgba(59,130,246,0.08)',
            '退款指标': 'rgba(239,68,68,0.08)',
            '推广指标': 'rgba(59,130,246,0.12)',
            '付费报表': 'rgba(99,102,241,0.08)',
            '客户指标': 'rgba(16,185,129,0.08)',
            '引潜指标': 'rgba(245,158,11,0.08)',
            '评分': 'rgba(139,92,246,0.08)',
        };

        // 构建分组行和列头行
        let groupRowHtml = '<th class="th-rank th-sticky-left-1">全选</th><th class="th-product th-sticky-left-2">商品信息</th>';
        let headerRowHtml = '<th class="th-sticky-left-1"><input type="checkbox" id="selectAll" onchange="toggleSelectAll(this.checked)" title="全选"></th><th class="th-sticky-left-2"></th>';
        let currentGroup = '';
        let groupSpan = 0;

        // 跳过 image 和 title 列（已合并到"商品信息"列）
        const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');

        metricCols.forEach((col, idx) => {
            const isSorted = sortKey === col.key;
            const arrow = isSorted ? (sortOrder === 'asc' ? '▲' : '▼') : '▲▼';
            const sortedCls = isSorted ? ' sorted' : '';
            const alignCls = (col.type === 'money' || col.type === 'number' || col.type === 'percent' || col.type === 'decimal') ? ' text-right' : '';

            // 分组行
            if (col.group !== currentGroup) {
                if (currentGroup && groupSpan > 0) {
                    groupRowHtml += `<th colspan="${groupSpan}" class="th-group" style="background:${groupColors[currentGroup] || 'transparent'}">${currentGroup}</th>`;
                }
                currentGroup = col.group;
                groupSpan = 1;
            } else {
                groupSpan++;
            }

            // 列头行（带排序和筛选图标）
            const filterIcon = (col.type === 'text' && col.key !== 'image') ? '<span class="col-filter-icon" onclick="event.stopPropagation();toggleColFilter(\'' + col.key + '\')">▾</span>' : '';
            headerRowHtml += `<th class="th-col${alignCls}${sortedCls}" data-key="${col.key}" data-col="${col.key}" onclick="sortTable('${col.key}')" style="${currentGroup ? 'border-top:2px solid ' + (groupColors[currentGroup] ? groupColors[currentGroup].replace(/[\d.]+\)$/, '0.25)') : 'transparent') : ''}">${col.label} <span class="sort-arrows">${arrow}</span>${filterIcon}</th>`;
        });
        // 最后一个分组
        if (currentGroup && groupSpan > 0) {
            groupRowHtml += `<th colspan="${groupSpan}" class="th-group" style="background:${groupColors[currentGroup] || 'transparent'}">${currentGroup}</th>`;
        }

        thead.innerHTML = `<tr class="group-row">${groupRowHtml}</tr><tr class="header-row">${headerRowHtml}</tr>`;
        normalizeProductTableHeader(visibleCols);
    }

    // ---- 渲染行 ----
    const tbody = document.getElementById('productTableBody');
    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');
    tbody.innerHTML = pageData.map((p, i) => {
        const rank = startIdx + i + 1;
        return buildProductRow(p, rank, metricCols, visibleCols);
    }).join('');

    // 合计行
    renderSummaryRow(pageData, visibleCols);

    // 空数据列自动隐藏
    // Keep the configured view grid intact. Hiding individual cells leaves
    // colgroup tracks behind and makes a fixed-layout table misalign.

    // 加载更多按钮（追加到表格底部）
    if (page * pageSize < total) {
        var loadMoreRow = document.createElement('tr');
        loadMoreRow.innerHTML = '<td colspan="99" style="text-align:center;padding:12px;"><button class="load-more-btn" onclick="loadMoreProducts()">加载更多（剩余 ' + (total - page * pageSize) + ' 件）</button></td>';
        tbody.appendChild(loadMoreRow);
    }

    // 显示商品总数
    var totalEl = document.getElementById('productTotal');
    if (totalEl) totalEl.textContent = '共 ' + total + ' 件商品';

    // 翻页控件
    const pagEl = document.getElementById('tablePagination');
    pagEl.innerHTML = `
        <button ${page <= 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">上一页</button>
        <span class="page-info">${page} / ${totalPages}（共${total}条）</span>
        <input type="number" class="page-jump" min="1" max="${totalPages}" placeholder="跳转" onkeydown="if(event.key==='Enter')goPage(Math.max(1,Math.min(${totalPages},Number(this.value))))" style="width:52px;padding:3px 6px;border-radius:4px;border:1px solid var(--border);background:var(--bg-card);color:var(--text-primary);font-size:0.78rem;text-align:center;">
        <button ${page >= totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">下一页</button>
    `;

    // 更新排序箭头样式
    document.querySelectorAll('#productTable .header-row th').forEach(th => {
        const key = th.dataset.key;
        const arrows = th.querySelector('.sort-arrows');
        if (!arrows) return;
        if (key === sortKey) {
            th.classList.add('sorted');
            arrows.innerHTML = sortOrder === 'asc' ? '<span class="arrow-active asc">▲</span><span>▼</span>' : '<span>▲</span><span class="arrow-active desc">▼</span>';
        } else {
            th.classList.remove('sorted');
            arrows.innerHTML = '<span>▲</span><span>▼</span>';
        }
    });

    // 初始化列宽拖拽
    initColumnResize();
    // 绑定行内编辑事件
    bindInlineEditEvents();
    // 更新横向滚动指示器
    updateScrollIndicators();
}

// 列筛选弹窗
function toggleColFilter(key) {
    // 收集该列所有唯一值
    const vals = new Set();
    (STATE.productData || []).forEach(p => {
        const v = p[key];
        if (v != null && v !== '') vals.add(v);
    });
    const sorted = [...vals].sort();

    // 移除已有弹窗
    const existing = document.getElementById('colFilterPopup');
    if (existing) existing.remove();

    const th = document.querySelector(`th[data-key="${key}"]`);
    if (!th) return;
    const rect = th.getBoundingClientRect();
    const wrapper = document.querySelector('.table-wrapper');
    const wrapperRect = wrapper.getBoundingClientRect();

    const popup = document.createElement('div');
    popup.id = 'colFilterPopup';
    popup.className = 'col-filter-popup';
    popup.innerHTML = `
        <div class="col-filter-header">
            <input type="text" class="col-filter-search" placeholder="搜索..." oninput="filterColFilterOptions(this.value)">
            <button class="col-filter-clear" onclick="clearColFilter('${key}')">清除筛选</button>
        </div>
        <div class="col-filter-options">
            <label class="col-filter-option"><input type="checkbox" checked onchange="applyColFilter('${key}')"> 全部</label>
            ${sorted.slice(0, 50).map(v => `<label class="col-filter-option"><input type="checkbox" value="${String(v).replace(/"/g, '&quot;')}" onchange="applyColFilter('${key}')"> ${v}</label>`).join('')}
            ${sorted.length > 50 ? `<div style="color:#64748B;font-size:0.75rem;padding:4px 8px;">仅显示前50项...</div>` : ''}
        </div>
    `;
    popup.style.left = (rect.left - wrapperRect.left) + 'px';
    popup.style.top = (rect.bottom - wrapperRect.top + 4) + 'px';
    wrapper.style.position = 'relative';
    wrapper.appendChild(popup);

    // 点击外部关闭
    setTimeout(() => {
        document.addEventListener('click', function closeFilter(e) {
            if (!popup.contains(e.target) && !th.contains(e.target)) {
                popup.remove();
                document.removeEventListener('click', closeFilter);
            }
        });
    }, 10);
}

function filterColFilterOptions(query) {
    const options = document.querySelectorAll('#colFilterPopup .col-filter-option');
    options.forEach(opt => {
        const text = opt.textContent.toLowerCase();
        opt.style.display = text.includes(query.toLowerCase()) ? '' : 'none';
    });
}

function applyColFilter(key) {
    const popup = document.getElementById('colFilterPopup');
    if (!popup) return;
    const checkboxes = popup.querySelectorAll('.col-filter-options input[type="checkbox"]:checked');
    const allCheckbox = popup.querySelector('.col-filter-options input[type="checkbox"]:first-child');
    const values = [];
    checkboxes.forEach(cb => { if (cb !== allCheckbox) values.push(cb.value); });

    if (allCheckbox && allCheckbox.checked) {
        STATE.colFilters = STATE.colFilters || {};
        delete STATE.colFilters[key];
    } else {
        STATE.colFilters = STATE.colFilters || {};
        STATE.colFilters[key] = values;
    }
    STATE.page = 1;
    applyTableFilters();
    popup.remove();
}

function clearColFilter(key) {
    STATE.colFilters = STATE.colFilters || {};
    delete STATE.colFilters[key];
    STATE.page = 1;
    applyTableFilters();
    const popup = document.getElementById('colFilterPopup');
    if (popup) popup.remove();
}

function applyTableFilters() {
    let data = STATE.productData || [];
    const filters = STATE.colFilters || {};
    for (const [key, values] of Object.entries(filters)) {
        if (values && values.length > 0) {
            data = data.filter(p => values.includes(String(p[key] ?? '')));
        }
    }
    // 星标过滤
    if (STATE.starFilter) {
        data = data.filter(p => p.starred == 1);
    }
    updateFilterChips();
    // 重新排序和分页渲染（不重新请求API）
    const { sortKey, sortOrder, page, pageSize } = STATE;
    const sorted = [...data].sort((a, b) => {
        let va = a[sortKey], vb = b[sortKey];
        if (va == null) va = 0;
        if (vb == null) vb = 0;
        if (typeof va === 'string') return sortOrder === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        return sortOrder === 'asc' ? va - vb : vb - va;
    });
    const total = sorted.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    const startIdx = (Math.min(page, totalPages) - 1) * pageSize;
    const pageData = sorted.slice(startIdx, startIdx + pageSize);

    const visibleCols = getVisibleColumns();
    const metricCols = visibleCols.filter(c => c.key !== 'image' && c.key !== 'title');
    const tbody = document.getElementById('productTableBody');
    tbody.innerHTML = pageData.map((p, i) => {
        const rank = startIdx + i + 1;
        return buildProductRow(p, rank, metricCols, visibleCols);
    }).join('');

    renderSummaryRow(pageData, visibleCols);

    const pagEl = document.getElementById('tablePagination');
    pagEl.innerHTML = `
        <button ${page <= 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">上一页</button>
        <span class="page-info">${Math.min(page, totalPages)} / ${totalPages}（共${total}条）</span>
        <button ${page >= totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">下一页</button>
    `;
}

function sortTable(key) {
    if (STATE.sortKey === key) {
        STATE.sortOrder = STATE.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        STATE.sortKey = key;
        STATE.sortOrder = key === 'title' || key === 'style' ? 'asc' : 'desc';
    }
    // Sync to columnConfig
    columnConfig.sortKey = STATE.sortKey;
    columnConfig.sortOrder = STATE.sortOrder;
    saveColumnConfig();
    STATE.page = 1;
    // 服务端排序：重新请求数据
    loadProducts(STATE.dim, STATE.period);
}

function goPage(p) {
    var total = STATE.totalProducts || 0;
    var totalPages = Math.ceil(total / STATE.pageSize);
    if (p < 1) p = 1;
    if (totalPages > 0 && p > totalPages) p = totalPages;
    STATE.page = p;
    loadProducts(STATE.dim, STATE.period);
}

// 加载更多商品（追加到当前表格）
async function loadMoreProducts() {
    STATE.page++;
    var dim = STATE.dim;
    var period = STATE.period;
    var sort = STATE.sortKey || 'payment_amount';
    var order = STATE.sortOrder || 'desc';
    var offset = (STATE.page - 1) * STATE.pageSize;

    var url = '/api/products?dim=' + dim + '&period=' + period + '&limit=' + STATE.pageSize + '&offset=' + offset + '&sort=' + sort + '&order=' + order;
    // 添加现有筛选条件
    var tier = document.getElementById('productTierFilter') ? document.getElementById('productTierFilter').value : '';
    var style = document.getElementById('productStyleFilter') ? document.getElementById('productStyleFilter').value : '';
    var search = document.getElementById('productSearch') ? document.getElementById('productSearch').value : '';
    var status = document.getElementById('productStatusFilter') ? document.getElementById('productStatusFilter').value : '';
    if (tier && tier !== '全部') url += '&tier=' + encodeURIComponent(tier);
    if (style && style !== '全部') url += '&style=' + encodeURIComponent(style);
    if (search) url += '&search=' + encodeURIComponent(search);
    if (status) url += '&status=' + encodeURIComponent(status);

    try {
        var res = await apiFetch(url);
        var data = Array.isArray(res) ? res : (res.data || []);
        // 追加行到现有表格
        var tbody = document.querySelector('#productTableBody');
        if (tbody && data.length > 0) {
            // 移除加载更多按钮行
            var loadMoreBtn = tbody.querySelector('.load-more-btn');
            if (loadMoreBtn) loadMoreBtn.closest('tr').remove();

            var startRank = offset + 1;
            var visibleCols = getVisibleColumns();
            var metricCols = visibleCols.filter(function(c) { return c.key !== 'image' && c.key !== 'title'; });
            data.forEach(function(p, i) {
                var html = buildProductRow(p, startRank + i, metricCols, visibleCols);
                tbody.insertAdjacentHTML('beforeend', html);
            });
            // 追加到 STATE.productData
            STATE.productData = STATE.productData.concat(data);
            bindInlineEditEvents();
            showToast('已加载 ' + data.length + ' 件商品', 'info');

            // 如果还有更多数据，继续显示加载更多按钮
            var total = STATE.totalProducts || 0;
            if (STATE.page * STATE.pageSize < total) {
                var newLoadMoreRow = document.createElement('tr');
                newLoadMoreRow.innerHTML = '<td colspan="99" style="text-align:center;padding:12px;"><button class="load-more-btn" onclick="loadMoreProducts()">加载更多（剩余 ' + (total - STATE.page * STATE.pageSize) + ' 件）</button></td>';
                tbody.appendChild(newLoadMoreRow);
            }
            // 更新翻页控件
            var totalPages = Math.max(1, Math.ceil(total / STATE.pageSize));
            var pagEl = document.getElementById('tablePagination');
            pagEl.innerHTML = '<button disabled>上一页</button><span class="page-info">已加载 ' + STATE.productData.length + ' / ' + total + ' 条</span><button disabled>下一页</button>';
        } else {
            showToast('没有更多数据了', 'info');
        }
    } catch(e) {
        console.error('加载更多失败:', e);
        showToast('加载失败', 'error');
    }
}

/* ================================================================
   商品搜索/筛选
================================================================ */
let _searchTimer = null;

function debounceSearch() {
    const val = document.getElementById('productSearch').value;
    const clearBtn = document.getElementById('searchClear');
    if (clearBtn) clearBtn.style.display = val ? 'flex' : 'none';
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => filterProducts(), 300);
}

function clearSearch() {
    const input = document.getElementById('productSearch');
    input.value = '';
    const clearBtn = document.getElementById('searchClear');
    if (clearBtn) clearBtn.style.display = 'none';
    filterProducts();
}

function filterProducts() {
    const search = document.getElementById('productSearch').value.trim();
    const tier = document.getElementById('productTierFilter').value;
    const style = document.getElementById('productStyleFilter').value;
    const status = document.getElementById('productStatusFilter').value;
    STATE.page = 1;
    loadFilteredProducts(search, tier, style, status);
    syncURL();
}

async function loadFilteredProducts(search, tier, style, status) {
    setLoading('loading-table', true);

    const sort = STATE.sortKey || 'payment_amount';
    const order = STATE.sortOrder || 'desc';
    const offset = (STATE.page - 1) * STATE.pageSize;
    let url = `/api/products?dim=${STATE.dim}&period=${STATE.period}&limit=${STATE.pageSize}&offset=${offset}&sort=${sort}&order=${order}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (tier) url += `&tier=${encodeURIComponent(tier)}`;
    if (style) url += `&style=${encodeURIComponent(style)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;

    const res = await apiFetch(url);
    setLoading('loading-table', false);

    // 兼容新旧响应格式
    const data = Array.isArray(res) ? res : (res.data || []);
    const total = res.total || data.length;
    STATE.totalProducts = total;

    if (!data || data.length === 0) {
        STATE.productData = [];
        renderProductTable();
        return;
    }

    STATE.productData = data;
    loadProductActions(data);
    renderProductTable();
}

function populateStyleFilter(data) {
    const styles = new Set();
    const tiers = new Set();
    (data || []).forEach(p => {
        if (p.style) styles.add(p.style);
        if (p.tier) tiers.add(p.tier);
    });

    // 填充分层筛选
    const tierSel = document.getElementById('productTierFilter');
    if (tierSel) {
        const current = tierSel.value;
        tierSel.innerHTML = '<option value="">全部分层</option>';
        [...tiers].filter(t => t && t !== 'nan' && t !== 'null' && t !== 'None').sort().forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            tierSel.appendChild(opt);
        });
        tierSel.value = current;
    }

    // 填充风格筛选
    const sel = document.getElementById('productStyleFilter');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">全部风格</option>';
    [...styles].filter(s => s && s !== 'nan' && s !== 'null' && s !== 'None' && s !== '--').sort().forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        sel.appendChild(opt);
    });
    sel.value = current;
}

/* ================================================================
   初始化: 加载列配置
================================================================ */
// Call loadColumnConfig on script load so config is ready before first render
loadColumnConfig();

/* ================================================================
   商品详情弹窗
================================================================ */
function showProductDetail(product) {
    const popup = document.getElementById('productDetailPopup');
    const imgEl = document.getElementById('detailProductImg');
    const nameEl = document.getElementById('detailProductName');
    const metricsEl = document.getElementById('detailProductMetrics');

    if (!popup) return;

    // 设置图片和名称
    imgEl.src = product.image_url || '';
    imgEl.style.display = product.image_url ? 'block' : 'none';
    nameEl.textContent = product.title || '未知商品';

    // 设置指标
    const metrics = [
        { label: '支付金额', value: fmtWan(product.payment_amount) },
        { label: '支付件数', value: fmtNum(product.payment_count) },
        { label: '访客数', value: fmtNum(product.visitors) },
        { label: '转化率', value: fmtPct(product.conversion) },
        { label: '推广花费', value: fmtWan(product.ad_spend) },
        { label: 'ROI', value: product.roi != null ? Number(product.roi).toFixed(2) : '--' },
        { label: '退款率', value: fmtPct(product.refund_rate) },
        { label: '退款金额', value: fmtWan(product.refund_amount) },
    ];

    metricsEl.innerHTML = metrics.map(m => `
        <div class="detail-metric">
            <div class="detail-metric-label">${m.label}</div>
            <div class="detail-metric-value">${m.value}</div>
        </div>
    `).join('');

    popup.classList.add('open');
}

function closeProductDetail() {
    const popup = document.getElementById('productDetailPopup');
    if (popup) popup.classList.remove('open');
}

/* ================================================================
   批量打标签
================================================================ */
function openBatchTagPopover() {
    const ids = getSelectedIds();
    if (ids.length === 0) { showToast('请先勾选商品', 'warning'); return; }

    const popover = document.getElementById('batchTagPopover');
    if (popover) {
        popover.style.display = 'block';
        // 加载已有标签
        loadExistingTags(ids);
    }
}

function closeBatchTagPopover() {
    const popover = document.getElementById('batchTagPopover');
    if (popover) popover.style.display = 'none';
}

async function loadExistingTags(productIds) {
    const existingSection = document.getElementById('batchTagExisting');
    const tagList = document.getElementById('batchTagList');
    if (!existingSection || !tagList) return;

    const tags = await apiFetch(`/api/product_tags?product_ids=${productIds.join(',')}`);
    if (!tags || !Array.isArray(tags) || tags.length === 0) {
        existingSection.style.display = 'none';
        return;
    }

    // 去重
    const uniqueTags = [...new Set(tags.map(t => t.tag))];
    existingSection.style.display = 'block';
    tagList.innerHTML = uniqueTags.map(tag => `
        <span class="period-tag selected" style="cursor:pointer;margin:2px;" onclick="batchRemoveTag('${escapeHtml(tag)}')">${escapeHtml(tag)} &times;</span>
    `).join('');
}

async function batchAddTag() {
    const ids = getSelectedIds();
    if (ids.length === 0) return;

    const tagInput = document.getElementById('batchTagName');
    const tag = tagInput.value.trim();
    if (!tag) { showToast('请输入标签名称', 'warning'); return; }

    const result = await apiFetch('/api/batch_tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_ids: ids, tag: tag }),
    });

    if (result && result.success) {
        showToast(result.message, 'success');
        tagInput.value = '';
        loadExistingTags(ids);
    } else {
        showToast('添加标签失败', 'error');
    }
}

async function batchRemoveTag(tag) {
    const ids = getSelectedIds();
    if (ids.length === 0) return;

    const result = await apiFetch('/api/batch_tags', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_ids: ids, tag: tag }),
    });

    if (result && result.success) {
        showToast(result.message, 'success');
        loadExistingTags(ids);
    } else {
        showToast('移除标签失败', 'error');
    }
}

/* ================================================================
   Feature 10: 表格列宽拖拽
================================================================ */
function initColumnResize() {
    const table = document.getElementById('productTable');
    if (!table) return;

    // 恢复已保存的列宽
    const savedWidths = {};
    try {
        const saved = JSON.parse(localStorage.getItem('colWidths') || '{}');
        Object.assign(savedWidths, saved);
    } catch (e) {}

    // 应用已保存的列宽
    if (Object.keys(savedWidths).length > 0) {
        const ths = table.querySelectorAll('.header-row th[data-key]');
        ths.forEach(th => {
            const key = th.dataset.key;
            if (savedWidths[key]) {
                th.style.width = savedWidths[key] + 'px';
                th.style.minWidth = savedWidths[key] + 'px';
            }
        });
    }

    // 为每个表头添加拖拽手柄
    const headerThs = table.querySelectorAll('.header-row th[data-key]');
    headerThs.forEach(th => {
        // 避免重复添加
        if (th.querySelector('.th-resize-handle')) return;

        const handle = document.createElement('div');
        handle.className = 'th-resize-handle';
        th.appendChild(handle);

        handle.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();

            const startX = e.clientX;
            const startWidth = th.offsetWidth;
            const key = th.dataset.key;

            th.classList.add('resizing');
            handle.classList.add('resizing');

            // 禁用文本选择
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';

            function onMouseMove(e) {
                const diff = e.clientX - startX;
                const newWidth = Math.max(60, startWidth + diff);
                th.style.width = newWidth + 'px';
                th.style.minWidth = newWidth + 'px';
            }

            function onMouseUp() {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                th.classList.remove('resizing');
                handle.classList.remove('resizing');
                document.body.style.userSelect = '';
                document.body.style.cursor = '';

                // 保存列宽
                savedWidths[key] = th.offsetWidth;
                try {
                    localStorage.setItem('colWidths', JSON.stringify(savedWidths));
                } catch (e) {}
            }

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    });
}

/* ================================================================
   Feature 11: 表格行内快速编辑
================================================================ */
function startInlineEdit(td, productId, field) {
    // 如果已经在编辑中，不重复创建
    if (td.querySelector('.inline-edit-input') || td.querySelector('.inline-edit-select')) return;

    const currentValue = td.textContent.trim() || '';
    const originalHtml = td.innerHTML;

    if (field === 'tier') {
        // 分层下拉
        const select = document.createElement('select');
        select.className = 'inline-edit-select';
        ['S', 'A', 'B', 'C'].forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            if (currentValue === opt) option.selected = true;
            select.appendChild(option);
        });
        td.innerHTML = '';
        td.appendChild(select);
        select.focus();

        async function save() {
            const newValue = select.value;
            if (newValue !== currentValue) {
                const ok = await saveInlineEdit(productId, field, newValue);
                if (ok) {
                    td.textContent = newValue;
                    // 同步更新STATE中的数据
                    const product = (STATE.productData || []).find(p => p.product_id === productId);
                    if (product) product[field] = newValue;
                } else {
                    td.innerHTML = originalHtml;
                }
            } else {
                td.innerHTML = originalHtml;
            }
        }

        select.addEventListener('change', save);
        select.addEventListener('blur', function() {
            setTimeout(save, 100);
        });
        select.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { td.innerHTML = originalHtml; }
        });
    } else if (field === 'style') {
        // 风格下拉（从已有数据中收集）
        const styles = new Set();
        (STATE.productData || []).forEach(p => {
            if (p.style && p.style !== 'nan' && p.style !== 'null' && p.style !== 'None') {
                styles.add(p.style);
            }
        });
        const styleList = [...styles].sort();

        const select = document.createElement('select');
        select.className = 'inline-edit-select';
        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = '-- 请选择 --';
        select.appendChild(defaultOpt);
        styleList.forEach(s => {
            const option = document.createElement('option');
            option.value = s;
            option.textContent = s;
            if (currentValue === s) option.selected = true;
            select.appendChild(option);
        });
        // 允许自定义输入
        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.textContent = '+ 自定义输入';
        select.appendChild(customOpt);

        td.innerHTML = '';
        td.appendChild(select);
        select.focus();

        select.addEventListener('change', function() {
            if (select.value === '__custom__') {
                // 切换为文本输入
                const input = document.createElement('input');
                input.type = 'text';
                input.className = 'inline-edit-input';
                input.value = currentValue;
                td.innerHTML = '';
                td.appendChild(input);
                input.focus();
                input.select();
                bindInputEvents(input, td, productId, field, originalHtml);
            } else {
                const newValue = select.value;
                if (newValue !== currentValue) {
                    saveInlineEdit(productId, field, newValue).then(ok => {
                        if (ok) {
                            td.textContent = newValue;
                            const product = (STATE.productData || []).find(p => p.product_id === productId);
                            if (product) product[field] = newValue;
                        } else {
                            td.innerHTML = originalHtml;
                        }
                    });
                } else {
                    td.innerHTML = originalHtml;
                }
            }
        });
        select.addEventListener('blur', function() {
            if (select.value !== '__custom__') {
                setTimeout(() => {
                    const newValue = select.value;
                    if (newValue !== currentValue) {
                        saveInlineEdit(productId, field, newValue).then(ok => {
                            if (ok) {
                                td.textContent = newValue;
                                const product = (STATE.productData || []).find(p => p.product_id === productId);
                                if (product) product[field] = newValue;
                            } else {
                                td.innerHTML = originalHtml;
                            }
                        });
                    } else {
                        td.innerHTML = originalHtml;
                    }
                }, 100);
            }
        });
        select.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { td.innerHTML = originalHtml; }
        });
    } else {
        // 文本输入（scene, manager, remark）
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'inline-edit-input';
        input.value = currentValue;
        td.innerHTML = '';
        td.appendChild(input);
        input.focus();
        input.select();
        bindInputEvents(input, td, productId, field, originalHtml);
    }
}

function bindInputEvents(input, td, productId, field, originalHtml) {
    const currentValue = input.value;

    async function save() {
        const newValue = input.value.trim();
        if (newValue !== currentValue) {
            const ok = await saveInlineEdit(productId, field, newValue);
            if (ok) {
                td.textContent = newValue;
                const product = (STATE.productData || []).find(p => p.product_id === productId);
                if (product) product[field] = newValue;
            } else {
                td.innerHTML = originalHtml;
            }
        } else {
            td.innerHTML = originalHtml;
        }
    }

    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); save(); }
        if (e.key === 'Escape') { td.innerHTML = originalHtml; }
    });
    input.addEventListener('blur', function() {
        setTimeout(save, 100);
    });
}

async function saveInlineEdit(productId, field, value) {
    try {
        const resp = await fetch('/api/products/' + encodeURIComponent(productId) + '/field', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: field, value: value })
        });
        if (!resp.ok) {
            showToast('保存失败: ' + resp.statusText, 'error');
            return false;
        }
        const data = await resp.json();
        if (data && data.success) {
            showToast('已更新「' + field + '」', 'success');
            return true;
        } else {
            showToast('保存失败: ' + (data.error || '未知错误'), 'error');
            return false;
        }
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
        return false;
    }
}

// 为可编辑单元格绑定双击事件
function bindInlineEditEvents() {
    const editableFields = ['tier', 'style', 'scene', 'manager'];
    const tbody = document.getElementById('productTableBody');
    if (!tbody) return;

    tbody.querySelectorAll('tr[data-pid]').forEach(tr => {
        const productId = tr.dataset.pid;
        const metricCols = getVisibleColumns().filter(c => c.key !== 'image' && c.key !== 'title');
        const tds = tr.querySelectorAll('td');
        // 跳过前两个td（排名和商品信息）
        metricCols.forEach((col, idx) => {
            if (editableFields.includes(col.key) && tds[idx + 2]) {
                const td = tds[idx + 2];
                td.classList.add('editable-cell');
                td.title = '双击编辑';
                td.addEventListener('dblclick', function(e) {
                    e.stopPropagation();
                    startInlineEdit(td, productId, col.key);
                });
            }
        });
    });
}

/* ================================================================
   Feature 14: 数据表格横向滚动提示
================================================================ */
function updateScrollIndicators() {
    const wrapper = document.querySelector('.table-wrapper');
    if (!wrapper) return;

    // 确保滚动指示器元素存在
    let leftIndicator = wrapper.querySelector('.scroll-indicator-left');
    let rightIndicator = wrapper.querySelector('.scroll-indicator-right');

    if (!leftIndicator || !rightIndicator) {
        if (!leftIndicator) {
            leftIndicator = document.createElement('div');
            leftIndicator.className = 'scroll-indicator-left';
            wrapper.appendChild(leftIndicator);
        }
        if (!rightIndicator) {
            rightIndicator = document.createElement('div');
            rightIndicator.className = 'scroll-indicator-right';
            wrapper.appendChild(rightIndicator);
        }
    }

    function checkScroll() {
        const hasOverflow = wrapper.scrollWidth > wrapper.clientWidth;
        if (!hasOverflow) {
            leftIndicator.classList.remove('visible');
            rightIndicator.classList.remove('visible');
            return;
        }
        const scrollLeft = wrapper.scrollLeft;
        const maxScroll = wrapper.scrollWidth - wrapper.clientWidth;
        leftIndicator.classList.toggle('visible', scrollLeft > 5);
        rightIndicator.classList.toggle('visible', scrollLeft < maxScroll - 5);
    }

    // 初始检查
    checkScroll();

    // 监听滚动事件
    wrapper.removeEventListener('scroll', checkScroll);
    wrapper.addEventListener('scroll', checkScroll);

    // 监听窗口大小变化
    window.removeEventListener('resize', checkScroll);
    window.addEventListener('resize', checkScroll);
}

/* ================================================================
   商品画像标签
================================================================ */
// 标签数据缓存
let _productTagsMap = {};

async function loadProductTags() {
    const data = await apiFetch(`/api/product_tags?dim=${STATE.dim}&period=${STATE.period}`);
    if (!data || !Array.isArray(data)) return;

    // 构建标签映射
    _productTagsMap = {};
    data.forEach(item => {
        _productTagsMap[item.product_id] = item.tags || [];
    });

    // 将标签附加到商品数据
    (STATE.productData || []).forEach(p => {
        p._tags = _productTagsMap[p.product_id] || [];
    });

    // 重新渲染表格
    renderProductTable();
}

// 显示添加自定义标签对话框
function showAddTagDialog(productId) {
    // 移除已有弹窗
    const existing = document.getElementById('addTagDialog');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'addTagDialog';
    overlay.style.display = 'flex';
    overlay.innerHTML = `
        <div style="background:var(--bg-card);border-radius:12px;padding:20px;width:320px;box-shadow:var(--shadow-lg);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <span style="font-size:0.95rem;font-weight:600;color:var(--text-primary);">添加自定义标签</span>
                <button onclick="document.getElementById('addTagDialog').remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1.2rem;">&times;</button>
            </div>
            <div style="margin-bottom:12px;">
                <span style="font-size:0.82rem;color:var(--text-muted);">商品ID: ${productId}</span>
            </div>
            <div style="margin-bottom:12px;">
                <input type="text" id="customTagInput" placeholder="输入标签名称" maxlength="10"
                    style="width:100%;padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);font-size:0.85rem;"
                    onkeydown="if(event.key==='Enter')saveCustomTag('${productId}')">
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;">
                <button onclick="document.getElementById('addTagDialog').remove()" style="padding:6px 14px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text-secondary);cursor:pointer;font-size:0.82rem;">取消</button>
                <button onclick="saveCustomTag('${productId}')" style="padding:6px 14px;border-radius:6px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-size:0.82rem;">保存</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // 聚焦输入框
    setTimeout(() => {
        const input = document.getElementById('customTagInput');
        if (input) input.focus();
    }, 100);

    // 点击遮罩关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.remove();
    });
}

async function saveCustomTag(productId) {
    const input = document.getElementById('customTagInput');
    if (!input) return;
    const tag = input.value.trim();
    if (!tag) {
        showToast('请输入标签名称', 'error');
        return;
    }

    const res = await apiFetch('/api/product_tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, tag: tag }),
    });

    if (res && res.success) {
        showToast('标签已添加', 'success');
        document.getElementById('addTagDialog').remove();
        // 重新加载标签
        loadProductTags();
    } else {
        showToast('添加标签失败', 'error');
    }
}

async function deleteProductTag(tagId) {
    const res = await apiFetch(`/api/product_tags/${tagId}`, { method: 'DELETE' });
    if (res && res.success) {
        showToast('标签已删除', 'success');
        loadProductTags();
    } else {
        showToast('删除标签失败', 'error');
    }
}
