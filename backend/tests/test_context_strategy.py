"""上下文策略测试"""
import pytest
from app.agents.context_strategy import (
    FulltextContentStrategy,
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
