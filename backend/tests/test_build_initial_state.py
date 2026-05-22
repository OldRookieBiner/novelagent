"""Tests for build_initial_state DB preloading logic."""

import pytest
from unittest.mock import MagicMock


class TestBuildInitialState:
    """测试 build_initial_state 的 DB 预加载功能"""

    def test_accepts_db_param(self):
        """build_initial_state 应接受可选的 db 参数"""
        from app.api.workflow import build_initial_state
        import inspect

        sig = inspect.signature(build_initial_state)
        params = list(sig.parameters.keys())
        assert "db" in params, f"build_initial_state should have 'db' parameter, got: {params}"

    def test_preloads_characters_with_ids(self):
        """当 DB 有角色时，state['characters'] 应包含 id 字段"""
        from app.api.workflow import build_initial_state
        from app.models.character import Character

        project = MagicMock()
        project.id = 1
        project.chapter_outlines = []
        project.novel_length = 100000

        outline = MagicMock()
        outline.collected_info = {}
        outline.inspiration_template = None
        outline.title = "Test"
        outline.summary = "Summary"
        outline.plot_points = []
        outline.characters = []
        outline.world_setting = None
        outline.emotional_curve = None
        outline.confirmed = False
        outline.chapter_count_suggested = 10

        workflow_state = MagicMock()
        workflow_state.stage = "outline"
        workflow_state.current_chapter = 0
        workflow_state.workflow_mode = "hybrid"
        workflow_state.max_rewrite_count = 3
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

        db = MagicMock()

        # Mock character query chain
        char_mock = MagicMock()
        char_mock.id = 42
        char_mock.name = "Alice"
        char_mock.role = "主角"
        char_mock.personality = "Brave"
        char_mock.core_motivation = "Save world"
        char_mock.growth_arc = "Grows"

        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [char_mock]

        state = build_initial_state(project, outline, workflow_state, db=db)

        assert "characters" in state
        assert len(state["characters"]) == 1
        assert state["characters"][0]["id"] == 42
        assert state["characters"][0]["name"] == "Alice"

    def test_preloads_relations_with_ids(self):
        """当 DB 有关系时，state['relations'] 应包含 id 字段"""
        from app.api.workflow import build_initial_state
        from app.models.character import Character, Relation

        project = MagicMock()
        project.id = 1
        project.chapter_outlines = []
        project.novel_length = 100000

        outline = MagicMock()
        outline.collected_info = {}
        outline.inspiration_template = None
        outline.title = "Test"
        outline.summary = "Summary"
        outline.plot_points = []
        outline.characters = []
        outline.world_setting = None
        outline.emotional_curve = None
        outline.confirmed = False
        outline.chapter_count_suggested = 10

        workflow_state = MagicMock()
        workflow_state.stage = "outline"
        workflow_state.current_chapter = 0
        workflow_state.workflow_mode = "hybrid"
        workflow_state.max_rewrite_count = 3
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

        db = MagicMock()

        # Mock character query - empty
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        # Mock relation query
        rel_mock = MagicMock()
        rel_mock.id = 99
        rel_mock.character_a_id = 1
        rel_mock.character_b_id = 2
        rel_mock.relation_type = "信任"
        rel_mock.trust_level = 80
        rel_mock.current_status = "Friends"
        rel_mock.direction = "双向"

        # Need to set up the mock to return different results for different queries
        # This is tricky with MagicMock, so we'll use side_effect
        def mock_query(model):
            mock_q = MagicMock()
            if model == Character:
                mock_q.filter.return_value.order_by.return_value.all.return_value = []
                return mock_q
            elif model == Relation:
                mock_q.filter.return_value.all.return_value = [rel_mock]
                return mock_q
            return mock_q

        db.query.side_effect = mock_query

        state = build_initial_state(project, outline, workflow_state, db=db)

        assert "relations" in state
        assert len(state["relations"]) == 1
        assert state["relations"][0]["id"] == 99
