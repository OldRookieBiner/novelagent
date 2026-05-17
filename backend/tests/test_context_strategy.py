"""上下文策略测试"""
import pytest
from app.agents.context_strategy import (
    FulltextContentStrategy,
    HybridContentStrategy,
    SummaryContentStrategy,
    get_context_strategy,
)


class TestFulltextContentStrategy:
    def test_no_previous_chapters(self):
        """第一章没有前文"""
        strategy = FulltextContentStrategy()
        result = strategy.build_previous_context([], 1)
        assert "第一章" in result or "没有前文" in result

    def test_single_previous_chapter(self):
        """有一章前文"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "那天风很大。"},
        ]
        result = strategy.build_previous_context(chapters, 2)
        assert "起风了" in result
        assert "那天风很大" in result
        assert "第1章" in result

    def test_multiple_previous_chapters(self):
        """有多章前文"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 3)
        assert "第1章" in result
        assert "第2章" in result
        assert "风起" in result
        assert "雨落" in result

    def test_excludes_current_chapter(self):
        """不包含当前正在写的章节"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 2)
        assert "第1章" in result
        assert "第2章" not in result

    def test_skips_empty_content(self):
        """跳过没有内容的章节"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": ""},
        ]
        result = strategy.build_previous_context(chapters, 3)
        assert "第1章" in result
        assert "第2章" not in result


class TestGetContextStrategy:
    def test_short_novel_returns_fulltext(self):
        """短篇返回 Fulltext 策略"""
        strategy = get_context_strategy(50000)
        assert isinstance(strategy, FulltextContentStrategy)

    def test_medium_novel_returns_fulltext_for_now(self):
        """中篇暂时也返回 Fulltext（Phase 4 改为 Hybrid）"""
        strategy = get_context_strategy(200000)
        assert isinstance(strategy, FulltextContentStrategy)


class TestHybridContentStrategy:
    def test_no_previous_chapters(self):
        """第一章没有前文"""
        strategy = HybridContentStrategy(recent_count=3)
        result = strategy.build_previous_context([], 1)
        assert "没有前文" in result

    def test_all_recent_fulltext(self):
        """所有前章都在近章范围内，全部全文"""
        strategy = HybridContentStrategy(recent_count=3)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        outlines = [
            {"chapter_number": 1, "title": "起风了", "plot": "风吹过"},
            {"chapter_number": 2, "title": "雨来了", "plot": "雨倾盆"},
        ]
        result = strategy.build_previous_context(chapters, 3, outlines)
        assert "风起" in result
        assert "雨落" in result

    def test_distant_uses_outlines(self):
        """远章从 chapter_outlines 取概要，不取全文"""
        strategy = HybridContentStrategy(recent_count=1)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "很长的正文内容。"},
            {"chapter_number": 2, "title": "雨来了", "content": "也很长的正文。"},
            {"chapter_number": 3, "title": "雷鸣", "content": "雷声轰鸣。"},
        ]
        outlines = [
            {"chapter_number": 1, "title": "起风了", "plot": "大风席卷", "conflict": "人与自然", "hook": "风暴将至"},
            {"chapter_number": 2, "title": "雨来了", "plot": "暴雨如注", "conflict": "求生存"},
            {"chapter_number": 3, "title": "雷鸣", "plot": "雷电交加"},
        ]
        result = strategy.build_previous_context(chapters, 4, outlines)
        # 远章（1、2）只有概要，不出现全文
        assert "大风席卷" in result
        assert "很长的正文内容" not in result
        # 近章（3）有全文
        assert "雷声轰鸣" in result

    def test_distant_without_outlines_falls_back(self):
        """远章没有 chapter_outlines 时不输出概要"""
        strategy = HybridContentStrategy(recent_count=1)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 3, chapter_outlines=None)
        # 近章有全文
        assert "雨落" in result
        # 远章无 outlines 不输出概要段
        assert "前文概要" not in result

    def test_get_context_strategy_hybrid(self):
        """用户选择 hybrid 策略时返回 HybridContentStrategy"""
        strategy = get_context_strategy(100000, "hybrid")
        assert isinstance(strategy, HybridContentStrategy)

    def test_fulltext_ignores_chapter_outlines(self):
        """全文策略忽略 chapter_outlines 参数"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
        ]
        outlines = [{"chapter_number": 1, "plot": "不应该出现"}]
        result = strategy.build_previous_context(chapters, 2, outlines)
        assert "风起" in result
        assert "不应该出现" not in result


class TestSummaryContentStrategy:
    """摘要策略测试"""

    def setup_method(self):
        self.strategy = SummaryContentStrategy(recent_count=3)

    def test_first_chapter_returns_placeholder(self):
        """第一章没有前文"""
        result = self.strategy.build_previous_context(
            written_chapters=[],
            current_chapter=1,
        )
        assert "第一章" in result or "没有前文" in result

    def test_previous_arcs_summaries(self):
        """前面弧的概要应出现在上下文中"""
        arcs = [
            {"volume_number": 1, "arc_number": 1, "title": "初入江湖", "summary": "少年学艺", "chapter_count": 15},
            {"volume_number": 1, "arc_number": 2, "title": "门派试炼", "summary": "参加比武", "chapter_count": 20},
        ]
        written = [{"chapter_number": i, "content": f"第{i}章内容", "title": f"第{i}章"} for i in range(1, 25)]
        result = self.strategy.build_previous_context(
            written_chapters=written,
            current_chapter=25,
            arcs=arcs,
            chapter_summaries=[{"chapter_number": i, "summary": f"第{i}章摘要"} for i in range(1, 25)],
        )
        assert "前弧概要" in result
        assert "初入江湖" in result

    def test_current_arc_summaries(self):
        """当前弧已写章节摘要应出现"""
        arcs = [
            {"volume_number": 1, "arc_number": 1, "title": "初入江湖", "summary": "少年学艺", "chapter_count": 10},
        ]
        written = [{"chapter_number": i, "content": f"第{i}章内容", "title": f"第{i}章"} for i in range(1, 7)]
        chapter_summaries = [{"chapter_number": i, "summary": f"第{i}章摘要"} for i in range(1, 7)]
        result = self.strategy.build_previous_context(
            written_chapters=written,
            current_chapter=7,
            arcs=arcs,
            chapter_summaries=chapter_summaries,
        )
        assert "当前弧摘要" in result

    def test_recent_chapters_fulltext(self):
        """近3章应取全文"""
        arcs = [
            {"volume_number": 1, "arc_number": 1, "title": "弧1", "summary": "概要", "chapter_count": 20},
        ]
        written = [{"chapter_number": i, "content": f"第{i}章内容", "title": f"第{i}章"} for i in range(1, 10)]
        result = self.strategy.build_previous_context(
            written_chapters=written,
            current_chapter=10,
            arcs=arcs,
            chapter_summaries=[{"chapter_number": i, "summary": f"第{i}章摘要"} for i in range(1, 10)],
        )
        assert "近期全文" in result
        assert "第9章内容" in result

    def test_no_arcs_fallback_to_placeholder(self):
        """无弧数据时不应崩溃"""
        written = [{"chapter_number": 1, "content": "内容", "title": "第1章"}]
        result = self.strategy.build_previous_context(
            written_chapters=written,
            current_chapter=2,
            arcs=[],
        )
        assert isinstance(result, str)
