from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String, nullable=False)
    task_type = Column(String, nullable=True)
    cron_expr = Column(String, nullable=True)
    file_pattern = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    last_run = Column(String, nullable=True)
    next_run = Column(String, nullable=True)
    status = Column(String, nullable=True)

    created_at = Column(DateTime, default=func.now())


class ImportHistory(Base):
    __tablename__ = "import_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    import_type = Column(String, default="weekly")
    status = Column(String, nullable=False)
    product_count = Column(Integer, default=0)
    data_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())


class FileStorage(Base):
    __tablename__ = "file_storage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    storage_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String, nullable=True)
    file_extension = Column(String, nullable=True)
    usage_type = Column(String, nullable=True)
    usage_id = Column(Integer, nullable=True)
    created_by = Column(String, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String, unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=True)
    setting_type = Column(String, default="string")
    description = Column(String, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
