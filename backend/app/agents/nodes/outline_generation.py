"""大纲生成节点 — 创作智能体版本

基于故事种子生成大纲，解析并持久化到 DB。
复用旧版 parse_outline / prepare_outline_prompt 的解析逻辑，
但使用新 NovelState + KnowledgeBaseService 模式。
"""

import logging
import re
from typing import Optional

from app.agents.state import NovelState, Phase, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import OUTLINE_GENERATION_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def outline_generation_node(state: NovelState) -> NovelState:
    """基于故事种子生成大纲

    流程：
    1. 从 KB 获取 story_seed（已持久化到 DB）
    2. 调用 LLM 生成大纲
    3. 解析大纲（标题/概述/世界观/情节节点/角色/情感曲线）
    4. 持久化到 DB（Outline 模型）
    5. 设置 outline_id 到 state
    """
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)
    story_seed = kb.get_story_seed() or ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "outline_generation")

    if user_template:
        prompt_text = safe_format(user_template, story_seed=story_seed)
    else:
        prompt_text = safe_format(OUTLINE_GENERATION_PROMPT, story_seed=story_seed)

    # 流式生成
    response = ""
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt_text}],
            max_tokens=8192,
            temperature=0.7,
        ):
            response += chunk
            writer({"type": "outline_chunk", "content": chunk})
    except ImportError:
        # langgraph.config 不可用时退化为非流式
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt_text}],
            max_tokens=8192,
            temperature=0.7,
        ):
            response += chunk

    # 解析大纲
    outline_data = _parse_outline(response)

    # 持久化到 DB
    outline_id = _persist_outline(project_id, outline_data)

    return {
        "outline_id": outline_id,
        "chapter_count": outline_data.get("chapter_count_suggested", 20),
    }


def _clean_brackets(text: str) -> str:
    """清理文本中的方括号和多余空格"""
    if not text:
        return ""
    # 移除方括号
    text = re.sub(r'[\[\]]', '', text)
    # 清理多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_outline(response: str) -> dict:
    """完整版大纲解析

    从 LLM 输出中提取：
    - 标题
    - 概述
    - 世界观与势力
    - 情节节点
    - 情感曲线
    - 伏笔信息（暂不解析为结构化数据）
    - 主题内核
    """
    title = ""
    summary = ""
    world_setting = {}
    plot_points = []
    emotional_curve = ""
    chapter_count_suggested = 20

    # 1. 提取标题
    m = re.search(r'(?:#{1,3}\s*)?标题[���:]\s*(.+?)(?:\n|$)', response)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r'《(.+?)》', response)
        if m:
            title = m.group(1).strip()

    # 2. 提取概述
    m = re.search(r'(?:#{1,3}\s*)?概述[：:]?\s*(.+?)(?=\n#{1,3}|\n---|\Z)', response, re.DOTALL)
    if m:
        summary = m.group(1).strip()[:2000]

    # 3. 提取章节数
    m = re.search(r'建议章节数[：:]\s*(\d+)', response)
    if m:
        chapter_count_suggested = int(m.group(1))
    # 备选：共N章
    m = re.search(r'共(\d+)章', response)
    if m:
        chapter_count_suggested = int(m.group(1))

    # 4. 提取世界观与势力
    world_setting = _parse_world_setting(response)

    # 5. 提取情节节点
    plot_points = _parse_plot_points(response)

    # 6. 提取情感曲线
    emotional_curve = _parse_emotional_curve(response)

    return {
        "title": title,
        "summary": summary,
        "characters": [],  # 角色由 character_generation_node 单独生成
        "world_setting": world_setting,
        "plot_points": plot_points,
        "emotional_curve": emotional_curve,
        "chapter_count_suggested": chapter_count_suggested,
    }


def _parse_world_setting(response: str) -> dict:
    """解析世界观与势力

    提取格式：
    ### 三、世界观与势力
    - 时代背景 / 核心设定 / 社会结构 / 关键地点

    或 Markdown 列表格式
    """
    world_setting = {
        "era": "",
        "core_rules": "",
        "power_system": "",
        "key_locations": [],
    }

    # 匹配"世界观与势力"或"世界观的"部分
    m = re.search(
        r'(?:三|三、|###.*?世界观.*?)(.*?)(?=\n#{1,3}|\n---|\n[五六七八九十]+、|\Z)',
        response,
        re.DOTALL
    )
    if not m:
        return world_setting

    section = m.group(1)

    # 提取时代背景
    m = re.search(r'(?:时代背景|时代)[：:]\s*(.+?)(?:\n|$)', section)
    if m:
        world_setting["era"] = m.group(1).strip()

    # 提取核心设定
    m = re.search(r'(?:核心设定|核心)[：:]\s*(.+?)(?:\n|$)', section)
    if m:
        world_setting["core_rules"] = m.group(1).strip()

    # 提取社会结构
    m = re.search(r'(?:社会结构|社会)[：:]\s*(.+?)(?:\n|$)', section)
    if m:
        world_setting["power_system"] = m.group(1).strip()

    # 提取关键地点（列表格式）
    location_matches = re.findall(r'^\d+\.\s*(.+?)(?:\n|$)', section, re.MULTILINE)
    if location_matches:
        world_setting["key_locations"] = [loc.strip() for loc in location_matches[:5]]

    return world_setting


def _parse_plot_points(response: str) -> list[dict]:
    """解析情节节点

    提取格式：
    ### 四、情节节点（要求埋设伏笔）
    1. 开篇：[事件] | [冲突] | [钩子] | [伏笔：V1]
    2. 发展：[事件] | [冲突] | [钩子] | [伏笔：V2 / 回收：V1]
    ...
    N. 结局：[事件] | [冲突解决] | [伏笔回收：所有未回收]

    返回格式：[{"order": 1, "event": "...", "conflict": "...", "hook": "...", "foreshadowing": "..."}]
    """
    plot_points = []

    # 匹配"情节节点"部分
    m = re.search(
        r'(?:四|四、|###.*?情节.*?)(.*?)(?=\n#{1,3}|\n---|\n[五六七八九十]+、|\Z)',
        response,
        re.DOTALL
    )
    if not m:
        return plot_points

    section = m.group(1)

    # 匹配每行的情节节点：序号. 内容 | 内容 | 内容 | 内容
    # 更宽松的正则，处理各种格式
    lines = section.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 匹配 "数字. 内容" 格式
        match = re.match(r'(\d+)\.\s*(.+?)$', line)
        if not match:
            continue
            
        order = int(match.group(1))
        content = match.group(2)
        
        # 按 | 分割
        parts = [p.strip() for p in content.split('|')]
        
        # 清理每个部分的方括号
        parts = [_clean_brackets(p) for p in parts]
        
        # 构建情节节点
        plot_point = {
            "order": order,
            "event": parts[0] if len(parts) > 0 else "",
            "conflict": parts[1] if len(parts) > 1 else "",
            "hook": parts[2] if len(parts) > 2 else "",
            "foreshadowing": parts[3] if len(parts) > 3 else "",
        }
        
        plot_points.append(plot_point)

    return plot_points


def _parse_emotional_curve(response: str) -> str:
    """解析情感曲线

    提取格式：
    ### 五、情感曲线与节奏
    [开篇情绪] → [中段转折] → [高潮顶点] → [结局情绪]
    """
    # 匹配"情感曲线"或"情感"部分
    m = re.search(
        r'(?:五|五、|###.*?情感.*?)(.*?)(?=\n#{1,3}|\n---|\Z)',
        response,
        re.DOTALL
    )
    if not m:
        return ""

    section = m.group(1)

    # 匹配箭头格式的情感曲线
    m = re.search(r'([^\n→]+)\s*→\s*([^\n→]+)\s*→\s*([^\n→]+)\s*→\s*([^\n]+)', section)
    if m:
        parts = [p.strip() for p in m.groups()]
        return " → ".join(parts)

    # 备选：匹配简单的列表格式
    lines = [line.strip() for line in section.split('\n') if line.strip() and not line.strip().startswith('#')]
    if lines:
        return " → ".join(lines[:4])

    return ""


# ========== 旧版兼容函数 ==========

def _parse_outline_simple(response: str) -> dict:
    """简化版大纲解析（兼容旧 API）

    从 LLM 输出中提取标题、概述、角色、世界观、情节节点。
    """
    return _parse_outline(response)


def _persist_outline(project_id: int, outline_data: dict) -> Optional[int]:
    """持久化大纲到 DB，返回 outline_id"""
    from app.models.outline import Outline
    from app.agents.services.knowledge_base import KnowledgeBaseService

    kb = KnowledgeBaseService(project_id)
    try:
        with kb.session() as db:
            outline = db.query(Outline).filter(
                Outline.project_id == project_id
            ).first()

            if outline:
                # 更新现有大纲
                if outline_data.get("title"):
                    outline.title = outline_data["title"]
                if outline_data.get("summary"):
                    outline.summary = outline_data["summary"]
                if outline_data.get("plot_points"):
                    outline.plot_points = outline_data["plot_points"]
                if outline_data.get("characters"):
                    outline.characters = outline_data["characters"]
                if outline_data.get("world_setting"):
                    outline.world_setting = outline_data["world_setting"]
                if outline_data.get("emotional_curve"):
                    outline.emotional_curve = outline_data["emotional_curve"]
                outline.confirmed = True
                outline.chapter_count_suggested = outline_data.get("chapter_count_suggested", 0)
            else:
                # 创建新大纲
                outline = Outline(
                    project_id=project_id,
                    title=outline_data.get("title", ""),
                    summary=outline_data.get("summary", ""),
                    plot_points=outline_data.get("plot_points", []),
                    characters=outline_data.get("characters", []),
                    world_setting=outline_data.get("world_setting", {}),
                    emotional_curve=outline_data.get("emotional_curve", ""),
                    confirmed=True,
                    chapter_count_suggested=outline_data.get("chapter_count_suggested", 0),
                    chapter_count_confirmed=True,
                )
                db.add(outline)

            db.flush()
            db.refresh(outline)
            return outline.id
    except Exception as e:
        logger.error(f"Failed to persist outline: {e}")
        return None


# ========== 旧版兼容导出 ==========

# 旧版常量
DEFAULT_CHAPTER_COUNT = 20

# 旧版别名：outline_generation_node 同时作为 generate_outline_node
generate_outline_node = outline_generation_node


def generate_outline_stream(state, llm):
    """旧版流式生成兼容（退化为非流式，返回空迭代器）"""
    import asyncio
    async def _empty():
        return
        yield  # make it an async generator
    return _empty()


# 旧版 parse_outline 函数（简化实现）
def parse_outline(response: str) -> dict:
    """解析大纲响应（兼容旧 API）"""
    return _parse_outline(response)


def parse_chapter_count(response: str) -> int:
    """从大纲响应中解析建议章节数

    搜索格式：
    - 建议章节数：N
    - 建议章节数:N
    - 章节数：N
    - 共N章

    未找到时返回默认值 DEFAULT_CHAPTER_COUNT。
    """
    # 匹配"建议章节数：N"或"章节数：N"格式
    match = re.search(r'(?:建议)?章节数[：:]\s*(\d+)', response)
    if match:
        return int(match.group(1))
    # 匹配"共N章"格式
    match = re.search(r'共(\d+)章', response)
    if match:
        return int(match.group(1))
    return DEFAULT_CHAPTER_COUNT
