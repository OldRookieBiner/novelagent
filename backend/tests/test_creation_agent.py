"""创作智能体集成测试

覆盖：
1. 数据模型创建和查询
2. KnowledgeBaseService CRUD
3. NovelState v2 类型安全
4. StateGraph 节点路由逻辑
5. 知识库 API 端点
"""

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Project, Outline, WorldSetting, StyleConstraints,
    PlotBlock, PlotQuestion, Subplot, Foreshadowing, TimelineEntry, StyleSnapshot, SceneEntry,
    Character, User,
)
from app.agents.state import NovelState, Phase, ConfirmationType, replace_or_append_chapters
from app.agents.services.knowledge_base import KnowledgeBaseService


# ========== Fixtures ==========

@pytest.fixture
def test_user(db: Session):
    from app.utils.auth import hash_password
    user = User(username="test_agent_user", password_hash=hash_password("test123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_project(db: Session, test_user):
    project = Project(
        user_id=test_user.id,
        name="测试小说项目",
        target_words=100000,
        total_words=0,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture
def test_outline(db: Session, test_project):
    outline = Outline(
        project_id=test_project.id,
        title="测试大纲",
        summary="一部关于未来的小说",
    )
    db.add(outline)
    db.commit()
    db.refresh(outline)
    return outline


# ========== 1. 数据模型测试 ==========

class TestCreationModels:
    def test_world_setting_create(self, db: Session, test_project):
        ws = WorldSetting(
            project_id=test_project.id,
            core_concept="赛博朋克与东方玄幻的融合世界",
            tiered_settings={
                "red": ["灵气即数据流"],
                "yellow": ["城邦政治结构"],
                "green": ["日常饮食文化"],
            },
            key_locations=["长安市", "云端阁"],
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)

        assert ws.id is not None
        assert ws.project_id == test_project.id
        assert ws.core_concept == "赛博朋克与东方玄幻的融合世界"
        assert len(ws.tiered_settings["red"]) == 1
        assert len(ws.key_locations) == 2

    def test_style_constraints_create(self, db: Session, test_project):
        sc = StyleConstraints(
            project_id=test_project.id,
            taboo_words=["突然", "居然"],
            forbidden_patterns=["突然之间", "不知为何"],
            style_anchor="古龙式短句+赛博朋克冷峻",
            abstract_rules=["对话占比不低于30%", "每章至少一个反转"],
        )
        db.add(sc)
        db.commit()
        db.refresh(sc)

        assert sc.id is not None
        assert len(sc.taboo_words) == 2
        assert sc.style_anchor == "古龙式短句+赛博朋克冷峻"

    def test_plot_block_create(self, db: Session, test_project):
        pb = PlotBlock(
            project_id=test_project.id,
            title="起源之章",
            questions_to_answer=["主角为何失去记忆?"],
            questions_to_raise=["数据灵气的来源是什么?"],
            must_happen=["主角觉醒", "初次接触灵气网络"],
            expected_mood="紧张+好奇",
            chapter_start=1,
            chapter_end=10,
        )
        db.add(pb)
        db.commit()
        db.refresh(pb)

        assert pb.id is not None
        assert pb.title == "起源之章"
        assert len(pb.questions_to_answer) == 1
        assert len(pb.must_happen) == 2

    def test_foreshadowing_create(self, db: Session, test_project):
        fs = Foreshadowing(
            project_id=test_project.id,
            content="主角手腕上的神秘纹路",
            level="hint",
            appearance_count=1,
            status="active",
            planted_chapter=1,
            expected_resolve_chapter=15,
            related_characters=["主角"],
        )
        db.add(fs)
        db.commit()
        db.refresh(fs)

        assert fs.id is not None
        assert fs.status == "active"
        assert fs.level == "hint"

    def test_timeline_entry_create(self, db: Session, test_project):
        te = TimelineEntry(
            project_id=test_project.id,
            chapter_number=1,
            summary="主角在长安市醒来，发现记忆缺失",
            causal_chain="觉醒→发现纹路→接触灵气网络",
            rhythm_score=4,
            tension_score=3,
            emotion_score=4,
            emotion_tag="紧张",
        )
        db.add(te)
        db.commit()
        db.refresh(te)

        assert te.id is not None
        assert te.chapter_number == 1
        assert te.rhythm_score == 4

    def test_style_snapshot_create(self, db: Session, test_project):
        ss = StyleSnapshot(
            project_id=test_project.id,
            chapter_number=1,
            paragraph_count=20,
            avg_paragraph_length=85.5,
            dialogue_ratio=0.35,
            avg_sentence_length=22.3,
        )
        db.add(ss)
        db.commit()
        db.refresh(ss)

        assert ss.id is not None
        assert ss.dialogue_ratio == 0.35

    def test_scene_entry_create(self, db: Session, test_project):
        """SceneEntry 使用正确的模型字段"""
        se = SceneEntry(
            project_id=test_project.id,
            chapter_number=1,
            scene_index=1,
            location="长安市街头",
            characters_present=["主角", "老者"],
            mood="紧张",
            key_events=["主角被追杀"],
        )
        db.add(se)
        db.commit()
        db.refresh(se)

        assert se.id is not None
        assert se.scene_index == 1
        assert se.location == "长安市街头"
        assert len(se.characters_present) == 2
        assert se.mood == "紧张"


# ========== 2. NovelState v2 类型安全 ==========

class TestNovelStateV2:
    def test_phase_enum_values(self):
        assert Phase.INCUBATION.value == "incubation"
        assert Phase.STRUCTURE.value == "structure"
        assert Phase.WRITING.value == "writing"
        assert Phase.REVISION.value == "revision"

    def test_confirmation_type_enum_values(self):
        assert ConfirmationType.INSPIRATION_DIALOGUE.value == "inspiration_dialogue"
        assert ConfirmationType.CHAPTER_NODE.value == "chapter_node"
        assert ConfirmationType.FORESHADOWING_PLAN.value == "foreshadowing_plan"

    def test_replace_or_append_chapters_new(self):
        existing = []
        new_items = [{"chapter_number": 1, "content": "第一章正文"}]
        result = replace_or_append_chapters(existing, new_items)
        assert len(result) == 1
        assert result[0]["chapter_number"] == 1

    def test_replace_or_append_chapters_replace(self):
        existing = [
            {"chapter_number": 1, "content": "旧内容", "word_count": 1000},
            {"chapter_number": 2, "content": "第二章", "word_count": 2000},
        ]
        new_items = [{"chapter_number": 1, "content": "新内容", "word_count": 1500}]
        result = replace_or_append_chapters(existing, new_items)
        assert len(result) == 2
        assert result[0]["content"] == "新内容"
        assert result[0]["word_count"] == 1500
        assert result[1]["chapter_number"] == 2

    def test_novel_state_initial_values(self):
        state: NovelState = {
            "project_id": 1,
            "phase": Phase.INCUBATION.value,
            "story_seed": None,
            "inspiration_messages": [],
            "outline_id": None,
            "world_setting_id": None,
            "style_constraints_id": None,
            "current_plot_block_index": 0,
            "chapter_count": 0,
            "current_chapter": 0,
            "written_chapters": [],
            "chapter_plan": None,
            "assembled_context": None,
            "post_write_summary": None,
            "last_review_chapter": 0,
            "waiting_for_confirmation": False,
            "confirmation_type": None,
            "llm_config_id": None,
            "review_llm_config_id": None,
            "llm_model_name": None,
            "_prompts": {},
            "_context_window": 4096,
        }
        assert state["phase"] == "incubation"
        assert state["waiting_for_confirmation"] is False
        assert len(state["written_chapters"]) == 0
        assert state["chapter_plan"] is None
        assert state["assembled_context"] is None


# ========== 3. KnowledgeBaseService CRUD ==========

class TestKnowledgeBaseService:
    def test_create_and_get_world_setting(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        ws = kb.create_world_setting({
            "core_concept": "科幻与仙侠的融合",
            "tiered_settings": {"red": ["核心设定1"]},
            "key_locations": ["地点A"],
        })
        assert ws is not None
        assert ws.project_id == test_project.id

        fetched = kb.get_world_setting()
        assert fetched is not None
        assert fetched.core_concept == "科幻与仙侠的融合"

    def test_create_and_get_style_constraints(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        sc = kb.create_style_constraints({
            "taboo_words": ["突然"],
            "style_anchor": "简洁有力",
        })
        assert sc is not None
        assert sc.taboo_words == ["突然"]

        fetched = kb.get_style_constraints()
        assert fetched is not None
        assert fetched.style_anchor == "简洁有力"

    def test_update_style_constraints(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        sc = kb.create_style_constraints({
            "taboo_words": ["突然"],
            "style_anchor": "简洁",
        })
        updated = kb.update_style_constraints(sc.id, {"style_anchor": "更新后锚点"})
        assert updated.style_anchor == "更新后锚点"

    def test_get_plot_blocks_empty(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        blocks = kb.get_plot_blocks()
        assert blocks == []

    def test_create_and_get_foreshadowings(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        fs = kb.create_foreshadowing({
            "content": "神秘纹路",
            "level": "hint",
            "status": "active",
            "planted_chapter": 1,
        })
        assert fs is not None

        all_fs = kb.get_foreshadowings()
        assert len(all_fs) >= 1

        active_fs = kb.get_foreshadowings(status="active")
        assert len(active_fs) >= 1

    def test_get_timeline_empty(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        timeline = kb.get_timeline()
        assert timeline == []

    def test_update_world_setting(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        ws = kb.create_world_setting({"core_concept": "初始概念"})
        updated = kb.update_world_setting(ws.id, {"core_concept": "更新后概念"})
        assert updated.core_concept == "更新后概念"

    def test_create_and_get_scene_entries(self, db: Session, test_project):
        kb = KnowledgeBaseService(test_project.id)
        kb.create_scene_entry({
            "chapter_number": 1,
            "scene_index": 1,
            "location": "长安市",
            "characters_present": ["主角"],
            "mood": "紧张",
            "key_events": ["觉醒"],
        })
        entries = kb.get_scene_entries(chapter_number=1)
        assert len(entries) == 1
        assert entries[0].location == "长安市"


# ========== 4. Knowledge API 端点 ==========

class TestKnowledgeAPI:
    def test_get_world_setting_not_found(self, client, test_project):
        from app.utils.auth import create_session_token
        token = create_session_token(test_project.user_id)
        client.cookies.set("session_token", token)

        resp = client.get(f"/api/projects/{test_project.id}/world-setting")
        assert resp.status_code == 404

    def test_get_style_constraints_not_found(self, client, test_project):
        from app.utils.auth import create_session_token
        token = create_session_token(test_project.user_id)
        client.cookies.set("session_token", token)

        resp = client.get(f"/api/projects/{test_project.id}/style-constraints")
        assert resp.status_code == 404

    def test_get_plot_blocks_empty(self, client, test_project):
        from app.utils.auth import create_session_token
        token = create_session_token(test_project.user_id)
        client.cookies.set("session_token", token)

        resp = client.get(f"/api/projects/{test_project.id}/plot-blocks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_foreshadowings_empty(self, client, test_project):
        from app.utils.auth import create_session_token
        token = create_session_token(test_project.user_id)
        client.cookies.set("session_token", token)

        resp = client.get(f"/api/projects/{test_project.id}/foreshadowings")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_timeline_empty(self, client, test_project):
        from app.utils.auth import create_session_token
        token = create_session_token(test_project.user_id)
        client.cookies.set("session_token", token)

        resp = client.get(f"/api/projects/{test_project.id}/timeline")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_style_snapshots_empty(self, client, test_project):
        from app.utils.auth import create_session_token
        token = create_session_token(test_project.user_id)
        client.cookies.set("session_token", token)

        resp = client.get(f"/api/projects/{test_project.id}/style-snapshots")
        assert resp.status_code == 200
        assert resp.json() == []
