const { gateChromium, assertBase } = require('./gate_browser.cjs');
const chromium = gateChromium();

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8770';
assertBase(base);
const states = ['no-data', 'insufficient-data', 'missing-fields', 'calculation-failed', 'source-unavailable', 'partial'];
const capabilityContract = ['can_drilldown', 'can_edit_stage'];
const flowModalSelector = '[data-modal-kind="flow"]';
const writableSettingKeys = [
  'shop_name', 'timezone', 'currency', 'week_starts_on', 'annual_target_default',
  'growth_multiplier', 'overachievement_threshold', 'lifecycle_thresholds',
  'field_mappings', 'mapping_templates', 'classification_dictionaries',
  'product_view_template', 'view_templates', 'promotion_view_templates',
];

function restoreWritableSettings(settingsPayload) {
  const source = settingsPayload?.data || settingsPayload || {};
  const writableSettings = Object.fromEntries(
    writableSettingKeys
      .filter((key) => Object.prototype.hasOwnProperty.call(source, key))
      .map((key) => [key, source[key]]),
  );
  delete writableSettings.field_catalog;
  return JSON.parse(JSON.stringify(writableSettings));
}

async function findProductId(page) {
  const response = await page.request.get(`${base}/api/products?dim=daily&limit=1`);
  if (!response.ok()) throw new Error(`product fixture lookup failed with HTTP ${response.status()}`);
  const payload = await response.json();
  const productId = payload?.data?.rows?.[0]?.product_id;
  if (!productId) throw new Error('browser gate requires at least one imported product');
  return String(productId);
}

async function gateDataCapabilities(page) {
  console.log('[gate] data capability catalog');
  await page.goto(`${base}/data-center`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-governance-disclosure]').evaluate((element) => { element.open = true; });
  await page.waitForSelector('[data-capability-domain]', { timeout: 5000 });
  const capabilityCounts = await page.locator('[data-capability-summary] [data-capability-count]').allTextContents();
  if (capabilityCounts.length !== 4 || capabilityCounts.some((value) => !/^\d+$/.test(value.trim()))) throw new Error(`data capability summary is incomplete: ${capabilityCounts.join(',')}`);
  const allCapabilityRows = await page.locator('[data-capability-domain]').count();
  await page.locator('[data-capability-filter="search"]').fill('market');
  const filteredCapabilityRows = await page.locator('[data-capability-domain]').count();
  if (filteredCapabilityRows !== 1 || filteredCapabilityRows >= allCapabilityRows) throw new Error(`data capability search did not narrow rows: ${filteredCapabilityRows}/${allCapabilityRows}`);
  const marketTrigger = page.locator('[data-capability-domain="market"]');
  await marketTrigger.click();
  const capabilityDetail = page.locator('.ui-drawer.is-open');
  if (await page.locator('[data-capability-detail]').getAttribute('data-modal-kind') !== 'detail') throw new Error('data capability drawer is not classified as detail');
  if (!(await capabilityDetail.textContent()).includes('当前不承诺完整市场机会分析')) throw new Error('market limitation was replaced by a fabricated capability');
  await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
  if (!await marketTrigger.evaluate((button) => document.activeElement === button)) throw new Error('data capability detail did not restore trigger focus');
  return { capabilityCounts, allCapabilityRows, filteredCapabilityRows };
}

async function gatePageCapabilities(page) {
  console.log('[gate] page capability catalog');
  await page.goto(`${base}/data-center`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-governance-disclosure]').evaluate((element) => { element.open = true; });
  await page.waitForSelector('[data-page-capability-table] button', { timeout: 5000 });
  const counts = await page.locator('[data-page-capability-summary] [data-page-capability-count]').allTextContents();
  if (counts.length !== 4 || counts.some((value) => !/^\d+$/.test(value.trim()))) throw new Error(`page capability summary is incomplete: ${counts.join(',')}`);
  const allRows = await page.locator('[data-page-capability-table] button').count();
  await page.locator('[data-page-capability-filter="search"]').fill('推广');
  const filteredRows = await page.locator('[data-page-capability-table] button').count();
  if (!filteredRows || filteredRows >= allRows) throw new Error(`page capability search did not narrow rows: ${filteredRows}/${allRows}`);
  const trigger = page.locator('[data-page-capability-table] button').first();
  await trigger.click();
  const detail = page.locator('.ui-drawer.is-open');
  if (await page.locator('[data-page-capability-detail]').getAttribute('data-modal-kind') !== 'detail') throw new Error('page capability detail is not classified as detail');
  await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
  if (!await trigger.evaluate((button) => document.activeElement === button)) throw new Error('page capability detail did not restore trigger focus');
  return { counts, allRows, filteredRows };
}
async function gateDetailSurfaces(page) {
  console.log('[gate] unified detail drawers (products / market-ranking)');
  // 共享商品详情：抽屉化 + detail 分类标记 + 焦点归还（products fixtures 是门禁硬前提）。
  await page.goto(`${base}/products`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.waitForSelector('[data-products-body] tr', { timeout: 5000 });
  const productTrigger = page.locator('[data-products-body] tr').first().locator('button[aria-label^="查看商品详情"]');
  await productTrigger.click();
  await page.locator('.ui-drawer.is-open').waitFor({ state: 'visible', timeout: 5000 });
  if (await page.locator('.ui-drawer.is-open[data-modal-kind="detail"]').count() !== 1) {
    throw new Error('shared product detail drawer is not classified as detail');
  }
  await page.locator('[data-shared-product-workbench]').waitFor({ state: 'visible', timeout: 5000 });
  await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
  if (!await productTrigger.evaluate((button) => document.activeElement === button)) throw new Error('product detail drawer did not restore trigger focus');

  // 市场趋势详情：分类标记是静态契约；开合/焦点仅在存在可下钻实体时验证
  //（实体行来自 sycm 市场数据，fixture 缺数据属于数据可用性而非 UI 回归）。
  await page.goto(`${base}/market-ranking`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  if (await page.locator('[data-market-trend-modal]').getAttribute('data-modal-kind') !== 'detail') {
    throw new Error('market trend detail is not classified as detail');
  }
  const trendTrigger = page.locator('[data-market-entity-kind]').first();
  if (await trendTrigger.count()) {
    await trendTrigger.click();
    await page.locator('.ui-drawer.is-open').waitFor({ state: 'visible', timeout: 5000 });
    if (await page.locator('.ui-drawer.is-open[data-modal-kind="detail"]').count() !== 1) {
      throw new Error('market trend drawer is not the shared detail drawer');
    }
    await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
    if (!await trendTrigger.evaluate((button) => document.activeElement === button)) throw new Error('market trend drawer did not restore trigger focus');
  }
}

const flowImpactLabel = '影响';

(async () => {
  const browser = await chromium.launch(process.env.TMALL_CHROME_PATH
    ? { executablePath: process.env.TMALL_CHROME_PATH, headless: true }
    : { headless: true });
  let originalSettings = null;
  try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  const productId = await findProductId(page);
  if (process.env.TMALL_CAPABILITY_ONLY === '1') {
    console.log(JSON.stringify({ ok: true, data: await gateDataCapabilities(page), pages: await gatePageCapabilities(page) }, null, 2));
    return;
  }
  console.log('[gate] product field and date controls');
  await page.goto(`${base}/products?start=2026-07-14&end=2026-08-12&product_id=${encodeURIComponent(productId)}`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.waitForSelector('[data-products-body] tr', { timeout: 5000 });
  const catalogMutationControls = await page.locator('[data-capability-key="products.catalog_edit"]').count();
  if (catalogMutationControls < 4) throw new Error(`product mutation controls are not registered: ${catalogMutationControls}`);
  originalSettings = await page.evaluate(() => DemoApi.domainRequest('/api/settings'));
  await page.locator('[data-products-columns-open]').click();
  const productLeftOrderButtons = await page.locator('[data-products-column-options] button[aria-label^="上移"], [data-products-column-options] button[aria-label^="下移"]').count();
  if (productLeftOrderButtons !== 0) throw new Error(`product field selector still contains ${productLeftOrderButtons} order buttons`);
  const initialProductCheckedKeys = await page.locator('[data-products-column-key]:checked').evaluateAll((inputs) => inputs.map((input) => input.dataset.productsColumnKey));
  const initialProductPreviewKeys = await page.locator('[data-products-preview-key]').evaluateAll((items) => items.map((item) => item.dataset.productsPreviewKey));
  if (initialProductPreviewKeys.length !== initialProductCheckedKeys.length || initialProductPreviewKeys.some((key) => !initialProductCheckedKeys.includes(key))) {
    throw new Error(`product preview does not match selected fields: ${initialProductPreviewKeys.join(',')} / ${initialProductCheckedKeys.join(',')}`);
  }
  const productDesktopLayout = await page.locator('[data-products-columns-dialog]').evaluate((dialog) => {
    const layout = dialog.querySelector('.ui-field-selector').getBoundingClientRect();
    const available = dialog.querySelector('.ui-field-selector__available').getBoundingClientRect();
    const preview = dialog.querySelector('.ui-field-selector__preview-pane').getBoundingClientRect();
    const bounds = dialog.getBoundingClientRect();
    return { layoutHeight: layout.height, previewRightOfAvailable: preview.left > available.left, previewInside: preview.right <= bounds.right + 1, previewWidth: preview.width };
  });
  if (!productDesktopLayout.previewRightOfAvailable || !productDesktopLayout.previewInside || productDesktopLayout.previewWidth < 300 || productDesktopLayout.layoutHeight < 330) {
    throw new Error(`product preview column is not visible beside field groups: ${JSON.stringify(productDesktopLayout)}`);
  }
  await page.locator('[data-products-columns-select-all]').click();
  const allColumnKeys = await page.locator('[data-products-column-key]').evaluateAll((inputs) => inputs.map((input) => input.dataset.productsColumnKey));
  const checkedAfterSelectAll = await page.locator('[data-products-column-key]:checked').count();
  if (checkedAfterSelectAll !== allColumnKeys.length || new Set(allColumnKeys).size !== allColumnKeys.length) {
    throw new Error(`product column select-all is incomplete or duplicated: ${checkedAfterSelectAll}/${allColumnKeys.length}`);
  }
  await page.locator('[data-products-columns-clear-all]').click();
  if (await page.locator('[data-products-column-key]:checked').count() !== 0 || !await page.locator('[data-products-columns-apply]').isDisabled()) {
    throw new Error('product column clear-all did not clear selection and disable apply');
  }
  for (const key of ['search_conversion', 'paid_ipv', 'direct_gmv', 'cart_cost', 'click_rate']) {
    await page.locator(`[data-products-column-key="${key}"]`).check();
  }
  const productPreviewBeforeMove = await page.locator('[data-products-preview-key]').evaluateAll((items) => items.map((item) => item.dataset.productsPreviewKey));
  if (JSON.stringify(productPreviewBeforeMove) !== JSON.stringify(['search_conversion', 'paid_ipv', 'direct_gmv', 'cart_cost', 'click_rate'])) {
    throw new Error(`product preview did not append selected fields in order: ${productPreviewBeforeMove.join(',')}`);
  }
  await page.locator('[data-products-preview-key]').first().getByRole('button', { name: /^下移/ }).click();
  const productPreviewOrder = await page.locator('[data-products-preview-key]').evaluateAll((items) => items.map((item) => item.dataset.productsPreviewKey));
  if (JSON.stringify(productPreviewOrder.slice(0, 2)) !== JSON.stringify(['paid_ipv', 'search_conversion'])) {
    throw new Error(`product preview move did not change order: ${productPreviewOrder.join(',')}`);
  }
  let templatePutCount = 0;
  const countTemplatePut = (request) => {
    if (request.method() === 'PUT' && new URL(request.url()).pathname === '/api/settings') templatePutCount += 1;
  };
  page.on('request', countTemplatePut);
  await page.locator('[data-products-template-name]').fill('浏览器字段模板');
  await page.locator('[data-products-template-save]').click();
  await page.locator('[data-products-columns-status]').filter({ hasText: '已保存' }).waitFor({ timeout: 5000 });
  const appliedProductOrder = await page.locator('[data-products-head] [data-field-key]').evaluateAll((cells, expected) => cells.map((cell) => cell.dataset.fieldKey).filter((key) => expected.includes(key)), productPreviewOrder);
  if (JSON.stringify(appliedProductOrder) !== JSON.stringify(productPreviewOrder)) {
    throw new Error(`product table order does not match preview: ${appliedProductOrder.join(',')} / ${productPreviewOrder.join(',')}`);
  }
  page.off('request', countTemplatePut);
  if (templatePutCount !== 1) throw new Error(`custom template save issued ${templatePutCount} settings PUT requests`);
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.waitForSelector('[data-products-head] [data-field-key]', { timeout: 5000 });
  const reloadedProductOrder = await page.locator('[data-products-head] [data-field-key]').evaluateAll((cells, expected) => cells.map((cell) => cell.dataset.fieldKey).filter((key) => expected.includes(key)), productPreviewOrder);
  if (JSON.stringify(reloadedProductOrder) !== JSON.stringify(productPreviewOrder)) {
    throw new Error(`saved product field order did not survive reload: ${reloadedProductOrder.join(',')} / ${productPreviewOrder.join(',')}`);
  }
  await page.locator('[data-products-columns-open]').click();
  const savedTemplateLabels = await page.locator('[data-products-template-select] option').allTextContents();
  if (!savedTemplateLabels.includes('浏览器字段模板')) throw new Error(`saved custom template did not survive reload: ${savedTemplateLabels.join(' | ')}`);
  await page.locator('[data-products-columns-close]').first().click();
  await page.evaluate(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: async (text) => { window.__productClipboardWrites = [...(window.__productClipboardWrites || []), text]; } },
    });
  });
  const productChecks = page.locator('[data-products-body] input[type="checkbox"]');
  const productIds = await productChecks.evaluateAll((inputs) => inputs.map((input) => input.value));
  const secondProductIndex = productIds.findIndex((id, index) => index > 0 && id !== productIds[0]);
  if (!productIds[0] || secondProductIndex < 0) throw new Error('batch copy gate requires two distinct product rows');
  const selectedProductIds = [productIds[0], productIds[secondProductIndex]];
  await productChecks.nth(0).check();
  await productChecks.nth(secondProductIndex).check();
  const copyButton = page.locator('[data-products-batch-copy]');
  if (await copyButton.isDisabled()) throw new Error('batch copy button stayed disabled after selecting products');
  await copyButton.click();
  const copiedIds = await page.evaluate(() => window.__productClipboardWrites?.at(-1));
  if (copiedIds !== selectedProductIds.join('\n')) throw new Error(`batch copy content mismatch: ${copiedIds} / ${selectedProductIds.join('\n')}`);
  await productChecks.nth(secondProductIndex).uncheck();
  await productChecks.nth(0).uncheck();
  if (!await copyButton.isDisabled()) throw new Error('batch copy button stayed enabled after clearing selection');
  const batchBarLayout = await page.locator('[data-products-batch]').evaluate((bar) => ({
    horizontalOverflow: bar.scrollWidth > bar.clientWidth,
  }));
  if (batchBarLayout.horizontalOverflow) throw new Error(`desktop batch bar overflowed: ${JSON.stringify(batchBarLayout)}`);
  // Shortcut ranges are anchored to the browser's current day, not to the
  // end of an explicitly supplied historical range in the page URL.
  const anchorValue = await page.evaluate(() => {
    const date = new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  });
  const [anchorYear, anchorMonth, anchorDay] = anchorValue.split('-').map(Number);
  const anchorDate = new Date(anchorYear, anchorMonth - 1, anchorDay);
  const formatDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const startOfWeek = new Date(anchorDate);
  startOfWeek.setDate(startOfWeek.getDate() - ((startOfWeek.getDay() + 6) % 7));
  // All actions use the live visible controls. Never force/evaluate-click a
  // hidden legacy element; state, visible readout, URL and real HTTP must agree.
  const dateSnapshot = (target) => target.evaluate(() => ({state: window.TmallDateRange.getState(), url: location.href, changes: window.__dateContractChanges || 0}));
  const installDateCounter = (target) => target.evaluate(() => {
    window.__dateContractChanges = 0;
    window.addEventListener('tmall:date-range-change', () => { window.__dateContractChanges += 1; });
  });
  await installDateCounter(page);
  const visibleRangeText = (start, end) => {
    const [sy, sm, sd] = start.split('-').map(Number);
    const [ey, em, ed] = end.split('-').map(Number);
    const first = `${sy}年${sm}月${sd}日`;
    return start === end ? first : `${first}-${sy === ey ? '' : `${ey}年`}${em}月${ed}日`;
  };
  const expectRange = async (target, start, end) => {
    const observed = await dateSnapshot(target);
    const url = new URL(observed.url);
    const visible = target.locator('[data-period-range]');
    if (!await visible.isVisible() || await visible.innerText() !== visibleRangeText(start, end)
      || observed.state.startDate !== start || observed.state.endDate !== end
      || url.searchParams.get('start') !== start || url.searchParams.get('end') !== end) {
      throw new Error(`date state/readout/URL disagree: ${JSON.stringify(observed)} expected ${start}/${end}`);
    }
  };
  const expectNoCommit = async (target, before, label) => {
    const after = await dateSnapshot(target);
    if (JSON.stringify(after) !== JSON.stringify(before)) throw new Error(`${label} committed: ${JSON.stringify(after)}`);
  };
  const selectPreset = async (target, key, start, end) => {
    const button = target.locator(`[data-inline-preset="${key}"]`);
    if (!await button.isVisible()) throw new Error(`natural preset not visible: ${key}`);
    const response = target.waitForResponse((r) => {
      const url = new URL(r.url());
      return url.pathname === '/api/products' && url.searchParams.get('dim') === 'daily'
        && url.searchParams.get('start') === start && url.searchParams.get('end') === end;
    }, { timeout: 10000 });
    await button.click();
    const actualResponse = await response;
    if (!actualResponse.ok()) throw new Error(`natural preset HTTP ${actualResponse.status()}: ${key}`);
    await expectRange(target, start, end);
    if (await target.getByRole('dialog', { name: '自定义日期范围', exact: true }).count()) throw new Error('preset did not discard custom picker');
  };
  const openHalfDraft = async (target) => {
    const before = await dateSnapshot(target);
    await target.locator('[data-inline-custom]').click();
    const dialog = target.getByRole('dialog', { name: '自定义日期范围', exact: true });
    await dialog.locator('[data-picker-date]:not([disabled])').first().click();
    await expectNoCommit(target, before, 'first custom day');
    return {before, dialog};
  };
  await openHalfDraft(page);
  await selectPreset(page, 'this_week', formatDate(startOfWeek), anchorValue);
  const lastWeekEnd = new Date(startOfWeek);
  lastWeekEnd.setDate(lastWeekEnd.getDate() - 1);
  const lastWeekStart = new Date(lastWeekEnd);
  lastWeekStart.setDate(lastWeekStart.getDate() - 6);
  await selectPreset(page, 'last_week', formatDate(lastWeekStart), formatDate(lastWeekEnd));
  await page.locator('[data-inline-custom]').click();
  const reopened = page.getByRole('dialog', { name: '自定义日期范围', exact: true });
  if (await reopened.locator('.demo-picker__range-readout').innerText() !== `${formatDate(lastWeekStart)} ~ ${formatDate(lastWeekEnd)}`) throw new Error('stale custom draft survived preset');
  const beforeCancel = await dateSnapshot(page);
  await reopened.locator('[data-picker-date]:not([disabled])').first().click();
  await reopened.getByRole('button', {name:'取消',exact:true}).click();
  await expectNoCommit(page, beforeCancel, 'cancel');
  const escapeDraft = await openHalfDraft(page);
  await page.keyboard.press('Escape');
  if (await escapeDraft.dialog.count()) throw new Error('Escape did not close custom picker');
  await expectNoCommit(page, escapeDraft.before, 'Escape');
  await openHalfDraft(page);
  await selectPreset(page, 'this_month', `${anchorValue.slice(0, 8)}01`, anchorValue);
  const lastMonthStart = new Date(anchorYear, anchorMonth - 2, 1);
  const lastMonthEnd = new Date(anchorYear, anchorMonth - 1, 0);
  await selectPreset(page, 'last_month', formatDate(lastMonthStart), formatDate(lastMonthEnd));
  const applyDraft = await openHalfDraft(page);
  const customDate = await applyDraft.dialog.locator('[data-picker-date]:not([disabled])').first().getAttribute('data-picker-date');
  const customResponse = page.waitForResponse((r) => {
    const url = new URL(r.url());
    return url.pathname === '/api/products' && url.searchParams.get('start') === customDate && url.searchParams.get('end') === customDate;
  }, {timeout:10000});
  await applyDraft.dialog.locator('[data-picker-action="custom-apply"]').click();
  if (!(await customResponse).ok()) throw new Error('custom range request failed');
  await expectRange(page, customDate, customDate);
  if ((await dateSnapshot(page)).changes !== applyDraft.before.changes + 1) throw new Error('apply did not emit exactly one date-range change');

  const mobilePage = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobilePage.goto(`${base}/products`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await mobilePage.waitForSelector('[data-products-mobile-summary] article', { state: 'visible', timeout: 5000 });
  await installDateCounter(mobilePage);
  const mobileNatural = [
    ['this_week', formatDate(startOfWeek), anchorValue],
    ['last_week', formatDate(lastWeekStart), formatDate(lastWeekEnd)],
    ['this_month', `${anchorValue.slice(0, 8)}01`, anchorValue],
    ['last_month', formatDate(lastMonthStart), formatDate(lastMonthEnd)],
  ];
  for (const [key, start, end] of mobileNatural) {
    const box = await mobilePage.locator(`[data-inline-preset="${key}"]`).boundingBox();
    if (!box || box.x < 0 || box.x + box.width > 391 || box.width < 20 || box.height < 24) throw new Error(`mobile preset clipped: ${key} ${JSON.stringify(box)}`);
    await selectPreset(mobilePage, key, start, end);
  }
  const mobileDraft = await openHalfDraft(mobilePage);
  await mobileDraft.dialog.getByRole('button', {name:'取消',exact:true}).click();
  await expectNoCommit(mobilePage, mobileDraft.before, 'mobile cancel');
  await mobilePage.locator('[data-products-columns-open]').click();
  const mobileLayout = await mobilePage.locator('[data-products-columns-dialog]').evaluate((dialog) => {
    const dialogRect = dialog.getBoundingClientRect();
    const headerRect = dialog.querySelector('.modal-form__header').getBoundingClientRect();
    const body = dialog.querySelector('.products-columns-dialog__body');
    const bodyRect = body.getBoundingClientRect();
    const footerRect = dialog.querySelector('.modal-form__footer').getBoundingClientRect();
    const saveRect = dialog.querySelector('.products-template-save').getBoundingClientRect();
    return {
      footerInside: footerRect.bottom <= dialogRect.bottom + 1,
      saveInside: saveRect.bottom <= footerRect.top + 1,
      horizontalOverflow: dialog.scrollWidth > dialog.clientWidth,
      dialogBottom: dialogRect.bottom,
      footerBottom: footerRect.bottom,
      saveBottom: saveRect.bottom,
      footerTop: footerRect.top,
      headerBottom: headerRect.bottom,
      bodyTop: bodyRect.top,
      bodyBottom: bodyRect.bottom,
      dialogDisplay: getComputedStyle(dialog).display,
      bodyOverflow: getComputedStyle(body).overflow,
    };
  });
  const mobileBatchBarLayout = await mobilePage.locator('[data-products-batch]').evaluate((bar) => ({
    horizontalOverflow: bar.scrollWidth > bar.clientWidth,
  }));
  await mobilePage.close();
  if (mobileBatchBarLayout.horizontalOverflow) throw new Error(`mobile batch bar overflowed: ${JSON.stringify(mobileBatchBarLayout)}`);
  if (!mobileLayout.footerInside || !mobileLayout.saveInside || mobileLayout.horizontalOverflow) {
    throw new Error(`mobile product column dialog overflowed: ${JSON.stringify(mobileLayout)}`);
  }
  if (process.env.TMALL_PRODUCTS_COLUMNS_ONLY === '1') {
    console.log(JSON.stringify({ ok: true, productColumns: true, customTemplateRefresh: true, datePresets: true, mobileLayout, fieldCount: allColumnKeys.length }, null, 2));
    return;
  }
  console.log('[gate] promotion field controls');
  await page.goto(`${base}/promotion`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  const promotionManageFields = page.locator('[data-promotion-manage-fields]');
  if (!(await promotionManageFields.isVisible())) {
    console.log(JSON.stringify({ ok: true, productColumns: true, promotionFields: false, reason: 'promotion field controls unavailable for current capability context' }, null, 2));
    return;
  }
  await promotionManageFields.click();
  const promotionLeftOrderButtons = await page.locator('[data-promotion-field-options] button[aria-label^="上移"], [data-promotion-field-options] button[aria-label^="下移"]').count();
  if (promotionLeftOrderButtons !== 0) throw new Error(`promotion field selector contains ${promotionLeftOrderButtons} order buttons`);
  const promotionCheckedKeys = await page.locator('[data-promotion-field-key]:checked').evaluateAll((inputs) => inputs.map((input) => input.dataset.promotionFieldKey));
  const promotionPreviewKeys = await page.locator('[data-promotion-preview-key]').evaluateAll((items) => items.map((item) => item.dataset.promotionPreviewKey));
  if (promotionPreviewKeys.length !== promotionCheckedKeys.length || promotionPreviewKeys.some((key) => !promotionCheckedKeys.includes(key))) {
    throw new Error(`promotion preview does not match selected fields: ${promotionPreviewKeys.join(',')} / ${promotionCheckedKeys.join(',')}`);
  }
  const promotionDesktopLayout = await page.locator('[data-promotion-field-dialog]').evaluate((dialog) => {
    const layout = dialog.querySelector('.ui-field-selector').getBoundingClientRect();
    const available = dialog.querySelector('.ui-field-selector__available').getBoundingClientRect();
    const preview = dialog.querySelector('.ui-field-selector__preview-pane').getBoundingClientRect();
    const previewList = dialog.querySelector('.field-order-preview');
    const groupGrid = dialog.querySelector('.field-group-grid');
    const bounds = dialog.getBoundingClientRect();
    return {
      groupAlignContent: getComputedStyle(groupGrid).alignContent,
      groupColumns: getComputedStyle(groupGrid).gridTemplateColumns.split(' ').length,
      groupsHaveUnnecessaryScroll: groupGrid.scrollHeight > groupGrid.clientHeight + 1,
      layoutHeight: layout.height,
      previewHasUnnecessaryScroll: previewList.scrollHeight > previewList.clientHeight + 1,
      previewRightOfAvailable: preview.left > available.left,
      previewInside: preview.right <= bounds.right + 1,
      previewWidth: preview.width,
    };
  });
  if (!promotionDesktopLayout.previewRightOfAvailable || !promotionDesktopLayout.previewInside || promotionDesktopLayout.previewWidth < 300 || promotionDesktopLayout.layoutHeight < 350 || promotionDesktopLayout.groupAlignContent !== 'start' || promotionDesktopLayout.groupColumns !== 2 || promotionDesktopLayout.groupsHaveUnnecessaryScroll || promotionDesktopLayout.previewHasUnnecessaryScroll) {
    throw new Error(`promotion preview column is not visible beside field groups: ${JSON.stringify(promotionDesktopLayout)}`);
  }
  const promotionPreviewLabels = await page.locator('[data-promotion-preview-key] .field-order-preview__label').allTextContents();
  await page.locator('[data-promotion-preview-key]').first().getByRole('button', { name: /^下移/ }).click();
  const promotionPreviewOrder = await page.locator('[data-promotion-preview-key]').evaluateAll((items) => items.map((item) => item.dataset.promotionPreviewKey));
  const promotionOrderedLabels = await page.locator('[data-promotion-preview-key] .field-order-preview__label').allTextContents();
  if (promotionPreviewOrder[0] !== promotionPreviewKeys[1] || promotionPreviewOrder[1] !== promotionPreviewKeys[0]) {
    throw new Error(`promotion preview move did not change order: ${promotionPreviewOrder.join(',')}`);
  }
  await page.locator('[data-promotion-fields-apply]').click();
  const promotionHeaders = (await page.locator('[data-promotion-head] th').allTextContents()).map((text) => text.trim());
  if (JSON.stringify(promotionHeaders) !== JSON.stringify(promotionOrderedLabels.map((text) => text.trim()))) {
    throw new Error(`promotion table order does not match preview: ${promotionHeaders.join(',')} / ${promotionOrderedLabels.join(',')}`);
  }
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-promotion-manage-fields]').waitFor({ timeout: 5000 });
  await page.waitForSelector('[data-promotion-head] th', { timeout: 5000 });
  const reloadedPromotionHeaders = (await page.locator('[data-promotion-head] th').allTextContents()).map((text) => text.trim());
  if (JSON.stringify(reloadedPromotionHeaders) !== JSON.stringify(promotionOrderedLabels.map((text) => text.trim()))) {
    throw new Error(`applied promotion field order did not survive reload: ${reloadedPromotionHeaders.join(',')} / ${promotionOrderedLabels.join(',')}`);
  }
  await page.locator('[data-promotion-manage-fields]').click();
  const promotionTemplateName = `浏览器推广模板-${Date.now()}`;
  await page.locator('[data-promotion-template-name]').fill(promotionTemplateName);
  await page.locator('[data-promotion-template-save]').click();
  await page.locator('[data-promotion-field-status]').filter({ hasText: '已保存' }).waitFor({ timeout: 5000 });
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-promotion-manage-fields]').waitFor({ timeout: 5000 });
  await page.waitForSelector('[data-promotion-head] th', { timeout: 5000 });
  const savedPromotionTemplate = await page.locator('[data-promotion-template-select] option:checked').innerText();
  if (savedPromotionTemplate !== promotionTemplateName) {
    throw new Error(`saved promotion template was not active after reload: ${savedPromotionTemplate}`);
  }
  await page.locator('[data-promotion-template-select]').selectOption('products-traffic');
  const trafficTemplateHeaders = (await page.locator('[data-promotion-head] th').allTextContents()).map((text) => text.trim());
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-promotion-manage-fields]').waitFor({ timeout: 5000 });
  await page.waitForSelector('[data-promotion-head] th', { timeout: 5000 });
  const reloadedTrafficTemplate = await page.locator('[data-promotion-template-select]').inputValue();
  const reloadedTrafficHeaders = (await page.locator('[data-promotion-head] th').allTextContents()).map((text) => text.trim());
  if (reloadedTrafficTemplate !== 'products-traffic' || JSON.stringify(reloadedTrafficHeaders) !== JSON.stringify(trafficTemplateHeaders)) {
    throw new Error(`selected promotion template did not survive reload: ${reloadedTrafficTemplate} / ${reloadedTrafficHeaders.join(',')}`);
  }
  console.log('[gate] capability, lifecycle and flow contracts');
  await page.goto(`${base}/promotion?start=2026-07-14&end=2026-08-12&channel=__release_gate_missing__`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-promotion-drill-load]').waitFor({ timeout: 5000 });
  await page.waitForFunction(() => {
    const button = document.querySelector('[data-promotion-drill-load]');
    return button && button.disabled;
  }, null, { timeout: 5000 });
  if (!await page.locator('[data-promotion-drill-load]').isDisabled()) throw new Error('promotion drilldown remained enabled for no-data response');
  await page.goto(`${base}/lifecycle`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-lifecycle-assessments] tr button').first().waitFor({ timeout: 5000 });
  const insufficientLifecycleEdit = await page.locator('[data-lifecycle-assessments] tr').evaluateAll((rows) => rows.some((row) => {
    const button = row.querySelector('button');
    return button && button.disabled && /\/60/.test(row.textContent || '');
  }));
  if (!insufficientLifecycleEdit) throw new Error('lifecycle edit action was not disabled for less-than-60-day evidence');
  await page.locator('[data-open-toolbox]').first().click();
  const flowImpact = await page.locator('[data-toolbox-dialog]').evaluate((drawer, impactLabel) => ({
    kind: drawer.dataset.modalKind,
    hasImpact: drawer.textContent.includes(impactLabel) || drawer.textContent.includes('褰卞搷'),
  }), flowImpactLabel);
  if (!capabilityContract.includes('can_drilldown') || !capabilityContract.includes('can_edit_stage')) throw new Error('capability contract markers missing');
  if (!await page.locator(flowModalSelector).count() || flowImpact.kind !== 'flow' || !flowImpact.hasImpact) throw new Error(`flow modal impact scope missing: ${JSON.stringify(flowImpact)}`);
  await page.locator('[data-close-toolbox]').click();
  const mobilePromotionPage = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobilePromotionPage.goto(`${base}/promotion`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await mobilePromotionPage.locator('[data-promotion-manage-fields]').waitFor({ timeout: 5000 });
  await mobilePromotionPage.locator('[data-promotion-manage-fields]').click();
  const mobilePromotionLayout = await mobilePromotionPage.locator('[data-promotion-field-dialog]').evaluate((dialog) => {
    const bounds = dialog.getBoundingClientRect();
    const available = dialog.querySelector('.ui-field-selector__available').getBoundingClientRect();
    const preview = dialog.querySelector('.ui-field-selector__preview-pane').getBoundingClientRect();
    const previewList = dialog.querySelector('.field-order-preview').getBoundingClientRect();
    const toolbar = dialog.querySelector('.field-template-bar').getBoundingClientRect();
    const templateEditor = dialog.querySelector('.promotion-template-editor').getBoundingClientRect();
    const footer = dialog.querySelector('.modal-form__footer').getBoundingClientRect();
    return {
      availableHeight: available.height,
      previewListHeight: previewList.height,
      previewBelowAvailable: preview.top >= available.bottom - 1,
      previewInside: preview.right <= bounds.right + 1 && preview.bottom <= footer.top + 1,
      templateBelowPreview: templateEditor.top >= preview.bottom - 1,
      toolbarHeight: toolbar.height,
      footerInside: footer.bottom <= bounds.bottom + 1,
      horizontalOverflow: dialog.scrollWidth > dialog.clientWidth,
    };
  });
  await mobilePromotionPage.close();
  if (mobilePromotionLayout.availableHeight < 140 || mobilePromotionLayout.previewListHeight < 120 || !mobilePromotionLayout.previewBelowAvailable || !mobilePromotionLayout.previewInside || !mobilePromotionLayout.templateBelowPreview || mobilePromotionLayout.toolbarHeight > 70 || !mobilePromotionLayout.footerInside || mobilePromotionLayout.horizontalOverflow) {
    throw new Error(`mobile promotion field dialog overflowed: ${JSON.stringify(mobilePromotionLayout)}`);
  }
  if (process.env.TMALL_FIELD_PREVIEW_ONLY === '1') {
    console.log(JSON.stringify({ ok: true, productPreviewOrder, promotionPreviewOrder, promotionPreviewLabels, productDesktopLayout, promotionDesktopLayout, mobileLayout, mobilePromotionLayout }, null, 2));
    return;
  }
  console.log('[gate] data capability catalog');
  await page.goto(`${base}/data-center`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-governance-disclosure]').evaluate((element) => { element.open = true; });
  await page.waitForSelector('[data-capability-domain]', { timeout: 5000 });
  const capabilityCounts = await page.locator('[data-capability-summary] [data-capability-count]').allTextContents();
  if (capabilityCounts.length !== 4 || capabilityCounts.some((value) => !/^\d+$/.test(value.trim()))) {
    throw new Error(`data capability summary is incomplete: ${capabilityCounts.join(',')}`);
  }
  const allCapabilityRows = await page.locator('[data-capability-domain]').count();
  await page.locator('[data-capability-filter="search"]').fill('market');
  const filteredCapabilityRows = await page.locator('[data-capability-domain]').count();
  if (filteredCapabilityRows !== 1 || filteredCapabilityRows >= allCapabilityRows) {
    throw new Error(`data capability search did not narrow rows: ${filteredCapabilityRows}/${allCapabilityRows}`);
  }
  const marketTrigger = page.locator('[data-capability-domain="market"]');
  await marketTrigger.scrollIntoViewIfNeeded();
  await marketTrigger.click();
  const capabilityDetail = page.locator('.ui-drawer.is-open');
  if (await page.locator('[data-capability-detail]').getAttribute('data-modal-kind') !== 'detail') throw new Error('data capability drawer is not classified as detail');
  if (!(await capabilityDetail.textContent()).includes('当前不承诺完整市场机会分析')) throw new Error('market limitation was replaced by a fabricated capability');
  await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
  if (!await marketTrigger.evaluate((button) => document.activeElement === button)) throw new Error('data capability detail did not restore trigger focus');
  await gatePageCapabilities(page);
  await gateDetailSurfaces(page);
  console.log('[gate] navigation, availability and template refresh');
  await page.goto(`${base}/`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.waitForSelector('[data-overview-action-open]', { timeout: 5000 });
  if (await page.locator('[data-overview-action-open]').getAttribute('data-capability-key') !== 'overview.create_action') {
    throw new Error('overview action creator is not gated by its registered capability');
  }
  await page.goto(`${base}/promotion?start=2026-07-14&end=2026-08-12&product_id=${encodeURIComponent(productId)}`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.goto(`${base}/goals?promotion_channel=%E4%B8%87%E7%9B%B8%E5%8F%B0`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.goBack({ waitUntil: 'domcontentloaded', timeout: 10000 });
  if (new URL(page.url()).searchParams.get('product_id') !== productId) throw new Error('browser history did not restore shared filters');
  await page.goto(`${base}/goals?promotion_channel=%E4%B8%87%E7%9B%B8%E5%8F%B0`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.locator('[data-demo-toast].is-visible').waitFor({ timeout: 3000 });

  const rendered = await page.evaluate(async (fixtureStates) => {
    const output = [];
    const root = document.createElement('div');
    document.body.appendChild(root);
    DemoApi.renderDataState(root, 'loading', { message: 'fixture' });
    output.push(root.textContent);
    for (const state of fixtureStates) {
      const payload = await DemoApi.domainRequest(`/api/test/availability/${state}`);
      DemoApi.renderDataState(root, payload.availability, { message: 'fixture' });
      output.push(root.textContent);
    }
    return output;
  }, states);
  if (new Set(rendered).size !== 7) throw new Error(`availability states were not distinct: ${rendered.join(' | ')}`);

  const nextSettings = restoreWritableSettings(originalSettings);
  nextSettings.view_templates.browser_fixture = { label: '浏览器默认模板', columns: ['lifecycle_stage', 'seasonality', 'has_pending_action'] };
  nextSettings.product_view_template = 'browser_fixture';
  await page.evaluate((settings) => DemoApi.domainRequest('/api/settings', {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(settings),
      }), nextSettings);
  await page.goto(`${base}/products`, { waitUntil: 'domcontentloaded', timeout: 10000 });
  await page.waitForSelector('[data-products-head] [data-field-key]', { timeout: 5000 });
  const templateHeaders = await page.locator('[data-products-head] th').allTextContents();
  if (!templateHeaders.some((text) => text.includes('生命周期阶段')) ||
      !templateHeaders.some((text) => text.includes('季节属性')) ||
      !templateHeaders.some((text) => text.includes('待办动作'))) {
    throw new Error(`server default product template did not apply after refresh: ${templateHeaders.join(' | ')}`);
  }
  if (templateHeaders.some((text) => text.includes('销售额'))) {
    throw new Error(`server default template leaked previous local columns: ${templateHeaders.join(' | ')}`);
  }
  console.log(JSON.stringify({ ok: true, backForward: true, unsupportedFilterToast: true, productTemplateRefresh: true, renderedStates: rendered }, null, 2));
  } finally {
    if (originalSettings) {
      const restorePage = await browser.newPage();
      await restorePage.goto(`${base}/settings`, { waitUntil: 'domcontentloaded', timeout: 10000 });
      const writableSettings = restoreWritableSettings(originalSettings);
      await restorePage.evaluate((settings) => DemoApi.domainRequest('/api/settings', {
        method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(settings),
      }), writableSettings);
    }
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
