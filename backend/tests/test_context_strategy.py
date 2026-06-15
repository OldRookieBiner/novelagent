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

    def test_token_budget_truncates_older_chapters(self):
        """token_budget 不足时截断较早的章节（保留最近的）"""
        strategy = FulltextContentStrategy()
        # 创建大内容章节
        chapters = [
            {"chapter_number": 1, "title": "古老章", "content": "古" * 500},
            {"chapter_number": 2, "title": "中间章", "content": "中" * 500},
            {"chapter_number": 3, "title": "最近章", "content": "近" * 100},
        ]
        # 限制很小的预算，只能放下最近的章节
        result = strategy.build_previous_context(chapters, 4, token_budget=500)
        assert "最近章" in result
        # 古老章和中间章内容太长，被截断
        assert "古老章" not in result

    def test_token_budget_none_behaves_as_before(self):
        """token_budget=None 时行为与原来一致"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result_with_budget = strategy.build_previous_context(chapters, 3, token_budget=None)
        result_without = strategy.build_previous_context(chapters, 3)
        assert result_with_budget == result_without

    def test_token_budget_zero_returns_no_chapters(self):
        """token_budget=0 时无章节内容"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
        ]
        result = strategy.build_previous_context(chapters, 2, token_budget=0)
        assert "没有前文" in result


class TestGetContextStrategy:
    def test_short_novel_returns_fulltext(self):
        """短篇返回 Fulltext 策略"""
        strategy = get_context_strategy(50000)
        assert isinstance(strategy, FulltextContentStrategy)

    def test_medium_novel_returns_fulltext_for_now(self):
        """中篇暂时也返回 Fulltext（Phase 4 改为 Hybrid）"""
        strategy = get_context_strategy(200000)
        assert isinstance(strategy, FulltextContentStrategy)

    def test_get_context_strategy_hybrid(self):
        """用户选择 hybrid 策略时返回 HybridContentStrategy"""
        strategy = get_context_strategy(100000, "hybrid")
        assert isinstance(strategy, HybridContentStrategy)

    def test_get_context_strategy_summary(self):
        """用户选择 summary 策略时返回 SummaryContentStrategy"""
        strategy = get_context_strategy(100000, "summary")
        assert isinstance(strategy, SummaryContentStrategy)

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

    def test_token_budget_limits_fulltext(self):
        """token_budget 限制近章全文"""
        strategy = HybridContentStrategy(recent_count=5)
        # 创建大内容章节（每章 ~2000 token 估算）
        chapters = [
            {"chapter_number": i, "title": f"第{i}章", "content": "X" * 3000}
            for i in range(1, 6)
        ]
        # 60% 的预算用于近章全文，预算只够最近 1 章
        result = strategy.build_previous_context(chapters, 6, token_budget=4000)
        assert "第5章" in result
        # 较早的章节内容太长，被截断
        assert "第1章" not in result

    def test_token_budget_covers_outlines_after_fulltext(self):
        """有剩余预算时，远章概要也被包含"""
        strategy = HybridContentStrategy(recent_count=1)
        # 3 章：1 远 + 2 近范围（recent_count=1），但预算只够近章全文
        chapters = [
            {"chapter_number": 1, "title": "远章", "content": "A" * 2000},
            {"chapter_number": 2, "title": "中间章", "content": "B" * 2000},
            {"chapter_number": 3, "title": "近章", "content": "近"},
        ]
        outlines = [
            {"chapter_number": 1, "title": "远章", "plot": "远章概要信息"},
            {"chapter_number": 2, "title": "中间章", "plot": "中间概要"},
        ]
        # 预算只够近章全文（60%=约1200），远章用概要
        result = strategy.build_previous_context(chapters, 4, outlines, token_budget=2000)
        assert "近章" in result
        # 远章概要
        assert "远章概要信息" in result

    def test_covered_numbers_not_duplicated_in_outlines(self):
        """已有全文的章节不应在远章概要中重复出现"""
        strategy = HybridContentStrategy(recent_count=3)
        chapters = [
            {"chapter_number": 1, "title": "第一章", "content": "内容1"},
            {"chapter_number": 2, "title": "第二章", "content": "内容2"},
        ]
        outlines = [
            {"chapter_number": 1, "title": "第一章", "plot": "概要1"},
            {"chapter_number": 2, "title": "第二章", "plot": "概要2"},
        ]
        # 两章都是近章（recent_count=3），应该只有全文，不重复概要
        result = strategy.build_previous_context(chapters, 3, outlines)
        assert "内容1" in result
        assert "内容2" in result
        # 概要不应出现（因为已在全文中）
        assert "概要1" not in result
        assert "概要2" not in result


class TestSummaryContentStrategy:
    def test_no_previous_chapters(self):
        """第一章没有前文"""
        strategy = SummaryContentStrategy()
        result = strategy.build_previous_context([], 1)
        assert "没有前文" in result

    def test_recent_fulltext_only(self):
        """无弧纲时只输出近章全文"""
        strategy = SummaryContentStrategy(recent_count=2)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 3)
        assert "风起" in result
        assert "雨落" in result

    def test_with_arc_summary(self):
        """有弧纲时输出当前弧摘要"""
        strategy = SummaryContentStrategy(recent_count=1)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        arcs = [
            {"title": "风起篇", "start_chapter": 1, "end_chapter": 5, "summary": "风起云涌"},
        ]
        chapter_summaries = [
            {"chapter_number": 1, "summary": "风起概要"},
        ]
        result = strategy.build_previous_context(
            chapters, 3, arcs=arcs, chapter_summaries=chapter_summaries,
        )
        # 近章全文
        assert "雨落" in result
        # 当前弧摘要
        assert "风起云涌" in result
        # 弧内章节摘要（1不在covered_numbers中，因为它在fulltext中）
        # chapter 1 有全文，不会出现在摘要中

    def test_previous_arc_summary(self):
        """前弧摘要出现在结果中"""
        strategy = SummaryContentStrategy(recent_count=1)
        chapters = [
            {"chapter_number": 3, "title": "新篇", "content": "新内容"},
        ]
        arcs = [
            {"title": "前篇", "start_chapter": 1, "end_chapter": 2, "summary": "前篇概要"},
            {"title": "新篇", "start_chapter": 3, "end_chapter": 5, "summary": "新篇概要"},
        ]
        chapter_summaries = [
            {"chapter_number": 1, "summary": "第一章摘要"},
            {"chapter_number": 2, "summary": "第二章摘要"},
        ]
        result = strategy.build_previous_context(
            chapters, 4, arcs=arcs, chapter_summaries=chapter_summaries,
        )
        assert "前篇概要" in result
        assert "新篇概要" in result

    def test_token_budget_truncation(self):
        """token_budget 不足时截断"""
        strategy = SummaryContentStrategy(recent_count=2)
        chapters = [
            {"chapter_number": 1, "title": "远", "content": "X" * 2000},
            {"chapter_number": 2, "title": "近", "content": "近"},
        ]
        # 40% 预算用于全文，只有近章能放下
        result = strategy.build_previous_context(chapters, 3, token_budget=1000)
        assert "近" in result

    def test_chapter_summaries_exclude_covered(self):
        """已有全文的章节不出现在章节摘要中"""
        strategy = SummaryContentStrategy(recent_count=2)
        chapters = [
            {"chapter_number": 1, "title": "第一章", "content": "内容1"},
            {"chapter_number": 2, "title": "第二章", "content": "内容2"},
        ]
        arcs = [
            {"title": "篇一", "start_chapter": 1, "end_chapter": 5, "summary": "弧概要"},
        ]
        chapter_summaries = [
            {"chapter_number": 1, "summary": "第一章摘要"},
            {"chapter_number": 2, "summary": "第二章摘要"},
        ]
        result = strategy.build_previous_context(
            chapters, 3, arcs=arcs, chapter_summaries=chapter_summaries,
        )
        # 全文
        assert "内容1" in result
        assert "内容2" in result
        # 章节摘要不重复
        assert "第一章摘要" not in result
        assert "第二章摘要" not in result


class TestSelectStrategy:
    def test_user_override_fulltext(self):
        """用户指定 fulltext 时直接返回 Fulltext"""
        from app.agents.context_strategy import select_strategy
        strategy = select_strategy([], 1, 1000, strategy_name="fulltext")
        assert isinstance(strategy, FulltextContentStrategy)

    def test_user_override_hybrid(self):
        """用户指定 hybrid 时直接返回 Hybrid"""
        from app.agents.context_strategy import select_strategy
        strategy = select_strategy([], 1, 1000, strategy_name="hybrid")
        assert isinstance(strategy, HybridContentStrategy)

    def test_user_override_summary(self):
        """用户指定 summary 时直接返回 Summary"""
        from app.agents.context_strategy import select_strategy
        strategy = select_strategy([], 1, 1000, strategy_name="summary")
        assert isinstance(strategy, SummaryContentStrategy)

    def test_budget_enough_returns_fulltext(self):
        """预算充足时返回 Fulltext"""
        from app.agents.context_strategy import select_strategy
        chapters = [{"chapter_number": 1, "content": "短"}]
        strategy = select_strategy(chapters, 2, 100000)
        assert isinstance(strategy, FulltextContentStrategy)

    def test_budget_limited_with_outlines_returns_hybrid(self):
        """预算有限 + 有 chapter_outlines → Hybrid"""
        from app.agents.context_strategy import select_strategy
        chapters = [{"chapter_number": i, "content": "中" * 1000} for i in range(1, 10)]
        outlines = [{"chapter_number": i, "title": f"第{i}章"} for i in range(1, 10)]
        strategy = select_strategy(chapters, 10, 3000, chapter_outlines=outlines)
        assert isinstance(strategy, HybridContentStrategy)

    def test_budget_limited_no_outlines_returns_summary(self):
        """预算有限 + 无 chapter_outlines → Summary"""
        from app.agents.context_strategy import select_strategy
        chapters = [{"chapter_number": i, "content": "中" * 1000} for i in range(1, 10)]
        strategy = select_strategy(chapters, 10, 3000)
        assert isinstance(strategy, SummaryContentStrategy)

    def test_empty_chapters_returns_fulltext(self):
        """无前文章节时返回 Fulltext（全文策略会输出"没有前文"）"""
        from app.agents.context_strategy import select_strategy
        strategy = select_strategy([], 1, 10000)
        assert isinstance(strategy, FulltextContentStrategy)
