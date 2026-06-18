"""伏笔存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.foreshadowing import Foreshadowing

logger = logging.getLogger(__name__)


class ForeshadowingStore(_BaseStore):
    """伏笔读写"""

    def get(self, foreshadowing_id: int) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(Foreshadowing).filter(
                Foreshadowing.id == foreshadowing_id,
                Foreshadowing.project_id == self.project_id,
            ).first()
            return self._to_dict(obj)

    def list_foreshadowings(self, status: Optional[str] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(Foreshadowing).filter(
                Foreshadowing.project_id == self.project_id
            )
            if status:
                query = query.filter(Foreshadowing.status == status)
            return self._to_dict_list(query.all())

    def list_pending(self) -> list[dict]:
        """status='pending_reclaim'"""
        return self.list_foreshadowings(status="pending_reclaim")

    def list_overdue(self, current_chapter: int) -> list[dict]:
        """active/pending_reclaim 且 expected_resolve_chapter < current"""
        with self.session(readonly=True) as db:
            objs = db.query(Foreshadowing).filter(
                Foreshadowing.project_id == self.project_id,
                Foreshadowing.status.in_(["active", "pending_reclaim"]),
                Foreshadowing.expected_resolve_chapter.isnot(None),
                Foreshadowing.expected_resolve_chapter < current_chapter,
            ).all()
            return self._to_dict_list(objs)

    def list_due_or_overdue(self, current_chapter: int) -> list[dict]:
        """active/pending_reclaim 且 expected_resolve_chapter <= current

        与 list_overdue（严格小于）不同，此方法覆盖"刚到期"的伏笔，
        用于在 record_chapter_meta 末尾提醒作者本章未标记回收的到期伏笔。
        """
        with self.session(readonly=True) as db:
            objs = db.query(Foreshadowing).filter(
                Foreshadowing.project_id == self.project_id,
                Foreshadowing.status.in_(["active", "pending_reclaim"]),
                Foreshadowing.expected_resolve_chapter.isnot(None),
                Foreshadowing.expected_resolve_chapter <= current_chapter,
            ).all()
            return self._to_dict_list(objs)

    def create(self, data: dict) -> dict:
        with self.session() as db:
            obj = Foreshadowing(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update(self, foreshadowing_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(Foreshadowing).filter(
                Foreshadowing.id == foreshadowing_id,
                Foreshadowing.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"Foreshadowing {foreshadowing_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- 内部方法 ---

    def _read_all_with_session(self, db) -> list[dict]:
        objs = db.query(Foreshadowing).filter(
            Foreshadowing.project_id == self.project_id
        ).all()
        return self._to_dict_list(objs)

    def _create_with_session(self, db, data: dict) -> dict:
        obj = Foreshadowing(project_id=self.project_id, **data)
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return self._to_dict(obj)
