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
            name: 角色名
            role: Character role - one of: 主角, 核心反派, 重要配角, 配角
            personality: 性格特征描述
            catchphrase: 口头禅或典型语言风格
            habit_action: 习惯动作或姿态
            deep_fear: 深层恐惧
            core_motivation: 驱动角色行动的核心动机
            growth_arc: 成长弧线/角色发展轨迹
            appearance: 外貌描写
            backstory: 背景故事
            signature_item: 标志性物品或配饰
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
