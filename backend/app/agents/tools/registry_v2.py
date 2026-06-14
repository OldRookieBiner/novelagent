"""动态工具注册表

根据项目规模和阶段动态调整工具列表。
R13 修正：基于集合运算的声明式定义，递进关系由集合运算保证。
保持向后兼容：旧常量 INCUBATION_TOOLS / STRUCTURE_TOOLS / WRITING_TOOLS 仍可用。
"""

from app.agents.tools.registry import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.constants import Phase


# 大型项目额外启用的工具名
_LARGE_PROJECT_TOOL_NAMES = {"consistency_scan", "check_chapter_transition"}

# 小型项目排除的工具名
_SMALL_PROJECT_EXCLUDE_NAMES = {"rhythm_analysis"}

# 阶段基线（保持递进关系）
_PHASE_BASE_TOOLS = {
    Phase.INCUBATION.value: INCUBATION_TOOLS,
    Phase.STRUCTURE.value: STRUCTURE_TOOLS,
    Phase.WRITING.value: WRITING_TOOLS,
    Phase.REVISION.value: WRITING_TOOLS,
}


class ToolRegistry:
    """动态工具注册表"""

    def __init__(self, project_id: int, phase: str):
        self.project_id = project_id
        self.phase = phase

    def get_tools(self) -> list:
        """根据项目规模和阶段动态返回工具列表"""
        base_tools = list(_PHASE_BASE_TOOLS.get(self.phase, WRITING_TOOLS))

        # 估算项目规模
        total_chapters = 0
        try:
            kb = KnowledgeBaseService(self.project_id)
            outline = kb.outlines.get()
            if outline:
                total_chapters = (
                    outline.get("chapter_count_confirmed")
                    or outline.get("chapter_count_suggested")
                    or 0
                )
        except Exception:
            pass

        # 大型项目：启用高级感知工具
        if total_chapters >= 20:
            base_tool_names = {t.name for t in base_tools}
            for t in WRITING_TOOLS:
                if t.name in _LARGE_PROJECT_TOOL_NAMES and t.name not in base_tool_names:
                    base_tools.append(t)

        # 小型项目：禁用部分工具减少噪音
        if 0 < total_chapters <= 10:
            base_tools = [t for t in base_tools if t.name not in _SMALL_PROJECT_EXCLUDE_NAMES]

        return base_tools
