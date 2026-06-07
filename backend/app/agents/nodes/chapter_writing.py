"""章节正文生成节点（执行）

基于章节点 + 组装上下文 + 风格约束写正文。
"""

from app.agents.state import NovelState
from app.agents.constants import NODE_TEMPERATURES
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHAPTER_WRITING_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def chapter_writing_node(state: NovelState) -> NovelState:
    """基于章节点+上下文+风格约束写正文"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 从 state 读取 chapter_planning_node 的输出
    chapter_plan = state.get("chapter_plan", "（无章节点）")
    assembled_context = state.get("assembled_context", "")

    # 读取风格约束
    style = kb.get_style_constraints()
    style_text = ""
    if style:
        parts = []
        if style.taboo_words:
            parts.append(f"禁忌词：{', '.join(style.taboo_words)}")
        if style.style_anchor:
            parts.append(f"风格锚点：{style.style_anchor}")
        if style.abstract_rules:
            parts.append(f"抽象规则：{', '.join(style.abstract_rules)}")
        if parts:
            style_text = "\n".join(parts)

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "chapter_writing")

    # 目标字数
    outline = kb.get_outline()
    target_words = 3000
    if outline and outline.project:
        # 粗略估算
        target_words = max(1500, min(5000, (outline.project.target_words or 100000) // max(state.get("chapter_count", 30), 10)))

    # 获取 state 中的场景导演和 POV 信息
    scene_directions = state.get("scene_directions", "")
    if scene_directions:
        # 将 scene_directions 转为可读格式
        if isinstance(scene_directions, list):
            scene_text = ""
            for i, scene in enumerate(scene_directions):
                scene_text += f"\n场景{i+1}: {scene.get('location', '')} {scene.get('characters', '')}\n"
                scene_text += f"  POV: {scene.get('pov', '')}, 信息层级: {scene.get('info_level', '')}\n"
                scene_text += f"  情绪节拍: {scene.get('rhythm_beat', '')}, 感官: {scene.get('sense_channels', '')}\n"
                scene_text += f"  切入: {scene.get('entry_point', '')}, 切出: {scene.get('exit_point', '')}"
            scene_directions = scene_text
    else:
        scene_directions = "（无场景导演指令）"

    # 获取 POV
    pov_character = state.get("pov_character", "（无明确 POV）")

    # 获取前章收束画面
    last_chapter_closing_scene = state.get("last_chapter_closing_scene", "（无上章内容）")

    # 获取写作约束
    writing_constraints = state.get("writing_constraints", [])
    if writing_constraints:
        constraints_text = "## 本章写作约束（必须遵守）\n" + "\n".join(f"- {c}" for c in writing_constraints)
    else:
        constraints_text = "（无特殊约束）"

    if user_template:
        prompt_text = safe_format(user_template,
            chapter_node=chapter_plan,
            style_constraints=style_text,
            previous_context=assembled_context,
            target_words=str(target_words),
            scene_directions=scene_directions,
            pov_character=pov_character,
            last_chapter_closing_scene=last_chapter_closing_scene,
            writing_constraints=constraints_text,
        )
    else:
        prompt_text = safe_format(CHAPTER_WRITING_PROMPT,
            chapter_node=chapter_plan,
            style_constraints=style_text,
            previous_context=assembled_context,
            target_words=str(target_words),
            scene_directions=scene_directions,
            pov_character=pov_character,
            last_chapter_closing_scene=last_chapter_closing_scene,
            writing_constraints=constraints_text,
        )

    response = ""
    # 使用配置的温度，默认为 0.55
    writing_temperature = NODE_TEMPERATURES.get("chapter_writing", 0.55)
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=writing_temperature
    ):
        response += chunk

    # 保存章节内容到 DB（检查点瘦身：正文不入检查点）
    word_count = len(response)
    kb.save_chapter_content(current_chapter, response, word_count)

    # state 中只存元数据，写后自检链需要 content（同一次运行内可用）
    new_chapter = {
        "chapter_number": current_chapter,
        "content": response,
        "word_count": word_count,
    }

    return {
        "written_chapters": [new_chapter],
        "current_chapter": current_chapter + 1,
        # 清除写作工作记忆，避免下章误用
        "chapter_plan": None,
        "assembled_context": None,
    }
