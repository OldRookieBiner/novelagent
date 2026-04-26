"""Tests for chapter rewrite node"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.agents.nodes.rewrite import rewrite_chapter_node, rewrite_with_retry


class TestRewriteChapterNode:
    """Tests for rewrite_chapter_node function"""

    @pytest.mark.asyncio
    async def test_rewrite_returns_content(self):
        """Should return rewritten content"""
        mock_llm = Mock()
        mock_llm.chat = AsyncMock(return_value="这是重写后的章节内容...")

        state = {
            "collected_info": {"novelType": "玄幻"},
            "outline_characters": [{"name": "林风", "personality": "坚韧"}]
        }
        chapter_outline = {
            "title": "第一章",
            "scene": "山村",
            "characters": "林风",
            "plot": "少年觉醒",
            "conflict": "内外交困",
            "hook": "神秘老人出现"
        }
        original_content = "原始章节内容..."
        review_feedback = "情节过于平淡，需要增加冲突"

        result = await rewrite_chapter_node(
            state,
            chapter_outline,
            original_content,
            review_feedback,
            mock_llm
        )

        assert result == "这是重写后的章节内容..."
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_rewrite_uses_characters(self):
        """Should use character information in rewrite"""
        mock_llm = Mock()
        mock_llm.chat = AsyncMock(return_value="重写内容")

        state = {
            "collected_info": {},
            "outline_characters": [
                {"name": "张三", "personality": "豪爽"},
                {"name": "李四", "personality": "阴险"}
            ]
        }
        chapter_outline = {"title": "测试章节"}
        original_content = "原始内容"
        review_feedback = "反馈"

        await rewrite_chapter_node(
            state,
            chapter_outline,
            original_content,
            review_feedback,
            mock_llm
        )

        # 验证调用参数包含人物信息
        call_args = mock_llm.chat.call_args
        prompt = call_args[0][0][0]["content"]
        assert "张三" in prompt
        assert "李四" in prompt

    @pytest.mark.asyncio
    async def test_rewrite_falls_back_to_protagonist(self):
        """Should fall back to protagonist when no character outlines"""
        mock_llm = Mock()
        mock_llm.chat = AsyncMock(return_value="重写内容")

        state = {
            "collected_info": {
                "protagonist": "主角名称",
                "customProtagonist": "自定义主角描述"
            },
            "outline_characters": []
        }
        chapter_outline = {"title": "测试章节"}
        original_content = "原始内容"
        review_feedback = "反馈"

        await rewrite_chapter_node(
            state,
            chapter_outline,
            original_content,
            review_feedback,
            mock_llm
        )

        call_args = mock_llm.chat.call_args
        prompt = call_args[0][0][0]["content"]
        assert "自定义主角描述" in prompt


class TestRewriteWithRetry:
    """Tests for rewrite_with_retry function"""

    @pytest.mark.asyncio
    async def test_pass_on_first_review(self):
        """Should pass without rewrite if first review passes"""
        mock_llm = Mock()
        mock_llm.chat = AsyncMock(return_value="""
【审核结果】通过
情节一致性：8/10
人物一致性：8/10
文笔质量：8/10
情感张力：8/10
AI味程度：2/10
【问题列表】无
【修改建议】无
---
""")

        state = {}
        chapter_outline = {"title": "测试章节"}
        original_content = "原始内容"

        result = await rewrite_with_retry(
            state,
            chapter_outline,
            original_content,
            mock_llm,
            max_retries=3
        )

        assert result["passed"] is True
        assert result["rewrite_count"] == 0
        assert result["content"] == original_content

    @pytest.mark.asyncio
    async def test_retry_until_pass(self):
        """Should retry until review passes"""
        call_count = [0]

        async def mock_chat(messages):
            call_count[0] += 1
            # 第一次审核不通过，第二次审核通过
            if call_count[0] == 1:
                return """
【审核结果】不通过
情节一致性：5/10
人物一致性：8/10
文笔质量：8/10
情感张力：8/10
AI味程度：2/10
【问题列表】情节问题
【修改建议】增加冲突
---
"""
            elif call_count[0] == 2:
                return "重写后的内容"
            else:
                return """
【审核结果】通过
情节一致性：8/10
人物一致性：8/10
文笔质量：8/10
情感张力：8/10
AI味程度：2/10
【问题列表】无
【修改建议】无
---
"""

        mock_llm = Mock()
        mock_llm.chat = mock_chat

        state = {}
        chapter_outline = {"title": "测试章节"}
        original_content = "原始内容"

        result = await rewrite_with_retry(
            state,
            chapter_outline,
            original_content,
            mock_llm,
            max_retries=3
        )

        assert result["passed"] is True
        assert result["rewrite_count"] == 1
        assert result["content"] == "重写后的内容"

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Should fail after max retries"""
        mock_llm = Mock()
        mock_llm.chat = AsyncMock(return_value="""
【审核结果】不通过
情节一致性：5/10
人物一致性：8/10
文笔质量：8/10
情感张力：8/10
AI味程度：2/10
【问题列表】情节问题
【修改建议】增加冲突
---
""")

        state = {}
        chapter_outline = {"title": "测试章节"}
        original_content = "原始内容"

        result = await rewrite_with_retry(
            state,
            chapter_outline,
            original_content,
            mock_llm,
            max_retries=2
        )

        assert result["passed"] is False
        assert result["rewrite_count"] == 2


class TestRewriteNodeIntegration:
    """Integration tests for rewrite node"""

    @pytest.mark.asyncio
    async def test_rewrite_node_structure(self):
        """Test that rewrite_node has correct signature"""
        from app.agents.nodes.rewrite import rewrite_node
        import inspect

        # 验证是异步函数
        assert inspect.iscoroutinefunction(rewrite_node)

        # 验证参数签名
        sig = inspect.signature(rewrite_node)
        params = list(sig.parameters.keys())
        assert "state" in params

    @pytest.mark.asyncio
    async def test_rewrite_node_updates_state(self):
        """Test that rewrite_node properly updates state"""
        from app.agents.nodes.rewrite import rewrite_node

        mock_llm = Mock()
        mock_llm.chat = AsyncMock(return_value="重写后的内容")

        state = {
            "collected_info": {"novelType": "玄幻"},
            "outline_characters": [],
            "review_result": {
                "raw_response": "需要修改情节",
                "suggestions": "增加冲突"
            },
            "current_chapter": 2,
            "written_chapters": [
                {"chapter_number": 1, "content": "第一章内容"},
                {"chapter_number": 2, "content": "原始第二章内容"}
            ],
            "chapter_outlines": [
                {"chapter_number": 1, "title": "第一章"},
                {"chapter_number": 2, "title": "第二章", "scene": "测试"}
            ],
            "rewrite_count": 0
        }

        with patch('app.agents.nodes.rewrite.get_llm_from_state_async', return_value=mock_llm):
            result = await rewrite_node(state)

            assert "written_chapters" in result
            assert result["rewrite_count"] == 1
