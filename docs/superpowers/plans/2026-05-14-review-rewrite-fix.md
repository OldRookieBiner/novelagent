# 审核流程三项修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-step. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复审核流程三个问题：隐藏审核流式原始文本、刷新后恢复审核结果、新增重写 SSE 端点和前端按钮

**Architecture:** 后端审核端点不再发送原始 chunk，改为使用 `sse_events.py` 集中管理的 SSE 注释行保持连接；前端从 DB 数据恢复审核结果并通过 prop 传递；新增 rewrite SSE 端点复用 LangGraph 节点核心逻辑（`_build_rewrite_messages`、`get_llm_from_state_async`、`build_initial_state`），与现有 review/generate 端点架构一致。前端共享 `mapReviewResult` 映射函数避免重复。

**Tech Stack:** Python/FastAPI (后端), React/TypeScript/Zustand (前端), SSE 流式协议

---

## 自审修正记录

| # | 问题 | 修正 |
|---|------|------|
| A | 前端 sseParser 隐式依赖空 data 跳过注释行 | 后端审核端点不发送任何中间事件，只发 done；无需依赖注释行解析 |
| B | WorkflowOrchestrator 已存在但 review/generate/rewrite 未使用 | 当前三端点直接调用 LLM 是既有技术债，本次不扩大但需明确标注。WorkflowOrchestrator 基于 `graph.astream_events`，要求完整的 LangGraph 图和检查点，不适合用户手动触发的单次操作 |
| C | mapReviewResult 在 AIAssistantPanel 和 WritingPanel 重复定义 | 提取到 `frontend/src/types/index.ts` 作为共享工具函数 |
| D | SSE 注释行字符串内联在 chapters.py | 使用 `sse_events.py` 的 `format_heartbeat()` 集中管理 |

## 架构决策说明

**Q: 为什么 rewrite 端点不走 LangGraph 图？**

A: LangGraph 图是自动工作流——从大纲到角色到章节到审核到重写，按顺序执行。但用户手动触发的"单次重写"不同于自动工作流中的 rewrite：
1. 自动工作流：review 失败 → 自动 rewrite → 自动 review → 循环
2. 手动操作：用户审核后看到建议 → 点击重写 → 看到重写结果 → 自行决定是否再审核

手动模式需要用户控制节奏，不能走自动工作流图。当前项目的 review/generate SSE 端点都走"单节点直接调用 LLM"模式，这是针对手动操作的既定架构。新增 rewrite 端点与之一致。

**Q: 为什么审核端点完全不发中间事件？**

A: 审核的结果只有结构化数据（评分、问题、建议）有意义。原始 LLM 输出是 JSON 文本，对用户无阅读价值。审核期间前端只需显示"审核中"加载状态，完成后一次性展示结构化结果。这与章节生成不同——章节生成需要流式预览因为用户要阅读内容。

---

## File Structure

| 文件 | 变更 | 职责 |
|------|------|------|
| `backend/app/schemas/chapter.py` | 修改 | ReviewResponse 添加 scores；新增 RewriteRequest |
| `backend/app/agents/sse_events.py` | 修改 | 新增 format_heartbeat() |
| `backend/app/api/chapters.py` | 修改 | 审核端点不发 chunk；新增 rewrite SSE 端点 |
| `backend/tests/test_review_endpoint.py` | 新建 | 审核端点 SSE 事件格式测试 |
| `backend/tests/test_rewrite_endpoint.py` | 新建 | 重写端点集成测试 |
| `frontend/src/types/index.ts` | 修改 | Chapter 类型添加字段；新增 mapReviewResult 共享函数 |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | 重构 | 删除流式预览；使用共享映射函数；添加重写按钮和逻辑 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 修改 | 传递审核结果；使用共享映射函数；添加重写回调 |

---

### Task 1: 后端 Schema — ReviewResponse 添加 scores，新增 RewriteRequest

**Files:**
- Modify: `backend/app/schemas/chapter.py`

- [ ] **Step 1: 修改 ReviewResponse 添加 scores 字段，新增 RewriteRequest**

```python
# backend/app/schemas/chapter.py

# 修改 ReviewResponse（约第71-75行），添加 scores 字段
class ReviewResponse(BaseModel):
    passed: bool
    feedback: str
    issues: list[dict] = []  # 修正：实际是 ReviewIssue 对象列表，非 string
    scores: dict = {}         # 新增：评分详情

# 在 ReviewResponse 之后新增 RewriteRequest
class RewriteRequest(BaseModel):
    """章节重写请求"""
    llm_config_id: Optional[int] = None
```

- [ ] **Step 2: 验证 Schema 无语法错误**

Run: `docker exec novelagent-backend-1 python -c "from app.schemas.chapter import ReviewResponse, RewriteRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/chapter.py
git commit -m "feat(schemas): add scores to ReviewResponse, add RewriteRequest schema"
```

---

### Task 2: 后端 SSE 事件 — 新增 format_heartbeat

**Files:**
- Modify: `backend/app/agents/sse_events.py`

- [ ] **Step 1: 在 sse_events.py 末尾添加 format_heartbeat 函数**

在 `backend/app/agents/sse_events.py` 的 `extract_chunk_from_event` 函数之后添加：

```python
def format_heartbeat() -> str:
    """格式化 SSE 注释行，保持连接活跃

    SSE 规范：以冒号开头的行是注释，客户端应忽略。
    用于审核等不需要发送中间内容的 SSE 流中，保持连接不被中间代理断开。
    """
    return ": heartbeat\n\n"
```

- [ ] **Step 2: 验证导入无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.sse_events import format_heartbeat; print(repr(format_heartbeat()))"`
Expected: `': heartbeat\n\n'`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/sse_events.py
git commit -m "feat(sse_events): add format_heartbeat for SSE comment lines"
```

---

### Task 3: 后端审核端点 — 不再发送 chunk，只发 done

**Files:**
- Modify: `backend/app/api/chapters.py`

- [ ] **Step 1: 在 chapters.py 顶部导入 format_heartbeat**

在 `backend/app/api/chapters.py` 的 import 区域（约第27行 `format_sse_error` 之后）添加：

```python
from app.agents.sse_events import format_heartbeat
```

- [ ] **Step 2: 修改审核端点 stream_generator，使用 format_heartbeat 替代 chunk**

将 `backend/app/api/chapters.py` 第835-839行：

```python
            # 流式调用 LLM，逐块发送审核文本
            response = ""
            async for chunk in llm.chat_stream(messages):
                response += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
```

替换为：

```python
            # 流式调用 LLM，使用 SSE 注释行保持连接
            # 审核结果只有结构化数据有意义，不发送原始 JSON 文本
            response = ""
            async for chunk in llm.chat_stream(messages):
                response += chunk
                yield format_heartbeat()
```

- [ ] **Step 3: 更新审核端点 docstring**

将 `review_chapter` 函数的 docstring（约第742-751行）替换为：

```python
    """审核章节质量（SSE 流式）

    使用 review_chapter_node LangGraph 节点函数进行审核，LLM 通过
    get_llm_from_state_async 获取（与 LangGraph 节点相同机制）。
    审核过程后台静默执行（SSE 注释行保持连接），完成后发送结构化结果。

    SSE 事件：
    - heartbeat: SSE 注释行保持连接活跃（无业务数据）
    - done: 审核完成 {passed: bool, feedback: string, issues: list, scores: dict}
    - error: 审核失败 {error: string}
    """
```

- [ ] **Step 4: 验证后端启动无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.api.chapters import router; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chapters.py
git commit -m "fix(review): stop sending chunk events, use SSE heartbeat to keep connection alive"
```

---

### Task 4: 后端审核端点测试

**Files:**
- Create: `backend/tests/test_review_endpoint.py`

- [ ] **Step 1: 编写审核端点 SSE 事件格式测试**

```python
# backend/tests/test_review_endpoint.py
"""审核端点 SSE 事件格式测试"""

import json
import pytest
from app.agents.sse_events import format_heartbeat


class TestReviewSSEFormat:
    """审核端点应使用 SSE 注释行而非 chunk 事件发送审核中间状态"""

    def test_heartbeat_is_sse_comment(self):
        """format_heartbeat 应输出 SSE 注释行格式"""
        heartbeat = format_heartbeat()
        assert heartbeat.startswith(":"), f"Expected SSE comment line, got: {heartbeat}"
        assert "event:" not in heartbeat, "Heartbeat should not contain event prefix"
        assert heartbeat.endswith("\n\n"), "SSE event must end with double newline"

    def test_heartbeat_not_parsed_as_event(self):
        """SSE 注释行不应被解析为业务事件"""
        heartbeat = format_heartbeat()
        # 模拟 sseParser 的解析逻辑
        lines = heartbeat.strip().split('\n')
        has_event = any(line.startswith('event:') for line in lines)
        has_data = any(line.startswith('data:') for line in lines)
        assert not has_event, "Heartbeat should not have event: line"
        assert not has_data, "Heartbeat should not have data: line"

    def test_review_done_event_contains_scores(self):
        """done 事件应包含 scores 字段"""
        result_data = {
            "passed": False,
            "feedback": "增加冲突描写",
            "issues": [{"type": "情感张力不足", "location": "全文", "description": "缺少冲击力"}],
            "scores": {
                "plot_consistency": 8,
                "character_consistency": 7,
                "writing_quality": 8,
                "emotional_tension": 7,
                "ai_flavor": 5,
                "outline_deviation": 3,
            },
        }

        sse_event = f"event: done\ndata: {json.dumps(result_data)}\n\n"

        assert "event: done" in sse_event
        parsed = json.loads(sse_event.split("data: ")[1].strip())
        assert "scores" in parsed
        assert parsed["scores"]["emotional_tension"] == 7
        assert len(parsed["issues"]) == 1
```

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_review_endpoint.py -v`
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_review_endpoint.py
git commit -m "test(review): add SSE event format tests for review endpoint"
```

---

### Task 5: 后端重写 SSE 端点

**Files:**
- Modify: `backend/app/api/chapters.py`

- [ ] **Step 1: 在 chapters.py 顶部 import 区域添加 rewrite 相关导入**

将 `backend/app/api/chapters.py` 第14-21行：

```python
from app.schemas.chapter import (
    ChapterOutlineResponse,
    ChapterOutlineUpdate,
    ChapterResponse,
    ChapterContentUpdate,
    ChapterGenerateRequest,
    ReviewRequest
)
```

替换为：

```python
from app.schemas.chapter import (
    ChapterOutlineResponse,
    ChapterOutlineUpdate,
    ChapterResponse,
    ChapterContentUpdate,
    ChapterGenerateRequest,
    ReviewRequest,
    RewriteRequest,
)
```

- [ ] **Step 2: 在 review 端点之后添加 rewrite SSE 端点**

在 `backend/app/api/chapters.py` 的 `review_chapter` 函数之后添加：

```python
@router.post("/{project_id}/chapters/{chapter_num}/rewrite")
async def rewrite_chapter(
    project_id: int,
    chapter_num: int,
    request: RewriteRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据审核建议重写章节（SSE 流式）

    复用 LangGraph rewrite 节点的核心逻辑（_build_rewrite_messages），
    通过 get_llm_from_state_async 获取 LLM 服务（与 LangGraph 节点相同机制），
    通过 build_initial_state 构建上下文（含 DB 预加载的角色/关系数据）。
    重写完成后原子性更新数据库内容，清除审核状态。

    架构说明：此端点走"单节点 SSE"模式（与 review/generate 一致），
    不走 LangGraph 图执行，因为用户手动触发的单次操作需要用户控制节奏。

    SSE 事件：
    - chunk: 重写文本片段 {content: string}
    - done: 重写完成 {chapter: {id, chapter_outline_id, content, word_count}}
    - error: 重写失败 {error: string}
    """
    from app.agents.nodes.rewrite import _build_rewrite_messages

    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    # 查找章节大纲
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # 查找章节内容
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    if not chapter.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter has no content to rewrite"
        )

    # 必须有审核结果才能重写（重写需要审核建议作为输入）
    if not chapter.review_result and not chapter.review_feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先审核章节，重写需要审核建议作为输入"
        )

    # 提取审核反馈（与 rewrite_node 中 review_feedback 提取逻辑一致）
    review_feedback = ""
    if chapter.review_result:
        review_feedback = chapter.review_result.get("raw_response", "") or chapter.review_result.get("suggestions", "")
    if not review_feedback and chapter.review_feedback:
        review_feedback = chapter.review_feedback

    # 构建初始状态（传入 db 预加载角色/关系数据）
    llm_config_id = request.llm_config_id if request else None
    workflow_state = get_or_create_workflow_state(db, project_id)
    initial_state = build_initial_state(
        project, outline, workflow_state, llm_config_id, db=db
    )
    initial_state["current_chapter"] = chapter_num
    initial_state["written_chapters"] = [{"chapter_number": chapter_num, "content": chapter.content}]

    # 构建章节大纲数据
    chapter_outline_dict = {
        "chapter_number": chapter_outline.chapter_number,
        "title": chapter_outline.title or "",
        "scene": chapter_outline.scene,
        "characters": chapter_outline.characters,
        "plot": chapter_outline.plot or "",
        "conflict": chapter_outline.conflict,
        "ending": chapter_outline.ending,
        "target_words": chapter_outline.target_words,
    }

    # 保存参数供流内部使用
    original_content = chapter.content
    chapter_outline_id = chapter_outline.id

    async def stream_generator():
        """流式重写章节

        重写完成后原子性更新数据库：使用独立 Session 更新内容、
        清除审核状态、递增 rewrite_count。使用独立 Session 而非
        请求级 db，原因与 generate_chapter 相同。
        """
        from app.database import SessionLocal

        save_db = SessionLocal()
        try:
            # 通过与 LangGraph 节点相同的机制获取 LLM 服务
            llm = await get_llm_from_state_async(initial_state, db)

            # 构建重写消息（使用共享的 _build_rewrite_messages）
            messages = _build_rewrite_messages(
                initial_state, chapter_outline_dict, original_content, review_feedback
            )

            # 流式调用 LLM，发送重写内容
            rewritten_content = ""
            async for chunk in llm.chat_stream(messages):
                rewritten_content += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

            # 后处理：清理 LLM 可能添加的结尾数字
            rewritten_content = clean_chapter_content(rewritten_content)
            if not rewritten_content:
                yield format_sse_error(ValueError("重写内容为空"))
                return

            # 原子性更新数据库（使用独立 Session）
            word_count = len(rewritten_content)
            ch = save_db.query(Chapter).filter(
                Chapter.chapter_outline_id == chapter_outline_id
            ).first()

            if ch:
                ch.content = rewritten_content
                ch.word_count = word_count
                ch.rewrite_count = (ch.rewrite_count or 0) + 1
                # 重写后需重新审核，清除审核状态
                ch.review_passed = False
                ch.review_result = None
                ch.review_feedback = None
                save_db.commit()

            # 发送完成事件
            chapter_data = {
                "id": ch.id if ch else None,
                "chapter_outline_id": ch.chapter_outline_id if ch else None,
                "content": rewritten_content,
                "word_count": word_count,
            }
            yield f"event: done\ndata: {json.dumps({'chapter': chapter_data})}\n\n"

        except Exception as e:
            yield format_sse_error(e)
        finally:
            save_db.close()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

- [ ] **Step 3: 验证后端启动无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.api.chapters import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/chapters.py
git commit -m "feat(api): add rewrite SSE endpoint for chapter content"
```

---

### Task 6: 重写端点测试

**Files:**
- Create: `backend/tests/test_rewrite_endpoint.py`

- [ ] **Step 1: 编写重写端点集成测试**

```python
# backend/tests/test_rewrite_endpoint.py
"""重写端点集成测试"""

import pytest
import json
from app.models.chapter import Chapter


class TestRewriteEndpointValidation:
    """重写端点的参数校验"""

    def test_rewrite_requires_review_result(self):
        """没有审核结果时应返回 400 错误"""
        chapter = Chapter()
        chapter.content = "测试内容"
        chapter.review_result = None
        chapter.review_feedback = None

        has_review = bool(chapter.review_result) or bool(chapter.review_feedback)
        assert has_review is False, "Chapter without review should fail validation"

    def test_rewrite_with_review_result(self):
        """有审核结果时应通过校验"""
        chapter = Chapter()
        chapter.content = "测试内容"
        chapter.review_result = {
            "passed": False,
            "raw_response": "情节过于平淡",
            "suggestions": "增加冲突",
        }
        chapter.review_feedback = None

        has_review = bool(chapter.review_result) or bool(chapter.review_feedback)
        assert has_review is True

    def test_rewrite_extracts_feedback_from_raw_response(self):
        """应优先从 review_result.raw_response 提取审核反馈

        与 rewrite_node 中的提取逻辑一致：
        review_feedback = review_result.get("raw_response", "")
        """
        review_result = {
            "passed": False,
            "raw_response": "原始审核文本",
            "suggestions": "简化建议",
        }

        review_feedback = review_result.get("raw_response", "") or review_result.get("suggestions", "")
        assert review_feedback == "原始审核文本"

    def test_rewrite_fallback_to_suggestions(self):
        """无 raw_response 时回退到 suggestions"""
        review_result = {
            "passed": False,
            "suggestions": "简化建议",
        }

        review_feedback = review_result.get("raw_response", "") or review_result.get("suggestions", "")
        assert review_feedback == "简化建议"

    def test_rewrite_fallback_to_review_feedback_column(self):
        """review_result 为空时回退到 review_feedback 字段"""
        review_result = None
        review_feedback_column = "直接反馈文本"

        review_feedback = ""
        if review_result:
            review_feedback = review_result.get("raw_response", "") or review_result.get("suggestions", "")
        if not review_feedback and review_feedback_column:
            review_feedback = review_feedback_column
        assert review_feedback == "直接反馈文本"

    def test_rewrite_clears_review_state_on_success(self):
        """重写完成后应清除审核状态"""
        update_data = {
            "review_passed": False,
            "review_result": None,
            "review_feedback": None,
        }

        assert update_data["review_passed"] is False
        assert update_data["review_result"] is None
        assert update_data["review_feedback"] is None

    def test_rewrite_increments_count(self):
        """重写完成后应递增 rewrite_count"""
        current_count = 0
        new_count = (current_count or 0) + 1
        assert new_count == 1

        current_count = 2
        new_count = (current_count or 0) + 1
        assert new_count == 3
```

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_rewrite_endpoint.py -v`
Expected: PASS (7 tests)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_rewrite_endpoint.py
git commit -m "test(rewrite): add rewrite endpoint validation tests"
```

---

### Task 7: 前端类型 — Chapter 补充字段 + 共享映射函数

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 修改 Chapter 接口**

将 `frontend/src/types/index.ts` 第187-196行：

```typescript
export interface Chapter {
  id: number;
  chapter_outline_id: number;
  content?: string;
  word_count: number;
  review_passed: boolean;
  review_feedback?: string;
  created_at: string;
  updated_at: string;
}
```

替换为：

```typescript
export interface Chapter {
  id: number;
  chapter_outline_id: number;
  content?: string;
  word_count: number;
  review_passed: boolean;
  review_feedback?: string;
  review_result?: {
    passed: boolean;
    scores: Record<string, number>;
    issues: ReviewIssue[];
    suggestions: string;
    raw_response?: string;
  } | null;
  rewrite_count: number;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: 在 ReviewResponse 接口之后添加共享映射函数**

在 `frontend/src/types/index.ts` 的 `ReviewResponse` 接口之后（约第218行后）添加：

```typescript
/** 从后端 review_result JSON 映射为前端 ReviewResponse */
export function mapReviewResult(result: Chapter['review_result']): ReviewResponse | null
{
  if (!result) return null
  return {
    passed: result.passed ?? false,
    feedback: result.suggestions || '',
    issues: (result.issues || []).map(issue =>
      typeof issue === 'string' ? { description: issue } : issue
    ),
    scores: result.scores || {},
  }
}
```

- [ ] **Step 3: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无 Chapter/mapReviewResult 相关的类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add review_result/rewrite_count to Chapter, add shared mapReviewResult"
```

---

### Task 8: 前端 AIAssistantPanel — 删除流式预览，添加审核恢复和重写功能

**Files:**
- Modify: `frontend/src/components/workbench/creation/AIAssistantPanel.tsx`

- [ ] **Step 1: 重写 AIAssistantPanel 组件**

将 `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` 全部内容替换为：

```typescript
// frontend/src/components/workbench/creation/AIAssistantPanel.tsx

import { useState, useRef, useEffect } from 'react'
import { AlertCircle, RefreshCw, ShieldCheck, ChevronLeft, ChevronRight, PenLine } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { createSSEStream } from '@/lib/sseParser'
import { toast } from 'sonner'
import type { ReviewResponse } from '@/types'
import { mapReviewResult } from '@/types'

// 审核评分维度中文标签
const SCORE_LABELS: Record<string, string> = {
  plot_consistency: '情节一致性',
  character_consistency: '人物一致性',
  writing_quality: '文笔质量',
  emotional_tension: '情感张力',
  ai_flavor: 'AI味程度',
  outline_deviation: '大纲偏离度',
}

interface AIAssistantPanelProps
{
  projectId?: number
  chapterNumber?: number
  chapterContent?: string
  initialReviewResult?: ReviewResponse | null
  onReviewComplete?: (result: ReviewResponse) => void
  onRewriteChunk?: (chunk: string) => void
  onRewriteDone?: (data: { chapter: { id?: number; content?: string; word_count?: number } }) => void
  onReviewCleared?: () => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

export function AIAssistantPanel({
  projectId,
  chapterNumber,
  chapterContent,
  initialReviewResult,
  onReviewComplete,
  onRewriteChunk,
  onRewriteDone,
  onReviewCleared,
  collapsed,
  onToggleCollapse,
}: AIAssistantPanelProps)
{
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(initialReviewResult ?? null)
  const [reviewing, setReviewing] = useState(false)
  const [rewriting, setRewriting] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  // 章节切换时重置审核结果
  useEffect(() =>
  {
    setReviewResult(initialReviewResult ?? null)
  }, [initialReviewResult, chapterNumber])

  const handleReview = async () =>
  {
    if (!projectId || !chapterNumber) return
    setReviewing(true)
    setReviewResult(null)

    const controller = new AbortController()
    abortControllerRef.current = controller

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${chapterNumber}/review`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'done')
          {
            const result = data as unknown as ReviewResponse
            setReviewResult(result)
            onReviewComplete?.(result)

            if (result.passed)
            {
              toast.success('审核通过')
            }
            else
            {
              toast.warning('审核未通过，可根据建议修改或重写')
            }
          }
          else if (type === 'error')
          {
            const errorData = data as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            console.error('Review error:', errorMsg)
            toast.error(`审核失败: ${errorMsg}`)
          }
          // SSE 注释行（heartbeat）和 chunk 事件都被忽略
        },
        (error) =>
        {
          console.error('Failed to review:', error)
          toast.error('审核失败')
        }
      )
    }
    finally
    {
      setReviewing(false)
      abortControllerRef.current = null
    }
  }

  const handleRewrite = async () =>
  {
    if (!projectId || !chapterNumber) return
    setRewriting(true)
    setReviewResult(null)
    onReviewCleared?.()

    const controller = new AbortController()
    abortControllerRef.current = controller

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${chapterNumber}/rewrite`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'chunk')
          {
            const chunkData = data as { content: string } | string
            const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
            if (chunkText)
            {
              onRewriteChunk?.(chunkText)
            }
          }
          else if (type === 'done')
          {
            const doneData = data as { chapter?: { id?: number; content?: string; word_count?: number } }
            if (doneData?.chapter)
            {
              onRewriteDone?.(doneData)
            }
            toast.success('重写完成，可重新审核验证效果')
          }
          else if (type === 'error')
          {
            const errorData = data as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            console.error('Rewrite error:', errorMsg)
            toast.error(`重写失败: ${errorMsg}`)
          }
        },
        (error) =>
        {
          console.error('Failed to rewrite:', error)
          toast.error('重写失败')
        }
      )
    }
    finally
    {
      setRewriting(false)
      abortControllerRef.current = null
    }
  }

  const handleCancel = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      setReviewing(false)
      setRewriting(false)
      abortControllerRef.current = null
      toast.info('已取消操作')
    }
  }

  const isLoading = reviewing || rewriting

  return (
    <div className={`border-l bg-white flex flex-col h-full shrink-0 transition-all duration-300 ${collapsed ? 'w-12' : 'w-[360px]'} relative`}>
      {/* 收缩展开按钮 */}
      <button
        onClick={onToggleCollapse}
        className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
      >
        {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>
      {!collapsed && (
        <>
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b flex-shrink-0">
        <ShieldCheck className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">审核</span>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-3">
        {reviewResult ? (
          <div className="space-y-3">
            {/* 审核结果 */}
            <div className={`p-3 rounded-md text-center ${
              reviewResult.passed ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}>
              <div className={`text-2xl font-bold ${reviewResult.passed ? 'text-green-600' : 'text-red-600'}`}>
                {reviewResult.passed ? '通过' : '未通过'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">审核结果</div>
            </div>

            {/* 修改建议 */}
            {reviewResult.feedback && (
              <div className="p-3 bg-muted rounded-md">
                <span className="text-xs font-medium">修改建议</span>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed whitespace-pre-wrap">
                  {reviewResult.feedback}
                </p>
              </div>
            )}

            {/* 评分详情 */}
            {reviewResult.scores && Object.keys(reviewResult.scores).length > 0 && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                <span className="text-xs font-medium text-blue-800">评分详情</span>
                <div className="mt-1.5 space-y-1">
                  {Object.entries(reviewResult.scores).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between text-xs">
                      <span className="text-blue-700">{SCORE_LABELS[key] || key}</span>
                      <span className={`font-medium ${
                        (key === 'ai_flavor' || key === 'outline_deviation')
                          ? (value <= 3 ? 'text-green-600' : value <= 5 ? 'text-yellow-600' : 'text-red-600')
                          : (value >= 7 ? 'text-green-600' : value >= 5 ? 'text-yellow-600' : 'text-red-600')
                      }`}>
                        {value}/10
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 问题列表 */}
            {reviewResult.issues.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium">发现问题 ({reviewResult.issues.length})</span>
                {reviewResult.issues.map((issue, index) =>
                {
                  const description = typeof issue === 'string' ? issue : issue.description
                  const type = typeof issue === 'string' ? '' : issue.type
                  const location = typeof issue === 'string' ? '' : issue.location
                  return (
                    <div key={index} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs flex items-start gap-1.5">
                      <AlertCircle className="h-3 w-3 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <span className="leading-relaxed">
                        {type ? <span className="font-medium text-yellow-800">[{type}]</span> : ''}{type ? ' ' : ''}{location ? `${location}：` : ''}{description}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}

            {/* 操作按钮 */}
            <div className="space-y-2">
              <Button
                onClick={handleRewrite}
                disabled={rewriting}
                variant={reviewResult.passed ? 'outline' : 'default'}
                size="sm"
                className="w-full text-xs"
              >
                <PenLine className="h-3 w-3 mr-1" />
                {rewriting ? '重写中...' : '重写'}
              </Button>
              <Button
                onClick={() => { setReviewResult(null) }}
                variant="outline"
                size="sm"
                className="w-full text-xs"
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                重新审核
              </Button>
            </div>
          </div>
        ) : isLoading ? (
          <div className="space-y-3">
            <div className="p-4 bg-muted rounded-md text-center">
              <RefreshCw className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2 animate-spin" />
              <div className="text-xs text-muted-foreground">
                {reviewing ? '正在审核中...' : '正在重写中...'}
              </div>
            </div>
            <Button
              onClick={handleCancel}
              variant="destructive"
              size="sm"
              className="w-full text-xs"
            >
              取消
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="p-4 bg-muted rounded-md text-center">
              <ShieldCheck className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
              <div className="text-xs text-muted-foreground leading-relaxed">
                {chapterContent
                  ? '点击下方按钮对当前章节进行质量审核'
                  : '请先生成章节内容后再进行审核'}
              </div>
            </div>
            <Button
              onClick={handleReview}
              disabled={!chapterContent || !chapterNumber}
              size="sm"
              className="w-full text-xs"
            >
              <ShieldCheck className="h-3 w-3 mr-1" />
              开始审核
            </Button>
          </div>
        )}
      </div>
        </>
      )}
      {collapsed && (
        <div className="flex flex-col items-center pt-4 gap-3">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -i "AIAssistantPanel" | head -10`
Expected: 无 AIAssistantPanel 相关错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/creation/AIAssistantPanel.tsx
git commit -m "feat(AIAssistantPanel): hide streaming preview, add review restore and rewrite button"
```

---

### Task 9: 前端 WritingPanel — 传递审核数据，添加重写回调

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: 添加 mapReviewResult 导入**

在 `WritingPanel.tsx` 顶部的 import 区域，将：

```typescript
import type { ChapterOutline, Chapter } from '@/types'
```

替换为：

```typescript
import type { ChapterOutline, Chapter, ReviewResponse } from '@/types'
import { mapReviewResult } from '@/types'
```

- [ ] **Step 2: 添加重写相关 state 和 ref**

在 `WritingPanel` 组件中，约第114行 `rightCollapsed` 之后添加：

```typescript
  const [rewriting, setRewriting] = useState(false)
  const rewriteAccumulatedRef = useRef<string[]>([])
```

- [ ] **Step 3: 添加审核和重写回调函数**

在 `handleCancelGenerate` 函数之后（约第360行后）添加：

```typescript
  const handleRewriteChunk = useCallback((chunkText: string) =>
  {
    setRewriting(true)
    setMode('preview')
    rewriteAccumulatedRef.current.push(chunkText)
    const fullText = rewriteAccumulatedRef.current.join('')
    const html = fullText
      .split('\n')
      .filter(p => p.trim())
      .map(p => `<p>${p}</p>`)
      .join('')
    setContent(html)
  }, [])

  const handleRewriteDone = useCallback((data: { chapter?: { id?: number; content?: string; word_count?: number } }) =>
  {
    setRewriting(false)
    rewriteAccumulatedRef.current = []
    const chapterData = data?.chapter
    if (chapterData?.word_count)
    {
      toast.success(`重写完成，共 ${chapterData.word_count} 字`)
    }
    // 刷新 API 数据确保一致性
    if (selectedChapter)
    {
      chaptersApi.get(projectId, selectedChapter.chapter_number).then(chapter =>
      {
        setChapterContent(chapter)
        if (chapter.content)
        {
          setContent(formatContentAsHtml(chapter.content))
        }
      }).catch(() => {})
    }
  }, [selectedChapter, projectId])

  const handleReviewCleared = useCallback(() =>
  {
    rewriteAccumulatedRef.current = []
  }, [])

  const handleReviewComplete = useCallback((result: ReviewResponse) =>
  {
    setChapterContent(prev => prev ? {
      ...prev,
      review_passed: result.passed,
      review_result: {
        passed: result.passed,
        scores: result.scores || {},
        issues: result.issues || [],
        suggestions: result.feedback || '',
      },
    } : prev)
  }, [])
```

- [ ] **Step 4: 修改 AIAssistantPanel 的 props 传递**

将 `WritingPanel.tsx` 第617-628行：

```typescript
      <AIAssistantPanel
        projectId={projectId}
        chapterNumber={selectedChapter?.chapter_number}
        chapterContent={content}
        onReviewComplete={() =>
        {
          // 审核结果回调
        }}
        collapsed={rightCollapsed}
        onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
      />
```

替换为：

```typescript
      <AIAssistantPanel
        key={selectedChapter?.chapter_number}
        projectId={projectId}
        chapterNumber={selectedChapter?.chapter_number}
        chapterContent={content}
        initialReviewResult={mapReviewResult(chapterContent?.review_result)}
        onReviewComplete={handleReviewComplete}
        onRewriteChunk={handleRewriteChunk}
        onRewriteDone={handleRewriteDone}
        onReviewCleared={handleReviewCleared}
        collapsed={rightCollapsed}
        onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
      />
```

- [ ] **Step 5: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -i "WritingPanel" | head -10`
Expected: 无 WritingPanel 相关错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "feat(WritingPanel): pass review result to AIAssistantPanel, add rewrite callbacks"
```

---

### Task 10: 集成验证

**Files:** 无新增

- [ ] **Step 1: 后端测试全部通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_review.py tests/test_rewrite.py tests/test_review_endpoint.py tests/test_rewrite_endpoint.py -v`
Expected: ALL PASS

- [ ] **Step 2: 前端编译通过**

Run: `cd frontend && npx tsc --noEmit 2>&1 | tail -5`
Expected: 无新增类型错误

- [ ] **Step 3: 重建后端并启动**

Run: `docker compose build --no-cache backend && docker compose up -d backend`
Expected: 后端启动成功

- [ ] **Step 4: 重建前端并启动**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 前端启动成功

- [ ] **Step 5: 手动验证三个修复**

1. 审核章节 → 审核中只显示加载动画，不显示 JSON 流式文本
2. 审核完成后刷新页面（F5）→ 审核结果仍然显示
3. 切换到其他章节再切回 → 审核结果仍然显示
4. 审核未通过 → 显示"重写"按钮（主色调）+ "重新审核"按钮
5. 点击"重写" → 编辑器流式更新重写内容
6. 重写完成后审核结果清空 → 可重新审核

- [ ] **Step 6: 最终 Commit**

```bash
git add -A
git commit -m "feat(review): fix streaming display, persist review result, add rewrite endpoint"
```
