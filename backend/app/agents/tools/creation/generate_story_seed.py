"""生成故事种子工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb


@tool
async def generate_story_seed(
    seed_narrative: str,
    core_tension: str = "",
    protagonist_archetype: str = "",
    world_tone: str = "",
    emotional_tone: str = "",
) -> dict:
    """生成并保存故事种子文档。

    故事种子是小说创作的起点，包含核心概念、主题和基本设定。
    通常在项目初始化时自动调用，但 Agent 也可以手动调用以更新或补充故事种子。
    当用户提供了新的创意方向、需要重新定义故事核心时，可以手动调用此工具更新种子。

    Args:
            seed_narrative: 300-500 字的故事叙述
            core_tension: 核心冲突/悬念
            protagonist_archetype: 主角原型
            world_tone: 世界独特质感
            emotional_tone: 读者应有的情感体验

    Returns:
        dict:
            - action (str): 操作类型 - "created"
            - seed_length (int): 故事叙述字数
            - message (str): 操作结果描述
    """
    project_id = get_project_id()
    kb = _kb()

    # 使用 OutlineStore 的 upsert 方法
    seed_block = seed_narrative
    if core_tension:
        seed_block += f"\n\n核心张力：{core_tension}"
    if protagonist_archetype:
        seed_block += f"\n\n主角原型：{protagonist_archetype}"
    if world_tone:
        seed_block += f"\n\n世界基调：{world_tone}"
    if emotional_tone:
        seed_block += f"\n\n情感基调：{emotional_tone}"

    # 同时更新 story_seed 和 outline.summary
    kb.update_story_seed(seed_block)

    outline = kb.outlines.get()
    if outline:
        kb.outlines.update({"summary": seed_block})
    else:
        kb.outlines.upsert({"summary": seed_block})

    return {
        "action": "created",
        "seed_length": len(seed_narrative),
        "message": "故事种子已生成并写入知识库",
    }
