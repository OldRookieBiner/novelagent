"""向后兼容层 — 所有导入已迁移到 app.agents.tools

此文件保留为兼容层，确保旧导入路径仍然可用。
新代码应使用 from app.agents.tools import ...
"""

from app.agents.tools import *  # noqa: F401,F403
from app.agents.tools import (
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    AGENT_TOOLS,
    _kb,
    _extract_keywords,
    _grade_impact,
)
