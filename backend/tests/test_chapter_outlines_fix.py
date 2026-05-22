# backend/tests/test_chapter_outlines_fix.py
# 验证章节大纲生成的根因修复：
# 1. 使用 generate_chapter_outlines_stream 而非完整 graph
# 2. progress 事件格式正确
# 3. done 事件包含 total 和 stage
# 4. 章节大纲写入数据库
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from app.agents.nodes.chapter_generation import parse_single_chapter_outline


def _make_mock_stream(chapters_data):
    """构造 mock 的流式生成器"""
    async def mock_stream(state, llm):
        for i, ch in enumerate(chapters_data, 1):
            yield {
                "type": "progress",
                "chapter_number": i,
                "total": len(chapters_data),
                "chapter": ch,
            }
        yield {
            "type": "done",
            "chapter_outlines": chapters_data,
        }
    return mock_stream


def _make_patches():
    """构造共享的 patch 上下文管理器列表"""
    return [
        patch("app.api.chapters.get_llm_from_state_async", return_value=MagicMock()),
        patch("app.api.chapters.get_project_for_user"),
        patch("app.api.chapters.get_outline_for_project"),
        patch("app.api.chapters.get_user_settings_or_raise"),
        patch("app.api.chapters.get_or_create_workflow_state"),
        patch("app.api.chapters.build_initial_state", return_value={"project_id": 1}),
    ]


class TestChapterOutlinesGeneration:
    """验证 create_chapter_outlines 端点修复后的行为"""

    @pytest.mark.asyncio
    async def test_uses_stream_function_not_full_graph(self):
        """章节大纲生成应使用 generate_chapter_outlines_stream，而非完整 graph"""
        chapters = [
            {"chapter_number": 1, "title": "第一章", "scene": "", "plot": ""},
            {"chapter_number": 2, "title": "第二章", "scene": "", "plot": ""},
            {"chapter_number": 3, "title": "第三章", "scene": "", "plot": ""},
        ]

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=_make_mock_stream(chapters)) as mock_gen:
            patches = _make_patches()
            for p in patches:
                p.start()
            try:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                # _stream_chapter_outlines_sse 使用 SessionLocal，需 mock
                mock_save_db = MagicMock()
                with patch("app.api.chapters.SessionLocal", return_value=mock_save_db):
                    from app.api.chapters import create_chapter_outlines

                    response = await create_chapter_outlines(
                        project_id=1,
                        request=None,
                        db=mock_db,
                        current_user=MagicMock()
                    )

                    from fastapi.responses import StreamingResponse
                    assert isinstance(response, StreamingResponse)

                    events = []
                    async for chunk in response.body_iterator:
                        events.append(chunk)

                    mock_gen.assert_called_once()
            finally:
                for p in patches:
                    p.stop()

    @pytest.mark.asyncio
    async def test_progress_events_format(self):
        """progress 事件应包含 chapter_number、total 和 chapter"""
        chapters = [
            {"chapter_number": 1, "title": "开篇", "scene": "城池", "plot": "故事开始"},
            {"chapter_number": 2, "title": "转折", "scene": "战场", "plot": "危机降临"},
        ]

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=_make_mock_stream(chapters)):
            patches = _make_patches()
            for p in patches:
                p.start()
            try:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_save_db = MagicMock()
                with patch("app.api.chapters.SessionLocal", return_value=mock_save_db):
                    from app.api.chapters import create_chapter_outlines

                    response = await create_chapter_outlines(
                        project_id=1,
                        request=None,
                        db=mock_db,
                        current_user=MagicMock()
                    )

                    events = []
                    async for chunk in response.body_iterator:
                        events.append(chunk)

                    progress_events = [e for e in events if "event: progress" in e]
                    assert len(progress_events) == 2

                    data_str = progress_events[0].split("data: ", 1)[1].strip()
                    data = json.loads(data_str)
                    assert data["chapter_number"] == 1
                    assert data["total"] == 2
                    assert data["chapter"]["chapter_number"] == 1
                    assert data["chapter"]["title"] == "开篇"
            finally:
                for p in patches:
                    p.stop()

    @pytest.mark.asyncio
    async def test_done_event_has_total_and_stage(self):
        """done 事件必须包含 total 和 stage 字段，不能是 undefined"""
        chapters = [
            {"chapter_number": 1, "title": "测试章", "scene": "", "plot": ""},
        ]

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=_make_mock_stream(chapters)):
            patches = _make_patches()
            for p in patches:
                p.start()
            try:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_save_db = MagicMock()
                with patch("app.api.chapters.SessionLocal", return_value=mock_save_db):
                    from app.api.chapters import create_chapter_outlines

                    response = await create_chapter_outlines(
                        project_id=1,
                        request=None,
                        db=mock_db,
                        current_user=MagicMock()
                    )

                    events = []
                    async for chunk in response.body_iterator:
                        events.append(chunk)

                    done_events = [e for e in events if "event: done" in e]
                    assert len(done_events) == 1

                    data_str = done_events[0].split("data: ", 1)[1].strip()
                    data = json.loads(data_str)
                    assert "total" in data, f"done 事件缺少 total 字段: {data}"
                    assert data["total"] == 1
                    assert "stage" in data, f"done 事件缺少 stage 字段: {data}"
                    assert data["stage"] == "chapter_outlines"
            finally:
                for p in patches:
                    p.stop()

    @pytest.mark.asyncio
    async def test_chapter_outlines_written_to_db(self):
        """章节大纲生成后应写入数据库（通过 SessionLocal 独立会话）"""
        added_chapters = []
        chapters = [
            {"chapter_number": 1, "title": "第一回", "scene": "A", "plot": "B"},
            {"chapter_number": 2, "title": "第二回", "scene": "C", "plot": "D"},
        ]

        def mock_add(obj):
            added_chapters.append(obj)

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=_make_mock_stream(chapters)):
            patches = _make_patches()
            for p in patches:
                p.start()
            try:
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = None

                # 模拟 SessionLocal 返回的独立会话
                mock_save_db = MagicMock()
                mock_save_db.add = mock_add

                with patch("app.api.chapters.SessionLocal", return_value=mock_save_db):
                    from app.api.chapters import create_chapter_outlines

                    response = await create_chapter_outlines(
                        project_id=1,
                        request=None,
                        db=mock_db,
                        current_user=MagicMock()
                    )

                    async for _ in response.body_iterator:
                        pass

                    # 验证 DB 写入（通过 SessionLocal 独立会话）
                    assert len(added_chapters) == 2
                    assert added_chapters[0].chapter_number == 1
                    assert added_chapters[0].title == "第一回"
                    assert added_chapters[1].chapter_number == 2
                    assert added_chapters[1].title == "第二回"
                    mock_save_db.commit.assert_called()
            finally:
                for p in patches:
                    p.stop()


class TestParseSingleChapterOutlineSceneTruncation:
    """验证 parse_single_chapter_outline 对 scene 字段的防御性截断"""

    def test_scene_truncation_when_over_500_chars(self):
        """scene 字段超过 500 字符时截断至 500"""
        long_scene = "一个很长的场景描述" * 100  # > 500 字符
        response = f"章节名：测试\n场景：{long_scene}\n情节：测试情节"
        result = parse_single_chapter_outline(response, 1)
        assert len(result["scene"]) <= 500, f"scene 长度 {len(result['scene'])} 超过 500"

    def test_scene_not_truncated_when_under_500_chars(self):
        """scene 字段未超过 500 字符时保持原样"""
        scene = "这是一段正常的场景描述"
        response = f"章节名：测试\n场景：{scene}\n情节：测试情节"
        result = parse_single_chapter_outline(response, 1)
        assert result["scene"] == scene

    def test_scene_empty_when_no_match(self):
        """无场景匹配时 scene 为空字符串"""
        response = "章节名：测试\n情节：只有情节没有场景"
        result = parse_single_chapter_outline(response, 1)
        assert result["scene"] == ""
