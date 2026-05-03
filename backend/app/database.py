"""Database connection and session management"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create engine
engine = create_engine(
    settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session

    SSE 流式请求期间，节点内部的 SessionLocal() 实例可能在线程池中并发操作，
    导致 finally 中的 db.close() 抛出 IllegalStateChangeError。
    使用 try/except 安全关闭，回滚未提交的更改后关闭会话。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
