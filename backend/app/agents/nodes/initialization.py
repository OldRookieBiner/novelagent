"""项目初始化节点

根据用户输入的概念描述，初始化项目的基础知识库：
1. 概念 → 故事种子
2. 故事种子 → [小说名, 世界观, 大纲] 并行
3. [世界观, 大纲] → [角色, 风格] 并行

每个阶段完成后 yield SSE 事件，跳过失败的节点继续执行。
"""

import re
import asyncio
import logging
import json
from typing import AsyncIterator, Optional, Tuple

from app.database import SessionLocal
from app.models.project import Project
from app.models.outline import Outline
from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.sse_events import (
    format_init_start,
    format_init_concept,
    format_init_novel_name,
    format_init_world,
    format_init_characters,
    format_init_outline,
    format_init_style,
    format_init_complete,
    format_init_done,
    format_init_error,
    format_init_cancelled,
    format_init_timeout,
)
from app.agents.prompts import (
    STORY_SEED_PROMPT,
    WORLD_SETTING_PROMPT,
    CHARACTER_GENERATION_PROMPT,
    OUTLINE_GENERATION_PROMPT,
    STYLE_SETUP_PROMPT,
)
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import safe_format, parse_world_setting_response

logger = logging.getLogger(__name__)


class InitializationCancelledError(Exception):
    """客户端断开连接，初始化被取消"""
    pass


class InitializationTimeoutError(Exception):
    """LLM 流式空闲超时"""
    pass


# 小说名生成 prompt
NOVEL_NAME_PROMPT = """根据以下故事种子，生成一个吸引人的小说名。

## 故事种子
{story_seed}

要求：
- 简洁有力，2-8 个字
- 能体现故事核心氛围
- 不要书名号，直接输出名字

直接输出小说名，不要其他解释。"""




async def check_disconnect(request):
    """检查客户端是否断连，断连则抛出取消异常"""
    if request is not None:
        try:
            if await request.is_disconnected():
                raise InitializationCancelledError("客户端断开连接")
        except RuntimeError as e:
            # request 对象可能在某些情况下不可用，记录日志而非静默忽略
            logger.warning(f"check_disconnect RuntimeError: {e}")


async def generate_story_seed(concept: str, llm, request=None) -> str:
    """根据概念生成故事种子"""
    prompt = STORY_SEED_PROMPT.format(conversation_summary=concept)
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7):
        response += chunk
        await check_disconnect(request)
    return response.strip()


async def generate_novel_name(story_seed: str, llm, request=None) -> str:
    """根据故事种子生成小说名"""
    prompt = NOVEL_NAME_PROMPT.format(story_seed=story_seed)
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7):
        response += chunk
        await check_disconnect(request)
    # 清理书名号和空格
    return response.strip().strip("《》")


async def generate_world_setting(story_seed: str, kb: KnowledgeBaseService, llm, request=None) -> Tuple[Optional[int], str]:
    """根据故事种子生成世界观，返回 (id, 文本内容)"""
    prompt = safe_format(WORLD_SETTING_PROMPT, outline=story_seed)
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7):
        response += chunk
        await check_disconnect(request)

    # 从 LLM 输出中解析分级设定和关键地点
    parsed = parse_world_setting_response(response)
    world_setting = kb.create_world_setting({
        "core_concept": parsed["core_concept"],
        "tiered_settings": parsed["tiered_settings"],
        "key_locations": parsed["key_locations"],
    })
    return world_setting.id, response


async def generate_characters(story_seed: str, world_setting_text: str, kb: KnowledgeBaseService, llm, request=None) -> int:
    """根据故事种子和世界观生成角色

    Args:
        story_seed: 故事种子文本
        world_setting_text: 世界观文本内容

    Returns:
        创建的角色数量
    """
    prompt = safe_format(CHARACTER_GENERATION_PROMPT,
        outline=story_seed,
        world_setting=world_setting_text,
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7):
        response += chunk
        await check_disconnect(request)

    # 解析角色
    characters = _parse_characters(response)

    # 解析失败时记录警告
    if not characters:
        logger.warning(
            f"Failed to parse characters from LLM response. "
            f"Response length: {len(response)}, first 200 chars: {response[:200]}"
        )
        return 0

    # 持久化到数据库
    for char_data in characters:
        kb.create_character(char_data)

    logger.info(f"Successfully created {len(characters)} characters")
    return len(characters)


def _map_role(role_text: str) -> str:
    """将大纲中的角色标签映射到 Character 模型的 role 枚举值"""
    role_keywords = {
        "主角": "主角",
        "反派": "核心反派",
        "敌": "核心反派",
        "重要": "重要配角",
        "配角": "配角",
    }
    for keyword, role_type in role_keywords.items():
        if keyword in role_text:
            return role_type
    return "配角"


def _parse_characters(response: str) -> list[dict]:
    """解析 LLM 返回的角色列表

    支持 CHARACTER_GENERATION_PROMPT 的 Markdown 输出格式：
    ## 角色名
    - **角色定位**：主角
    - **核心动机**：xxx
    - **核心冲突**：xxx
    - **人物弧**：从xxx到xxx
    - **说话风格**：xxx
    - **知识边界**：xxx
    """
    characters = []

    if not response or not response.strip():
        return characters

    # 移除 ** 粗体标记（避免干扰正则）
    response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)

    # 匹配从 ## 或 ### 开始到下一个 ## 或 ### 或文档结尾
    section_pattern = r'(?:^|\n)(#{1,3})\s*([^\n#]+?)(?:\n)(.*?)(?=(?:^#{1,3})|\Z)'

    for match in re.finditer(section_pattern, response, re.DOTALL | re.MULTILINE):
        name = match.group(2).strip()
        if not name:
            continue

        # 清理书名号和引号
        name = re.sub(r"^[《\"']|[》\"']$", "", name).strip()
        if not name or len(name) > 15:
            continue

        section = match.group(3)

        # 提取角色定位
        role = "配角"
        role_match = re.search(r'角色定位[：:]\s*([^\n]+)', section)
        if role_match:
            role = _map_role(role_match.group(1).strip())

        # 提取核心动机
        motivation = ""
        mot_match = re.search(r'核心动机[：:]\s*([^\n]+)', section)
        if mot_match:
            motivation = mot_match.group(1).strip()[:500]

        # 提取核心冲突
        conflict = ""
        conflict_match = re.search(r'核心冲突[：:]\s*([^\n]+)', section)
        if conflict_match:
            conflict = conflict_match.group(1).strip()[:500]

        # 提取人物弧
        arc = ""
        arc_match = re.search(r'人物弧[：:]\s*([^\n]+)', section)
        if arc_match:
            arc = arc_match.group(1).strip()[:500]

        # 提取说话风格作为性格
        personality = ""
        pers_match = re.search(r'说话风格[：:]\s*([^\n]+)', section)
        if pers_match:
            personality = pers_match.group(1).strip()[:500]

        # 如果没有动机但有冲突，用冲突替代
        if not motivation and conflict:
            motivation = conflict

        characters.append({
            "name": name,
            "role": role,
            "personality": personality,
            "core_motivation": motivation,
            "growth_arc": arc,
        })

    # 备选：管道分隔格式 - 角色定位 | 姓名 | 性格 | 核心动机 | 成长弧线
    if not characters:
        pipe_pattern = re.compile(
            r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
        )
        for line in response.splitlines():
            m = pipe_pattern.search(line)
            if not m:
                continue
            role_label, name, personality, motivation, arc = m.groups()
            name = (name or "").strip()
            if not name:
                continue
            characters.append({
                "name": name,
                "role": _map_role(role_label),
                "personality": (personality or "").strip()[:500],
                "core_motivation": (motivation or "").strip()[:500],
                "growth_arc": (arc or "").strip()[:500],
            })

    # 兜底：从行首关键词提取角色名
    if not characters:
        seen = set()
        for line in response.splitlines():
            line = line.strip()
            if not line:
                continue
            # "主角：李明" 格式
            simple_match = re.match(r'^([主角反配重要角色敌]+)[：:]\s*(.+)', line)
            if simple_match:
                role_text = simple_match.group(1)
                name = simple_match.group(2).strip().split()[0] if simple_match.group(2).strip() else ""
                name = re.sub(r"^[《\"']|[》\"']$", "", name).strip()
                if name and len(name) <= 15 and name not in seen:
                    seen.add(name)
                    characters.append({
                        "name": name,
                        "role": _map_role(role_text),
                        "personality": "",
                        "core_motivation": "",
                        "growth_arc": "",
                    })

    return characters


def _clean_brackets(text: str) -> str:
    """清理文本中的方括号和多余空格"""
    if not text:
        return ""
    text = re.sub(r'[\[\]]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_outline(response: str, chapter_count: int) -> dict:
    """解析大纲响应 - 完整版

    从 LLM 输出中提取：
    - 标题
    - 概述
    - 世界观与势力
    - 情节节点
    - 情感曲线
    """
    title = ""
    summary = ""
    world_setting = {}
    plot_points = []
    emotional_curve = ""

    # 1. 提取标题
    m = re.search(r"《(.+?)》", response)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r"(?:#{1,3}\s*)?标题[：:]\s*(.+?)(?:\n|$)", response)
        if m:
            title = m.group(1).strip()

    # 2. 提取概述
    m = re.search(r"(?:#{1,3}\s*)?概述[：:]?\s*(.+?)(?=\n#{1,3}|\n---|\Z)", response, re.DOTALL)
    if m:
        summary = m.group(1).strip()[:2000]

    # 3. 提取章节数（LLM 可能返回建议章节数）
    m = re.search(r'建议章节数[：:]\s*(\d+)', response)
    if m:
        chapter_count = int(m.group(1))
    m = re.search(r'共(\d+)章', response)
    if m:
        chapter_count = int(m.group(1))

    # 4. 提取世界观与势力
    world_setting = _parse_world_setting(response)

    # 5. 提取情节节点
    plot_points = _parse_plot_points(response)

    # 6. 提取情感曲线
    emotional_curve = _parse_emotional_curve(response)

    return {
        "title": title,
        "summary": summary,
        "plot_points": plot_points,
        "characters": [],  # 角色由 generate_characters 单独生成
        "world_setting": world_setting,
        "emotional_curve": emotional_curve,
        "chapter_count_suggested": chapter_count,
    }


def _parse_world_setting(response: str) -> dict:
    """解析大纲中的世界观与势力部分

    注意：此函数解析的是 OUTLINE_GENERATION_PROMPT 的输出，
    世界观独立生成（WORLD_SETTING_PROMPT）的解析见 parse_world_setting_response。
    如果解析不到任何有效内容，返回空 dict 以避免存入全空默认值。
    """
    m = re.search(
        r'(?:三|三、|###.*?世界观.*?)(.*?)(?=\n#{1,3}|\n---|\n[五六七八九十]+、|\Z)',
        response,
        re.DOTALL
    )
    if not m:
        return {}

    section = m.group(1)

    world_setting: dict = {}

    m = re.search(r'(?:时代背景|时代)[：:]\s*(.+?)(?:\n|$)', section)
    if m:
        world_setting["era"] = m.group(1).strip()

    m = re.search(r'(?:核心设定|核心)[：:]\s*(.+?)(?:\n|$)', section)
    if m:
        world_setting["core_rules"] = m.group(1).strip()

    m = re.search(r'(?:社会结构|社会)[：:]\s*(.+?)(?:\n|$)', section)
    if m:
        world_setting["power_system"] = m.group(1).strip()

    location_matches = re.findall(r'^\d+\.\s*(.+?)(?:\n|$)', section, re.MULTILINE)
    if location_matches:
        world_setting["key_locations"] = [loc.strip() for loc in location_matches[:5]]

    return world_setting


def _parse_plot_points(response: str) -> list[dict]:
    """解析情节节点部分"""
    plot_points = []

    m = re.search(
        r'(?:四|四、|###.*?情节.*?)(.*?)(?=\n#{1,3}|\n---|\n[五六七八九十]+、|\Z)',
        response,
        re.DOTALL
    )
    if not m:
        return plot_points

    section = m.group(1)

    # 按行解析
    for line in section.split('\n'):
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
        parts = [_clean_brackets(p) for p in parts]

        plot_points.append({
            "order": order,
            "event": parts[0] if len(parts) > 0 else "",
            "conflict": parts[1] if len(parts) > 1 else "",
            "hook": parts[2] if len(parts) > 2 else "",
            "foreshadowing": parts[3] if len(parts) > 3 else "",
        })

    return plot_points


def _parse_emotional_curve(response: str) -> str:
    """解析情感曲线部分"""
    m = re.search(
        r'(?:五|五、|###.*?情感.*?)(.*?)(?=\n#{1,3}|\n---|\Z)',
        response,
        re.DOTALL
    )
    if not m:
        return ""

    section = m.group(1)

    # 匹配箭头格式
    m = re.search(r'([^\n→]+)\s*→\s*([^\n→]+)\s*→\s*([^\n→]+)\s*→\s*([^\n]+)', section)
    if m:
        parts = [p.strip() for p in m.groups()]
        return " → ".join(parts)

    # 备选：简单列表
    lines = [line.strip() for line in section.split('\n')
             if line.strip() and not line.strip().startswith('#')]
    if lines:
        return " → ".join(lines[:4])

    return ""


async def generate_outline(story_seed: str, kb: KnowledgeBaseService, llm, target_words: int, request=None) -> Tuple[Optional[int], str]:
    """根据故事种子生成大纲，返回 (id, 文本摘要)"""
    chapter_count = max(10, min(50, target_words // 5000))

    prompt = safe_format(OUTLINE_GENERATION_PROMPT,
        story_seed=story_seed,
        chapter_count=str(chapter_count),
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=8192):
        response += chunk
        await check_disconnect(request)

    # 解析大纲
    outline_data = _parse_outline(response, chapter_count)

    # 持久化：检查是否已存在 Outline，存在则更新，不存在则创建
    db = SessionLocal()
    try:
        outline = db.query(Outline).filter(Outline.project_id == kb.project_id).first()

        if outline:
            # 更新现有大纲
            outline.title = outline_data.get("title", "待命名")
            outline.summary = outline_data.get("summary", "")
            outline.plot_points = outline_data.get("plot_points", [])
            outline.characters = outline_data.get("characters", [])
            outline.world_setting = outline_data.get("world_setting", {})
            outline.emotional_curve = outline_data.get("emotional_curve", "")
            outline.confirmed = True
            outline.chapter_count_suggested = outline_data.get("chapter_count_suggested", chapter_count)
            outline.chapter_count_confirmed = True
        else:
            # 创建新大纲
            outline = Outline(
                project_id=kb.project_id,
                title=outline_data.get("title", "待命名"),
                summary=outline_data.get("summary", ""),
                plot_points=outline_data.get("plot_points", []),
                characters=outline_data.get("characters", []),
                world_setting=outline_data.get("world_setting", {}),
                emotional_curve=outline_data.get("emotional_curve", ""),
                confirmed=True,
                chapter_count_suggested=outline_data.get("chapter_count_suggested", chapter_count),
                chapter_count_confirmed=True,
            )
            db.add(outline)

        db.commit()
        db.refresh(outline)
        return outline.id, outline_data.get("summary", "")
    finally:
        db.close()


async def generate_style(story_seed: str, outline_text: str, kb: KnowledgeBaseService, llm, request=None) -> Optional[int]:
    """生成风格约束"""
    prompt = safe_format(STYLE_SETUP_PROMPT,
        outline=outline_text,
        world_setting=story_seed,
        user_preference="",
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.5):
        response += chunk
        await check_disconnect(request)

    constraints = kb.create_style_constraints({
        "taboo_words": [],
        "forbidden_patterns": [],
        "style_anchor": response,
        "abstract_rules": [],
    })
    return constraints.id


async def stream_initialization(
    concept: str,
    target_words: int,
    project_id: int,
    user_id: int,
    model_config_id: Optional[int] = None,
    model_id: Optional[str] = None,
    request=None,
) -> AsyncIterator[str]:
    """初始化流程 SSE 流

    执行分波：
    - 波次 0: 故事种子 ← concept
    - 波次 1: [小说名, 世界观, 大纲] 并行 ← story_seed
    - 波次 2: [角色, 风格] 并行 ← 角色需要世界观文本，风格需要大纲文本

    Args:
        concept: 用户输入的概念描述
        target_words: 目标字数
        project_id: 项目 ID
        user_id: 用户 ID

    Yields:
        SSE 事件字符串
    """
    # 发送开始事件
    yield format_init_start()

    # 创建 LLM 服务需要的 state
    state = NovelState(
        llm_config_id=model_config_id,
        llm_model_name=model_id,
        project_id=project_id,
        user_id=user_id,
        phase="incubation",
    )

    llm = None
    try:
        llm = await get_llm_from_state_async(state)
    except Exception as e:
        logger.error(f"Failed to get LLM service: {e}")
        yield format_init_error({"stage": "llm_init", "error": str(e)})
        yield format_init_done({"project_id": project_id, "status": "partial"})
        return

    kb = KnowledgeBaseService(project_id)
    story_seed = ""

    # ===== 波次 0: 生成故事种子 =====
    try:
        story_seed = await generate_story_seed(concept, llm, request=request)
        kb.update_story_seed(story_seed)
        yield format_init_concept({"concept": concept, "story_seed": story_seed[:100] + "..."})
    except InitializationCancelledError as e:
        logger.warning(f"初始化被取消: {e}")
        yield format_init_cancelled({"reason": str(e)})
        yield format_init_done({"project_id": project_id, "status": "cancelled"})
        return
    except InitializationTimeoutError as e:
        logger.error(f"初始化超时: {e}")
        yield format_init_timeout({"reason": str(e)})
        yield format_init_done({"project_id": project_id, "status": "timeout"})
        return
    except Exception as e:
        logger.error(f"Failed to generate story seed: {e}")
        yield format_init_error({"stage": "story_seed", "error": str(e)})
        yield format_init_done({"project_id": project_id, "status": "partial"})
        return

    # ===== 波次 1: 并行生成小说名、世界观、大纲 =====
    # 使用 Queue 实现实时事件推送
    event_queue: asyncio.Queue = asyncio.Queue()
    novel_name = "新建项目"
    world_setting_id = None
    world_setting_text = ""
    outline_id = None
    outline_summary = ""

    async def run_novel_name():
        nonlocal novel_name
        try:
            result = await generate_novel_name(story_seed, llm, request=request)
            if result:
                novel_name = result
                # 更新 Project.name
                db = SessionLocal()
                try:
                    project = db.query(Project).filter(Project.id == project_id).first()
                    if project:
                        project.name = novel_name
                        db.commit()
                finally:
                    db.close()
            await event_queue.put(("novel_name", {"name": novel_name}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate novel name: {e}")
            await event_queue.put(("error", {"stage": "novel_name", "error": str(e)}))

    async def run_world_setting():
        nonlocal world_setting_id, world_setting_text
        try:
            world_setting_id, world_setting_text = await generate_world_setting(story_seed, kb, llm, request=request)
            await event_queue.put(("world", {"world_setting_id": world_setting_id}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate world setting: {e}")
            await event_queue.put(("error", {"stage": "world_setting", "error": str(e)}))

    async def run_outline():
        nonlocal outline_id, outline_summary
        try:
            outline_id, outline_summary = await generate_outline(story_seed, kb, llm, target_words, request=request)
            await event_queue.put(("outline", {"outline_id": outline_id, "chapter_count": max(10, target_words // 5000)}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate outline: {e}")
            await event_queue.put(("error", {"stage": "outline", "error": str(e)}))

    # 并行执行波次 1 的三个任务
    wave1_tasks = [
        asyncio.create_task(run_novel_name()),
        asyncio.create_task(run_world_setting()),
        asyncio.create_task(run_outline()),
    ]

    # 收集事件直到所有任务完成
    events_received = 0
    expected_events = 3  # novel_name, world, outline
    wave1_cancelled = False
    wave1_timeout = False

    while events_received < expected_events:
        try:
            event_type, data = await asyncio.wait_for(event_queue.get(), timeout=120.0)
            # _cancelled 是内部信号，不发给前端
            if event_type == "_cancelled":
                wave1_cancelled = True
                break
            events_received += 1
            # 根据事件类型选择对应的 SSE 格式化函数
            if event_type == "novel_name":
                yield format_init_novel_name(data)
            elif event_type == "world":
                yield format_init_world(data)
            elif event_type == "outline":
                yield format_init_outline(data)
            elif event_type == "error":
                yield format_init_error(data)
            else:
                logger.warning(f"Unknown wave1 event type: {event_type}")
        except asyncio.TimeoutError:
            logger.error("Wave 1 timeout waiting for events")
            wave1_timeout = True
            break

    # 等待所有任务完成
    await asyncio.gather(*wave1_tasks, return_exceptions=True)

    if wave1_cancelled:
        yield format_init_cancelled({"reason": "客户端断开连接"})
        yield format_init_done({"project_id": project_id, "status": "cancelled"})
        return
    if wave1_timeout:
        yield format_init_timeout({"reason": "等待事件超时"})
        yield format_init_done({"project_id": project_id, "status": "timeout"})
        return

    # ===== 波次 2: 并行生成角色、风格 =====
    # 角色依赖世界观文本，风格依赖大纲摘要

    async def run_characters():
        try:
            # 如果世界观生成失败，使用空字符串
            ws_text = world_setting_text if world_setting_text else story_seed
            count = await generate_characters(story_seed, ws_text, kb, llm, request=request)
            await event_queue.put(("characters", {"character_count": count}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate characters: {e}")
            await event_queue.put(("error", {"stage": "characters", "error": str(e)}))

    async def run_style():
        try:
            # 如果大纲生成失败，使用故事种子
            ot_text = outline_summary if outline_summary else story_seed
            style_id = await generate_style(story_seed, ot_text, kb, llm, request=request)
            await event_queue.put(("style", {"style_constraints_id": style_id}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate style: {e}")
            await event_queue.put(("error", {"stage": "style", "error": str(e)}))

    wave2_tasks = [
        asyncio.create_task(run_characters()),
        asyncio.create_task(run_style()),
    ]

    # 收集波次 2 的事件
    events_received2 = 0
    expected_events2 = 2  # characters, style
    wave2_cancelled = False
    wave2_timeout = False

    while events_received2 < expected_events2:
        try:
            event_type, data = await asyncio.wait_for(event_queue.get(), timeout=120.0)
            if event_type == "_cancelled":
                wave2_cancelled = True
                break
            events_received2 += 1
            # 根据事件类型选择对应的 SSE 格式化函数
            if event_type == "characters":
                yield format_init_characters(data)
            elif event_type == "style":
                yield format_init_style(data)
            elif event_type == "error":
                yield format_init_error(data)
            else:
                logger.warning(f"Unknown wave2 event type: {event_type}")
        except asyncio.TimeoutError:
            logger.error("Wave 2 timeout waiting for events")
            wave2_timeout = True
            break

    # 等待所有任务完成
    await asyncio.gather(*wave2_tasks, return_exceptions=True)

    if wave2_cancelled:
        yield format_init_cancelled({"reason": "客户端断开连接"})
        yield format_init_done({"project_id": project_id, "status": "cancelled"})
        return
    if wave2_timeout:
        yield format_init_timeout({"reason": "等待事件超时"})
        yield format_init_done({"project_id": project_id, "status": "timeout"})
        return

    # 完成
    yield format_init_complete({"project_id": project_id, "name": novel_name})
    yield format_init_done({"project_id": project_id, "status": "complete"})
