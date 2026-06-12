"""角色、关系、演变规划/记录存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.models.character import Character, Relation, EvolutionPlan, EvolutionRecord

logger = logging.getLogger(__name__)


class CharacterStore(_BaseStore):
    """角色 + 关系 + 演变读写"""

    # --- Character ---

    def list_characters(self) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(Character).filter(
                Character.project_id == self.project_id
            ).all()
            return self._to_dict_list(objs)

    def get_character(self, character_id: int) -> Optional[dict]:
        with self.session(readonly=True) as db:
            obj = db.query(Character).filter(
                Character.id == character_id,
                Character.project_id == self.project_id,
            ).first()
            return self._to_dict(obj)

    def create_character(self, data: dict) -> dict:
        with self.session() as db:
            obj = Character(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_character(self, character_id: int, data: dict) -> dict:
        """更新角色（直接字段更新，用于 impact decision 的 apply）"""
        with self.session() as db:
            obj = db.query(Character).filter(
                Character.id == character_id,
                Character.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"Character {character_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- Relation ---

    def list_relations(self) -> list[dict]:
        with self.session(readonly=True) as db:
            objs = db.query(Relation).filter(
                Relation.project_id == self.project_id
            ).all()
            return self._to_dict_list(objs)

    def create_relation(self, data: dict) -> dict:
        with self.session() as db:
            obj = Relation(project_id=self.project_id, **data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def update_relation(self, relation_id: int, data: dict) -> dict:
        with self.session() as db:
            obj = db.query(Relation).filter(
                Relation.id == relation_id,
                Relation.project_id == self.project_id,
            ).first()
            if not obj:
                raise ValueError(f"Relation {relation_id} not found")
            for key, value in data.items():
                setattr(obj, key, value)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def get_relations_by_character_names(self, names: list[str]) -> list[dict]:
        """获取涉及指定角色名的关系"""
        with self.session() as db:
            characters = (
                db.query(Character)
                .filter(Character.project_id == self.project_id, Character.name.in_(names))
                .all()
            )
            character_ids = [c.id for c in characters]
            if not character_ids:
                return []
            from sqlalchemy import or_
            relations = (
                db.query(Relation)
                .filter(
                    Relation.project_id == self.project_id,
                    or_(
                        Relation.character_a_id.in_(character_ids),
                        Relation.character_b_id.in_(character_ids),
                    ),
                )
                .all()
            )
            return self._to_dict_list(relations)

    # --- EvolutionPlan ---

    def list_evolution_plans_triggering_at(self, chapter_number: int) -> list[dict]:
        """获取在指定章节触发的关系演变规划"""
        with self.session(readonly=True) as db:
            relation_ids = (
                db.query(Relation.id)
                .filter(Relation.project_id == self.project_id)
                .all()
            )
            relation_ids = [r.id for r in relation_ids]
            if not relation_ids:
                return []
            plans = (
                db.query(EvolutionPlan)
                .filter(
                    EvolutionPlan.relation_id.in_(relation_ids),
                    EvolutionPlan.trigger_chapter <= chapter_number,
                    EvolutionPlan.is_triggered == False,
                )
                .all()
            )
            return self._to_dict_list(plans)

    def list_relations_with_plans(self) -> list[dict]:
        """获取所有关系及其演变规划（嵌套 dict）"""
        with self.session(readonly=True) as db:
            relations = (
                db.query(Relation)
                .filter(Relation.project_id == self.project_id)
                .all()
            )
            result = []
            for rel in relations:
                rel_dict = self._to_dict(rel)
                plans = (
                    db.query(EvolutionPlan)
                    .filter(EvolutionPlan.relation_id == rel.id)
                    .order_by(EvolutionPlan.trigger_chapter)
                    .all()
                )
                rel_dict["plans"] = self._to_dict_list(plans)
                result.append(rel_dict)
            return result

    def create_evolution_plan(self, data: dict) -> dict:
        with self.session() as db:
            obj = EvolutionPlan(**data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    def mark_evolution_plan_triggered(self, relation_id: int, chapter_number: int) -> list[dict]:
        """标记指定章节的演变规划为已触发"""
        with self.session() as db:
            plans = (
                db.query(EvolutionPlan)
                .filter(
                    EvolutionPlan.relation_id == relation_id,
                    EvolutionPlan.trigger_chapter == chapter_number,
                    EvolutionPlan.is_triggered == False,
                )
                .all()
            )
            for plan in plans:
                plan.is_triggered = True
            db.flush()
            return self._to_dict_list(plans)

    def update_relation_trust_level(self, relation_id: int, new_trust_level: int) -> None:
        """更新关系信任度"""
        with self.session() as db:
            rel = db.query(Relation).filter(Relation.id == relation_id).first()
            if rel:
                rel.trust_level = max(0, min(100, new_trust_level))

    # --- EvolutionRecord ---

    def create_evolution_record(self, data: dict) -> dict:
        """创建演变记录（幂等：同章节同关系只创建一条）"""
        with self.session() as db:
            existing = (
                db.query(EvolutionRecord)
                .filter(
                    EvolutionRecord.relation_id == data.get("relation_id"),
                    EvolutionRecord.chapter_number == data.get("chapter_number"),
                )
                .first()
            )
            if existing:
                return self._to_dict(existing)
            obj = EvolutionRecord(**data)
            db.add(obj)
            db.flush()
            db.refresh(obj)
            return self._to_dict(obj)

    # --- 内部方法 ---

    def _read_all_characters_with_session(self, db) -> list[dict]:
        objs = db.query(Character).filter(
            Character.project_id == self.project_id
        ).all()
        return self._to_dict_list(objs)

    def _read_all_relations_with_session(self, db) -> list[dict]:
        objs = db.query(Relation).filter(
            Relation.project_id == self.project_id
        ).all()
        return self._to_dict_list(objs)
