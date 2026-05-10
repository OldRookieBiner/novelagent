# backend/tests/test_chapter_outlines_fix.py
# 验证章节大纲生成的根因修复：
# 1. 使用 generate_chapter_outlines_stream 而非完整 graph
# 2. progress 事件格式正确
# 3. done 事件包含 total 和 stage
# 4. 章节大纲写入数据库
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


class TestChapterOutlinesGeneration:
    """验证 create_chapter_outlines 端点修复后的行为"""

    @pytest.mark.asyncio
    async def test_uses_stream_function_not_full_graph(self):
        """章节大纲生成应使用 generate_chapter_outlines_stream，而非完整 graph"""
        from app.agents.nodes.chapter_generation import generate_chapter_outlines_stream

        # 构造 mock 的流式生成器
        async def mock_stream(state, llm):
            yield {
                "type": "progress",
                "chapter_number": 1,
                "total": 3,
                "chapter": {"chapter_number": 1, "title": "第一章", "scene": "", "plot": ""},
            }
            yield {
                "type": "progress",
                "chapter_number": 2,
                "total": 3,
                "chapter": {"chapter_number": 2, "title": "第二章", "scene": "", "plot": ""},
            }
            yield {
                "type": "progress",
                "chapter_number": 3,
                "total": 3,
                "chapter": {"chapter_number": 3, "title": "第三章", "scene": "", "plot": ""},
            }
            yield {
                "type": "done",
                "chapter_outlines": [
                    {"chapter_number": 1, "title": "第一章"},
                    {"chapter_number": 2, "title": "第二章"},
                    {"chapter_number": 3, "title": "第三章"},
                ],
            }

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=mock_stream) as mock_gen:
            with patch("app.api.chapters.get_llm_from_state_async", return_value=MagicMock()):
                with patch("app.api.chapters.get_project_for_user"):
                    with patch("app.api.chapters.get_outline_for_project"):
                        with patch("app.api.chapters.get_user_settings_or_raise"):
                            with patch("app.api.chapters.get_or_create_workflow_state"):
                                with patch("app.api.chapters.build_initial_state", return_value={"project_id": 1}):
                                    # 模拟数据库（无已存在的章节大纲）
                                    mock_db = MagicMock()
                                    mock_db.query.return_value.filter.return_value.first.return_value = None

                                    # 模拟 FastAPI 依赖注入
                                    with patch("app.api.chapters.get_db", return_value=iter([mock_db])):
                                        with patch("app.api.chapters.get_current_user", return_value=MagicMock()):
                                            from app.api.chapters import create_chapter_outlines
                                            from fastapi import Request

                                            # 调用端点
                                            response = await create_chapter_outlines(
                                                project_id=1,
                                                request=None,
                                                db=mock_db,
                                                current_user=MagicMock()
                                            )

                                            # 验证返回 StreamingResponse
                                            from fastapi.responses import StreamingResponse
                                            assert isinstance(response, StreamingResponse)

                                            # 收集 SSE 事件
                                            events = []
                                            async for chunk in response.body_iterator:
                                                events.append(chunk)

                                            # 验证调用了 generate_chapter_outlines_stream
                                            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_progress_events_format(self):
        """progress 事件应包含 chapter_number、total 和 chapter"""
        async def mock_stream(state, llm):
            yield {
                "type": "progress",
                "chapter_number": 1,
                "total": 2,
                "chapter": {"chapter_number": 1, "title": "开篇", "scene": "城池", "plot": "故事开始"},
            }
            yield {
                "type": "progress",
                "chapter_number": 2,
                "total": 2,
                "chapter": {"chapter_number": 2, "title": "转折", "scene": "战场", "plot": "危机降临"},
            }
            yield {
                "type": "done",
                "chapter_outlines": [
                    {"chapter_number": 1, "title": "开篇"},
                    {"chapter_number": 2, "title": "转折"},
                ],
            }

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=mock_stream):
            with patch("app.api.chapters.get_llm_from_state_async", return_value=MagicMock()):
                with patch("app.api.chapters.get_project_for_user"):
                    with patch("app.api.chapters.get_outline_for_project"):
                        with patch("app.api.chapters.get_user_settings_or_raise"):
                            with patch("app.api.chapters.get_or_create_workflow_state"):
                                with patch("app.api.chapters.build_initial_state", return_value={"project_id": 1}):
                                    mock_db = MagicMock()
                                    mock_db.query.return_value.filter.return_value.first.return_value = None

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

                                    # 提取 progress 事件
                                    progress_events = [e for e in events if "event: progress" in e]
                                    assert len(progress_events) == 2

                                    # 验证第一个 progress 事件格式
                                    data_str = progress_events[0].split("data: ", 1)[1].strip()
                                    data = json.loads(data_str)
                                    assert data["chapter_number"] == 1
                                    assert data["total"] == 2
                                    assert data["chapter"]["chapter_number"] == 1
                                    assert data["chapter"]["title"] == "开篇"

    @pytest.mark.asyncio
    async def test_done_event_has_total_and_stage(self):
        """done 事件必须包含 total 和 stage 字段，不能是 undefined"""
        async def mock_stream(state, llm):
            yield {
                "type": "progress",
                "chapter_number": 1,
                "total": 1,
                "chapter": {"chapter_number": 1, "title": "测试章"},
            }
            yield {
                "type": "done",
                "chapter_outlines": [
                    {"chapter_number": 1, "title": "测试章", "scene": "", "plot": ""},
                ],
            }

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=mock_stream):
            with patch("app.api.chapters.get_llm_from_state_async", return_value=MagicMock()):
                with patch("app.api.chapters.get_project_for_user"):
                    with patch("app.api.chapters.get_outline_for_project"):
                        with patch("app.api.chapters.get_user_settings_or_raise"):
                            with patch("app.api.chapters.get_or_create_workflow_state"):
                                with patch("app.api.chapters.build_initial_state", return_value={"project_id": 1}):
                                    mock_db = MagicMock()
                                    mock_db.query.return_value.filter.return_value.first.return_value = None

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

                                    # 找到 done 事件
                                    done_events = [e for e in events if "event: done" in e]
                                    assert len(done_events) == 1

                                    # 验证 done 事件包含 total 和 stage
                                    data_str = done_events[0].split("data: ", 1)[1].strip()
                                    data = json.loads(data_str)
                                    assert "total" in data, f"done 事件缺少 total 字段: {data}"
                                    assert data["total"] == 1
                                    assert "stage" in data, f"done 事件缺少 stage 字段: {data}"
                                    assert data["stage"] == "chapter_outlines"

    @pytest.mark.asyncio
    async def test_chapter_outlines_written_to_db(self):
        """章节大纲生成后应写入数据库"""
        added_chapters = []

        async def mock_stream(state, llm):
            yield {
                "type": "progress",
                "chapter_number": 1,
                "total": 2,
                "chapter": {"chapter_number": 1, "title": "第一回"},
            }
            yield {
                "type": "progress",
                "chapter_number": 2,
                "total": 2,
                "chapter": {"chapter_number": 2, "title": "第二回"},
            }
            yield {
                "type": "done",
                "chapter_outlines": [
                    {"chapter_number": 1, "title": "第一回", "scene": "A", "plot": "B"},
                    {"chapter_number": 2, "title": "第二回", "scene": "C", "plot": "D"},
                ],
            }

        def mock_add(obj):
            added_chapters.append(obj)

        with patch("app.api.chapters.generate_chapter_outlines_stream", side_effect=mock_stream):
            with patch("app.api.chapters.get_llm_from_state_async", return_value=MagicMock()):
                with patch("app.api.chapters.get_project_for_user"):
                    with patch("app.api.chapters.get_outline_for_project"):
                        with patch("app.api.chapters.get_user_settings_or_raise"):
                            with patch("app.api.chapters.get_or_create_workflow_state"):
                                with patch("app.api.chapters.build_initial_state", return_value={"project_id": 1}):
                                    mock_db = MagicMock()
                                    mock_db.query.return_value.filter.return_value.first.return_value = None
                                    mock_db.add = mock_add

                                    from app.api.chapters import create_chapter_outlines

                                    response = await create_chapter_outlines(
                                        project_id=1,
                                        request=None,
                                        db=mock_db,
                                        current_user=MagicMock()
                                    )

                                    # 消费流以触发 DB 写入
                                    async for _ in response.body_iterator:
                                        pass

                                    # 验证 DB 写入
                                    assert len(added_chapters) == 2
                                    assert added_chapters[0].chapter_number == 1
                                    assert added_chapters[0].title == "第一回"
                                    assert added_chapters[1].chapter_number == 2
                                    assert added_chapters[1].title == "第二回"
                                    mock_db.commit.assert_called()
