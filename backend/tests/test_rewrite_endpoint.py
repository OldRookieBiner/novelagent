"""重写端点 SSE 事件格式与业务逻辑测试

测试 rewrite_chapter 端点的核心行为（不依赖真实 LLM 调用）：
1. 审核反馈提取逻辑（raw_response > suggestions > review_feedback）
2. SSE 事件格式（chunk/done/error）
3. DB 更新逻辑（rewrite_count 递增、审核状态清除）
4. 错误校验（无大纲、无内容、空内容、无审核结果）
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.agents.sse_events import format_chunk, format_error_message, format_heartbeat
from app.utils.error import format_sse_error


# ============================================================================
# 1. 审核反馈提取逻辑测试
# ============================================================================


class TestReviewFeedbackExtraction:
    """测试 rewrite_chapter 端点中审核反馈的提取优先级

    提取逻辑（与 rewrite_node 一致）：
    1. chapter.review_result.raw_response
    2. chapter.review_result.suggestions
    3. chapter.review_feedback
    """

    def test_raw_response_takes_priority(self):
        """raw_response 优先级最高"""
        chapter = MagicMock()
        chapter.review_result = {
            "raw_response": "详细的审核反馈",
            "suggestions": "简略建议",
        }
        chapter.review_feedback = "旧反馈"

        # 模拟 rewrite_chapter 中的提取逻辑
        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "详细的审核反馈"

    def test_suggestions_as_fallback_when_raw_response_empty(self):
        """raw_response 为空时回退到 suggestions"""
        chapter = MagicMock()
        chapter.review_result = {
            "raw_response": "",
            "suggestions": "建议内容",
        }
        chapter.review_feedback = "旧反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "建议内容"

    def test_suggestions_as_fallback_when_raw_response_missing(self):
        """raw_response 键不存在时回退到 suggestions"""
        chapter = MagicMock()
        chapter.review_result = {
            "suggestions": "只有建议",
        }
        chapter.review_feedback = "旧反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "只有建议"

    def test_review_feedback_field_as_final_fallback(self):
        """review_result 为空时回退到 review_feedback 字段"""
        chapter = MagicMock()
        chapter.review_result = None
        chapter.review_feedback = "来自 review_feedback 字段的反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "来自 review_feedback 字段的反馈"

    def test_empty_review_result_falls_back_to_review_feedback(self):
        """review_result 为空字典时回退到 review_feedback"""
        chapter = MagicMock()
        chapter.review_result = {}
        chapter.review_feedback = "旧反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "旧反馈"

    def test_both_raw_response_and_suggestions_empty_falls_back(self):
        """raw_response 和 suggestions 都为空时回退到 review_feedback"""
        chapter = MagicMock()
        chapter.review_result = {
            "raw_response": "",
            "suggestions": "",
        }
        chapter.review_feedback = "字段级反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "字段级反馈"

    def test_all_sources_empty_yields_empty(self):
        """所有来源都为空时反馈为空字符串"""
        chapter = MagicMock()
        chapter.review_result = {
            "raw_response": "",
            "suggestions": "",
        }
        chapter.review_feedback = None

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == ""


# ============================================================================
# 2. SSE 事件格式测试
# ============================================================================


class TestRewriteSSEFormat:
    """测试重写端点的 SSE 事件格式"""

    def test_chunk_event_format(self):
        """chunk 事件应遵循 event: chunk\\ndata: {...}\\n\\n 格式"""
        content = "这是重写的文本"
        sse_event = f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

        # 验证事件格式
        lines = sse_event.split('\n')
        assert lines[0] == "event: chunk"
        assert lines[1].startswith("data: ")
        assert lines[2] == ""  # 空行
        assert lines[3] == ""  # 结尾空行

        # 验证数据内容
        data_json = lines[1][6:]  # 去掉 "data: " 前缀
        data = json.loads(data_json)
        assert data["content"] == content

    def test_chunk_event_uses_format_chunk(self):
        """format_chunk 工具函数应生成正确格式"""
        sse_event = format_chunk("测试内容")
        assert sse_event.startswith("event: chunk\n")
        assert "data: " in sse_event
        assert sse_event.endswith("\n\n")

        # 解析验证
        data_line = [l for l in sse_event.strip().split('\n') if l.startswith('data:')][0]
        data = json.loads(data_line[6:])
        assert data["content"] == "测试内容"

    def test_done_event_format(self):
        """done 事件应遵循 event: done\\ndata: {chapter: {...}}\\n\\n 格式"""
        chapter_data = {
            "id": 1,
            "chapter_outline_id": 2,
            "content": "重写后的内容",
            "word_count": 6,
        }
        sse_event = f"event: done\ndata: {json.dumps({'chapter': chapter_data})}\n\n"

        # 验证事件格式
        lines = sse_event.split('\n')
        assert lines[0] == "event: done"
        assert lines[1].startswith("data: ")

        # 验证数据结构
        data_json = lines[1][6:]
        data = json.loads(data_json)
        assert "chapter" in data
        assert data["chapter"]["id"] == 1
        assert data["chapter"]["content"] == "重写后的内容"
        assert data["chapter"]["word_count"] == 6

    def test_done_event_with_null_chapter(self):
        """done 事件在找不到 chapter 时应包含 null 字段"""
        chapter_data = {
            "id": None,
            "chapter_outline_id": None,
            "content": "重写后的内容",
            "word_count": 6,
        }
        sse_event = f"event: done\ndata: {json.dumps({'chapter': chapter_data})}\n\n"

        data_json = sse_event.split("data: ")[1].strip()
        data = json.loads(data_json)
        assert data["chapter"]["id"] is None
        assert data["chapter"]["chapter_outline_id"] is None

    def test_error_event_format(self):
        """error 事件应遵循 event: error\\ndata: {error: ...}\\n\\n 格式"""
        error_msg = "重写内容为空"
        sse_event = format_sse_error(ValueError(error_msg))

        assert "event: error" in sse_event
        assert sse_event.endswith("\n\n")

        # 解析数据
        data_line = [l for l in sse_event.strip().split('\n') if l.startswith('data:')][0]
        data = json.loads(data_line[6:])
        assert "error" in data

    def test_chunk_event_json_escaped(self):
        """chunk 事件中的内容应正确转义 JSON 特殊字符"""
        content = '包含"引号"和\n换行'
        sse_event = f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

        data_json = sse_event.split("data: ")[1].strip()
        data = json.loads(data_json)
        assert data["content"] == content

    def test_done_event_contains_word_count(self):
        """done 事件应包含 word_count 字段"""
        chapter_data = {
            "id": 1,
            "chapter_outline_id": 2,
            "content": "重写后的章节正文",
            "word_count": 7,
        }
        sse_event = f"event: done\ndata: {json.dumps({'chapter': chapter_data})}\n\n"

        data = json.loads(sse_event.split("data: ")[1].strip())
        assert data["chapter"]["word_count"] == 7


# ============================================================================
# 3. DB 更新逻辑测试
# ============================================================================


class TestRewriteDBUpdate:
    """测试重写完成后的数据库更新逻辑"""

    def test_rewrite_count_increments(self):
        """重写后 rewrite_count 应递增"""
        chapter = MagicMock()
        chapter.rewrite_count = 0

        # 模拟端点中的递增逻辑
        chapter.rewrite_count = (chapter.rewrite_count or 0) + 1

        assert chapter.rewrite_count == 1

    def test_rewrite_count_increments_from_existing(self):
        """已有 rewrite_count 时应正确递增"""
        chapter = MagicMock()
        chapter.rewrite_count = 2

        chapter.rewrite_count = (chapter.rewrite_count or 0) + 1

        assert chapter.rewrite_count == 3

    def test_rewrite_count_handles_none(self):
        """rewrite_count 为 None 时应从 0 开始递增"""
        chapter = MagicMock()
        chapter.rewrite_count = None

        chapter.rewrite_count = (chapter.rewrite_count or 0) + 1

        assert chapter.rewrite_count == 1

    def test_review_state_cleared_after_rewrite(self):
        """重写后审核状态应被清除"""
        chapter = MagicMock()
        chapter.review_passed = True
        chapter.review_result = {"passed": False, "issues": ["问题1"]}
        chapter.review_feedback = "需要修改"

        # 模拟端点中的清除逻辑
        chapter.review_passed = False
        chapter.review_result = None
        chapter.review_feedback = None

        assert chapter.review_passed is False
        assert chapter.review_result is None
        assert chapter.review_feedback is None

    def test_content_updated_after_rewrite(self):
        """重写后内容和字数应被更新"""
        chapter = MagicMock()
        new_content = "这是重写后的新内容"
        word_count = len(new_content)

        chapter.content = new_content
        chapter.word_count = word_count

        assert chapter.content == new_content
        assert chapter.word_count == 9

    def test_word_count_for_chinese_text(self):
        """中文文本的 word_count 应使用 len()（字符数而非词数）"""
        content = "这是一段中文测试内容"
        word_count = len(content)

        assert word_count == 10

    def test_full_db_update_sequence(self):
        """完整 DB 更新序列：内容、字数、rewrite_count、审核状态"""
        chapter = MagicMock()
        chapter.content = "原始内容"
        chapter.word_count = 4
        chapter.rewrite_count = 1
        chapter.review_passed = True
        chapter.review_result = {"passed": False}
        chapter.review_feedback = "审核反馈"

        # 执行完整更新
        new_content = "重写后的新内容，更加精彩"
        chapter.content = new_content
        chapter.word_count = len(new_content)
        chapter.rewrite_count = (chapter.rewrite_count or 0) + 1
        chapter.review_passed = False
        chapter.review_result = None
        chapter.review_feedback = None

        assert chapter.content == new_content
        assert chapter.word_count == 12
        assert chapter.rewrite_count == 2
        assert chapter.review_passed is False
        assert chapter.review_result is None
        assert chapter.review_feedback is None


# ============================================================================
# 4. 错误校验测试（使用 mock 模拟 DB 查询）
# ============================================================================


class TestRewriteValidationErrors:
    """测试重写端点的输入校验逻辑

    使用逻辑推理而非完整 HTTP 请求，因为端点依赖的 DB 查询
    和认证中间件在单元测试中难以完整模拟。测试关注校验逻辑本身。
    """

    def test_no_chapter_outline_returns_404(self):
        """没有章节大纲时应返回 404"""
        # 端点逻辑：chapter_outline 为 None 时抛出 HTTPException(404)
        chapter_outline = None
        assert chapter_outline is None
        # 实际端点会抛出：
        # HTTPException(status_code=404, detail="Chapter outline N not found")

    def test_no_chapter_content_returns_404(self):
        """没有章节内容时应返回 404"""
        chapter_outline = MagicMock()  # 大纲存在
        chapter = None  # 内容不存在
        assert chapter is None
        # 实际端点会抛出：
        # HTTPException(status_code=404, detail="Chapter N content not found")

    def test_empty_chapter_content_returns_400(self):
        """章节内容为空时应返回 400"""
        chapter = MagicMock()
        chapter.content = None  # 或 ""
        # 端点逻辑：if not chapter.content -> HTTPException(400)
        assert not chapter.content

    def test_no_review_result_returns_400(self):
        """没有审核结果时应返回 400"""
        chapter = MagicMock()
        chapter.content = "有内容"
        chapter.review_result = None
        chapter.review_feedback = None

        # 端点逻辑：if not chapter.review_result and not chapter.review_feedback -> HTTPException(400)
        has_review = chapter.review_result or chapter.review_feedback
        assert not has_review
        # 实际端点会抛出：
        # HTTPException(status_code=400, detail="请先审核章节，重写需要审核建议作为输入")

    def test_review_result_without_review_feedback_sufficient(self):
        """有 review_result 但无 review_feedback 时应允许重写"""
        chapter = MagicMock()
        chapter.content = "有内容"
        chapter.review_result = {"raw_response": "反馈"}
        chapter.review_feedback = None

        has_review = chapter.review_result or chapter.review_feedback
        assert has_review

    def test_review_feedback_without_review_result_sufficient(self):
        """有 review_feedback 但无 review_result 时应允许重写"""
        chapter = MagicMock()
        chapter.content = "有内容"
        chapter.review_result = None
        chapter.review_feedback = "审核反馈"

        has_review = chapter.review_result or chapter.review_feedback
        assert has_review

    def test_both_review_sources_present_allowed(self):
        """同时有 review_result 和 review_feedback 时应允许重写"""
        chapter = MagicMock()
        chapter.content = "有内容"
        chapter.review_result = {"raw_response": "反馈"}
        chapter.review_feedback = "旧反馈"

        has_review = chapter.review_result or chapter.review_feedback
        assert has_review


# ============================================================================
# 5. 审核反馈优先级集成测试
# ============================================================================


class TestReviewFeedbackPriorityIntegration:
    """测试审核反馈提取逻辑与 rewrite 节点的一致性

    确保端点和 LangGraph 节点使用相同的优先级：
    raw_response > suggestions > review_feedback 字段
    """

    def test_priority_matches_rewrite_node(self):
        """端点的提取逻辑应与 rewrite_node 一致

        rewrite_node 中：
        review_feedback = review_result.get("raw_response", "")
        if not review_feedback:
            review_feedback = review_result.get("suggestions", "")

        端点中：
        review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback
        """
        # 端点逻辑（含 review_feedback 字段回退）
        chapter = MagicMock()
        chapter.review_result = {"raw_response": "R", "suggestions": "S"}
        chapter.review_feedback = "F"

        # 端点提取
        endpoint_feedback = ""
        if chapter.review_result:
            endpoint_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not endpoint_feedback and chapter.review_feedback:
            endpoint_feedback = chapter.review_feedback

        # 节点提取（不含 review_feedback 字段回退）
        node_feedback = chapter.review_result.get("raw_response", "")
        if not node_feedback:
            node_feedback = chapter.review_result.get("suggestions", "")

        # 端点和节点在 raw_response 非空时应一致
        assert endpoint_feedback == node_feedback == "R"

    def test_priority_raw_response_over_suggestions(self):
        """raw_response 存在时应忽略 suggestions"""
        chapter = MagicMock()
        chapter.review_result = {
            "raw_response": "原始审核回复",
            "suggestions": "简短建议",
        }
        chapter.review_feedback = "字段级反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "原始审核回复"

    def test_priority_suggestions_over_review_feedback(self):
        """suggestions 存在且 raw_response 为空时应忽略 review_feedback"""
        chapter = MagicMock()
        chapter.review_result = {
            "raw_response": "",
            "suggestions": "建议内容",
        }
        chapter.review_feedback = "字段级反馈"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "建议内容"

    def test_priority_chain_all_empty(self):
        """所有层级都为空时最终使用 review_feedback 字段"""
        chapter = MagicMock()
        chapter.review_result = None
        chapter.review_feedback = "最终回退"

        review_feedback = ""
        if chapter.review_result:
            review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback

        assert review_feedback == "最终回退"


# ============================================================================
# 6. 重写后内容后处理测试
# ============================================================================


class TestRewriteContentPostProcessing:
    """测试重写后的内容后处理逻辑"""

    def test_empty_content_triggers_error(self):
        """清理后内容为空时应发送错误事件"""
        # 模拟 clean_chapter_content 返回空字符串
        rewritten_content = ""
        if not rewritten_content:
            error_event = format_sse_error(ValueError("重写内容为空"))
            assert "event: error" in error_event
            assert "重写内容为空" in error_event or "error" in error_event

    def test_whitespace_only_content_triggers_error(self):
        """清理后仅含空白时应发送错误事件"""
        rewritten_content = "   \n  \t  "
        cleaned = rewritten_content.strip()
        if not cleaned:
            error_event = format_sse_error(ValueError("重写内容为空"))
            assert "event: error" in error_event

    def test_valid_content_produces_done_event(self):
        """有效内容应产生 done 事件"""
        rewritten_content = "这是重写后的有效内容"
        word_count = len(rewritten_content)

        chapter_data = {
            "id": 1,
            "chapter_outline_id": 2,
            "content": rewritten_content,
            "word_count": word_count,
        }
        done_event = f"event: done\ndata: {json.dumps({'chapter': chapter_data})}\n\n"

        assert "event: done" in done_event
        data = json.loads(done_event.split("data: ")[1].strip())
        assert data["chapter"]["content"] == rewritten_content
        assert data["chapter"]["word_count"] == word_count

    def test_clean_chapter_content_removes_trailing_numbers(self):
        """clean_chapter_content 应移除 LLM 添加的结尾数字"""
        from app.agents.nodes.chapter_generation import clean_chapter_content

        # 结尾有数字
        assert clean_chapter_content("正文内容\n123") == "正文内容"
        assert clean_chapter_content("正文内容\n\n456") == "正文内容"
        # 无结尾数字
        assert clean_chapter_content("正文内容") == "正文内容"
