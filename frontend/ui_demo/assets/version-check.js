(function () {
  const assetBase = new URL('.', document.currentScript?.src || window.location.href);
  const SEMVER_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
  const normalizeVersion = value => {
    const normalized = String(value ?? '').trim().replace(/^v/i, '');
    return SEMVER_PATTERN.test(normalized) ? normalized : null;
  };
  const currentVersion = normalizeVersion(window.TMALL_WEB_VERSION) || '0.0.0';
  if (window.tmallDesktop?.isDesktop) return;

  const newerThan = (candidate, current) => {
    const parse = value => normalizeVersion(value)?.split('.').map(Number) || null;
    const next = parse(candidate);
    const installed = parse(current);
    if (!next || !installed) return false;
    for (let index = 0; index < Math.max(next.length, installed.length); index += 1) {
      if (next[index] !== installed[index]) return next[index] > installed[index];
    }
    return false;
  };

  const dismissKey = `tmall-update-dismissed:${currentVersion}`;
  const dismissed = () => {
    try { return sessionStorage.getItem(dismissKey) === '1'; } catch { return false; }
  };
  const dismiss = () => {
    try { sessionStorage.setItem(dismissKey, '1'); } catch {}
  };
  const showBanner = version => {
    const safeVersion = normalizeVersion(version);
    if (!safeVersion || dismissed() || document.querySelector('[data-update-banner]')) return;
    const banner = document.createElement('aside');
    banner.className = 'web-update-banner';
    banner.dataset.updateBanner = 'true';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    const message = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = `发现新版本 ${safeVersion}`;
    const hint = document.createElement('span');
    hint.textContent = '刷新页面后立即生效';
    message.append(title, hint);
    const actions = document.createElement('span');
    actions.className = 'web-update-banner__actions';
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.dataset.updateRefresh = 'true';
    refresh.textContent = '立即刷新';
    const later = document.createElement('button');
    later.type = 'button';
    later.dataset.updateDismiss = 'true';
    later.setAttribute('aria-label', '稍后提醒');
    later.textContent = '稍后';
    actions.append(refresh, later);
    banner.append(message, actions);
    refresh.addEventListener('click', () => window.location.reload());
    later.addEventListener('click', () => { dismiss(); banner.remove(); });
    document.body.appendChild(banner);
  };

  const check = async () => {
    try {
      const response = await fetch(new URL('../api/version?client=web', assetBase), { cache: 'no-store', headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const version = (await response.json())?.data?.version;
      if (newerThan(version, currentVersion)) showBanner(version);
    } catch {
      // Update checks are best-effort and must not affect dashboard use.
    }
  };

  check();
  window.setInterval(check, 5 * 60 * 1000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') check(); });
})();
