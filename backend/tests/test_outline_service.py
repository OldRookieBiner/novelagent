# backend/tests/test_outline_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.outline_service import OutlineService


class TestOutlineService:
    def test_validate_can_generate_raises_when_confirmed(self):
        """Cannot regenerate a confirmed outline"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = True

        with patch("app.services.outline_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            service = OutlineService(db, project_id=1, user_id=1)
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc:
                service.validate_can_generate()
            assert exc.value.status_code == 400

    def test_validate_can_generate_passes_when_not_confirmed(self):
        """Can generate when outline is not confirmed"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = False

        with patch("app.services.outline_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            service = OutlineService(db, project_id=1, user_id=1)
            service.validate_can_generate()  # should not raise

    @pytest.mark.asyncio
    async def test_generate_returns_async_iterator(self):
        """generate() returns an AsyncIterator of SSE strings"""
        db = MagicMock()
        outline = MagicMock()
        outline.confirmed = False
        outline.collected_info = {}
        outline.inspiration_template = None

        with patch("app.services.outline_service.get_project_and_outline", return_value=(MagicMock(), outline)):
            with patch("app.services.outline_service.get_user_settings_or_raise"):
                with patch("app.services.outline_service.get_or_create_workflow_state"):
                    with patch("app.services.outline_service.build_initial_state", return_value={"project_id": 1}):
                        with patch("app.services.outline_service.create_novel_graph_with_checkpointer"):
                            with patch("app.services.workflow_orchestrator.WorkflowOrchestrator") as MockOrch:
                                mock_orch = MockOrch.return_value
                                async def mock_run(*args, **kwargs):
                                    yield "event: node_start\ndata: {}\n\n"
                                    yield "event: done\ndata: {}\n\n"
                                mock_orch.run = mock_run

                                service = OutlineService(db, project_id=1, user_id=1)
                                events = []
                                async for event in service.generate():
                                    events.append(event)
                                assert len(events) == 2
