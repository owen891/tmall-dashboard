import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'dashboard.db')

def run_migration():
    print("="*60)
    print("运营日历表迁移")
    print("="*60)
    print(f"数据库: {DB_PATH}")
    
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operation_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT NOT NULL,
            event_type TEXT(50) NOT NULL,
            title TEXT(200) NOT NULL,
            description TEXT,
            product_id TEXT(50),
            product_name TEXT(200),
            operator TEXT(50),
            tags TEXT(200),
            metrics_before TEXT,
            metrics_after TEXT,
            payment_before REAL DEFAULT 0,
            payment_after REAL DEFAULT 0,
            visitors_before INTEGER DEFAULT 0,
            visitors_after INTEGER DEFAULT 0,
            conversion_before REAL DEFAULT 0,
            conversion_after REAL DEFAULT 0,
            ad_spend_before REAL DEFAULT 0,
            ad_spend_after REAL DEFAULT 0,
            budget REAL DEFAULT 0,
            actual_cost REAL DEFAULT 0,
            roi REAL DEFAULT 0,
            effectiveness_score INTEGER DEFAULT 0,
            status TEXT(20) DEFAULT 'planned',
            priority TEXT(20) DEFAULT 'medium',
            repeat_type TEXT(20),
            related_alert TEXT(500),
            follow_up TEXT(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_event_date ON operation_calendar(event_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_event_type ON operation_calendar(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_product_id ON operation_calendar(product_id)")
    
    db.commit()
    
    count = cursor.execute("SELECT COUNT(*) FROM operation_calendar").fetchone()[0]
    print(f"  operation_calendar: {count} rows")
    
    db.close()
    print("\n[SUCCESS] 运营日历表创建成功!")

if __name__ == '__main__':
    run_migration()
