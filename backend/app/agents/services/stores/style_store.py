"""风格约束和风格快照存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.style_constraints import StyleConstraints
from app.models.style_snapshot import StyleSnapshot

logger = logging.getLogger(__name__)


class StyleStore(_BaseStore):
    """风格约束 + 风格快照读写"""

    # --- StyleConstraints（单实例） ---

    def get_constraints(self) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(StyleConstraints).filter(
                StyleConstraints.project_id == self.project_id
            ).first()
            return self._to_dict(obj)

    def create_constraints(self, data: dict) -> dict:
        data = self._filter_writable(StyleConstraints, data)
        with self.session() as db:
            obj = StyleConstraints(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            result = self._to_dict(obj)
        self._bump_version("style_constraints")
        return result

    def update_constraints(self, data: dict) -> dict:
        """更新风格约束（单实例，不需要传 id）"""
        modified = False
        with self.session() as db:
            obj = db.query(StyleConstraints).filter(
                StyleConstraints.project_id == self.project_id
            ).first()
            if not obj:
                raise ValueError(f"StyleConstraints not found for project {self.project_id}")
            for key, value in data.items():
                setattr(obj, key, value)
            modified = True
            db.flush()
            db.refresh(obj)
            result = self._to_dict(obj)
        if modified:
            self._bump_version("style_constraints")
        return result

    def update_constraints_by_id(self, constraints_id: int, data: dict) -> dict:
        """按 id 更新（供 API 端点和 impact decision 使用）"""
        modified = False
        with self.session() as db:
            obj = db.query(StyleConstraints).filter(
                StyleConstraints.id == constraints_id,
                StyleConstraints.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"StyleConstraints {constraints_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            modified = True
            db.flush()
            db.refresh(obj)
            result = self._to_dict(obj)
        if modified:
            self._bump_version("style_constraints")
        return result

    # --- StyleSnapshot ---

    def list_snapshots(self, last_n: Optional[int] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(StyleSnapshot).filter(
                StyleSnapshot.project_id == self.project_id
            ).order_by(StyleSnapshot.id.desc())
            if last_n:
                query = query.limit(last_n)
            return self._to_dict_list(query.all())

    def create_snapshot(self, data: dict) -> dict:
        with self.session() as db:
            obj = StyleSnapshot(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- 内部方法 ---

    def _read_constraints_with_session(self, db) -> Optional[dict]:
        obj = db.query(StyleConstraints).filter(
            StyleConstraints.project_id == self.project_id
        ).first()
        return self._to_dict(obj)

    def _create_snapshot_with_session(self, db, data: dict) -> dict:
        obj = StyleSnapshot(project_id=self.project_id, **data)
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return self._to_dict(obj)

    def _read_snapshots_with_session(self, db, last_n: int = 10) -> list[dict]:
        """单次 session 内批量读取最近 N 条风格快照"""
        from app.models.style_snapshot import StyleSnapshot
        objs = db.query(StyleSnapshot).filter(
            StyleSnapshot.project_id == self.project_id
        ).order_by(StyleSnapshot.id.desc()).limit(last_n).all()
        return self._to_dict_list(objs)
