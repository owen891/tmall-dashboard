import sqlite3
import os
from contextlib import contextmanager
import yaml
from flask import current_app, has_app_context

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
    config = load_config()
    configured_path = config['data']['db_path']
    return configured_path if os.path.isabs(configured_path) else os.path.join(PROJECT_ROOT, configured_path)

def get_connection(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def get_db(db_path=None):
    """Context manager: 自动关闭连接，异常时也不泄漏"""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()

def init_db(db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

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

    CREATE TABLE IF NOT EXISTS daily_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        data_source TEXT,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, date)
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
    CREATE INDEX IF NOT EXISTS idx_weekly_product ON weekly_data(product_id);
    CREATE INDEX IF NOT EXISTS idx_weekly_date ON weekly_data(week_start);
    CREATE INDEX IF NOT EXISTS idx_monthly_product ON monthly_data(product_id);
    CREATE INDEX IF NOT EXISTS idx_monthly_month ON monthly_data(month);
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

    CREATE INDEX IF NOT EXISTS idx_product_tags_product ON product_tags(product_id);
    CREATE INDEX IF NOT EXISTS idx_product_tags_tag ON product_tags(tag);

    CREATE INDEX IF NOT EXISTS idx_keyword_metrics_date ON keyword_metrics(date);
    CREATE INDEX IF NOT EXISTS idx_keyword_metrics_category ON keyword_metrics(category);
    CREATE INDEX IF NOT EXISTS idx_task_items_status ON task_items(status);
    CREATE INDEX IF NOT EXISTS idx_user_kpis_period ON user_kpis(period);
    ''')

    conn.commit()

    batch_change_columns = {row[1] for row in cursor.execute('PRAGMA table_info(import_batch_changes)').fetchall()}
    if 'written_by' not in batch_change_columns:
        cursor.execute("ALTER TABLE import_batch_changes ADD COLUMN written_by TEXT NOT NULL DEFAULT ''")
        cursor.execute("UPDATE import_batch_changes SET written_by = batch_id WHERE written_by = ''")
        conn.commit()

    # SQLite cannot alter CHECK constraints in place; extend pre-existing goal lock tables.
    goal_locks_sql = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'goal_locks'"
    ).fetchone()
    goal_locks_definition = goal_locks_sql[0] if goal_locks_sql else ''
    if goal_locks_sql and ("'quarter'" not in goal_locks_definition or "'year'" not in goal_locks_definition):
        cursor.executescript('''
        ALTER TABLE goal_locks RENAME TO goal_locks_legacy;
        CREATE TABLE goal_locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            period_type TEXT NOT NULL CHECK(period_type IN ('year', 'quarter', 'month', 'week', 'date')),
            period_key TEXT NOT NULL,
            version INTEGER NOT NULL,
            locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, period_type, period_key)
        );
        INSERT INTO goal_locks (id, year, period_type, period_key, version, locked_at)
        SELECT id, year, period_type, period_key, version, locked_at FROM goal_locks_legacy;
        DROP TABLE goal_locks_legacy;
        CREATE INDEX IF NOT EXISTS idx_goal_locks_year ON goal_locks(year);
        ''')
        conn.commit()

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
            try:
                cursor.execute(f'ALTER TABLE product_health ADD COLUMN {col} {default}')
            except Exception:
                pass
    conn.commit()

    # Migration: add new columns to products table
    new_product_cols = {
        'manager': 'TEXT DEFAULT \'\'',
        'starred': 'INTEGER DEFAULT 0',
    }
    cursor.execute("PRAGMA table_info(products)")
    existing_product_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_product_cols.items():
        if col not in existing_product_cols:
            try:
                cursor.execute(f'ALTER TABLE products ADD COLUMN {col} {col_def}')
            except Exception:
                pass

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
    }
    cursor.execute("PRAGMA table_info(monthly_data)")
    existing_monthly_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_monthly_cols.items():
        if col not in existing_monthly_cols:
            try:
                cursor.execute(f'ALTER TABLE monthly_data ADD COLUMN {col} {col_def}')
            except Exception:
                pass

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
            try:
                cursor.execute(f'ALTER TABLE paid_detail ADD COLUMN {col} {col_def}')
            except Exception:
                pass

    # Migration: add new columns to daily_data table
    new_daily_cols = {
        'uv_value': 'REAL DEFAULT 0',
        'cart_qty': 'INTEGER DEFAULT 0',
        'fav_users': 'INTEGER DEFAULT 0',
        'search_conversion': 'REAL DEFAULT 0',
        'search_visitors': 'INTEGER DEFAULT 0',
        'cart_users': 'INTEGER DEFAULT 0',
    }
    cursor.execute("PRAGMA table_info(daily_data)")
    existing_daily_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_daily_cols.items():
        if col not in existing_daily_cols:
            try:
                cursor.execute(f'ALTER TABLE daily_data ADD COLUMN {col} {col_def}')
            except Exception:
                pass

    # Migration: add new columns to weekly_data table
    new_weekly_cols = {
        'industry_ctr': 'REAL DEFAULT 0',
    }
    cursor.execute("PRAGMA table_info(weekly_data)")
    existing_weekly_cols = {row[1] for row in cursor.fetchall()}
    for col, col_def in new_weekly_cols.items():
        if col not in existing_weekly_cols:
            try:
                cursor.execute(f'ALTER TABLE weekly_data ADD COLUMN {col} {col_def}')
            except Exception:
                pass

    conn.commit()
    conn.close()
    print(f"Database initialized: {db_path}")

if __name__ == '__main__':
    init_db()
