# backend/app/agents/services/edit_service.py
"""精细编辑服务

提供段落级编辑能力：edit_paragraph, insert_scene, revise_section, polish_prose。
精确操作（edit_paragraph, insert_scene）不调 LLM，直接 DB 读写。
语义操作（revise_section, polish_prose）调 LLM 执行修改。
"""

import re

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.outline import ChapterOutline
from app.agents.tool_context import get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service  # 共享 LLM 服务解析函数
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_paragraphs(content: str) -> list[str]:
    """规范化段落分割

    处理 \r\n、\n\n、连续空行、HTML 标签等格式变体。
    返回非空段落列表。
    """
    # 移除 HTML 标签
    clean = re.sub(r'<[^>]+>', '', content)
    # 统一换行符
    clean = clean.replace('\r\n', '\n').replace('\r', '\n')
    # 按连续换行分割段落
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', clean)]
    return [p for p in paragraphs if p]


def _join_paragraphs(paragraphs: list[str]) -> str:
    """段落列表拼接回纯文本"""
    return '\n\n'.join(paragraphs)


async def edit_paragraph(
    db: Session,
    project_id: int,
    chapter_number: int,
    paragraph_index: int,
    new_content: str,
) -> dict:
    """替换指定段落（0-indexed）"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    paragraphs = _normalize_paragraphs(chapter.content)
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return {"error": f"段落索引超出范围（共{len(paragraphs)}段）"}

    old_para = paragraphs[paragraph_index]
    paragraphs[paragraph_index] = new_content
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()

    return {
        "success": True,
        "paragraph_index": paragraph_index,
        "old_preview": old_para[:50],
        "new_preview": new_content[:50],
    }


async def insert_scene(
    db: Session,
    project_id: int,
    chapter_number: int,
    position: int,
    scene_content: str,
) -> dict:
    """在指定位置前插入场景（0=开头，N=末尾）"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter:
        return {"error": f"第{chapter_number}章不存在"}

    paragraphs = _normalize_paragraphs(chapter.content) if chapter.content else []
    if position < 0 or position > len(paragraphs):
        return {"error": f"插入位置超出范围（0-{len(paragraphs)}）"}

    paragraphs.insert(position, scene_content)
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()

    return {"success": True, "position": position, "total_paragraphs": len(paragraphs)}


async def revise_section(
    db: Session,
    project_id: int,
    chapter_number: int,
    instruction: str,
    start_para: int = 0,
    end_para: int = -1,
) -> dict:
    """按指令重写段落范围"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    paragraphs = _normalize_paragraphs(chapter.content)
    if end_para == -1:
        end_para = len(paragraphs) - 1
    if start_para < 0 or end_para >= len(paragraphs) or start_para > end_para:
        return {"error": f"段落范围超出（共{len(paragraphs)}段）"}

    target = '\n\n'.join(paragraphs[start_para:end_para + 1])

    # 获取 LLM 服务
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    # 获取章节大纲上下文
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    prompt = f"""修改以下小说段落。

修改指令：{instruction}

章节背景：
- 章节标题：{outline.title if outline else ''}
- 情节要点：{outline.plot if outline else ''}
- 冲突：{outline.conflict if outline else ''}

原文段落：
{target}

请直接输出修改后的段落，不要输出其他说明。"""

    try:
        revised = await llm.chat([{"role": "user", "content": prompt}], max_tokens=8192)
    except Exception as e:
        return {"error": f"修改失败: {str(e)}"}

    if not revised or not revised.strip():
        return {"error": "修改结果为空，请重试"}

    # 替换原段落范围
    paragraphs[start_para:end_para + 1] = [revised.strip()]
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()

    return {"success": True, "preview": revised[:200], "range": f"段落{start_para+1}-{end_para+1}"}


async def polish_prose(
    db: Session,
    project_id: int,
    chapter_number: int,
    style_instruction: str = "",
) -> dict:
    """保持情节不变，优化文笔"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    # 获取 LLM 服务
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    style_note = f"\n风格要求：{style_instruction}" if style_instruction else ""
    prompt = f"""请润色以下小说章节的文笔，保持情节、人物对话、结构完全不变。
只优化语言的流畅度、节奏感和文学性。{style_note}

原文：
{chapter.content}

请直接输出润色后的完整章节。"""

    try:
        polished = await llm.chat([{"role": "user", "content": prompt}], max_tokens=16384)
    except Exception as e:
        return {"error": f"润色失败: {str(e)}"}

    if not polished or not polished.strip():
        return {"error": "润色结果为空，请重试"}

    chapter.content = polished.strip()
    db.commit()

    word_count = len(polished)
    preview = polished[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章已润色",
        "word_count": word_count,
        "preview": preview,
    }
