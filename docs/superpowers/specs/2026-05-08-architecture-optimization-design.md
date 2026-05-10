# NovelAgent 架构优化设计文档

> **对应 PRD：** [Issue #13 — 架构优化：消除重复代码、清晰化接缝、强化 LangGraph 规范合规](https://github.com/OldRookieBiner/novelagent/issues/13)
> **版本：** v0.8.2+
> **目标：** 纯重构（pure refactor），不改变任何外部 API 契约、SSE 事件格式、UI 外观和交互

---

## 1. 设计概述

本次优化是一次**纯架构重构**，核心目标是将 NovelAgent 后端和前端的浅模块（shallow modules）转化为深模块（deep modules），消除重复代码、清晰化接缝，同时强化 LangGraph 规范合规性。

**重构范围：**
- 后端：SSE 流式编排、节点依赖注入、业务服务层提取、NovelState 契约
- 前端：API 客户端合并、Store 状态合并、面板组件拆分、CRUD 抽象

**不变项（hard constraints）：**
- API URL 路径、请求/响应格式、SSE 事件类型（`node_start`, `chunk`, `node_done`, `waiting`, `done`, `error`）
- LangGraph 节点签名保持 `(state, config) -> state` 或 `(state) -> state`
- `NovelState` 全程为可 JSON 序列化的字典，不混入 ORM 模型
- 数据库 schema 不新增表、不修改列
- UI 外观、交互逻辑、页面路由保持不变
- **例外：** 在保持 API 契约不变的前提下，允许修复已存在的语法错误和运行时错误（如 `chapters.py` 中的 `Noneracker` 打字错误、未定义变量等）

---

## 2. 后端架构设计

### 2.1 WorkflowOrchestrator 服务

**问题：** `api/outline.py`、`api/chapters.py`、`api/workflow.py` 的 SSE 流式端点各自实现了相似的逻辑：构建初始状态 → 创建图 → 流式输出 → 捕获 `node_done` → 写入数据库 → 发送兼容 `done` 事件。

**设计方案：**

创建 `app.services.workflow_orchestrator.WorkflowOrchestrator` 类，封装以下职责：

```python
class WorkflowOrchestrator:
    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    async def run(
        self,
        node_name: str,
        initial_state: NovelState,
        persist_callback: Callable[[NovelState], Awaitable[None]] | None = None,
        llm_config_id: int | None = None,
    ) -> AsyncIterator[str]:
        """执行工作流并生成 SSE 事件流"""
```

**关键接口：**

| 方法 | 职责 |
|------|------|
| `run()` | 创建图 → 流式执行 → 解析事件 → 触发持久化回调 → 发送兼容 done |
| `_build_graph()` | 创建带 checkpointer 的图，注入 `configurable` |
| `_stream_events()` | 包装 `astream_events`，统一转换为 SSE 格式 |
| `_call_persist()` | 在 `node_done` 且目标节点匹配时，调用持久化回调 |

**持久化回调签名：**

```python
PersistCallback = Callable[[NovelState, Session], Awaitable[dict]]
# 返回 dict 用于构造兼容前端的 done 事件数据
```

**端点改造示例（`outline.py`）：**

```python
@router.post("/{project_id}/outline")
async def generate_outline(...):
    ...
    orchestrator = WorkflowOrchestrator(db, project_id)

    async def persist_outline(state: NovelState, db: Session) -> dict:
        outline.title = state.get("outline_title")
        outline.summary = state.get("outline_summary")
        ...
        db.commit()
        return {"outline": {...}, "stage": STAGE_OUTLINE}

    return StreamingResponse(
        orchestrator.run(
            node_name="outline_generation_node",
            initial_state=initial_state,
            persist_callback=persist_outline,
        ),
        media_type="text/event-stream",
        headers={...}
    )
```

**删除范围：**
- `api/outline.py` 中 `stream_generator()` 内联逻辑（约 60 行）
- `api/chapters.py` 中 `stream_generator()` 内联逻辑（约 80 行）
- `agents/streaming.py` 中废弃的 `stream_node_events` 和 `create_single_node_graph`

### 2.2 节点依赖注入（LangGraph Config 注入）

**问题：** 多个节点内部直接 `import SessionLocal; db = SessionLocal()`，导致：
- 会话生命周期与图执行脱节
- 检查点恢复时节点重新创建新会话
- 测试困难（无法注入 mock session）

**设计方案：**

通过 `config["configurable"]` 注入依赖，**节点签名不变**：

```python
# 节点工厂（推荐用于需要复杂注入的场景）
def make_outline_generation_node(prompt_loader, llm_factory):
    async def node(state: NovelState, config: dict) -> NovelState:
        # 从 config 获取注入的依赖
        # db = config["configurable"].get("db_session")
        # 但节点不应直接操作 DB，只负责状态转换
        llm = llm_factory(state)
        prompt = prompt_loader.load("outline_generation", state)
        ...
    return node
```

**简化方案（当前推荐）：**

对于 `character_generation_node` 和 `relation_generation_node`，它们内部创建 `SessionLocal` 主要是为了加载 `get_system_prompt()`。可以改为：

1. 在 `api/workflow.py` 的 `build_initial_state()` 中，将所需的 prompt 文本预加载并注入到 `initial_state` 中（或 `config["configurable"]`）。
2. 节点内部不再查询数据库获取 prompt。

但 prompt 可能很长，不适合塞进 state。

**推荐方案（双层回退）：**

通过 `config["configurable"]` 传入 `db_session`，同时保留回退机制：

```python
async def create_characters_from_outline_node(state: NovelState, config: dict) -> NovelState:
    db = config.get("configurable", {}).get("db_session")
    if db is None:
        # 回退：创建新 session（保持向后兼容，测试时注入 mock）
        from app.database import SessionLocal
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        prompt = get_system_prompt(db, "character_generation")
        ...
    finally:
        if should_close:
            db.close()
```

**LLM 获取简化：**

当前 `get_llm_from_state_async` 的调用链深达四层，且内部自行创建 `SessionLocal`。改为节点接收可选 `db` 参数，调用压缩后的 `get_llm_from_state_async(state, db)`：

```python
# app/utils/llm.py — 压缩后的函数
async def get_llm_from_state_async(state: dict, db: Session = None) -> "LLMService":
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    try:
        project_id = state.get("project_id")
        project = db.query(Project).filter(Project.id == project_id).first()
        ...
        return get_llm_for_user(user_id, user_settings, db, state.get("llm_config_id"))
    finally:
        if should_close:
            db.close()
```

节点调用方式：

```python
llm = await get_llm_from_state_async(state, db)
response = await llm.chat([...])
```

**注意：** `LLMService` 实例不可序列化，**禁止**将其注入 `config["configurable"]`。必须通过函数调用按需创建。

**同步 DB 访问策略：**

注入的 `db_session` 是同步 SQLAlchemy session。在 async 节点中直接调用 `db.query()` 会阻塞 event loop，影响所有并发的 SSE 流式请求。

推荐采用 **Prompt 预加载方案**，彻底避免节点内部的 DB 访问：

```python
# WorkflowOrchestrator.run() 中预加载
prompts = {
    "character_generation": get_system_prompt(db, "character_generation"),
    "relation_generation": get_system_prompt(db, "relation_generation"),
}
config = {
    "configurable": {
        "thread_id": "default",
        "prompts": prompts,  # 节点直接从 config 读取
    }
}
```

节点内部不再调用 `get_system_prompt(db, ...)`：

```python
async def create_characters_from_outline_node(state: NovelState, config: dict) -> NovelState:
    prompts = config.get("configurable", {}).get("prompts", {})
    prompt = prompts.get("character_generation", DEFAULT_CHARACTER_PROMPT)
    ...
```

**备选方案（若必须保留 DB 访问）：** 使用 `run_in_executor` 包装同步 DB 调用：

```python
import asyncio
loop = asyncio.get_event_loop()
prompt = await loop.run_in_executor(None, get_system_prompt, db, "character_generation")
```

**决策：** 优先采用 Prompt 预加载方案，使节点成为纯函数，完全避免同步 DB 访问的阻塞风险。

### 2.3 业务服务层提取

**问题：** API 路由混合了授权、校验、数据库查询、LLM 编排、SSE 解析、响应格式化。

**设计方案：**

创建以下服务类：

```python
# app/services/outline_service.py
class OutlineService:
    def __init__(self, db: Session, project_id: int, user_id: int):
        self.db = db
        self.project_id = project_id
        self.user_id = user_id

    def validate_can_generate(self) -> None:
        """校验大纲是否可以重新生成（未确认等）"""

    def calculate_chapter_count(self, collected_info: dict) -> int:
        """根据目标字数和每章字数计算章节数"""

    async def generate(self, llm_config_id: int | None = None) -> AsyncIterator[str]:
        """调用 WorkflowOrchestrator 生成大纲并返回 SSE 流"""

# app/services/chapter_service.py
class ChapterService:
    ...
```

**服务层边界：**
- 服务层接收 `Session` 和 `User` 上下文
- 服务层负责业务校验（如"大纲已确认不能重新生成"）
- 服务层调用 `WorkflowOrchestrator`，提供节点特定的持久化回调
- 服务层不直接操作 `StreamingResponse`，返回 `AsyncIterator[str]`

**API 路由改造后：**

```python
@router.post("/{project_id}/outline")
async def generate_outline(project_id: int, ..., db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = OutlineService(db, project_id, user.id)
    service.validate_can_generate()
    return StreamingResponse(
        service.generate(llm_config_id=request.llm_config_id if request else None),
        media_type="text/event-stream",
        headers={...}
    )
```

### 2.4 NovelState 节点契约

**问题：** 30+ 字段的状态没有显式读写契约，节点间存在隐式依赖。

**设计方案：**

为每个节点在代码注释中明确标注读写契约：

```python
async def outline_generation_node(state: NovelState, config: dict) -> NovelState:
    """大纲生成节点

    读取字段:
        - project_id (int)
        - collected_info (dict): 必须包含 novelType, targetWords, coreTheme...
        - inspiration_template (str | None)
        - outline_world_setting (dict | None)

    写入字段:
        - outline_title (str)
        - outline_summary (str)
        - outline_plot_points (list[dict])
        - outline_characters (list[dict])
        - outline_world_setting (dict)
        - outline_emotional_curve (str | None)
        - stage (str): 设置为 STAGE_OUTLINE

    前置条件:
        - collected_info 不为空
    """
```

**角色数据一致性：**

`create_characters_from_outline_node` 当前返回的 `characters` 没有 `id`。`generate_relations_node` 被迫自己查数据库。

**关键问题：** 持久化回调在 API 路由层执行，写入 DB 后修改 `output` 字典，但这个修改**不会同步到 LangGraph 已保存的检查点**。当用户调用 `confirm_workflow` 恢复执行时，LangGraph 从检查点加载的是旧状态（不含 `id`），`relation_generation_node` 仍然拿不到 `id`。

**正确方案（build_initial_state 预加载）：**

在 `build_initial_state()` 中，从数据库预加载已持久化的角色/关系数据（带 `id`），覆盖 state 中的对应字段。这样无论检查点中存的是什么，初始状态总是从 DB 获取最新数据。

```python
def build_initial_state(project, outline, workflow_state, llm_config_id=None):
    state = {...}
    # 从 DB 预加载已持久化的角色（带 id），覆盖检查点中的旧数据
    db_characters = db.query(Character).filter(
        Character.project_id == project.id
    ).order_by(Character.id).all()
    if db_characters:
        state["characters"] = [
            {"id": c.id, "name": c.name, "role": c.role, ...}
            for c in db_characters
        ]
    # 同理预加载关系
    db_relations = db.query(Relation).filter(Relation.project_id == project.id).all()
    if db_relations:
        state["relations"] = [
            {"id": r.id, "character_a_id": r.character_a_id, ...}
            for r in db_relations
        ]
    return state
```

**效果：**
- `generate_relations_node` 从 `state["characters"]` 获取带 `id` 的角色，无需自己查 DB
- 检查点恢复后，`build_initial_state` 保证 state 中的角色/关系始终是最新的 DB 数据
- 节点保持纯状态转换，不直接查询数据库

### 2.5 非 SSE 端点的处理范围

**问题：** 当前工作流相关端点不全是 SSE 流式。`chapters.py` 中的 `review_chapter` 使用 `graph.ainvoke()` 同步调用，`workflow.py` 中的 `cancel_workflow`、`update_workflow_stage` 等是纯 REST 端点。

**设计方案：**

| 端点 | 类型 | 处理方式 |
|------|------|----------|
| `POST /outline` | SSE 流式 | 纳入 WorkflowOrchestrator |
| `POST /chapter-outlines` | SSE 流式 | 纳入 WorkflowOrchestrator |
| `POST /chapters/{n}/generate` | SSE 流式 | 纳入 WorkflowOrchestrator |
| `POST /workflow/run` | SSE 流式 | 纳入 WorkflowOrchestrator |
| `POST /workflow/confirm` | SSE 流式 | 纳入 WorkflowOrchestrator |
| `POST /chapters/{n}/review` | 同步调用（`ainvoke`） | **本次重构暂不改造**，保持现有逻辑，仅修复已存在 bug（如 `Noneracker` 打字错误、未定义变量） |
| `POST /workflow/cancel` | 纯 REST | 不纳入 WorkflowOrchestrator，保持原样 |
| `PUT /workflow/stage` | 纯 REST | 不纳入 WorkflowOrchestrator，保持原样 |

**理由：** `review_chapter` 不使用 SSE，且涉及审核结果解析和 DB 写入的特殊逻辑，与流式编排模式不同。强行纳入 WorkflowOrchestrator 会增加复杂度而非降低。保持现有结构，仅修复语法错误。

### 2.6 WorkflowOrchestrator 错误处理策略

**问题：** 持久化回调在 SSE 流式过程中被调用，如果回调中发生异常（如数据库唯一键冲突、外键约束失败），必须妥善处理，避免流式连接异常断开或数据不一致。

**设计方案：**

```python
class WorkflowOrchestrator:
    async def _call_persist(
        self,
        node_name: str,
        event_name: str,
        state: NovelState,
        persist_callback: PersistCallback | None,
    ) -> dict:
        """调用持久化回调，异常转换为 SSE error 事件数据"""
        if persist_callback is None or event_name != node_name:
            return {}

        try:
            result = await persist_callback(state, self.db)
            return result or {}
        except Exception as e:
            # 记录详细错误日志
            logger.error(f"Persist callback failed for {node_name}: {e}")
            # 回滚当前事务，避免部分写入
            self.db.rollback()
            # 返回 error 标记，由调用方决定是否中断流
            return {"_persist_error": str(e)}

    async def run(self, ...):
        async for sse_event in self._stream_events(graph, config, initial_state):
            yield sse_event

            # 检查持久化是否出错
            if isinstance(sse_event, dict) and sse_event.get("_persist_error"):
                error_msg = sse_event["_persist_error"]
                yield f"event: error\ndata: {json.dumps({'error': f'持久化失败: {error_msg}'})}\n\n"
                # 持久化失败是严重错误，中断流
                return
```

**关键约束：**
- 持久化回调异常时，**必须回滚事务**（`self.db.rollback()`），避免部分写入导致数据不一致
- 错误信息通过 SSE `error` 事件发送给前端，前端显示友好的错误提示
- 流式生成器在遇到持久化错误时**中断输出**，不再继续执行后续节点

---

## 3. 前端架构设计

### 3.1 API 客户端合并

**问题：** `workflowApi.ts` 自己实现了 `buildAuthHeaders()` 和 `makeRequest()`，与 `api.ts` 的 `request()` 重复。

**设计方案：**

删除 `workflowApi.ts` 中的：
- `buildAuthHeaders()` 函数
- `makeRequest()` 函数

将 `workflowApi` 中的非流式方法（`confirmWorkflow`, `getWorkflowState`, `cancelWorkflow`, `setWorkflowMode`, `updateStage`）改用 `api.ts` 的 `request()`：

```typescript
// workflowApi.ts
import { request } from './api'

export const workflowApi = {
  async confirmWorkflow(projectId: number): Promise<void> {
    await request<void>(`/api/projects/${projectId}/workflow/confirm`, {
      method: 'POST',
    })
  },
  // ...
}
```

`runWorkflow()` 仍需使用 `createSSEStream`，但认证头通过 `getSessionToken()` 统一获取，不重复 `buildAuthHeaders` 逻辑。

### 3.2 Store 合并

**问题：** `projectStore` 和 `workflowStore` 同时拥有 `outline` 和 `chapterOutlines`。

**设计方案：**

将 `projectStore` 中的数据状态迁移到 `workflowStore`（因为 workflowStore 更完整）：

```typescript
// 删除 projectStore 中的重复字段
interface ProjectState {
  currentProject: ProjectDetail | null
  currentChapterNum: number
  setCurrentProject: (project: ProjectDetail | null) => void
  setCurrentChapterNum: (num: number) => void
  clear: () => void
}
```

所有原本使用 `useProjectStore(state => state.outline)` 的组件，改为使用 `useWorkflowStore(state => state.outline)`。

**兼容性处理：** 由于组件数量可能较多，可以先在 `projectStore` 中添加兼容层（deprecated 标记），内部委托到 `workflowStore`，然后逐步迁移。

### 3.3 面板组件拆分

**问题：** `InspirationPanel.tsx`（1035 行）、`WritingPanel.tsx`（587 行）混合数据获取、表单校验、API 调用、UI 渲染。

**设计方案：**

每个面板拆分为 **Panel 组件** + **Feature Hook**。

以 `InspirationPanel` 为例：

```typescript
// hooks/useInspiration.ts
export function useInspiration(projectId: number) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // ... 所有数据逻辑

  return {
    data,
    loading,
    error,
    actions: {
      saveInspiration,
      generateOutline,
      // ...
    }
  }
}

// InspirationPanel.tsx
export function InspirationPanel({ projectId }: { projectId: number }) {
  const { data, loading, error, actions } = useInspiration(projectId)
  // 纯渲染逻辑
}
```

### 3.4 通用 CRUD Hook + 组件

**问题：** 人物、关系、演变规划等 CRUD 对话框重复同样的表单状态管理模式。

**设计方案：**

```typescript
// hooks/useCrudDialog.ts
export interface CrudDialogState<T> {
  open: boolean
  editingItem: T | null
  formData: Partial<T>
}

export function useCrudDialog<T extends Record<string, unknown>>(
  defaultValues: Partial<T>
) {
  const [state, setState] = useState<CrudDialogState<T>>({
    open: false,
    editingItem: null,
    formData: defaultValues,
  })

  const openCreate = () => setState({ open: true, editingItem: null, formData: defaultValues })
  const openEdit = (item: T) => setState({ open: true, editingItem: item, formData: item })
  const close = () => setState({ open: false, editingItem: null, formData: defaultValues })
  const updateField = (field: keyof T, value: unknown) =>
    setState(s => ({ ...s, formData: { ...s.formData, [field]: value } }))

  return { ...state, openCreate, openEdit, close, updateField }
}
```

---

## 4. 数据流

### 4.1 后端工作流数据流（重构后）

```
API Route (FastAPI)
  -> Project/Outline/Chapter Service
    -> WorkflowOrchestrator.run()
      -> build_initial_state() + build_graph()
      -> graph.astream_events()
        -> LangGraph Node (state, config) -> state
      -> parse node_done
      -> call PersistCallback (写入 DB，回填 state)
      -> yield SSE events
```

### 4.2 前端数据流（重构后）

```
Page Component
  -> Feature Hook (useInspiration / useWriting / useCharacters)
    -> API Client (统一 request() 或 createSSEStream)
      -> Zustand Store (workflowStore 作为唯一数据真相源)
  -> Panel Component (纯渲染，接收 props)
```

---

## 5. 关键约束与决策

### 5.1 LangGraph 规范约束

- **节点签名：** 必须保持 `(state: NovelState, config: dict) -> NovelState` 或 `(state: NovelState) -> NovelState`
- **状态可序列化：** `NovelState` 全程为 dict/list/str/int/bool/None，禁止混入 ORM 模型、datetime 对象、自定义类实例
- **依赖注入：** 通过 `config["configurable"]` 传入轻量级数据（如 `db_session`），禁止改为函数参数注入
- **LLM 服务不可注入 config：** `LLMService` 实例包含 HTTP 客户端等不可序列化对象，**禁止**塞入 `config["configurable"]`。节点通过压缩后的 `get_llm_from_state_async(state, db)` 按需创建

### 5.2 检查点兼容性

- `WorkflowCheckpoint.checkpoint` 存储的是 LangGraph 内部状态格式（`{"channel_values": {...}, ...}`）
- `channel_values` 即为 `NovelState` 的字典形式
- 任何新增到 `NovelState` 的字段都必须是可 JSON 序列化的

### 5.3 向后兼容

- API 接口完全不变
- 前端 `workflowApi`、`outlineApi`、`chapterOutlinesApi`、`chaptersApi` 的公开接口不变
- SSE 事件格式不变
- 数据库 schema 不变
- **`review_chapter` 等非 SSE 端点暂不纳入 WorkflowOrchestrator**：保持现有同步调用逻辑，避免不匹配的改造增加复杂度
- **允许修复已存在 bug：** `chapters.py` 中的 `Noneracker` 打字错误、未定义变量等运行时错误，在重构中一并修复

### 5.4 测试安全网

- 重构前：运行 `pytest -v` 和 `cd frontend && npm run test`，记录基线
- 重构中：每完成一个模块，运行相关测试
- 重构后：全部测试必须通过，零失败

---

## 6. 实施顺序建议

| 顺序 | 模块 | 风险 | 依赖 |
|------|------|------|------|
| 1 | 前端 API 客户端合并 | 低 | 无 |
| 2 | 后端 WorkflowOrchestrator | 中 | 无 |
| 3 | 后端节点 config 注入 | 中 | 2 |
| 4 | 后端服务层提取 | 中 | 2, 3 |
| 5 | 前端 Store 合并 | 低 | 1 |
| 6 | 前端面板拆分 + CRUD 抽象 | 低 | 5 |

---

## 7. 验收标准

- [ ] `pytest -v` 全部通过（当前基线：约 15 个测试文件）
- [ ] `cd frontend && npm run test` 全部通过
- [ ] 手动走通完整工作流：灵感采集 → 大纲生成 → 角色生成 → 关系生成 → 章节大纲 → 章节正文 → 审核
- [ ] 代码重复率显著下降（可通过 `jscpd` 或 `pylint` 检测）
- [ ] 新增代码有对应单元测试覆盖
