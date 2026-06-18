"""生成章节内容工具"""

import logging

from langchain_core.tools import tool

from app.agents.tools.utils import _kb

logger = logging.getLogger(__name__)


def _compute_style_snapshot(content: str) -> dict:
    """从章节文本计算风格统计指标

    指标：
        - paragraph_count / avg_paragraph_length / dialogue_ratio / avg_sentence_length（基础）
        - ai_marker_density: FORBIDDEN_WORDS 字符出现率（命中字符数 / 总字符数）
        - sentence_variety: 句长标准差（≥2 句时有效）
    """
    import re as _re
    from statistics import stdev

    from app.agents.constants import FORBIDDEN_WORDS

    if not content or not content.strip():
        return {
            "paragraph_count": 0,
            "avg_paragraph_length": 0.0,
            "dialogue_ratio": 0.0,
            "avg_sentence_length": 0.0,
            "ai_marker_density": 0.0,
            "sentence_variety": 0.0,
        }

    total_chars = len(content)
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    paragraph_count = len(paragraphs) if paragraphs else 1
    avg_paragraph_length = sum(len(p) for p in paragraphs) / paragraph_count

    dialogue_chars = 0
    for m in _re.finditer(r"「([^」]*)」", content):
        dialogue_chars += len(m.group(1))
    for m in _re.finditer(r"\u201c([^\u201d]*)\u201d", content):
        dialogue_chars += len(m.group(1))
    quote_open = False
    start = 0
    for i, ch in enumerate(content):
        if ch == '"':
            if not quote_open:
                quote_open = True
                start = i + 1
            else:
                dialogue_chars += len(content[start:i])
                quote_open = False

    dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0.0

    sentence_ends = _re.split(r"[。！？…]+", content)
    sentences = [s for s in sentence_ends if s.strip()]
    avg_sentence_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0.0

    # AI 味浓度：禁用词字符出现率（命中字符总数 / 总字符数）
    safe_total = max(total_chars, 1)
    marker_chars = sum(content.count(w) * len(w) for w in FORBIDDEN_WORDS)
    ai_marker_density = marker_chars / safe_total

    # 句式变异性：句长标准差（≥2 句时计算，否则 0）
    if len(sentences) >= 2:
        sentence_variety = stdev(len(s) for s in sentences)
    else:
        sentence_variety = 0.0

    return {
        "paragraph_count": paragraph_count,
        "avg_paragraph_length": round(avg_paragraph_length, 1),
        "dialogue_ratio": round(dialogue_ratio, 3),
        "avg_sentence_length": round(avg_sentence_length, 1),
        "ai_marker_density": round(ai_marker_density, 4),
        "sentence_variety": round(sentence_variety, 2),
    }


@tool
async def generate_chapter_content(
    chapter_number: int,
    chapter_title: str,
    content: str,
    word_count: int = 0,
) -> dict:
    """生成并保存完整章节内容。

    这是写作章节的主要工具。创建章节正文并��步更新风格统计。
    注意：追踪参数（伏笔、时间线、节奏评分）建议改用 record_chapter_meta 工具单独记录。

    Prerequisites:
        - 章节大纲必须已确认（使用 generate_chapter_outline 生成并确认）

    Args:
        chapter_number: 章节号（如 1）
        chapter_title: 章节标题
        content: 完整章节正文内容
        word_count: 字数统计（可选，默认自动计算）

    Returns:
        dict:
            - action (str): 操作类型 - "created"(新建) 或 "updated"(更新)
            - chapter_number (int): 章节号
            - title (str): 章节标题
            - word_count (int): 字数
            - style_snapshot_created (bool): 风格快照是否创建成功
            - style_snapshot_error (str, optional): 风格快照创建失败原因
            - message (str): 操作结果描述
            - error (str, optional): 出错时的错误信息
            - hint (str, optional): 出错时的建议操作
    """
    kb = _kb()

    # 检查当前章是否有已确认的大纲
    try:
        co = kb.outlines.get_chapter_outline(chapter_number)
        if co and not co.get("confirmed"):
            return {
                "error": f"第{chapter_number}章大纲尚未确认，请先审查并确认章节大纲后再写作",
                "hint": "使用 generate_chapter_outline 工具生成大纲，或提醒用户确认大纲",
            }
    except Exception as e:
        logger.error("大纲确认状态检查异常: %s", e)
        return {
            "error": f"大纲确认状态检查失败（数据库异常），为安全起见阻止写入: {e}",
            "hint": "请稍后重试，或联系管理员检查数据库状态",
        }

    # 1. 保存章节正文
    existing_co = kb.outlines.get_chapter_outline(chapter_number)
    if not existing_co:
        kb.outlines.create_chapter_outline({
            "chapter_number": chapter_number,
            "title": chapter_title,
        })

    chapter_result = kb.chapters.save_content(chapter_number, content, word_count or len(content))
    existing_chapter = chapter_result.get("id") is not None

    # 2. 风格快照
    style_snapshot_created = False
    style_snapshot_error = None
    if content and content.strip():
        try:
            snapshot_data = _compute_style_snapshot(content)
            snapshot_data["chapter_number"] = chapter_number
            kb.styles.create_snapshot(snapshot_data)
            style_snapshot_created = True
        except Exception as e:
            style_snapshot_error = str(e)
            logger.warning("风格快照创建失败: %s", e)

    result = {
        "action": "created" if not existing_chapter else "updated",
        "chapter_number": chapter_number,
        "title": chapter_title,
        "word_count": word_count or len(content),
        "style_snapshot_created": style_snapshot_created,
        "style_snapshot_error": style_snapshot_error,
        "message": f"第{chapter_number}章「{chapter_title}」已写入（{word_count or len(content)}字）",
    }
    return result
