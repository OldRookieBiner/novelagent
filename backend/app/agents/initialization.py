"""项目初始化节点

根据用户输入的概念描述，初始化项目的基础知识库（串行依赖，下游可见完整前序产物）：
1. 概念 → 故事种子
2. 故事种子 → [小说名, 大纲] 并行
3. 故事种子 + 大纲 → 世界观
4. 故事种子 + 大纲 + 世界观 → [角色(返回 名字→id 映射), 风格] 并行
5. 角色映射 → 关系；大纲伏笔信息 → 伏笔入库

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
    RELATION_GENERATION_PROMPT,
    OUTLINE_GENERATION_PROMPT,
    STYLE_SETUP_PROMPT,
)
from app.agents.nodes_utils import safe_format, parse_world_setting_response, extract_json_block

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
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=8192):
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


def _normalize_tiered(parsed: dict) -> dict:
    """将解析出的世界观规整为前端期望的字符串数组结构"""
    ts = parsed.get("tiered_settings") or {}
    result = {"red": [], "yellow": [], "green": []}
    for tier in ("red", "yellow", "green"):
        items = ts.get(tier) or []
        for item in items:
            # JSON 可能误产出 {"rule": ...} 对象，统一压成字符串
            if isinstance(item, dict):
                rule = item.get("rule") or item.get("content") or ""
                cost = item.get("cost")
                text = f"{rule}（代价：{cost}）" if cost else rule
                if text:
                    result[tier].append(str(text))
            elif item is not None and str(item).strip():
                result[tier].append(str(item).strip())
    return result


def _normalize_locations(parsed: dict) -> list:
    """关键地点规整为字符串数组"""
    locs = parsed.get("key_locations") or []
    out = []
    for loc in locs:
        if isinstance(loc, dict):
            name = loc.get("name") or ""
            desc = loc.get("description") or loc.get("role") or ""
            text = f"{name}：{desc}" if desc else name
            if text:
                out.append(str(text))
        elif loc is not None and str(loc).strip():
            out.append(str(loc).strip())
    return out


async def generate_world_setting(
    story_seed: str,
    kb: KnowledgeBaseService,
    llm,
    title: str = "",
    outline_summary: str = "",
    request=None,
) -> Tuple[Optional[int], str]:
    """根据故事种子 + 大纲生成世界观，返回 (id, 文本内容)

    优先解析 JSON 输出；失败时降级到旧 Markdown 正则解析。
    """
    outline_text = (outline_summary or story_seed)
    prompt = safe_format(
        WORLD_SETTING_PROMPT,
        title=title or "（未命名）",
        outline=outline_text,
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=16384):
        response += chunk
        await check_disconnect(request)

    parsed = extract_json_block(response)
    if not isinstance(parsed, dict) or not parsed.get("tiered_settings"):
        # 降级：旧正则解析
        logger.warning("世界观 JSON 解析失败，降级到正则解析")
        parsed = parse_world_setting_response(response)

    world_setting = kb.world_setting.create({
        "core_concept": parsed.get("core_concept") or response.strip()[:500],
        "tiered_settings": _normalize_tiered(parsed),
        "key_locations": _normalize_locations(parsed),
    })
    return world_setting["id"], response


# 角色 JSON 可写入的字段白名单（对齐 Character 模型列）
_CHARACTER_FIELDS = {
    "name", "role", "personality", "catchphrase", "habit_action",
    "deep_fear", "core_motivation", "growth_arc", "appearance",
    "backstory", "signature_item", "knowledge_boundary",
    "speech_style", "speech_samples",
}


def _coerce_str(value) -> str:
    """把 JSON 里可能出现的 list/dict 字段压成字符串，便于存入 Text 列"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "；".join(_coerce_str(v) for v in value if v is not None)
    if isinstance(value, dict):
        # 知识边界常见 {"unknown": [...], "misbelief": [...]} 结构
        parts = []
        for k, v in value.items():
            parts.append(f"{k}：{_coerce_str(v)}")
        return "；".join(parts)
    return str(value)


def _normalize_character(raw: dict) -> Optional[dict]:
    """将一条角色 JSON 规整为可入库的 dict（仅保留模型字段）"""
    if not isinstance(raw, dict):
        return None
    name = _coerce_str(raw.get("name"))
    if not name or len(name) > 15:
        return None
    data = {"name": name, "role": _map_role(_coerce_str(raw.get("role")) or "配角")}
    for field in _CHARACTER_FIELDS:
        if field in ("name", "role"):
            continue
        if field in raw:
            data[field] = _coerce_str(raw.get(field))[:2000]
    return data


def _format_plot_clue(plot_points: Optional[list]) -> str:
    """把大纲情节节点压成简短线索文本（事件 + 冲突 + 钩子），供角色生成参考"""
    if not plot_points:
        return ""
    lines = []
    for pp in plot_points:
        if not isinstance(pp, dict):
            continue
        parts = [str(pp.get("event") or "").strip()]
        conflict = str(pp.get("conflict") or "").strip()
        hook = str(pp.get("hook") or "").strip()
        if conflict:
            parts.append(f"冲突：{conflict}")
        if hook:
            parts.append(f"钩子：{hook}")
        text = "｜".join(p for p in parts if p)
        if text:
            order = pp.get("order")
            prefix = f"{order}. " if isinstance(order, int) else "- "
            lines.append(f"{prefix}{text}")
    return "\n".join(lines)


async def generate_characters(story_seed: str, world_setting_text: str, kb: KnowledgeBaseService, llm, outline_text: str = "", plot_points: Optional[list] = None, request=None) -> Tuple[int, dict, dict]:
    """根据大纲 + 世界观生成角色（含全字段）

    优先解析 JSON；失败时降级到旧 Markdown 正则解析。

    Returns:
        (创建的角色数量, 名字→角色id 映射, 名字→角色画像 映射)
    """
    # 把大纲情节节点（事件/冲突/钩子）作为线索拼进 outline 上下文，
    # 帮助角色阵容与情节中出现的人物对齐
    plot_clue = _format_plot_clue(plot_points)
    outline_ctx = (outline_text or story_seed)
    if plot_clue:
        outline_ctx = f"{outline_ctx}\n\n## 情节线索\n{plot_clue}"
    prompt = safe_format(CHARACTER_GENERATION_PROMPT,
        outline=outline_ctx,
        world_setting=world_setting_text,
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=16384):
        response += chunk
        await check_disconnect(request)

    parsed = extract_json_block(response)
    characters = []
    if isinstance(parsed, list):
        for raw in parsed:
            norm = _normalize_character(raw)
            if norm:
                characters.append(norm)

    # 降级：旧正则解析（仅 5 字段）
    if not characters:
        logger.warning(
            f"角色 JSON 解析失败，降级到正则解析。"
            f"Response length: {len(response)}, first 200 chars: {response[:200]}"
        )
        characters = _parse_characters(response)

    if not characters:
        logger.warning("角色解析彻底失败，本步骤跳过")
        return 0, {}, {}

    name_to_id = {}
    name_to_profile = {}
    for char_data in characters:
        created = kb.characters.create_character(char_data)
        if created and created.get("id") is not None:
            name_to_id[char_data["name"]] = created["id"]
            name_to_profile[char_data["name"]] = {
                "role": char_data.get("role") or "",
                "core_motivation": char_data.get("core_motivation") or "",
                "personality": char_data.get("personality") or "",
            }

    logger.info(f"Successfully created {len(characters)} characters")
    return len(characters), name_to_id, name_to_profile


# 关系类型/方向的合法取值（对齐 Relation 模型与 schema 枚举）
_RELATION_TYPES = {"信任", "敌对", "感情", "合作", "利用", "陌生"}
_RELATION_DIRECTIONS = {"双向", "单向A→B", "单向B→A"}


def _format_character_desc(name: str, profile: Optional[dict]) -> str:
    """把角色画像压成一行描述，供关系生成 prompt 使用"""
    if not profile:
        return f"- {name}"
    fields = [name]
    role = (profile.get("role") or "").strip()
    motivation = (profile.get("core_motivation") or "").strip()
    personality = (profile.get("personality") or "").strip()
    if role:
        fields.append(role)
    if motivation:
        fields.append(f"动机：{motivation}")
    if personality:
        fields.append(f"性格：{personality}")
    return "- " + " | ".join(fields)


async def generate_relations(name_to_id: dict, kb: KnowledgeBaseService, llm, name_to_profile: Optional[dict] = None, request=None) -> int:
    """根据已入库角色生成人物关系，返回创建的关系数量

    依赖初始化内构建的"名字→id"映射做入库时的 id 查找（不做按名回查）；
    name_to_profile 仅用于丰富给 LLM 的角色描述，不参与 id 查找。
    """
    if len(name_to_id) < 2:
        return 0

    name_to_profile = name_to_profile or {}
    characters_desc = "\n".join(
        _format_character_desc(name, name_to_profile.get(name))
        for name in name_to_id.keys()
    )
    prompt = safe_format(RELATION_GENERATION_PROMPT, characters=characters_desc)
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=8192):
        response += chunk
        await check_disconnect(request)

    parsed = extract_json_block(response)
    if not isinstance(parsed, list):
        logger.warning("关系 JSON 解析失败，跳过关系生成")
        return 0

    created_count = 0
    for raw in parsed:
        if not isinstance(raw, dict):
            continue
        a_name = _coerce_str(raw.get("character_a_name"))
        b_name = _coerce_str(raw.get("character_b_name"))
        a_id = name_to_id.get(a_name)
        b_id = name_to_id.get(b_name)
        if not a_id or not b_id or a_id == b_id:
            continue
        rel_type = _coerce_str(raw.get("relation_type"))
        if rel_type not in _RELATION_TYPES:
            rel_type = "陌生"
        direction = _coerce_str(raw.get("direction"))
        if direction not in _RELATION_DIRECTIONS:
            direction = "双向"
        trust = raw.get("trust_level", 50)
        try:
            trust = max(0, min(100, int(trust)))
        except (TypeError, ValueError):
            trust = 50
        try:
            kb.characters.create_relation({
                "character_a_id": a_id,
                "character_b_id": b_id,
                "relation_type": rel_type,
                "direction": direction,
                "current_status": _coerce_str(raw.get("current_status"))[:500],
                "trust_level": trust,
            })
            created_count += 1
        except Exception as e:
            logger.warning(f"创建关系失败 {a_name}-{b_name}: {e}")

    logger.info(f"Successfully created {created_count} relations")
    return created_count


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
        "world_setting": world_setting,
        "emotional_curve": emotional_curve,
        # 正则降级无法可靠提取主题，置空保持与 JSON 路径字段一致
        "theme": "",
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


def _extract_foreshadowing_content(raw: str) -> str:
    """从降级路径伏笔字段提取实质内容，无实质内容时返回空串。

    降级路径下，情节节点的第 4 段通常形如 "V1: 埋设龙印" 或纯标签 "V1"。
    去除起始的 V/编号前缀及分隔符后，若仍有实质文本则视为伏笔内容；
    纯标签（如 "V1"）返回空串，避免 generate_foreshadowings 入库无意义条目。
    级别推断仍由调用方基于原始标签全文进行，故此处只关心内容。
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    # 去除起始的 V/编号前缀及其后的分隔符（: ：. 、- , ， 空格）
    stripped = re.sub(r'^([Vv]\d+|\d+)\s*[:：.\-、,，]?\s*', '', raw).strip()
    return stripped


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

        foreshadowing_raw = parts[3] if len(parts) > 3 else ""
        # 仅当去除编号前缀后仍有实质文本才回填 content，纯标签（如 V1）置空
        foreshadowing_content = _extract_foreshadowing_content(foreshadowing_raw)

        plot_points.append({
            "order": order,
            "event": parts[0] if len(parts) > 0 else "",
            "conflict": parts[1] if len(parts) > 1 else "",
            "hook": parts[2] if len(parts) > 2 else "",
            # 保留原始标签全文，供 _infer_foreshadowing_level 推断级别
            "foreshadowing": foreshadowing_raw,
            "foreshadowing_content": foreshadowing_content,
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


def _normalize_outline_json(parsed: dict, chapter_count: int) -> dict:
    """将大纲 JSON 规整为可入库结构"""
    plot_points = []
    for pp in parsed.get("plot_points") or []:
        if not isinstance(pp, dict):
            continue
        plot_points.append({
            "order": pp.get("order"),
            "event": str(pp.get("event") or ""),
            "conflict": str(pp.get("conflict") or ""),
            "hook": str(pp.get("hook") or ""),
            "foreshadowing": str(pp.get("foreshadowing_label") or pp.get("foreshadowing") or ""),
            "foreshadowing_label": str(pp.get("foreshadowing_label") or ""),
            "foreshadowing_content": str(pp.get("foreshadowing_content") or ""),
        })
    suggested = parsed.get("chapter_count_suggested")
    try:
        suggested = int(suggested)
    except (TypeError, ValueError):
        suggested = chapter_count
    return {
        "title": str(parsed.get("title") or "").strip(),
        "summary": str(parsed.get("summary") or "").strip()[:2000],
        "plot_points": plot_points,
        "emotional_curve": str(parsed.get("emotional_curve") or "").strip(),
        "theme": str(parsed.get("theme") or "").strip(),
        "chapter_count_suggested": suggested,
    }


async def generate_outline(story_seed: str, kb: KnowledgeBaseService, llm, target_words: int, request=None) -> Tuple[Optional[int], dict]:
    """根据故事种子生成大纲，返回 (id, 完整 outline_data)

    优先解析 JSON；失败时降级到旧 Markdown 正则解析。
    """
    chapter_count = max(10, min(50, target_words // 5000))

    prompt = safe_format(OUTLINE_GENERATION_PROMPT,
        story_seed=story_seed,
        chapter_count=str(chapter_count),
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=16384):
        response += chunk
        await check_disconnect(request)

    parsed = extract_json_block(response)
    if isinstance(parsed, dict) and (parsed.get("title") or parsed.get("plot_points")):
        outline_data = _normalize_outline_json(parsed, chapter_count)
    else:
        # 记录响应摘要，便于定位是截断、非 JSON 还是格式瑕疵导致的解析失败
        snippet = (response or "").strip().replace("\n", " ")[:200]
        logger.warning(
            f"大纲 JSON 解析失败，降级到正则解析。"
            f"响应长度={len(response)}，前200字={snippet}"
        )
        outline_data = _parse_outline(response, chapter_count)
        # 降级正则对 JSON 文本几乎提取不到内容，summary 为空说明本次大纲质量严重退化
        if not (outline_data.get("summary") or "").strip():
            logger.error(
                "大纲降级解析后概述仍为空，入库大纲将仅含标题/章节数，"
                "请检查 LLM 输出格式（疑似 JSON 瑕疵或非 JSON 输出）"
            )

    result = kb.outlines.upsert({
        "title": outline_data.get("title") or "待命名",
        "summary": outline_data.get("summary", ""),
        "plot_points": outline_data.get("plot_points", []),
        # 角色由 Character 表承载，Outline.characters 初始化阶段刻意不写（保留列不删）
        # 世界观由波次 2 的 WorldSetting 表承载，Outline.world_setting 初始化阶段刻意不写
        "emotional_curve": outline_data.get("emotional_curve", ""),
        "theme": outline_data.get("theme", ""),
        # 初始化生成的总纲为草稿，需作者显式确认后才进入结构阶段
        "confirmed": False,
        "chapter_count_suggested": outline_data.get("chapter_count_suggested", chapter_count),
        "chapter_count_confirmed": False,
    })
    outline_data["id"] = result["id"]
    return result["id"], outline_data


def _infer_foreshadowing_level(label: str) -> str:
    """从伏笔标签推断重要级别（对齐 Foreshadowing.level: hint/clue/major）"""
    label = (label or "")
    if "回收" in label or "高潮" in label or "结局" in label:
        return "major"
    if "强化" in label or "线索" in label:
        return "clue"
    return "hint"


async def generate_foreshadowings(outline_data: dict, kb: KnowledgeBaseService) -> int:
    """从大纲 plot_points 的伏笔信息聚合入库，返回创建数量

    仅对"埋设"性质的伏笔建条目（回收说明不重复建条目），
    并尽量补全 level / planted_chapter 字段，便于后续追踪。
    """
    plot_points = outline_data.get("plot_points") or []
    created = 0
    seen = set()
    for pp in plot_points:
        if not isinstance(pp, dict):
            continue
        content = (pp.get("foreshadowing_content") or "").strip()
        if not content or content in seen:
            continue
        # 仅回收说明（无新内容）跳过，避免把回收行当成新伏笔
        label = str(pp.get("foreshadowing_label") or pp.get("foreshadowing") or "")
        if "回收" in label and "埋" not in label and len(content) < 4:
            continue
        seen.add(content)
        order = pp.get("order")
        planted = order if isinstance(order, int) else None
        try:
            kb.foreshadowings.create({
                "content": content[:1000],
                "level": _infer_foreshadowing_level(label),
                "planted_chapter": planted,
                "status": "active",
            })
            created += 1
        except Exception as e:
            logger.warning(f"创建伏笔失败: {e}")
    if created:
        logger.info(f"Successfully created {created} foreshadowings")
    return created


def _str_list(value) -> list:
    """把 JSON 字段规整为字符串列表"""
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict):
                v = v.get("rule") or v.get("word") or v.get("pattern") or ""
            if v is not None and str(v).strip():
                out.append(str(v).strip())
        return out
    return []


async def generate_style(story_seed: str, outline_text: str, world_setting_text: str, kb: KnowledgeBaseService, llm, request=None) -> Optional[int]:
    """生成风格约束（四字段全部写入）

    优先解析 JSON；失败时把整段响应存入 style_anchor 作为降级。
    """
    prompt = safe_format(STYLE_SETUP_PROMPT,
        outline=(outline_text or story_seed),
        world_setting=(world_setting_text or story_seed),
        user_preference="",
    )
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}], temperature=0.5, max_tokens=8192):
        response += chunk
        await check_disconnect(request)

    parsed = extract_json_block(response)
    if isinstance(parsed, dict):
        constraints = kb.styles.create_constraints({
            "taboo_words": _str_list(parsed.get("taboo_words")),
            "forbidden_patterns": _str_list(parsed.get("forbidden_patterns")),
            "style_anchor": str(parsed.get("style_anchor") or "").strip() or response,
            "abstract_rules": _str_list(parsed.get("abstract_rules")),
        })
    else:
        logger.warning("风格 JSON 解析失败，降级到整段存入 style_anchor")
        constraints = kb.styles.create_constraints({
            "taboo_words": [],
            "forbidden_patterns": [],
            "style_anchor": response,
            "abstract_rules": [],
        })
    return constraints["id"]


# 波次排空的内部哨兵，区分取消/超时
_SENTINEL_CANCELLED = object()
_SENTINEL_TIMEOUT = object()


async def _drain_wave(event_queue, tasks, expected: int, project_id: int, dispatch: dict):
    """排空一个并行波次的事件队列，按 dispatch 映射格式化为 SSE 字符串逐个 yield

    - dispatch: {事件类型: format_init_* 函数}
    - error 事件统一走 format_init_error
    - 收到取消/超时时 yield 对应哨兵后停止（调用方负责收尾）
    结束前 gather 所有任务，吞掉异常（失败节点已通过 error 事件上报）。
    """
    received = 0
    outcome = None
    while received < expected:
        try:
            event_type, data = await asyncio.wait_for(event_queue.get(), timeout=120.0)
        except asyncio.TimeoutError:
            logger.error("Wave timeout waiting for events")
            outcome = _SENTINEL_TIMEOUT
            break
        if event_type == "_cancelled":
            outcome = _SENTINEL_CANCELLED
            break
        received += 1
        if event_type == "error":
            yield format_init_error(data)
        elif event_type in dispatch:
            yield dispatch[event_type](data)
        else:
            logger.warning(f"Unknown wave event type: {event_type}")

    await asyncio.gather(*tasks, return_exceptions=True)
    if outcome is not None:
        yield outcome


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

    执行分波（串行依赖）：
    - 波次 0: 故事种子 ← concept
    - 波次 1: [小说名, 大纲] 并行 ← story_seed
    - 波次 2: 世界观 ← story_seed + 大纲标题/概述
    - 波次 3: [角色, 风格] 并行 ← story_seed + 大纲文本 + 世界观文本（角色返回 名字→id 映射）
    - 波次 4: [关系, 伏笔] 并行 ← 角色映射 / 大纲伏笔信息

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

    # ===== 波次 1: 并行生成小说名、大纲 =====
    event_queue: asyncio.Queue = asyncio.Queue()
    novel_name = "新建项目"
    outline_id = None
    outline_data: dict = {}

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

    async def run_outline():
        nonlocal outline_id, outline_data
        try:
            outline_id, outline_data = await generate_outline(story_seed, kb, llm, target_words, request=request)
            await event_queue.put(("outline", {
                "outline_id": outline_id,
                "chapter_count": outline_data.get("chapter_count_suggested") or max(10, target_words // 5000),
                "plot_point_count": len(outline_data.get("plot_points") or []),
            }))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate outline: {e}")
            await event_queue.put(("error", {"stage": "outline", "error": str(e)}))

    wave1_tasks = [
        asyncio.create_task(run_novel_name()),
        asyncio.create_task(run_outline()),
    ]

    async for event_str in _drain_wave(
        event_queue, wave1_tasks, expected=2, project_id=project_id,
        dispatch={
            "novel_name": format_init_novel_name,
            "outline": format_init_outline,
        },
    ):
        if event_str is _SENTINEL_CANCELLED:
            yield format_init_cancelled({"reason": "客户端断开连接"})
            yield format_init_done({"project_id": project_id, "status": "cancelled"})
            return
        if event_str is _SENTINEL_TIMEOUT:
            yield format_init_timeout({"reason": "等待事件超时"})
            yield format_init_done({"project_id": project_id, "status": "timeout"})
            return
        yield event_str

    # 大纲是下游关键依赖，失败则终止
    if outline_id is None:
        yield format_init_error({"stage": "outline", "error": "大纲生成失败"})
        yield format_init_done({"project_id": project_id, "status": "partial"})
        return

    # 大纲标题/概述供世界观参考
    outline_title = outline_data.get("title") or ""
    outline_summary = outline_data.get("summary") or ""

    # ===== 波次 2: 生成世界观（依赖大纲）=====
    world_setting_text = ""
    try:
        world_setting_id, world_setting_text = await generate_world_setting(
            story_seed, kb, llm,
            title=outline_title,
            outline_summary=outline_summary,
            request=request,
        )
        yield format_init_world({"world_setting_id": world_setting_id})
    except InitializationCancelledError as e:
        yield format_init_cancelled({"reason": str(e)})
        yield format_init_done({"project_id": project_id, "status": "cancelled"})
        return
    except InitializationTimeoutError as e:
        yield format_init_timeout({"reason": str(e)})
        yield format_init_done({"project_id": project_id, "status": "timeout"})
        return
    except Exception as e:
        logger.error(f"Failed to generate world setting: {e}")
        yield format_init_error({"stage": "world_setting", "error": str(e)})
        yield format_init_done({"project_id": project_id, "status": "partial"})
        return

    # 组装供下游使用的大纲文本（标题 + 概述）
    outline_text = "\n".join(p for p in (
        f"《{outline_title}》" if outline_title else "",
        outline_summary,
    ) if p)

    # ===== 波次 3: 并行生成角色、风格 =====
    name_to_id: dict = {}
    name_to_profile: dict = {}

    async def run_characters():
        nonlocal name_to_id, name_to_profile
        try:
            ws_text = world_setting_text if world_setting_text else story_seed
            count, name_to_id, name_to_profile = await generate_characters(
                story_seed, ws_text, kb, llm,
                outline_text=outline_text,
                plot_points=outline_data.get("plot_points"),
                request=request,
            )
            await event_queue.put(("characters", {"character_count": count}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate characters: {e}")
            await event_queue.put(("error", {"stage": "characters", "error": str(e)}))

    async def run_style():
        try:
            ws_text = world_setting_text if world_setting_text else story_seed
            style_id = await generate_style(
                story_seed,
                outline_text or story_seed,
                ws_text,
                kb, llm, request=request,
            )
            await event_queue.put(("style", {"style_constraints_id": style_id}))
        except (InitializationCancelledError, InitializationTimeoutError) as e:
            await event_queue.put(("_cancelled", {"reason": str(e)}))
            raise
        except Exception as e:
            logger.error(f"Failed to generate style: {e}")
            await event_queue.put(("error", {"stage": "style", "error": str(e)}))

    wave3_tasks = [
        asyncio.create_task(run_characters()),
        asyncio.create_task(run_style()),
    ]

    async for event_str in _drain_wave(
        event_queue, wave3_tasks, expected=2, project_id=project_id,
        dispatch={
            "characters": format_init_characters,
            "style": format_init_style,
        },
    ):
        if event_str is _SENTINEL_CANCELLED:
            yield format_init_cancelled({"reason": "客户端断开连接"})
            yield format_init_done({"project_id": project_id, "status": "cancelled"})
            return
        if event_str is _SENTINEL_TIMEOUT:
            yield format_init_timeout({"reason": "等待事件超时"})
            yield format_init_done({"project_id": project_id, "status": "timeout"})
            return
        yield event_str

    # 角色是波次 4 的关键依赖，为空则终止
    if not name_to_id:
        yield format_init_error({"stage": "characters", "error": "角色生成失败"})
        yield format_init_done({"project_id": project_id, "status": "partial"})
        return

    # ===== 波次 4: 关系（依赖角色映射）+ 伏笔（依赖大纲）=====
    relation_count = 0
    foreshadowing_count = 0
    try:
        relation_count = await generate_relations(name_to_id, kb, llm, name_to_profile=name_to_profile, request=request)
    except (InitializationCancelledError, InitializationTimeoutError) as e:
        yield format_init_cancelled({"reason": str(e)})
        yield format_init_done({"project_id": project_id, "status": "cancelled"})
        return
    except Exception as e:
        logger.error(f"Failed to generate relations: {e}")
        yield format_init_error({"stage": "relations", "error": str(e)})

    try:
        foreshadowing_count = await generate_foreshadowings(outline_data, kb)
    except Exception as e:
        logger.error(f"Failed to generate foreshadowings: {e}")
        yield format_init_error({"stage": "foreshadowings", "error": str(e)})

    # 完成
    yield format_init_complete({
        "project_id": project_id,
        "name": novel_name,
        "relation_count": relation_count,
        "foreshadowing_count": foreshadowing_count,
    })
    yield format_init_done({"project_id": project_id, "status": "complete"})
