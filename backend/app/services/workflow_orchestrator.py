"""Workflow Orchestrator - Central SSE streaming service for LangGraph endpoints.

All SSE streaming endpoints use this module to:
1. Execute a LangGraph graph via astream_events
2. Parse LangGraph events into SSE format
3. Call persist callbacks when target nodes complete
4. Handle errors gracefully with transaction rollback
"""

import logging
from typing import AsyncIterator, Callable, Awaitable, Optional

from app.agents.state import NovelState
from app.agents.sse_events import (
    format_node_start,
    format_node_done,
    format_chunk,
    format_done,
    format_waiting,
    format_error_message,
    format_sse_error,
)

logger = logging.getLogger(__name__)

PersistCallback = Callable[[NovelState, "Session"], Awaitable[Optional[dict]]]


class WorkflowOrchestrator:
    """Central orchestrator for LangGraph SSE streaming.

    Interface:
        orch = WorkflowOrchestrator(db, project_id)
        async for sse_event in orch.run(graph, config, initial_state, target_node, persist_callback):
            yield sse_event

    Invariants:
        - db session lifecycle is managed by the caller (API route)
        - persist_callback exceptions trigger db.rollback() and yield error event
        - SSE event format never changes (backward compatible)
    """

    def __init__(self, db: "Session", project_id: int):
        self.db = db
        self.project_id = project_id

    async def run(
        self,
        graph,
        config: dict,
        initial_state: Optional[dict] = None,
        target_node: Optional[str] = None,
        persist_callback: Optional[PersistCallback] = None,
    ) -> AsyncIterator[str]:
        """Execute graph and yield SSE events.

        Args:
            graph: Compiled LangGraph StateGraph
            config: LangGraph config dict (must contain configurable.thread_id)
            initial_state: Initial NovelState. If None, resumes from checkpoint.
            target_node: Node name that triggers persist_callback when completed.
            persist_callback: Async function (state, db) -> dict, called on target_node done.

        Yields:
            SSE formatted strings ending with \n\n
        """
        try:
            # 首次执行 vs 恢复执行
            if initial_state is not None:
                yield format_node_start("workflow", "Starting workflow")
            else:
                yield format_node_start("workflow_resume", "Resuming workflow")

            async for event in graph.astream_events(initial_state, config, version="v2"):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if event_type == "on_chain_start":
                    yield format_node_start(event_name)

                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", str(chunk))
                        if content:
                            yield format_chunk(content)

                elif event_type == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        # 持久化回调
                        if target_node and event_name == target_node and persist_callback is not None:
                            persist_result = await self._call_persist(output, persist_callback)
                            if persist_result.get("_persist_error"):
                                error_msg = persist_result["_persist_error"]
                                yield format_error_message(f"持久化失败: {error_msg}")
                                return

                        if output.get("waiting_for_confirmation"):
                            yield format_waiting(output.get("confirmation_type"), node=event_name)
                            yield format_done("Workflow paused for confirmation")
                            return
                        else:
                            yield format_node_done(event_name, output)

            yield format_done("Workflow completed")

        except Exception as e:
            logger.exception("WorkflowOrchestrator run error")
            yield format_sse_error(e)

    async def _call_persist(
        self,
        state: dict,
        persist_callback: PersistCallback,
    ) -> dict:
        """Call persist callback with rollback on error.

        Returns:
            Dict from callback, or {"_persist_error": str} on failure.
        """
        try:
            result = await persist_callback(state, self.db)
            return result or {}
        except Exception as e:
            logger.error(f"Persist callback failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            return {"_persist_error": str(e)}
