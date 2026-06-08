"""重写章节工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id, get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.agents.constants import NODE_TEMPERATURES
from app.agents.rewrite_utils import _build_rewrite_messages, clean_chapter_content
from app.agents.tools.utils import _kb, _build_state_for_review


@tool
async def rewrite_chapter(chapter_number: int) -> dict:
    """Rewrite a chapter based on its latest review feedback.

    The chapter must have been reviewed first (review_feedback must exist).
    Generates new content, saves it to the database, increments rewrite_count,
    and clears the review state so it can be re-reviewed.

    Args:
        chapter_number: The chapter number to rewrite (e.g., 1, 2, 3)
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
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.models.chapter import Chapter

    db = SessionLocal()
    try:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return {"error": f"Chapter {chapter_number} outline not found"}

        chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == co.id
        ).first()
        if not chapter or not chapter.content:
            return {"error": f"Chapter {chapter_number} not found or has no content"}

        # Must have review feedback
        review_feedback = ""
        if chapter.review_result:
            review_feedback = (
                chapter.review_result.get("raw_response", "")
                or chapter.review_result.get("suggestions", "")
            )
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback
        if not review_feedback:
            return {"error": f"Chapter {chapter_number} has not been reviewed yet, use review_chapter first"}

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
        }
        original_content = chapter.content
        chapter_id = chapter.id
    finally:
        db.close()

    # Build state for rewrite message construction
    state = _build_state_for_review(project_id, chapter_number)

    # Build messages and call LLM
    messages = _build_rewrite_messages(
        state, chapter_outline_dict, original_content, review_feedback
    )
    try:
        response = await llm.chat(
            messages,
            temperature=NODE_TEMPERATURES["rewrite"],
            max_tokens=16384,
        )
        new_content = clean_chapter_content(response)
    except Exception as e:
        return {"error": f"Rewrite LLM call failed: {e}"}

    # Save to DB
    save_db = SessionLocal()
    committed = False
    try:
        ch = save_db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if ch:
            ch.content = new_content
            ch.word_count = len(new_content)
            ch.rewrite_count = (ch.rewrite_count or 0) + 1
            ch.review_passed = False
            ch.review_result = None
            ch.review_feedback = None
            save_db.commit()
            committed = True
            word_count = len(new_content)
        else:
            return {"error": "Chapter deleted during rewrite"}
    except Exception as e:
        return {"error": f"Failed to save rewrite result: {e}"}
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
        "action": "rewritten",
        "chapter_number": chapter_number,
        "word_count": word_count,
        "message": f"Chapter {chapter_number} rewritten ({word_count} chars), please review again",
    }
