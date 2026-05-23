# backend/app/agents/services/chapter_service.py
"""章节生成/审核/重写核心服务

MVP 方案：生成类 tool 在完成后返回摘要+预览，
用户在 WritingPanel 查看完整章节。
流式输出在后续迭代通过 side channel SSE 实现。
"""

import json
from sqlalchemy.orm import Session
from app.models.outline import ChapterOutline
from app.models.chapter import Chapter
from app.agents.tool_context import get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.utils.logger import get_logger

logger = get_logger(__name__)



def _calc_max_tokens(target_words: int) -> int:
    """根据目标字数动态计算 max_tokens"""
    return max(int(target_words * 2.5) + 512, 8192)


async def generate_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """生成章节正文，完成后写入 DB，返回摘要"""
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()
    if not outline:
        return {"error": f"第{chapter_number}章大纲不存在"}

    prompt = f"""请根据以下信息撰写第{chapter_number}章「{outline.title}」的正文：

章节大纲：
- 场景：{outline.scene or ''}
- 出场人物：{outline.characters or ''}
- 情节要点：{outline.plot or ''}
- 冲突：{outline.conflict or ''}
- 结尾：{outline.ending or ''}

目标字数：{outline.target_words or 3000}字

请直接输出章节正文，不要输出标题或其他说明。"""

    llm_service = resolve_llm_service(get_model_config_id(), get_user_id())
    max_tokens = _calc_max_tokens(outline.target_words or 3000)

    full_content = ""
    try:
        async for chunk in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ):
            if chunk:
                full_content += chunk
    except Exception as e:
        logger.error(f"Chapter generation failed: {e}")
        return {"error": f"生成失败: {str(e)}"}

    if not full_content.strip():
        return {"error": "生成结果为空，请重试"}

    # 写入 DB
    try:
        chapter = db.query(Chapter).filter(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        ).first()
        if chapter:
            chapter.content = full_content
        else:
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=outline.title,
                content=full_content,
                target_words=outline.target_words or 3000,
            )
            db.add(chapter)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save chapter: {e}")
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(full_content)
    preview = full_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章「{outline.title}」已生成（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title,
        "word_count": word_count,
        "preview": preview,
    }


async def review_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """审核章节，返回结构化审核结果"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    prompt = f"""请审核以下章节内容，按 JSON 格式返回审核结果。

章节大纲：
- 标题：{outline.title if outline else ''}
- 情节要点：{outline.plot if outline else ''}

章节正文（前2000字）：
{chapter.content[:2000]}

请严格按以下 JSON 格式返回，不要包含其他内容：
{{
  "passed": true/false,
  "scores": {{"情节": 1-10, "人物": 1-10, "文笔": 1-10, "逻辑": 1-10, "节奏": 1-10}},
  "issues": [{{"type": "逻辑/情节/人物/文笔", "location": "位置描述", "description": "问题描述"}}],
  "suggestions": "整体改进建议"
}}"""

    llm_service = resolve_llm_service(get_model_config_id(), get_user_id())
    try:
        result_text = await llm_service.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        review_result = json.loads(result_text)
        return {"success": True, "review": review_result}
    except json.JSONDecodeError:
        return {"success": True, "review": {"passed": True, "raw": result_text}, "warning": "审核结果解析不完整"}
    except Exception as e:
        logger.error(f"Review failed: {e}")
        return {"error": f"审核失败: {str(e)}"}


async def rewrite_chapter(db: Session, project_id: int, chapter_number: int, review_feedback: str) -> dict:
    """根据审核意见重写章节，完成后写入 DB，返回摘要"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在"}

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    prompt = f"""请根据审核意见重写第{chapter_number}章「{outline.title if outline else ''}」。

原章节正文：
{chapter.content}

审核意见：
{review_feedback}

章节大纲：
- 情节要点：{outline.plot if outline else ''}
- 冲突：{outline.conflict if outline else ''}
- 结尾：{outline.ending if outline else ''}

目标字数：{outline.target_words or 3000}字

请直接输出重写后的章节正文。"""

    llm_service = resolve_llm_service(get_model_config_id(), get_user_id())
    max_tokens = _calc_max_tokens(outline.target_words if outline else 3000)

    full_content = ""
    try:
        async for chunk in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ):
            if chunk:
                full_content += chunk
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        return {"error": f"重写失败: {str(e)}"}

    if not full_content.strip():
        return {"error": "重写结果为空，请重试"}

    try:
        chapter.content = full_content
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(full_content)
    preview = full_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章已重写（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title if outline else f"第{chapter_number}章",
        "word_count": word_count,
        "preview": preview,
    }
