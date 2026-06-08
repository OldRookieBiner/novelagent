"""共享工具函数

从 agent_tools.py 提取的公共函数，供所有工具使用。
"""

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.tool_context import get_project_id


def _kb() -> KnowledgeBaseService:
    """Get KnowledgeBaseService for the current project context.

    Raises ValueError if project_id is not set in tool_context.
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")
    return KnowledgeBaseService(project_id)


def _serialize(obj) -> dict | list | str:
    """Serialize an ORM object to a dict, handling detached sessions."""
    if obj is None:
        return {}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dict__") and hasattr(obj, "__table__"):
        return {
            c.name: getattr(obj, c.name)
            for c in obj.__table__.columns
            if c.name not in ("created_at", "updated_at")
        }
    return str(obj)


def _get_current_value(kb: KnowledgeBaseService, target_type: str, target_id: int) -> dict:
    """Get the current value of a knowledge base object for comparison."""
    if target_type == "world_setting":
        obj = kb.get_world_setting()
        if obj and obj.id == target_id:
            return _serialize(obj)
    elif target_type == "character":
        chars = kb.get_characters()
        for c in chars:
            if c.id == target_id:
                return _serialize(c)
    elif target_type == "foreshadowing":
        foreshadowings = kb.get_foreshadowings()
        for f in foreshadowings:
            if f.id == target_id:
                return _serialize(f)
    elif target_type == "style":
        style = kb.get_style_constraints()
        if style and style.id == target_id:
            return _serialize(style)
    elif target_type == "outline":
        outline = kb.get_outline()
        if outline and outline.id == target_id:
            return _serialize(outline)
    elif target_type == "relation":
        relations = kb.get_relations()
        for r in relations:
            if r.id == target_id:
                return _serialize(r)
    return {}


def _extract_keywords(old_value: dict, new_value: dict, description: str) -> list[str]:
    """Extract search keywords from the change description and values."""
    keywords = []
    for word in description.split():
        if len(word) >= 2:
            keywords.append(word)
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        for key in new_value:
            if new_value.get(key) != old_value.get(key):
                val = new_value[key]
                if isinstance(val, str):
                    for word in val.split():
                        if len(word) >= 2:
                            keywords.append(word)
    return keywords[:20]


def _grade_impact(
    affected_chapters: list, target_type: str, new_value: dict, old_value: dict
) -> tuple[str, str]:
    """Grade the impact level of a proposed change.

    Returns (level, detail) where level is one of:
    none, minor, moderate, severe
    """
    total_paragraphs = sum(len(ch.get("matching_paragraphs", [])) for ch in affected_chapters)
    total_chapters = len(affected_chapters)

    if total_chapters == 0:
        return "none", "变更不影响任何已写内容"

    if total_chapters <= 1 and total_paragraphs <= 2:
        return "minor", f"轻微影响：{total_chapters} 章、{total_paragraphs} 段提及，读者不易察觉"

    if total_chapters <= 3 and total_paragraphs <= 5:
        return "moderate", f"中度影响：{total_chapters} 章、{total_paragraphs} 段提及，细心读者可能发现矛盾"

    return "severe", f"严重影响：{total_chapters} 章、{total_paragraphs} 段提及，核心情节可能直接矛盾"


def _build_state_for_review(project_id: int, chapter_number: int) -> dict:
    """Build a minimal NovelState dict for review/rewrite message construction.

    Reads characters, relations, world_setting, chapter_outlines, written_chapters
    from KnowledgeBaseService to satisfy _build_review_messages / _build_rewrite_messages contracts.
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline

    kb = KnowledgeBaseService(project_id)

    # Outline for chapter_count and target words
    outline = kb.get_outline()
    target_words = 100000
    if outline:
        target_words = (outline.chapter_count_confirmed or outline.chapter_count_suggested or 100) * 3000

    # Characters
    chars_raw = kb.get_characters()
    characters = []
    for c in chars_raw:
        characters.append({
            "id": c.id, "name": c.name, "role": getattr(c, "role", ""),
            "personality": getattr(c, "personality", ""),
            "appearance": getattr(c, "appearance", ""),
            "backstory": getattr(c, "backstory", ""),
            "catchphrase": getattr(c, "catchphrase", ""),
            "habit_action": getattr(c, "habit_action", ""),
            "deep_fear": getattr(c, "deep_fear", ""),
            "core_motivation": getattr(c, "core_motivation", ""),
            "growth_arc": getattr(c, "growth_arc", ""),
            "signature_item": getattr(c, "signature_item", ""),
        })

    # Relations
    relations_raw = kb.get_relations()
    relations = []
    for r in relations_raw:
        relations.append({
            "character_a_id": getattr(r, "character_a_id", None),
            "character_b_id": getattr(r, "character_b_id", None),
            "relation_type": getattr(r, "relation_type", ""),
            "current_status": getattr(r, "current_status", ""),
        })

    # Evolution plans
    evolution_plans_raw = kb.get_relations_with_plans()
    evolution_plans = []
    for ep in evolution_plans_raw:
        evolution_plans.append(ep if isinstance(ep, dict) else _serialize(ep))

    # World setting
    ws = kb.get_world_setting()

    # Chapter outlines
    chapter_outlines = []
    db = SessionLocal()
    try:
        co_list = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number).all()
        for co in co_list:
            chapter_outlines.append({
                "chapter_number": co.chapter_number,
                "title": co.title or "",
                "scene": co.scene,
                "characters": co.characters,
                "plot": co.plot or "",
                "conflict": co.conflict,
                "turning_point": co.turning_point,
                "hook": co.hook,
                "transition": co.transition,
                "ending": co.ending,
                "target_words": co.target_words,
            })
    finally:
        db.close()

    # Written chapters (timeline summaries for context)
    timeline = kb.get_timeline()
    written_chapters = []
    for t in timeline:
        written_chapters.append({
            "chapter_number": t.chapter_number,
            "summary": getattr(t, "summary", ""),
        })

    # Collected info (style preferences, genre)
    collected_info = {}
    if outline:
        collected_info["novelType"] = getattr(outline, "novel_type", "") or ""
    style = kb.get_style_constraints()
    if style:
        collected_info["stylePreference"] = getattr(style, "style_preference", "") or ""
    collected_info["targetWords"] = target_words

    # 加载 prompt 模板
    from app.agents.prompts import DEFAULT_PROMPTS
    _prompts = DEFAULT_PROMPTS

    return {
        "project_id": project_id,
        "current_chapter": chapter_number,
        "characters": characters,
        "relations": relations,
        "evolution_plans": evolution_plans,
        "evolution_records": [],
        "world_setting": _serialize(ws) if ws else {},
        "chapter_outlines": chapter_outlines,
        "written_chapters": written_chapters,
        "collected_info": collected_info,
        "_prompts": _prompts,
        "_context_window": 32000,
    }


# ========================================================================
# 方案 B 增强所需的辅助函数
# ========================================================================


def _mood_to_tension(mood: str) -> int:
    """情绪标签转张力分值（1-5）"""
    mapping = {
        "紧张": 5,
        "悬疑": 5,
        "高潮": 5,
        "转折": 4,
        "冲突": 4,
        "日常": 2,
        "温馨": 2,
        "舒缓": 1,
        "平静": 1,
    }
    return mapping.get(mood, 3)


def _compare_with_anchor(content: str, anchor: str) -> dict:
    """风格锚点对比"""
    anchor_words = anchor.split("，")[:5]
    found = []
    for word in anchor_words:
        if word in content:
            found.append(word)

    return {
        "anchor_words": anchor_words,
        "found_words": found,
        "match_rate": len(found) / max(len(anchor_words), 1),
    }


def _extract_names(text: str, kb: KnowledgeBaseService | None = None) -> list[str]:
    """从文本提取角色名

    优先使用知识库角色名精确匹配，无 KB 时降级为中文人名模式匹配。
    """
    found = []

    # 优先路径：从知识库获取角色名，在文本中查找
    if kb is not None:
        try:
            chars = kb.get_characters()
            char_names = [c.name for c in chars if c.name]
            # 按名字长度降序排列，避免短名误匹配（如"李"匹配"李白"）
            char_names.sort(key=len, reverse=True)
            for name in char_names:
                if name in text:
                    found.append(name)
            return found
        except Exception:
            pass  # KB 查询失败，降级

    # 降级路径：中文人名模式匹配（2-3字常见人名）
    import re
    # 排除常见非人名双字组合
    stopwords = {"但是", "因为", "所以", "如果", "虽然", "已经", "可以", "这个",
                 "那个", "什么", "怎么", "这样", "那样", "他们", "我们", "她们",
                 "自己", "不是", "没有", "知道", "看到", "一个", "就是", "还是"}
    candidates = re.findall(r"[一-龥]{2,3}", text)
    for c in candidates:
        if c not in stopwords and c not in found:
            found.append(c)
    return found


def _extract_times(text: str) -> list[str]:
    """从文本提取时间表达"""
    import re
    patterns = [
        r"第[一二三四五六七八九十\d]+天",
        r"第[一二三四五六七八九十\d]+年",
        r"\d{1,2}月\d{1,2}日",
        r"早上|中午|晚上|深夜|黎明",
    ]
    times = []
    for p in patterns:
        times.extend(re.findall(p, text))
    return times
