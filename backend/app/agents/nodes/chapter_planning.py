"""章节点生成节点（决策）

基于上下文生成本章的章节点（因果链/钩子/场景规划）。
输出写入 state["chapter_plan"]，供 chapter_writing_node 使用。
"""

from app.agents.state import NovelState, ConfirmationType
from app.agents.constants import NODE_TEMPERATURES
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHAPTER_PLANNING_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def chapter_planning_node(state: NovelState) -> NovelState:
    """生成本章的章节点（因果链/钩子/场景规划）"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 使用 context_assembly_node 已组装的上下文
    assembled_context = state.get("assembled_context", "")

    # 补充 chapter_planning 需要的额外上下文
    current_block = kb.get_current_plot_block(current_chapter)
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    pending = kb.get_pending_foreshadowings()
    questions = kb.get_questions_for_chapter(current_chapter)

    # 格式化上下文
    plot_block_goal = ""
    if current_block:
        plot_block_goal = f"{current_block.title}"
        if current_block.must_happen:
            plot_block_goal += f"：{', '.join(current_block.must_happen)}"

    foreshadowing_text = "\n".join([
        f"- {f.content}（等级：{f.level}，状态：{f.status}）"
        for f in (overdue + pending[:5])
    ])
    questions_text = "\n".join([f"- {q.question_text}" for q in questions])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "chapter_planning")

    if user_template:
        prompt_text = safe_format(user_template,
            plot_block_goal=plot_block_goal,
            style_constraints="（见组装上下文）",
            pending_foreshadowings=foreshadowing_text,
            pending_questions=questions_text,
            characters_info="（见组装上下文）",
            world_setting_info="（见组装上下文）",
            previous_context=assembled_context,
            chapter_number=str(current_chapter),
            next_block="后续",
        )
    else:
        prompt_text = safe_format(CHAPTER_PLANNING_PROMPT,
            plot_block_goal=plot_block_goal,
            style_constraints="（见组装上下文）",
            pending_foreshadowings=foreshadowing_text,
            pending_questions=questions_text,
            characters_info="（见组装上下文）",
            world_setting_info="（见组装上下文）",
            previous_context=assembled_context,
            chapter_number=str(current_chapter),
            next_block="后续",
        )

    response = ""
    planning_temperature = NODE_TEMPERATURES.get("chapter_planning", 0.7)
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=planning_temperature
    ):
        response += chunk

    # ========== 解析场景导演信息 ==========
    scene_directions = _parse_scene_directions(response)
    pov_character = _extract_pov_from_plan(response, scene_directions)

    return {
        "chapter_plan": response,
        "scene_directions": scene_directions,
        "pov_character": pov_character,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.CHAPTER_NODE.value,
    }


def _parse_scene_directions(plan_text: str) -> list[dict]:
    """从章节点文本中解析场景导演信息"""
    import re
    
    scenes = []
    # 匹配 "场景N：" 或 "- 场景N：" 开头的段落
    scene_pattern = re.compile(
        r'(?:场景[一二三四五六七八九十0-9]+[：:]\s*)?'
        r'([^\n]+?)\n'  # 场景标题行
        r'(?:\s*-\s*POV[：:]\s*([^\n]+))?\n?'
        r'(?:\s*-\s*镜头类型[：:]\s*([^\n]+))?\n?'
        r'(?:\s*-\s*信息层级[：:]\s*([^\n]+))?\n?'
        r'(?:\s*-\s*情绪节拍[：:]\s*([^\n]+))?\n?'
        r'(?:\s*-\s*感官通道[：:]\s*([^\n]+))?\n?'
        r'(?:\s*-\s*切入动作[：:]\s*([^\n]+))?\n?'
        r'(?:\s*-\s*切出动作[：:]\s*([^\n]+))?\n?',
        re.MULTILINE
    )
    
    # 简单的解析：按 "场景" 关键词分割
    lines = plan_text.split('\n')
    current_scene = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 检测新场景开始
        if '场景' in line and ('：' in line or ':' in line or line.startswith('-')):
            if current_scene:
                scenes.append(current_scene)
            current_scene = {"location": line, "pov": "", "scene_type": "", "info_level": "", "rhythm_beat": "", "sense_channels": "", "entry_point": "", "exit_point": ""}
        # 解析场景属性
        elif current_scene:
            if 'POV' in line:
                current_scene["pov"] = line.split('：')[-1].split(':')[-1].strip()
            elif '镜头类型' in line:
                current_scene["scene_type"] = line.split('：')[-1].split(':')[-1].strip()
            elif '信息层级' in line:
                current_scene["info_level"] = line.split('：')[-1].split(':')[-1].strip()
            elif '情绪节拍' in line:
                current_scene["rhythm_beat"] = line.split('：')[-1].split(':')[-1].strip()
            elif '感官通道' in line:
                current_scene["sense_channels"] = line.split('：')[-1].split(':')[-1].strip()
            elif '切入动作' in line:
                current_scene["entry_point"] = line.split('：')[-1].split(':')[-1].strip()
            elif '切出动作' in line:
                current_scene["exit_point"] = line.split('：')[-1].split(':')[-1].strip()
    
    if current_scene:
        scenes.append(current_scene)
    
    return scenes if scenes else None


def _extract_pov_from_plan(plan_text: str, scene_directions: list[dict]) -> str:
    """从章节点或场景导演中提取 POV 角色"""
    import re
    
    # 优先从场景导演提取
    if scene_directions and scene_directions[0].get("pov"):
        return scene_directions[0]["pov"]
    
    # 从文本中搜索 "POV：" 或 "视角：" 关键词
    pov_match = re.search(r'(?:POV|视角)[:：]\s*([^\n,，]+)', plan_text)
    if pov_match:
        return pov_match.group(1).strip()
    
    # 从"涉及角色"字段提取第一个角色
    char_match = re.search(r'涉及角色[：:][^\n]*?([^\n]+)', plan_text)
    if char_match:
        return char_match.group(1).strip()
    
    return ""
