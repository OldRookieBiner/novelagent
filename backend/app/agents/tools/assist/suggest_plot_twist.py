"""反转建议工具

增强：多角色分析 + 读者预期反转。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def suggest_plot_twist(current_chapter: int) -> dict:
    """基于节奏曲线、角色弧线和活跃伏笔，建议情节反转方向。

    分析所有主要角色的动机冲突，返回最有反转潜力的选项。

    Args:
        current_chapter: 当前章节号
    """
    kb = _kb()

    timeline = kb.timelines.list_timeline()
    foreshadowings = kb.foreshadowings.list_foreshadowings(status="active")
    characters = kb.characters.list_characters()
    block = kb.plots.get_current_plot_block(current_chapter)

    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.get("tension_score"):
                recent_tension.append(t["tension_score"])

    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    twist_types = []

    # 1. 节奏驱动反转
    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    # 2. 伏笔误导
    if len(foreshadowings) >= 2:
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowing_ids": [f["id"] for f in foreshadowings[:3]],
        })

    # 3. 多角色分析（分析所有主要角色，不只第一个）
    main_chars = [c for c in characters if c.get("role") in ("主角", "核心反派", "重要配角")]
    char_twists = []
    for c in main_chars[:3]:
        core_mot = c.get("core_motivation", "")
        deep_fear = c.get("deep_fear", "")
        growth_arc = c.get("growth_arc", "")
        if core_mot or deep_fear:
            twist_direction = ""
            if deep_fear and growth_arc:
                twist_direction = f"让「{c['name']}」的成长弧线突然受挫——其深层恐惧「{deep_fear[:20]}」被触发，迫使面对最不想面对的处境"
            elif core_mot:
                twist_direction = f"揭示「{c['name']}」的真正动机与表面不同——核心动机「{core_mot[:20]}」背后隐藏更深的目的"
            if twist_direction:
                char_twists.append({
                    "type": "角色反转",
                    "character_id": c["id"],
                    "character_name": c["name"],
                    "character_role": c.get("role", ""),
                    "direction": twist_direction,
                })

    twist_types.extend(char_twists)

    # 4. 读者预期反转（基于活跃伏笔的预期方向，建议相反方向）
    reader_expectation_twists = []
    for f in foreshadowings[:3]:
        content = f.get("content", "")
        expected_resolve = f.get("expected_resolve_chapter")
        if content and expected_resolve and expected_resolve > current_chapter:
            reader_expectation_twists.append({
                "type": "读者预期反转",
                "foreshadowing_id": f["id"],
                "foreshadowing_preview": content[:60],
                "direction": f"伏笔「{content[:30]}」引导读者期待一个方向，实际揭示时走向相反方向——制造意外但合理的效果",
            })
    twist_types.extend(reader_expectation_twists)

    return {
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:5],
    }
