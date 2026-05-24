# Agent 模式写作体验升级 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Agent 模式写小说达到 Claude Code 级别体验——统一 prompt 体系、原文注入上下文、精细编辑能力、聊天区内容可读。

**Architecture:** 分四步执行。Step 0 先消除技术债（提取共享 LLM 解析、chapter_service 接入 prompt 体系），Step 1 改造上下文注入（BudgetTracker + 原文注入），Step 2 新增精细编辑 tools，Step 3 升级聊天区 UX。后端遵循 services 层模式（agent_tools → services → DB），前端遵循 Zustand + SSE 事件驱动模式。

**Tech Stack:** FastAPI + LangGraph + SQLAlchemy + React 18 + Zustand + Tailwind + SSE

---

## Task 0.1: 提取共享 `resolve_llm_service()` 到 `backend/app/utils/llm.py`

**Files:**
- Modify: `backend/app/utils/llm.py`
- Modify: `backend/app/agents/services/chapter_service.py`
- Modify: `backend/app/agents/agent_graph.py`

- [ ] **Step 1: 在 `backend/app/utils/llm.py` 末尾追加 `resolve_llm_service()`**

```python
# backend/app/utils/llm.py 追加

def resolve_llm_service(model_config_id: int | None = None, user_id: int | None = None):
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

- [ ] **Step 2: 替换 `chapter_service.py` 中的 `_get_llm_service()`**

删除 `_get_llm_service()` 函数（第 23-50 行），替换所有调用点为 `resolve_llm_service(get_model_config_id(), get_user_id())`：

```python
# 文件顶部 import 区追加
from app.utils.llm import resolve_llm_service

# 删除整个 _get_llm_service() 函数（第23-50行）

# generate_chapter 中（原来第80行）：
# llm_service = _get_llm_service()
# 改为：
llm_service = resolve_llm_service(get_model_config_id(), get_user_id())

# review_chapter 中（原来第164行）：
# llm_service = _get_llm_service()
# 改为：
llm_service = resolve_llm_service(get_model_config_id(), get_user_id())

# rewrite_chapter 中（原来第213行）：
# llm_service = _get_llm_service()
# 改为：
llm_service = resolve_llm_service(get_model_config_id(), get_user_id())
```

同时删除不再需要的 import：`get_llm_service_from_config`, `get_llm_service`, `ModelConfig`, `UserSettings`, `SessionLocal`（如果只用于 `_get_llm_service`）。

- [ ] **Step 3: 替换 `agent_graph.py` 中的内联 LLM 解析**

```python
# backend/app/agents/agent_graph.py

# 文件顶部 import 区追加
from app.utils.llm import resolve_llm_service

# create_agent_graph() 函数中，删除第67-92行的内联 LLM 解析代码，替换为：
def create_agent_graph(model_config_id: int = None, user_id: int = None):
    """创建 Agent 图实例"""
    llm_service = resolve_llm_service(model_config_id, user_id)
    llm = _get_llm_from_service(llm_service)

    graph = create_react_agent(
        model=llm,
        tools=AGENT_TOOLS,
    )
    return graph
```

删除不再需要的 import：`get_llm_service_from_config`, `ModelConfig`（如果不再使用）。

- [ ] **Step 4: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.utils.llm import resolve_llm_service; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/llm.py backend/app/agents/services/chapter_service.py backend/app/agents/agent_graph.py
git commit -m "refactor(agents): extract shared resolve_llm_service() to utils/llm.py"
```

---

## Task 0.2: chapter_service.py 接入 prompt 体系

**Files:**
- Modify: `backend/app/agents/services/chapter_service.py`

- [ ] **Step 1: 新增 `_build_agent_novel_state()` 函数**

在 `chapter_service.py` 的 import 区之后、现有函数之前插入：

```python
# backend/app/agents/services/chapter_service.py
# 在现有 import 之后追加以下 import：
from app.agents.nodes.chapter_generation import (
    _calc_max_tokens,
    _build_chapter_content_messages,
    generate_chapter_content_stream,
    _self_check_chapter,
    _refine_chapter_stream,
)
from app.agents.nodes.utils import (
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    safe_format,
    get_prompt_template,
    get_prompts_from_state,
    parse_words_per_chapter,
    _format_chapter_outline_str,
)
from app.agents.context_strategy import get_context_strategy
from app.agents.state import NovelState
from app.agents.prompts import DEFAULT_PROMPTS
from app.models.outline import Outline
from app.models.character import Character, CharacterRelation
from app.models.chapter import Chapter


def _build_agent_novel_state(db: Session, project_id: int, chapter_number: int) -> NovelState:
    """从 DB 构建 Agent 模式下的模拟 NovelState

    Agent tool 不在 LangGraph 工作流中运行，没有现成的 state。
    从 DB 加载所有必要数据，构建与工作流模式等价的 state dict，
    确保 _build_chapter_content_messages 等函数可以正常工作。
    """
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    chapter_outlines = (
        db.query(ChapterOutline)
        .filter(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number)
        .all()
    )
    chapters = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
        .all()
    )

    return {
        "outline_title": outline.title if outline else "",
        "outline_summary": outline.summary if outline else "",
        "outline_plot_points": outline.plot_points if outline else [],
        "outline_world_setting": outline.world_setting if outline else {},
        "outline_emotional_curve": outline.emotional_curve if outline else "",
        "chapter_count": outline.chapter_count_confirmed or outline.chapter_count_suggested or 10,
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
            "novelType": outline.novel_type if outline and hasattr(outline, 'novel_type') else "",
            "targetWords": outline.target_words if outline and hasattr(outline, 'target_words') else 100000,
            "stylePreference": outline.style_preference if outline and hasattr(outline, 'style_preference') else "",
            "contextStrategy": outline.context_strategy if outline and hasattr(outline, 'context_strategy') else None,
        },
        "_prompts": DEFAULT_PROMPTS,
        "arcs": [],
    }
```

- [ ] **Step 2: 删除 `_calc_max_tokens` 重复定义**

删除 `chapter_service.py` 中第 53-55 行的 `_calc_max_tokens` 函数（已从 `chapter_generation.py` 导入）。

- [ ] **Step 3: 重写 `generate_chapter()` 使用三阶段管道**

将现有的 `generate_chapter()` 函数（第 58-131 行）替换为：

```python
async def generate_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """生成章节正文——使用与工作流模式相同的 prompt 体系和质量管道"""
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()
    if not outline:
        return {"error": f"第{chapter_number}章大纲不存在"}

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

    # Phase 1: Draft
    draft_content = ""
    try:
        async for chunk in generate_chapter_content_stream(state, chapter_outline, llm):
            draft_content += chunk
    except Exception as e:
        logger.error(f"Chapter draft generation failed: {e}")
        return {"error": f"生成失败: {str(e)}"}

    if not draft_content.strip():
        return {"error": "生成结果为空，请重试"}

    # Phase 2: SelfCheck
    try:
        check_result = await _self_check_chapter(llm, draft_content, state)
    except Exception as e:
        logger.warning(f"Chapter self-check failed, using draft: {e}")
        check_result = {"paragraphs": []}

    # Phase 3: Refine
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
    }
```

- [ ] **Step 4: 重写 `review_chapter()` 使用 prompt 模板**

将现有的 `review_chapter()` 函数（第 133-179 行）替换为：

```python
async def review_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """审核章节——使用系统 prompt 模板"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    # 构建章节大纲字符串（供 prompt 模板使用）
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
    system_template, user_template = get_prompts_from_state(state, "review")
    prompt_template = get_prompt_template(system_template, user_template)

    # 获取题材/风格信息
    info = state.get("collected_info", {})
    genre = info.get("novelType", "")

    prompt = safe_format(prompt_template,
        strictness="standard",
        chapter_outline=chapter_outline_str,
        chapter_content=chapter.content,
        genre=genre,
        style_preference=info.get("stylePreference", ""),
    )

    try:
        result_text = await llm.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        review_result = json.loads(result_text)
        return {"success": True, "review": review_result}
    except json.JSONDecodeError:
        return {"success": True, "review": {"passed": True, "raw": result_text}, "warning": "审核结果解析不完整"}
    except Exception as e:
        logger.error(f"Review failed: {e}")
        return {"error": f"审核失败: {str(e)}"}
```

- [ ] **Step 5: 重写 `rewrite_chapter()` 使用 prompt 模板**

将现有的 `rewrite_chapter()` 函数（第 182-247 行）替换为：

```python
async def rewrite_chapter(db: Session, project_id: int, chapter_number: int, review_feedback: str) -> dict:
    """根据审核意见重写章节——使用 prompt 模板"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在"}

    state = _build_agent_novel_state(db, project_id, chapter_number)
    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

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

    # 使用 get_prompts_from_state 正确解析 prompt
    system_template, user_template = get_prompts_from_state(state, "rewrite")
    prompt_template = get_prompt_template(system_template, user_template)

    info = state.get("collected_info", {})
    genre = info.get("novelType", "")

    prompt = safe_format(prompt_template,
        chapter_outline=chapter_outline_str,
        review_feedback=review_feedback,
        original_content=chapter.content,
        genre=genre,
    )

    max_tokens = _calc_max_tokens(outline.target_words if outline else 3000)

    full_content = ""
    try:
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ):
            if chunk:
                full_content += chunk
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        return {"error": f"重写失败: {str(e)}"}

    if not full_content.strip():
        return {"error": "重写结果为空，请重试"}

    try:
        chapter.content = full_content
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(full_content)
    preview = full_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章已重写（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title if outline else f"第{chapter_number}章",
        "word_count": word_count,
        "preview": preview,
    }
```

- [ ] **Step 6: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.services.chapter_service import _build_agent_novel_state, generate_chapter, review_chapter, rewrite_chapter; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/services/chapter_service.py
git commit -m "refactor(agents): integrate chapter_service with prompt system and Draft-SelfCheck-Refine pipeline"
```

---

## Task 1.1: 创建 `backend/app/agents/agent_context.py`

**Files:**
- Create: `backend/app/agents/agent_context.py`

- [ ] **Step 1: 创建文件**

```python
# backend/app/agents/agent_context.py
"""Agent 上下文构建器

按优先级将项目数据注入 Agent system message，受 token budget 约束。
与 agent_graph.py 分离，方便独立测试。
"""

import json
import re

from app.database import SessionLocal
from app.models.outline import Outline, ChapterOutline
from app.models.character import Character
from app.models.chapter import Chapter


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
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return int(chinese_chars * 2 + english_words * 1.3)


def build_project_context(
    project_id: int,
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
) -> dict:
    """构建项目上下文，按优先级注入原文，受 token budget 约束

    优先级：
    P1: 当前章节完整正文
    P2: 完整大纲
    P3: 角色列表
    P4: 当前章节大纲
    P5: 所有章节标题+状态
    P6: 前后章节摘要
    """
    db = SessionLocal()
    try:
        budget = BudgetTracker(max_tokens)
        context: dict = {}

        # P1: 当前章节完整正文
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

        # P3: 角色列表
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

        # P5: 所有章节标题+状态
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

        # P6: 前后章节摘要
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

- [ ] **Step 2: 验证导入**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.agent_context import BudgetTracker, estimate_tokens, build_project_context; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_context.py
git commit -m "feat(agents): add agent_context.py with BudgetTracker and prioritized context builder"
```

---

## Task 1.2: 更新 `agent_graph.py` 使用新 context 模块

**Files:**
- Modify: `backend/app/agents/agent_graph.py`

- [ ] **Step 1: 删除旧的 `build_project_context()`，改为从 agent_context 导入**

```python
# backend/app/agents/agent_graph.py

# 删除第 19-44 行的 build_project_context 函数

# 在 import 区追加：
from app.agents.agent_context import build_project_context

# 删除不再需要的 import：Outline, ChapterOutline, Character（如果只用于旧函数）
```

- [ ] **Step 2: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.agent_graph import build_project_context; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_graph.py
git commit -m "refactor(agents): delegate build_project_context to agent_context module"
```

---

## Task 1.3: 更新 `agent.py` system message 模板

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 更新 `AgentChatRequest` 新增 `current_chapter_number` 字段**

```python
# backend/app/api/agent.py

class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str
    model_config_id: Optional[int] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    current_chapter_number: Optional[int] = None  # 新增
    history: Optional[list[dict]] = None
```

- [ ] **Step 2: 更新 `agent_chat()` 中 system message 构建逻辑**

```python
# backend/app/api/agent.py
# 在 agent_chat() 函数中，替换 context 构建和 system message 部分：

    # 构建项目上下文（原文注入 + token budget）
    context = build_project_context(
        project_id,
        current_chapter_number=req.current_chapter_number,
    )

    # 构建 system message
    current_chapter_line = f"\\n当前章节：第{req.current_chapter_number}章" if req.current_chapter_number else ""
    system_content = f"""你是一位专业的小说创作搭档。你可以帮助用户修改大纲、角色设定、章节大纲，也可以生成章节正文、审核章节、重写章节。

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
4. 优先使用 revise_section 做局部修改，避免整章重写

用户当前查看：{req.active_tab or '未知'}{f' / {req.active_menu_item}' if req.active_menu_item else ''}{current_chapter_line}

请根据用户的需求，调用相应的工具来修改项目内容或生成内容。修改后简要说明你做了什么。"""
```

- [ ] **Step 3: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.api.agent import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "feat(agent): update system message with full context injection and behavioral rules"
```

---

## Task 2.1: 创建 `backend/app/agents/services/edit_service.py`

**Files:**
- Create: `backend/app/agents/services/edit_service.py`

- [ ] **Step 1: 创建文件**

```python
# backend/app/agents/services/edit_service.py
"""精细编辑服务

提供段落级编辑能力：edit_paragraph, insert_scene, revise_section, polish_prose。
精确操作（edit_paragraph, insert_scene）不调 LLM，直接 DB 读写。
语义操作（revise_section, polish_prose）调 LLM 执行修改。
"""

import re

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.outline import ChapterOutline
from app.agents.tool_context import get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_paragraphs(content: str) -> list[str]:
    """规范化段落分割

    处理 \\r\\n、\\n\\n、连续空行、HTML 标签等格式变体。
    返回非空段落列表。
    """
    clean = re.sub(r'<[^>]+>', '', content)
    clean = clean.replace('\r\n', '\n').replace('\r', '\n')
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', clean)]
    return [p for p in paragraphs if p]


def _join_paragraphs(paragraphs: list[str]) -> str:
    """段落列表拼接回纯文本"""
    return '\n\n'.join(paragraphs)


async def edit_paragraph(
    db: Session,
    project_id: int,
    chapter_number: int,
    paragraph_index: int,
    new_content: str,
) -> dict:
    """替换指定段落（0-indexed）"""
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


async def insert_scene(
    db: Session,
    project_id: int,
    chapter_number: int,
    position: int,
    scene_content: str,
) -> dict:
    """在指定位置前插入场景（0=开头，N=末尾）"""
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


async def revise_section(
    db: Session,
    project_id: int,
    chapter_number: int,
    instruction: str,
    start_para: int = 0,
    end_para: int = -1,
) -> dict:
    """按指令重写段落范围"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    paragraphs = _normalize_paragraphs(chapter.content)
    if end_para == -1:
        end_para = len(paragraphs) - 1
    if start_para < 0 or end_para >= len(paragraphs) or start_para > end_para:
        return {"error": f"段落范围超出（共{len(paragraphs)}段）"}

    target = '\n\n'.join(paragraphs[start_para:end_para + 1])

    llm = resolve_llm_service(get_model_config_id(), get_user_id())
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

    paragraphs[start_para:end_para + 1] = [revised.strip()]
    chapter.content = _join_paragraphs(paragraphs)
    db.commit()

    return {"success": True, "preview": revised[:200], "range": f"段落{start_para+1}-{end_para+1}"}


async def polish_prose(
    db: Session,
    project_id: int,
    chapter_number: int,
    style_instruction: str = "",
) -> dict:
    """保持情节不变，优化文笔"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    llm = resolve_llm_service(get_model_config_id(), get_user_id())

    style_note = f"\n风格要求：{style_instruction}" if style_instruction else ""
    prompt = f"""请润色以下小说章节的文笔，保持情节、人物对话、结构完全不变。
只优化语言的流畅度、节奏感和文学性。{style_note}

原文：
{chapter.content}

请直接输出润色后的完整章节。"""

    try:
        polished = await llm.chat([{"role": "user", "content": prompt}], max_tokens=16384)
    except Exception as e:
        return {"error": f"润色失败: {str(e)}"}

    if not polished or not polished.strip():
        return {"error": "润色结果为空，请重试"}

    chapter.content = polished.strip()
    db.commit()

    word_count = len(polished)
    preview = polished[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章已润色",
        "word_count": word_count,
        "preview": preview,
    }
```

- [ ] **Step 2: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.services.edit_service import _normalize_paragraphs, _join_paragraphs, edit_paragraph, insert_scene, revise_section, polish_prose; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/services/edit_service.py
git commit -m "feat(agents): add edit_service with paragraph-level editing tools"
```

---

## Task 2.2: 在 `agent_tools.py` 注册 4 个新 tool

**Files:**
- Modify: `backend/app/agents/agent_tools.py`

- [ ] **Step 1: 追加 import 和 4 个新 tool 定义**

```python
# backend/app/agents/agent_tools.py

# 在 import 区追加：
from app.agents.services.edit_service import (
    edit_paragraph as svc_edit_paragraph,
    insert_scene as svc_insert_scene,
    revise_section as svc_revise_section,
    polish_prose as svc_polish_prose,
)

# 在文件末尾（AGENT_TOOLS 之前）追加 4 个新 tool：

@tool
async def edit_paragraph(project_id: int, chapter_number: int, paragraph_index: int, new_content: str) -> dict:
    """替换指定章节的某个段落。paragraph_index 从 0 开始计数。"""
    db = SessionLocal()
    try:
        return await svc_edit_paragraph(db, project_id, chapter_number, paragraph_index, new_content)
    finally:
        db.close()


@tool
async def insert_scene(project_id: int, chapter_number: int, position: int, scene_content: str) -> dict:
    """在章节的指定位置插入新场景。position=0 表示开头，position=N 表示末尾。"""
    db = SessionLocal()
    try:
        return await svc_insert_scene(db, project_id, chapter_number, position, scene_content)
    finally:
        db.close()


@tool
async def revise_section(project_id: int, chapter_number: int, instruction: str, start_para: int = 0, end_para: int = -1) -> dict:
    """按指令修改章节中的段落范围。start_para 和 end_para 从 0 开始计数，-1 表示到末尾。instruction 用自然语言描述修改要求。"""
    db = SessionLocal()
    try:
        return await svc_revise_section(db, project_id, chapter_number, instruction, start_para, end_para)
    finally:
        db.close()


@tool
async def polish_prose(project_id: int, chapter_number: int, style_instruction: str = "") -> dict:
    """润色章节文笔，保持情节不变。style_instruction 可选，指定风格方向。"""
    db = SessionLocal()
    try:
        return await svc_polish_prose(db, project_id, chapter_number, style_instruction)
    finally:
        db.close()


# AGENT_TOOLS 列表追加 4 个新 tool：
AGENT_TOOLS = [
    read_outline,
    read_characters,
    read_chapter_outlines,
    read_relations,
    update_outline,
    update_character,
    create_character,
    update_chapter_outline,
    update_relations,
    generate_chapter_content,
    review_chapter,
    rewrite_chapter,
    edit_paragraph,       # 新增
    insert_scene,          # 新增
    revise_section,        # 新增
    polish_prose,          # 新增
]
```

- [ ] **Step 2: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.agent_tools import AGENT_TOOLS; print(f'Total tools: {len(AGENT_TOOLS)}')"
```

期望输出：`Total tools: 16`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_tools.py
git commit -m "feat(agents): register 4 new editing tools in agent_tools"
```

---

## Task 2.3: 更新 `agent.py` write_tools 和 module_map

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 在 `stream_agent_events()` 中追加新 tool 配置**

```python
# backend/app/api/agent.py
# 在 stream_agent_events() 函数中：

    write_tools = {
        "update_outline", "update_character", "create_character",
        "update_chapter_outline", "update_relations",
        "generate_chapter_content", "rewrite_chapter",
        "edit_paragraph", "insert_scene", "revise_section", "polish_prose",  # 新增
    }
    module_map = {
        "update_outline": "outline",
        "update_character": "characters",
        "create_character": "characters",
        "update_chapter_outline": "chapter_outlines",
        "update_relations": "relations",
        "generate_chapter_content": "writing",
        "rewrite_chapter": "writing",
        "edit_paragraph": "writing",       # 新增
        "insert_scene": "writing",          # 新增
        "revise_section": "writing",        # 新增
        "polish_prose": "writing",          # 新增
    }
```

- [ ] **Step 2: 验证**

```bash
docker exec novelagent-backend-1 python -c "from app.api.agent import router; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "feat(agent): add new editing tools to write_tools and module_map"
```

---

## Task 3.1: ChapterPreviewCard 懒加载完整内容

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionChat.tsx`

- [ ] **Step 1: 更新 ChapterPreviewCard 组件**

```tsx
// frontend/src/components/workbench/AICompanionChat.tsx

// 在文件顶部追加 import：
import { useParams } from 'react-router-dom'

// ChapterPreviewCard 组件替换为：

function ChapterPreviewCard({ data }: { data: Record<string, unknown> })
{
  const [expanded, setExpanded] = useState(false)
  const [fullContent, setFullContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const preview = String(data.preview || '')
  const title = String(data.title || '')
  const wordCount = Number(data.word_count || 0)
  const chapterNumber = Number(data.chapter_number || 0)
  const action = String(data.action || 'generated')
  const actionLabel = action === 'rewritten' ? '已重写' : '已生成'
  const { id } = useParams()
  const projectId = parseInt(id || '0')

  const handleExpand = async () =>
  {
    if (fullContent !== null)
    {
      setExpanded(!expanded)
      return
    }
    setLoading(true)
    try
    {
      const res = await fetch(`/api/projects/${projectId}/chapters`)
      const data = await res.json()
      const chapter = (data.chapters || []).find(
        (ch: { chapter_number: number }) => ch.chapter_number === chapterNumber
      )
      if (chapter?.content)
      {
        setFullContent(chapter.content)
        setExpanded(true)
      }
    }
    catch
    {
      // 加载失败，保持预览状态
    }
    finally
    {
      setLoading(false)
    }
  }

  return (
    <div className="my-1.5 rounded bg-slate-800/60 border border-emerald-700/30 px-2.5 py-2">
      <div className="text-[10px] text-emerald-400/80 mb-1">
         {title} · {actionLabel} · {wordCount}字
      </div>
      <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
        {expanded && fullContent ? fullContent : preview.slice(0, 150)}
        {(preview.length > 150 || (!expanded && wordCount > 200)) && (
          <button
            onClick={handleExpand}
            disabled={loading}
            className="ml-1 text-slate-500 hover:text-slate-300 disabled:opacity-50"
          >
            {loading ? '加载中...' : expanded ? '收起' : '...展开全部'}
          </button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 验证构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

期望：构建成功无错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/AICompanionChat.tsx
git commit -m "feat(frontend): add lazy full content loading to ChapterPreviewCard"
```

---

## Task 3.2: AICompanionInput 新增快捷指令按钮

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionInput.tsx`

- [ ] **Step 1: 更新组件**

```tsx
// frontend/src/components/workbench/AICompanionInput.tsx

import { useState } from 'react'
import { Send, PenTool, Search, Sparkles, FileText, Users } from 'lucide-react'

interface QuickCommand
{
  label: string
  icon: React.ComponentType<{ className?: string }>
  prompt: string
  showWhen: string[]
}

const QUICK_COMMANDS: QuickCommand[] = [
  { label: '写下一章', icon: PenTool, prompt: '请继续写下一章', showWhen: ['writing'] },
  { label: '审核本章', icon: Search, prompt: '请审核当前章节', showWhen: ['writing'] },
  { label: '润色本章', icon: Sparkles, prompt: '请润色当前章节的文笔，保持情节不变', showWhen: ['writing'] },
  { label: '查看大纲', icon: FileText, prompt: '请展示当前大纲概要', showWhen: ['outline', 'chapter_outlines', 'characters', 'relations', 'settings'] },
  { label: '查看角色', icon: Users, prompt: '请展示所有角色', showWhen: ['characters', 'relations'] },
]

interface AICompanionInputProps
{
  onSend: (message: string) => void
  disabled?: boolean
  disabledReason?: string
  activeTab?: string
}

export function AICompanionInput({ onSend, disabled, disabledReason, activeTab }: AICompanionInputProps)
{
  const [input, setInput] = useState('')

  const handleSubmit = (e: React.FormEvent) =>
  {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  const handleQuickCommand = (prompt: string) =>
  {
    setInput(prompt)
  }

  const visibleCommands = QUICK_COMMANDS.filter(
    (cmd) => !activeTab || cmd.showWhen.includes(activeTab)
  )

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-700 p-2">
      {disabled && disabledReason && (
        <div className="text-[10px] text-amber-400/80 mb-1.5 text-center">{disabledReason}</div>
      )}

      {/* 快捷指令按钮 */}
      {visibleCommands.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {visibleCommands.map((cmd) => (
            <button
              key={cmd.label}
              type="button"
              onClick={() => handleQuickCommand(cmd.prompt)}
              disabled={disabled}
              className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 disabled:opacity-50 transition-colors"
            >
              <cmd.icon className="h-3 w-3" />
              {cmd.label}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="说说你的想法..."
          disabled={disabled}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white px-3 py-2 rounded-md text-xs transition-colors"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </form>
  )
}
```

- [ ] **Step 2: 验证构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/AICompanionInput.tsx
git commit -m "feat(frontend): add quick command buttons to AICompanionInput"
```

---

## Task 3.3: AICompanionSidebar 传入 activeTab

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionSidebar.tsx`

- [ ] **Step 1: 传递 activeTab prop**

```tsx
// frontend/src/components/workbench/AICompanionSidebar.tsx

// 在 AICompanionSidebar 函数体中，sending state 之后追加：
const activeTabFromStore = useWorkbenchStore((s) => s.activeTab)

// 找到：
<AICompanionInput onSend={handleSend} disabled={disabled} disabledReason={disabledReason} />

// 改为：
<AICompanionInput
  onSend={handleSend}
  disabled={disabled}
  disabledReason={disabledReason}
  activeTab={activeTabFromStore}
/>
```

注意：`handleSend` 函数内部已经通过 `useWorkbenchStore.getState()` 获取了 `activeTab`，不需要改动 handleSend 逻辑。

- [ ] **Step 2: 验证构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/AICompanionSidebar.tsx
git commit -m "feat(frontend): pass activeTab to AICompanionInput for quick commands"
```

---

## Task 3.4: 更新 agentApi 传递 current_chapter_number

**Files:**
- Modify: `frontend/src/lib/agentApi.ts`
- Modify: `frontend/src/components/workbench/AICompanionSidebar.tsx`

- [ ] **Step 1: 更新 AgentChatOptions 接口**

```typescript
// frontend/src/lib/agentApi.ts

export interface AgentChatOptions {
  modelConfigId?: number
  activeTab?: string
  activeMenuItem?: string
  currentChapterNumber?: number  // 新增
  history?: Array<{ role: string; content: string }>
  signal?: AbortSignal
}
```

- [ ] **Step 2: 更新 sendAgentMessage 传递字段**

```typescript
// frontend/src/lib/agentApi.ts
// 在 createSSEStream 调用的 body 中追加：

body: {
  message,
  model_config_id: options?.modelConfigId,
  active_tab: options?.activeTab,
  active_menu_item: options?.activeMenuItem,
  current_chapter_number: options?.currentChapterNumber,  // 新增
  history: options?.history,
},
```

- [ ] **Step 3: 更新 AICompanionSidebar 传递 currentChapterNumber**

```tsx
// frontend/src/components/workbench/AICompanionSidebar.tsx

// 在 handleSend 函数中，修改从 store 获取的数据：
const { activeTab, activeMenuItem, aiMessages, selectedChapterNumber } = useWorkbenchStore.getState()

// 在 sendAgentMessage 调用的 options 中追加：
await sendAgentMessage(projectId, message, {
  // ... 现有回调 ...
}, {
  activeTab,
  activeMenuItem,
  currentChapterNumber: selectedChapterNumber || undefined,  // 新增
  history,
  modelConfigId: selectedModelId || undefined,
  signal: controller.signal,
})
```

- [ ] **Step 4: 验证 TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 5: 验证构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/agentApi.ts frontend/src/components/workbench/AICompanionSidebar.tsx
git commit -m "feat(frontend): pass currentChapterNumber to agent chat for context injection"
```

---

## 执行顺序

任务必须按顺序执行：

```
Step 0: 消除技术债
  Task 0.1 → Task 0.2

Step 1: 上下文注入
  Task 1.1 → Task 1.2 → Task 1.3

Step 2: 精细编辑 Tools
  Task 2.1 → Task 2.2 → Task 2.3

Step 3: UX 升级
  Task 3.1 → Task 3.2 → Task 3.3 → Task 3.4
```

Step 间无强依赖（Step 1 不依赖 Step 0 完成），但建议按顺序执行以减少冲突。

---

## 最终验证

全部任务完成后：

```bash
# 后端验证
docker exec novelagent-backend-1 python -c "
from app.utils.llm import resolve_llm_service
from app.agents.agent_context import BudgetTracker, build_project_context
from app.agents.services.chapter_service import _build_agent_novel_state, generate_chapter, review_chapter, rewrite_chapter
from app.agents.services.edit_service import _normalize_paragraphs, edit_paragraph, insert_scene, revise_section, polish_prose
from app.agents.agent_tools import AGENT_TOOLS
from app.agents.agent_graph import create_agent_graph, build_project_context
print(f'All imports OK. Tools: {len(AGENT_TOOLS)}')
"

# 前端验证
cd frontend && npm run build
```

预期：所有导入成功，前端构建通过。
