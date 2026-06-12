# 写作前置校验与面板优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Agent 写作前置条件校验（关键项缺失阻断）+ 写作页面 UI 优化（底部状态栏 + 自动保存）

**Architecture:** 后端在 `agent_context.py` 新增校验函数，结果注入 `context["prerequisites"]`；前端修改 `WritingPanel.tsx` 实现底部状态栏和自动保存。

**Tech Stack:** FastAPI (后端), React + Zustand (前端), shadcn/ui

---

## 文件结构

### 后端改动
- `backend/app/agents/agent_context.py` - 新增 `validate_prerequisites()` 函数
- `backend/app/agents/prompts.py` - 修改 `AGENT_SYSTEM_PROMPT` 模板
- `backend/app/api/agent.py` - 修改 `agent_chat` 注入引导文字
- `backend/app/api/knowledge_status.py` - 新增 KB 状态 API
- `backend/app/main.py` - 注册新路由

### 前端改动
- `frontend/src/components/workbench/creation/WritingPanel.tsx` - 移除冗余按钮 + 添加自动保存 + 底部状态栏
- `frontend/src/lib/api.ts` - 新增 `knowledgeStatusApi`

---

## 实施任务

### Task 1: 后端 - 实现前置条件校验函数

**Files:**
- Modify: `backend/app/agents/agent_context.py`

- [ ] **Step 1: 在 `_load_writing_context` 函数末尾添加校验调用**

在 `_load_writing_context` 函数末尾（`recent_decisions` 和 `relation_evolution_cues` 之后）添加：

```python
# 前置条件校验
prereq = validate_prerequisites(kb.project_id, current_chapter_number)
context["prerequisites"] = prereq
```

- [ ] **Step 2: 在文件末尾添加 `validate_prerequisites` 函数**

在 `agent_context.py` 文件末尾添加。关键设计：每个检查项独立 try-except，单项失败不影响整体。

```python
def validate_prerequisites(project_id: int, current_chapter: int | None) -> dict:
    """校验写作前置条件，返回 blocked 和 warnings 列表
    
    每个检查项独立 try-except，单项查询失败不影响其他检查项。
    失败的检查项记入 errors 列表（区别于 blocked/warnings）。
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.models.character import Character, EvolutionPlan
    from app.models.world_setting import WorldSetting
    from app.models.foreshadowing import Foreshadowing
    from app.models.style_constraints import StyleConstraints
    from app.models.plot_structure import PlotBlock
    from app.models.chapter import Chapter
    from app.models.timeline import TimelineEntry
    
    db = SessionLocal()
    blocked = []
    warnings = []
    errors = []  # 查询异常记录
    
    try:
        # === 关键项检查 ===
        
        # 1. 章节大纲记录存在 + 已确认
        if current_chapter:
            try:
                co = db.query(ChapterOutline).filter(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == current_chapter,
                ).first()
                if not co:
                    blocked.append({
                        "type": "chapter_outline_missing",
                        "chapter": current_chapter,
                        "message": f"第{current_chapter}章大纲不存在",
                        "severity": "error"
                    })
                elif not co.confirmed:
                    blocked.append({
                        "type": "outline_unconfirmed",
                        "chapter": current_chapter,
                        "message": f"第{current_chapter}章大纲尚未确认",
                        "severity": "error"
                    })
            except Exception as e:
                errors.append({"type": "chapter_outline_check", "message": str(e)})
        
        # 2. 角色存在
        try:
            char_count = db.query(Character).filter(Character.project_id == project_id).count()
            if char_count == 0:
                blocked.append({
                    "type": "character_missing",
                    "message": "项目中没有任何角色",
                    "severity": "error"
                })
        except Exception as e:
            errors.append({"type": "character_check", "message": str(e)})
        
        # 3. 世界观存在（core_concept 非空）
        try:
            ws = db.query(WorldSetting).filter(WorldSetting.project_id == project_id).first()
            if not ws or not ws.core_concept:
                blocked.append({
                    "type": "world_setting_missing",
                    "message": "项目世界观尚未完善",
                    "severity": "error"
                })
        except Exception as e:
            errors.append({"type": "world_setting_check", "message": str(e)})
        
        # === 次要项检查 ===
        
        # 4. 伏笔记录
        try:
            fs_count = db.query(Foreshadowing).filter(Foreshadowing.project_id == project_id).count()
            if fs_count == 0:
                warnings.append({
                    "type": "foreshadowing_empty",
                    "message": "当前无伏笔记录",
                    "severity": "warning"
                })
        except Exception as e:
            errors.append({"type": "foreshadowing_check", "message": str(e)})
        
        # 5. 风格约束（只要记录存在即可）
        try:
            style = db.query(StyleConstraints).filter(StyleConstraints.project_id == project_id).first()
            if not style:
                warnings.append({
                    "type": "style_constraints_missing",
                    "message": "尚未设置风格约束",
                    "severity": "warning"
                })
        except Exception as e:
            errors.append({"type": "style_check", "message": str(e)})
        
        # 6. 情节块
        try:
            block_count = db.query(PlotBlock).filter(PlotBlock.project_id == project_id).count()
            if block_count == 0:
                warnings.append({
                    "type": "plot_block_empty",
                    "message": "尚未创建情节块",
                    "severity": "warning"
                })
        except Exception as e:
            errors.append({"type": "plot_block_check", "message": str(e)})
        
        # 7. 上一章结尾内容
        if current_chapter and current_chapter > 1:
            try:
                prev_co = db.query(ChapterOutline).filter(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == current_chapter - 1,
                ).first()
                if prev_co:
                    prev_ch = db.query(Chapter).filter(
                        Chapter.chapter_outline_id == prev_co.id
                    ).first()
                    if not prev_ch or not prev_ch.content:
                        warnings.append({
                            "type": "previous_chapter_empty",
                            "chapter": current_chapter - 1,
                            "message": f"第{current_chapter - 1}章尚无正文",
                            "severity": "warning"
                        })
            except Exception as e:
                errors.append({"type": "previous_chapter_check", "message": str(e)})
        
        # 8. 关系演变规划
        try:
            plan_count = db.query(EvolutionPlan).filter(
                EvolutionPlan.relation.has(Relation.project_id == project_id)
            ).count()
            if plan_count == 0:
                warnings.append({
                    "type": "relation_evolution_empty",
                    "message": "尚未创建关系演变规划",
                    "severity": "warning"
                })
        except Exception as e:
            errors.append({"type": "evolution_check", "message": str(e)})
        
        # 9. 时间线记录
        try:
            timeline_count = db.query(TimelineEntry).filter(
                TimelineEntry.project_id == project_id
            ).count()
            if timeline_count == 0:
                warnings.append({
                    "type": "timeline_empty",
                    "message": "尚未创建时间线记录",
                    "severity": "warning"
                })
        except Exception as e:
            errors.append({"type": "timeline_check", "message": str(e)})
        
    finally:
        db.close()
    
    result = {
        "blocked": blocked,
        "warnings": warnings,
        "validated": True
    }
    if errors:
        result["errors"] = errors
    return result
```

- [ ] **Step 3: 验证函数可导入**

Run: `cd /Users/biner/Dev/novelagent && docker compose exec backend python -c "from app.agents.agent_context import validate_prerequisites; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/agent_context.py
git commit -m "feat(agent): add validate_prerequisites for writing prerequisites check"
```

---

### Task 2: 后端 - 修改 Agent System Prompt

**Files:**
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: 查看 AGENT_SYSTEM_PROMPT 模板完整内容**

Run: `rg -n "AGENT_SYSTEM_PROMPT" backend/app/agents/prompts.py -A 80 | head -100`

- [ ] **Step 2: 在模板中添加 `context_prerequisites_warning` 占位符**

在 `AGENT_SYSTEM_PROMPT` 模板中找到 `## 当前阶段信息` 段落（或 `{context_block}` 之后），在其后添加：

```
## 前置条件检测结果
{context_prerequisites_warning}

当 prerequisites.blocked 非空且用户请求生成/重写/续写章节时，你应当：
1. 向用户列出所有 blocked 缺失项（用中文）
2. 说明每项缺失对写作质量的影响
3. 引导用户通过对应工具补全后再试
4. 除非用户明确要求，否则不要尝试绕过缺失项生成内容

当仅有 warnings 时，你可以继续执行，但在正文结尾添加一条写作建议（用中文）。
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/prompts.py
git commit -m "feat(agent): add prerequisites warning placeholder to system prompt"
```

---

### Task 3: 后端 - 注入引导变量

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 找到 `agent_chat` 中 context_block 构造位置**

在 `agent_chat` 函数中，找到 `context = build_agent_context(...)` 调用之后的代码段。

- [ ] **Step 2: 在 `context_block` 构造之前添加 `context_prerequisites_warning` 变量**

在 `context_block = json.dumps(context, ...)` 之前添加：

```python
# 构建前置条件警告文字
prereq = context.get("prerequisites", {})
if prereq.get("blocked"):
    blocked_items = "\n".join([f"- {item['message']}" for item in prereq["blocked"]])
    context_prerequisites_warning = f"""⚠️ 当前无法生成正文，存在以下阻断问题：

{blocked_items}

请先在知识库中补全以上内容。"""
elif prereq.get("warnings"):
    warning_items = "\n".join([f"- {item['message']}" for item in prereq["warnings"]])
    context_prerequisites_warning = f"""📝 当前存在以下次要项缺失（不影响生成）：

{warning_items}

你可以在写作时留意这些方面。"""
else:
    context_prerequisites_warning = ""
```

- [ ] **Step 3: 在两个 format 调用中都注入变量**

找到第一个 format 调用（正常分支）：

```python
system_content = AGENT_SYSTEM_PROMPT.format(
    phase_label=phase_label,
    project_name=project.name,
    context_block=context_block,
)
```

改为：

```python
system_content = AGENT_SYSTEM_PROMPT.format(
    phase_label=phase_label,
    project_name=project.name,
    context_block=context_block,
    context_prerequisites_warning=context_prerequisites_warning,
)
```

找到第二个 format 调用（压缩分支，`history_budget <= 0` 内部）：

```python
system_content = AGENT_SYSTEM_PROMPT.format(
    phase_label=phase_label,
    project_name=project.name,
    context_block=slim_block,
)
```

同样改为：

```python
system_content = AGENT_SYSTEM_PROMPT.format(
    phase_label=phase_label,
    project_name=project.name,
    context_block=slim_block,
    context_prerequisites_warning=context_prerequisites_warning,
)
```

- [ ] **Step 4: 重启后端服务**

Run: `docker compose restart backend`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "feat(agent): inject prerequisites warning into system prompt"
```

---

### Task 4: 后端 - 新增 KB 状态 API

**Files:**
- Create: `backend/app/api/knowledge_status.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 knowledge_status.py API**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.utils.project import get_project_for_user
from app.agents.agent_context import validate_prerequisites

router = APIRouter()

@router.get("/{project_id}/knowledge-status")
async def get_knowledge_status(
    project_id: int,
    current_chapter: int | None = Query(None, description="当前章节号"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目知识库完整性状态"""
    get_project_for_user(project_id, current_user.id, db)
    
    result = validate_prerequisites(project_id, current_chapter)
    return result
```

- [ ] **Step 2: 在 main.py 注册路由**

在 `backend/app/main.py` 的路由注册部分添加：

```python
from app.api import knowledge_status

router.include_router(knowledge_status.router, prefix="/api", tags=["knowledge"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/knowledge_status.py backend/app/main.py
git commit -m "feat(api): add knowledge status endpoint"
```

---

### Task 5: 前端 - 添加 knowledgeStatusApi

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 在 api.ts 末尾添加 knowledgeStatusApi**

```typescript
// ==================== Knowledge Status API ====================

export const knowledgeStatusApi = {
  async get(projectId: number, currentChapter?: number): Promise<{
    blocked: { type: string; chapter?: number; message: string; severity: string }[];
    warnings: { type: string; message: string; severity: string }[];
    validated: boolean;
  }> {
    const params = new URLSearchParams();
    if (currentChapter !== undefined) {
      params.set("current_chapter", String(currentChapter));
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/api/${projectId}/knowledge-status${query}`);
  },
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(api): add knowledgeStatusApi to frontend"
```

---

### Task 6: 前端 - 实现底部状态栏 + 知识库状态展示 + 移除冗余按钮 + 自动保存

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

此 Task 合并前端所有改动，避免同一文件多次修改造成冲突。

- [ ] **Step 1: 添加新状态和 import**

在现有 import 之后添加：

```typescript
import { knowledgeStatusApi } from '@/lib/api'
```

在组件内添加状态：

```typescript
const [kbStatus, setKbStatus] = useState<{
  blocked: { type: string; message: string }[];
  warnings: { type: string; message: string }[];
}>({ blocked: [], warnings: [] });

type SaveStatus = 'saved' | 'saving' | 'error';

const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved');
const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
const contentRef = useRef<string>(content);  // 保持最新 content 引用
```

- [ ] **Step 2: 添加 KB 状态加载逻辑**

```typescript
useEffect(() => {
  const fetchKbStatus = async () => {
    try {
      const data = await knowledgeStatusApi.get(projectId, selectedChapter?.chapter_number);
      setKbStatus({ blocked: data.blocked || [], warnings: data.warnings || [] });
    } catch (e) {
      console.error('Failed to fetch KB status:', e);
    }
  };
  fetchKbStatus();
}, [projectId, selectedChapter?.chapter_number]);
```

- [ ] **Step 3: 添加自动保存逻辑**

```typescript
// 保持 contentRef 与 content 同步
useEffect(() => {
  contentRef.current = content;
}, [content]);

// 手动保存（重试时调用）
const handleManualSave = useCallback(async () => {
  if (!selectedChapter) return;
  setSaveStatus('saving');
  try {
    await chaptersApi.update(projectId, selectedChapter.chapter_number, { content: contentRef.current });
    setSaveStatus('saved');
  } catch (e) {
    console.error('Manual save failed:', e);
    setSaveStatus('error');
  }
}, [projectId, selectedChapter]);

// 防抖自动保存
const handleContentChange = useCallback((newContent: string) => {
  setContent(newContent);
  contentRef.current = newContent;
  
  if (saveTimeoutRef.current) {
    clearTimeout(saveTimeoutRef.current);
  }
  
  saveTimeoutRef.current = setTimeout(async () => {
    if (!selectedChapter) return;
    setSaveStatus('saving');
    try {
      await chaptersApi.update(projectId, selectedChapter.chapter_number, { content: newContent });
      setSaveStatus('saved');
    } catch (e) {
      console.error('Auto-save failed:', e);
      setSaveStatus('error');
    }
  }, 2000);
}, [projectId, selectedChapter]);
```

- [ ] **Step 4: 切换章节时自动保存**

修改现有的 `useEffect`（监听 `selectedChapter` 变化的那个），在加载新章节内容之前先保存当前内容：

```typescript
useEffect(() => {
  if (!selectedChapter) return;

  const loadContent = async () => {
    // 先保存待保存的内容
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    // 注意：此处不能用 content state，因为闭包中可能是旧值
    // 使用 contentRef.current 获取最新内容
    const currentContent = contentRef.current;
    if (currentContent) {
      try {
        // 使用上一个章节号保存（selectedChapter 已切换，无法获取旧章节号）
        // 实际实现中需要用 prevChapterNumber ref
      } catch (e) {
        console.error('Save on chapter switch failed:', e);
      }
    }

    setLoadingContent(true);
    try {
      const chapter = await chaptersApi.get(projectId, selectedChapter.chapter_number);
      setChapterContent(chapter);
      setContent(formatContentAsHtml(chapter.content || ''));
      contentRef.current = formatContentAsHtml(chapter.content || '');
      setSaveStatus('saved');
    } catch {
      setChapterContent(null);
      setContent('');
      contentRef.current = '';
      setSaveStatus('saved');
    } finally {
      setLoadingContent(false);
    }
  };
  loadContent();
}, [projectId, selectedChapter]);
```

为了正确保存旧章节内容，需要添加 `prevChapterRef`：

```typescript
const prevChapterRef = useRef<ChapterOutline | null>(null);

// 在 selectedChapter 变化前保存
useEffect(() => {
  return () => {
    // cleanup: 章节即将切换时保存当前内容
    const currentContent = contentRef.current;
    const prevChapter = prevChapterRef.current;
    if (currentContent && prevChapter) {
      chaptersApi.update(projectId, prevChapter.chapter_number, { content: currentContent }).catch(e => {
        console.error('Save on chapter switch failed:', e);
      });
    }
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
  };
}, [selectedChapter?.id]); // 当 selectedChapter.id 变化时触发 cleanup

// 同步 prevChapterRef
useEffect(() => {
  if (selectedChapter) {
    prevChapterRef.current = selectedChapter;
  }
}, [selectedChapter]);
```

- [ ] **Step 5: 离开页面时自动保存（使用 sendBeacon）**

```typescript
useEffect(() => {
  const handleBeforeUnload = () => {
    const currentContent = contentRef.current;
    if (!currentContent || !selectedChapter) return;
    
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    // sendBeacon 保证在页面卸载前发送请求
    const token = getSessionToken();
    const url = `/api/projects/${projectId}/chapters/${selectedChapter.chapter_number}`;
    const payload = JSON.stringify({ content: currentContent });
    
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      // sendBeacon 不支持自定义 header，但项目 cookie 中有 session_token
      navigator.sendBeacon(url, blob);
    }
  };
  
  window.addEventListener('beforeunload', handleBeforeUnload);
  return () => window.removeEventListener('beforeunload', handleBeforeUnload);
}, [projectId, selectedChapter]);
```

注意：`sendBeacon` 使用 Cookie 认证（项目已有 Cookie 中的 session_token），不需要手动设置 Authorization header。

- [ ] **Step 6: 替换工具栏按钮为保存状态指示器**

找到工具栏区域（包含 "AI 生成"、"预览"、"保存" 按钮的部分），替换为：

```tsx
<div className="flex gap-2 items-center">
  <SaveStatusIndicator status={saveStatus} onRetry={handleManualSave} />
</div>
```

添加组件（在 WritingPanel 组件外定义）：

```typescript
function SaveStatusIndicator({ status, onRetry }: { status: SaveStatus; onRetry: () => void }) {
  const config: Record<SaveStatus, { icon: string; text: string; className: string }> = {
    saved: { icon: '✓', text: '已自动保存', className: 'text-muted-foreground bg-muted' },
    saving: { icon: '↻', text: '保存中...', className: 'text-blue-600 bg-blue-50' },
    error: { icon: '⚠', text: '保存失败，点击重试', className: 'text-red-600 bg-red-50 cursor-pointer' },
  };
  const c = config[status];
  return (
    <span 
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${c.className}`}
      onClick={status === 'error' ? onRetry : undefined}
    >
      <span>{c.icon}</span>
      <span>{c.text}</span>
    </span>
  );
}
```

- [ ] **Step 7: 替换底部区域为状态栏**

找到底部导航区域，替换为：

```tsx
<div className="border-t p-3 flex items-center justify-between bg-white">
  <div className="flex items-center gap-4 text-xs text-muted-foreground">
    <span>第 {selectedChapter?.chapter_number || 1} 章 / {chapters.length} 章</span>
    <span className="border-l pl-4">字数 {wordCount.toLocaleString()}</span>
    {kbStatus.blocked.length > 0 && (
      <span className="border-l pl-4 text-red-500 font-medium">
        ⚠ 缺失: {kbStatus.blocked.map(b => {
          const typeMap: Record<string, string> = {
            'character_missing': '角色',
            'world_setting_missing': '世界观',
            'outline_unconfirmed': '大纲确认',
            'chapter_outline_missing': '章节大纲'
          };
          return typeMap[b.type] || b.type;
        }).join(' · ')}
      </span>
    )}
  </div>
  
  <div className="flex items-center gap-3 text-xs">
    <KnowledgeStatusItem label="角色" ok={!kbStatus.blocked.find(b => b.type === 'character_missing')} />
    <KnowledgeStatusItem label="世界观" ok={!kbStatus.blocked.find(b => b.type === 'world_setting_missing')} />
    <KnowledgeStatusItem label="伏笔" ok={!kbStatus.warnings.find(w => w.type === 'foreshadowing_empty')} />
    <KnowledgeStatusItem label="风格约束" ok={!kbStatus.warnings.find(w => w.type === 'style_constraints_missing')} />
    <KnowledgeStatusItem label="情节块" ok={!kbStatus.warnings.find(w => w.type === 'plot_block_empty')} />
    <KnowledgeStatusItem label="时间线" ok={!kbStatus.warnings.find(w => w.type === 'timeline_empty')} />
  </div>
</div>
```

添加组件（在 WritingPanel 组件外定义）：

```typescript
function KnowledgeStatusItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={ok ? "text-green-600" : "text-red-500"}>
      {ok ? "✓" : "✗"} {label}
    </span>
  );
}
```

- [ ] **Step 8: 清理不再需要的函数和导入**

- 删除 `handleSave` 函数
- 删除 `handleReplan` 函数（用户直接在 Agent 侧边栏对话即可）
- 删除 `mode` 状态（不再需要预览/编辑切换）
- 删除不再使用的导入：`Save`, `Loader2`, `Check`, `RefreshCw`, `MessageSquare`, `Pencil`, `Eye`
- 删除 TipTapEditor 中 `mode` 相关的条件渲染，始终使用编辑模式
- 删除 `dangerouslySetInnerHTML` 预览渲染分支

- [ ] **Step 9: 修改 TipTapEditor 调用**

将 `onChange` 改为 `handleContentChange`：

```tsx
<TipTapEditor
  key={selectedChapter?.id}
  content={content}
  onChange={handleContentChange}
  placeholder="开始写作..."
/>
```

移除 `mode === 'edit'` 的条件判断，始终渲染 TipTapEditor。

- [ ] **Step 10: 验证编译**

Run: `cd /Users/biner/Dev/novelagent/frontend && npm run build 2>&1 | tail -20`

- [ ] **Step 11: Commit**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "feat(frontend): knowledge status bar, auto-save, remove redundant buttons"
```

---

### Task 7: 后端 - 为 validate_prerequisites 编写单元测试

**Files:**
- Create: `backend/tests/test_validate_prerequisites.py`

- [ ] **Step 1: 编写测试用例**

```python
import pytest
from unittest.mock import patch, MagicMock
from app.agents.agent_context import validate_prerequisites


@pytest.fixture
def mock_db():
    with patch("app.agents.agent_context.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        yield mock_session


def test_all_prerequisites_met(mock_db):
    """所有前置条件满足时，blocked 和 warnings 为空"""
    # 模拟所有查询返回正常
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        confirmed=True, core_concept="测试世界观"
    )
    mock_db.query.return_value.filter.return_value.count.return_value = 3
    
    result = validate_prerequisites(1, current_chapter=1)
    
    assert result["blocked"] == []
    assert result["warnings"] == []
    assert result["validated"] is True


def test_missing_characters_blocked(mock_db):
    """角色缺失时，加入 blocked"""
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        confirmed=True, core_concept="测试"
    )
    
    # 需要更精细的 mock 来区分不同查询
    result = validate_prerequisites(1, current_chapter=1)
    assert any(b["type"] == "character_missing" for b in result["blocked"])


def test_outline_unconfirmed_blocked(mock_db):
    """大纲未确认时，加入 blocked"""
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        confirmed=False, core_concept="测试"
    )
    mock_db.query.return_value.filter.return_value.count.return_value = 1
    
    result = validate_prerequisites(1, current_chapter=1)
    assert any(b["type"] == "outline_unconfirmed" for b in result["blocked"])


def test_no_current_chapter_skips_chapter_checks(mock_db):
    """current_chapter 为 None 时，跳过章节相关检查"""
    mock_db.query.return_value.filter.return_value.count.return_value = 1
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        core_concept="测试"
    )
    
    result = validate_prerequisites(1, current_chapter=None)
    # 不应有 chapter_outline_missing 或 outline_unconfirmed
    chapter_types = {"chapter_outline_missing", "outline_unconfirmed", "previous_chapter_empty"}
    assert not any(b["type"] in chapter_types for b in result["blocked"])
    assert not any(w["type"] in chapter_types for w in result["warnings"])


def test_single_check_failure_does_not_affect_others(mock_db):
    """单项查询异常不影响其他检查项"""
    # 让第一个查询抛异常，后续查询正常
    call_count = {"n": 0}
    
    def mock_query(model):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Exception("DB error")
        result = MagicMock()
        result.filter.return_value.first.return_value = MagicMock(confirmed=True, core_concept="测试")
        result.filter.return_value.count.return_value = 1
        return result
    
    mock_db.query.side_effect = mock_query
    
    result = validate_prerequisites(1, current_chapter=1)
    # 至少有部分检查完成了
    assert result["validated"] is True
    assert "errors" in result
```

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_validate_prerequisites.py -v`
Expected: 测试通过（可能需要根据实际 mock 行为调整）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_validate_prerequisites.py
git commit -m "test(agent): add unit tests for validate_prerequisites"
```

---

## 验收标准

### 后端
- [ ] 调用 Agent chat 时，`context.prerequisites` 字段正确返回
- [ ] 关键项缺失时，Agent 返回阻断信息
- [ ] 仅次要项缺失时，Agent 正常执行并在末尾添加建议
- [ ] `/knowledge-status` API 正常返回 KB 状态
- [ ] 校验函数中单项异常不影响整体结果
- [ ] 单元测试覆盖关键场景

### 前端
- [ ] 写作页面底部显示状态栏，包含章节进度、字数、知识库状态
- [ ] 编辑器内容变化后 2 秒自动保存
- [ ] 切换章节时自动保存
- [ ] 离开页面时自动保存
- [ ] 保存状态指示器实时反馈保存状态（saved/saving/error）
- [ ] 保存失败可点击重试
- [ ] 无"AI 生成"、"保存"、"预览"按钮
- [ ] 知识库状态栏正确显示各检查项状态

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-12-writing-prerequisites-and-panel-optimization-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每次 dispatch 一个 subagent 执行单个任务，两阶段 review，快速迭代

**2. Inline Execution** - 使用 executing-plans 分批执行，带 checkpoint review

**Which approach?**
