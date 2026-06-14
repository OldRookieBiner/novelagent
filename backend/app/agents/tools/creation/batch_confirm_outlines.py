"""批量确认章节大纲工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def batch_confirm_outlines(chapter_numbers: str) -> dict:
    """批量确认章节大纲。将指定章节的大纲标记为已确认，使其可以开始写作。

    Args:
        chapter_numbers: JSON 字符串列表，要确认的章节号列表（如 "[1,2,3]"）
    """
    kb = _kb()

    nums, warn = parse_json_param(chapter_numbers, [], "chapter_numbers")
    if warn:
        return {"error": f"chapter_numbers 参数解析失败: {warn}"}

    if not nums:
        return {"error": "chapter_numbers 不能为空"}

    confirmed = []
    not_found = []
    already_confirmed = []
    errors = []

    for ch_num in nums:
        try:
            outline = kb.outlines.get_chapter_outline(ch_num)
            if not outline:
                not_found.append(ch_num)
            elif outline.get("confirmed"):
                already_confirmed.append(ch_num)
            else:
                kb.outlines.update_chapter_outline(ch_num, {"confirmed": True})
                confirmed.append(ch_num)
        except Exception as e:
            errors.append({"chapter_number": ch_num, "error": str(e)})

    result = {
        "confirmed": confirmed,
        "already_confirmed": already_confirmed,
        "not_found": not_found,
        "errors": errors,
        "total_requested": len(nums),
        "total_confirmed": len(confirmed),
        "message": f"已确认 {len(confirmed)} 个章节大纲" if confirmed else "没有新的章节大纲需要确认",
    }
    if not_found:
        result["hint"] = f"章节 {not_found} 大纲不存在，请先用 generate_chapter_outline 创建"
    return result
