"""Phase 4: Volume Management + Full-Book Revision tests

Tests for:
1. Volume model + cross-volume models
2. KnowledgeBaseService volume/cross-volume CRUD
3. Volume transition node logic
4. Graph routing (volume_transition, per-volume/full-book revision)
5. Cross-volume warning checks
6. SSE event formatters
7. Enhanced revision nodes (scope control)
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ========== Volume Model ==========

class TestVolumeModel:
    """Test Volume model Phase 4 fields"""

    def test_volume_has_phase4_fields(self):
        from app.models.volume import Volume
        # Verify model has the Phase 4 columns
        col_names = [c.name for c in Volume.__table__.columns]
        assert "chapter_offset" in col_names
        assert "character_snapshot" in col_names
        assert "last_block_summary" in col_names

    def test_volume_default_offset(self):
        from app.models.volume import Volume
        # Verify the column definition has default=0
        col = Volume.__table__.c.chapter_offset
        assert col.default is not None
        assert col.default.arg == 0


class TestCrossVolumeModels:
    """Test CrossVolumeForeshadowing, CrossVolumeSubplot, CharacterChangeLog"""

    def test_cvf_model_fields(self):
        from app.models.cross_volume import CrossVolumeForeshadowing
        col_names = [c.name for c in CrossVolumeForeshadowing.__table__.columns]
        assert "source_foreshadowing_id" in col_names
        assert "appearance_count" in col_names
        assert "expected_volume" in col_names
        assert "status" in col_names

    def test_cvs_model_fields(self):
        from app.models.cross_volume import CrossVolumeSubplot
        col_names = [c.name for c in CrossVolumeSubplot.__table__.columns]
        assert "source_subplot_id" in col_names
        assert "status" in col_names
        assert "expected_intersection_volume" in col_names

    def test_ccl_model_fields(self):
        from app.models.cross_volume import CharacterChangeLog
        col_names = [c.name for c in CharacterChangeLog.__table__.columns]
        assert "volume_number" in col_names
        assert "character_id" in col_names
        assert "changes" in col_names
        assert "chapter_number" in col_names


# ========== NovelState Phase 4 ==========

class TestNovelStatePhase4:
    """Test NovelState Phase 4 fields"""

    def test_volume_transition_confirmation(self):
        from app.agents.state import ConfirmationType
        assert ConfirmationType.VOLUME_TRANSITION.value == "volume_transition"

    def test_revision_context_enum(self):
        from app.agents.state import RevisionContext
        assert RevisionContext.PER_VOLUME.value == "per_volume"
        assert RevisionContext.FULL_BOOK.value == "full_book"


# ========== KnowledgeBaseService CRUD ==========

class TestKnowledgeBaseVolumeCRUD:
    """Test volume and cross-volume CRUD methods exist"""

    def test_has_volume_methods(self):
        from app.agents.services.knowledge_base import KnowledgeBaseService
        kb = KnowledgeBaseService(project_id=1)
        assert hasattr(kb, "get_volumes")
        assert hasattr(kb, "get_volume")
        assert hasattr(kb, "create_volume")
        assert hasattr(kb, "update_volume")
        assert hasattr(kb, "get_current_volume")

    def test_has_cross_volume_methods(self):
        from app.agents.services.knowledge_base import KnowledgeBaseService
        kb = KnowledgeBaseService(project_id=1)
        assert hasattr(kb, "get_cross_volume_foreshadowings")
        assert hasattr(kb, "create_cross_volume_foreshadowing")
        assert hasattr(kb, "update_cross_volume_foreshadowing")
        assert hasattr(kb, "get_cross_volume_subplots")
        assert hasattr(kb, "create_cross_volume_subplot")
        assert hasattr(kb, "update_cross_volume_subplot")
        assert hasattr(kb, "get_character_change_logs")
        assert hasattr(kb, "create_character_change_log")


# ========== Volume Transition Node ==========

class TestVolumeTransitionNode:
    """Test volume_transition_node logic"""

    @pytest.mark.asyncio
    async def test_node_increments_volume(self):
        from app.agents.nodes.volume_transition import volume_transition_node
        from app.agents.state import RevisionContext

        # Mock KB service
        with patch("app.agents.nodes.volume_transition.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            # Mock volume
            mock_volume = MagicMock()
            mock_volume.id = 1
            mock_volume.character_snapshot = []
            mock_kb.get_volume.return_value = mock_volume
            mock_kb.get_foreshadowings.return_value = []
            mock_kb.get_subplots.return_value = []
            mock_kb.get_characters.return_value = []
            mock_kb.get_cross_volume_foreshadowings.return_value = []
            mock_kb.get_cross_volume_subplots.return_value = []
            mock_kb.get_current_plot_block.return_value = None

            # Mock RetrievalService
            with patch("app.agents.nodes.volume_transition.RetrievalService") as MockRetrieval:
                mock_retrieval = MagicMock()
                MockRetrieval.return_value = mock_retrieval

                # Mock LLM
                with patch("app.agents.nodes.volume_transition.get_llm_from_state_async") as MockLLM:
                    mock_llm = AsyncMock()
                    mock_llm.chat_stream = AsyncMock(return_value=iter(["过渡摘要"]))
                    MockLLM.return_value = mock_llm

                    state = {
                        "project_id": 1,
                        "current_volume": 1,
                        "current_chapter": 50,
                    }

                    result = await volume_transition_node(state)

                    assert result["current_volume"] == 2
                    assert result["revision_context"] == RevisionContext.PER_VOLUME.value
                    mock_kb.create_volume.assert_called_once()


# ========== Graph Routing ==========

class TestGraphRouting:
    """Test Phase 4 graph routing functions"""

    def test_should_transition_user_trigger(self):
        from app.agents.graph import _should_transition_volume
        from app.agents.state import ConfirmationType

        state = {
            "project_id": 1,
            "current_chapter": 10,
            "current_volume": 1,
            "confirmation_type": ConfirmationType.VOLUME_TRANSITION.value,
        }
        assert _should_transition_volume(state) is True

    def test_should_not_transition_normal(self):
        from app.agents.graph import _should_transition_volume

        with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            # Normal volume with low chapter count
            mock_volume = MagicMock()
            mock_volume.chapter_offset = 0
            mock_kb.get_volume.return_value = mock_volume
            mock_kb.get_current_plot_block.return_value = None

            state = {
                "project_id": 1,
                "current_chapter": 10,
                "current_volume": 1,
            }
            assert _should_transition_volume(state) is False

    def test_should_transition_capacity_first_volume(self):
        from app.agents.graph import _should_transition_volume

        with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            mock_volume = MagicMock()
            mock_volume.chapter_offset = 0
            mock_kb.get_volume.return_value = mock_volume
            mock_kb.get_current_plot_block.return_value = None

            # First volume, > 120 chapters
            state = {
                "project_id": 1,
                "current_chapter": 125,
                "current_volume": 1,
            }
            assert _should_transition_volume(state) is True

    def test_route_after_final_polish_per_volume(self):
        from app.agents.graph import route_after_final_polish
        from app.agents.state import RevisionContext

        state = {"revision_context": RevisionContext.PER_VOLUME.value}
        assert route_after_final_polish(state) == "context_assembly"

    def test_route_after_final_polish_full_book(self):
        from app.agents.graph import route_after_final_polish

        state = {"revision_context": None}
        assert route_after_final_polish(state) == "__end__"

    def test_route_after_volume_transition(self):
        from app.agents.graph import route_after_volume_transition

        state = {}
        assert route_after_volume_transition(state) == "structural_review"


# ========== Cross-Volume Warnings ==========

class TestCrossVolumeWarnings:
    """Test cross-volume warning checks"""

    def test_cv_subplot_overdue_no_volume(self):
        from app.agents.services.warning import WarningService
        with patch("app.agents.services.warning.KnowledgeBaseService"):
            ws = WarningService(project_id=1)
            # Volume <= 1: no cross-volume checks
            assert ws.check_cross_volume_subplot_overdue(1) is None

    def test_cv_subplot_overdue_with_overdue(self):
        from app.agents.services.warning import WarningService
        with patch("app.agents.services.warning.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            ws = WarningService(project_id=1)
            ws.kb = mock_kb

            mock_cvs = MagicMock()
            mock_cvs.id = 1
            mock_cvs.expected_intersection_volume = 3
            mock_kb.get_cross_volume_subplots.return_value = [mock_cvs]

            result = ws.check_cross_volume_subplot_overdue(5)
            assert result is not None
            assert result["type"] == "cross_volume_subplot_overdue"

    def test_character_state_jump_no_jump(self):
        from app.agents.services.warning import WarningService
        with patch("app.agents.services.warning.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            ws = WarningService(project_id=1)
            ws.kb = mock_kb

            # No change logs
            mock_kb.get_character_change_logs.return_value = []
            result = ws.check_character_state_jump(2)
            assert result is None

    def test_long_term_foreshadowing_overdue_no_overdue(self):
        from app.agents.services.warning import WarningService
        with patch("app.agents.services.warning.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            ws = WarningService(project_id=1)
            ws.kb = mock_kb

            # Active CVF but not overdue
            mock_cvf = MagicMock()
            mock_cvf.id = 1
            mock_cvf.expected_volume = 5
            mock_cvf.status = "active"
            mock_kb.get_cross_volume_foreshadowings.return_value = [mock_cvf]

            result = ws.check_long_term_foreshadowing_overdue(4)
            assert result is None

    def test_check_all_includes_cross_volume(self):
        from app.agents.services.warning import WarningService
        with patch("app.agents.services.warning.KnowledgeBaseService") as MockKB:
            mock_kb = MagicMock()
            MockKB.return_value = mock_kb

            ws = WarningService(project_id=1)
            ws.kb = mock_kb

            # Mock all basic checks to return None
            mock_kb.get_overdue_foreshadowings.return_value = []
            mock_kb.get_style_snapshots.return_value = []
            mock_kb.get_timeline.return_value = []
            mock_kb.get_world_setting.return_value = MagicMock(tiered_settings=None)
            mock_kb.get_plot_questions.return_value = []

            # Cross-volume data: overdue CVF
            mock_cvf = MagicMock()
            mock_cvf.id = 1
            mock_cvf.expected_volume = 3
            mock_cvf.status = "active"
            mock_kb.get_cross_volume_foreshadowings.return_value = [mock_cvf]
            mock_kb.get_cross_volume_subplots.return_value = []
            mock_kb.get_character_change_logs.return_value = []

            # Clear dedup cache
            from app.agents.services.warning import _project_warnings
            _project_warnings.clear()

            result = ws.check_all(50, current_volume=5)
            # Should include cross-volume warning
            warning_types = [w["type"] for w in result]
            assert "long_term_foreshadowing_overdue" in warning_types


# ========== SSE Events ==========

class TestSSEEvents:
    """Test Phase 4 SSE event formatters"""

    def test_volume_transition_event(self):
        from app.agents.sse_events import format_volume_transition
        data = {"current_volume": 1, "new_volume": 2, "chapter_offset": 50}
        result = format_volume_transition(data)
        assert "volume_transition" in result
        assert "1" in result
        assert "2" in result

    def test_volume_review_event(self):
        from app.agents.sse_events import format_volume_review
        data = {"volume_number": 2, "review_type": "per_volume", "issues": []}
        result = format_volume_review(data)
        assert "volume_review" in result

    def test_revision_report_event(self):
        from app.agents.sse_events import format_revision_report
        data = {"revision_context": "full_book", "total_volumes": 3, "issues": []}
        result = format_revision_report(data)
        assert "revision_report" in result


# ========== Prompts ==========

class TestPhase4Prompts:
    """Test Phase 4 prompts are registered"""

    def test_volume_transition_prompt_exists(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "volume_transition" in DEFAULT_PROMPTS

    def test_per_volume_structural_review_prompt(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "per_volume_structural_review" in DEFAULT_PROMPTS

    def test_full_book_structural_review_prompt(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "full_book_structural_review" in DEFAULT_PROMPTS

    def test_per_volume_character_arc_review_prompt(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "per_volume_character_arc_review" in DEFAULT_PROMPTS

    def test_full_book_character_arc_review_prompt(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "full_book_character_arc_review" in DEFAULT_PROMPTS

    def test_final_polish_full_prompt(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "final_polish_full" in DEFAULT_PROMPTS

    def test_volume_review_prompt(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "volume_review" in DEFAULT_PROMPTS
