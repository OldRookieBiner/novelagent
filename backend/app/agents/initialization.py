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
from typing import AsyncIterator, Optional, Tuple

from app.database import SessionLocal
from app.models.project import Project
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
from app.agents.nodes_utils import safe_format, parse_world_setting_response

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
    return response.strip().strip("《》")


async def generate_world_setting(story_seed: str, kb: KnowledgeBaseService, llm, request=None) -> Tuple[Optional[int], str]:
    """根据故事种子生成世界观，返回 (id, 文本内容)"""
    prompt = safe_format(WORLD_SETTING_PROMPT, outline=story_seed)
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7):
        response += chunk
        await check_disconnect(request)

    parsed = parse_world_setting_response(response)
    world_setting = kb.world_setting.create({
        "core_concept": parsed["core_concept"],
        "tiered_settings": parsed["tiered_settings"],
        "key_locations": parsed["key_locations"],
    })
    return world_setting["id"], response


async def generate_characters(story_seed: str, world_setting_text: str, kb: KnowledgeBaseService, llm, request=None) -> int:
    """根据故事种子和世界观生成角色

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

    characters = _parse_characters(response)

    if not characters:
        logger.warning(
            f"Failed to parse characters from LLM response. "
            f"Response length: {len(response)}, first 200 chars: {response[:200]}"
        )
        return 0

    for char_data in characters:
        kb.characters.create_character(char_data)

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

    # 移除 ** 粗体标记
    response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)

    section_pattern = r'(?:^|\n)(#{1,3})\s*([^\n#]+?)(?:\n)(.*?)(?=(?:^#{1,3})|\Z)'

    for match in re.finditer(section_pattern, response, re.DOTALL | re.MULTILINE):
        name = match.group(2).strip()
        if not name:
            continue

        name = re.sub(r"^[《\"']|[》\"']$", "", name).strip()
        if not name or len(name) > 15:
            continue

        section = match.group(3)

        role = "配角"
        role_match = re.search(r'角色定位[：:]\s*([^\n]+)', section)
        if role_match:
            role = _map_role(role_match.group(1).strip())

        motivation = ""
        mot_match = re.search(r'核心动机[：:]\s*([^\n]+)', section)
        if mot_match:
            motivation = mot_match.group(1).strip()[:500]

        conflict = ""
        conflict_match = re.search(r'核心冲突[：:]\s*([^\n]+)', section)
        if conflict_match:
            conflict = conflict_match.group(1).strip()[:500]

        arc = ""
        arc_match = re.search(r'人物弧[：:]\s*([^\n]+)', section)
        if arc_match:
            arc = arc_match.group(1).strip()[:500]

        personality = ""
        pers_match = re.search(r'说话风格[：:]\s*([^\n]+)', section)
        if pers_match:
            personality = pers_match.group(1).strip()[:500]

        if not motivation and conflict:
            motivation = conflict

        characters.append({
            "name": name,
            "role": role,
            "personality": personality,
            "core_motivation": motivation,
            "growth_arc": arc,
        })

    # 备选：管道分隔格式
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
    """解析大纲响应"""
    title = ""
    summary = ""
    world_setting = {}
    plot_points = []
    emotional_curve = ""

    # 提取标题
    m = re.search(r"《(.+?)》", response)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r"(?:#{1,3}\s*)?标题[：:]\s*(.+?)(?:\n|$)", response)
        if m:
            title = m.group(1).strip()

    # 提取概述
    m = re.search(r"(?:#{1,3}\s*)?概述[：:]?\s*(.+?)(?=\n#{1,3}|\n---|\Z)", response, re.DOTALL)
    if m:
        summary = m.group(1).strip()[:2000]

    # 提取章节数
    m = re.search(r'建议章节数[：:]\s*(\d+)', response)
    if m:
        chapter_count = int(m.group(1))
    m = re.search(r'共(\d+)章', response)
    if m:
        chapter_count = int(m.group(1))

    # 提取世界观与势力
    world_setting = _parse_world_setting(response)

    # 提取情节节点
    plot_points = _parse_plot_points(response)

    # 提取情感曲线
    emotional_curve = _parse_emotional_curve(response)

    return {
        "title": title,
        "summary": summary,
        "plot_points": plot_points,
        "characters": [],
        "world_setting": world_setting,
        "emotional_curve": emotional_curve,
        "chapter_count_suggested": chapter_count,
    }


def _parse_world_setting(response: str) -> dict:
    """解析大纲中的世界观与势力部分"""
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

    for line in section.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = re.match(r'(\d+)\.\s*(.+?)$', line)
        if not match:
            continue

        order = int(match.group(1))
        content = match.group(2)

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

    m = re.search(r'([^\n→]+)\s*→\s*([^\n→]+)\s*→\s*([^\n→]+)\s*→\s*([^\n]+)', section)
    if m:
        parts = [p.strip() for p in m.groups()]
        return " → ".join(parts)

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

    outline_data = _parse_outline(response, chapter_count)

    result = kb.outlines.upsert({
        "title": outline_data.get("title", "待命名"),
        "summary": outline_data.get("summary", ""),
        "plot_points": outline_data.get("plot_points", []),
        "characters": outline_data.get("characters", []),
        "world_setting": outline_data.get("world_setting", {}),
        "emotional_curve": outline_data.get("emotional_curve", ""),
        "confirmed": True,
        "chapter_count_suggested": outline_data.get("chapter_count_suggested", chapter_count),
        "chapter_count_confirmed": True,
    })
    return result["id"], outline_data.get("summary", "")


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

    constraints = kb.styles.create_constraints({
        "taboo_words": [],
        "forbidden_patterns": [],
        "style_anchor": response,
        "abstract_rules": [],
    })
    return constraints["id"]


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

    Yields:
        SSE 事件字符串
    """
    yield format_init_start()

    llm = None
    try:
        from app.utils.llm import resolve_llm_service
        llm = resolve_llm_service(
            model_config_id=model_config_id,
            user_id=user_id,
            model_name=model_id,
        )
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

    wave1_tasks = [
        asyncio.create_task(run_novel_name()),
        asyncio.create_task(run_world_setting()),
        asyncio.create_task(run_outline()),
    ]

    events_received = 0
    expected_events = 3
    wave1_cancelled = False
    wave1_timeout = False

    while events_received < expected_events:
        try:
            event_type, data = await asyncio.wait_for(event_queue.get(), timeout=120.0)
            if event_type == "_cancelled":
                wave1_cancelled = True
                break
            events_received += 1
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
    async def run_characters():
        try:
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

    events_received2 = 0
    expected_events2 = 2
    wave2_cancelled = False
    wave2_timeout = False

    while events_received2 < expected_events2:
        try:
            event_type, data = await asyncio.wait_for(event_queue.get(), timeout=120.0)
            if event_type == "_cancelled":
                wave2_cancelled = True
                break
            events_received2 += 1
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
