from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_date = Column(String, nullable=True)
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(String, default="warning")
    title = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    metric_name = Column(String, nullable=True)
    current_value = Column(Float, default=0)
    target_value = Column(Float, default=0)
    period = Column(String, nullable=True)
    dismissed = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String, nullable=False)
    operator = Column(String, nullable=False)
    threshold = Column(Float, nullable=False)
    level = Column(String, default="warning")
    enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=True)

    title = Column(String, nullable=False)
    detail = Column(Text, nullable=True)

    current_value = Column(Float, default=0)
    threshold_value = Column(Float, default=0)

    status = Column(String, default="pending")
    handler = Column(String, default="")
    level = Column(String, default="warning")

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
