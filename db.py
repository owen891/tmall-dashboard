import sqlite3
import os
import time
from contextlib import contextmanager
import yaml
from flask import current_app, g, has_app_context

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEMA_VERSION = 4

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


def get_shop_id(default='3828498662'):
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
    if shop_id not in ('default', '3828498662'):
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

# 服务启动时可能正好撞上批量导入（如派米 BI 每日导入）长时间持有的写锁——
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
            print(f'init_db: 数据库被占用（{error}），{wait}s 后重试（第 {attempt} 次）', flush=True)
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
    print(f"Database initialized: {db_path}")


def _schema_is_current(conn):
    """单调版本门：user_version 达标且台账有对应记录的库跳过全量重放。

    SQLite 的 PRAGMA user_version 存储在文件头，读取代价极低；用它避免
    每次启动都重放约 1200 行的「PRAGMA table_info 检查列」式迁移。
    版本落后（升级部署）或记录缺失（异常状态）时返回 False，
    走原有的全量重放路径。"""
    cursor = conn.cursor()
    if cursor.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        return False
    row = cursor.execute(
        'SELECT COUNT(*) FROM schema_migrations WHERE version = ? AND state = ?',
        (SCHEMA_VERSION, 'applied'),
    ).fetchone()
    return bool(row and row[0])


def _run_init_migrations(conn):
    cursor = conn.cursor()
    # 版本门依赖 schema_migrations 表存在；当前库没有时下列建表后立刻检查。
    cursor.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'applied',
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    if _schema_is_current(conn):
        return

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT UNIQUE NOT NULL,
        title TEXT,
        category TEXT,
        tier TEXT,
        style TEXT,
        scene TEXT,
        list_date TEXT,
        status TEXT DEFAULT 'active',
        remark TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS product_identity_map (
        shop_id TEXT NOT NULL DEFAULT 'default',
        source_system TEXT NOT NULL,
        external_product_id TEXT NOT NULL,
        canonical_product_id TEXT,
        identity_status TEXT NOT NULL DEFAULT 'unresolved',
        display_title TEXT NOT NULL DEFAULT '',
        image_url TEXT NOT NULL DEFAULT '',
        first_seen_date DATE,
        last_seen_date DATE,
        fact_row_count INTEGER NOT NULL DEFAULT 0,
        ad_spend REAL NOT NULL DEFAULT 0,
        attributed_payment_amount REAL NOT NULL DEFAULT 0,
        first_source_batch_id TEXT,
        last_source_batch_id TEXT,
        resolution_reason TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (shop_id, source_system, external_product_id),
        FOREIGN KEY (canonical_product_id) REFERENCES products(product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_product_identity_canonical
        ON product_identity_map(shop_id, canonical_product_id);
    CREATE INDEX IF NOT EXISTS idx_product_identity_status
        ON product_identity_map(shop_id, identity_status);

    CREATE TABLE IF NOT EXISTS daily_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id TEXT NOT NULL DEFAULT 'default',
        product_id TEXT NOT NULL,
        date DATE NOT NULL,
        payment_amount REAL DEFAULT 0,
        refund_amount REAL DEFAULT 0,
        net_sales REAL DEFAULT 0,
        payment_qty INTEGER DEFAULT 0,
        ipv INTEGER DEFAULT 0,
        pv INTEGER DEFAULT 0,
        search_ipv INTEGER DEFAULT 0,
        recommend_ipv INTEGER DEFAULT 0,
        paid_ipv INTEGER DEFAULT 0,
        organic_ipv INTEGER DEFAULT 0,
        payment_conversion REAL DEFAULT 0,
        cart_rate REAL DEFAULT 0,
        fav_rate REAL DEFAULT 0,
        bounce_rate REAL DEFAULT 0,
        avg_stay_duration REAL DEFAULT 0,
        ad_spend REAL DEFAULT 0,
        ad_roi REAL DEFAULT 0,
        buyers INTEGER DEFAULT 0,
        avg_order_value REAL DEFAULT 0,
        repurchase_rate REAL DEFAULT 0,
        repurchase_users INTEGER DEFAULT 0,
        presale_amount REAL DEFAULT 0,
        presale_qty INTEGER DEFAULT 0,
        search_click_rate REAL DEFAULT 0,
        cross_sell_qty INTEGER DEFAULT 0,
        cross_sell_rate REAL DEFAULT 0,
        category_width INTEGER DEFAULT 0,
        data_source TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shop_id, product_id, date)
    );

    CREATE TABLE IF NOT EXISTS weekly_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        week_start DATE NOT NULL,
        payment_amount REAL DEFAULT 0,
        refund_amount REAL DEFAULT 0,
        net_sales REAL DEFAULT 0,
        presale_amount REAL DEFAULT 0,
        presale_qty INTEGER DEFAULT 0,
        ipv INTEGER DEFAULT 0,
        pv INTEGER DEFAULT 0,
        search_ipv INTEGER DEFAULT 0,
        recommend_ipv INTEGER DEFAULT 0,
        paid_ipv INTEGER DEFAULT 0,
        organic_ipv INTEGER DEFAULT 0,
        payment_conversion REAL DEFAULT 0,
        cart_rate REAL DEFAULT 0,
        fav_rate REAL DEFAULT 0,
        search_click_rate REAL DEFAULT 0,
        bounce_rate REAL DEFAULT 0,
        avg_stay_duration REAL DEFAULT 0,
        ad_spend REAL DEFAULT 0,
        ad_roi REAL DEFAULT 0,
        repurchase_rate REAL DEFAULT 0,
        repurchase_users INTEGER DEFAULT 0,
        cross_sell_qty INTEGER DEFAULT 0,
        cross_sell_rate REAL DEFAULT 0,
        avg_order_value REAL DEFAULT 0,
        category_width INTEGER DEFAULT 0,
        action_1 TEXT,
        action_2 TEXT,
        data_source TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, week_start)
    );

    CREATE TABLE IF NOT EXISTS monthly_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        month TEXT NOT NULL,
        payment_amount REAL DEFAULT 0,
        refund_amount REAL DEFAULT 0,
        net_sales REAL DEFAULT 0,
        visitors INTEGER DEFAULT 0,
        page_views INTEGER DEFAULT 0,
        uv_value REAL DEFAULT 0,
        search_visitors INTEGER DEFAULT 0,
        search_ratio REAL DEFAULT 0,
        payment_conversion REAL DEFAULT 0,
        search_conversion REAL DEFAULT 0,
        cart_rate REAL DEFAULT 0,
        fav_rate REAL DEFAULT 0,
        bounce_rate REAL DEFAULT 0,
        avg_stay_duration REAL DEFAULT 0,
        ad_spend REAL DEFAULT 0,
        ad_roi REAL DEFAULT 0,
        overall_roi REAL DEFAULT 0,
        paid_ratio REAL DEFAULT 0,
        refund_paid_ratio REAL DEFAULT 0,
        keyword_spend REAL DEFAULT 0,
        keyword_sales REAL DEFAULT 0,
        keyword_roi REAL DEFAULT 0,
        keyword_visitors INTEGER DEFAULT 0,
        keyword_ppc REAL DEFAULT 0,
        crowd_spend REAL DEFAULT 0,
        crowd_sales REAL DEFAULT 0,
        crowd_roi REAL DEFAULT 0,
        crowd_visitors INTEGER DEFAULT 0,
        crowd_ppc REAL DEFAULT 0,
        site_spend REAL DEFAULT 0,
        site_sales REAL DEFAULT 0,
        site_roi REAL DEFAULT 0,
        site_visitors INTEGER DEFAULT 0,
        site_ppc REAL DEFAULT 0,
        refund_rate REAL DEFAULT 0,
        repurchase_rate REAL DEFAULT 0,
        cross_sell_rate REAL DEFAULT 0,
        buyers INTEGER DEFAULT 0,
        avg_order_value REAL DEFAULT 0,
        payment_qty INTEGER DEFAULT 0,
        cart_qty INTEGER DEFAULT 0,
        fav_users INTEGER DEFAULT 0,
        click_rate REAL DEFAULT 0,
        score INTEGER DEFAULT 0,
        data_source TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, month)
    );

    CREATE TABLE IF NOT EXISTS paid_detail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        date_range TEXT NOT NULL,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        cost REAL DEFAULT 0,
        ctr REAL DEFAULT 0,
        cpc REAL DEFAULT 0,
        cpm REAL DEFAULT 0,
        total_gmv REAL DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        direct_gmv REAL DEFAULT 0,
        indirect_gmv REAL DEFAULT 0,
        roi REAL DEFAULT 0,
        cart_adds INTEGER DEFAULT 0,
        cart_rate REAL DEFAULT 0,
        favs INTEGER DEFAULT 0,
        new_buyers INTEGER DEFAULT 0,
        members_gmv REAL DEFAULT 0,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, date_range)
    );

    CREATE INDEX IF NOT EXISTS idx_daily_product ON daily_data(product_id);
    CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_data(date);

    CREATE TABLE IF NOT EXISTS daily_data_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id TEXT NOT NULL DEFAULT 'default',
        product_id TEXT NOT NULL,
        date DATE NOT NULL,
        source_system TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_batch_id TEXT,
        source_filename TEXT,
        payload_json TEXT NOT NULL,
        field_presence_json TEXT NOT NULL DEFAULT '{}',
        quality_status TEXT NOT NULL DEFAULT 'passed',
        observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shop_id, product_id, date, source_system, source_type, source_batch_id)
    );
    CREATE INDEX IF NOT EXISTS idx_daily_observations_key
        ON daily_data_observations(shop_id, product_id, date);
    CREATE INDEX IF NOT EXISTS idx_daily_observations_source
        ON daily_data_observations(source_system, source_type, observed_at DESC);

    CREATE TABLE IF NOT EXISTS daily_data_observations_quarantine (
        quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_id INTEGER NOT NULL UNIQUE,
        shop_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        date DATE NOT NULL,
        source_system TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_batch_id TEXT,
        source_filename TEXT,
        payload_json TEXT NOT NULL,
        field_presence_json TEXT NOT NULL DEFAULT '{}',
        quality_status TEXT NOT NULL DEFAULT 'passed',
        observed_at TIMESTAMP,
        quarantine_reason TEXT NOT NULL,
        quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_observation_quarantine_key
        ON daily_data_observations_quarantine(shop_id, product_id, date);

    CREATE TABLE IF NOT EXISTS fact_field_lineage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id TEXT NOT NULL DEFAULT 'default',
        product_id TEXT NOT NULL,
        date DATE NOT NULL,
        field_key TEXT NOT NULL,
        effective_source_system TEXT NOT NULL,
        effective_source_type TEXT NOT NULL,
        source_batch_id TEXT,
        source_role TEXT NOT NULL,
        fallback_used INTEGER NOT NULL DEFAULT 0,
        conflict_status TEXT NOT NULL DEFAULT 'none',
        observed_sources_json TEXT NOT NULL DEFAULT '[]',
        effective_value_json TEXT,
        reason TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shop_id, product_id, date, field_key)
    );
    -- 附属索引已裁撤：所有在线查询走 UNIQUE(shop_id, product_id, date, field_key)
    -- 自动索引；历史冗余 idx_fact_lineage_product_date / idx_fact_lineage_source
    -- 由 db_migrations 外层 DROP 收尾（2026-09-23 体积治理）。

    CREATE TABLE IF NOT EXISTS reconciliation_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id TEXT NOT NULL DEFAULT 'default',
        product_id TEXT NOT NULL,
        date DATE NOT NULL,
        field_key TEXT NOT NULL,
        status TEXT NOT NULL,
        primary_source TEXT,
        effective_source_system TEXT NOT NULL,
        values_json TEXT NOT NULL DEFAULT '[]',
        delta REAL,
        threshold REAL,
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shop_id, product_id, date, field_key)
    );
    CREATE INDEX IF NOT EXISTS idx_reconciliation_status
        ON reconciliation_results(status, date DESC);
    CREATE INDEX IF NOT EXISTS idx_weekly_product ON weekly_data(product_id);
    CREATE INDEX IF NOT EXISTS idx_weekly_date ON weekly_data(week_start);
    CREATE INDEX IF NOT EXISTS idx_monthly_product ON monthly_data(product_id);
    CREATE INDEX IF NOT EXISTS idx_monthly_month ON monthly_data(month);

    -- 原始派米 BI 月度商品总览字段：保留报表中未映射到 monthly_data 的完整字段。
    -- 每个商品/月份只有一份当前有效载荷，导入时按月份整体替换，便于回滚。
    CREATE TABLE IF NOT EXISTS monthly_source_payload (
        product_id TEXT NOT NULL,
        month TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (product_id, month)
    );
    CREATE INDEX IF NOT EXISTS idx_monthly_source_payload_month
        ON monthly_source_payload(month);

    -- Retention and archive metadata live in the online database even when
    -- large raw payloads are moved to external compressed files.
    CREATE TABLE IF NOT EXISTS retention_policies (
        policy_key TEXT PRIMARY KEY,
        source_kind TEXT NOT NULL,
        source_table TEXT NOT NULL,
        retention_days INTEGER NOT NULL,
        mode TEXT NOT NULL DEFAULT 'archive',
        protected INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_retention_policies_table
        ON retention_policies(source_table, protected);

    CREATE TABLE IF NOT EXISTS archive_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        archive_key TEXT NOT NULL UNIQUE,
        source_kind TEXT NOT NULL,
        source_table TEXT NOT NULL,
        source_batch_id TEXT,
        archive_path TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        row_count INTEGER NOT NULL DEFAULT 0,
        min_value TEXT,
        max_value TEXT,
        archived_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'verified',
        metadata_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_archive_catalog_source
        ON archive_catalog(source_table, min_value, max_value);
    CREATE INDEX IF NOT EXISTS idx_archive_catalog_archived_at
        ON archive_catalog(archived_at DESC);

    -- 字段目录由导入器按源文件真实表头维护，供设置接口和商品字段选择器使用。
    CREATE TABLE IF NOT EXISTS source_field_catalog (
        field_key TEXT PRIMARY KEY,
        source_column TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL,
        group_name TEXT NOT NULL DEFAULT 'BI 数据源字段',
        data_type TEXT NOT NULL DEFAULT 'text',
        format TEXT NOT NULL DEFAULT 'text',
        source_type TEXT NOT NULL DEFAULT 'bi_monthly_overview',
        available_months_json TEXT NOT NULL DEFAULT '[]',
        nonempty_count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_source_field_catalog_source_type
        ON source_field_catalog(source_type, source_column);
    CREATE INDEX IF NOT EXISTS idx_paid_product ON paid_detail(product_id);
    CREATE INDEX IF NOT EXISTS idx_paid_product_imported ON paid_detail(product_id, imported_at DESC);

    CREATE TABLE IF NOT EXISTS operation_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        action_date DATE NOT NULL,
        action_type TEXT,
        action_detail TEXT,
        before_payment REAL DEFAULT 0,
        before_visitors INTEGER DEFAULT 0,
        before_conversion REAL DEFAULT 0,
        before_roi REAL DEFAULT 0,
        after_payment REAL DEFAULT 0,
        after_visitors INTEGER DEFAULT 0,
        after_conversion REAL DEFAULT 0,
        after_roi REAL DEFAULT 0,
        payment_change REAL DEFAULT 0,
        conversion_change REAL DEFAULT 0,
        roi_change REAL DEFAULT 0,
        effectiveness_score REAL DEFAULT 0,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_actions_product ON operation_actions(product_id);
    CREATE INDEX IF NOT EXISTS idx_actions_date ON operation_actions(action_date);

    CREATE TABLE IF NOT EXISTS import_batches (
        id TEXT PRIMARY KEY,
        shop_id TEXT NOT NULL DEFAULT 'default',
        source_type TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        total_rows INTEGER NOT NULL DEFAULT 0,
        valid_rows INTEGER NOT NULL DEFAULT 0,
        invalid_rows INTEGER NOT NULL DEFAULT 0,
        inserted_count INTEGER NOT NULL DEFAULT 0,
        updated_count INTEGER NOT NULL DEFAULT 0,
        quality_summary TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_import_batches_status ON import_batches(status);

    CREATE TABLE IF NOT EXISTS import_staging_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL,
        row_no INTEGER NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'staged',
        staged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        published_at TIMESTAMP,
        UNIQUE(batch_id, row_no),
        FOREIGN KEY (batch_id) REFERENCES import_batches(id)
    );
    CREATE INDEX IF NOT EXISTS idx_import_staging_batch ON import_staging_rows(batch_id, row_no);

    CREATE TABLE IF NOT EXISTS import_batch_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL,
        table_name TEXT NOT NULL,
        business_key TEXT NOT NULL,
        previous_row TEXT,
        written_by TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES import_batches(id)
    );
    CREATE INDEX IF NOT EXISTS idx_import_batch_changes_batch ON import_batch_changes(batch_id);
    CREATE INDEX IF NOT EXISTS idx_import_batch_changes_created_at ON import_batch_changes(created_at);

    CREATE TABLE IF NOT EXISTS import_previews (
        id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        content BLOB NOT NULL,
        mapping_json TEXT NOT NULL,
        quality_summary TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_import_previews_created_at ON import_previews(created_at);

    CREATE TABLE IF NOT EXISTS import_scan_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        folder_path TEXT NOT NULL,
        file_pattern TEXT NOT NULL DEFAULT '*',
        source_type TEXT NOT NULL DEFAULT 'auto',
        mapping_template_json TEXT NOT NULL DEFAULT '{}',
        cron_expr TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        last_run TEXT,
        next_run TEXT,
        lease_token TEXT,
        lease_until TEXT,
        last_error TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_import_scan_jobs_due
        ON import_scan_jobs(enabled, status, next_run);

    CREATE TABLE IF NOT EXISTS import_scan_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        canonical_path TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        mtime_ns INTEGER NOT NULL,
        source_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        preview_id TEXT,
        batch_id TEXT,
        error_code TEXT,
        error_message TEXT,
        discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        imported_at TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(job_id, canonical_path, source_hash),
        FOREIGN KEY (job_id) REFERENCES import_scan_jobs(id)
    );
    CREATE INDEX IF NOT EXISTS idx_import_scan_files_job ON import_scan_files(job_id, updated_at);
    CREATE INDEX IF NOT EXISTS idx_import_scan_files_status ON import_scan_files(job_id, status);

    CREATE TABLE IF NOT EXISTS import_scan_runs (
        id TEXT PRIMARY KEY,
        job_id INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        discovered_count INTEGER NOT NULL DEFAULT 0,
        imported_count INTEGER NOT NULL DEFAULT 0,
        blocked_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        FOREIGN KEY (job_id) REFERENCES import_scan_jobs(id)
    );
    CREATE INDEX IF NOT EXISTS idx_import_scan_runs_job ON import_scan_runs(job_id, started_at DESC);

    CREATE TABLE IF NOT EXISTS store_daily_facts (
        shop_id TEXT NOT NULL DEFAULT 'default',
        date DATE NOT NULL,
        payment_amount REAL,
        successful_refund_amount REAL,
        product_visitors INTEGER,
        payment_buyers INTEGER,
        returning_payment_buyers INTEGER,
        ad_spend REAL,
        source_batch_id TEXT,
        PRIMARY KEY (shop_id, date)
    );
    CREATE TABLE IF NOT EXISTS promotion_daily_facts (
        shop_id TEXT NOT NULL DEFAULT 'default',
        date DATE NOT NULL,
        channel TEXT NOT NULL,
        campaign_id TEXT NOT NULL DEFAULT '',
        unit_id TEXT NOT NULL DEFAULT '',
        product_id TEXT NOT NULL DEFAULT '',
        grain TEXT NOT NULL DEFAULT '',
        campaign_name TEXT NOT NULL DEFAULT '',
        cart_adds INTEGER,
        cart_cost REAL,
        new_buyers INTEGER,
        ad_spend REAL,
        attributed_payment_amount REAL,
        impressions INTEGER,
        clicks INTEGER,
        payment_buyers INTEGER,
        direct_payment_amount REAL,
        indirect_payment_amount REAL,
        source_batch_id TEXT,
        PRIMARY KEY (shop_id, date, channel, campaign_id, unit_id, product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_promotion_daily_facts_grain ON promotion_daily_facts(date, channel, campaign_id, unit_id, product_id);
    CREATE TABLE IF NOT EXISTS promotion_period_summary (
        shop_id TEXT NOT NULL DEFAULT 'default',
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        channel TEXT NOT NULL,
        ad_spend REAL,
        source_batch_id TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (shop_id, period_start, period_end, channel)
    );
    CREATE INDEX IF NOT EXISTS idx_promotion_period_summary_period
        ON promotion_period_summary(shop_id, period_start, period_end);

    CREATE TABLE IF NOT EXISTS promotion_creatives (
        shop_id TEXT NOT NULL DEFAULT 'default',
        creative_id TEXT NOT NULL,
        creative_name TEXT NOT NULL DEFAULT '',
        image_url TEXT NOT NULL DEFAULT '',
        video_url TEXT NOT NULL DEFAULT '',
        creative_format TEXT NOT NULL DEFAULT '',
        product_id TEXT NOT NULL DEFAULT '',
        product_name TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (shop_id, creative_id)
    );
    CREATE INDEX IF NOT EXISTS idx_promotion_creatives_product
        ON promotion_creatives(shop_id, product_id);

    CREATE TABLE IF NOT EXISTS promotion_creative_daily (
        shop_id TEXT NOT NULL DEFAULT 'default',
        date DATE NOT NULL,
        channel TEXT NOT NULL,
        creative_id TEXT NOT NULL,
        product_id TEXT NOT NULL DEFAULT '',
        campaign_id TEXT NOT NULL DEFAULT '',
        ad_spend REAL,
        attributed_payment_amount REAL,
        impressions INTEGER,
        clicks INTEGER,
        payment_buyers INTEGER,
        direct_payment_amount REAL,
        indirect_payment_amount REAL,
        cart_adds INTEGER,
        new_buyers INTEGER,
        source_batch_id TEXT,
        PRIMARY KEY (shop_id, date, channel, creative_id)
    );
    CREATE INDEX IF NOT EXISTS idx_promotion_creative_daily_product
        ON promotion_creative_daily(shop_id, product_id, date);

    CREATE TABLE IF NOT EXISTS promotion_campaign_items (
        shop_id TEXT NOT NULL DEFAULT 'default',
        campaign_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        campaign_name TEXT NOT NULL DEFAULT '',
        product_name TEXT NOT NULL DEFAULT '',
        image_url TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (shop_id, campaign_id, product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_promotion_campaign_items_product
        ON promotion_campaign_items(shop_id, product_id);

    CREATE TABLE IF NOT EXISTS lifecycle_profiles (
        product_id TEXT PRIMARY KEY,
        recommended_stage TEXT,
        manual_stage TEXT,
        stage_locked INTEGER NOT NULL DEFAULT 0,
        seasonal_attribute TEXT,
        seasonal_source TEXT,
        confidence TEXT,
        rationale TEXT,
        next_key_date TEXT,
        version INTEGER NOT NULL DEFAULT 1,
        updated_by TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS lifecycle_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        recommended_stage TEXT,
        manual_stage TEXT,
        seasonal_attribute TEXT,
        locked INTEGER NOT NULL DEFAULT 0,
        reason TEXT,
        operator TEXT,
        version INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS period_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_type TEXT NOT NULL CHECK(period_type IN ('day','week','month')),
        period_key TEXT NOT NULL,
        summary TEXT NOT NULL,
        conclusions TEXT NOT NULL,
        next_actions TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        sections TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'draft',
        template_version TEXT NOT NULL DEFAULT '',
        target_amount REAL,
        category_mode TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(period_type, period_key)
    );

    CREATE TABLE IF NOT EXISTS goal_versions (
        year INTEGER PRIMARY KEY,
        version INTEGER NOT NULL,
        annual_target REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS daily_goals (
        year INTEGER NOT NULL,
        goal_date DATE NOT NULL,
        target_amount REAL NOT NULL,
        source TEXT NOT NULL DEFAULT 'recommended',
        reason TEXT,
        version INTEGER NOT NULL,
        PRIMARY KEY (year, goal_date)
    );
    CREATE INDEX IF NOT EXISTS idx_daily_goals_year_date ON daily_goals(year, goal_date);

    CREATE TABLE IF NOT EXISTS goal_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        period_type TEXT NOT NULL,
        period_key TEXT NOT NULL,
        target_amount REAL NOT NULL,
        operator TEXT NOT NULL,
        reason TEXT NOT NULL,
        version INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_goal_adjustments_year ON goal_adjustments(year, created_at DESC);

    CREATE TABLE IF NOT EXISTS goal_locks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        period_type TEXT NOT NULL CHECK(period_type IN ('year', 'quarter', 'month', 'week', 'date')),
        period_key TEXT NOT NULL,
        version INTEGER NOT NULL,
        locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(year, period_type, period_key)
    );
    CREATE INDEX IF NOT EXISTS idx_goal_locks_year ON goal_locks(year);

    CREATE TABLE IF NOT EXISTS product_actions (
        id TEXT PRIMARY KEY,
        action_group_id TEXT,
        product_id TEXT NOT NULL,
        purpose_type TEXT NOT NULL,
        purpose_note TEXT NOT NULL,
        action_type TEXT NOT NULL,
        action_detail TEXT NOT NULL,
        target_metric TEXT NOT NULL,
        expected_change REAL,
        target_value REAL,
        acceptance_criteria TEXT,
        status TEXT NOT NULL,
        planned_at DATE NOT NULL,
        executed_at DATE,
        observer_window_days INTEGER NOT NULL,
        assigned_to TEXT,
        blocked_reason TEXT,
        expected_recovery_at DATE,
        before_metric_value REAL,
        after_metric_value REAL,
        result_change REAL,
        calculation_note TEXT,
        review_effective INTEGER,
        review_reason TEXT,
        review_conclusion TEXT,
        review_next_action TEXT,
        reviewed_by TEXT,
        reviewed_at TIMESTAMP,
        source_period_type TEXT,
        source_period_key TEXT,
        source_compare_mode TEXT,
        source_compare_period_key TEXT,
        source_product_id TEXT,
        source_problem_key TEXT,
        source_diagnosis_snapshot TEXT,
        verification_period_type TEXT,
        verification_period_key TEXT,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    CREATE INDEX IF NOT EXISTS idx_product_actions_status ON product_actions(status, planned_at);
    CREATE INDEX IF NOT EXISTS idx_product_actions_product ON product_actions(product_id);

    CREATE TABLE IF NOT EXISTS product_action_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_id TEXT NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        detail TEXT,
        operator TEXT,
        version INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (action_id) REFERENCES product_actions(id)
    );
    CREATE INDEX IF NOT EXISTS idx_product_action_history_action ON product_action_history(action_id, id);

    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS shop_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT NOT NULL,
        target_gsv REAL DEFAULT 0,
        target_ad_spend REAL DEFAULT 0,
        target_ad_ratio REAL DEFAULT 0,
        target_conversion REAL DEFAULT 0,
        target_refund_rate REAL DEFAULT 0,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(period)
    );

    CREATE TABLE IF NOT EXISTS product_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT,
        tier TEXT,
        period TEXT NOT NULL,
        target_gsv REAL DEFAULT 0,
        target_ad_spend REAL DEFAULT 0,
        target_ad_ratio REAL DEFAULT 0,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, period)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_date DATE NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT DEFAULT 'warning',
        title TEXT,
        detail TEXT,
        metric_name TEXT,
        current_value REAL DEFAULT 0,
        target_value REAL DEFAULT 0,
        period TEXT,
        dismissed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts(alert_date);
    CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);

    CREATE TABLE IF NOT EXISTS product_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        period TEXT NOT NULL,
        sales_score REAL DEFAULT 0,
        conversion_score REAL DEFAULT 0,
        roi_score REAL DEFAULT 0,
        refund_score REAL DEFAULT 0,
        growth_score REAL DEFAULT 0,
        review_score REAL DEFAULT 0,
        gmv_change_score REAL DEFAULT 0,
        ad_spend_change_score REAL DEFAULT 0,
        roi_change_score REAL DEFAULT 0,
        refund_rate_score REAL DEFAULT 0,
        cart_rate_score REAL DEFAULT 0,
        search_ratio_score REAL DEFAULT 0,
        new_customer_cost_score REAL DEFAULT 0,
        direct_cart_cost_score REAL DEFAULT 0,
        total_cart_cost_score REAL DEFAULT 0,
        repurchase_rate_score REAL DEFAULT 0,
        cross_sell_rate_score REAL DEFAULT 0,
        search_ctr_vs_industry_score REAL DEFAULT 0,
        health_score REAL DEFAULT 0,
        health_level TEXT,
        alert_dimensions TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, period)
    );
    CREATE INDEX IF NOT EXISTS idx_health_product ON product_health(product_id);
    CREATE INDEX IF NOT EXISTS idx_health_period ON product_health(period);

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        review_date TEXT,
        content TEXT NOT NULL,
        rating INTEGER DEFAULT 5,
        reviewer TEXT DEFAULT '',
        is_effective INTEGER DEFAULT 1,
        sentiment TEXT DEFAULT 'neutral',
        positive_dims TEXT DEFAULT '[]',
        negative_dims TEXT DEFAULT '[]',
        scenes TEXT DEFAULT '[]',
        has_image INTEGER DEFAULT 0,
        source TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
    CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment);

    CREATE TABLE IF NOT EXISTS review_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        analysis_date TEXT,
        total_reviews INTEGER DEFAULT 0,
        positive_rate REAL DEFAULT 0,
        negative_rate REAL DEFAULT 0,
        effective_rate REAL DEFAULT 0,
        top_positive_dims TEXT DEFAULT '[]',
        top_negative_dims TEXT DEFAULT '[]',
        top_scenes TEXT DEFAULT '[]',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, analysis_date)
    );
    CREATE INDEX IF NOT EXISTS idx_review_summary_product ON review_summary(product_id);

    CREATE TABLE IF NOT EXISTS alert_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT 'store',
        metric TEXT NOT NULL,
        operator TEXT NOT NULL CHECK(operator IN ('gt','lt','gte','lte')),
        threshold REAL NOT NULL,
        level TEXT NOT NULL DEFAULT 'warning' CHECK(level IN ('info','warning','danger')),
        enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS product_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        note TEXT NOT NULL,
        created_by TEXT DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );

    CREATE TABLE IF NOT EXISTS market_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_date TEXT NOT NULL,
        category_path TEXT,
        category_short TEXT,
        period_30d TEXT,
        period_7d TEXT,
        period_trend TEXT,
        total_keywords INTEGER DEFAULT 0,
        avg_ctr_7d REAL,
        avg_cvr_30d REAL,
        top5_keywords TEXT,
        summary_data TEXT,
        keywords_data TEXT,
        need_stats_data TEXT,
        dimension_details TEXT,
        histograms_data TEXT,
        rankings_data TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(analysis_date, category_path)
    );

    CREATE TABLE IF NOT EXISTS market_keyword_opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_date TEXT NOT NULL,
        keyword TEXT NOT NULL,
        pop_30d REAL,
        ctr_7d REAL,
        cvr_30d REAL,
        opportunity_category TEXT,
        opportunity_score REAL,
        need_tags TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_market_date ON market_analysis(analysis_date);
    CREATE INDEX IF NOT EXISTS idx_market_category ON market_analysis(category_path);
    CREATE INDEX IF NOT EXISTS idx_market_opp_date ON market_keyword_opportunities(analysis_date);
    CREATE INDEX IF NOT EXISTS idx_market_opp_category ON market_keyword_opportunities(opportunity_category);

    CREATE TABLE IF NOT EXISTS market_snapshot_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_type TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        source_hash TEXT NOT NULL UNIQUE,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_items (
        batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        cate_name TEXT, item_id TEXT NOT NULL, title TEXT, product_url TEXT,
        core_keyword TEXT, shop_name TEXT, shop_type TEXT, uv_value REAL, uv_range TEXT,
        pay_buyer_value REAL, pay_buyer_range TEXT, rank INTEGER, trend TEXT,
        UNIQUE(batch_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_searches (
        batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        cate_name TEXT, keyword TEXT NOT NULL, search_heat_value REAL, search_heat_range TEXT,
        pay_rate_value REAL, pay_rate_range TEXT, click_rate_value REAL, click_rate_range TEXT,
        rank INTEGER, UNIQUE(batch_id, cate_name, keyword)
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_rival_items (
        batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        item_id TEXT NOT NULL, title TEXT, shop_name TEXT, tag TEXT,
        pay_buyer_value REAL, pay_buyer_range TEXT, transaction_growth TEXT,
        uv_value REAL, uv_range TEXT, traffic_growth TEXT, estimated_payment_amount TEXT,
        UNIQUE(batch_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS market_snapshot_rival_shops (
        batch_id INTEGER NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
        shop_id TEXT NOT NULL, shop_name TEXT, address TEXT, tag TEXT,
        pay_buyer_value REAL, pay_buyer_range TEXT, transaction_growth TEXT,
        uv_value REAL, uv_range TEXT, traffic_growth TEXT,
        UNIQUE(batch_id, shop_id)
    );
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_item_period ON market_snapshot_items(period_start, period_end, item_id);
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_search_period ON market_snapshot_searches(period_start, period_end, keyword);
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_rival_item_period ON market_snapshot_rival_items(period_start, period_end, item_id);
    CREATE INDEX IF NOT EXISTS idx_market_snapshot_rival_shop_period ON market_snapshot_rival_shops(period_start, period_end, shop_id);

    CREATE TABLE IF NOT EXISTS market_item_links (
        item_id TEXT PRIMARY KEY,
        title TEXT,
        pic_url TEXT,
        detail_url TEXT,
        source_filename TEXT NOT NULL,
        period_start TEXT,
        period_end TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS product_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        is_auto INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, tag)
    );

    CREATE TABLE IF NOT EXISTS operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        detail TEXT,
        operator TEXT DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        operator TEXT NOT NULL,
        reason TEXT NOT NULL,
        before_value TEXT,
        after_value TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
      ON audit_logs(entity_type, entity_id, id);

    CREATE TABLE IF NOT EXISTS chart_events (
        id INTEGER PRIMARY KEY,
        event_date TEXT,
        title TEXT,
        description TEXT,
        color TEXT DEFAULT '#EF4444',
        chart_type TEXT DEFAULT 'sales',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # 搜索词效能
    conn.execute('''CREATE TABLE IF NOT EXISTS keyword_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        keyword TEXT,
        popularity INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0,
        cost REAL DEFAULT 0,
        gmv REAL DEFAULT 0,
        cvr REAL DEFAULT 0,
        roi REAL DEFAULT 0,
        cpc REAL DEFAULT 0,
        conversion INTEGER DEFAULT 0,
        efficacy REAL DEFAULT 0,
        category TEXT DEFAULT '流量词',
        data_source TEXT DEFAULT '',
        imported_at TEXT DEFAULT (datetime('now')),
        UNIQUE(date, keyword)
    )''')

    # 任务看板
    conn.execute('''CREATE TABLE IF NOT EXISTS task_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT DEFAULT 'todo',
        priority TEXT DEFAULT 'P2',
        assignee TEXT DEFAULT '',
        due_date TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )''')

    # 用户KPI
    conn.execute('''CREATE TABLE IF NOT EXISTS user_kpis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        period TEXT,
        target_gmv REAL DEFAULT 0,
        actual_gmv REAL DEFAULT 0,
        achievement_rate REAL DEFAULT 0,
        rating TEXT DEFAULT 'C',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )''')

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id INTEGER PRIMARY KEY,
        task_name TEXT,
        task_type TEXT DEFAULT 'data_import',
        cron_expr TEXT,
        file_pattern TEXT,
        enabled INTEGER DEFAULT 1,
        last_run TEXT,
        next_run TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS collector_runs (
        id TEXT PRIMARY KEY,
        source_key TEXT NOT NULL,
        shop_id TEXT NOT NULL DEFAULT 'default',
        window_start TEXT,
        window_end TEXT,
        mode TEXT NOT NULL DEFAULT 'manual',
        status TEXT NOT NULL DEFAULT 'queued',
        priority INTEGER NOT NULL DEFAULT 100,
        attempt INTEGER NOT NULL DEFAULT 0,
        worker_id TEXT,
        lease_until TEXT,
        requested_by TEXT,
        started_at TEXT,
        finished_at TEXT,
        checkpoint_json TEXT NOT NULL DEFAULT '{}',
        stats_json TEXT NOT NULL DEFAULT '{}',
        error_code TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS collector_leases (
        source_key TEXT NOT NULL,
        shop_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        lease_until TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (source_key, shop_id),
        FOREIGN KEY (run_id) REFERENCES collector_runs(id)
    );
    CREATE INDEX IF NOT EXISTS idx_collector_leases_until ON collector_leases(lease_until);

    CREATE INDEX IF NOT EXISTS idx_collector_runs_status
        ON collector_runs(status, priority, created_at);
    CREATE INDEX IF NOT EXISTS idx_collector_runs_source_window
        ON collector_runs(source_key, shop_id, window_start, window_end);

    CREATE TABLE IF NOT EXISTS collector_checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        unit_type TEXT NOT NULL,
        unit_key TEXT NOT NULL,
        page_no INTEGER,
        cursor TEXT,
        status TEXT NOT NULL,
        row_count INTEGER NOT NULL DEFAULT 0,
        source_hash TEXT,
        last_error_code TEXT,
        last_error_message TEXT,
        started_at TEXT,
        finished_at TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(run_id, unit_type, unit_key, page_no),
        FOREIGN KEY(run_id) REFERENCES collector_runs(id)
    );
    CREATE INDEX IF NOT EXISTS idx_collector_checkpoints_run
        ON collector_checkpoints(run_id, status);

    CREATE TABLE IF NOT EXISTS collector_quality_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        rule_key TEXT NOT NULL,
        severity TEXT NOT NULL,
        expected_value TEXT,
        actual_value TEXT,
        status TEXT NOT NULL,
        message TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES collector_runs(id)
    );
    CREATE INDEX IF NOT EXISTS idx_collector_quality_run
        ON collector_quality_results(run_id, status);

    CREATE TABLE IF NOT EXISTS collector_artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES collector_runs(id)
    );
    CREATE INDEX IF NOT EXISTS idx_collector_artifacts_run
        ON collector_artifacts(run_id, artifact_type);

    CREATE TABLE IF NOT EXISTS collector_data_staging (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        unit_type TEXT NOT NULL DEFAULT 'row',
        unit_key TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'staged',
        quality_message TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        published_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_collector_data_staging_batch
        ON collector_data_staging(batch_id, status);

    CREATE TABLE IF NOT EXISTS collector_health_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'warning',
        status TEXT NOT NULL DEFAULT 'open',
        fingerprint TEXT NOT NULL,
        message TEXT NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT,
        UNIQUE(source_key, alert_type, fingerprint, status)
    );
    CREATE INDEX IF NOT EXISTS idx_collector_health_alerts_status
        ON collector_health_alerts(status, last_seen_at);

    CREATE TABLE IF NOT EXISTS collector_schema_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT NOT NULL,
        schema_hash TEXT NOT NULL,
        schema_json TEXT NOT NULL,
        observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_key, schema_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_collector_schema_snapshots_source
        ON collector_schema_snapshots(source_key, observed_at);

    CREATE INDEX IF NOT EXISTS idx_product_tags_product ON product_tags(product_id);
    CREATE INDEX IF NOT EXISTS idx_product_tags_tag ON product_tags(tag);

    CREATE INDEX IF NOT EXISTS idx_keyword_metrics_date ON keyword_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_keyword_metrics_category ON keyword_metrics(category);
    CREATE INDEX IF NOT EXISTS idx_task_items_status ON task_items(status);
    CREATE INDEX IF NOT EXISTS idx_user_kpis_period ON user_kpis(period);
    ''')


    batch_change_columns = {row[1] for row in cursor.execute('PRAGMA table_info(import_batch_changes)').fetchall()}
    if 'written_by' not in batch_change_columns:
        cursor.execute("ALTER TABLE import_batch_changes ADD COLUMN written_by TEXT NOT NULL DEFAULT ''")
        cursor.execute("UPDATE import_batch_changes SET written_by = batch_id WHERE written_by = ''")
    if 'reverted_at' not in batch_change_columns:
        cursor.execute("ALTER TABLE import_batch_changes ADD COLUMN reverted_at TIMESTAMP")

    action_columns = {row[1] for row in cursor.execute('PRAGMA table_info(product_actions)').fetchall()}
    for column in (
        'source_rule_key', 'source_rule_name', 'source_period', 'source_category_mode',
        'source_period_type', 'source_period_key', 'source_compare_mode',
        'source_compare_period_key', 'source_product_id', 'source_problem_key',
        'source_diagnosis_snapshot', 'verification_period_type', 'verification_period_key',
    ):
        if column not in action_columns:
            cursor.execute(f'ALTER TABLE product_actions ADD COLUMN {column} TEXT')
    if 'target_value' not in action_columns:
        cursor.execute('ALTER TABLE product_actions ADD COLUMN target_value REAL')
    if 'acceptance_criteria' not in action_columns:
        cursor.execute('ALTER TABLE product_actions ADD COLUMN acceptance_criteria TEXT')

    # Structured period reviews (weekly/monthly) extend the original thin
    # summary/conclusions/next_actions columns. Existing rows keep working and
    # the legacy columns stay populated for backward compatibility.
    period_review_columns = {row[1] for row in cursor.execute('PRAGMA table_info(period_reviews)').fetchall()}
    if 'sections' not in period_review_columns:
        cursor.execute("ALTER TABLE period_reviews ADD COLUMN sections TEXT NOT NULL DEFAULT '{}'")
    if 'status' not in period_review_columns:
        cursor.execute("ALTER TABLE period_reviews ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
    if 'template_version' not in period_review_columns:
        cursor.execute("ALTER TABLE period_reviews ADD COLUMN template_version TEXT NOT NULL DEFAULT ''")
    if 'target_amount' not in period_review_columns:
        cursor.execute('ALTER TABLE period_reviews ADD COLUMN target_amount REAL')
    if 'category_mode' not in period_review_columns:
        cursor.execute("ALTER TABLE period_reviews ADD COLUMN category_mode TEXT NOT NULL DEFAULT ''")
    # 复盘目标不止销售额：利润、推广费、净费比也要能设目标（对齐经营目标表）。
    # 注意净费比分母是净销售额，与「费比」（÷GSV）不是一个口径，列名显式带 net。
    if 'target_profit' not in period_review_columns:
        cursor.execute('ALTER TABLE period_reviews ADD COLUMN target_profit REAL')
    if 'target_ad_spend' not in period_review_columns:
        cursor.execute('ALTER TABLE period_reviews ADD COLUMN target_ad_spend REAL')
    if 'target_net_expense_ratio' not in period_review_columns:
        cursor.execute('ALTER TABLE period_reviews ADD COLUMN target_net_expense_ratio REAL')

    alert_rule_columns = {row[1] for row in cursor.execute('PRAGMA table_info(alert_rules)').fetchall()}
    if 'name' not in alert_rule_columns:
        cursor.execute("ALTER TABLE alert_rules ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if 'scope' not in alert_rule_columns:
        cursor.execute("ALTER TABLE alert_rules ADD COLUMN scope TEXT NOT NULL DEFAULT 'store'")
    empty_alert_rule_count = cursor.execute(
        "SELECT COUNT(*) FROM alert_rules WHERE name = ''"
    ).fetchone()[0]
    if empty_alert_rule_count:
        cursor.execute("UPDATE alert_rules SET name = metric || ' 预警' WHERE name = ''")
    promotion_rule_count = cursor.execute(
        "SELECT COUNT(*) FROM alert_rules WHERE scope = 'promotion_product'"
    ).fetchone()[0]
    if promotion_rule_count == 0:
        cursor.executemany(
            '''INSERT INTO alert_rules (name, scope, metric, operator, threshold, level, enabled)
               VALUES (?, 'promotion_product', 'roi', 'lt', ?, ?, 1)''',
            [('ROI 低于安全线', 3.0, 'warning'), ('ROI 严重偏低', 1.5, 'danger')],
        )

    # SQLite cannot alter CHECK constraints in place; extend pre-existing goal lock tables.
    goal_locks_sql = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'goal_locks'"
    ).fetchone()
    goal_locks_definition = goal_locks_sql[0] if goal_locks_sql else ''
    if goal_locks_sql and ("'quarter'" not in goal_locks_definition or "'year'" not in goal_locks_definition):
        cursor.execute('ALTER TABLE goal_locks RENAME TO goal_locks_legacy')
        cursor.execute('''CREATE TABLE goal_locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            period_type TEXT NOT NULL CHECK(period_type IN ('year', 'quarter', 'month', 'week', 'date')),
            period_key TEXT NOT NULL,
            version INTEGER NOT NULL,
            locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, period_type, period_key)
        )''')
        cursor.execute('''INSERT INTO goal_locks (id, year, period_type, period_key, version, locked_at)
            SELECT id, year, period_type, period_key, version, locked_at FROM goal_locks_legacy''')
        cursor.execute('DROP TABLE goal_locks_legacy')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_goal_locks_year ON goal_locks(year)')

    # Migration: bind import batches to the shop that produced them. Existing
    # single-shop history remains owned by the default shop.
    cursor.execute("PRAGMA table_info(import_batches)")
    import_batch_columns = {row[1] for row in cursor.fetchall()}
    if 'shop_id' not in import_batch_columns:
        cursor.execute("ALTER TABLE import_batches ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'default'")
    cursor.execute('DROP INDEX IF EXISTS idx_import_batches_shop_status')
    cursor.execute('CREATE INDEX idx_import_batches_shop_status ON import_batches(shop_id, status, created_at DESC)')

    # Migration: bind persisted import previews to the shop that created them.
    # Existing previews belong to the legacy default shop.
    cursor.execute("PRAGMA table_info(import_previews)")
    import_preview_columns = {row[1] for row in cursor.fetchall()}
    if 'shop_id' not in import_preview_columns:
        cursor.execute("ALTER TABLE import_previews ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'default'")
    cursor.execute('DROP INDEX IF EXISTS idx_import_previews_shop_created')
    cursor.execute('CREATE INDEX idx_import_previews_shop_created ON import_previews(shop_id, created_at DESC)')

    # Migration: bind scheduled import scans to their owning shop. Existing
    # single-shop jobs remain owned by the legacy default shop.
    cursor.execute("PRAGMA table_info(import_scan_jobs)")
    import_scan_job_columns = {row[1] for row in cursor.fetchall()}
    if 'shop_id' not in import_scan_job_columns:
        cursor.execute("ALTER TABLE import_scan_jobs ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'default'")
    cursor.execute('DROP INDEX IF EXISTS idx_import_scan_jobs_shop_due')
    cursor.execute('CREATE INDEX idx_import_scan_jobs_shop_due ON import_scan_jobs(shop_id, enabled, status, next_run)')

    # Migration: add new health dimension columns if they don't exist
    new_health_cols = [
        'gmv_change_score', 'ad_spend_change_score', 'roi_change_score',
        'refund_rate_score', 'cart_rate_score', 'search_ratio_score',
        'new_customer_cost_score', 'direct_cart_cost_score', 'total_cart_cost_score',
        'repurchase_rate_score', 'cross_sell_rate_score', 'search_ctr_vs_industry_score',
        'alert_dimensions',
    ]
    cursor.execute("PRAGMA table_info(product_health)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    for col in new_health_cols:
        if col not in existing_cols:
            default = "TEXT DEFAULT '[]'" if col == 'alert_dimensions' else 'REAL DEFAULT 0'
            cursor.execute(f'ALTER TABLE product_health ADD COLUMN {col} {default}')

    # Migration: add new columns to products table
    new_product_cols = {
        'manager': 'TEXT DEFAULT \'\'',
        'starred': 'INTEGER DEFAULT 0',
        'parent_product_id': 'TEXT DEFAULT \'\'',
        'product_type': 'TEXT DEFAULT \'\'',
        'sku_code': 'TEXT DEFAULT \'\'',
        'source_status': 'TEXT DEFAULT \'\'',
        'product_tags': 'TEXT DEFAULT \'\'',
        'product_growth_stage': 'TEXT DEFAULT \'\'',
        'product_time_node': 'TEXT DEFAULT \'\'',
        'shop_label': 'TEXT DEFAULT \'\'',
    }
    cursor.execute("PRAGMA table_info(products)")
    existing_product_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_product_cols.items():
        if col not in existing_product_cols:
            cursor.execute(f'ALTER TABLE products ADD COLUMN {col} {col_def}')

    # Migration: add new columns to monthly_data table
    new_monthly_cols = {
        'payment_qty': 'INTEGER DEFAULT 0',
        'paid_ipv': 'INTEGER DEFAULT 0',
        'organic_ipv': 'INTEGER DEFAULT 0',
        'search_ipv': 'INTEGER DEFAULT 0',
        'recommend_ipv': 'INTEGER DEFAULT 0',
        'cart_users': 'INTEGER DEFAULT 0',
        'industry_ctr': 'REAL DEFAULT 0',
        'cross_sell_qty': 'INTEGER DEFAULT 0',
        'cross_sell_categories': 'INTEGER DEFAULT 0',
        'repurchase_users': 'INTEGER DEFAULT 0',
        'guide_visits': 'INTEGER DEFAULT 0',
        'guide_visitors': 'INTEGER DEFAULT 0',
        'guide_potential': 'INTEGER DEFAULT 0',
        'guide_potential_ratio': 'REAL DEFAULT 0',
        'new_buyers': 'INTEGER DEFAULT 0',
        'new_buyer_ratio': 'REAL DEFAULT 0',
        # 月度成本与利润（与 daily_data 同名同口径，可空 REAL，缺失必须保持 NULL）。
        'product_cost': 'REAL',
        'sales_cost': 'REAL',
        'custom_cost': 'REAL',
        'logistics_cost': 'REAL',
        'other_cost': 'REAL',
        'platform_fee': 'REAL',
        'after_sales_loss': 'REAL',
        'gross_profit': 'REAL',
        'operating_profit': 'REAL',
        'profit_rate': 'REAL',
        'profit_target': 'REAL',
    }
    cursor.execute("PRAGMA table_info(monthly_data)")
    existing_monthly_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_monthly_cols.items():
        if col not in existing_monthly_cols:
            cursor.execute(f'ALTER TABLE monthly_data ADD COLUMN {col} {col_def}')

    # Migration: add dimension/behavior columns to promotion_daily_facts.
    # grain tags each row's aggregation level ('channel'/'campaign'/'unit'/'product')
    # so report queries can sum a single grain instead of mixing overlapping rows.
    new_promotion_cols = {
        'grain': "TEXT NOT NULL DEFAULT ''",
        'campaign_name': "TEXT NOT NULL DEFAULT ''",
        'cart_adds': 'INTEGER',
        'cart_cost': 'REAL',
        'new_buyers': 'INTEGER',
    }
    cursor.execute("PRAGMA table_info(promotion_daily_facts)")
    existing_promotion_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_promotion_cols.items():
        if col not in existing_promotion_cols:
            cursor.execute(f'ALTER TABLE promotion_daily_facts ADD COLUMN {col} {col_def}')

    # Migration: add new columns to paid_detail table
    new_paid_cols = {
        'direct_orders': 'INTEGER DEFAULT 0',
        'indirect_orders': 'INTEGER DEFAULT 0',
        'click_conversion': 'REAL DEFAULT 0',
        'presale_roi': 'REAL DEFAULT 0',
        'total_cost': 'REAL DEFAULT 0',
        'direct_cart_adds': 'INTEGER DEFAULT 0',
        'indirect_cart_adds': 'INTEGER DEFAULT 0',
        'store_favs': 'INTEGER DEFAULT 0',
        'store_fav_cost': 'REAL DEFAULT 0',
        'total_fav_cart': 'INTEGER DEFAULT 0',
        'total_fav_cart_cost': 'REAL DEFAULT 0',
        'item_fav_cart': 'INTEGER DEFAULT 0',
        'item_fav_cart_cost': 'REAL DEFAULT 0',
        'total_favs': 'INTEGER DEFAULT 0',
        'item_fav_cost': 'REAL DEFAULT 0',
        'item_fav_rate': 'REAL DEFAULT 0',
        'cart_cost': 'REAL DEFAULT 0',
    }
    cursor.execute("PRAGMA table_info(paid_detail)")
    existing_paid_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_paid_cols.items():
        if col not in existing_paid_cols:
            cursor.execute(f'ALTER TABLE paid_detail ADD COLUMN {col} {col_def}')

    # Migration: add new columns to daily_data table
    new_daily_cols = {
        'uv_value': 'REAL DEFAULT 0',
        'cart_qty': 'INTEGER DEFAULT 0',
        'fav_users': 'INTEGER DEFAULT 0',
        'search_conversion': 'REAL DEFAULT 0',
        'search_visitors': 'INTEGER DEFAULT 0',
        'cart_users': 'INTEGER DEFAULT 0',
        'order_buyers': 'INTEGER DEFAULT 0',
        'order_items': 'INTEGER DEFAULT 0',
        'order_amount': 'REAL DEFAULT 0',
        'order_conversion': 'REAL DEFAULT 0',
        'new_payment_buyers': 'INTEGER DEFAULT 0',
        'returning_payment_buyers': 'INTEGER DEFAULT 0',
        'returning_payment_amount': 'REAL DEFAULT 0',
        'juhuasuan_payment_amount': 'REAL DEFAULT 0',
        'competitiveness_score': 'REAL DEFAULT 0',
        'year_to_date_payment_amount': 'REAL DEFAULT 0',
        'month_to_date_payment_amount': 'REAL DEFAULT 0',
        'month_to_date_payment_items': 'INTEGER DEFAULT 0',
        'search_payment_buyers': 'INTEGER DEFAULT 0',
        'structured_detail_conversion': 'REAL DEFAULT 0',
        'structured_detail_payment_ratio': 'REAL DEFAULT 0',
        'paid_ipv': 'INTEGER DEFAULT 0',
        'organic_ipv': 'INTEGER DEFAULT 0',
        'search_ipv': 'INTEGER DEFAULT 0',
        'recommend_ipv': 'INTEGER DEFAULT 0',
        'favorite_cart_rate': 'REAL DEFAULT 0',
        'repurchase_rate': 'REAL DEFAULT 0',
        'presale_amount': 'REAL DEFAULT 0',
        'presale_qty': 'INTEGER DEFAULT 0',
        'search_click_rate': 'REAL DEFAULT 0',
        'cross_sell_qty': 'INTEGER DEFAULT 0',
        'cross_sell_rate': 'REAL DEFAULT 0',
        'cross_sell_categories': 'INTEGER DEFAULT 0',
        'category_width': 'INTEGER DEFAULT 0',
        'repurchase_users': 'INTEGER DEFAULT 0',
        # 成本与利润字段（BI「运营视窗」原始列）。
        # 刻意使用可空 REAL 而不是 `DEFAULT 0`：成本缺失必须表现为 NULL，
        # 不能被静默默认成 0——否则「经营利润」会被高估成 净销售额−推广花费。
        # 口径：利润=支付预估；商品成本=净货品成本(支付)；推广花费沿用账单口径的 ad_spend。
        'product_cost': 'REAL',
        'sales_cost': 'REAL',
        'custom_cost': 'REAL',
        'logistics_cost': 'REAL',
        'other_cost': 'REAL',
        'platform_fee': 'REAL',
        'after_sales_loss': 'REAL',
        'gross_profit': 'REAL',
        'operating_profit': 'REAL',
        'profit_rate': 'REAL',
        'profit_target': 'REAL',
        # 推广平台明细（BI「商品总览」原始列）。同样刻意可空：
        # 平台当周期没投放时必须表现为 NULL，不能被当成 0 拉低费比。
        # 来源列：货品全站推花费 / 全站推广成交金额 / 首单礼金 / 品牌新享营销托管软件服务费。
        #
        # 说明：wujie_spend / wujie_payment 保留为「万相台」列的落库位置，
        # 但该列在近两年的 BI 导出中整列为 '--' 或 0，实际无界数据改由
        # promotion_daily_facts（万相台后台采集）提供，见 period_review_service。
        'wujie_spend': 'REAL',
        'wujie_payment': 'REAL',
        'product_sitewide_spend': 'REAL',
        'product_sitewide_payment': 'REAL',
        'gift_cost': 'REAL',
        'brand_marketing_spend': 'REAL',
    }
    cursor.execute("PRAGMA table_info(daily_data)")
    existing_daily_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_daily_cols.items():
        if col not in existing_daily_cols:
            cursor.execute(f'ALTER TABLE daily_data ADD COLUMN {col} {col_def}')

    # Migrate the product-day fact grain from product/date to
    # shop/product/date. SQLite cannot drop an inline UNIQUE constraint, so
    # existing databases need a one-time table rebuild.
    cursor.execute("PRAGMA table_info(daily_data)")
    daily_info = cursor.fetchall()
    daily_column_names = {row[1] for row in daily_info}
    if 'shop_id' not in daily_column_names:
        cursor.execute("ALTER TABLE daily_data ADD COLUMN shop_id TEXT NOT NULL DEFAULT 'default'")
        cursor.execute("PRAGMA table_info(daily_data)")
        daily_info = cursor.fetchall()

    unique_indexes = []
    for index_row in cursor.execute("PRAGMA index_list(daily_data)").fetchall():
        if index_row[2]:
            index_name = index_row[1]
            unique_indexes.append(tuple(
                column[2] for column in cursor.execute(f'PRAGMA index_info("{index_name}")').fetchall()
            ))
    if ('shop_id', 'product_id', 'date') not in unique_indexes:
        legacy_table = 'daily_data_legacy_shop_migration'
        legacy_exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (legacy_table,)
        ).fetchone()
        if legacy_exists:
            # Recover an interrupted rename/rebuild by restoring the legacy
            # table as the source, then retry the rebuild in this transaction.
            cursor.execute('DROP TABLE IF EXISTS daily_data')
            cursor.execute('ALTER TABLE daily_data_legacy_shop_migration RENAME TO daily_data')
            cursor.execute("PRAGMA table_info(daily_data)")
            daily_info = cursor.fetchall()
        cursor.execute('ALTER TABLE daily_data RENAME TO daily_data_legacy_shop_migration')
        definitions = []
        column_names = []
        for column in daily_info:
            name, column_type, not_null, default_value, primary_key = (
                column[1], column[2] or '', column[3], column[4], column[5]
            )
            column_names.append(name)
            if name == 'id' and primary_key:
                definitions.append('"id" INTEGER PRIMARY KEY AUTOINCREMENT')
                continue
            definition = f'"{name}" {column_type}'.rstrip()
            if not_null:
                definition += ' NOT NULL'
            if default_value is not None:
                definition += f' DEFAULT {default_value}'
            definitions.append(definition)
        definitions.append('UNIQUE(shop_id, product_id, date)')
        cursor.execute(f'CREATE TABLE daily_data ({", ".join(definitions)})')
        quoted_columns = ', '.join(f'"{name}"' for name in column_names)
        cursor.execute(
            f'INSERT INTO daily_data ({quoted_columns}) SELECT {quoted_columns} FROM {legacy_table}'
        )
        cursor.execute(f'DROP TABLE {legacy_table}')
    cursor.execute('DROP INDEX IF EXISTS idx_daily_product')
    cursor.execute('DROP INDEX IF EXISTS idx_daily_date')
    cursor.execute('CREATE INDEX idx_daily_product ON daily_data(shop_id, product_id)')
    cursor.execute('CREATE INDEX idx_daily_date ON daily_data(shop_id, date)')

    # Migration: add new columns to weekly_data table
    new_weekly_cols = {
        'industry_ctr': 'REAL DEFAULT 0',
    }
    cursor.execute("PRAGMA table_info(weekly_data)")
    existing_weekly_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_weekly_cols.items():
        if col not in existing_weekly_cols:
            cursor.execute(f'ALTER TABLE weekly_data ADD COLUMN {col} {col_def}')

    cursor.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    cursor.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'applied',
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, name, state) VALUES (?, ?, 'applied')",
        (SCHEMA_VERSION, 'legacy_schema_reconciliation'),
    )

    # Storage-growth migration: keep the online fact paths and retention scans
    # indexed without changing any rows.  This is deliberately idempotent so
    # application startup and standalone maintenance tools share one schema
    # upgrade path.
    storage_indexes = {
        'idx_daily_observations_latest':
            'CREATE INDEX IF NOT EXISTS idx_daily_observations_latest '
            'ON daily_data_observations(shop_id, product_id, date, observed_at DESC, id DESC)',
        'idx_fact_lineage_scope_date':
            'CREATE INDEX IF NOT EXISTS idx_fact_lineage_scope_date '
            'ON fact_field_lineage(shop_id, date, product_id, field_key)',
        'idx_collector_staging_retention':
            'CREATE INDEX IF NOT EXISTS idx_collector_staging_retention '
            'ON collector_data_staging(status, published_at, created_at)',
        'idx_collector_artifacts_created':
            'CREATE INDEX IF NOT EXISTS idx_collector_artifacts_created '
            'ON collector_artifacts(created_at, id)',
        'idx_collector_checkpoints_status_updated':
            'CREATE INDEX IF NOT EXISTS idx_collector_checkpoints_status_updated '
            'ON collector_checkpoints(status, updated_at, run_id)',
        # ``overview_context`` 要找出「最近一个在本店铺真正落了事实的导入批次」，
        # 写法是 import_batches 上挂三个相关子查询 EXISTS(source_batch_id = ? AND shop_id = ?)。
        # 这三张事实表原先都没有 source_batch_id 上的索引，于是 260 个批次 × 十几万行
        # 变成全表扫描，/api/overview 单次 45~116 秒，首页 KPI 一直卡在「等待加载…」。
        # 列序刻意把 source_batch_id 放前面：既满足这里的两列等值查找，
        # 也能服务那些只按 source_batch_id 过滤的既有查询
        # （scripts/quarantine_orphan_observations.py、db_quality_check.py 等）。
        'idx_store_daily_facts_source_batch':
            'CREATE INDEX IF NOT EXISTS idx_store_daily_facts_source_batch '
            'ON store_daily_facts(source_batch_id, shop_id)',
        'idx_promotion_daily_facts_source_batch':
            'CREATE INDEX IF NOT EXISTS idx_promotion_daily_facts_source_batch '
            'ON promotion_daily_facts(source_batch_id, shop_id)',
        'idx_daily_observations_source_batch':
            'CREATE INDEX IF NOT EXISTS idx_daily_observations_source_batch '
            'ON daily_data_observations(source_batch_id, shop_id)',
        # ``MetricsRepo.get_daily_matrix`` 在有品类筛选时会先物化一张
        # ``_source_meta`` 临时表：按 date 区间取观测行，再用窗口函数按
        # (shop_id, product_id, date, source_filename) 取最新一条，把
        # 日期+文件名映射回 source_batch_id / source_type。
        # 原先没有任何以 date 打头的索引，一个月区间要全表扫 11.7 万行，
        # 首页又会同时打 /api/overview 和 /api/overview/daily-matrix 两次，
        # 合计 ~1.4s。这个覆盖索引把窗口函数所需的全部列都放进索引里，
        # 让这一步变成纯索引扫描（0.71s → 0.31s）。
        'idx_daily_observations_date_source':
            'CREATE INDEX IF NOT EXISTS idx_daily_observations_date_source '
            'ON daily_data_observations(date, shop_id, product_id, source_filename, '
            'observed_at DESC, id DESC, source_batch_id, source_type)',
    }
    for statement in storage_indexes.values():
        cursor.execute(statement)

    # ``idx_daily_date`` and ``idx_daily_shop_date`` are byte-for-byte
    # duplicates on upgraded databases. Keep the canonical name and remove
    # only the redundant index; no data or constraint is affected.
    cursor.execute('DROP INDEX IF EXISTS idx_daily_shop_date')
    # The latest-observation index has the old lookup key as its left prefix,
    # while also satisfying the common ORDER BY observed_at/id LIMIT 1 path.
    cursor.execute('DROP INDEX IF EXISTS idx_daily_observations_key')
    # Lineage volume cleanup (2026-09-23): every online reader resolves lineage
    # by (shop_id, product_id, date) via the UNIQUE auto-index, so these two
    # legacy indexes were pure dead weight (~236 MiB on the live database).
    cursor.execute('DROP INDEX IF EXISTS idx_fact_lineage_product_date')
    cursor.execute('DROP INDEX IF EXISTS idx_fact_lineage_source')
    retention_defaults = [
        ('collector_data_staging', 'runtime', 'collector_data_staging', 14, 'purge_after_archive', 0),
        ('collector_artifacts', 'runtime', 'collector_artifacts', 30, 'archive', 0),
        ('collector_checkpoints', 'runtime', 'collector_checkpoints', 30, 'compact', 0),
        ('monthly_source_payload', 'raw_payload', 'monthly_source_payload', 180, 'archive', 0),
        ('bi_product_daily_raw', 'raw_payload', 'bi_product_daily_raw', 180, 'archive', 0),
        ('daily_data_observations', 'audit', 'daily_data_observations', 0, 'retain', 1),
        ('fact_field_lineage', 'audit', 'fact_field_lineage', 0, 'retain', 1),
    ]
    cursor.executemany(
        '''INSERT OR IGNORE INTO retention_policies
           (policy_key, source_kind, source_table, retention_days, mode, protected)
           VALUES (?, ?, ?, ?, ?, ?)''',
        retention_defaults,
    )
    cursor.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, name, state) "
        "VALUES (?, ?, 'applied')",
        (SCHEMA_VERSION, 'storage_growth_indexes'),
    )

if __name__ == '__main__':
    init_db()
