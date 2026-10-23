import sqlite3
import os
import time
import logging
from contextlib import contextmanager
import yaml
from flask import current_app, g, has_app_context

_log = logging.getLogger(__name__)
from db_migrations import SCHEMA_VERSION, _run_init_migrations, _schema_is_current  # noqa: E402,F401

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

_config_cache = None

def load_config():
    global _config_cache
    if _config_cache is None:
        # 使用基于 __file__ 的绝对路径，确保从任何目录都能找到配置文件
        config_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(config_dir, 'config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache

def get_db_path():
    if has_app_context():
        configured_path = current_app.config.get('DATABASE_PATH')
        if configured_path:
            return os.path.abspath(configured_path)
    override = os.environ.get('TMALL_DB_PATH')
    if override:
        return os.path.abspath(override)
    # Keep standalone scripts on the same production default as create_app.
    # config.yaml remains available for thresholds and import settings, but it
    # must not select a second database behind the application's back.
    return os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')


# 命名店铺标识是部署私有配置：公开代码不带具体店铺号，运行环境经
# TMALL_LEGACY_SHOP_ID 注入（本机部署已配置，见运维手册）。
def legacy_shop_id():
    """部署私有的命名店铺号（运行时读环境，公开代码不带具体值）。"""
    return os.environ.get('TMALL_LEGACY_SHOP_ID', '')


def get_shop_id(default=None):
    """Return the canonical request or server shop scope."""
    default = default or legacy_shop_id() or 'default'
    """Return the canonical request or server shop scope."""
    if has_app_context():
        scoped = getattr(g, 'shop_id', None)
        if scoped:
            return scoped
        configured = str(current_app.config.get('SHOP_ID') or '').strip()
        if configured:
            return configured
    return os.environ.get('TMALL_SHOP_ID', default) or default


def require_default_shop_scope():
    """Fail closed while all current product tables remain single-shop."""
    shop_id = get_shop_id()
    if shop_id not in ('default', legacy_shop_id()):
        raise PermissionError(f'当前产品仅支持 default 店铺 scope，不允许访问 {shop_id}')
    return shop_id

def get_connection(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    # Import scans and dashboard mutations can overlap.  Give short-lived
    # readers/writers time to wait for the WAL writer instead of surfacing a
    # transient "database is locked" error to the request.
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    # 性能优化：WAL模式下NORMAL足够安全，写入更快
    conn.execute("PRAGMA synchronous=NORMAL")
    # 缓存20MB（默认2MB）
    conn.execute("PRAGMA cache_size=-20000")
    # 临时表用内存
    conn.execute("PRAGMA temp_store=MEMORY")
    # 启用mmap提高读性能（256MB）
    conn.execute("PRAGMA mmap_size=268435456")
    return conn

@contextmanager
def get_db(db_path=None):
    """Context manager: 自动关闭连接，异常时也不泄漏"""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()

# 服务启动时可能正好撞上批量导入（如 BI 每日导入）长时间持有的写锁——
# 那条路径是「一次 BEGIN IMMEDIATE 提交整批文件」，持锁可达数分钟。
# 只靠 get_connection 的 30s busy_timeout 不够，init_db 会直接抛
# "database is locked" 让服务起不来（2026-09-20 22:28 就是这么挂的）。
# 这里对锁类错误做退避重试；正常启动路径没有任何额外开销。
INIT_DB_LOCK_WAIT_SECONDS = 600


def init_db(db_path=None):
    deadline = time.monotonic() + INIT_DB_LOCK_WAIT_SECONDS
    attempt = 0
    while True:
        try:
            return _init_db(db_path)
        except sqlite3.OperationalError as error:
            message = str(error).lower()
            if 'locked' not in message and 'busy' not in message:
                raise
            attempt += 1
            if time.monotonic() >= deadline:
                raise
            wait = min(5 * attempt, 15)
            _log.warning('init_db: 数据库被占用（%s），%ss 后重试（第 %s 次）', error, wait, attempt)
            time.sleep(wait)


def _init_db(db_path=None):
    conn = get_connection(db_path)
    try:
        _run_init_migrations(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        # 迁移过程中任何异常（最典型的是 database is locked）都必须释放连接，
        # 否则重试路径会不断堆积打开着的连接。
        conn.close()
    _log.info("Database initialized: %s", db_path)


if __name__ == '__main__':
    init_db()
