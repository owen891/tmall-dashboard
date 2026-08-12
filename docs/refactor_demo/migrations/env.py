"""
Alembic 环境配置 — 自动检测 ORM 模型变更。

替代 db.py 中手写的 ALTER TABLE 迁移逻辑。
"""
from alembic import context
from flask import current_app
import logging

# 导入所有模型，确保 Alembic 能检测到
import models.product
import models.data
import models.paid
import models.health
import models.review
import models.market
import models.action
import models.alert
import models.system
from models import db

config = context.config
logger = logging.getLogger('alembic.env')


def get_engine():
    """获取 Flask-SQLAlchemy 引擎"""
    try:
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    """获取数据库连接字符串"""
    try:
        return get_engine().url.render_as_string(hide_password=False)
    except AttributeError:
        return str(get_engine().url)


def run_migrations_offline():
    """离线模式：生成 SQL 脚本但不执行"""
    url = config.get_main_option("sqlalchemy.url") or get_engine_url()
    context.configure(
        url=url,
        target_metadata=db.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """在线模式：直接执行迁移"""
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    conf_args = {
        'target_metadata': db.metadata,
        'process_revision_directives': process_revision_directives,
        **current_app.extensions['migrate'].configure_args,
    }

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(connection=connection, **conf_args)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
