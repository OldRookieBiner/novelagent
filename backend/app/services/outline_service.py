"""Outline Service - Business logic for outline generation.

Encapsulates validation, state building, and WorkflowOrchestrator delegation.
"""

from typing import AsyncIterator, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.outline import Outline
from app.models.project import Project
from app.models.workflow_state import WorkflowState
from app.agents.state import NovelState, STAGE_OUTLINE
from app.agents.graph import create_novel_graph_with_checkpointer
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.utils.project import get_project_and_outline
from app.utils.deps import get_user_settings_or_raise
from app.utils.workflow import get_or_create_workflow_state
from app.api.workflow import build_initial_state


class OutlineService:
    """Service for outline generation operations.

    Interface:
        service = OutlineService(db, project_id, user_id)
        service.validate_can_generate()
        async for sse in service.generate(llm_config_id):
            yield sse
    """

    def __init__(self, db: Session, project_id: int, user_id: int):
        self.db = db
        self.project_id = project_id
        self.user_id = user_id
        self.project: Optional[Project] = None
        self.outline: Optional[Outline] = None

    def _load_project_outline(self) -> tuple[Project, Outline]:
        """Lazy-load project and outline."""
        if self.project is None or self.outline is None:
            self.project, self.outline = get_project_and_outline(
                self.project_id, self.user_id, self.db
            )
        return self.project, self.outline

    def validate_can_generate(self) -> None:
        """校验大纲是否可以重新生成。

        Raises:
            HTTPException: 400 如果大纲已确认
        """
        _, outline = self._load_project_outline()
        if outline.confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot regenerate a confirmed outline"
            )

    async def generate(
        self,
        llm_config_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """生成大纲并返回 SSE 事件流。

        Args:
            llm_config_id: 可选的模型配置 ID

        Yields:
            SSE 格式字符串
        """
        project, outline = self._load_project_outline()
        user_settings = get_user_settings_or_raise(
            self.db.query(User).filter(User.id == self.user_id).first(),
            self.db
        )

        # 更新工作流状态
        workflow_state = get_or_create_workflow_state(self.db, self.project_id)
        workflow_state.stage = STAGE_OUTLINE
        self.db.commit()

        # 构建初始状态（预加载角色/关系数据）
        initial_state = build_initial_state(
            project, outline, workflow_state, llm_config_id, db=self.db
        )

        # 预加载 prompts
        from app.services.prompt_loader import get_system_prompt
        prompts = {
            "outline_generation": get_system_prompt(self.db, "outline_generation"),
            "character_generation": get_system_prompt(self.db, "character_generation"),
            "relation_generation": get_system_prompt(self.db, "relation_generation"),
        }

        # 创建图
        graph = create_novel_graph_with_checkpointer(self.project_id, "default")
        config = {
            "configurable": {
                "thread_id": "default",
                "prompts": prompts,
            }
        }

        # 持久化回调
        async def persist_outline(state: NovelState, db: Session) -> dict:
            """在 outline_generation_node 完成后持久化大纲数据"""
            outline.title = state.get("outline_title", outline.title)
            outline.summary = state.get("outline_summary", outline.summary)
            outline.plot_points = state.get("outline_plot_points", [])
            outline.characters = state.get("outline_characters", [])
            outline.world_setting = state.get("outline_world_setting")
            outline.emotional_curve = state.get("outline_emotional_curve")
            db.commit()
            return {"outline_title": outline.title, "stage": STAGE_OUTLINE}

        # 执行
        orchestrator = WorkflowOrchestrator(self.db, self.project_id)
        async for event in orchestrator.run(
            graph=graph,
            config=config,
            initial_state=initial_state,
            target_node="outline_generation_node",
            persist_callback=persist_outline,
        ):
            yield event