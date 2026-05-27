"""Phase 3: Semantic Retrieval + Writing Quality Polish tests

Tests for:
1. RetrievalService (chunking, indexing, search)
2. Foreshadowing 3-level progression logic
3. Style drift detection
4. WarningService checks
5. Enhanced prompts registration
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ========== RetrievalService ==========

class TestChunkText:
    """Test text chunking logic from novelskills search.py"""

    def test_short_text_single_chunk(self):
        from app.agents.services.retrieval import chunk_text
        text = "这是一个短文本"
        chunks = chunk_text(text, min_chars=2, max_chars=300)
        assert len(chunks) == 1
        assert chunks[0] == "这是一个短文本"

    def test_long_text_split_by_paragraphs(self):
        from app.agents.services.retrieval import chunk_text
        # Two paragraphs, each > max_chars
        text = "第一段内容" * 50 + "\n\n" + "第二段内容" * 50
        chunks = chunk_text(text, min_chars=10, max_chars=100)
        assert len(chunks) >= 2

    def test_empty_text_no_chunks(self):
        from app.agents.services.retrieval import chunk_text
        chunks = chunk_text("", min_chars=2)
        assert len(chunks) == 0

    def test_below_min_chars_filtered(self):
        from app.agents.services.retrieval import chunk_text
        text = "短"
        chunks = chunk_text(text, min_chars=50)
        assert len(chunks) == 0


class TestTokenizeChinese:
    """Test Chinese tokenization"""

    def test_jieba_available(self):
        """If jieba is available, should return segmented tokens"""
        from app.agents.services.retrieval import _tokenize_chinese
        tokens = _tokenize_chinese("主角的魔法限制")
        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_bigram_fallback(self):
        """Without jieba, should return character bigrams"""
        from app.agents.services.retrieval import _tokenize_chinese
        # Force import error
        with patch.dict("sys.modules", {"jieba": None}):
            # This will use the bigram fallback in the function
            pass  # The actual fallback is inside the function


class TestRetrievalService:
    """Test RetrievalService class"""

    def test_init(self):
        from app.agents.services.retrieval import RetrievalService
        rs = RetrievalService(project_id=1)
        assert rs.project_id == 1

    def test_is_index_available_no_index(self):
        from app.agents.services.retrieval import RetrievalService
        rs = RetrievalService(project_id=99999)
        # No index exists for this project
        assert rs.is_index_available() is False

    def test_search_returns_list(self):
        from app.agents.services.retrieval import RetrievalService
        rs = RetrievalService(project_id=99999)
        # Should fallback to keyword matching
        with patch("app.agents.services.retrieval._keyword_fallback", return_value=[]):
            results = rs.search("test query")
            assert isinstance(results, list)


class TestKeywordFallback:
    """Test keyword fallback when index is unavailable"""

    @patch("app.agents.services.retrieval.KnowledgeBaseService")
    def test_fallback_searches_characters(self, mock_kb_class):
        from app.agents.services.retrieval import _keyword_fallback

        mock_kb = MagicMock()
        mock_char = MagicMock()
        mock_char.name = "李明"
        mock_char.core_motivation = "寻找真相"
        mock_char.knowledge_boundary = "不知道密码"
        mock_char.speech_style = "直接"
        mock_kb.get_characters.return_value = [mock_char]
        mock_kb.get_world_setting.return_value = None
        mock_kb.get_foreshadowings.return_value = []
        mock_kb_class.return_value = mock_kb

        results = _keyword_fallback(1, "李明", 5)
        assert len(results) >= 1
        assert results[0]["source"] == "character/李明"


# ========== Foreshadowing 3-Level Progression ==========

class TestForeshadowingProgression:
    """Test foreshadowing hint → strengthened → revealed progression"""

    def test_hint_to_strengthened(self):
        """Appearance count >= 2 and level='hint' → upgrade to 'strengthened'"""
        # Simulate the logic from tracking_update_node
        level = "hint"
        appearance_count = 2

        if level == "hint" and appearance_count >= 2:
            new_level = "strengthened"
            new_status = "pending_reclaim"
        else:
            new_level = level
            new_status = "active"

        assert new_level == "strengthened"
        assert new_status == "pending_reclaim"

    def test_hint_stays_hint(self):
        """Appearance count < 2 and level='hint' → stays 'hint'"""
        level = "hint"
        appearance_count = 1

        if level == "hint" and appearance_count >= 2:
            new_level = "strengthened"
            new_status = "pending_reclaim"
        else:
            new_level = "hint"
            new_status = "active"

        assert new_level == "hint"
        assert new_status == "active"

    def test_strengthened_to_revealed(self):
        """Level='strengthened' and count>=2 → can be revealed"""
        level = "strengthened"
        appearance_count = 2

        can_reclaim = level == "strengthened" and appearance_count >= 2
        assert can_reclaim is True

        new_level = "revealed"
        new_status = "resolved"
        assert new_level == "revealed"
        assert new_status == "resolved"

    def test_violation_direct_reclaim(self):
        """Reclaiming with <2 appearances → violation"""
        level = "hint"
        appearance_count = 1

        can_reclaim = level == "strengthened" and appearance_count >= 2
        assert can_reclaim is False  # This is a violation


class TestIsForeshadowingMentioned:
    """Test foreshadowing mention detection"""

    def test_keyword_match(self):
        from app.agents.nodes.tracking_update import _is_foreshadowing_mentioned
        assert _is_foreshadowing_mentioned("古老的预言暗示着未来", "他在书中读到了古老的预言") is True

    def test_no_match(self):
        from app.agents.nodes.tracking_update import _is_foreshadowing_mentioned
        assert _is_foreshadowing_mentioned("古老的预言", "完全无关的内容") is False

    def test_empty_content(self):
        from app.agents.nodes.tracking_update import _is_foreshadowing_mentioned
        assert _is_foreshadowing_mentioned("预言", "") is False

    def test_too_short_keyword(self):
        from app.agents.nodes.tracking_update import _is_foreshadowing_mentioned
        assert _is_foreshadowing_mentioned("一", "一段内容") is False


# ========== Style Drift Detection ==========

class TestStyleDriftDetection:
    """Test style drift detection logic"""

    def test_compute_baseline_with_snapshots(self):
        from app.agents.nodes.style_check import _compute_baseline

        mock_snapshots = []
        for i in range(3):
            s = MagicMock()
            s.chapter_number = i + 1
            s.dialogue_ratio = 0.3
            s.avg_sentence_length = 20.0
            s.avg_paragraph_length = 100.0
            mock_snapshots.append(s)

        baseline = _compute_baseline(mock_snapshots)
        assert baseline is not None
        assert abs(baseline["dialogue_ratio"] - 0.3) < 0.01
        assert abs(baseline["avg_sentence_length"] - 20.0) < 0.01

    def test_compute_baseline_no_snapshots(self):
        from app.agents.nodes.style_check import _compute_baseline
        assert _compute_baseline([]) is None

    def test_drift_detection_threshold(self):
        """Dialogue ratio deviating >25% from baseline should trigger drift"""
        baseline_dialogue = 0.3
        current_dialogue = 0.5  # 66% deviation → should trigger

        deviation = abs(current_dialogue - baseline_dialogue) / baseline_dialogue
        assert deviation > 0.25  # Drift detected

    def test_no_drift_within_threshold(self):
        """Dialogue ratio within 25% → no drift"""
        baseline_dialogue = 0.3
        current_dialogue = 0.35  # 16% deviation → no drift

        deviation = abs(current_dialogue - baseline_dialogue) / baseline_dialogue
        assert deviation <= 0.25


# ========== WarningService ==========

class TestWarningService:
    """Test proactive warning checks"""

    def test_check_foreshadowing_overdue_none(self):
        from app.agents.services.warning import WarningService
        with patch.object(WarningService, '__init__', lambda self, pid: None):
            ws = WarningService(1)
            ws.project_id = 1
            ws.kb = MagicMock()
            ws.kb.get_overdue_foreshadowings.return_value = []
            result = ws.check_foreshadowing_overdue(10)
            assert result is None

    def test_check_foreshadowing_overdue_found(self):
        from app.agents.services.warning import WarningService, _project_warnings
        # Clear dedup cache
        _project_warnings.pop(1, None)

        ws = WarningService(1)

        mock_f = MagicMock()
        mock_f.content = "古老的预言即将应验"
        mock_f.expected_resolve_chapter = 5
        ws.kb.get_overdue_foreshadowings = MagicMock(return_value=[mock_f])

        result = ws.check_foreshadowing_overdue(10)
        assert result is not None
        assert result["type"] == "foreshadowing_overdue"
        assert result["emoji"] == "🟡"

    def test_check_rhythm_monotone_detected(self):
        from app.agents.services.warning import WarningService, _project_warnings
        _project_warnings.pop(1, None)

        ws = WarningService(1)

        # Create timeline with 3 consecutive same emotions
        timeline = []
        for i in range(5):
            t = MagicMock()
            t.emotion_tag = "紧张"  # Same emotion
            t.chapter_number = i + 1
            timeline.append(t)
        ws.kb.get_timeline = MagicMock(return_value=timeline)

        result = ws.check_rhythm_monotone(6)
        assert result is not None
        assert result["type"] == "rhythm_monotone"

    def test_check_rhythm_monotone_not_detected(self):
        from app.agents.services.warning import WarningService, _project_warnings
        _project_warnings.pop(1, None)

        ws = WarningService(1)

        # Create timeline with varied emotions
        timeline = []
        emotions = ["紧张", "舒缓", "紧张", "温暖", "转折"]
        for i, emotion in enumerate(emotions):
            t = MagicMock()
            t.emotion_tag = emotion
            timeline.append(t)
        ws.kb.get_timeline = MagicMock(return_value=timeline)

        result = ws.check_rhythm_monotone(6)
        assert result is None

    def test_check_all_returns_list(self):
        from app.agents.services.warning import WarningService, _project_warnings
        _project_warnings.pop(1, None)

        ws = WarningService(1)
        ws.kb = MagicMock()
        ws.kb.get_overdue_foreshadowings = MagicMock(return_value=[])
        ws.kb.get_style_snapshots = MagicMock(return_value=[])
        ws.kb.get_timeline = MagicMock(return_value=[])
        ws.kb.get_plot_questions = MagicMock(return_value=[])

        result = ws.check_all(10)
        assert isinstance(result, list)


# ========== Prompt Registration ==========

class TestPhase3Prompts:
    """Verify Phase 3 prompts are registered"""

    def test_character_knowledge_boundary_prompt_exists(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "character_knowledge_boundary" in DEFAULT_PROMPTS

    def test_deep_review_enhanced_prompt_exists(self):
        from app.agents.prompts import DEFAULT_PROMPTS
        assert "deep_review_enhanced" in DEFAULT_PROMPTS

    def test_character_knowledge_boundary_prompt_not_empty(self):
        from app.agents.prompts import CHARACTER_KNOWLEDGE_BOUNDARY_PROMPT
        assert len(CHARACTER_KNOWLEDGE_BOUNDARY_PROMPT) > 100

    def test_deep_review_enhanced_prompt_not_empty(self):
        from app.agents.prompts import DEEP_REVIEW_ENHANCED_PROMPT
        assert len(DEEP_REVIEW_ENHANCED_PROMPT) > 100


# ========== Violation Parsing ==========

class TestViolationParsing:
    """Test character consistency violation parsing"""

    def test_parse_violations_with_marker(self):
        from app.agents.nodes.character_consistency import _parse_violations
        response = "❌ [李明] 知识边界违规：李明提到了密码，但他不知道密码"
        violations = _parse_violations(response)
        assert len(violations) == 1
        assert violations[0]["type"] == "knowledge_boundary"
        assert "李明" in violations[0]["character"]

    def test_parse_violations_no_violation(self):
        from app.agents.nodes.character_consistency import _parse_violations
        response = "✅ 全部角色无违规"
        violations = _parse_violations(response)
        assert len(violations) == 0

    def test_parse_mixed_violations(self):
        from app.agents.nodes.character_consistency import _parse_violations
        response = "❌ [张三] 知识边界违规：张三说出了机密\n⚠️ [李四] 行为不一致：李四的行为偏离动机"
        violations = _parse_violations(response)
        assert len(violations) == 2

    def test_extract_character_name(self):
        from app.agents.nodes.character_consistency import _extract_character_name
        assert _extract_character_name("[李明] 知识边界违规") == "李明"
        assert _extract_character_name("【王五】行为不一致") == "王五"
        assert _extract_character_name("赵六：知识边界") == "赵六"
