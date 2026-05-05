import sys
sys.path.insert(0, "f:/ai/.accelerate/tmall-dashboard/backend")

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models import User

print(f"数据库 URL: {settings.DATABASE_URL}")
print(f"Engine URL: {engine.url}")

# 测试原始连接
raw_conn = engine.raw_connection()
cursor = raw_conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"\nSQLAlchemy 看到的表: {[t[0] for t in tables]}")

cursor.execute("SELECT COUNT(*) FROM users")
count = cursor.fetchone()[0]
print(f"users 表记录数 (通过原始连接): {count}")
raw_conn.close()

# 测试 SQLAlchemy session
db = SessionLocal()
users = db.query(User).all()
print(f"users 表记录数 (通过 SQLAlchemy): {len(users)}")

for user in users:
    print(f"  - {user.username} / {user.role}")

db.close()
