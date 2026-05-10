# backend/tests/test_chapter_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.chapter_service import ChapterService


class TestChapterService:
    def test_validate_can_generate_chapter_outlines_raises_when_outline_not_confirmed(self):
        """Cannot generate chapter outlines when outline not confirmed"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = False

        with patch("app.services.chapter_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            service = ChapterService(db, project_id=1, user_id=1)
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc:
                service.validate_can_generate_chapter_outlines()
            assert exc.value.status_code == 400

    def test_validate_can_generate_chapter_outlines_passes_when_confirmed(self):
        """Can generate chapter outlines when outline is confirmed"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = True

        with patch("app.services.chapter_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            service = ChapterService(db, project_id=1, user_id=1)
            service.validate_can_generate_chapter_outlines()  # should not raise

    @pytest.mark.asyncio
    async def test_create_chapter_outlines_returns_async_iterator(self):
        """create_chapter_outlines() returns an AsyncIterator of SSE strings"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = True
        outline.collected_info = {}
        outline.inspiration_template = None

        with patch("app.services.chapter_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            with patch("app.services.chapter_service.get_or_create_workflow_state"):
                with patch("app.services.chapter_service.build_initial_state", return_value={"project_id": 1}):
                    with patch("app.services.chapter_service.create_novel_graph_with_checkpointer"):
                        with patch("app.services.workflow_orchestrator.WorkflowOrchestrator") as MockOrch:
                            mock_orch = MockOrch.return_value
                            async def mock_run(*args, **kwargs):
                                yield "event: node_start\ndata: {}\n\n"
                                yield "event: done\ndata: {}\n\n"
                            mock_orch.run = mock_run

                            service = ChapterService(db, project_id=1, user_id=1)
                            events = []
                            async for event in service.create_chapter_outlines():
                                events.append(event)
                            assert len(events) == 2