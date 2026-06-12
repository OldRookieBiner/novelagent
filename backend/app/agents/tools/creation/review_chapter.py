"""审核章节工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id, get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.agents.constants import NODE_TEMPERATURES
from app.agents.review_utils import _build_review_messages, parse_review_result, check_review_passed
from app.agents.tools.utils import _kb, _build_state_for_review


@tool
async def review_chapter(chapter_number: int) -> dict:
    """Review a chapter for quality across 6 dimensions.

    Performs a comprehensive quality review analyzing plot consistency,
    character consistency, writing quality, emotional tension, AI flavor,
    and outline deviation. Results are saved to the database.

    Args:
        chapter_number: The chapter number to review (e.g., 1, 2, 3)
    """
    project_id = get_project_id()
    model_config_id = get_model_config_id()
    user_id = get_user_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # Resolve LLM service
    try:
        llm = resolve_llm_service(model_config_id, user_id)
    except ValueError as e:
        return {"error": f"Cannot resolve LLM config: {e}"}

    # 通过 _kb() 读取章节数据（统一走 tool_context）
    kb = _kb()
    chapter = kb.get_chapter_by_number(chapter_number)
    if not chapter or not chapter.content:
        return {"error": f"Chapter {chapter_number} not found or has no content"}

    # 获取章节大纲
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    db = SessionLocal()
    try:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return {"error": f"Chapter {chapter_number} outline not found"}
        chapter_outline_dict = {
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
            "opening_state": getattr(co, "opening_state", None),
            "emotional_arc": getattr(co, "emotional_arc", None),
            "key_scenes": getattr(co, "key_scenes", None),
            "pacing_note": getattr(co, "pacing_note", None),
        }
        chapter_outline_id = co.id
    finally:
        db.close()

    # Build state for review message construction
    state = _build_state_for_review(project_id, chapter_number)

    # Build messages and call LLM
    messages = _build_review_messages(state, chapter.content, chapter_outline_dict)
    try:
        response = await llm.chat(messages, temperature=NODE_TEMPERATURES["review"])
        review_result = parse_review_result(response)
        review_result["raw_response"] = response
        passed = check_review_passed(review_result)
    except Exception as e:
        return {"error": f"Review LLM call failed: {e}"}

    # Save to DB
    from app.models.chapter import Chapter
    save_db = SessionLocal()
    committed = False
    try:
        ch = save_db.query(Chapter).filter(
            Chapter.chapter_outline_id == chapter_outline_id
        ).first()
        if ch:
            ch.review_passed = passed
            ch.review_feedback = response
            ch.review_result = review_result
            save_db.commit()
            committed = True
    except Exception as e:
        return {"error": f"Failed to save review result: {e}"}
    finally:
        if not committed:
            try:
                save_db.rollback()
            except Exception:
                pass
        try:
            save_db.close()
        except Exception:
            pass

    return {
        "chapter_number": chapter_number,
        "passed": passed,
        "scores": review_result.get("scores", {}),
        "issues": review_result.get("issues", []),
        "suggestions": review_result.get("suggestions", ""),
        "message": f"Review {'passed' if passed else 'failed'} — "
                   f"{len(review_result.get('issues', []))} issues found",
    }
