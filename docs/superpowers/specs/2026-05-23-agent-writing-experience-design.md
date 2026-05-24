# Agent 模式写作体验升级 设计文档

> 日期：2026-05-23
> 状态：审查修正版
> 范围：Agent 上下文注入改造 + prompt 体系统一 + 精细编辑 tools + 聊天区体验升级

---

## 1. 背景与目标

### 当前问题（根因分析）

1. **上下文是摘要而非原文** — Agent 的 system message 只注入元数据摘要。Agent 看不到实际内容
2. **Agent 绕过 prompt 体系（根因）** — `chapter_service.py` 用硬编码 f-string 生成章节，而工作流模式使用 `get_prompt_template` + `safe_format` + system/user 双层消息 + `context_strategy` + `token_budget` + Draft→SelfCheck→Refine 管道。同一项目两种生成质量
3. **编辑粒度只有整章重写** — 缺少段落级编辑能力
4. **聊天区内容不可见** — 生成章节只显示 200 字预览
5. **LLM 解析逻辑 3 处重复** — `agent_graph.py`、`chapter_service.py`、`agent.py` 各自实现相同的 model_config → user_settings 回退

### 目标

让 Agent 模式写小说的体验达到 Claude Code 级别：看得见原文、用同一套 prompt 体系保证质量一致、能精细修改、内容在对话流中直接可读。

---

## 2. 设计范围

### 在范围内

- 上下文注入从「元数据摘要」改为「原文注入 + token budget」
- **chapter_service.py 接入 prompt 体系**（get_prompt_template + safe_format + context_strategy）
- **Agent 生成采用 Draft→SelfCheck→Refine 管道**（与工作流一致）
- **提取共享 LLM 解析函数**（消除 3 处重复）
- 4 个精细编辑 tools
- 聊天区章节预览展开、自动审核、快捷指令
- 后端编辑服务层（edit_service.py）

### 不在范围内

- 聊天历史持久化
- 多轮对话上下文窗口管理策略
- Agent 操作回滚/版本控制
- 移动端适配

---

## 3. Step 0: 消除技术债（先于功能开发）

### 3.1 提取共享 LLM 解析函数

**问题：** `agent_graph.py`、`chapter_service.py`、`agent.py` 三处各自实现了 model_config → user_settings 回退逻辑。

**方案：** 在 `backend/app/utils/llm.py` 新增 `resolve_llm_service()`：

```python
# backend/app/utils/llm.py 新增

def resolve_llm_service(model_config_id: int = None, user_id: int = None) -> LLMService:
    """统一的 LLM 服务解析入口
    
    优先级：model_config_id > user_settings > error
    所有 Agent 相关代码统一使用此函数获取 LLMService。
    """
    from app.database import SessionLocal
    from app.models.model_config import ModelConfig
    from app.models.settings import UserSettings
    from app.services.llm import get_llm_service_from_config, get_llm_service
    
    if model_config_id and user_id:
        db = SessionLocal()
        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
            if config:
                return get_llm_service_from_config(config, user_id)
        finally:
            db.close()
    
    if user_id:
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings:
                return get_llm_service(settings)
        finally:
            db.close()
    
    raise ValueError("无法获取 LLM 配置：请先在设置中配置 API Key")
```

**影响范围：**
- `chapter_service.py`：删除 `_get_llm_service()`，改用 `resolve_llm_service(get_model_config_id(), get_user_id())`
- `agent_graph.py`：`create_agent_graph` 中删除内联 LLM 解析，改用 `resolve_llm_service()` + `_get_llm_from_service()`
- `edit_service.py`（新增）：直接使用 `resolve_llm_service()`

### 3.2 chapter_service.py 接入 prompt 体系

**问题：** `generate_chapter`、`rewrite_chapter` 使用硬编码 f-string prompt，与工作流模式的 `_build_chapter_content_messages` 完全不同。

**方案：** `generate_chapter` 和 `rewrite_chapter` 复用 `chapter_generation.py` 的 prompt 构建逻辑。

**关键决策：** Agent tool 不在 LangGraph state 上下文中运行，无法直接使用 `get_prompts_from_state(state)` 获取用户自定义 prompt。需要从 DB 读取 SystemPrompt 表。

```python
# backend/app/agents/services/chapter_service.py 重构后

from app.agents.nodes.chapter_generation import (
    _calc_max_tokens,
    _build_chapter_content_messages,
    generate_chapter_content_stream,
)
from app.agents.nodes.utils import (
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    safe_format,
    get_prompt_template,
    parse_words_per_chapter,
    _format_chapter_outline_str,
)
from app.agents.context_strategy import get_context_strategy
from app.agents.state import NovelState
from app.utils.llm import resolve_llm_service


def _build_agent_novel_state(db: Session, project_id: int, chapter_number: int) -> NovelState:
    """从 DB 构建 Agent 模式下的模拟 NovelState
    
    Agent tool 不在 LangGraph 工作流中运行，没有现成的 state。
    从 DB 加载所有必要数据，构建与工作流模式等价的 state dict，
    确保 _build_chapter_content_messages 等函数可以正常工作。
    """
    from app.models.outline import Outline, ChapterOutline
    from app.models.character import Character, CharacterRelation
    from app.models.chapter import Chapter
    from app.agents.prompts import DEFAULT_PROMPTS
    
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    chapter_outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).order_by(ChapterOutline.chapter_number).all()
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.chapter_number).all()
    
    return {
        "outline_title": outline.title if outline else "",
        "outline_summary": outline.summary if outline else "",
        "outline_plot_points": outline.plot_points if outline else [],
        "outline_world_setting": outline.world_setting if outline else {},
        "outline_emotional_curve": outline.emotional_curve if outline else "",
        "chapter_count": outline.chapter_count_suggested or 10 if outline else 10,
        "characters": [
            {
                "name": c.name,
                "role": c.role,
                "personality": c.personality or "",
                "core_motivation": c.core_motivation or "",
                "growth_arc": c.growth_arc or "",
                "background": c.background or "",
                "appearance": c.appearance or "",
                "abilities": c.abilities or "",
            }
            for c in characters
        ],
        "chapter_outlines": [
            {
                "chapter_number": co.chapter_number,
                "title": co.title,
                "scene": co.scene or "",
                "characters": co.characters or "",
                "plot": co.plot or "",
                "conflict": co.conflict or "",
                "turning_point": co.turning_point or "",
                "hook": co.hook or "",
                "transition": co.transition or "",
                "ending": co.ending or "",
                "target_words": co.target_words or 3000,
            }
            for co in chapter_outlines
        ],
        "written_chapters": [
            {
                "chapter_number": ch.chapter_number,
                "title": ch.title or "",
                "content": ch.content or "",
                "summary": ch.summary or "",
            }
            for ch in chapters if ch.content
        ],
        "collected_info": {
            "novelType": (outline.collected_info or {}).get("novelType", "") if outline else "",
            "targetWords": (outline.collected_info or {}).get("targetWords", 100000) if outline else 100000,
            "stylePreference": (outline.collected_info or {}).get("stylePreference", "") if outline else "",
            "contextStrategy": (outline.collected_info or {}).get("contextStrategy") if outline else None,
        },
        # Agent 模式下使用 DEFAULT_PROMPTS（不从 state 获取用户自定义 prompt）
        "_prompts": DEFAULT_PROMPTS,
        "arcs": [],  # Agent 模式下不支持弧纲上下文
    }


async def generate_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """生成章节正文——使用与工作流模式相同的 prompt 体系和质量管道"""
    from app.agents.nodes.chapter_generation import (
        generate_chapter_content_stream,
        _self_check_chapter,
        _refine_chapter_stream,
        _calc_max_tokens,
    )
    
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()
    if not outline:
        return {"error": f"第{chapter_number}章大纲不存在"}
    
    # 构建模拟 state
    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())
    
    chapter_outline = {
        "chapter_number": chapter_number,
        "title": outline.title,
        "scene": outline.scene or "",
        "characters": outline.characters or "",
        "plot": outline.plot or "",
        "conflict": outline.conflict or "",
        "turning_point": outline.turning_point or "",
        "hook": outline.hook or "",
        "transition": outline.transition or "",
        "ending": outline.ending or "",
        "target_words": outline.target_words or 3000,
    }
    
    # Phase 1: Draft（流式生成初稿）
    draft_content = ""
    try:
        async for chunk in generate_chapter_content_stream(state, chapter_outline, llm):
            draft_content += chunk
    except Exception as e:
        logger.error(f"Chapter draft generation failed: {e}")
        return {"error": f"生成失败: {str(e)}"}
    
    if not draft_content.strip():
        return {"error": "生成结果为空，请重试"}
    
    # Phase 2: SelfCheck（段落自检）
    try:
        check_result = await _self_check_chapter(llm, draft_content, state)
    except Exception as e:
        logger.warning(f"Chapter self-check failed, using draft: {e}")
        check_result = {"paragraphs": []}
    
    # Phase 3: Refine（仅当发现问题时精修）
    info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(info)
    
    if check_result.get("paragraphs"):
        final_content = ""
        try:
            async for chunk in _refine_chapter_stream(llm, draft_content, check_result, min_words, state):
                final_content += chunk
        except Exception as e:
            logger.warning(f"Chapter refine failed, using draft: {e}")
            final_content = draft_content
    else:
        final_content = draft_content
    
    # 写入 DB
    try:
        chapter = db.query(Chapter).filter(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        ).first()
        if chapter:
            chapter.content = final_content
        else:
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=outline.title,
                content=final_content,
                target_words=outline.target_words or 3000,
            )
            db.add(chapter)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save chapter: {e}")
        return {"error": f"保存失败: {str(e)}"}
    
    word_count = len(final_content)
    preview = final_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章「{outline.title}」已生成（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title,
        "word_count": word_count,
        "preview": preview,
        "full_content": final_content,
    }
```

**review_chapter 同样接入 prompt 体系：**

```python
async def review_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """审核章节——使用系统 prompt 模板"""
    chapter = db.query(Chapter).filter(...).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}
    
    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())
    
    # 构建章节大纲字符串
    chapter_outline_data = {
        "title": outline.title if outline else "",
        "scene": outline.scene or "",
        "characters": outline.characters or "",
        "plot": outline.plot or "",
        "conflict": outline.conflict or "",
        "turning_point": outline.turning_point or "",
        "ending": outline.ending or "",
    }
    chapter_outline_str = _format_chapter_outline_str(chapter_outline_data)
    
    # 使用 get_prompts_from_state 正确解析 prompt（处理 dict/string 两种格式）
    from app.agents.nodes.utils import get_prompts_from_state, get_prompt_template, safe_format, _format_chapter_outline_str
    system_template, user_template = get_prompts_from_state(state, "review")
    prompt_template = get_prompt_template(system_template, user_template)
    
    info = state.get("collected_info", {})
    prompt = safe_format(prompt_template,
        strictness="standard",
        chapter_outline=chapter_outline_str,
        chapter_content=chapter.content,
        genre=info.get("novelType", ""),
        style_preference=info.get("stylePreference", ""),
    )
    
    result_text = await llm.chat([{"role": "user", "content": prompt}], max_tokens=2048)
    # ... JSON 解析逻辑保持不变 ...
```

**rewrite_chapter 同理接入 prompt 体系**（模板变量与 review 不同，使用 `get_prompts_from_state(state, "rewrite")`，变量名匹配 REWRITE_USER_PROMPT 模板：`{chapter_outline}`, `{review_feedback}`, `{original_content}`, `{genre}`）。

### 3.3 提取共享 `_calc_max_tokens`

当前 `_calc_max_tokens` 在 `chapter_generation.py` 和 `chapter_service.py` 各定义一次。Step 0 中将 `chapter_service.py` 的版本删除，统一从 `chapter_generation.py` 导入。

---

## 4. Step 1: 上下文注入改造

### 4.1 当前状态

`build_project_context` 返回元数据摘要，且位于 `agent_graph.py` 中。

### 4.2 目标状态

`build_project_context` 返回原文内容，按优先级组装，受 token budget 约束。移至独立模块 `backend/app/agents/agent_context.py`（与 agent_graph.py 分离，方便测试）。

```python
# backend/app/agents/agent_context.py 新增

class BudgetTracker:
    """Token 预算追踪器"""
    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0
    
    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max
    
    def add(self, tokens: int):
        self.used += tokens
    
    def remaining(self) -> int:
        return max(0, self.max - self.used)


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文字数 × 2，英文单词数 × 1.3"""
    import re
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return int(chinese_chars * 2 + english_words * 1.3)


def build_project_context(
    project_id: int,
    active_tab: str = None,
    active_menu_item: str = None,
    current_chapter_number: int = None,
    max_tokens: int = 12000,
) -> dict:
    """构建项目上下文，按优先级注入原文，受 token budget 约束"""
    db = SessionLocal()
    try:
        budget = BudgetTracker(max_tokens)
        context = {}
        
        # P1: 当前章节完整正文（如果指定）
        if current_chapter_number:
            chapter = db.query(Chapter).filter(
                Chapter.project_id == project_id,
                Chapter.chapter_number == current_chapter_number,
            ).first()
            if chapter and chapter.content:
                content_tokens = estimate_tokens(chapter.content)
                if budget.can_add(content_tokens):
                    context["current_chapter"] = {
                        "chapter_number": current_chapter_number,
                        "title": chapter.title,
                        "content": chapter.content,
                    }
                    budget.add(content_tokens)
        
        # P2: 完整大纲
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if outline:
            outline_data = {
                "title": outline.title,
                "summary": outline.summary or "",
                "plot_points": outline.plot_points or [],
                "chapter_count": outline.chapter_count_confirmed or outline.chapter_count_suggested or 0,
                "confirmed": outline.confirmed,
            }
            outline_json = json.dumps(outline_data, ensure_ascii=False)
            outline_tokens = estimate_tokens(outline_json)
            if budget.can_add(outline_tokens):
                context["outline"] = outline_data
                budget.add(outline_tokens)
        
        # P3: 角色列表（完整设定，每个角色控制在 200 字内）
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        char_list = []
        for c in characters:
            char_info = f"{c.name}（{c.role}）：{c.personality or ''}。动机：{c.core_motivation or ''}"
            char_tokens = estimate_tokens(char_info)
            if budget.can_add(char_tokens):
                char_list.append({
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality or "",
                    "core_motivation": c.core_motivation or "",
                    "growth_arc": c.growth_arc or "",
                })
                budget.add(char_tokens)
        context["characters"] = char_list
        
        # P4: 当前章节大纲
        if current_chapter_number:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == current_chapter_number,
            ).first()
            if co:
                co_data = {
                    "title": co.title,
                    "plot": co.plot or "",
                    "conflict": co.conflict or "",
                    "ending": co.ending or "",
                    "target_words": co.target_words or 3000,
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                if budget.can_add(estimate_tokens(co_json)):
                    context["current_outline"] = co_data
                    budget.add(estimate_tokens(co_json))
        
        # P5: 所有章节标题+状态（轻量索引）
        chapter_outlines = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number).all()
        all_chapters = []
        for co in chapter_outlines:
            chapter = db.query(Chapter).filter(
                Chapter.project_id == project_id,
                Chapter.chapter_number == co.chapter_number,
            ).first()
            entry = f"第{co.chapter_number}章《{co.title}》"
            if chapter and chapter.content:
                entry += f"（已写，{len(chapter.content)}字）"
            else:
                entry += "（待写）"
            entry_tokens = estimate_tokens(entry)
            if budget.can_add(entry_tokens):
                all_chapters.append(entry)
                budget.add(entry_tokens)
        context["all_chapters"] = all_chapters
        
        # P6: 前后章节摘要（从已写章节提取）
        if current_chapter_number:
            adjacent = []
            for offset in [-2, -1, 1]:
                cn = current_chapter_number + offset
                if cn < 1:
                    continue
                ch = db.query(Chapter).filter(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == cn,
                ).first()
                if ch and ch.content:
                    summary_text = f"第{cn}章：{ch.content[:150]}"
                    adj_tokens = estimate_tokens(summary_text)
                    if budget.can_add(adj_tokens):
                        adjacent.append(summary_text)
                        budget.add(adj_tokens)
            if adjacent:
                context["adjacent_summaries"] = adjacent
        
        context["_budget_used"] = budget.used
        return context
    finally:
        db.close()
```

### 4.3 system message 模板更新

`agent.py` 中 system message 改为结构化注入：

```python
context = build_project_context(
    project_id,
    active_tab=req.active_tab,
    active_menu_item=req.active_menu_item,
)

system_content = f"""你是一位专业的小说创作搭档。

## 项目上下文

### 大纲
{json.dumps(context.get('outline', {}), ensure_ascii=False)}

### 角色
{json.dumps(context.get('characters', []), ensure_ascii=False)}

### 章节总览
{chr(10).join(context.get('all_chapters', []))}

### 当前章节正文
{json.dumps(context.get('current_chapter', {}), ensure_ascii=False)}

### 当前章节大纲
{json.dumps(context.get('current_outline', {}), ensure_ascii=False)}

## 行为准则

1. 生成章节后必须调用 review_chapter 审核质量
2. 审核不通过时应根据审核意见调用 rewrite_chapter 重写
3. 修改大纲/角色/章节后简要说明改了什么
4. 优先使用 revise_section 做局部修改，避免整章重写"""
```

### 4.4 改动文件

| 文件 | 改动 |
|------|------|
| `backend/app/agents/agent_context.py` | **新增** — BudgetTracker + build_project_context |
| `backend/app/agents/agent_graph.py` | 删除旧 `build_project_context`，导入新版本 |
| `backend/app/api/agent.py` | system message 模板更新；传入 current_chapter_number |

---

## 5. Step 2: 精细编辑 Tools

### 5.1 新增 Tools

| Tool | 类型 | 参数 | 说明 |
|------|------|------|------|
| `edit_paragraph` | 精确 | `project_id, chapter_number, paragraph_index, new_content` | 替换指定段落（0-indexed） |
| `insert_scene` | 精确 | `project_id, chapter_number, position, scene_content` | 在 position 前插入（0=开头，N=末尾） |
| `revise_section` | 语义 | `project_id, chapter_number, instruction, start_para, end_para` | 按指令重写段落范围 |
| `polish_prose` | 语义 | `project_id, chapter_number, style_instruction` | 保持情节不变，优化文笔 |

### 5.2 内容格式处理

章节内容以纯文本存储（`
` 分隔段落）。操作前先规范化：

```python
def _normalize_paragraphs(content: str) -> list[str]:
    """规范化段落分割
    
    处理 \r\n、\n\n、连续空行、HTML 标签等格式变体。
    返回非空段落列表。
    """
    import re
    # 移除 HTML 标签（如果用户通过 TipTap 编辑过）
    clean = re.sub(r'<[^>]+>', '', content)
    # 统一换行符
    clean = clean.replace('\r\n', '\n').replace('\r', '\n')
    # 按连续换行符分割，去除首尾空白，过滤空段
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', clean)]
    return [p for p in paragraphs if p]


def _join_paragraphs(paragraphs: list[str]) -> str:
    """段落列表拼接回纯文本"""
    return '\n\n'.join(paragraphs)
```

### 5.3 实现模式

**精确操作（edit_paragraph, insert_scene）：不调 LLM，直接 DB 读写**

```python
async def edit_paragraph(db, project_id, chapter_number, paragraph_index, new_content):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}
    
    paragraphs = _normalize_paragraphs(chapter.content)
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return {"error": f"段落索引超出范围（共{len(paragraphs)}段）"}
    
    old_para = paragraphs[paragraph_index]
    paragraphs[paragraph_index] = new_content
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()
    
    return {
        "success": True,
        "paragraph_index": paragraph_index,
        "old_preview": old_para[:50],
        "new_preview": new_content[:50],
    }


async def insert_scene(db, project_id, chapter_number, position, scene_content):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter:
        return {"error": f"第{chapter_number}章不存在"}
    
    paragraphs = _normalize_paragraphs(chapter.content) if chapter.content else []
    if position < 0 or position > len(paragraphs):
        return {"error": f"插入位置超出范围（0-{len(paragraphs)}）"}
    
    paragraphs.insert(position, scene_content)
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()
    
    return {"success": True, "position": position, "total_paragraphs": len(paragraphs)}
```

**语义操作（revise_section, polish_prose）：调 LLM，利用 tool_context 获取 LLM 配置**

```python
async def revise_section(db, project_id, chapter_number, instruction, start_para, end_para):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}
    
    paragraphs = _normalize_paragraphs(chapter.content)
    if start_para < 0 or end_para >= len(paragraphs):
        return {"error": f"段落范围超出（共{len(paragraphs)}段）"}
    
    target = '\n\n'.join(paragraphs[start_para:end_para + 1])
    
    llm = resolve_llm_service(get_model_config_id(), get_user_id())
    # 使用系统审核 prompt 中的写作风格指导
    state = _build_agent_novel_state(db, project_id, chapter_number)
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()
    
    prompt = f"""修改以下小说段落。

修改指令：{instruction}

章节背景：
- 章节标题：{outline.title if outline else ''}
- 情节要点：{outline.plot if outline else ''}
- 冲突：{outline.conflict if outline else ''}

原文段落：
{target}

请直接输出修改后的段落，不要输出其他说明。"""
    
    try:
        revised = await llm.chat([{"role": "user", "content": prompt}], max_tokens=4096)
    except Exception as e:
        return {"error": f"修改失败: {str(e)}"}
    
    if not revised or not revised.strip():
        return {"error": "修改结果为空，请重试"}
    
    # 替换目标段落（原子操作：先修改内存，一次性 commit）
    paragraphs[start_para:end_para + 1] = [revised.strip()]
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()
    
    return {"success": True, "preview": revised[:200], "range": f"段落{start_para+1}-{end_para+1}"}
```

### 5.4 改动文件

| 文件 | 改动 |
|------|------|
| `backend/app/agents/services/edit_service.py` | **新增** — 4 个编辑服务函数 + `_normalize_paragraphs` + `_join_paragraphs` |
| `backend/app/agents/agent_tools.py` | 注册 4 个新 tool，`AGENT_TOOLS` 列表追加 |
| `backend/app/api/agent.py` | `write_tools` 和 `module_map` 追加新 tool 名 |

---

## 6. Step 3: 聊天区体验升级

### 6.1 章节内容完整可读

**问题修正：** 原方案通过 SSE 事件传 `full_content`（3000+ 中文字符），可能超出 nginx `proxy_buffer_size`（默认 4KB/8KB）。

**修正方案：** SSE 事件仅传 `preview`（前 200 字）。前端 ChapterPreviewCard 点击「展开全部」时，通过单独 API 获取完整内容：

```typescript
// 新增轻量 API
GET /api/projects/{id}/chapters/{chapter_number}/content
→ { "content": "完整章节正文..." }
```

`ChapterPreviewCard` 组件增加 `fetchFullContent` 逻辑：折叠时显示 200 字预览，点击展开后 fetch 完整内容并渲染（带 loading skeleton）。

**后端无需新增端点** — `GET /api/projects/{id}/chapters` 已返回每章 `content` 字段。前端可直接从此接口获取。

### 6.2 自动审核（修正）

**原方案问题：** 在 SSE 流内部 `await review_chapter()` 会阻塞整个 SSE 流 30-60 秒。

**修正方案：** 通过 **system prompt 行为准则**引导 Agent 自动调用 `review_chapter`：

```
## 行为准则
1. 生成章节后必须调用 review_chapter 审核质量
2. 审核不通过时应根据审核意见调用 rewrite_chapter 重写
3. 修改大纲/角色/章节后简要说明改了什么
```

Agent 在 ReAct 循环中自行决策调用 `review_chapter`，审核结果作为普通 tool_result 事件返回，前端 `onToolEnd` 回调中检测 `review_chapter` 类型并渲染审核卡片。

**不修改 `stream_agent_events`** — 现有代码中已有的 `review_chapter` tool 处理逻辑（`agent.py:139-142`）直接复用。

### 6.3 快捷指令

`AICompanionInput` 上方新增快捷按钮栏：

```tsx
const QUICK_COMMANDS = [
  { label: '写下一章', icon: PenTool, prompt: '请继续写下一章', showWhen: ['writing'] },
  { label: '审核本章', icon: Search, prompt: '请审核当前章节', showWhen: ['writing'] },
  { label: '润色本章', icon: Sparkles, prompt: '请润色当前章节的文笔，保持情节不变', showWhen: ['writing'] },
  { label: '查看大纲', icon: FileText, prompt: '请展示当前大纲概要', showWhen: ['settings'] },
  { label: '查看角色', icon: Users, prompt: '请展示所有角色', showWhen: ['settings'] },
]
```

- 根据 `activeTab` 筛选显示
- 点击填入输入框（不自动发送）
- 使用 `text-[10px]` 小标签样式

### 6.4 改动文件

| 文件 | 改动 |
|------|------|
| `frontend/src/components/workbench/AICompanionChat.tsx` | ChapterPreviewCard fetch 完整内容 + 审核卡片复用现有逻辑 |
| `frontend/src/components/workbench/AICompanionInput.tsx` | 新增快捷指令按钮栏 |
| `frontend/src/components/workbench/AICompanionSidebar.tsx` | 传入 `activeTab` 给 Input |
| `backend/app/api/agent.py` | system prompt 更新（行为准则）；无需修改 stream_agent_events |

---

## 7. 数据流

### 7.1 用户发送消息流程

```
用户输入 "把第3章第5段改得更紧张"
  → agentApi.sendAgentMessage()
    → POST /api/projects/{id}/agent/chat
      → agent.py 构建 system message（原文注入 + 行为准则）
        → create_react_agent 决策
          → tool: revise_section(project_id=1, chapter_number=3, 
                   instruction="更紧张", start_para=4, end_para=4)
            → edit_service.revise_section()
              → _normalize_paragraphs + LLM 重写 + _join_paragraphs
              → db.commit()
              → 返回 preview
          → SSE: agent_tool_result + agent_chapter_preview（前端渲染卡片）
```

### 7.2 自动审核流程（修正后）

```
Agent 生成章节（generate_chapter_content tool）
  → chapter_service.generate_chapter()
    → Draft→SelfCheck→Refine 管道
    → 落库
    → 返回 preview
  → SSE: agent_tool_result + agent_chapter_preview
  → Agent 根据 system prompt 行为准则，自动决策调用 review_chapter
    → chapter_service.review_chapter()（使用 prompt 模板）
    → 返回审核结果
  → SSE: agent_tool_result（前端 onToolEnd 检测 review_chapter → 渲染审核卡片）
  → 如果不通过，Agent 自动调用 rewrite_chapter
  → SSE: agent_chapter_preview（渲染新章节卡片）
```

---

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| 章节不存在（编辑时） | `{"error": "第N章内容不存在，请先生成"}` |
| 段落索引越界 | `{"error": "段落索引超出范围（共N段）"}` |
| LLM 调用失败（语义操作） | `{"error": "修改失败: ..."}`，原文未被修改（commit 在 LLM 成功后） |
| LLM 失败（生成章节） | Draft/SelfCheck/Refine 各阶段有独立 try/catch，失败回退到前一步结果 |
| Token budget 超出 | 从低优先级开始裁剪，logger.warning 记录 |
| 并发冲突（is_busy） | 复用现有 409 机制 |
| `_build_agent_novel_state` DB 读取失败 | 对应字段置空/默认值，不阻塞生成流程 |
| SSE full_content 过大 | 不再通过 SSE 传输完整内容，改为前端按需 fetch |

---

## 9. 测试策略

| 层 | 测什么 |
|----|--------|
| `agent_context.py` | 单元测试：BudgetTracker 预算计算、build_project_context 各优先级裁剪、边界情况（空 DB） |
| `utils/llm.py` | 单元测试：resolve_llm_service 回退逻辑 |
| `edit_service.py` | 单元测试：_normalize_paragraphs 各种格式、4 个编辑函数的正确段落操作、边界处理 |
| `chapter_service.py` | 集成测试：_build_agent_novel_state 数据正确性、generate_chapter 三阶段管道 |
| `agent_tools.py` | 集成测试：新 tool 注册正确、参数透传 |
| `agent.py` | 集成测试：system prompt 包含行为准则、SSE 事件顺序 |
| `AICompanionChat.tsx` | 组件测试：展开 fetch 内容、审核卡片渲染 |
| `AICompanionInput.tsx` | 组件测试：快捷按钮显示/隐藏、填入逻辑 |

---

## 10. 改动文件总览

| 文件 | 改动 | 步骤 |
|------|------|------|
| `backend/app/utils/llm.py` | 新增 `resolve_llm_service()` | 0 |
| `backend/app/agents/services/chapter_service.py` | 重构：接入 prompt 体系 + Draft→SelfCheck→Refine 管道 | 0 |
| `backend/app/agents/agent_context.py` | **新增** — BudgetTracker + build_project_context | 1 |
| `backend/app/agents/agent_graph.py` | 删除旧 build_project_context + 使用 resolve_llm_service | 0,1 |
| `backend/app/api/agent.py` | system message 模板更新、行为准则注入 | 1,3 |
| `backend/app/agents/services/edit_service.py` | **新增** — 4 个编辑服务 + 段落规范化 | 2 |
| `backend/app/agents/agent_tools.py` | 注册 4 个新 tool | 2 |
| `frontend/src/components/workbench/AICompanionChat.tsx` | ChapterPreviewCard fetch 完整内容 | 3 |
| `frontend/src/components/workbench/AICompanionInput.tsx` | 快捷指令按钮栏 | 3 |
| `frontend/src/components/workbench/AICompanionSidebar.tsx` | 传入 activeTab 给 Input | 3 |

**预估总工作量：** 8-10 小时（因 Step 0 增加了 prompt 体系统一和 LLM 解析统一的重构工作）
