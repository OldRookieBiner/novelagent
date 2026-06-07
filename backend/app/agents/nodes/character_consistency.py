"""角色一致性自查节点 — 增强版

检查维度：
1. 角色知识边界检测：角色是否说出了知识边界之外的信息
2. 行为一致性：行为是否符合核心动机
3. 对话风格一致性：对话是否符合说话风格设定

发现违规时写入 DB 警告记录，并通过 SSE 推送到前端。
"""

import json
import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHARACTER_KNOWLEDGE_BOUNDARY_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format, find_chapter_by_number

logger = logging.getLogger(__name__)


# ========== POV 漂移检测：非 POV 角色的内心动词列表 ==========
POV_VIOLATION_VERBS = [
    "心想", "想到", "觉得", "感到", "意识到", "明白", "了解", "知道",
    "猜测", "怀疑", "估计", "推测", "判断", "认为", "确信", "确定",
    "回忆", "想起", "记得", "怀念", "怀念起", "思索", "思考", "考虑",
    "担忧", "忧虑", "害怕", "恐惧", "希望", "渴望", "期盼", "期待",
    "后悔", "自责", "感激", "感动", "温暖", "幸福", "悲伤", "难过",
]


def _check_pov_drift(content: str, pov_character: str) -> list[dict]:
    """��测 POV 漂移：非 POV 角色出现内心独白"""
    import re
    
    if not pov_character or pov_character == "（无明确 POV）":
        return []
    
    violations = []
    lines = content.split(chr(10))
    
    for line_num, line in enumerate(lines, 1):
        for verb in POV_VIOLATION_VERBS:
            if verb in line:
                match = re.search(r'([^，。,.]+?)\s*' + re.escape(verb), line)
                if match:
                    subject = match.group(1).strip()
                    if subject != pov_character and subject not in [pov_character]:
                        violations.append({
                            "type": "pov_drift",
                            "character": subject,
                            "verb": verb,
                            "line": line_num,
                            "detail": f"第 {line_num} 行：{subject}{verb}，但本章 POV 为 {pov_character}"
                        })
    
    return violations


async def character_consistency_node(state: NovelState) -> NovelState:
    """角色一致性自查 + 知识边界检测

    对每个出场角色检查：
    1. 是否说出了其知识边界之外的信息（OOC 核心）
    2. 行为是否符合核心动机
    3. 对话是否符合说话风格

    输出结构化违规列表，写入 DB 警告。
    """
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

    # ========== POV 漂移检测（新增）==========
    pov_character = state.get("pov_character", "")
    pov_violations = []
    if pov_character and pov_character != "（无明确 POV）":
        pov_violations = _check_pov_drift(content, pov_character)
        if pov_violations:
            logger.warning(f"项目 {project_id} 第 {written_chapter_num} 章 POV 漂移：{len(pov_violations)} 处")
            for v in pov_violations[:3]:
                logger.warning(f"  - {v.get('detail', '')}")

    # 加载角色设定（含知识边界）
    characters = kb.get_characters()
    if not characters:
        return {**state}

    # 构建角色信息摘要（含知识边界，这是核心检查维度）
    chars_info = []
    for c in characters:
        info = f"角色：{c.name}"
        if hasattr(c, 'role') and c.role:
            info += f"\n  定位：{c.role}"
        if hasattr(c, 'core_motivation') and c.core_motivation:
            info += f"\n  核心动机：{c.core_motivation}"
        if hasattr(c, 'knowledge_boundary') and c.knowledge_boundary:
            boundary = c.knowledge_boundary
            if isinstance(boundary, dict):
                info += f"\n  知识边界：不知道{json.dumps(boundary.get('unknown', []), ensure_ascii=False)}，误以为{json.dumps(boundary.get('mistaken', []), ensure_ascii=False)}"
            else:
                info += f"\n  知识边界：{boundary}"
        if hasattr(c, 'speech_style') and c.speech_style:
            info += f"\n  说话风格：{c.speech_style}"
        chars_info.append(info)

    chars_text = "\n\n".join(chars_info)

    # 使用增强的 Prompt 进行检查
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "character_knowledge_boundary")

    if user_template:
        prompt_text = safe_format(user_template,
            chapter_content=content[:3000],
            characters_info=chars_text,
            chapter_number=written_chapter_num,
        )
    else:
        prompt_text = safe_format(CHARACTER_KNOWLEDGE_BOUNDARY_PROMPT,
            chapter_content=content[:3000],
            characters_info=chars_text,
            chapter_number=written_chapter_num,
        )

    llm = await get_llm_from_state_async(state)
    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.2
    ):
        response += chunk

    # 解析违规结果
    violations = _parse_violations(response)

    # 记录违规到日志（后续 WarningService 会消费）
    if violations:
        logger.warning(f"项目 {project_id} 第 {written_chapter_num} 章角色违规：{len(violations)} 项")
        for v in violations:
            logger.warning(f"  - {v.get('character', '?')}：{v.get('type', '?')} - {v.get('detail', '?')}")

    return {**state}


def _parse_violations(response: str) -> list[dict]:
    """解析 LLM 返回的违规列表

    期望格式：
    ❌ [角色名] 知识边界违规：[具体内容]
    或
    ✅ 无违规
    """
    violations = []
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("❌") or line.startswith("⚠️"):
            # 尝试解析结构化信息
            parts = line.lstrip("❌⚠️").strip()
            violations.append({
                "type": "knowledge_boundary" if "知识边界" in parts or "边界" in parts else "consistency",
                "detail": parts,
                "character": _extract_character_name(parts),
            })
    return violations


def _extract_character_name(text: str) -> str:
    """从违规描述中提取角色名"""
    # 尝试匹配 [角色名] 格式
    import re
    match = re.search(r'[【\[]([^】\]]+)[】\]]', text)
    if match:
        return match.group(1)
    # 否则取第一个冒号前的文本
    if "：" in text:
        return text.split("：")[0].strip()
    if ":" in text:
        return text.split(":")[0].strip()
    return "未知"
