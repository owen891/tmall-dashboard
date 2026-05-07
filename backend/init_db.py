#!/usr/bin/env python3
"""
Initialize or migrate database schema
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base, SessionLocal
from app.core.config import get_settings
from app.models import *
import shutil

def init_db():
    settings = get_settings()
    
    # Backup existing database
    db_path = settings.DATABASE_URL.replace('sqlite:///', '')
    backup_path = f"{db_path}.backup"
    if os.path.exists(db_path):
        shutil.copy(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ All database tables created/updated")
    
    # Verify tables
    session = SessionLocal()
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"✅ Tables in database: {sorted(tables)}")
    session.close()

if __name__ == "__main__":
    init_db()
