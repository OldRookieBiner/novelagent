"""知识库读写服务

所有 Agent 节点共享的知识库操作层。

设计原则：
- 每个 API 内部创建独立 DB session，操作完成后立即关闭
- 写操作：try/commit → except/rollback → finally/close
- 读操作：try/finally/close（无事务需要管理）
- 返回的 ORM 对象在 session 关闭后为 detached 状态，
  调用方不应再访问 lazy-loaded 关系属性
- LangGraph 节点无需管理 session 生命周期
- SSE 流式请求中不会出现 session 并发冲突
- 节点失败时自动回滚，不污染其他节点的 session
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.world_setting import WorldSetting
from app.models.style_constraints import StyleConstraints
from app.models.plot_structure import PlotBlock, PlotQuestion, Subplot
from app.models.foreshadowing import Foreshadowing
from app.models.timeline import TimelineEntry
from app.models.style_snapshot import StyleSnapshot
from app.models.scene_entry import SceneEntry
from app.models.character import Character, Relation
from app.models.outline import Outline

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """知识库读写服务

    每个 API 内部创建独立 DB session，确保：
    1. LangGraph 节点无需管理 session 生命周期
    2. SSE 流式请求中不会出现 session 并发冲突
    3. 节点失败时自动回滚，不污染其他节点的 session
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    # ========== Session 管理 ==========

    def _get_db(self) -> Session:
        return SessionLocal()

    @staticmethod
    def _close_db_read(db: Session):
        """只读操作的 session 关闭：直接 close，无需 rollback"""
        try:
            db.close()
        except Exception:
            pass

    @staticmethod
    def _close_db_write(db: Session, committed: bool):
        """写操作的 session 关闭

        Args:
            committed: 是否已成功 commit。
                       True → 直接 close（数据已持久化）
                       False → 先 rollback 再 close（回滚未提交的变更）
        """
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass

    # ========== 大纲 ==========

    def get_outline(self) -> Optional[Outline]:
        db = self._get_db()
        try:
            return db.query(Outline).filter(
                Outline.project_id == self.project_id
            ).first()
        finally:
            self._close_db_read(db)

    # ========== 世界观 ==========

    def get_world_setting(self) -> Optional[WorldSetting]:
        db = self._get_db()
        try:
            return db.query(WorldSetting).filter(
                WorldSetting.project_id == self.project_id
            ).first()
        finally:
            self._close_db_read(db)

    def create_world_setting(self, data: dict) -> WorldSetting:
        db = self._get_db()
        committed = False
        try:
            setting = WorldSetting(project_id=self.project_id, **data)
            db.add(setting)
            db.commit()
            committed = True
            db.refresh(setting)
            return setting
        finally:
            self._close_db_write(db, committed)

    def update_world_setting(self, setting_id: int, data: dict) -> WorldSetting:
        db = self._get_db()
        committed = False
        try:
            setting = db.query(WorldSetting).filter(
                WorldSetting.id == setting_id,
                WorldSetting.project_id == self.project_id,
            ).first()
            if not setting:
                raise ValueError(f"WorldSetting {setting_id} not found")
            for key, value in data.items():
                setattr(setting, key, value)
            db.commit()
            committed = True
            db.refresh(setting)
            return setting
        finally:
            self._close_db_write(db, committed)

    # ========== 角色 ==========

    def get_characters(self) -> list[Character]:
        db = self._get_db()
        try:
            return db.query(Character).filter(
                Character.project_id == self.project_id
            ).all()
        finally:
            self._close_db_read(db)

    def create_character(self, data: dict) -> Character:
        db = self._get_db()
        committed = False
        try:
            char = Character(project_id=self.project_id, **data)
            db.add(char)
            db.commit()
            committed = True
            db.refresh(char)
            return char
        finally:
            self._close_db_write(db, committed)

    # ========== 关系 ==========

    def get_relations(self) -> list[Relation]:
        db = self._get_db()
        try:
            return db.query(Relation).filter(
                Relation.project_id == self.project_id
            ).all()
        finally:
            self._close_db_read(db)

    # ========== 风格约束 ==========

    def get_style_constraints(self) -> Optional[StyleConstraints]:
        db = self._get_db()
        try:
            return db.query(StyleConstraints).filter(
                StyleConstraints.project_id == self.project_id
            ).first()
        finally:
            self._close_db_read(db)

    def create_style_constraints(self, data: dict) -> StyleConstraints:
        db = self._get_db()
        committed = False
        try:
            constraints = StyleConstraints(project_id=self.project_id, **data)
            db.add(constraints)
            db.commit()
            committed = True
            db.refresh(constraints)
            return constraints
        finally:
            self._close_db_write(db, committed)

    def update_style_constraints(self, constraints_id: int, data: dict) -> StyleConstraints:
        db = self._get_db()
        committed = False
        try:
            constraints = db.query(StyleConstraints).filter(
                StyleConstraints.id == constraints_id,
                StyleConstraints.project_id == self.project_id,
            ).first()
            if not constraints:
                raise ValueError(f"StyleConstraints {constraints_id} not found")
            for key, value in data.items():
                setattr(constraints, key, value)
            db.commit()
            committed = True
            db.refresh(constraints)
            return constraints
        finally:
            self._close_db_write(db, committed)

    # ========== 情节块 ==========

    def get_plot_blocks(self) -> list[PlotBlock]:
        db = self._get_db()
        try:
            return db.query(PlotBlock).filter(
                PlotBlock.project_id == self.project_id
            ).order_by(PlotBlock.chapter_start).all()
        finally:
            self._close_db_read(db)

    def create_plot_block(self, data: dict) -> PlotBlock:
        db = self._get_db()
        committed = False
        try:
            block = PlotBlock(project_id=self.project_id, **data)
            db.add(block)
            db.commit()
            committed = True
            db.refresh(block)
            return block
        finally:
            self._close_db_write(db, committed)

    def update_plot_block(self, block_id: int, data: dict) -> PlotBlock:
        db = self._get_db()
        committed = False
        try:
            block = db.query(PlotBlock).filter(
                PlotBlock.id == block_id,
                PlotBlock.project_id == self.project_id,
            ).first()
            if not block:
                raise ValueError(f"PlotBlock {block_id} not found")
            for key, value in data.items():
                setattr(block, key, value)
            db.commit()
            committed = True
            db.refresh(block)
            return block
        finally:
            self._close_db_write(db, committed)

    def get_current_plot_block(self, chapter_number: int) -> Optional[PlotBlock]:
        """根据章节号查找当前所属的情节块"""
        db = self._get_db()
        try:
            return db.query(PlotBlock).filter(
                PlotBlock.project_id == self.project_id,
                PlotBlock.chapter_start <= chapter_number,
            ).order_by(PlotBlock.chapter_start.desc()).first()
        finally:
            self._close_db_read(db)

    # ========== 问题链 ==========

    def get_plot_questions(self, status: Optional[str] = None) -> list[PlotQuestion]:
        db = self._get_db()
        try:
            query = db.query(PlotQuestion).filter(
                PlotQuestion.project_id == self.project_id
            )
            if status:
                query = query.filter(PlotQuestion.status == status)
            return query.all()
        finally:
            self._close_db_read(db)

    def get_questions_for_chapter(self, chapter_number: int) -> list[PlotQuestion]:
        """获取指定章节需要回答的问题"""
        db = self._get_db()
        try:
            return db.query(PlotQuestion).filter(
                PlotQuestion.project_id == self.project_id,
                PlotQuestion.status == "pending",
                PlotQuestion.raised_in_chapter <= chapter_number,
            ).all()
        finally:
            self._close_db_read(db)

    def create_plot_question(self, data: dict) -> PlotQuestion:
        db = self._get_db()
        committed = False
        try:
            q = PlotQuestion(project_id=self.project_id, **data)
            db.add(q)
            db.commit()
            committed = True
            db.refresh(q)
            return q
        finally:
            self._close_db_write(db, committed)

    def update_plot_question(self, question_id: int, data: dict) -> PlotQuestion:
        db = self._get_db()
        committed = False
        try:
            q = db.query(PlotQuestion).filter(
                PlotQuestion.id == question_id,
                PlotQuestion.project_id == self.project_id,
            ).first()
            if not q:
                raise ValueError(f"PlotQuestion {question_id} not found")
            for key, value in data.items():
                setattr(q, key, value)
            db.commit()
            committed = True
            db.refresh(q)
            return q
        finally:
            self._close_db_write(db, committed)

    # ========== 支线 ==========

    def get_subplots(self) -> list[Subplot]:
        db = self._get_db()
        try:
            return db.query(Subplot).filter(
                Subplot.project_id == self.project_id
            ).all()
        finally:
            self._close_db_read(db)

    def create_subplot(self, data: dict) -> Subplot:
        db = self._get_db()
        committed = False
        try:
            s = Subplot(project_id=self.project_id, **data)
            db.add(s)
            db.commit()
            committed = True
            db.refresh(s)
            return s
        finally:
            self._close_db_write(db, committed)

    def update_subplot(self, subplot_id: int, data: dict) -> Subplot:
        db = self._get_db()
        committed = False
        try:
            s = db.query(Subplot).filter(
                Subplot.id == subplot_id,
                Subplot.project_id == self.project_id,
            ).first()
            if not s:
                raise ValueError(f"Subplot {subplot_id} not found")
            for key, value in data.items():
                setattr(s, key, value)
            db.commit()
            committed = True
            db.refresh(s)
            return s
        finally:
            self._close_db_write(db, committed)

    # ========== 伏笔 ==========

    def get_foreshadowings(self, status: Optional[str] = None) -> list[Foreshadowing]:
        db = self._get_db()
        try:
            query = db.query(Foreshadowing).filter(
                Foreshadowing.project_id == self.project_id
            )
            if status:
                query = query.filter(Foreshadowing.status == status)
            return query.all()
        finally:
            self._close_db_read(db)

    def get_pending_foreshadowings(self) -> list[Foreshadowing]:
        """获取所有待回收伏笔"""
        return self.get_foreshadowings(status="pending_reclaim")

    def get_overdue_foreshadowings(self, current_chapter: int) -> list[Foreshadowing]:
        """获取超期未回收的伏笔"""
        db = self._get_db()
        try:
            return db.query(Foreshadowing).filter(
                Foreshadowing.project_id == self.project_id,
                Foreshadowing.status.in_(["active", "pending_reclaim"]),
                Foreshadowing.expected_resolve_chapter.isnot(None),
                Foreshadowing.expected_resolve_chapter < current_chapter,
            ).all()
        finally:
            self._close_db_read(db)

    def create_foreshadowing(self, data: dict) -> Foreshadowing:
        db = self._get_db()
        committed = False
        try:
            f = Foreshadowing(project_id=self.project_id, **data)
            db.add(f)
            db.commit()
            committed = True
            db.refresh(f)
            return f
        finally:
            self._close_db_write(db, committed)

    def update_foreshadowing(self, foreshadowing_id: int, data: dict) -> Foreshadowing:
        db = self._get_db()
        committed = False
        try:
            f = db.query(Foreshadowing).filter(
                Foreshadowing.id == foreshadowing_id,
                Foreshadowing.project_id == self.project_id,
            ).first()
            if not f:
                raise ValueError(f"Foreshadowing {foreshadowing_id} not found")
            for key, value in data.items():
                setattr(f, key, value)
            db.commit()
            committed = True
            db.refresh(f)
            return f
        finally:
            self._close_db_write(db, committed)

    # ========== 时间线 ==========

    def get_timeline(
        self, chapter_range: Optional[tuple[int, int]] = None
    ) -> list[TimelineEntry]:
        db = self._get_db()
        try:
            query = db.query(TimelineEntry).filter(
                TimelineEntry.project_id == self.project_id
            ).order_by(TimelineEntry.chapter_number)
            if chapter_range:
                query = query.filter(
                    TimelineEntry.chapter_number >= chapter_range[0],
                    TimelineEntry.chapter_number <= chapter_range[1],
                )
            return query.all()
        finally:
            self._close_db_read(db)

    def create_timeline_entry(self, data: dict) -> TimelineEntry:
        db = self._get_db()
        committed = False
        try:
            entry = TimelineEntry(project_id=self.project_id, **data)
            db.add(entry)
            db.commit()
            committed = True
            db.refresh(entry)
            return entry
        finally:
            self._close_db_write(db, committed)

    # ========== 风格统计 ==========

    def get_style_snapshots(self, last_n: Optional[int] = None) -> list[StyleSnapshot]:
        db = self._get_db()
        try:
            query = db.query(StyleSnapshot).filter(
                StyleSnapshot.project_id == self.project_id
            ).order_by(StyleSnapshot.chapter_number.desc())
            if last_n:
                query = query.limit(last_n)
            return query.all()
        finally:
            self._close_db_read(db)

    def create_style_snapshot(self, data: dict) -> StyleSnapshot:
        db = self._get_db()
        committed = False
        try:
            snapshot = StyleSnapshot(project_id=self.project_id, **data)
            db.add(snapshot)
            db.commit()
            committed = True
            db.refresh(snapshot)
            return snapshot
        finally:
            self._close_db_write(db, committed)

    # ========== 场景清单 ==========

    def get_scene_entries(self, chapter_number: Optional[int] = None) -> list[SceneEntry]:
        db = self._get_db()
        try:
            query = db.query(SceneEntry).filter(
                SceneEntry.project_id == self.project_id
            )
            if chapter_number is not None:
                query = query.filter(SceneEntry.chapter_number == chapter_number)
            return query.order_by(SceneEntry.id).all()
        finally:
            self._close_db_read(db)

    def create_scene_entry(self, data: dict) -> SceneEntry:
        db = self._get_db()
        committed = False
        try:
            entry = SceneEntry(project_id=self.project_id, **data)
            db.add(entry)
            db.commit()
            committed = True
            db.refresh(entry)
            return entry
        finally:
            self._close_db_write(db, committed)
