# Desktop EXE Packaging and GitHub Updater Design

## Goal

Deliver a Windows desktop distribution of the existing Tmall Dashboard that a user can install and launch by double-clicking, without installing Python, Node.js, or manually starting a local server. The desktop shell must preserve the existing Flask, SQLite, API, frontend, import, audit, backup, and rollback capabilities.

The distribution uses a fully bundled WebView2 installer so first-run setup does not depend on network access. A public GitHub repository hosts release metadata and installer assets for in-app update checks.

## Non-goals

- Rewriting the Flask API, database schema, or frontend into Electron.
- Running scheduled imports while the application process is fully closed without an explicit Windows Task Scheduler integration.
- Downloading or executing arbitrary GitHub source archives as updates.

## Language and Windows integration

The delivered product is Chinese-first. The installer wizard, desktop shortcut, Start Menu entry, uninstall entry, startup diagnostics, update notifications, release notes link text, checksum errors, and rollback errors use Simplified Chinese. The existing dashboard pages remain the source of truth for business terminology and are not translated or duplicated in the desktop shell. The executable and installer metadata use the product name `天猫数据仪表盘`.

## Architecture

The existing application remains the business runtime:

```text
TmallDashboard.exe
  -> desktop launcher
  -> Waitress on a loopback-only ephemeral port
  -> existing Flask application and native frontend
  -> pywebview window backed by WebView2
```

The launcher owns process lifecycle only. It starts the WSGI server in a child thread/process, waits for `/healthz`, opens the desktop window at `/`, and shuts the server down when the window closes. The browser address bar and console window are hidden.

The PyInstaller build uses `--onedir --windowed`. An installer packages the application directory, the WebView2 Evergreen Standalone installer, and the updater. The installer creates shortcuts and an uninstall entry.

## Resource and data paths

Read-only application resources are resolved through a PyInstaller-aware resource helper. Writable state never targets the bundled application directory:

- `%APPDATA%\\TmallDashboard\\data\\dashboard.db`
- `%APPDATA%\\TmallDashboard\\data\\uploads\\`
- `%APPDATA%\\TmallDashboard\\data\\import-inbox\\`
- `%APPDATA%\\TmallDashboard\\data\\backups\\`
- `%LOCALAPPDATA%\\TmallDashboard\\logs\\`

On first launch, required directories are created and the existing database initialization/migration path runs against the user database. Existing repository data can be imported through the normal import workflow or an explicit migration option; the installer never overwrites a user's database.

## WebView2 installation

The installer first detects the Evergreen WebView2 runtime. If it is absent, it runs the bundled offline Evergreen Standalone installer. If installation fails, setup stops with an actionable error rather than producing a partially working desktop installation. If WebView2 is already present, the bundled installer is skipped.

This avoids a first-run network dependency while retaining the native Windows rendering experience and keeping the application shell smaller than an embedded Chromium distribution.

## GitHub Releases update flow

The public GitHub repository is the update source. Each release publishes:

```text
TmallDashboard-Setup-<version>.exe
latest.json
SHA256SUMS.txt
```

`latest.json` contains the semantic version, release notes URL, installer URL, SHA-256, minimum Windows version, and a manifest schema version. The app checks the manifest at startup with a bounded timeout and also exposes a manual check action. A failed check is non-blocking and never prevents local use.

When an update is accepted, the app downloads the installer to a temporary directory, verifies the declared SHA-256 before execution, and launches the installer after the desktop process exits. The updater refuses downgrades unless explicitly requested and keeps the current installation intact until the new installer completes. The current database is not replaced by an update; database migrations continue to run on application startup.

The initial implementation uses SHA-256 integrity verification and HTTPS GitHub release URLs. Release signing can be added later without changing the app/update interface by adding a signature field to `latest.json`.

## Background task boundary

All existing capabilities work while the desktop application is running. The local import scanner and scheduled jobs do not execute when the application is completely closed. The packaging phase will document this boundary and provide an optional Windows Task Scheduler registration command that launches a headless scanner using the same user data directory.

## Error handling

- Port allocation retries a bounded number of times and reports a clear startup error if no loopback port is available.
- `/healthz` readiness has a timeout; failed readiness closes the child server and shows a diagnostic dialog.
- Missing or corrupt user data directories are recreated where safe; database corruption is reported without deleting the original file.
- Update network errors, invalid manifests, checksum mismatches, and installer failures are logged and surfaced as non-destructive notifications.
- The app refuses to execute an update that fails HTTPS, manifest schema, version, or checksum validation.

## Verification plan

- Unit tests for resource path resolution, user data directory resolution, manifest parsing, version comparison, and SHA-256 verification.
- Launcher smoke test that starts the real WSGI app on an ephemeral loopback port and verifies `/healthz` and `/`.
- Packaging smoke test on Windows that runs the installed executable without Python on `PATH`, opens the overview page, writes a temporary database, and exits cleanly.
- Upgrade test using a local HTTP fixture or GitHub release fixture that verifies accepted update, checksum rejection, malformed manifest rejection, and downgrade refusal.
- Existing Python, JavaScript, release audit, and browser smoke suites remain required gates.

## Release workflow

1. Set the application version in one source of truth.
2. Build the PyInstaller directory and offline installer.
3. Generate `latest.json`, `SHA256SUMS.txt`, and release notes.
4. Run package, launch, database-write, and upgrade smoke checks.
5. Publish a public GitHub Release with the three assets.
