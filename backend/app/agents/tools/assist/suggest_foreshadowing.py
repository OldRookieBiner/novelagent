"""伏笔建议工具

增强：未解释现象扫描 + reasoning 字段。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb
from app.utils.text import _jieba_available

# J1: Stopwords for foreshadowing suggestion
_SUGGEST_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "吗",
}


@tool
async def suggest_foreshadowing(current_chapter: int) -> dict:
    """基于当前情节块和已有内容，建议伏笔放置位置和方向。

    分析当前情节块、活跃伏笔和最近章节中未追踪的神秘元素。

    Args:
        current_chapter: 当前章节号
    """
    kb = _kb()

    block = kb.plots.get_current_plot_block(current_chapter)
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    active = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]

    if not block:
        return {"suggestion": "当前没有情节块信息，建议先完成结构设计"}

    suggestions = []
    for question in (block.get("questions_to_raise") or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
            "reasoning": f"此问题是当前情节块需要提出的关键问题，在提出前埋下伏笔可以增加悬念",
        })

    if len(active) < 3 and block.get("chapter_end") and block.get("chapter_start"):
        span = block["chapter_end"] - block["chapter_start"]
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
                "reasoning": "长情节块中伏笔密度不足会导致读者缺乏悬念感，建议每 2-3 章至少有 1 个活跃伏笔",
            })

    # 增强功能：未解释现象扫描
    unexplained = []
    recent_chapters = []
    for ch_offset in range(3):
        ch_num = current_chapter - ch_offset
        if ch_num > 0:
            ch = kb.chapters.get_by_number(ch_num)
            if ch and ch.get("content"):
                recent_chapters.append((ch_num, ch["content"]))

    if recent_chapters:
        # 获取已追踪的伏笔内容关键词
        tracked_contents = set()
        for f in active:
            content = f.get("content", "")
            if content:
                for word in content.split("，")[:3]:
                    if len(word) >= 2:
                        tracked_contents.add(word)

        # 简单检测：找出现两次以上的神秘元素（物品/事件/人物描述）
        from app.utils.text import tokenize_chinese
        word_freq = {}
        for ch_num, content in recent_chapters:
            tokens = tokenize_chinese(content)
            for token in tokens:
                if len(token) >= 3:
                    word_freq[token] = word_freq.get(token, 0) + 1

        # 找出高频但未在伏笔中追踪的词
        for word, freq in sorted(word_freq.items(), key=lambda x: -x[1]):
            if freq >= 2 and word not in tracked_contents:
                unexplained.append({"element": word, "occurrences": freq})
                if len(unexplained) >= 3:
                    break

        for ue in unexplained:
            suggestions.append({
                "type": "未解释现象",
                "content": f"「{ue['element']}」在最近章节出现了 {ue['occurrences']} 次但未被追踪为伏笔",
                "reasoning": f"反复出现的元素适合作为伏笔对象——读者会自然期待它有意义，将其正式纳入伏笔追踪体系可以增强叙事一致性",
            })

    return {
        "current_chapter": current_chapter,
        "plot_block": block.get("title") if block else None,
        "active_foreshadowings": len(active),
        "suggestions": suggestions,
    }
