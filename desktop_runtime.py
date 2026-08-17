import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopPaths:
    database: str
    uploads: str
    import_inbox: str
    logs: str


def resource_root() -> str:
    return os.path.abspath(getattr(sys, '_MEIPASS', os.path.dirname(__file__)))


def desktop_data_paths(environment=None) -> DesktopPaths:
    env = environment or os.environ
    roaming = env.get('APPDATA') or os.path.join(Path.home(), 'AppData', 'Roaming')
    local = env.get('LOCALAPPDATA') or os.path.join(Path.home(), 'AppData', 'Local')
    data_root = os.path.join(roaming, 'TmallDashboard', 'data')
    return DesktopPaths(
        database=os.path.join(data_root, 'dashboard.db'),
        uploads=os.path.join(data_root, 'uploads'),
        import_inbox=os.path.join(data_root, 'import-inbox'),
        logs=os.path.join(local, 'TmallDashboard', 'logs'),
    )


def ensure_desktop_directories(paths: DesktopPaths) -> None:
    os.makedirs(os.path.dirname(paths.database), exist_ok=True)
    os.makedirs(paths.uploads, exist_ok=True)
    os.makedirs(paths.import_inbox, exist_ok=True)
    os.makedirs(paths.logs, exist_ok=True)


def desktop_environment(paths: DesktopPaths, environment=None) -> dict:
    source_environment = os.environ if environment is None else environment
    configured_roots = str(source_environment.get('IMPORT_SCAN_ALLOWED_ROOTS') or '')
    scan_roots = [paths.import_inbox, *(
        root for root in configured_roots.split(os.pathsep) if root.strip()
    )]
    scan_roots = list(dict.fromkeys(scan_roots))
    return {
        'TMALL_DB_PATH': paths.database,
        'DATABASE_URL': _sqlite_url(paths.database),
        'TMALL_UPLOAD_FOLDER': paths.uploads,
        'IMPORT_SCAN_ALLOWED_ROOTS': os.pathsep.join(scan_roots),
        'TMALL_DESKTOP_MODE': '1',
    }


def _sqlite_url(path: str) -> str:
    return 'sqlite:///' + os.fspath(path).replace('\\', '/')
