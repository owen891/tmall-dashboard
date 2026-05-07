#!/usr/bin/env python3
"""
Migrate legacy database schema to new schema
"""
import sys
import os
import sqlite3
import shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_db():
    old_db = 'data/db/dashboard.db'
    new_db = 'data/db/dashboard_new.db'
    
    # Backup old db
    shutil.copy(old_db, old_db + '.backup')
    
    # Connect to old db
    conn_old = sqlite3.connect(old_db)
    cursor_old = conn_old.cursor()
    
    # Connect to new db (will be created)
    from app.core.database import engine, Base, SessionLocal
    from app.models import Product, DailyData, WeeklyData, MonthlyData
    
    Base.metadata.create_all(bind=engine)
    
    # Now check if products table exists in new schema and has all fields
    import sqlite3
    conn_new = sqlite3.connect(new_db)
    conn_new.execute("ATTACH DATABASE 'data/db/dashboard.db' AS old")
    
    # Copy data from old to new
    print("Migrating products...")
    try:
        conn_new.execute("""
            INSERT INTO products (
                product_id, title, category, tier, style, scene,
                list_date, status, remark, image_url, manager,
                starred, created_at, updated_at
            )
            SELECT 
                product_id, title, category, tier, style, scene,
                list_date, status, remark, image_url, manager,
                starred, created_at, updated_at
            FROM old.products
        """)
        conn_new.commit()
        print(f"  Copied {conn_new.execute('SELECT COUNT(*) FROM products').fetchone()[0]} products")
    except Exception as e:
        print(f"  Note: {e}")
    
    # Copy daily_data
    print("\nMigrating daily_data...")
    try:
        # First check which fields exist in old table
        cursor_old.execute("PRAGMA table_info(daily_data)")
        old_cols = [col[1] for col in cursor_old.fetchall()]
        
        # Select common columns
        common_cols = [c for c in old_cols if c not in ['id']]
        cols_str = ', '.join(common_cols)
        conn_new.execute(f"""
            INSERT INTO daily_data ({cols_str})
            SELECT {cols_str} FROM old.daily_data
        """)
        conn_new.commit()
        count = conn_new.execute("SELECT COUNT(*) FROM daily_data").fetchone()[0]
        print(f"  Copied {count} daily records")
    except Exception as e:
        print(f"  Note: {e}")
    
    # Copy weekly_data
    print("\nMigrating weekly_data...")
    try:
        cursor_old.execute("PRAGMA table_info(weekly_data)")
        old_cols = [col[1] for col in cursor_old.fetchall()]
        common_cols = [c for c in old_cols if c not in ['id']]
        cols_str = ', '.join(common_cols)
        conn_new.execute(f"""
            INSERT INTO weekly_data ({cols_str})
            SELECT {cols_str} FROM old.weekly_data
        """)
        conn_new.commit()
        count = conn_new.execute("SELECT COUNT(*) FROM weekly_data").fetchone()[0]
        print(f"  Copied {count} weekly records")
    except Exception as e:
        print(f"  Note: {e}")
    
    # Copy monthly_data
    print("\nMigrating monthly_data...")
    try:
        cursor_old.execute("PRAGMA table_info(monthly_data)")
        old_cols = [col[1] for col in cursor_old.fetchall()]
        common_cols = [c for c in old_cols if c not in ['id']]
        cols_str = ', '.join(common_cols)
        conn_new.execute(f"""
            INSERT INTO monthly_data ({cols_str})
            SELECT {cols_str} FROM old.monthly_data
        """)
        conn_new.commit()
        count = conn_new.execute("SELECT COUNT(*) FROM monthly_data").fetchone()[0]
        print(f"  Copied {count} monthly records")
    except Exception as e:
        print(f"  Note: {e}")
    
    conn_old.close()
    conn_new.close()
    
    # Replace old with new
    os.replace(new_db, old_db)
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate_db()
