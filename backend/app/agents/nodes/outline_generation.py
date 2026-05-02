"""大纲生成节点"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_OUTLINE
from app.services.prompt_loader import get_system_prompt
from app.database import SessionLocal
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state_async

# 预编译正则表达式，提升性能
# 标题匹配模式：支持多种格式
# 1. "标题：《xxx》"
# 2. "# 一、标题\n《xxx》"
# 3. "# 小说大纲：xxx"
# 4. "# 《xxx》"
RE_TITLE = re.compile(r"(?:##\s*)?(?:\*\*)?标题(?:\*\*)?[：:]\s*(.+?)(?:\n|$)")
RE_TITLE_OUTLINE = re.compile(r"#\s*小说大纲[：:]\s*(.+?)(?:\n|$)")
RE_TITLE_BRACKET = re.compile(r"#\s*《(.+?)》")
RE_TITLE_CHAPTER = re.compile(r"#\s*[一二三四五六七八九十]+[、.].*\n《(.+?)》")  # 新增：# 一、标题 后面跟《xxx》

# 概述匹配模式：支持 “三、人物设定” / “# 三、人物设定” 等后续标题格式
RE_SUMMARY = re.compile(
    r"(?:##\s*)?(?:\*\*)?概述(?:\*\*)?[：:]\s*(.+?)(?=(?:\n[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?(?:人物设定|世界观|主要情节节点|情节节点)|---|\n\d+\.)",
    re.DOTALL,
)
RE_SUMMARY_MD = re.compile(
    r"(?:##\s*)?(?:\*\*)?概述(?:\*\*)?\s*\n+(.+?)(?=(?:\n[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?(?:人物设定|世界观|主要情节节点|情节节点)|$)",
    re.DOTALL,
)
# 新增：支持 # 二、概述 后面直接跟内容的格式
RE_SUMMARY_CHAPTER = re.compile(
    r"#\s*[一二三四五六七八九十]+[、.].*\n概述\s*\n+(.+?)(?=(?:\n#|\n##)|$)",
    re.DOTALL,
)

# 情节节点匹配模式 - 支持多种格式
# 1. "1. 开篇：... | ..."
# 2. "1. **开篇：...**"
# 3. "## 第一章：...\n1. 开篇：..."
RE_PLOT_BOLD = re.compile(r"\d+\.\s*(?:\*\*)?(.+?)(?:\*\*)?\s*\n", re.DOTALL)
RE_PLOT_FALLBACK = re.compile(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", re.DOTALL)
RE_PLOT_CHAPTER = re.compile(r"\d+\.\s*\*\*?([^|*]+)\*\*?[：:]*\s*(.+?)(?=\n\d+\.|$)", re.DOTALL)  # 支持带章节名的情况

# 章节数匹配模式
RE_CHAPTER_COUNT = re.compile(r"建议章节数[：:]\s*(\d+)")

# ==================== 章节数计算常量 ====================
# 根据目标字数计算章节数的配置
# 参考：超短篇 1-5万字，短篇 5-20万字，中篇 20-50万字，长篇 50-100万字，超长篇 100万字+

# 默认章节数
DEFAULT_CHAPTER_COUNT = 40

# 字数阈值（字）
WORDS_THRESHOLD_SHORT = 50000      # 超短篇上限
WORDS_THRESHOLD_MEDIUM = 200000    # 短篇上限
WORDS_THRESHOLD_LONG = 500000      # 中篇上限
WORDS_THRESHOLD_VERY_LONG = 1000000  # 长篇上限

# 每章目标字数
WORDS_PER_CHAPTER_SHORT = 3500     # 超短篇：约3500字/章
WORDS_PER_CHAPTER_MEDIUM = 4000    # 短篇：约4000字/章
WORDS_PER_CHAPTER_LONG = 5000      # 中篇：约5000字/章
WORDS_PER_CHAPTER_VERY_LONG = 6000 # 长篇：约6000字/章
WORDS_PER_CHAPTER_EPIC = 7000      # 超长篇：约7000字/章

# 最小章节数
MIN_CHAPTERS_SHORT = 5
MIN_CHAPTERS_MEDIUM = 15
MIN_CHAPTERS_LONG = 40
MIN_CHAPTERS_VERY_LONG = 80
MIN_CHAPTERS_EPIC = 150


def parse_outline(response: str) -> Dict[str, Any]:
    """从 AI 响应中解析大纲（增强版）

    支持多种 LLM 输出格式：
    - 格式 A：- 主角：叶辰 | 性格 | 动机 | 弧线
    - 格式 B：### 主角 | 叶辰\\n- **核心性格**：xxx
    - 格式 C：- **主角：叶辰 | 描述**\\n  - 口头禅：xxx\\n  - 核心动机：xxx

    返回结构：
    {
        "title": str,
        "summary": str,
        "characters": [{"name", "role", "personality", "motivation", "arc"}],
        "world_setting": {"era", "core_rules", "power_system"},
        "plot_points": [{"order", "event", "conflict", "hook"}],
        "emotional_curve": str
    }
    """
    outline = {
        "title": "",
        "summary": "",
        "characters": [],
        "world_setting": {},
        "plot_points": [],
        "emotional_curve": ""
    }

    # 提取标题 - 支持多种格式
    title_match = RE_TITLE.search(response)
    if not title_match:
        title_match = RE_TITLE_OUTLINE.search(response)
    if not title_match:
        title_match = RE_TITLE_BRACKET.search(response)
    if not title_match:
        title_match = RE_TITLE_CHAPTER.search(response)  # 新增
    if title_match:
        title = title_match.group(1).strip()
        # 清理标题 - 移除书名号
        if title.startswith("《") and title.endswith("》"):
            title = title[1:-1]
        outline["title"] = title

    # 提取概述 - 支持多种格式
    summary_match = RE_SUMMARY.search(response)
    if not summary_match:
        summary_match = RE_SUMMARY_MD.search(response)
    if not summary_match:
        summary_match = RE_SUMMARY_CHAPTER.search(response)  # 新增
    if summary_match:
        outline["summary"] = summary_match.group(1).strip()

    # 提取人物设定
    _parse_characters_section(response, outline)

    # 提取世界观
    _parse_world_setting(response, outline)

    # 提取情节节点
    _parse_plot_points(response, outline)

    # 提取情感曲线
    _parse_emotional_curve(response, outline)

    return outline


def _parse_characters_section(response: str, outline: Dict[str, Any]):
    """从响应中提取人物设定，支持多种格式"""
    # 匹配 "人物设定（xxx）" 或 "三、人物设定" 等变体
    characters_section = re.search(
        r"(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?人物设定(?:[（(][^)）]*[)）])?[：:\s]*\n*(.+?)(?=(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?(?:世界观|情节节点|情感曲线)|---|$)",
        response,
        re.DOTALL
    )
    if not characters_section:
        return

    chars_text = characters_section.group(1)

    # 角色类型关键词
    role_keywords = r"(主角|核心反派|重要配角\d*|配角\d*)"

    # 找到所有角色行（支持 - **主角：xxx 或 - 主角：xxx 或 ### 主角 等格式）
    role_line_pattern = re.compile(
        r"(?:^|\n)[-•]\s*\*{0,2}\s*" + role_keywords + r"\s*[：:]"
        r"|(?:^|\n)###\s*" + role_keywords,
        re.MULTILINE
    )
    role_starts = list(role_line_pattern.finditer(chars_text))

    if not role_starts:
        return

    for idx, m in enumerate(role_starts):
        start = m.start()
        # 如果匹配到换行符开头的，跳过换行符
        if chars_text[start] == '\n':
            start += 1

        # 确定这个角色块的结束位置：下一个角色行的开始，或文本末尾
        if idx + 1 < len(role_starts):
            block_end = role_starts[idx + 1].start()
        else:
            block_end = len(chars_text)

        block_text = chars_text[start:block_end]
        lines = block_text.split('\n')

        # 第一行是角色主行
        first_line = lines[0]
        role = m.group(1) or m.group(2)
        role = role.strip()

        # ### 格式（Format B）
        if '###' in first_line:
            # ### 主角：姓名 | 描述
            after_hash = re.sub(r'^###\s*', '', first_line)
            # 先去掉 ** 包裹
            after_hash = after_hash.strip().rstrip('*').strip()
            pipe_parts = [p.strip() for p in after_hash.split('|')]
            # parts[0] = "主角：姓名" 或 "主角"
            first_part = pipe_parts[0]
            # 提取冒号后的名字
            colon_match = re.search(r'[：:]\s*(.+)$', first_part)
            if colon_match:
                name = colon_match.group(1).strip()
            else:
                name = first_part.replace(role, '').strip().strip('：:').strip()
            # 清理 name 中的 ** 标记
            name = re.sub(r'\*\*', '', name).strip()
            # parts[1] 作为 personality（如果有）
            personality = pipe_parts[1] if len(pipe_parts) > 1 else ''
            personality = re.sub(r'\*\*', '', personality).strip()
            # parts[2] 作为补充描述（如果有）
            if len(pipe_parts) > 2:
                extra = pipe_parts[2].strip()
                if personality and extra:
                    personality = f"{personality}；{extra}"
                elif extra:
                    personality = extra
            motivation = ''
            arc = ''
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                clean = re.sub(r'^[-•]\s*\*{0,2}', '', line).strip()
                clean = re.sub(r'\*{0,2}$', '', clean).strip()
                if '核心性格' in clean or '性格' in clean:
                    val = re.sub(r'.*?[：:]\s*', '', clean).strip()
                    if val:
                        personality = val
                elif '口头禅' in clean:
                    catchphrase = re.sub(r'.*?[：:]\s*', '', clean).strip()
                    if personality and catchphrase:
                        personality = f"{personality}；口头禅：{catchphrase}"
                elif '深层恐惧' in clean or '弱点' in clean:
                    fear = re.sub(r'.*?[：:]\s*', '', clean).strip()
                    if motivation and fear:
                        motivation = f"{motivation}；弱点：{fear}"
                elif '核心动机' in clean or '动机' in clean:
                    motivation = re.sub(r'.*?[：:]\s*', '', clean).strip()
                elif '成长弧线' in clean or '弧线' in clean:
                    arc = re.sub(r'.*?[：:]\s*', '', clean).strip()
        else:
            # Format A/C: - **主角：姓名 | 描述** 或 - 主角：姓名 | 描述
            content_after_colon = re.sub(
                r'^[-•]\s*\*{0,2}\s*' + role_keywords + r'\s*[：:]\s*',
                '', first_line
            )
            content_after_colon = content_after_colon.strip().rstrip('*').strip()

            parts = [p.strip() for p in content_after_colon.split('|')]
            name = parts[0] if parts else ''
            # 清理 name 中的所有 * 和 ** 标记
            name = re.sub(r'\*+', '', name).strip()
            personality = parts[1] if len(parts) > 1 else ''
            personality = re.sub(r'\*+', '', personality).strip()  # 清理 personality
            motivation = ''
            arc = ''

            # 从子行提取详细字段
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                clean = re.sub(r'^[-•]\s*\*{0,2}', '', line).strip()
                clean = re.sub(r'\*{0,2}$', '', clean).strip()

                if '核心性格' in clean or '性格' in clean:
                    val = re.sub(r'.*?[：:]\s*', '', clean).strip()
                    if not personality:
                        personality = val
                elif '核心动机' in clean or '动机' in clean:
                    motivation = re.sub(r'.*?[：:]\s*', '', clean).strip()
                elif '成长弧线' in clean or '弧线' in clean:
                    arc = re.sub(r'.*?[：:]\s*', '', clean).strip()
                elif '口头禅' in clean:
                    catchphrase = re.sub(r'.*?[：:]\s*', '', clean).strip()
                    if personality and catchphrase:
                        personality = f"{personality}；口头禅：{catchphrase}"
                elif '深层恐惧' in clean or '弱点' in clean:
                    fear = re.sub(r'.*?[：:]\s*', '', clean).strip()
                    if motivation and fear:
                        motivation = f"{motivation}；弱点：{fear}"

        char = {
            "name": name,
            "role": role,
            "personality": personality[:500],
            "motivation": motivation[:500],
            "arc": arc[:500]
        }
        outline["characters"].append(char)


def _parse_world_setting(response: str, outline: Dict[str, Any]):
    """从响应中提取世界观，支持粗体格式"""
    world_section = re.search(
        r"(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?世界观(?:与势力)?(?:[（(][^)）]*[)）])?[：:\s]*\n*(.+?)(?=(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?(?:情节节点|情感曲线)|---|$)",
        response,
        re.DOTALL
    )
    if not world_section:
        return

    world_text = world_section.group(1)

    # 支持 "- **时代背景**：xxx" 和 "时代背景：xxx" 两种格式
    era_match = re.search(r"(?:[-•]\s*\*{0,2})?\s*时代背景\s*\*{0,2}\s*[：:]\s*(.+)", world_text)
    rules_match = re.search(r"(?:[-•]\s*\*{0,2})?\s*核心设定\s*\*{0,2}\s*[：:]\s*(.+)", world_text)
    power_match = re.search(r"(?:[-•]\s*\*{0,2})?\s*力量体系\s*\*{0,2}\s*[：:]\s*(.+)", world_text)
    # 社会结构/势力分布
    structure_match = re.search(r"(?:[-•]\s*\*{0,2})?\s*(?:社会结构|势力分布|势力)\s*\*{0,2}\s*[：:]\s*(.+)", world_text)

    era = era_match.group(1).strip() if era_match else ""
    # 清理粗体尾部
    era = re.sub(r"\*\*$", "", era).strip()

    core_rules = rules_match.group(1).strip() if rules_match else ""
    core_rules = re.sub(r"\*\*$", "", core_rules).strip()

    power_system = power_match.group(1).strip() if power_match else ""
    power_system = re.sub(r"\*\*$", "", power_system).strip()

    # 如果有社会结构信息，附加到 core_rules
    if structure_match:
        structure = structure_match.group(1).strip()
        structure = re.sub(r"\*\*$", "", structure).strip()
        if core_rules:
            core_rules = f"{core_rules}\n势力：{structure}"
        else:
            core_rules = f"势力：{structure}"

    outline["world_setting"] = {
        "era": era,
        "core_rules": core_rules,
        "power_system": power_system
    }


def _parse_plot_points(response: str, outline: Dict[str, Any]):
    """从响应中提取情节节点，支持多种格式"""
    plot_section = re.search(
        r"(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?情节节点(?:[（(][^)）]*[)）])?[：:\s]*\n*(.+?)(?=(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?情感曲线|---|$)",
        response,
        re.DOTALL
    )
    if plot_section:
        plot_text = plot_section.group(1)
        # 匹配 "N. xxx | xxx | xxx" 格式
        plot_matches = re.findall(r"(\d+)\.\s*(.+?)(?=\n\d+\.|$)", plot_text, re.DOTALL)
        for num, content in plot_matches:
            parts = [p.strip() for p in content.split("|")]
            plot = {
                "order": int(num),
                "event": parts[0] if len(parts) > 0 else content.strip(),
                "conflict": parts[1] if len(parts) > 1 else "",
                "hook": parts[2] if len(parts) > 2 else ""
            }
            outline["plot_points"].append(plot)

    # 如果上面没匹配到，尝试旧格式
    if not outline["plot_points"]:
        plot_matches = RE_PLOT_BOLD.findall(response)
        if plot_matches:
            outline["plot_points"] = [{"order": i+1, "event": p.strip(), "conflict": "", "hook": ""} for i, p in enumerate(plot_matches)]
        else:
            plot_matches = RE_PLOT_FALLBACK.findall(response)
            if plot_matches:
                outline["plot_points"] = [{"order": i+1, "event": p.strip(), "conflict": "", "hook": ""} for i, p in enumerate(plot_matches)]

    # 尝试匹配 "- **1.** xxx" 或 "- **N.** xxx" 粗体编号格式
    if not outline["plot_points"]:
        plot_matches = re.findall(r"[-•]\s*\*{0,2}(\d+)[.、]\s*\*{0,2}\s*(.+?)(?=\n[-•]|\n\d+[.、]|\n\n|$)", response, re.DOTALL)
        if plot_matches:
            outline["plot_points"] = [
                {"order": int(num), "event": content.strip(), "conflict": "", "hook": ""}
                for num, content in plot_matches
            ]


def _parse_emotional_curve(response: str, outline: Dict[str, Any]):
    """从响应中提取情感曲线"""
    curve_match = re.search(
        r"(?:[#]*\s*(?:[一二三四五六七八九十]+[、.])?\s*)?情感曲线(?:与节奏)?(?:[（(][^)）]*[)）])?[：:\s]*\n*(.+?)(?=---|$)",
        response,
        re.DOTALL
    )
    if curve_match:
        outline["emotional_curve"] = curve_match.group(1).strip()


def parse_chapter_count(response: str) -> int:
    """从响应中解析建议章节数"""
    match = RE_CHAPTER_COUNT.search(response)
    if match:
        return int(match.group(1))
    return 10  # 默认值


async def generate_outline_node(state: NovelState, llm: LLMService) -> NovelState:
    """从灵感模板生成大纲"""
    prompt, chapter_count = prepare_outline_prompt(state)

    response = await llm.chat([{"role": "user", "content": prompt}])

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_characters": outline["characters"],  # 新增：人物设定
        "outline_world_setting": outline["world_setting"],  # 新增：世界观
        "outline_plot_points": outline["plot_points"],
        "outline_emotional_curve": outline["emotional_curve"],  # 新增：情感曲线
        "chapter_count": chapter_count,
        "stage": STAGE_OUTLINE,
    }

    return new_state


def prepare_outline_prompt(state: NovelState) -> tuple[str, int]:
    """准备大纲生成提示词和章节数"""
    db = SessionLocal()
    inspiration_template = state.get("inspiration_template", "")
    collected_info = state.get("collected_info", {})

    # 获取目标字数和每章字数
    target_words = collected_info.get("targetWords", 100000)
    words_per_chapter_str = collected_info.get("wordsPerChapter", "")
    custom_words_per_chapter = collected_info.get("customWordsPerChapter")

    # 计算每章字数
    if words_per_chapter_str == "custom" and custom_words_per_chapter:
        words_per_chapter = custom_words_per_chapter
    elif words_per_chapter_str and words_per_chapter_str != "custom":
        try:
            words_per_chapter = int(words_per_chapter_str)
        except (ValueError, TypeError):
            words_per_chapter = WORDS_PER_CHAPTER_MEDIUM  # 默认值
    else:
        words_per_chapter = WORDS_PER_CHAPTER_MEDIUM  # 默认值

    # 根据目标字数和每章字数计算章节数
    if isinstance(target_words, int) and target_words > 0 and words_per_chapter > 0:
        chapter_count = max(3, int(target_words / words_per_chapter))  # 最少3章
    else:
        chapter_count = DEFAULT_CHAPTER_COUNT

    # 如果没有灵感模板，从 collected_info 生成基本信息
    if not inspiration_template:
        novel_type = collected_info.get("novelType", "未指定")
        core_theme = collected_info.get("coreTheme", "未指定")
        target_reader = collected_info.get("targetReader", "未指定")
        era = collected_info.get("era", "未指定")
        genre = collected_info.get("customGenre") or collected_info.get("genre", "未指定")
        world_setting = collected_info.get("customWorldSetting") or collected_info.get("worldSetting", "未指定")
        style = collected_info.get("stylePreference", "未指定")
        target_words_display = f"{target_words}字" if isinstance(target_words, int) else "未指定"

        # 根据目标读者获取主角设定
        target_reader_label = "男频" if target_reader == "male" else "女频" if target_reader == "female" else "未指定"
        if target_reader == "male":
            protagonist = collected_info.get("customMaleLead") or collected_info.get("maleLead", "未指定")
            protagonist_label = "男主"
            gold_finger = collected_info.get("customGoldFinger") or collected_info.get("goldFinger", "未指定")
        elif target_reader == "female":
            protagonist = collected_info.get("customFemaleLead") or collected_info.get("femaleLead", "未指定")
            protagonist_label = "女主"
            gold_finger = "未指定"
        else:
            protagonist = collected_info.get("customProtagonist") or collected_info.get("protagonist", "未指定")
            protagonist_label = "主角"
            gold_finger = collected_info.get("customGoldFinger") or collected_info.get("goldFinger", "未指定")

        inspiration_template = f"""# 小说创作灵感

## 基本信息
- **目标读者**：{target_reader_label}
- **小说类型**：{novel_type}
- **年代设定**：{era}
- **目标字数**：{target_words_display}

## 主角设定
- **{protagonist_label}**：{protagonist}

## 核心设定
- **核心主题**：{core_theme}
- **世界观**：{world_setting}
- **流派**：{genre}
- **金手指**：{gold_finger}

## 风格
- **风格偏好**：{style}
"""

    prompt = get_system_prompt(db, "outline_generation").format(
        inspiration_template=inspiration_template,
        chapter_count=chapter_count
    )

    db.close()
    return prompt, chapter_count


async def generate_outline_stream(
    state: NovelState,
    llm: LLMService
) -> AsyncIterator[str]:
    """Generate outline with streaming"""
    prompt, _ = prepare_outline_prompt(state)

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk


# ==================== LangGraph 兼容节点 ====================

async def outline_generation_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的大纲生成节点（流式版本）

    使用 llm.chat_stream() 确保 astream_events 能捕获逐字流式内容。
    签名：(state: NovelState) -> NovelState
    """
    # 获取 LLM 服务（异步）
    llm = await get_llm_from_state_async(state)

    prompt, chapter_count = prepare_outline_prompt(state)

    # 使用流式 API，框架自动捕获 on_chat_model_stream 事件
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk

    outline = parse_outline(response)

    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"outline parsed: title='{outline.get('title', '')}', "
        f"char={len(outline.get('characters', []))}, "
        f"plot={len(outline.get('plot_points', []))}"
    )

    new_state: NovelState = {
        **state,
        "outline_title": outline.get("title", ""),
        "outline_summary": outline["summary"],
        "outline_characters": outline["characters"],  # 新增：人物设定
        "outline_world_setting": outline["world_setting"],  # 新增：世界观
        "outline_plot_points": outline["plot_points"],
        "outline_emotional_curve": outline["emotional_curve"],  # 新增：情感曲线
        "chapter_count": chapter_count,
        "stage": STAGE_OUTLINE,
    }

    return new_state
