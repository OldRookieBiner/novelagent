"""情节块、问题链、支线存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.plot_structure import PlotBlock, PlotQuestion, Subplot

logger = logging.getLogger(__name__)


class PlotStore(_BaseStore):
    """情节块 + 问题链 + 支线读写"""

    # --- PlotBlock ---

    def list_plot_blocks(self) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(PlotBlock).filter(
                PlotBlock.project_id == self.project_id
            ).order_by(PlotBlock.chapter_start).all()
            return self._to_dict_list(objs)

    def get_current_plot_block(self, chapter_number: int) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(PlotBlock).filter(
                PlotBlock.project_id == self.project_id,
                PlotBlock.chapter_start <= chapter_number,
            ).order_by(PlotBlock.chapter_start.desc()).first()
            return self._to_dict(obj)

    def create_plot_block(self, data: dict) -> dict:
        with self.session() as db:
            obj = PlotBlock(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_plot_block(self, block_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(PlotBlock).filter(
                PlotBlock.id == block_id,
                PlotBlock.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"PlotBlock {block_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def delete_plot_block(self, block_id: int) -> None:
        with self.session() as db:
            obj = db.query(PlotBlock).filter(
                PlotBlock.id == block_id,
                PlotBlock.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"PlotBlock {block_id} not found")
            db.delete(obj)

    # --- PlotQuestion ---

    def list_plot_questions(self, status: Optional[str] = None) -> list[dict]:
        with self.session(readonly=True) as db:
            query = db.query(PlotQuestion).filter(
                PlotQuestion.project_id == self.project_id
            )
            if status:
                query = query.filter(PlotQuestion.status == status)
            return self._to_dict_list(query.all())

    def get_questions_for_chapter(self, chapter_number: int) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(PlotQuestion).filter(
                PlotQuestion.project_id == self.project_id,
                PlotQuestion.status == "pending",
                PlotQuestion.raised_in_chapter <= chapter_number,
            ).all()
            return self._to_dict_list(objs)

    def create_plot_question(self, data: dict) -> dict:
        with self.session() as db:
            obj = PlotQuestion(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_plot_question(self, question_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(PlotQuestion).filter(
                PlotQuestion.id == question_id,
                PlotQuestion.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"PlotQuestion {question_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- Subplot ---

    def list_subplots(self) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(Subplot).filter(
                Subplot.project_id == self.project_id
            ).all()
            return self._to_dict_list(objs)

    def create_subplot(self, data: dict) -> dict:
        with self.session() as db:
            obj = Subplot(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_subplot(self, subplot_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(Subplot).filter(
                Subplot.id == subplot_id,
                Subplot.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"Subplot {subplot_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def delete_subplot(self, subplot_id: int) -> None:
        with self.session() as db:
            obj = db.query(Subplot).filter(
                Subplot.id == subplot_id,
                Subplot.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"Subplot {subplot_id} not found")
            db.delete(obj)

    # --- 内部方法 ---

    def _read_all_with_session(self, db) -> dict:
        blocks = db.query(PlotBlock).filter(
            PlotBlock.project_id == self.project_id
        ).order_by(PlotBlock.chapter_start).all()
        questions = db.query(PlotQuestion).filter(
            PlotQuestion.project_id == self.project_id
        ).all()
        subplots = db.query(Subplot).filter(
            Subplot.project_id == self.project_id
        ).all()
        return {
            "plot_blocks": self._to_dict_list(blocks),
            "plot_questions": self._to_dict_list(questions),
            "subplots": self._to_dict_list(subplots),
        }
