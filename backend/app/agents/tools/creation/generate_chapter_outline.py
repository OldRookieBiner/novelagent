"""生成章节大纲工具"""

import json as _json
import logging

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id

logger = logging.getLogger(__name__)


@tool
async def generate_chapter_outline(
    chapter_number: int,
    title: str,
    scene: str = "",
    characters: str = "",
    plot: str = "",
    conflict: str = "",
    turning_point: str = "",
    hook: str = "",
    transition: str = "",
    ending: str = "",
    target_words: int = 3000,
    opening_state: str = "",
    emotional_arc: str = "",
    key_scenes: str = "[]",
    pacing_note: str = "",
) -> dict:
    """Generate or update the outline for a specific chapter.

    Use this when the user asks to plan or outline a specific chapter BEFORE writing it.
    This creates a detailed writing blueprint that will be referenced during chapter writing.

    Args:
        chapter_number: Chapter number (e.g., 1)
        title: Chapter title (e.g., "暗潮涌动")
        scene: Scene setting (e.g., "皇宫大殿·深夜")
        characters: Characters appearing in this chapter (e.g., "李承泽, 苏婉清")
        plot: Key plot points of this chapter
        conflict: Main conflict in this chapter
        turning_point: Turning point in this chapter
        hook: Suspense hook at chapter end
        transition: Transition/bridge to next chapter
        ending: Chapter ending description
        target_words: Target word count (default 3000)
        opening_state: State at chapter opening — character/situation status, links to previous chapter
        emotional_arc: Emotional trajectory (e.g., "压抑→紧张→爆发→余波")
        key_scenes: JSON string list of key scenes, each: {"seq": 1, "desc": "场景描述", "mood": "情绪"}
        pacing_note: Pacing instruction (e.g., "前慢后快，2/3处转折")
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline

    try:
        scenes = _json.loads(key_scenes) if isinstance(key_scenes, str) else key_scenes
    except _json.JSONDecodeError:
        logger.warning("key_scenes JSON 解析失败，使用空列表: %s", key_scenes[:100])
        scenes = []

    project_id = get_project_id()
    db = SessionLocal()
    committed = False

    try:
        chapter_outline = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()

        if chapter_outline:
            # 更新现有大纲（即使已确认也允许更新，但重置确认状态）
            chapter_outline.title = title
            if scene:
                chapter_outline.scene = scene
            if characters:
                chapter_outline.characters = characters
            if plot:
                chapter_outline.plot = plot
            if conflict:
                chapter_outline.conflict = conflict
            if turning_point:
                chapter_outline.turning_point = turning_point
            if hook:
                chapter_outline.hook = hook
            if transition:
                chapter_outline.transition = transition
            if ending:
                chapter_outline.ending = ending
            chapter_outline.target_words = target_words
            if opening_state:
                chapter_outline.opening_state = opening_state
            if emotional_arc:
                chapter_outline.emotional_arc = emotional_arc
            if scenes:
                chapter_outline.key_scenes = scenes
            if pacing_note:
                chapter_outline.pacing_note = pacing_note
            # 重置确认状态，要求用户重新审查
            chapter_outline.confirmed = False
            action = "updated"
        else:
            # 创建新大纲
            chapter_outline = ChapterOutline(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                scene=scene or None,
                characters=characters or None,
                plot=plot or None,
                conflict=conflict or None,
                turning_point=turning_point or None,
                hook=hook or None,
                transition=transition or None,
                ending=ending or None,
                target_words=target_words,
                opening_state=opening_state or None,
                emotional_arc=emotional_arc or None,
                key_scenes=scenes if scenes else None,
                pacing_note=pacing_note or None,
                confirmed=False,
            )
            db.add(chapter_outline)
            action = "created"

        db.commit()
        committed = True

        return {
            "action": action,
            "chapter_number": chapter_number,
            "title": title,
            "confirmed": False,
            "message": f"第{chapter_number}章「{title}」大纲已{action}，请审查后确认",
        }

    except Exception as e:
        logger.error("generate_chapter_outline 失败: %s", e, exc_info=True)
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass
