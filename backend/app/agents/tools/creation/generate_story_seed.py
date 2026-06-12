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
    """Generate and save the story seed document.

    The story seed is a narrative description that captures
    the essence of the story.

    Args:
        seed_narrative: 300-500 word narrative
        core_tension: The ultimate conflict/question
        protagonist_archetype: Who the protagonist is
        world_tone: World's unique texture
        emotional_tone: How readers should feel
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
