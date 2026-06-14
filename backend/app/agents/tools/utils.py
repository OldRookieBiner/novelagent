"""共享工具函数

从 agent_tools.py 提取的公共函数，供所有工具使用。
Store 返回 dict，不再需要 _serialize。
"""

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.tool_context import get_project_id
from app.utils.text import tokenize_chinese


def _kb() -> KnowledgeBaseService:
    """Get KnowledgeBaseService for the current project context.

    Raises ValueError if project_id is not set in tool_context.
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")
    return KnowledgeBaseService(project_id)


def _get_current_value(kb: KnowledgeBaseService, target_type: str, target_id: int) -> dict:
    """Get the current value of a knowledge base object for comparison.

    Store 返回 dict，直接返回即可。
    """
    if target_type == "world_setting":
        obj = kb.world_setting.get()
        if obj and obj.get("id") == target_id:
            return obj
    elif target_type == "character":
        chars = kb.characters.list_characters()
        for c in chars:
            if c["id"] == target_id:
                return c
    elif target_type == "foreshadowing":
        f = kb.foreshadowings.get(target_id)
        if f:
            return f
    elif target_type == "style":
        style = kb.styles.get_constraints()
        if style and style.get("id") == target_id:
            return style
    elif target_type == "outline":
        outline = kb.outlines.get()
        if outline and outline.get("id") == target_id:
            return outline
    elif target_type == "relation":
        relations = kb.characters.list_relations()
        for r in relations:
            if r["id"] == target_id:
                return r
    return {}


def _extract_keywords(old_value: dict, new_value: dict, description: str) -> list[str]:
    """Extract search keywords from the change description and values.
    
    使用 tokenize_chinese 替代 .split()，正确处理中文分词。
    """
    keywords = []
    for word in tokenize_chinese(description):
        if len(word) >= 2:
            keywords.append(word)
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        for key in new_value:
            if new_value.get(key) != old_value.get(key):
                val = new_value[key]
                if isinstance(val, str):
                    for word in tokenize_chinese(val):
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
            chars = kb.characters.list_characters()
            char_names = [c["name"] for c in chars if c.get("name")]
            # 按名字长度降序排列，避免短名误匹配
            char_names.sort(key=len, reverse=True)
            for name in char_names:
                if name in text:
                    found.append(name)
            return found
        except Exception:
            pass  # KB 查询失败，降级

    # 降级路径：中文人名模式匹配
    import re
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


def parse_json_param(value: str | list | dict, default, param_name: str = "") -> tuple:
    """解析 JSON 字符串参数，返回 (解析结果, 警告信息)

    如果 value 已经是目标类型（与 default 同类型），直接返回。
    如果解析失败，返回 default 和警告信息。

    Args:
        value: 输入值（可能是 JSON 字符串或已是目标类型）
        default: 解析失败时的默认返回值（同时作为类型参考）
        param_name: 参数名（用于警告信息）
    """
    import json
    if isinstance(value, type(default)):
        return value, None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, type(default)):
                return parsed, None
            warning = f"参数 {param_name} JSON 解析类型不匹配，使用默认值"
            return default, warning
        except json.JSONDecodeError as e:
            warning = f"参数 {param_name} JSON 解析失败({e})，使用默认值"
            return default, warning
    warning = f"参数 {param_name} 类型不支持，使用默认值"
    return default, warning
