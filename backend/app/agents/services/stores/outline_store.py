"""大纲和章节大纲存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.outline import Outline, ChapterOutline

logger = logging.getLogger(__name__)


class OutlineStore(_BaseStore):
    """大纲 + 章节大纲读写

    Outline 是单实例（每个项目一个）。
    ChapterOutline 归此类管理（大纲视角的章节蓝图）。
    """

    # --- Outline（单实例） ---

    def get(self) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(Outline).filter(
                Outline.project_id == self.project_id
            ).first()
            return self._to_dict(obj)

    def update(self, data: dict) -> dict:
        """更新大纲（单实例，不需要传 id）"""
        with self.session() as db:
            obj = db.query(Outline).filter(
                Outline.project_id == self.project_id
            ).first()
            if not obj:
                raise ValueError(f"Outline not found for project {self.project_id}")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def upsert(self, data: dict) -> dict:
        """创建或更新大纲（单实例 upsert，用于初始化流程）"""
        with self.session() as db:
            obj = db.query(Outline).filter(
                Outline.project_id == self.project_id
            ).first()
            if obj:
                for key, value in data.items():
                    setattr(obj, key, value)
            else:
                obj = Outline(project_id=self.project_id, **data)
                db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- ChapterOutline ---

    def get_chapter_outline(self, chapter_number: int) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            return self._to_dict(obj)

    def list_chapter_outlines(self) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id
            ).order_by(ChapterOutline.chapter_number).all()
            return self._to_dict_list(objs)

    def create_chapter_outline(self, data: dict) -> dict:
        with self.session() as db:
            obj = ChapterOutline(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_chapter_outline(self, chapter_number: int, data: dict) -> dict:
        """更新章节大纲（按 chapter_number 定位）"""
        with self.session() as db:
            obj = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not obj:
                raise ValueError(f"ChapterOutline for chapter {chapter_number} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- 内部方法 ---

    def _read_with_session(self, db) -> Optional[dict]:
        obj = db.query(Outline).filter(
            Outline.project_id == self.project_id
        ).first()
        return self._to_dict(obj)

    def _read_chapter_outlines_with_session(self, db) -> list[dict]:
        objs = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == self.project_id
        ).order_by(ChapterOutline.chapter_number).all()
        return self._to_dict_list(objs)
