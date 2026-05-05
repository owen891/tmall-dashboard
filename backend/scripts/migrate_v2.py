"""
数据库迁移脚本 - 2026-05-04
功能：
1. 创建用户表
2. 重构 ProductLifecycle 表（硬编码月份改为动态行存储）
3. 创建 ProductLifecycleMeta 表
4. 添加缺失索引
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'dashboard.db')


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def table_exists(conn, table_name):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def column_exists(conn, table_name, column_name):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def create_users_table(conn):
    if table_exists(conn, 'users'):
        print("[SKIP] 用户表已存在")
        return

    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR UNIQUE NOT NULL,
            email VARCHAR UNIQUE,
            hashed_password VARCHAR NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            role VARCHAR DEFAULT 'viewer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_users_username ON users(username)")
    print("[OK] 创建用户表")


def create_product_lifecycle_meta_table(conn):
    if table_exists(conn, 'product_lifecycle_meta'):
        print("[SKIP] 产品生命周期元数据表已存在")
        return

    conn.execute("""
        CREATE TABLE product_lifecycle_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id VARCHAR UNIQUE NOT NULL,
            lifecycle_stage VARCHAR,
            lifecycle_curve TEXT,
            gsv_25_total FLOAT DEFAULT 0,
            gsv_26_total FLOAT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX idx_lifecycle_meta_product_id ON product_lifecycle_meta(product_id)")
    print("[OK] 创建产品生命周期元数据表")


def migrate_product_lifecycle_table(conn):
    if not table_exists(conn, 'product_lifecycle'):
        print("[SKIP] 产品生命周期表不存在，创建新表")
        conn.execute("""
            CREATE TABLE product_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id VARCHAR NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                gsv FLOAT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX idx_lifecycle_product_id ON product_lifecycle(product_id)")
        conn.execute("CREATE INDEX idx_lifecycle_year ON product_lifecycle(year)")
        conn.execute("CREATE INDEX idx_lifecycle_month ON product_lifecycle(month)")
        print("[OK] 创建新产品生命周期表")
        return

    if column_exists(conn, 'product_lifecycle', 'year'):
        print("[SKIP] 产品生命周期表已经是新结构")
        return

    old_columns = [
        'gsv_25_01', 'gsv_25_02', 'gsv_25_03', 'gsv_25_04', 'gsv_25_05', 'gsv_25_06',
        'gsv_25_07', 'gsv_25_08', 'gsv_25_09', 'gsv_25_10', 'gsv_25_11', 'gsv_25_12',
        'gsv_26_01', 'gsv_26_02', 'gsv_26_03', 'gsv_26_04', 'gsv_26_05', 'gsv_26_06',
        'gsv_26_07', 'gsv_26_08', 'gsv_26_09', 'gsv_26_10', 'gsv_26_11', 'gsv_26_12',
        'gsv_25_total', 'gsv_26_total', 'lifecycle_stage', 'lifecycle_curve'
    ]

    has_old_structure = all(column_exists(conn, 'product_lifecycle', col) for col in old_columns[:2])

    if has_old_structure:
        print("[MIGRATE] 迁移旧的产品生命周期表数据...")

        cursor = conn.execute("SELECT * FROM product_lifecycle")
        columns = [desc[0] for desc in cursor.description]
        old_rows = cursor.fetchall()

        conn.execute("DROP TABLE product_lifecycle")

        conn.execute("""
            CREATE TABLE product_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id VARCHAR NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                gsv FLOAT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("CREATE INDEX idx_lifecycle_product_id ON product_lifecycle(product_id)")
        conn.execute("CREATE INDEX idx_lifecycle_year ON product_lifecycle(year)")
        conn.execute("CREATE INDEX idx_lifecycle_month ON product_lifecycle(month)")

        new_rows = []
        for old_row in old_rows:
            row_dict = dict(zip(columns, old_row))
            product_id = row_dict.get('product_id', '')

            for year_short, month in [(25, range(1, 13)), (26, range(1, 13))]:
                for m in month:
                    col_name = f'gsv_{year_short}_{m:02d}'
                    gsv_value = row_dict.get(col_name, 0) or 0
                    if gsv_value != 0:
                        new_rows.append((product_id, year_short, m, gsv_value))

        if new_rows:
            conn.executemany(
                "INSERT INTO product_lifecycle (product_id, year, month, gsv) VALUES (?, ?, ?, ?)",
                new_rows
            )
            print(f"[OK] 迁移了 {len(new_rows)} 条生命周期数据")
        else:
            print("[OK] 无历史数据需要迁移")

        cursor = conn.execute("SELECT * FROM product_lifecycle")
        columns = [desc[0] for desc in cursor.description]
        for old_row in old_rows:
            row_dict = dict(zip(columns, old_row))
            product_id = row_dict.get('product_id', '')

            conn.execute(
                """
                INSERT INTO product_lifecycle_meta 
                (product_id, lifecycle_stage, lifecycle_curve, gsv_25_total, gsv_26_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    row_dict.get('lifecycle_stage'),
                    row_dict.get('lifecycle_curve'),
                    row_dict.get('gsv_25_total', 0) or 0,
                    row_dict.get('gsv_26_total', 0) or 0,
                )
            )

        print(f"[OK] 迁移了 {len(old_rows)} 条生命周期元数据")
    else:
        print("[SKIP] 产品生命周期表结构未知，跳过迁移")


def add_missing_indexes(conn):
    indexes = [
        ("idx_weekly_data_product_date", "weekly_data", "product_id, week_start"),
        ("idx_monthly_data_product_date", "monthly_data", "product_id, month"),
        ("idx_daily_data_product_date", "daily_data", "product_id, date"),
        ("idx_product_tier", "products", "tier"),
        ("idx_product_manager", "products", "manager"),
        ("idx_product_status", "products", "status"),
        ("idx_product_category", "products", "category"),
        ("idx_alerts_type", "alerts", "alert_type"),
        ("idx_alerts_date", "alerts", "alert_date"),
        ("idx_reviews_product_id", "reviews", "product_id"),
        ("idx_refunds_product_id", "refunds", "product_id"),
        ("idx_operations_product_id", "operation_actions", "product_id"),
        ("idx_product_tags_product_id", "product_tags", "product_id"),
        ("idx_product_notes_product_id", "product_notes", "product_id"),
        ("idx_product_health_product_id", "product_health", "product_id"),
        ("idx_paid_detail_product_id", "paid_detail", "product_id"),
        ("idx_import_history_status", "import_history", "status"),
    ]

    for index_name, table_name, columns in indexes:
        if table_exists(conn, table_name):
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            if not cursor.fetchone():
                conn.execute(f"CREATE INDEX {index_name} ON {table_name}({columns})")
                print(f"[OK] 创建索引: {index_name} ON {table_name}({columns})")
            else:
                print(f"[SKIP] 索引已存在: {index_name}")


def create_default_admin(conn):
    import hashlib

    SALT = "haibeihai_dashboard_2026"

    def hash_password(password):
        return hashlib.sha256((password + SALT).encode()).hexdigest()

    cursor = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if cursor.fetchone()[0] > 0:
        print("[SKIP] 管理员账户已存在")
        return

    hashed_password = hash_password("admin123")
    conn.execute(
        "INSERT INTO users (username, email, hashed_password, role) VALUES (?, ?, ?, ?)",
        ("admin", "admin@haibeihai.com", hashed_password, "admin")
    )

    hashed_password = hash_password("manager123")
    conn.execute(
        "INSERT INTO users (username, email, hashed_password, role) VALUES (?, ?, ?, ?)",
        ("manager", "manager@haibeihai.com", hashed_password, "manager")
    )

    hashed_password = hash_password("viewer123")
    conn.execute(
        "INSERT INTO users (username, email, hashed_password, role) VALUES (?, ?, ?, ?)",
        ("viewer", "viewer@haibeihai.com", hashed_password, "viewer")
    )

    print("[OK] 创建默认用户账户")
    print("  - admin / admin123 (管理员)")
    print("  - manager / manager123 (经理)")
    print("  - viewer / viewer123 (查看者)")


def main():
    print("=" * 60)
    print("数据库迁移脚本 - 2026-05-04")
    print("=" * 60)
    print(f"数据库路径: {DB_PATH}\n")

    conn = get_connection()

    try:
        create_users_table(conn)
        create_product_lifecycle_meta_table(conn)
        migrate_product_lifecycle_table(conn)
        add_missing_indexes(conn)
        create_default_admin(conn)

        conn.commit()
        print("\n" + "=" * 60)
        print("[SUCCESS] 数据库迁移完成!")
        print("=" * 60)
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] 数据库迁移失败: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
