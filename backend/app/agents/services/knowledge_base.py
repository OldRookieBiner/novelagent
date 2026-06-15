"""知识库读写服务 — thin facade

委托给各 Store，提供跨 Store 编排方法。
所有 Store 返回 dict 而非 ORM 对象，消除 DetachedInstanceError。

设计原则：
- 属性式访问：kb.characters.list_characters() 而非 kb.list_characters()
- 编排方法在 facade 上：跨 Store 的原子操作
- 故事种子直接在 facade 上：Project 表不属于任何 Store
- SSE 流式请求中不会出现 session 并发冲突
"""

import logging
from contextlib import contextmanager
from typing import Optional

from app.database import SessionLocal
from app.models.project import Project
from app.agents.services.stores import (
    OutlineStore,
    WorldSettingStore,
    CharacterStore,
    PlotStore,
    ForeshadowingStore,
    StyleStore,
    TimelineStore,
    VolumeStore,
    ChapterStore,
    ChangeStore,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """知识库读写服务 — thin facade

    委托给各 Store，提供跨 Store 编排方法。
    Store 返回 dict，调用方不再直接接触 ORM 对象。
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.outlines = OutlineStore(project_id)
        self.world_setting = WorldSettingStore(project_id)
        self.characters = CharacterStore(project_id)
        self.plots = PlotStore(project_id)
        self.foreshadowings = ForeshadowingStore(project_id)
        self.styles = StyleStore(project_id)
        self.timelines = TimelineStore(project_id)
        self.volumes = VolumeStore(project_id)
        self.chapters = ChapterStore(project_id)
        self.changes = ChangeStore(project_id)

    # ========== Session 管理 ==========

    @contextmanager
    def session(self, readonly=False):
        """上下文管理器：创建独立 DB session，操作完成后自动关闭

        Args:
            readonly: 只读模式，不执行 commit/rollback
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

    # ========== 故事种子（项目元数据，不属于任何 Store）==========

    def get_story_seed(self) -> Optional[str]:
        """获取项目的故事种子文本"""
        with self.session(readonly=True) as db:
            project = db.query(Project).filter(
                Project.id == self.project_id
            ).first()
            return project.story_seed if project else None

    def update_story_seed(self, story_seed: str) -> None:
        """更新项目的故事种子"""
        with self.session() as db:
            project = db.query(Project).filter(
                Project.id == self.project_id
            ).first()
            if project:
                project.story_seed = story_seed

    # ========== 跨 Store 编排方法 ==========

    def write_chapter_with_tracking(
        self,
        chapter_data: dict,
        timeline_data: dict | None = None,
        foreshadowing_data: list[dict] | None = None,
        snapshot_data: dict | None = None,
    ) -> dict:
        """原子写入章节 + 追踪数据

        单次 session 内完成章节保存 + 时间线 + 伏笔 + 风格快照。
        任何步骤失败则整体回滚。
        """
        with self.session() as db:
            # 1. 保存章节
            result = self.chapters._create_with_session(db, chapter_data)

            # 2. 时间线
            if timeline_data:
                self.timelines._create_with_session(db, timeline_data)

            # 3. 伏笔
            if foreshadowing_data:
                for fs in foreshadowing_data:
                    self.foreshadowings._create_with_session(db, fs)

            # 4. 风格快照
            if snapshot_data:
                self.styles._create_snapshot_with_session(db, snapshot_data)

            return result

    def batch_read_for_index(self) -> dict:
        """单次 session 批量读取所有知识库数据，用于检索索引构建。

        R18 修正：_read_all_with_session 只调用一次并缓存结果，
        消除重复查询（plots 从 9 次降到 3 次，timelines 从 4 次降到 2 次）。
        """
        with self.session(readonly=True) as db:
            # 每种 Store 的 _read_all_with_session 只调用一次
            plots_data = self.plots._read_all_with_session(db)
            timelines_data = self.timelines._read_all_with_session(db)
            return {
                "world_setting": self.world_setting._read_with_session(db),
                "characters": self.characters._read_all_characters_with_session(db),
                "relations": self.characters._read_all_relations_with_session(db),
                "style_constraints": self.styles._read_constraints_with_session(db),
                "plot_blocks": plots_data.get("plot_blocks", []),
                "plot_questions": plots_data.get("plot_questions", []),
                "subplots": plots_data.get("subplots", []),
                "foreshadowings": self.foreshadowings._read_all_with_session(db),
                "timeline": timelines_data.get("timeline", []),
                "style_snapshots": [],  # 快照量大，单独加载
                "scene_entries": timelines_data.get("scene_entries", []),
            }

    def batch_read_volume_for_index(self, volume_number: int) -> dict:
        """单次 session 批量读取指定卷的知识库数据。

        返回 dict（值已为 dict/list[dict]，非 ORM 对象）。
        """
        from app.models.volume import Volume
        from app.models.timeline import TimelineEntry
        from app.models.foreshadowing import Foreshadowing
        from app.models.scene_entry import SceneEntry
        from app.models.cross_volume import CrossVolumeForeshadowing, CrossVolumeSubplot
        from app.agents.services.stores.base import _BaseStore

        with self.session(readonly=True) as db:
            volume = db.query(Volume).filter(
                Volume.project_id == self.project_id,
                Volume.volume_number == volume_number,
            ).first()
            next_volume = db.query(Volume).filter(
                Volume.project_id == self.project_id,
                Volume.volume_number == volume_number + 1,
            ).first()

            volume_dict = _BaseStore._to_dict(volume)
            next_volume_dict = _BaseStore._to_dict(next_volume)

            if volume:
                chapter_start = volume.chapter_offset + 1
                chapter_end = next_volume.chapter_offset if next_volume else 999999

                timeline = db.query(TimelineEntry).filter(
                    TimelineEntry.project_id == self.project_id,
                    TimelineEntry.chapter_number >= chapter_start,
                    TimelineEntry.chapter_number <= chapter_end,
                ).order_by(TimelineEntry.chapter_number).all()

                foreshadowings = db.query(Foreshadowing).filter(
                    Foreshadowing.project_id == self.project_id,
                    Foreshadowing.planted_chapter >= chapter_start,
                    Foreshadowing.planted_chapter <= chapter_end,
                ).all()

                scene_entries = db.query(SceneEntry).filter(
                    SceneEntry.project_id == self.project_id,
                    SceneEntry.chapter_number >= chapter_start,
                    SceneEntry.chapter_number <= chapter_end,
                ).order_by(SceneEntry.id).all()
            else:
                timeline = []
                foreshadowings = []
                scene_entries = []

            cv_foreshadowings = db.query(CrossVolumeForeshadowing).filter(
                CrossVolumeForeshadowing.project_id == self.project_id,
            ).all()
            cv_subplots = db.query(CrossVolumeSubplot).filter(
                CrossVolumeSubplot.project_id == self.project_id,
            ).all()

            return {
                "volume": volume_dict,
                "next_volume": next_volume_dict,
                "timeline": _BaseStore._to_dict_list(timeline),
                "foreshadowings": _BaseStore._to_dict_list(foreshadowings),
                "scene_entries": _BaseStore._to_dict_list(scene_entries),
                "cross_volume_foreshadowings": _BaseStore._to_dict_list(cv_foreshadowings),
                "cross_volume_subplots": _BaseStore._to_dict_list(cv_subplots),
            }

    def validate_prerequisites(self, current_chapter: int | None = None) -> dict:
        """校验写作前置条件，返回 blocked 和 warnings 列表

        从 agent_context.py 迁入，使用 Store 的 dict 返回值。
        """
        blocked = []
        warnings = []
        errors = []

        # 1. 章节大纲记录存在 + 已确认
        if current_chapter:
            try:
                co = self.outlines.get_chapter_outline(current_chapter)
                if not co:
                    blocked.append({
                        "type": "chapter_outline_missing",
                        "chapter": current_chapter,
                        "message": f"第{current_chapter}章大纲不存在",
                        "severity": "error",
                    })
                elif not co.get("confirmed"):
                    blocked.append({
                        "type": "outline_unconfirmed",
                        "chapter": current_chapter,
                        "message": f"第{current_chapter}章大纲尚未确认",
                        "severity": "error",
                    })
            except Exception as e:
                errors.append({"type": "chapter_outline_check", "message": str(e)})

        # 2. 角色存在
        try:
            chars = self.characters.list_characters()
            if not chars:
                blocked.append({
                    "type": "character_missing",
                    "message": "项目中没有任何角色",
                    "severity": "error",
                })
        except Exception as e:
            errors.append({"type": "character_check", "message": str(e)})

        # 3. 世界观存在
        try:
            ws = self.world_setting.get()
            if not ws or not ws.get("core_concept"):
                blocked.append({
                    "type": "world_setting_missing",
                    "message": "项目世界观尚未完善",
                    "severity": "error",
                })
        except Exception as e:
            errors.append({"type": "world_setting_check", "message": str(e)})

        # 4. 伏笔记录
        try:
            fs_list = self.foreshadowings.list_foreshadowings()
            if not fs_list:
                warnings.append({
                    "type": "foreshadowing_empty",
                    "message": "当前无伏笔记录",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "foreshadowing_check", "message": str(e)})

        # 5. 风格约束
        try:
            style = self.styles.get_constraints()
            if not style:
                warnings.append({
                    "type": "style_constraints_missing",
                    "message": "尚未设置风格约束",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "style_check", "message": str(e)})

        # 6. 情节块
        try:
            blocks = self.plots.list_plot_blocks()
            if not blocks:
                warnings.append({
                    "type": "plot_block_empty",
                    "message": "尚未创建情节块",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "plot_block_check", "message": str(e)})

        # 7. 上一章结尾内容
        if current_chapter and current_chapter > 1:
            try:
                prev_ch = self.chapters.get_by_number(current_chapter - 1)
                if not prev_ch or not prev_ch.get("content"):
                    warnings.append({
                        "type": "previous_chapter_empty",
                        "chapter": current_chapter - 1,
                        "message": f"第{current_chapter - 1}章尚无正文",
                        "severity": "warning",
                    })
            except Exception as e:
                errors.append({"type": "previous_chapter_check", "message": str(e)})

        # 8. 关系演变规划
        try:
            rels_with_plans = self.characters.list_relations_with_plans()
            has_plans = any(r.get("plans") for r in rels_with_plans)
            if not has_plans:
                warnings.append({
                    "type": "relation_evolution_empty",
                    "message": "尚未创建关系演变规划",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "evolution_check", "message": str(e)})

        # 9. 时间线记录
        try:
            timeline = self.timelines.list_timeline()
            if not timeline:
                warnings.append({
                    "type": "timeline_empty",
                    "message": "尚未创建时间线记录",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "timeline_check", "message": str(e)})

        result = {
            "blocked": blocked,
            "warnings": warnings,
            "validated": True,
        }
        if errors:
            result["errors"] = errors
        return result

    def search_chapters_for_references(self, keywords: list[str], max_chapters: int = 50) -> list[dict]:
        """搜索包含关键词的章节段落（跨 ChapterOutline + Chapter 联合查询）"""
        return self.chapters.search_references(keywords, max_chapters)

    def batch_read_for_context(self, current_chapter_number: int | None = None) -> dict:
        """单次 session 批量读取上下文构建所需的全部数据

        与 batch_read_for_index 的区别：
        - 包含章节正文（index 版本不含，太长）
        - 包含上一章结尾片段
        - 包含变更记录
        - 包含章节大纲（index 版本不含）
        - 不包含场景清单（index 版本需要）
        """
        with self.session(readonly=True) as db:
            plots_data = self.plots._read_all_with_session(db)
            timelines_data = self.timelines._read_all_with_session(db)

            # 章节：含正文
            chapters = self.chapters._read_all_with_session(db)

            # 章节大纲
            chapter_outlines = self.outlines._read_chapter_outlines_with_session(db)

            # 变更记录
            changes = self.changes._read_all_with_session(db)

            # 上一章结尾
            previous_closing = None
            if current_chapter_number and current_chapter_number > 1:
                prev = self.chapters._read_by_number_with_session(db, current_chapter_number - 1)
                if prev and prev.get("content"):
                    content = prev["content"]
                    previous_closing = content[-500:] if len(content) > 500 else content

            # 风格快照（最近 10 条）
            style_snapshots = self.styles._read_snapshots_with_session(db, last_n=10)

            return {
                "world_setting": self.world_setting._read_with_session(db),
                "characters": self.characters._read_all_characters_with_session(db),
                "relations": self.characters._read_all_relations_with_session(db),
                "style_constraints": self.styles._read_constraints_with_session(db),
                "outline": self.outlines._read_with_session(db),
                "chapter_outlines": chapter_outlines,
                "plot_blocks": plots_data.get("plot_blocks", []),
                "plot_questions": plots_data.get("plot_questions", []),
                "subplots": plots_data.get("subplots", []),
                "foreshadowings": self.foreshadowings._read_all_with_session(db),
                "timeline": timelines_data.get("timeline", []),
                "style_snapshots": style_snapshots,
                "chapters": chapters,
                "changes": changes,
                "previous_closing": previous_closing,
            }
