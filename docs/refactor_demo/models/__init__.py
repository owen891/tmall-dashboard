"""
SQLAlchemy ORM 模型定义。

这是重构后的数据模型层，替代 db.py 中的手写 CREATE TABLE。
所有表结构在此集中定义，Alembic 会自动检测变更并生成迁移。
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
