"""时间线和场景条目存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.timeline import TimelineEntry
from app.models.scene_entry import SceneEntry

logger = logging.getLogger(__name__)


class TimelineStore(_BaseStore):
    """时间线 + 场景条目读写"""

    # --- TimelineEntry ---

    def list_timeline(self, chapter_range: tuple[int, int] | None = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(TimelineEntry).filter(
                TimelineEntry.project_id == self.project_id
            ).order_by(TimelineEntry.chapter_number)
            if chapter_range:
                query = query.filter(
                    TimelineEntry.chapter_number >= chapter_range[0],
                    TimelineEntry.chapter_number <= chapter_range[1],
                )
            return self._to_dict_list(query.all())

    def get_by_chapter_number(self, chapter_number: int) -> dict | None:
        """按章节号查询时间线条目，返回最新的一条或 None"""
        with self.session(readonly=True) as db:
            entry = db.query(TimelineEntry).filter(
                TimelineEntry.project_id == self.project_id,
                TimelineEntry.chapter_number == chapter_number,
            ).order_by(TimelineEntry.id.desc()).first()
            return self._to_dict(entry) if entry else None

    def create_timeline_entry(self, data: dict) -> dict:
        with self.session() as db:
            obj = TimelineEntry(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_timeline_entry(self, entry_id: int, data: dict) -> dict:
        """更新时间线条目的指定字段"""
        with self.session() as db:
            entry = db.query(TimelineEntry).filter(
                TimelineEntry.project_id == self.project_id,
                TimelineEntry.id == entry_id,
            ).first()
            if not entry:
                raise ValueError(f"TimelineEntry id={entry_id} 不存在")
            for key, value in data.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            db.flush()
            db.refresh(entry)
            return self._to_dict(entry)

    # --- SceneEntry ---

    def list_scene_entries(self, chapter_number: Optional[int] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(SceneEntry).filter(
                SceneEntry.project_id == self.project_id
            )
            if chapter_number is not None:
                query = query.filter(SceneEntry.chapter_number == chapter_number)
            return self._to_dict_list(query.all())

    def create_scene_entry(self, data: dict) -> dict:
        with self.session() as db:
            obj = SceneEntry(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- 内部方法 ---

    def _read_all_with_session(self, db) -> dict:
        timeline = db.query(TimelineEntry).filter(
            TimelineEntry.project_id == self.project_id
        ).order_by(TimelineEntry.chapter_number).all()
        scenes = db.query(SceneEntry).filter(
            SceneEntry.project_id == self.project_id
        ).all()
        return {
            "timeline": self._to_dict_list(timeline),
            "scene_entries": self._to_dict_list(scenes),
        }

    def _create_with_session(self, db, data: dict) -> dict:
        obj = TimelineEntry(project_id=self.project_id, **data)
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return self._to_dict(obj)
