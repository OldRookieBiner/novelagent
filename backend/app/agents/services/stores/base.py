"""Store 基类

提供 session 上下文管理器和 ORM → dict 序列化。
所有 Store 继承此类，共享 session 管理和序列化逻辑。
"""

import logging
import threading
from contextlib import contextmanager
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# 序列化时排除的 ORM 列
_EXCLUDED_COLUMNS = {"created_at", "updated_at"}



# 类级别版本号注册表：data_type -> 版本号
_version_registry: dict[str, int] = {}
_version_lock = threading.Lock()

class _BaseStore:
    """知识库实体存储基类

    子类按领域实体分组，返回 dict 而非 ORM 对象。
    每个 Store 管理 project_id 下的一组内聚实体。
    Store 之间不共享 session。
    """

    def __init__(self, project_id: int):
        self.project_id = project_id


    @classmethod
    def _bump_version(cls, data_type: str) -> None:
        """写入操作后调用，使对应数据类型的缓存失效"""
        with _version_lock:
            _version_registry[data_type] = _version_registry.get(data_type, 0) + 1

    @classmethod
    def get_version(cls, data_type: str) -> int:
        """获取数据类型的当前版本号"""
        with _version_lock:
            return _version_registry.get(data_type, 0)

    # ========== Session 管理 ==========

    @contextmanager
    def session(self, readonly=False):
        """上下文管理器：创建独立 DB session，操作完成后自动关闭

        Args:
            readonly: 只读模式，不执行 commit/rollback

        使用方式：
            with self.session() as db:
                result = db.query(...)
            # 读操作：自动 close
            # 写操作：无异常时 commit + close，异常时 rollback + close
        """
        db = SessionLocal()
        try:
            yield db
            if not readonly:
                db.commit()
        except Exception:
            if not readonly:
                try:
                    db.rollback()
                except Exception:
                    pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass

    # ========== 序列化 ==========

    # 入库时自动排除的列（主键/外键/时间戳由系统维护）
    _NON_WRITABLE_COLUMNS = {"id", "project_id", "created_at", "updated_at"}

    @classmethod
    def _filter_writable(cls, model, data: dict) -> dict:
        """按 model 表列过滤入库 dict，丢弃未知键与系统维护列。

        基于 model.__table__.columns 动态导出可写列集合，
        将来加列无需同步维护白名单；防止 Model(**data) 因 LLM
        多产出字段而抛 TypeError。
        """
        if not data:
            return {}
        columns = getattr(getattr(model, "__table__", None), "columns", None)
        if columns is None:
            return dict(data)
        allowed = {c.name for c in columns} - cls._NON_WRITABLE_COLUMNS
        return {k: v for k, v in data.items() if k in allowed}

    @staticmethod
    def _to_dict(obj) -> Optional[dict]:
        """ORM 对象 → dict，排除 created_at/updated_at

        在 session 关闭前调用。返回的 dict 不包含 ORM 关系属性，
        避免 detached 访问问题。
        """
        if obj is None:
            return None
        if hasattr(obj, "__table__"):
            return {
                c.name: getattr(obj, c.name)
                for c in obj.__table__.columns
                if c.name not in _EXCLUDED_COLUMNS
            }
        return obj

    @staticmethod
    def _to_dict_list(objs) -> list[dict]:
        """ORM 对象列表 → dict 列表"""
        if not objs:
            return []
        return [_BaseStore._to_dict(obj) for obj in objs]
