"""提议设定变更工具"""

import json

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _get_current_value, _extract_keywords, _grade_impact


@tool
async def propose_setting_change(
    target_type: str,
    target_id: int,
    new_value: str,
    description: str,
) -> dict:
    """Propose a change to a knowledge base setting.

    Automatically triggers impact assessment. The change is NOT applied
    immediately — it creates a SettingChange record with status="proposed"
    and an impact report. The author must approve or abandon it.

    Args:
        target_type: What to change - "world_setting", "character",
                     "foreshadowing", "style", "outline", "relation"
        target_id: ID of the object to change
        new_value: JSON string describing the new value
        description: Natural language description of the proposed change
    """
    kb = _kb()

    old_value = _get_current_value(kb, target_type, target_id)

    try:
        new_value_parsed = json.loads(new_value) if isinstance(new_value, str) else new_value
    except json.JSONDecodeError:
        new_value_parsed = {"value": new_value}

    keywords = _extract_keywords(old_value, new_value_parsed, description)
    affected = kb.search_chapters_for_references(keywords)

    impact_level, impact_detail = _grade_impact(affected, target_type, new_value_parsed, old_value)

    impact_report = {
        "level": impact_level,
        "affected_chapters": len(affected),
        "affected_paragraphs": sum(len(ch.get("matching_paragraphs", [])) for ch in affected),
        "details": affected[:5],
        "grading_explanation": impact_detail,
    }

    change = kb.create_setting_change({
        "target_type": target_type,
        "target_id": target_id,
        "old_value": old_value,
        "new_value": new_value_parsed,
        "description": description,
        "status": "proposed",
        "impact_report": impact_report,
    })

    level_labels = {"none": "🟢 不影响", "minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    return {
        "change_id": change.id,
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_chapters": impact_report["affected_chapters"],
        "affected_paragraphs": impact_report["affected_paragraphs"],
        "detail": impact_detail,
        "next_steps": "作者需决策：proceed（按原方案修改）/ adjust（调整修改方案）/ abandon（放弃修改）",
    }
