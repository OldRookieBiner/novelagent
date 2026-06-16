"""记录章节追踪元数据工具（合并版）

合并原 record_chapter_meta 和 create_timeline_entry。
从 generate_chapter_content 拆分出来的追踪数据记录功能。
R24 修正：使用 TimelineStore.get_by_chapter_number + update_timeline_entry 实现 upsert。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def record_chapter_meta(
    chapter_number: int,
    timeline_summary: str | None = None,
    causal_chain: str | None = None,
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str | None = None,
    new_foreshadowings: str = "[]",
    reclaimed_foreshadowing_ids: str = "[]",
) -> dict:
    """记录章节的追踪元数据（时间线、伏笔、节奏评分等）。

    在 generate_chapter_content 保存章节正文后调用此工具补充追踪数据。
    也可以单独调用以补录遗漏的追踪数据。


    Prerequisites:
        - 章节内容必须已生成（使用 generate_chapter_content）

    Args:
        chapter_number: 章节号
        timeline_summary: 时间线摘要
        causal_chain: 因果链描述
        rhythm_score: 节奏评分 1-5
        tension_score: 张力评分 1-5
        emotion_score: 情感评分 1-5
        emotion_tag: 情绪标签
        new_foreshadowings: JSON 字符串列表，本章新埋的伏笔
        reclaimed_foreshadowing_ids: JSON 字符串列表，本章回收的伏笔 ID
    """
    kb = _kb()

    warnings = []

    # 1. 时间线 — upsert 模式
    timeline_action = "skipped"
    if timeline_summary:
        existing = kb.timelines.get_by_chapter_number(chapter_number)
        timeline_data = {
            "chapter_number": chapter_number,
            "summary": timeline_summary,
            "causal_chain": causal_chain or "",
            "rhythm_score": rhythm_score,
            "tension_score": tension_score,
            "emotion_score": emotion_score,
            "emotion_tag": emotion_tag or "",
        }
        try:
            if existing:
                kb.timelines.update_timeline_entry(existing["id"], timeline_data)
                timeline_action = "updated"
            else:
                kb.timelines.create_timeline_entry(timeline_data)
                timeline_action = "created"
        except Exception as e:
            warnings.append({"step": "timeline", "error": str(e)})

    # 2. 创建新伏笔
    new_fs, new_fs_warn = parse_json_param(new_foreshadowings, [], "new_foreshadowings")
    if new_fs_warn:
        warnings.append({"step": "parse_new_foreshadowings", "error": new_fs_warn})

    created_fs = []
    new_foreshadowing_errors = []
    for fs_data in new_fs:
        try:
            f = kb.foreshadowings.create({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f["id"], "content": (f.get("content") or "")[:60]})
        except Exception as e:
            new_foreshadowing_errors.append({"data": fs_data, "error": str(e)})
    if new_foreshadowing_errors:
        warnings.append({"step": "new_foreshadowings", "errors": new_foreshadowing_errors})

    # 3. 回收伏笔
    reclaimed_ids, reclaimed_warn = parse_json_param(reclaimed_foreshadowing_ids, [], "reclaimed_foreshadowing_ids")
    if reclaimed_warn:
        warnings.append({"step": "parse_reclaimed_ids", "error": reclaimed_warn})

    reclaim_errors = []
    for fs_id in reclaimed_ids:
        try:
            kb.foreshadowings.update(fs_id, {"status": "reclaimed", "resolved_chapter": chapter_number})
        except Exception as e:
            reclaim_errors.append({"foreshadowing_id": fs_id, "error": str(e)})
    if reclaim_errors:
        warnings.append({"step": "reclaim_foreshadowings", "errors": reclaim_errors})

    result = {
        "chapter_number": chapter_number,
        "timeline_action": timeline_action,
        "new_foreshadowings": len(created_fs),
        "new_foreshadowing_errors": new_foreshadowing_errors,
        "reclaimed_foreshadowings": len(reclaimed_ids) - len(reclaim_errors),
        "reclaim_errors": reclaim_errors,
        "message": f"第{chapter_number}章追踪数据已记录（时间线: {timeline_action}，新伏笔: {len(created_fs)}，回收: {len(reclaimed_ids) - len(reclaim_errors)}）",
    }
    if warnings:
        result["warnings"] = warnings
    return result
