"""创建角色工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_character(
    name: str,
    role: str,
    personality: str = "",
    catchphrase: str = "",
    habit_action: str = "",
    deep_fear: str = "",
    core_motivation: str = "",
    growth_arc: str = "",
    appearance: str = "",
    backstory: str = "",
    signature_item: str = "",
) -> dict:
    """在小说中创建一个新角色。

    当用户需要添加新角色到故事中时使用。创建后角色信息会写入知识库。

    Args:
            name: Character name
            role: Character role - one of: 主角, 核心反派, 重要配角, 配角
            personality: Personality traits description
            catchphrase: Character's catchphrase or typical speech pattern
            habit_action: Character's habitual gesture or action
            deep_fear: Character's deep-seated fear
            core_motivation: Character's core motivation driving their actions
            growth_arc: Character's growth arc / character development trajectory
            appearance: Physical appearance description
            backstory: Character's backstory
            signature_item: Character's signature item or accessory
    """
    kb = _kb()

    data = {"name": name, "role": role}
    for key, val in [
        ("personality", personality),
        ("catchphrase", catchphrase),
        ("habit_action", habit_action),
        ("deep_fear", deep_fear),
        ("core_motivation", core_motivation),
        ("growth_arc", growth_arc),
        ("appearance", appearance),
        ("backstory", backstory),
        ("signature_item", signature_item),
    ]:
        if val:
            data[key] = val

    char = kb.characters.create_character(data)
    return {
        "action": "created",
        "id": char["id"],
        "name": char["name"],
        "role": char["role"],
        "message": f"角色「{name}」已创建并写入知识库",
    }
