# 第一阶段：消除重复代码 + 修复 P0 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 10 处重复代码 + 修复 2 个 P0 缺陷，共涉及 15 个文件

**Architecture:** 后端抽取共享工具函数到 `app/agents/nodes/utils.py`（节点工具）和 `app/utils/deps.py`（依赖注入），前端统一使用 `ChapterList`、`createSSEStream`、`LoadingSpinner` 等已有组件，修复 Settings 静默失败和 ProjectDetail 恢复功能

**Tech Stack:** Python 3.11 + FastAPI, React 18 + TypeScript

**Spec:** `docs/superpowers/specs/2026-04-29-full-code-quality-optimization-design.md`

**Before starting:** Run `docker logs novelagent-backend-1 --tail 5` to verify backend is running. If not, run `docker compose up -d`.

---

### Task 1: 后端 - 创建节点工具函数模块

**Files:**
- Create: `backend/app/agents/nodes/utils.py`

- [ ] **Step 1: 创建 `backend/app/agents/nodes/utils.py`**

```python
"""节点共享工具函数"""


def _format_chapter_outline_str(chapter_outline: dict) -> str:
    """格式化章节大纲为提示词用字符串"""
    return f"""
章节名：{chapter_outline.get('title', '')}
场景：{chapter_outline.get('scene', '')}
人物：{chapter_outline.get('characters', '')}
情节：{chapter_outline.get('plot', '')}
冲突：{chapter_outline.get('conflict', '')}
转折：{chapter_outline.get('turning_point', '无')}
钩子：{chapter_outline.get('hook', '')}
"""


def format_characters_info(state: dict) -> str:
    """格式化人物设定信息为提示词用字符串

    优先使用详细人物设定(characters 字段)，回退到大纲人物设定，
    最后回退到灵感采集信息。
    """
    detailed_characters = state.get("characters", [])
    characters = state.get("outline_characters", [])
    info = state.get("collected_info", {})

    if detailed_characters:
        chars_str = "【详细人物设定】\n"
        for c in detailed_characters:
            chars_str += f"- {c.get('name', '')}（{c.get('role', '配角')}）：\n"
            if c.get('appearance'):
                chars_str += f"  外貌：{c.get('appearance')}\n"
            if c.get('personality'):
                chars_str += f"  性格：{c.get('personality')}\n"
            if c.get('background'):
                chars_str += f"  背景：{c.get('background')}\n"
            if c.get('skills'):
                chars_str += f"  能力：{c.get('skills')}\n"
            if c.get('goals'):
                chars_str += f"  目标：{c.get('goals')}\n"
        return chars_str
    elif characters:
        return "\n".join([
            f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
            for c in characters
        ])
    else:
        return info.get("customProtagonist") or info.get("protagonist", "未指定")


def format_relations_info(state: dict, current_chapter: int) -> str:
    """格式化人物关系为提示词用字符串"""
    relations = state.get("relations", [])
    if not relations:
        return ""

    relations_str = "\n【人物关系】\n"
    for r in relations:
        relations_str += f"- {r.get('character1', '')} 与 {r.get('character2', '')}：{r.get('relationship_type', '')}"
        if r.get('description'):
            relations_str += f"（{r.get('description')}）"
        relations_str += "\n"
    return relations_str


def format_evolution_info(state: dict, current_chapter: int) -> tuple:
    """格式化人物演变历史和规划为提示词用字符串

    Returns:
        (evolution_str, evolution_plans_str)
    """
    evolution_records = state.get("evolution_records", [])
    evolution_plans = state.get("evolution_plans", [])

    evolution_str = ""
    if evolution_records:
        evolution_str = "\n【人物演变（历史）】\n"
        for e in evolution_records[-3:]:
            evolution_str += f"- 第{e.get('chapter_number', '')}章：{e.get('actual_changes', '')}\n"

    evolution_plans_str = ""
    if evolution_plans:
        nearby_plans = [
            p for p in evolution_plans
            if abs(p.get("chapter_number", 0) - current_chapter) <= 2
        ]
        if nearby_plans:
            evolution_plans_str = "\n【即将发生的关系变化】\n"
            for p in nearby_plans:
                evolution_plans_str += f"- 第{p.get('chapter_number', 0)}章：{p.get('changes', '')}\n"

    return evolution_str, evolution_plans_str


def format_world_setting(state: dict) -> str:
    """格式化世界观设定为提示词用字符串"""
    world_setting = state.get("outline_world_setting", {})
    info = state.get("collected_info", {})

    if world_setting:
        return f"时代：{world_setting.get('era', '')}，核心设定：{world_setting.get('core_rules', '')}"
    else:
        return info.get("customWorldSetting") or info.get("worldSetting", "未指定")
```

- [ ] **Step 2: 验证导入成功**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info, format_relations_info, format_evolution_info, format_world_setting; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/nodes/utils.py
git commit -m "refactor(backend): add shared node utility functions

Extract _format_chapter_outline_str, format_characters_info,
format_relations_info, format_evolution_info, format_world_setting"
```

---

### Task 2: 后端 - chapter_generation.py 使用工具函数消除重复

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py`

- [ ] **Step 1: 在 chapter_generation.py 顶部添加导入**

在文件第 12 行后（`from app.utils.llm import get_llm_from_state_async` 之后）添加：

```python
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
)
```

- [ ] **Step 2: 替换 `generate_chapter_content_stream` 中的第 267-337 行**

删除原来的第 267-337 行（从 `# 格式化章节大纲` 到 `world_str = ...` 整个块），替换为：

```python
    # 格式化章节大纲（使用共享工具函数）
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)

    # 格式化人物关系（使用共享工具函数）
    relations_str = format_relations_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化人物演变历史（使用共享工具函数）
    evolution_str, evolution_plans_str = format_evolution_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)
```

- [ ] **Step 3: 替换 `generate_chapter_content_node` 中的第 427-469+ 行**

删除原来的第 427 行开始到关系变化格式化结束的整个块（约 43 行），替换为与 Step 2 相同的 5 个函数调用。具体行范围需要看文件当前状态。

查找 `# 格式化章节大纲` 开头的注释（第二处），从该注释开始到 `# 格式化世界观` 块的末尾（`world_str = format_world_setting(state)` 前的内容完全删除），替换为上述 6 行代码。

- [ ] **Step 4: 删除两个函数中不再需要的变量声明**

在 `generate_chapter_content_stream` 中，删除以下不再需要的变量声明行（如果存在）：
- `detailed_characters = state.get("characters", [])`
- `relations = state.get("relations", [])`
- `evolution_records = state.get("evolution_records", [])`
- `evolution_plans = state.get("evolution_plans", [])`

在 `generate_chapter_content_node` 中同样删除这些行。

注意：`characters = state.get("outline_characters", [])` 和 `info = state.get("collected_info", {})` 和 `world_setting = state.get("outline_world_setting", {})` 如果只用于格式化可以删除,但需要检查是否有其他用途。

- [ ] **Step 5: 验证导入和功能**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.nodes.chapter_generation import generate_chapter_content_stream, generate_chapter_content_node; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/nodes/chapter_generation.py
git commit -m "refactor(backend): use shared utils in chapter_generation

Replace duplicated formatting logic with _format_chapter_outline_str,
format_characters_info, format_relations_info, format_evolution_info,
format_world_setting"
```

---

### Task 3: 后端 - review.py 和 rewrite.py 使用工具函数

**Files:**
- Modify: `backend/app/agents/nodes/review.py`
- Modify: `backend/app/agents/nodes/rewrite.py`

- [ ] **Step 1: review.py 添加导入**

在 `review.py` 第 10 行后添加：

```python
from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info
```

- [ ] **Step 2: review.py 替换 `review_chapter_node` 中的格式化逻辑（第 80-95 行）**

删除第 80-95 行（从 `# 格式化章节大纲` 到 `chars_str = ...`），替换为：

```python
    # 格式化章节大纲（使用共享工具函数）
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)
```

- [ ] **Step 3: review.py 中删除不再需要的变量**

删除第 78 行的 `characters = state.get("outline_characters", [])` 和第 77 行的 `info = state.get("collected_info", {})`（如果 review_chapter_node 的其他地方不再使用这些变量）。

注意检查：`info` 在第 101、103 行仍在使用（`info.get("novelType"...)`, `info.get("stylePreference"...）`，所以 `info` 不能删除。

- [ ] **Step 4: rewrite.py 添加导入**

在 `rewrite.py` 第 9 行后添加：

```python
from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info
```

- [ ] **Step 5: rewrite.py 替换 `rewrite_chapter_node` 中的格式化逻辑（第 35-50 行）**

删除第 35-50 行，替换为：

```python
    # 格式化章节大纲（使用共享工具函数）
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)
```

- [ ] **Step 6: rewrite.py 中删除不再需要的变量**

删除第 32 行的 `info = state.get("collected_info", {})` 和第 33 行的 `characters = state.get("outline_characters", [])`。

检查：`info` 在第 56-57 行仍在使用，不能删除。`characters` 现在由 `format_characters_info` 内部处理，可以删除。

- [ ] **Step 7: 验证导入**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.nodes.review import review_chapter_node; from app.agents.nodes.rewrite import rewrite_chapter_node; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents/nodes/review.py backend/app/agents/nodes/rewrite.py
git commit -m "refactor(backend): use shared utils in review and rewrite nodes"
```

---

### Task 4: 后端 - 创建依赖注入工具模块

**Files:**
- Create: `backend/app/utils/deps.py`

- [ ] **Step 1: 创建 `backend/app/utils/deps.py`**

先确认 `backend/app/utils/` 目录存在：

```bash
ls /opt/project/novelagent/backend/app/utils/
```

然后读取 `backend/app/utils/llm.py` 中 `get_llm_for_user` 函数的完整签名以正确设计包装函数：

读取 `backend/app/utils/llm.py:16-74` 获取完整实现。

基于分析后编写 `deps.py`：

```python
"""API 端点依赖注入工具函数"""

from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.settings import UserSettings
from app.models.model_config import ModelConfig
from app.services.llm import get_llm_service, get_llm_service_from_config


def get_user_settings_or_raise(user: User, db: Session) -> UserSettings:
    """获取用户设置，如果不存在则抛出 400 错误"""
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.id
    ).first()

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings not found"
        )

    return user_settings


def get_llm_for_context(request, user: User, user_settings: UserSettings, db: Session):
    """根据请求和用户上下文获取 LLM 服务

    优先使用请求中指定的模型配置，回退到默认配置，最后使用用户设置中的全局 API key。
    """
    from app.utils.llm import get_llm_for_user

    llm_config_id = request.llm_config_id if request else None
    return get_llm_for_user(user.id, user_settings, db, llm_config_id)
```

- [ ] **Step 2: 验证导入**

```bash
docker exec novelagent-backend-1 python -c "from app.utils.deps import get_user_settings_or_raise, get_llm_for_context; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/utils/deps.py
git commit -m "refactor(backend): add API dependency injection utilities

Add get_user_settings_or_raise and get_llm_for_context to
reduce duplicated user settings / LLM fetch logic in API endpoints"
```

---

### Task 5: 后端 - API 端点使用 deps 工具函数

**Files:**
- Modify: `backend/app/api/outline.py`
- Modify: `backend/app/api/chapters.py`
- Modify: `backend/app/api/workflow.py`

- [ ] **Step 1: 三个文件添加导入**

在 `outline.py` 顶部 imports 区域添加：
```python
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
```

在 `chapters.py` 顶部 imports 区域添加：
```python
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
```

在 `workflow.py` 顶部 imports 区域添加：
```python
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
```

- [ ] **Step 2: outline.py 替换两处用户设置获取**

第一处（第 88-96 行，`generate_outline` 中）:
```python
    # 获取用户设置
    user_settings = get_user_settings_or_raise(current_user, db)
```

第二处（如果 `set_chapter_count` 或 `confirm_outline` 等其他端点也有相同的模式，同样替换）

替换 LLM 获取（第 104-105 行）:
```python
    # 获取 LLM 服务
    llm_config_id = request.llm_config_id if request else None
    llm = get_llm_for_user(current_user.id, user_settings, db, llm_config_id)
```
替换为:
```python
    # 获取 LLM 服务
    llm = get_llm_for_context(request, current_user, user_settings, db)
```

- [ ] **Step 3: chapters.py 替换三处用户设置获取**

读取 chapters.py 第 143-160 行确认具体位置，将以下模式:
```python
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not user_settings:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User settings not found")

    llm_config_id = request.llm_config_id if request else None
    llm = get_llm_for_user(current_user.id, user_settings, db, llm_config_id)
```
替换为:
```python
    user_settings = get_user_settings_or_raise(current_user, db)
    llm = get_llm_for_context(request, current_user, user_settings, db)
```

需要找到 chapters.py 中所有使用此模式的端点（至少 3 处：`generate_chapter_outlines`、`generate_chapter_content`、`generate_chapter_content_new`）

- [ ] **Step 4: workflow.py 替换用户设置获取**

`run_workflow` 中第 227-235 行：
```python
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User settings not found"
        )
```
替换为:
```python
    user_settings = get_user_settings_or_raise(current_user, db)
```

- [ ] **Step 5: 运行后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/outline.py backend/app/api/chapters.py backend/app/api/workflow.py
git commit -m "refactor(backend): use dependency injection utils in API endpoints

Replace duplicated user settings fetch and LLM service creation
with get_user_settings_or_raise and get_llm_for_context"
```

---

### Task 6: 后端 - 移除遗留端点和重复依赖

**Files:**
- Modify: `backend/app/api/outline.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 移除 `info_collection_chat` 端点**

删除 `outline.py` 中第 430-454 行的 `info_collection_chat` 端点函数。先读取确认准确的行范围。

- [ ] **Step 2: 删除 requirements.txt 的重复 httpx**

删除 `requirements.txt` 中第 35 行（第二个 `httpx>=0.27.0`）。

- [ ] **Step 3: 验证后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/outline.py backend/requirements.txt
git commit -m "chore(backend): remove deprecated info_collection_chat endpoint and duplicate httpx dep"
```

---

### Task 7: 前端 - 创建通用 LoadingSpinner 组件

**Files:**
- Create: `frontend/src/components/ui/LoadingSpinner.tsx`

- [ ] **Step 1: 创建 `frontend/src/components/ui/LoadingSpinner.tsx`**

```tsx
import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps
{
  size?: 'sm' | 'md' | 'lg'
  text?: string
  fullPage?: boolean
}

/**
 * 通用加载状态组件
 * 统一项目中所有加载状态的展示方式
 */
export default function LoadingSpinner({
  size = 'md',
  text,
  fullPage = false,
}: LoadingSpinnerProps)
{
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  const spinner = (
    <Loader2 className={`animate-spin ${sizeClasses[size]} text-primary`} />
  )

  if (fullPage)
  {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-2">
        {spinner}
        {text && <p className="text-muted-foreground text-sm">{text}</p>}
      </div>
    )
  }

  if (text)
  {
    return (
      <div className="flex items-center gap-2">
        {spinner}
        <span className="text-muted-foreground text-sm">{text}</span>
      </div>
    )
  }

  return spinner
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ui/LoadingSpinner.tsx
git commit -m "feat(frontend): add LoadingSpinner component for unified loading states"
```

---

### Task 8: 前端 - Settings 静默失败修复（P0）

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Settings 顶部添加 toast 导入**

确认是否已有 `toast` 导入。如果不需要，确保有：
```tsx
import { toast } from 'sonner'
```

Settings.tsx 第 1 行当前只有 React 的 imports，需要在顶部添加 toast 导入。

- [ ] **Step 2: 修复 `fetchSettings` 的 catch 块（第 71-72 行）**

将:
```tsx
    } catch (err) {
      console.error('Failed to fetch settings:', err)
```
改为:
```tsx
    } catch (err) {
      console.error('Failed to fetch settings:', err)
      toast.error('加载设置失败')
```

- [ ] **Step 3: 修复 `loadModelConfigs` 的 catch 块（第 87-88 行）**

将:
```tsx
    } catch (err) {
      console.error('Failed to load model configs:', err)
```
改为:
```tsx
    } catch (err) {
      console.error('Failed to load model configs:', err)
      toast.error('加载模型配置失败')
```

- [ ] **Step 4: 修复 `loadPrompts` 的 catch 块**

读取 Settings.tsx 第 120-123 行区域，找到 `loadPrompts` 函数的 catch 块，添加 `toast.error('加载提示词失败')`

- [ ] **Step 5: 修复 `handleSaveSettings` 的 catch 块**

读取 Settings.tsx 第 130-140 行区域，找到保存设置的 catch 块，添加 `toast.error('保存设置失败')`

- [ ] **Step 6: 修复模型配置操作的所有静默失败**

在以下位置添加 toast（每个都是 `console.error` 的地方）：
- `onSetDefault` 回调 (~第 260-262行): 添加 `toast.error('设置默认模型失败')`
- `onDelete` 回调 (~第 266-269行): 添加 `toast.error('删除模型配置失败')`
- `handleSaveConfig` (~第 190行区域): 添加 `toast.error('保存模型配置失败')`
- `handleCheckHealth` (如果存在): 添加 `toast.error('健康检查失败')`
- Prompt 保存/重置: 添加 `toast.error('保存提示词失败')`

- [ ] **Step 7: 运行前端测试**

```bash
cd frontend && npm run test:run
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "fix(frontend): show toast errors for all Settings operations

Replace silent console.error with toast.error in all catch blocks
so users are aware when model config, settings, or prompt operations fail"
```

---

### Task 9: 前端 - 恢复创作功能实现（P0）

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 实现 `onResume` 回调**

在 ProjectDetail.tsx 中找到 `ResumeDialog` 的使用位置（接近文件末尾）。

当前的 `onResume` 仅 `console.log('Resume workflow')`。

将其改为调用 `workflowApi.runWorkflow(project.id, callbacks)` 重新启动 LangGraph 工作流。

具体实现需要先确认 `workflowApi` 的 `runWorkflow` 签名和所需的 callbacks。查看 `workflowApi.ts` 和 `useWorkflowStore` 中的用法模式。

```tsx
const handleResume = async () => {
  try {
    // 重新运行工作流，LangGraph checkpoint 会自动从中断位置恢复
    await workflowApi.runWorkflow(project.id, {
      onNodeStart: (nodeName: string) => {
        // 更新 store 中的阶段状态
      },
      onWaiting: (data: any) => {
        // 显示等待确认弹窗
      },
      onDone: () => {
        refreshProject()
        toast.success('创作恢复成功')
      },
      onError: (error: string) => {
        toast.error(`恢复失败: ${error}`)
      },
    })
  } catch (err) {
    toast.error('恢复创作失败')
  }
}
```

- [ ] **Step 2: 传给 ResumeDialog**

将 `handleResume` 传给 `<ResumeDialog>` 的 `onResume` prop。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectDetail.tsx
git commit -m "fix(frontend): implement resume workflow functionality

Replace console.log placeholder with actual workflowApi.runWorkflow
call to resume LangGraph workflow from checkpoint"
```

---

### Task 10: 前端 - Writing.tsx SSE 解析统一

**Files:**
- Modify: `frontend/src/pages/Writing.tsx`

- [ ] **Step 1: 替换手动 SSE 解析为 createSSEStream**

Writing.tsx 第 98-172 行的 `handleGenerate` 函数自己实现了完整的 fetch + SSE 解析。

将其改为使用 `createSSEStream`：

```tsx
const handleGenerate = async () => {
  if (!id || !currentChapter || isGenerating) return

  setIsGenerating(true)
  setContent('')
  setWordCount(0)
  setError(null)

  const abortController = new AbortController()
  abortControllerRef.current = abortController

  let accumulated = ''

  await createSSEStream(
    {
      url: `/api/projects/${id}/chapters/${currentChapter.chapter_number}/generate`,
      method: 'POST',
      signal: abortController.signal,
    },
    (type, data) => {
      if (type === 'message' || !type || type === 'chunk') {
        const decoded = typeof data === 'string' ? data : ''
        accumulated += decoded
        setContent(accumulated)
        setWordCount(accumulated.length)
      } else if (type === 'done') {
        // 生成完成，刷新章节列表
        loadChapterOutlines().then(() => {
          toast.success('章节生成完成')
        })
      }
    },
    (error) => {
      setError(error)
      setIsGenerating(false)
    }
  )

  setIsGenerating(false)
}
```

- [ ] **Step 2: 添加 createSSEStream 导入**

在 Writing.tsx 顶部添加：
```tsx
import { createSSEStream } from '@/lib/sseParser'
```

- [ ] **Step 3: 删除不再需要的 fetch 相关代码**

删除原来的 `getSessionToken`、`fetch`、`reader`、`decoder`、`btoa` 等逻辑（第 109-172 行）。

- [ ] **Step 4: 确认 `loadChapterOutlines` 辅助函数**

确保有刷新章节列表的函数，如果没有则创建一个。

- [ ] **Step 5: 运行前端测试**

```bash
cd frontend && npm run test:run
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Writing.tsx
git commit -m "refactor(frontend): use createSSEStream in Writing page

Replace manual SSE parsing with shared sseParser.createSSEStream
for consistency with other SSE consumers"
```

---

### Task 11: 前端 - 章节列表复用 ChapterList 组件

**Files:**
- Modify: `frontend/src/pages/Reading.tsx`
- Modify: `frontend/src/pages/Writing.tsx`
- Read: `frontend/src/components/project/WritingPanel.tsx`

- [ ] **Step 1: Reading.tsx 使用 ChapterList**

Reading.tsx 第 109-170+ 行有内联的章节列表 JSX（遍历 chapterOutlines 渲染）。

将其替换为 `<ChapterList>` 组件。需要在 Reading.tsx 顶部添加：
```tsx
import ChapterList from '@/components/project/ChapterList'
```

然后替换内联的章节列表为：
```tsx
<ChapterList
  chapters={chapterOutlines}
  selectedChapter={currentOutline}
  onSelectChapter={(chapter) => goToChapter(chapter.chapter_number)}
/>
```

- [ ] **Step 2: Writing.tsx 使用 ChapterList**

同样在 Writing.tsx 中使用 ChapterList。先读取 Writing.tsx 中章节列表的实现确认具体位置，然后替换。

- [ ] **Step 3: 运行前端测试**

```bash
cd frontend && npm run test:run
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Reading.tsx frontend/src/pages/Writing.tsx
git commit -m "refactor(frontend): reuse ChapterList component in Reading and Writing"
```

---

### Task 12: 第一阶段最终验证

- [ ] **Step 1: 运行后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```
Expected: All tests pass

- [ ] **Step 2: 运行前端测试**

```bash
cd frontend && npm run test:run
```
Expected: All tests pass

- [ ] **Step 3: 前端类型检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -50
```
Expected: No errors (或仅限预存错误)

- [ ] **Step 4: 前端构建**

```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 5: 确认所有后端导入正常**

```bash
docker exec novelagent-backend-1 python -c "
from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info, format_relations_info, format_evolution_info, format_world_setting
from app.agents.nodes.chapter_generation import generate_chapter_content_stream, generate_chapter_content_node
from app.agents.nodes.review import review_chapter_node
from app.agents.nodes.rewrite import rewrite_chapter_node
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
from app.api.outline import router as outline_router
from app.api.chapters import router as chapters_router
from app.api.workflow import router as workflow_router
print('All imports OK')
"
```

---

## Execution Checklist

- [ ] Task 1: utils.py
- [ ] Task 2: chapter_generation.py
- [ ] Task 3: review.py + rewrite.py
- [ ] Task 4: deps.py
- [ ] Task 5: API endpoints (outline, chapters, workflow)
- [ ] Task 6: remove legacy endpoint + duplicate dep
- [ ] Task 7: LoadingSpinner
- [ ] Task 8: Settings error handling
- [ ] Task 9: Resume workflow
- [ ] Task 10: Writing SSE
- [ ] Task 11: ChapterList reuse
- [ ] Task 12: Final verification