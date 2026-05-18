"""Workflow Orchestrator - Central SSE streaming service for LangGraph endpoints.

All SSE streaming endpoints use this module to:
1. Execute a LangGraph graph via astream with stream_mode=['updates', 'custom']
2. Parse LangGraph events into SSE format
3. Call persist callbacks when target nodes complete
4. Handle errors gracefully with transaction rollback
"""

import asyncio
import json
import logging
from typing import AsyncIterator, Callable, Awaitable, Optional

from app.agents.sse_events import format_done, format_error_message, format_sse_error
from app.agents.state import NovelState

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

        使用 astream + stream_mode=['updates', 'custom'] 捕获：
        - custom: 节点通过 get_stream_writer() 发送的结构化流式事件
        - updates: 节点完成后的状态更新

        Args:
            graph: Compiled LangGraph StateGraph
            config: LangGraph config dict (must contain configurable.thread_id)
            initial_state: Initial NovelState. If None, resumes from checkpoint.
            target_node: Node name that triggers persist_callback when completed.
            persist_callback: Async function (state, db) -> dict, called on target_node done.

        Yields:
            SSE formatted strings ending with \\n\\n
        """
        try:
            # 首次执行 vs 恢复执行
            if initial_state is not None:
                yield (
                    f"event: node_start\n"
                    f"data: {json.dumps({'node': 'workflow', 'message': 'Starting workflow'})}\n\n"
                )
            else:
                yield (
                    f"event: node_start\n"
                    f"data: {json.dumps({'node': 'workflow_resume', 'message': 'Resuming workflow'})}\n\n"
                )

            async for mode_data in graph.astream(
                initial_state,
                config,
                stream_mode=['updates', 'custom'],
            ):
                mode, data = mode_data

                if mode == 'custom':
                    # 节点通过 get_stream_writer() 发送的结构化事件
                    if isinstance(data, dict) and data.get('type'):
                        custom_type = data.pop('type')
                        yield (
                            f"event: {custom_type}\n"
                            f"data: {json.dumps(data)}\n\n"
                        )

                elif mode == 'updates':
                    # 节点完成后的状态更新
                    if isinstance(data, dict):
                        for node_name, node_output in data.items():
                            if not isinstance(node_output, dict):
                                continue

                            # 持久化回调
                            if target_node and node_name == target_node and persist_callback is not None:
                                persist_result = await self._call_persist(node_output, persist_callback)
                                if persist_result.get("_persist_error"):
                                    error_msg = persist_result["_persist_error"]
                                    yield format_error_message(f"持久化失败: {error_msg}")
                                    yield format_done("Error occurred")
                                    return

                            # 等待确认
                            if node_output.get("waiting_for_confirmation"):
                                waiting_data = {
                                    'node': node_name,
                                    'confirmation_type': node_output.get('confirmation_type')
                                }
                                yield (
                                    f"event: waiting\n"
                                    f"data: {json.dumps(waiting_data)}\n\n"
                                )
                                yield (
                                    f"event: done\n"
                                    f"data: {json.dumps({'message': 'Workflow paused for confirmation'})}\n\n"
                                )
                                return
                            else:
                                yield (
                                    f"event: node_done\n"
                                    f"data: {json.dumps({'node': node_name, 'state': node_output})}\n\n"
                                )

            yield (
                f"event: done\n"
                f"data: {json.dumps({'message': 'Workflow completed'})}\n\n"
            )

        except asyncio.CancelledError:
            # async generator 中 CancelledError 后不能 yield（连接已关闭），必须 re-raise
            logger.warning("WorkflowOrchestrator SSE stream cancelled by server")
            raise
        except Exception as e:
            logger.exception("WorkflowOrchestrator run error")
            yield format_sse_error(e)
            yield format_done("Error occurred")

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
