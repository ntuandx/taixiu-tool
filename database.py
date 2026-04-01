from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import os

os.makedirs('instance', exist_ok=True)

DATABASE_URL = 'sqlite:///instance/taixiu.db'

# Tăng pool size và timeout
engine = create_engine(
    DATABASE_URL, 
    connect_args={'check_same_thread': False, 'timeout': 30},
    pool_size=5,           # Số kết nối tối đa
    max_overflow=10,       # Số kết nối dự phòng
    pool_timeout=30,       # Timeout chờ kết nối
    pool_recycle=3600      # Tái chế kết nối sau 1 giờ
)

# Dùng scoped_session để quản lý session tốt hơn
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()

def get_db():
    """Lấy session database, tự động đóng sau khi dùng"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()