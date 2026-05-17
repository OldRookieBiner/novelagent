"""写后摘要节点测试"""

import pytest
from app.agents.prompts import DEFAULT_PROMPTS


class TestBuildSummaryPrompt:
    """摘要 prompt 构建测试"""

    def test_replaces_chapter_content_placeholder(self):
        from app.agents.nodes.chapter_summary import build_summary_prompt

        prompts = {"chapter_summary_generation": DEFAULT_PROMPTS["chapter_summary_generation"]}
        result = build_summary_prompt("主角在山村遇到了师父", prompts)
        assert "主角在山村遇到了师父" in result

    def test_falls_back_to_default_template(self):
        from app.agents.nodes.chapter_summary import build_summary_prompt

        result = build_summary_prompt("测试内容", {})
        assert "测试内容" in result

    def test_empty_prompts_uses_default(self):
        from app.agents.nodes.chapter_summary import build_summary_prompt

        # 空 prompts dict 应回退到 DEFAULT_PROMPTS
        result = build_summary_prompt("测试内容", {})
        assert "200" in result  # 默认模板包含"200字以内"


class TestChapterSummaryNodeEdgeCases:
    """摘要节点边界条件测试（不测试 LLM 调用）"""

    def test_no_written_chapters_returns_empty(self):
        """无已写章节应返回空摘要列表"""
        from app.agents.nodes.chapter_summary import _get_target_chapter_num

        # current_chapter=1 表示还没写任何章节
        assert _get_target_chapter_num([], current_chapter=1) is None

    def test_current_chapter_1_means_no_chapters_written(self):
        """current_chapter=1 时 target 为 0，无摘要"""
        from app.agents.nodes.chapter_summary import _get_target_chapter_num

        result = _get_target_chapter_num(
            [{"chapter_number": 1, "content": "内容"}],
            current_chapter=1,
        )
        assert result is None

    def test_current_chapter_2_means_chapter_1_written(self):
        """current_chapter=2 时应摘要第1章"""
        from app.agents.nodes.chapter_summary import _get_target_chapter_num

        result = _get_target_chapter_num(
            [{"chapter_number": 1, "content": "内容"}],
            current_chapter=2,
        )
        assert result == 1
