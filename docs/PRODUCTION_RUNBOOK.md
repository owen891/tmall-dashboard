# Production Runbook

This deployment keeps Flask + SQLite + the native frontend and runs behind Waitress.
It is intended for a trusted LAN or a reverse proxy that terminates TLS.

## Release Gate

Run these checks from the release checkout before changing the live process:

```powershell
py -3 -m unittest discover -s tests -q
Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }
node scripts/validate_ui_demos.cjs
$env:DASHBOARD_USERNAME = 'operator'
$env:DASHBOARD_PASSWORD = '<long-random-secret>'
py -3 scripts/production_preflight.py --require-auth
py -3 scripts/production_smoke.py --port 8790
py -3 scripts/release_audit.py --database data/dashboard.db --strict
```

The authenticated preflight must report database integrity `ok`, all formal page
routes as HTTP 200, an external unauthenticated health request as HTTP 401, and
an authenticated external health request as HTTP 200.

The process smoke additionally starts the real Waitress WSGI process and checks
those same boundaries over HTTP before terminating the temporary process.

The release audit is intentionally read-only. It must report a clean worktree,
an integrity-checked database, and no mixed demo/real import batches before a
release artifact is handed off.

## Backup Before Migration

## Local Import Scanner

The scanner is local-only. Keep inbox folders inside
`IMPORT_SCAN_ALLOWED_ROOTS`; UNC/SMB paths, symlink folders, recursive
patterns, and files that are still changing are rejected. Configure jobs with
`/api/import-scans` and run the independent worker every minute:

```powershell
& .\.venv\Scripts\python.exe scripts/run_import_scanner.py --once
```

The worker acquires a SQLite lease, records every run and file fingerprint,
calls the canonical preview/quality/confirm flow, and never writes business
tables for blocked previews. Disable a job by setting `enabled=false` or by
calling `DELETE /api/import-scans/<id>`. The old schedule endpoints remain as
one-release migration shims and return `410 LEGACY_SCHEDULE_REMOVED`.

Create an online backup while the service is still running:

```powershell
py -3 scripts/backup_database.py --source data/dashboard.db
```

The command writes an integrity-checked snapshot below `data/backups/`, reports
SHA-256 hashes, and never mutates the source database. Keep the snapshot outside
the application checkout as an additional operational copy.

## Start

Copy `.env.example` to a protected local environment file and set a unique
password. Set the credentials in the process environment, then use the checked launcher.
It fails closed when credentials or the database are missing, runs the
authenticated preflight before binding the port, and can create an online
backup before startup:

```powershell
$env:DASHBOARD_USERNAME = 'operator'
$env:DASHBOARD_PASSWORD = '<long-random-secret>'
& .\scripts\start_production.ps1 -BackupBeforeStart
```

Use the direct command only when a process supervisor needs to own Waitress:

```powershell
$env:DASHBOARD_USERNAME = 'operator'
$env:DASHBOARD_PASSWORD = '<long-random-secret>'
py -3 -m waitress --host=0.0.0.0 --port=5000 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-for wsgi:application
```

Expose only the required LAN or reverse-proxy network. If a proxy is used, it
must preserve `X-Forwarded-For` and terminate TLS before forwarding to Waitress.
The application treats forwarded requests as external and requires Basic Auth.

## Health And Rollback

Monitor `GET /healthz` with the configured Basic Auth credentials. A failed
database check returns HTTP 503. To roll back, stop Waitress, copy the selected
backup to `data/dashboard.db`, run the recovery drill against a copy, then start
Waitress and rerun the authenticated preflight:

```powershell
py -3 scripts/production_preflight.py --recovery-source data/backups/dashboard-<stamp>.db
Copy-Item data/backups/dashboard-<stamp>.db data/dashboard.db
py -3 scripts/production_preflight.py --require-auth
```

Do not edit the live SQLite file while Waitress is serving traffic.
