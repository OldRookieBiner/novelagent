"""Database connection and session management

设计原则：
- pool_pre_ping=True: 自动检测断开的连接，防止"server closed the connection unexpectedly"
- pool_size=10, max_overflow=20: 支持并发的 SSE 流式请求 + 节点 DB 操作
- get_db 使用安全的 rollback + close，避免 SSE 流中 session 并发冲突

修复：
- get_db 中 rollback + close 顺序：先 rollback 再 close，且两步各自 try/except
  避免 rollback 抛出时导致 close 不被执行（session 泄漏）
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create engine with connection pool health checks
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,  # 30分钟回收连接，避免 PostgreSQL idle session 超时
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session

    SSE 流式请求期间，节点内部的 SessionLocal() 实例可能在线程池中并发操作，
    导致 finally 中的 db.close() 抛出 IllegalStateChangeError。

    使用独立的 try/except 确保 rollback 和 close 都能执行，
    即使其中一步抛出异常也不会影响另一步。
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
