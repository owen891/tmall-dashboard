(function () {
  const assetBase = new URL('.', document.currentScript?.src || window.location.href);
  const SEMVER_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
  const normalizeVersion = value => {
    const normalized = String(value ?? '').trim().replace(/^v/i, '');
    return SEMVER_PATTERN.test(normalized) ? normalized : null;
  };
  const currentVersion = normalizeVersion(window.TMALL_WEB_VERSION) || '0.0.0';
  if (window.tmallDesktop?.isDesktop) return;
  const project = window.TMALL_PROJECT || {
    latestRelease: 'https://github.com/owen891/tmall-dashboard/releases/latest',
    latestReleaseApi: 'https://api.github.com/repos/owen891/tmall-dashboard/releases/latest',
  };

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
  const githubCheckKey = 'tmall-update-github-last-check';
  const githubCheckInterval = 30 * 60 * 1000;
  const githubCheckDue = () => {
    try {
      const last = Number(localStorage.getItem(githubCheckKey) || 0);
      return !last || Date.now() - last >= githubCheckInterval;
    } catch { return true; }
  };
  const markGithubCheck = () => {
    try { localStorage.setItem(githubCheckKey, String(Date.now())); } catch {}
  };
  const dismissed = () => {
    try { return sessionStorage.getItem(dismissKey) === '1'; } catch { return false; }
  };
  const dismiss = () => {
    try { sessionStorage.setItem(dismissKey, '1'); } catch {}
  };
  const showBanner = (version, releaseUrl = project.latestRelease) => {
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
    hint.textContent = '查看更新说明后刷新页面生效';
    message.append(title, hint);
    const actions = document.createElement('span');
    actions.className = 'web-update-banner__actions';
    const notes = document.createElement('a');
    notes.href = releaseUrl;
    notes.target = '_blank';
    notes.rel = 'noreferrer';
    notes.textContent = '更新说明';
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.dataset.updateRefresh = 'true';
    refresh.textContent = '立即刷新';
    const later = document.createElement('button');
    later.type = 'button';
    later.dataset.updateDismiss = 'true';
    later.setAttribute('aria-label', '稍后提醒');
    later.textContent = '稍后';
    actions.append(notes, refresh, later);
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

  const checkGithubRelease = async () => {
    if (!githubCheckDue()) return;
    markGithubCheck();
    try {
      const response = await fetch(project.latestReleaseApi, { cache: 'no-store', headers: { Accept: 'application/vnd.github+json' } });
      if (!response.ok) return;
      const release = await response.json();
      const version = release?.tag_name;
      if (newerThan(version, currentVersion)) showBanner(version, project.latestRelease);
    } catch {
      // GitHub checks are best-effort and must not affect dashboard use.
    }
  };

  check();
  checkGithubRelease();
  window.setInterval(() => { check(); checkGithubRelease(); }, 30 * 60 * 1000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { check(); checkGithubRelease(); } });
})();
