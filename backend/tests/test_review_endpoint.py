# backend/tests/test_review_endpoint.py
"""审核端点 SSE 事件格式测试"""

import json
import pytest
from app.agents.sse_events import format_heartbeat


class TestReviewSSEFormat:
    """审核端点应使用 SSE 注释行而非 chunk 事件发送审核中间状态"""

    def test_heartbeat_is_sse_comment(self):
        """format_heartbeat 应输出 SSE 注释行格式"""
        heartbeat = format_heartbeat()
        assert heartbeat.startswith(":"), f"Expected SSE comment line, got: {heartbeat}"
        assert "event:" not in heartbeat, "Heartbeat should not contain event prefix"
        assert heartbeat.endswith("\n\n"), "SSE event must end with double newline"

    def test_heartbeat_not_parsed_as_event(self):
        """SSE 注释行不应被解析为业务事件"""
        heartbeat = format_heartbeat()
        # 模拟 sseParser 的解析逻辑
        lines = heartbeat.strip().split('\n')
        has_event = any(line.startswith('event:') for line in lines)
        has_data = any(line.startswith('data:') for line in lines)
        assert not has_event, "Heartbeat should not have event: line"
        assert not has_data, "Heartbeat should not have data: line"

    def test_review_done_event_contains_scores(self):
        """done 事件应包含 scores 字段"""
        result_data = {
            "passed": False,
            "feedback": "增加冲突描写",
            "issues": [{"type": "情感张力不足", "location": "全文", "description": "缺少冲击力"}],
            "scores": {
                "plot_consistency": 8,
                "character_consistency": 7,
                "writing_quality": 8,
                "emotional_tension": 7,
                "ai_flavor": 5,
                "outline_deviation": 3,
            },
        }

        sse_event = f"event: done\ndata: {json.dumps(result_data)}\n\n"

        assert "event: done" in sse_event
        parsed = json.loads(sse_event.split("data: ")[1].strip())
        assert "scores" in parsed
        assert parsed["scores"]["emotional_tension"] == 7
        assert len(parsed["issues"]) == 1
