"""生成大纲工具"""

from langchain_core.tools import tool



@tool
async def generate_outline(
    title: str,
    summary: str,
    chapter_count: int,
    plot_points: str = "[]",
    emotional_curve: str = "[]",
    characters: str = "[]",
    world_setting_summary: str = "",
) -> dict:
    """生成并保存完整的小说大纲。

    当用户需要从创意概念生成整体故事大纲时使用。包括章节规划、情节走向和情感曲线。

    Args:
        title: 小说标题
        summary: 故事摘要
        chapter_count: 预计章节数
        plot_points: JSON 字符串列表，关键情节节点
        emotional_curve: JSON 字符串列表，情感曲线
        characters: JSON 字符串列表，主要角色概要
        world_setting_summary: 世界观概要摘要（可选，追加到大纲摘要末尾）
    """
    from app.agents.tools.utils import _kb, parse_json_param

    points, points_warn = parse_json_param(plot_points, [], "plot_points")

    curve, curve_warn = parse_json_param(emotional_curve, [], "emotional_curve")

    char_list, char_list_warn = parse_json_param(characters, [], "characters")

    kb = _kb()

    # 追加 world_setting_summary 到 summary（如果提供了）
    final_summary = summary
    if world_setting_summary:
        final_summary = f"{summary}\n\n世界观概要：{world_setting_summary}"

    try:
        result = kb.outlines.upsert({
            "title": title,
            "summary": final_summary,
            "chapter_count_suggested": chapter_count,
            # 草稿态：章节数与总纲均待作者确认（confirmed 字段为布尔，勿赋整数）
            "chapter_count_confirmed": False,
            "plot_points": points,
            "emotional_curve": curve,
            "characters": char_list,
            "confirmed": False,
        })
        return {
            "action": "created",
            "title": title,
            "chapter_count": chapter_count,
            "plot_point_count": len(points),
            "message": f"大纲「{title}」已创建并写入知识库，共 {chapter_count} 章、{len(points)} 个情节节点",
        }
    except Exception as e:
        return {"error": str(e)}
