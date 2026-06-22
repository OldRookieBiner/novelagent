"""提议大纲调整工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param
from app.utils.text import tokenize_chinese


# 提议中允许写入总纲的字段白名单
_ALLOWED_OUTLINE_FIELDS = {
    "title", "summary", "plot_points", "characters",
    "world_setting", "emotional_curve",
}

# 需按 JSON 解析的字段
_JSON_OUTLINE_FIELDS = {"plot_points", "characters", "world_setting", "emotional_curve"}


@tool
async def propose_outline_adjustment(
    description: str,
    affected_plot_blocks: list[int] | None = None,
    proposed_outline: str | None = None,
) -> dict:
    """提议调整故事结构。

    当用户需要修改大纲、增删章节或调整情节走向时使用。自动评估变更对已有内容的影响，返回影响评估结果。
    若已确定具体的总纲新值，请通过 proposed_outline 传入结构化内容，作者确认后 apply_change 才能真正落库；
    仅传 description 时只生成影响评估，不含可应用的实际改动。

    Args:
        description: 调整内容的自然语言描述
        affected_plot_blocks: 受影响的情节块 ID 列表
        proposed_outline: JSON 字符串对象，拟应用的总纲新值，支持字段：
            title / summary / plot_points / characters / world_setting / emotional_curve
    """
    kb = _kb()

    # 解析结构化新值（可选），仅保留白名单字段
    outline_new_value: dict = {}
    parse_warnings: list[str] = []
    if proposed_outline:
        parsed, warn = parse_json_param(proposed_outline, {}, "proposed_outline")
        if warn:
            parse_warnings.append(warn)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if k not in _ALLOWED_OUTLINE_FIELDS or v is None:
                    continue
                if k in _JSON_OUTLINE_FIELDS and isinstance(v, str):
                    sub_default = {} if k == "world_setting" else []
                    sub_parsed, sub_warn = parse_json_param(v, sub_default, k)
                    if sub_warn:
                        parse_warnings.append(sub_warn)
                    outline_new_value[k] = sub_parsed
                else:
                    outline_new_value[k] = v

    blocks = kb.plots.list_plot_blocks()
    foreshadowings = kb.foreshadowings.list_foreshadowings(status="active")
    questions = kb.plots.list_plot_questions(status="pending")

    affected_blocks = []
    if affected_plot_blocks:
        affected_blocks = [b for b in blocks if b["id"] in affected_plot_blocks]
    else:
        for b in blocks:
            block_text = f"{b.get('title', '')} {' '.join(b.get('must_happen') or [])} {' '.join(b.get('questions_to_answer') or [])}"
            for word in tokenize_chinese(description):
                if len(word) >= 2 and word in block_text:
                    affected_blocks.append(b)
                    break

    affected_foreshadowings = []
    for f in foreshadowings:
        for b in affected_blocks:
            if b.get("chapter_start") and f.get("expected_resolve_chapter"):
                if b["chapter_start"] <= f["expected_resolve_chapter"] <= (b.get("chapter_end") or 999):
                    affected_foreshadowings.append({
                        "id": f["id"],
                        "content": f.get("content", "")[:60],
                        "expected_resolve_chapter": f["expected_resolve_chapter"],
                    })

    affected_questions = []
    for q in questions:
        for b in affected_blocks:
            if q.get("plot_block_id") == b["id"]:
                affected_questions.append({
                    "id": q["id"],
                    "question": q.get("question_text", "")[:60],
                    "status": q.get("status"),
                })

    impact_level = "minor"
    if affected_foreshadowings or affected_questions:
        impact_level = "moderate"
    if len(affected_blocks) > 2:
        impact_level = "severe"

    # 格式化 chapter_range，处理 None 情况
    affected_blocks_report = []
    for b in affected_blocks:
        cs = b.get("chapter_start")
        ce = b.get("chapter_end")
        chapter_range_str = f"{cs}-{ce}" if cs is not None and ce is not None else "未设定"
        affected_blocks_report.append({
            "id": b["id"],
            "title": b.get("title", ""),
            "chapter_range": chapter_range_str
        })

    change = kb.changes.create({
        "target_type": "outline_adjustment",
        "target_id": 0,
        "old_value": {},
        "new_value": {**outline_new_value, "description": description},
        "description": description,
        "status": "proposed",
        "impact_report": {
            "level": impact_level,
            "affected_blocks": affected_blocks_report,
            "affected_foreshadowings": affected_foreshadowings,
            "affected_questions": affected_questions,
        },
    })

    level_labels = {"minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    result = {
        "change_id": change["id"],
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_blocks": len(affected_blocks),
        "affected_foreshadowings": len(affected_foreshadowings),
        "affected_questions": len(affected_questions),
        "has_concrete_changes": bool(outline_new_value),
        "proposed_fields": list(outline_new_value.keys()),
        "next_steps": "作者需决策：proceed / adjust / abandon",
    }
    if parse_warnings:
        result["warnings"] = parse_warnings
    return result
