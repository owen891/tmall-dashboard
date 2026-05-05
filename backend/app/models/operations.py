from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class OperationAction(Base):
    __tablename__ = "operation_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    action_date = Column(String, nullable=False)
    action_type = Column(String, nullable=True)
    action_detail = Column(Text, nullable=True)
    before_payment = Column(Float, default=0)
    before_visitors = Column(Integer, default=0)
    before_conversion = Column(Float, default=0)
    before_roi = Column(Float, default=0)
    after_payment = Column(Float, default=0)
    after_visitors = Column(Integer, default=0)
    after_conversion = Column(Float, default=0)
    after_roi = Column(Float, default=0)
    payment_change = Column(Float, default=0)
    conversion_change = Column(Float, default=0)
    roi_change = Column(Float, default=0)
    effectiveness_score = Column(Float, default=0)
    imported_at = Column(DateTime, default=func.now())


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(Text, nullable=False)
    detail = Column(Text, nullable=True)
    operator = Column(String, nullable=True)

    created_at = Column(DateTime, default=func.now())
