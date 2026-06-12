"""世界观存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.world_setting import WorldSetting

logger = logging.getLogger(__name__)


class WorldSettingStore(_BaseStore):
    """世界观读写（单实例：每个项目一个 WorldSetting）"""

    def get(self) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(WorldSetting).filter(
                WorldSetting.project_id == self.project_id
            ).first()
            return self._to_dict(obj)

    def create(self, data: dict) -> dict:
        with self.session() as db:
            obj = WorldSetting(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update(self, data: dict) -> dict:
        """更新世界观（单实例，不需要传 id）"""
        with self.session() as db:
            obj = db.query(WorldSetting).filter(
                WorldSetting.project_id == self.project_id
            ).first()
            if not obj:
                raise ValueError(f"WorldSetting not found for project {self.project_id}")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_by_id(self, setting_id: int, data: dict) -> dict:
        """按 id 更新（供 API 端点和 impact decision 使用）"""
        with self.session() as db:
            obj = db.query(WorldSetting).filter(
                WorldSetting.id == setting_id,
                WorldSetting.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"WorldSetting {setting_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- 内部方法 ---

    def _read_with_session(self, db) -> Optional[dict]:
        """共享 session 读取"""
        obj = db.query(WorldSetting).filter(
            WorldSetting.project_id == self.project_id
        ).first()
        return self._to_dict(obj)
