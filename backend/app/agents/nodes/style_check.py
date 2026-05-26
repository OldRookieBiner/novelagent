"""风格检查节点

禁忌词快查 + 风格统计 + 对话样本提取。
"""

import re
from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.nodes.utils import find_chapter_by_number


async def style_check_node(state: NovelState) -> NovelState:
    """风格检查"""
    project_id = state["project_id"]
    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 找到刚写完的章节
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        return {**state}

    content = chapter.get("content", "")
    written_chapter_num = chapter.get("chapter_number", current_chapter - 1)

    if not content:
        return {**state}

    # 1. 禁忌词快查
    style = kb.get_style_constraints()
    taboo_violations = []
    if style and style.taboo_words:
        for word in style.taboo_words:
            if word in content:
                taboo_violations.append(word)

    # 2. 风格统计
    paragraphs = [p for p in content.split("\n") if p.strip()]
    paragraph_count = len(paragraphs)
    avg_para_len = sum(len(p) for p in paragraphs) / max(paragraph_count, 1)

    # 对话占比（以引号包围的内容）
    dialogue_chars = len(re.findall(r'[「"『].*?[」"』]', content))
    dialogue_ratio = dialogue_chars / max(len(content), 1)

    # 平均句长
    sentences = re.split(r'[。！？…]', content)
    sentences = [s for s in sentences if s.strip()]
    avg_sent_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

    kb.create_style_snapshot({
        "chapter_number": written_chapter_num,
        "paragraph_count": paragraph_count,
        "avg_paragraph_length": avg_para_len,
        "dialogue_ratio": round(dialogue_ratio, 3),
        "avg_sentence_length": round(avg_sent_len, 1),
    })

    return {**state}
