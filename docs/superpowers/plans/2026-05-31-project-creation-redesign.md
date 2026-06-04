# 项目创建流程重构计划

## 概述

**目标**：将创建项目从"输入名字 → 空项目"改为"输入概念 → AI 生成基础内容 → 进入有内容的工作台"。

**收益**：
- 用户冷启动心理压力降低（从空白开始 → 有基础内容）
- 创作流程更自然（先有想法，再有名）
- 项目创建后立即有可探索的内容

---

## 用户流程

```
[步骤 1] 输入概念
┌─────────────────────────────────────┐
│  概念描述                            │
│  ┌─────────────────────────────┐    │
│  │ 输入你的小说想法...          │    │
│  └─────────────────────────────┘    │
│                                     │
│  目标字数：[    100000    ] 字      │
│                                     │
│  [创建项目]                         │
└─────────────────────────────────────┘

         ↓

[步骤 2] 创建项目 API + SSE 进度
  └─ POST /api/projects/initialize
  └─ 返回 SSE 流，实时展示各阶段进度

[步骤 3] 完成 → 自动跳转工作台
  └─ 项目已有基础内容，可直接探索或继续对话
```

---

## 实现范围

### 后端改动

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `app/schemas/project.py` | 修改 | 添加 `ProjectInitializeRequest` schema |
| `app/api/projects.py` | 修改 | 新增 `/api/projects/initialize` 端点 |
| `app/agents/nodes/initialization.py` | 新增 | 封装初始化逻辑 |

### 前端改动

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/types/index.ts` | 修改 | 添加 `ProjectInitializeRequest` 类型 |
| `src/lib/api.ts` | 修改 | 添加 `projectsApi.initialize()` 方法 |
| `src/components/common/CreateProjectDialog.tsx` | 重构 | 改为概念输入表单 |
| `src/pages/ProjectCreating.tsx` | 新增 | 创建进度页面 |
| `src/App.tsx` | 修改 | 添加 `/project/creating` 路由 |
| `src/pages/Home.tsx` | 修改 | 创建成功后跳转到进度页面 |

---

## 详细设计

### 1. 后端 API 设计

**端点**：`POST /api/projects/initialize`

**请求体**：

```typescript
interface ProjectInitializeRequest {
  concept: string;          // 必填，用户的小说概念描述
  target_words?: number;   // 可选，默认 100000
}
```

**响应**：SSE 流（`text/event-stream`）

**SSE 事件**：

| 事件名 | data 字段 | 说明 |
|--------|-----------|------|
| `init:start` | `{}` | 开始初始化 |
| `init:concept` | `{concept: string, story_seed: string}` | 概念解析完成，返回故事种子 |
| `init:novel_name` | `{name: string}` | 小说名生成完成 |
| `init:world` | `{world_setting_id: number}` | 世界观生成完成 |
| `init:characters` | `{character_count: number}` | 角色生成完成 |
| `init:outline` | `{outline_id: number, chapter_count: number}` | 大纲生成完成 |
| `init:style` | `{style_constraints_id: number}` | 风格设定完成 |
| `init:complete` | `{project_id: number, name: string}` | 全部完成，返回项目 ID |
| `init:error` | `{stage: string, error: string}` | 某个阶段失败，继续下一步 |
| `init:done` | `{project_id: number, status: "partial" | "complete"}` | 流程结束 |

**失败策略**：跳过失败的节点，保留已成功的部分，最终返回 `status: "partial"`

---

### 2. 后端节点执行顺序

由于现有节点存在依赖关系（`world_setting_node` 需要 outline，`character_generation_node` 需要 outline + world_setting），需要调整调用方式：

```
1. concept → story_seed（直接使用 concept 作为输入）
2. story_seed → novel_name（新增简单 prompt）
3. story_seed → world_setting（跳过 outline 依赖，使用 story_seed）
4. world_setting → characters（跳过 outline 依赖，使用 world_setting）
5. story_seed + characters → outline（生成大纲）
6. outline + world_setting → style（生成风格）
```

**简化方案**：直接调用节点的核心逻辑，传递必要的参数，不走完整的工作流图。

---

### 3. 前端页面设计

**路由**：`/project/creating`

**参数**：`?project_id=xxx`

**状态管理**：

```typescript
interface CreatingState {
  stage: 'concept' | 'seed' | 'name' | 'world' | 'characters' | 'outline' | 'style' | 'complete';
  progress: number;        // 0-100
  currentLabel: string;    // 当前阶段的中文描述
  novelName: string;       // 已生成的小说名
  projectId: number | null;
  error: string | null;
}
```

**界面**：
- 顶部：进度条（百分比）
- 中间：当前阶段列表（✓ 完成，● 进行中，○ 等待中）
- 底部：预估剩余时间

**完成逻辑**：
- 收到 `init:complete` 或 `init:done` 事件后
- 延迟 1 秒让用户看到"100%"
- 自动跳转到 `/project/{project_id}/workbench`

---

### 4. 数据库改动

**无新增表**，复用现有表：

- `Project`：新增时 `name` 初始为 `"新建项目"`，初始化完成后更新为 AI 生成的小说名
- `Outline`：由初始化逻辑填充
- `WorldSetting`：由初始化逻辑填充
- `Character`：由初始化逻辑填充
- `StyleConstraints`：由初始化逻辑填充

---

## 实现步骤

### Step 1: 后端 - Schema

在 `app/schemas/project.py` 添加：

```python
class ProjectInitializeRequest(BaseModel):
    concept: str
    target_words: Optional[int] = 100000
```

---

### Step 2: 后端 - 初始化逻辑

新建 `app/agents/nodes/initialization.py`：

```python
async def initialize_project(
    concept: str,
    target_words: int,
    project_id: int,
    user_id: int,
    sse_writer
):
    """
    项目初始化主流程
    
    串行执行各阶段，跳过失败的节点，每个节点完成后 yield SSE 事件
    """
    # 1. 创建 Project（临时 name）
    # 2. 生成 story_seed
    # 3. 生成小说名，更新 Project.name
    # 4. 生成世界观
    # 5. 生成角色
    # 6. 生成大纲
    # 7. 生成风格
}
```

新增"生成小说名"逻辑：

```python
NOVEL_NAME_PROMPT = """根据以下故事种子，生成一个吸引人的小说名。

## 故事种子
{story_seed}

要求：
- 简洁有力，2-8 个字
- 能体现故事核心氛围
- 不要书名号，直接输出名字

直接输出小说名，不要其他解释。"""
```

---

### Step 3: 后端 - API 端点

在 `app/api/projects.py` 添加 `/initialize` 端点：

```python
@router.post("/initialize")
async def initialize_project(
    request: ProjectInitializeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """初始化项目：创建项目 + 生成基础知识库（SSE 流）"""
    
    # 1. 创建 Project（name 临时为 "新建项目-{timestamp}"）
    # 2. 创建 Outline（空的）
    # 3. 启动初始化流程，返回 SSE 流
```

---

### Step 4: 前端 - 类型

在 `src/types/index.ts` 添加：

```typescript
export interface ProjectInitializeRequest {
  concept: string;
  target_words?: number;
}
```

---

### Step 5: 前端 - API

在 `src/lib/api.ts` 添加：

```typescript
// 创建项目并初始化知识库（SSE 流）
initialize(
  concept: string,
  target_words?: number,
  onEvent: (event: SSEEvent) => void
): Promise<{ project_id: number; status: string }>
```

---

### Step 6: 前端 - 创建对话框

重构 `CreateProjectDialog.tsx`：
- 移除"项目名称"输入
- 添加"概念描述"多行文本框（textarea）
- 添加"目标字数"输入框（默认 10 万）
- 点击"创建项目"后调用 `projectsApi.initialize()`，展示进度
- 完成时自动跳转工作台

---

### Step 7: 前端 - 路由

在 `App.tsx` 添加：

```tsx
<Route 
  path="/project/creating" 
  element={
    <PrivateRoute>
      <ProjectCreating />
    </PrivateRoute>
  }
/>
```

---

## 测试计划

### 单元测试

| 测试项 | 说明 |
|--------|------|
| 后端：initialize 端点正常流程 | 发送概念，接收完整 SSE 事件流 |
| 后端：initialize 端点部分失败 | 模拟某个节点失败，验证 partial 状态 |
| 前端：ProjectCreating 状态机 | 验证各阶段状态转换正确 |
| 前端：完成跳转 | 验证完成后正确跳转 |

### 手动测试

| 测试项 | 步骤 | 预期 |
|--------|------|------|
| 完整创建流程 | 输入概念 → 创建 → 等待完成 → 进入工作台 | 工作台有内容 |
| 部分失败流程 | 模拟 LLM 失败 | 仍能进入工作台，缺失内容可手动补充 |
| 重复创建 | 快速点击创建按钮 | 只创建一个项目 |

---

## 边界情况

| 情况 | 处理 |
|------|------|
| concept 为空 | 前端阻止提交，后端额外验证 |
| concept 过短（<10 字） | 警告但允许提交 |
| LLM 服务不可用 | 跳过该节点，继续后续（返回 partial） |
| 用户在生成过程中关闭页面 | 项目已创建但内容不完整，用户可进入手动补充 |
| 生成时间过长（>120s） | 强制结束，返回当前进度 |

---

## 假设

1. 用户已配置有效的 LLM 模型
2. 前端有网络时始终可以完成 SSE 连接
3. 创建过程中的错误不会导致数据库不一致（事务保护）
4. 不需要"取消创建"功能（后续迭代）

---

## 待完成

- [x] 目标字数改为手填输入框
- [x] API 流程合并为一步（POST /api/projects/initialize 直接 SSE）
- [x] 节点依赖关系已考虑
- [x] 临时 Project.name 使用 "新建项目" + ��间戳
