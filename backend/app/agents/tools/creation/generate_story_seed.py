"""生成故事种子工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id


@tool
async def generate_story_seed(
    seed_narrative: str,
    core_tension: str = "",
    protagonist_archetype: str = "",
    world_tone: str = "",
    emotional_tone: str = "",
) -> dict:
    """Generate and save the story seed document.

    The story seed is a narrative description (not a form) that captures
    the essence of the story — its atmosphere, protagonist, and core tension.
    Use when the user wants to crystallize their story idea.

    Args:
        seed_narrative: 300-500 word narrative that captures the story's atmosphere and core appeal
        core_tension: The ultimate conflict/question of the story
        protagonist_archetype: Who the protagonist is, what they want, what's stopping them
        world_tone: One-sentence description of the world's unique texture
        emotional_tone: How readers should feel after finishing (e.g., "悲壮中带着希望")
    """
    from app.database import SessionLocal
    from app.models.outline import Outline

    project_id = get_project_id()
    db = SessionLocal()
    committed = False

    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if not outline:
            outline = Outline(project_id=project_id)
            db.add(outline)
            db.flush()

        # Store story seed in outline summary field as a narrative block
        seed_block = seed_narrative
        if core_tension:
            seed_block += f"\n\n核心张力：{core_tension}"
        if protagonist_archetype:
            seed_block += f"\n\n主角原型：{protagonist_archetype}"
        if world_tone:
            seed_block += f"\n\n世界基调：{world_tone}"
        if emotional_tone:
            seed_block += f"\n\n情感基调：{emotional_tone}"

        outline.summary = seed_block
        db.commit()
        committed = True

        return {
            "action": "created",
            "seed_length": len(seed_narrative),
            "message": "故事种子已生成并写入知识库",
        }
    except Exception as e:
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
