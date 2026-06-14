"""扩展世界观工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb
from app.utils.text import tokenize_chinese


@tool
async def expand_world_setting(aspect: str, description: str) -> dict:
    """在特定方向扩展世界观设定。

    自动评估扩展对已有内容的影响，检查与红色设定的冲突。
    扩展内容会写入知识库对应层级。

    Args:
        aspect: 扩展方向 - "location"(地点), "rule"(规则), "culture"(文化), "history"(历史), "technology"(技术)
        description: 扩展内容的自然语言描述
    """
    kb = _kb()
    ws = kb.world_setting.get()

    if not ws:
        return {"error": "世界观尚未创建，请先完成创意孵化阶段"}

    tiered = ws.get("tiered_settings") or {}
    red_settings = tiered.get("red", []) if isinstance(tiered, dict) else []
    contradictions = []
    for rule in red_settings:
        rule_text = rule if isinstance(rule, str) else str(rule)
        for word in tokenize_chinese(description):
            if len(word) >= 2 and word in rule_text:
                contradictions.append(rule_text[:80])

    impact_level = "none"
    impact_detail = "扩展不与现有🔴设定冲突"
    if contradictions:
        impact_level = "severe"
        impact_detail = f"扩展可能与🔴设定冲突：{'; '.join(contradictions[:3])}"

    keywords = [w for w in tokenize_chinese(description) if len(w) >= 2][:5]
    affected = kb.search_chapters_for_references(keywords) if keywords else []

    if affected and impact_level != "severe":
        impact_level = "minor"

    # 将扩展内容实际写入数据库（追加到 red/yellow/green 对应层级）
    tier_map = {"rule": "red", "culture": "yellow", "history": "yellow", "technology": "yellow", "location": "green"}
    target_tier = tier_map.get(aspect, "yellow")
    updated_tiered = dict(tiered) if tiered else {}
    if target_tier not in updated_tiered:
        updated_tiered[target_tier] = []
    updated_tiered[target_tier].append(f"[扩展-{aspect}] {description}")
    kb.world_setting.update_by_id(ws["id"], {"tiered_settings": updated_tiered})

    return {
        "aspect": aspect,
        "description": description,
        "impact_level": impact_level,
        "impact_detail": impact_detail,
        "affected_chapters": len(affected),
        "contradictions": contradictions,
        "suggestion": "可以安全扩展" if impact_level == "none" else "建议先解决冲突再扩展",
        "written": True,
        "tier": target_tier,
    }
