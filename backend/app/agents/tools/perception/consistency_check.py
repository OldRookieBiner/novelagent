"""一致性检查工具

A3 增强：在原有知识库约束返回基础上，新增章节内容交叉分析。
读取两章实际内容，提取角色名和时间表达，找出交叉数据。
不调用 LLM，由 Agent 判断矛盾。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _extract_names, _extract_times


@tool
async def consistency_check(chapter_a: int, chapter_b: int, aspect: str = "all") -> dict:
    """Check consistency between two chapters or across the whole novel.

    Use when the user suspects a contradiction or wants to verify
    consistency of character behavior, timeline, or settings.

    Args:
        chapter_a: First chapter number to compare
        chapter_b: Second chapter number to compare
        aspect: What to check - "character", "timeline", "setting", or "all"
    """
    kb = _kb()
    result = {"chapters_compared": [chapter_a, chapter_b], "issues": []}

    if aspect in ("all", "character"):
        chars = kb.characters.list_characters()
        constraints = []
        for char in chars:
            constraints.append({
                "name": char["name"],
                "knowledge_boundary": char.get("knowledge_boundary") or char.get("deep_fear") or "",
            })
        result["character_constraints"] = constraints

    if aspect in ("all", "timeline"):
        timeline = kb.timelines.list_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = timeline

    if aspect in ("all", "setting"):
        ws = kb.world_setting.get()
        if ws:
            result["world_setting_red"] = (ws.get("tiered_settings") or {}).get("red", [])

    # A3 增强：章节内容交叉分析
    if aspect in ("all", "character", "timeline"):
        chapter_a_obj = kb.chapters.get_by_number(chapter_a)
        chapter_b_obj = kb.chapters.get_by_number(chapter_b)

        if chapter_a_obj and chapter_a_obj.get("content") and chapter_b_obj and chapter_b_obj.get("content"):
            content_a = chapter_a_obj["content"]
            content_b = chapter_b_obj["content"]

            # 提取角色名（传入 kb 使用知识库精确匹配）
            names_a = set(_extract_names(content_a, kb))
            names_b = set(_extract_names(content_b, kb))
            common_names = names_a & names_b

            # 提取时间表达
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
