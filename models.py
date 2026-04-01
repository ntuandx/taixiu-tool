from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from database import Base

class Result(Base):
    __tablename__ = 'results'
    
    id = Column(Integer, primary_key=True, index=True)
    session = Column(String(50), unique=True, index=True, nullable=False)
    result = Column(String(10), nullable=False)
    time = Column(DateTime, default=func.now())
    source_time = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_result_time', 'result', 'time'),
    )