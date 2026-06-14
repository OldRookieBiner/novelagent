"""一致性检查工具

A3 增强：在原有知识库约束返回基础上，新增章节内容交叉分析。
R19 修正：字段名与 Character 模型一致。
R19b 精确加载：只加载出场角色的约束信息，减少 token 噪音。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _extract_names, _extract_times


@tool
async def consistency_check(chapter_a: int, chapter_b: int, aspect: str = "all") -> dict:
    """检查两章之间的一致性。

    当用户怀疑有矛盾或想验证角色行为、时间线、设定的一致性时使用。

    Args:
        chapter_a: 第一个章节号
        chapter_b: 第二个章节号
        aspect: 检查方面 - "character"(角色), "timeline"(时间线), "setting"(设定), 或 "all"(全部)
    """
    kb = _kb()
    result = {"chapters_compared": [chapter_a, chapter_b], "issues": []}

    # 读取两章内容以确定出场角色
    chapter_a_obj = kb.chapters.get_by_number(chapter_a)
    chapter_b_obj = kb.chapters.get_by_number(chapter_b)
    content_a = chapter_a_obj.get("content", "") if chapter_a_obj else ""
    content_b = chapter_b_obj.get("content", "") if chapter_b_obj else ""

    if aspect in ("all", "character"):
        # 精确加载：只加载出场角色的约束
        appearing_names = set()
        if content_a:
            appearing_names.update(_extract_names(content_a, kb))
        if content_b:
            appearing_names.update(_extract_names(content_b, kb))

        all_chars = kb.characters.list_characters()
        constraints = []
        for char in all_chars:
            # 如果有出场角色名，只加载出场角色；否则加载全部
            if appearing_names and char["name"] not in appearing_names:
                continue
            constraints.append({
                "name": char["name"],
                "deep_fear": char.get("deep_fear") or "",
                "core_motivation": char.get("core_motivation") or "",
            })
        result["character_constraints"] = constraints

    if aspect in ("all", "timeline"):
        timeline = kb.timelines.list_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = timeline

    if aspect in ("all", "setting"):
        ws = kb.world_setting.get()
        if ws:
            result["world_setting_red"] = (ws.get("tiered_settings") or {}).get("red", [])

    # 章节内容交叉分析
    if aspect in ("all", "character", "timeline"):
        if content_a and content_b:
            names_a = set(_extract_names(content_a, kb))
            names_b = set(_extract_names(content_b, kb))
            common_names = names_a & names_b

            times_a = set(_extract_times(content_a))
            times_b = set(_extract_times(content_b))
            common_times = times_a & times_b

            cross_analysis = {
                "chapter_a_length": len(content_a),
                "chapter_b_length": len(content_b),
                "names_in_a": len(names_a),
                "names_in_b": len(names_b),
                "common_names": list(common_names)[:20],
                "times_in_a": len(times_a),
                "times_in_b": len(times_b),
                "common_times": list(common_times)[:10],
            }

            if common_names and aspect in ("all", "character"):
                cross_analysis["character_overlap_note"] = (
                    f"两章共同出现 {len(common_names)} 个角色名，请检查行为是否一致"
                )
            if common_times and aspect in ("all", "timeline"):
                cross_analysis["timeline_overlap_note"] = (
                    f"两章共同出现 {len(common_times)} 个时间表达，请检查时间线是否一致"
                )

            result["cross_analysis"] = cross_analysis
        else:
            result["cross_analysis"] = {
                "note": "一章或两章内容不存在，无法进行内容交叉分析"
            }

    if not result["issues"]:
        result["message"] = "未发现明显的逻辑矛盾。请提供具体的矛盾描述，我可以帮你进一步分析。"
    return result
