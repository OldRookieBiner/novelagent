"""设定变更存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore

logger = logging.getLogger(__name__)


class ChangeStore(_BaseStore):
    """设定变更读写（SettingChange）"""

    def get(self, change_id: int) -> Optional[dict]:
        from app.models.setting_change import SettingChange
        with self.session(readonly=True) as db:
            obj = db.query(SettingChange).filter(
                SettingChange.id == change_id,
                SettingChange.project_id == self.project_id,
            ).first()
            return self._to_dict(obj)

    def list_changes(self, status: Optional[str] = None) -> list[dict]:
        from app.models.setting_change import SettingChange
        with self.session(readonly=True) as db:
            query = db.query(SettingChange).filter(
                SettingChange.project_id == self.project_id
            )
            if status:
                query = query.filter(SettingChange.status == status)
            return self._to_dict_list(query.all())

    def create(self, data: dict) -> dict:
        from app.models.setting_change import SettingChange
        with self.session() as db:
            obj = SettingChange(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update(self, change_id: int, data: dict) -> dict:
        from app.models.setting_change import SettingChange
        with self.session() as db:
            obj = db.query(SettingChange).filter(
                SettingChange.id == change_id,
                SettingChange.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"SettingChange {change_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)
