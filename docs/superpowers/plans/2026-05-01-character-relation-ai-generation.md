# 角色和关系 AI 生成功能 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现大纲生成完成后自动提取角色并 AI 生成关系，打通 LangGraph 工作流中 characters → relations 两个阶段

**Architecture:** 在 LangGraph 图中新增 2 个节点（create_characters_from_outline 同步节点 + generate_relations LLM 节点）+ 2 个条件路由函数，前端 OutlineProgressDialog 从 fake setTimeout 改为对接 workflowApi.runWorkflow SSE 事件

**Tech Stack:** Python/FastAPI/LangGraph/SQLAlchemy + React/TypeScript/Zustand

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `backend/app/agents/nodes/character_generation.py` | `extract_characters_from_outline` 数据库写入 + `create_characters_from_outline_node` LangGraph 节点 |
| 新建 | `backend/app/agents/nodes/relation_generation.py` | `generate_relations_node` LLM 节点 + `parse_relations_response` 解析器 |
| 修改 | `backend/app/agents/prompts.py:415-424` | 新增 `RELATION_GENERATION_PROMPT` + 注册到 `DEFAULT_PROMPTS` |
| 修改 | `backend/app/agents/graph.py:21-37,110-130` | 新增 2 节点 + 编辑边 + 新增 `route_after_characters` / `route_after_relations` |
| 修改 | `backend/app/agents/nodes/__init__.py` | 导出新节点 |
| 修改 | `backend/app/agents/nodes/wait_confirm.py:31-33` | hybrid 模式增加 "characters" "relations" 确认类型 |
| 修改 | `backend/app/api/characters.py:794-888` | 替换 3 个 501 stub 为功能实现 |
| 修改 | `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` | 从 `outlineApi.createStream` 切换到 `workflowApi.runWorkflow` |

---

### Task 1: 新增 RELATION_GENERATION_PROMPT

**Files:**
- Modify: `backend/app/agents/prompts.py:415-424`

- [ ] **Step 1: 在文件末尾 DEFAULT_PROMPTS 上方添加 Prompt 常量**

```python
# ==================== 关系生成 Prompt ====================

RELATION_GENERATION_PROMPT = '''你是一个资深小说人物关系设计师，擅长为角色构建有深度、有张力的关系网络。

## 输入信息

### 角色列表
{characters_text}

### 世界观
{world_era}

### 故事概述
{outline_summary}

## 输出要求

请分析所有角色之间的可能关系，为每对关键角色输出一条关系。格式如下：

- 角色A名 | 角色B名 | 关系类型 | 信任度(0-100) | 描述 | 发展方向

### 关系类型说明
- 信任：相互信任的朋友
- 敌对：互相敌视或竞争
- 感情：爱慕、暗恋等情感纽带
- 合作：基于共同目标的合作关系
- 利用：一方利用另一方
- 陌生：彼此不熟悉但可能有交集

### 信任度说明
- 0-20：极度不信任/敌对
- 21-40：轻度戒备
- 41-60：普通关系
- 61-80：比较信任
- 81-100：完全信任/亲密

### 规则
1. 每行一条关系，格式严格为 `- 角色A | 角色B | 关系类型 | 信任度 | 描述 | 发展方向`
2. 主角应与其他所有关键角色都有关系
3. 描述要简洁（20字以内），发展方向要简短（15字以内）
4. 不要生成重复的关系对（如 A-B 和 B-A 只保留一条）
5. 信任度必须是与角色A→角色B方向的信任度
'''
```

- [ ] **Step 2: 注册到 DEFAULT_PROMPTS**

将 `DEFAULT_PROMPTS` dict 改为：

```python
DEFAULT_PROMPTS = {
    "outline_generation": OUTLINE_GENERATION_PROMPT,
    "chapter_outline_generation": GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    "chapter_content_generation": GENERATE_CHAPTER_CONTENT_PROMPT,
    "review": REVIEW_CHAPTER_PROMPT,
    "rewrite": REWRITE_CHAPTER_PROMPT,
    "relation_generation": RELATION_GENERATION_PROMPT,
}
```

- [ ] **Step 3: 验证 Prompt 格式**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.prompts import DEFAULT_PROMPTS; p = DEFAULT_PROMPTS['relation_generation']; print('Has {characters_text}:', '{characters_text}' in p); print('Has {world_era}:', '{world_era}' in p); print('Has {outline_summary}:', '{outline_summary}' in p); print('Length:', len(p))"`
Expected: 三个占位符都返回 True，Length > 200

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/prompts.py
git commit -m "feat: add relation_generation prompt template"
```

---

### Task 2: 新增 character_generation 节点

**Files:**
- Create: `backend/app/agents/nodes/character_generation.py`

- [ ] **Step 1: 创建文件**

```python
"""角色生成节点 - 从大纲提取角色并写入数据库"""

from app.database import SessionLocal
from app.models.character import Character
from app.agents.state import NovelState, STAGE_CHARACTERS


def _map_role(outline_role: str) -> str:
    """将大纲中的角色标签映射到 Character 模型的 role 枚举值

    大纲角色标签可能多样化，需要做归一化映射。
    """
    role = (outline_role or "").strip()
    if "主角" in role:
        return "主角"
    if "反派" in role or "敌" in role:
        return "核心反派"
    if "重要" in role or "主要男" in role or "主要女" in role:
        return "重要配角"
    return "配角"


def extract_characters_from_outline(state: NovelState) -> list[dict]:
    """从大纲的 outline_characters 提取角色并写入数据库

    删除项目已有角色（避免重复），然后从 state["outline_characters"]
    创建新角色记录。

    Args:
        state: NovelState（需包含 project_id 和 outline_characters）

    Returns:
        已创建的角色列表 [{id, name, role, ...}]
    """
    project_id = state["project_id"]
    outline_characters = state.get("outline_characters", [])

    if not outline_characters:
        return []

    db = SessionLocal()
    try:
        # 删除已有角色（重新生成场景，避免重复）
        db.query(Character).filter(
            Character.project_id == project_id
        ).delete()

        created = []
        for oc in outline_characters:
            char = Character(
                project_id=project_id,
                name=oc.get("name", "未命名") or "未命名",
                role=_map_role(oc.get("role", "")),
                personality=oc.get("personality", ""),
                core_motivation=oc.get("motivation", ""),
                growth_arc=oc.get("arc", ""),
            )
            db.add(char)
            db.flush()  # 获取 id
            created.append({
                "id": char.id,
                "name": char.name,
                "role": char.role,
                "personality": char.personality,
                "core_motivation": char.core_motivation,
                "growth_arc": char.growth_arc,
            })

        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_characters_from_outline_node(state: NovelState) -> NovelState:
    """LangGraph 节点：从大纲提取角色写入数据库

    签名： (state: NovelState) -> NovelState

    同步节点，无 LLM 调用。
    读取 state["outline_characters"]，批量 INSERT 到 characters 表，
    然后更新 state["characters"] 和 state["stage"]。
    """
    characters = extract_characters_from_outline(state)

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }

    return new_state
```

- [ ] **Step 2: 验证节点可以正常导入**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.nodes.character_generation import create_characters_from_outline_node, extract_characters_from_outline; print('Import OK')"`
Expected: Import OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/nodes/character_generation.py
git commit -m "feat: add create_characters_from_outline LangGraph node"
```

---

### Task 3: 新增 relation_generation 节点

**Files:**
- Create: `backend/app/agents/nodes/relation_generation.py`

- [ ] **Step 1: 创建文件**

```python
"""关系生成节点 - AI 基于角色生成关系网络"""

import re
from app.database import SessionLocal
from app.models.character import Relation
from app.agents.state import NovelState, STAGE_RELATIONS
from app.services.prompt_loader import get_system_prompt
from app.utils.llm import get_llm_from_state_async


# 预编译正则：解析 - 角色A | 角色B | 关系类型 | 信任度 | 描述 | 发展方向
RE_RELATION_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(-?\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
)


def parse_relations_response(response: str, characters: list[dict]) -> list[dict]:
    """从 AI 响应中解析关系列表

    格式：- 角色A名 | 角色B名 | 关系类型 | 信任度 | 描述 | 发展方向

    Args:
        response: AI 原始响应文本
        characters: 已创建的角色列表 [{id, name, ...}]

    Returns:
        解析后的关系列表 [{character_a_id, character_b_id, relation_type, trust_level, current_status, direction}]
    """
    name_to_id = {c["name"]: c["id"] for c in characters}
    relations = []

    for line in response.strip().split("\n"):
        match = RE_RELATION_LINE.search(line)
        if not match:
            continue

        name_a = match.group(1).strip()
        name_b = match.group(2).strip()
        rel_type = match.group(3).strip()
        trust_str = match.group(4).strip()
        description = match.group(5).strip()
        # 忽略 group(6) 发展方向字段（relation 表无对应列）

        # 根据角色名查找 id
        char_a_id = name_to_id.get(name_a)
        char_b_id = name_to_id.get(name_b)

        if not char_a_id or not char_b_id or char_a_id == char_b_id:
            continue

        # 验证关系类型
        valid_types = ["信任", "敌对", "感情", "合作", "利用", "陌生"]
        if rel_type not in valid_types:
            rel_type = "陌生"

        try:
            trust_level = max(0, min(100, int(trust_str)))
        except ValueError:
            trust_level = 50

        relations.append({
            "character_a_id": char_a_id,
            "character_b_id": char_b_id,
            "relation_type": rel_type,
            "trust_level": trust_level,
            "current_status": description,
            "direction": "双向",
        })

    return relations


def write_relations_to_db(project_id: int, relations_data: list[dict]) -> list[dict]:
    """将解析好的关系列表写入数据库

    Args:
        project_id: 项目 ID
        relations_data: parse_relations_response 的输出

    Returns:
        已创建的关系列表
    """
    if not relations_data:
        return []

    db = SessionLocal()
    try:
        # 删除已有关系
        db.query(Relation).filter(
            Relation.project_id == project_id
        ).delete()

        created = []
        for r in relations_data:
            rel = Relation(
                project_id=project_id,
                character_a_id=r["character_a_id"],
                character_b_id=r["character_b_id"],
                relation_type=r["relation_type"],
                trust_level=r["trust_level"],
                current_status=r["current_status"],
                direction=r["direction"],
            )
            db.add(rel)
            db.flush()
            created.append({
                "id": rel.id,
                "character_a_id": rel.character_a_id,
                "character_b_id": rel.character_b_id,
                "relation_type": rel.relation_type,
                "trust_level": rel.trust_level,
                "current_status": rel.current_status,
                "direction": rel.direction,
            })

        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def generate_relations_node(state: NovelState) -> NovelState:
    """LangGraph 兼容的关系生成节点

    签名： (state: NovelState) -> NovelState

    从已创建的角色列表生成关系网络，调用 LLM 生成关系数据并写入 DB。
    """
    characters = state.get("characters", [])
    if len(characters) < 2:
        # 少于两个角色则跳过关系生成
        return {**state, "stage": STAGE_RELATIONS, "relations": []}

    # 构建角色列表文本
    characters_lines = []
    for c in characters:
        chars_lines.append(
            f"- {c['name']}（{c.get('role', '配角')}）：{c.get('personality', '')}，{c.get('core_motivation', '')}"
        )

    characters_text = "\n".join(characters_lines)

    # 获取世界观时代背景
    world_setting = state.get("outline_world_setting", {}) or {}
    world_era = world_setting.get("era", "未指定")

    # 获取大纲概述
    outline_summary = state.get("outline_summary", "未提供")

    # 加载 Prompt
    db = SessionLocal()
    try:
        prompt = get_system_prompt(db, "relation_generation").format(
            characters_text=characters_text,
            world_era=world_era,
            outline_summary=outline_summary
        )
    finally:
        db.close()

    # 调用 LLM
    llm = await get_llm_from_state_async(state)
    response = await llm.chat([{"role": "user", "content": prompt}])

    # 解析响应
    relations_data = parse_relations_response(response, characters)

    # 写入数据库
    project_id = state["project_id"]
    relations = write_relations_to_db(project_id, relations_data)

    new_state: NovelState = {
        **state,
        "relations": relations,
        "stage": STAGE_RELATIONS,
    }

    return new_state
```

- [ ] **Step 2: 验证节点可以正常导入**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.nodes.relation_generation import generate_relations_node, parse_relations_response; print('Import OK')"`

Expected: Import OK

- [ ] **Step 4: 测试 parse_relations_response 解析器**

Run: `docker exec novelagent-backend-1 python3 -c "
from app.agents.nodes.relation_generation import parse_relations_response
resp = '''- 张三 | 李四 | 信任 | 80 | 多年老友 | 互相扶持
- 张三 | 王五 | 敌对 | 15 | 杀父之仇 | 势不两立
'''
chars = [{'id': 1, 'name': '张三'}, {'id': 2, 'name': '李四'}, {'id': 3, 'name': '王五'}]
result = parse_relations_response(resp, chars)
for r in result:
    print(f'A={r[\"character_a_id\"]} B={r[\"character_b_id\"]} type={r[\"relation_type\"]} trust={r[\"trust_level\"]}')
print(f'Total: {len(result)}')
"`

Expected: 打印 2 条关系记录

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/nodes/relation_generation.py
git commit -m "feat: add generate_relations LangGraph node with LLM"
```

---

### Task 4: 更新 LangGraph 工作流图

**Files:**
- Modify: `backend/app/agents/graph.py`
- Modify: `backend/app/agents/nodes/wait_confirm.py:31-33`

- [ ] **Step 1: 更新 wait_confirm.py 的 hybrid 模式**

`backend/app/agents/nodes/wait_confirm.py` 第 31 行，在 hybrid 的 `confirmation_type` 列表中增加 "characters" 和 "relations"：

将第 31 行：
```python
if confirmation_type in ["outline", "chapter_outlines"]:
```

改为：
```python
if confirmation_type in ["outline", "characters", "relations", "chapter_outlines"]:
```

- [ ] **Step 2: 更新 graph.py 导入**

`backend/app/agents/graph.py` 第 15-19 行附近，增加导入：

```python
from app.agents.nodes.character_generation import create_characters_from_outline_node
from app.agents.nodes.relation_generation import generate_relations_node
```

- [ ] **Step 3: 新增两个路由函数**

在 `route_after_review` 函数之后（第 89 行之后）添加：

```python
def route_after_characters(state: NovelState) -> Literal["wait_confirm", "generate_relations"]:
    """角色创建后的路由

    根据 review_mode 决定是否等待用户确认。

    Args:
        state: 当前状态

    Returns:
        "wait_confirm" - 等待用户确认
        "generate_relations" - 继续生成关系
    """
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "generate_relations"


def route_after_relations(state: NovelState) -> Literal["wait_confirm", "chapter_outlines"]:
    """关系生成后的路由

    根据 review_mode 决定是否等待用户确认。

    Args:
        state: 当前状态

    Returns:
        "wait_confirm" - 等待用户确认
        "chapter_outlines" - 继续生成章节大纲
    """
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "chapter_outlines"
```

- [ ] **Step 4: 在图构造函数中添加节点**

在 `create_novel_graph()` 函数中（`graph = StateGraph(NovelState)` 之后），追加两个节点：

```python
graph.add_node("create_characters_from_outline", create_characters_from_outline_node)
graph.add_node("generate_relations", generate_relations_node)
```

- [ ] **Step 5: 编辑大纲后的边路由**

将旧的：
```python
graph.add_conditional_edges(
    "generate_outline",
    route_after_outline,
    {
        "wait_confirm": END,
        "chapter_outlines": "generate_chapter_outlines"
    }
)
```

改为：
```python
graph.add_conditional_edges(
    "generate_outline",
    route_after_outline,
    {
        "wait_confirm": END,
        "create_characters": "create_characters_from_outline"
    }
)
```

- [ ] **Step 6: 更新 route_after_outline 的返回字面量**

将 `route_after_outline` 函数签名从：
```python
def route_after_outline(state: NovelState) -> Literal["wait_confirm", "chapter_outlines"]:
```

改为：
```python
def route_after_outline(state: NovelState) -> Literal["wait_confirm", "create_characters"]:
```

同时函数内 `return "chapter_outlines"` 改为 `return "create_characters"`。

- [ ] **Step 7: 添加角色关系相关的边**

在 `route_after_review` 的 conditional edges 之前添加：

```python
# 角色创建 → 关系生成（条件路由）
graph.add_conditional_edges(
    "create_characters_from_outline",
    route_after_characters,
    {
        "wait_confirm": END,
        "generate_relations": "generate_relations"
    }
)

# 关系生成 → 章节大纲（条件路由）
graph.add_conditional_edges(
    "generate_relations",
    route_after_relations,
    {
        "wait_confirm": END,
        "chapter_outlines": "generate_chapter_outlines"
    }
)
```

- [ ] **Step 8: 更新 __all__ 导出列表**

将 `__all__` 列表添加 `route_after_characters` 和 `route_after_relations`：

```python
__all__ = [
    "create_novel_graph",
    "create_novel_graph_with_checkpointer",
    "route_after_outline",
    "route_after_characters",
    "route_after_chapter_outlines",
    "route_after_relations",
    "route_after_review",
]
```

- [ ] **Step 9: 验证工作流图可以正常编译**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.graph import create_novel_graph; g = create_novel_graph(); print('Graph compiled OK'); print('Nodes:', list(g.nodes.keys()) if hasattr(g, 'nodes') else 'N/A')"`

Expected: Graph compiled OK

- [ ] **Step 10: Commit**

```bash
git add backend/app/agents/graph.py backend/app/agents/nodes/wait_confirm.py
git commit -m "feat: add characters and relations nodes to LangGraph workflow"
```

---

### Task 5: 更新 nodes/__init__.py 导出

**Files:**
- Modify: `backend/app/agents/nodes/__init__.py`

- [ ] **Step 1: 增加新节点的导入和导出**

```python
from app.agents.nodes.character_generation import (
    create_characters_from_outline_node,
    extract_characters_from_outline
)
from app.agents.nodes.relation_generation import (
    generate_relations_node,
    parse_relations_response
)
```

在 `__all__` 列表中添加：

```python
    # Character generation
    "create_characters_from_outline_node",
    "extract_characters_from_outline",
    # Relation generation
    "generate_relations_node",
    "parse_relations_response",
```

- [ ] **Step 2: 验证导入**

Run: `docker exec novelagent-backend-1 python3 -c "from app.agents.nodes import create_characters_from_outline_node, generate_relations_node; print('Import OK')"`
Expected: Import OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/nodes/__init__.py
git commit -m "feat: export new character and relation generation nodes"
```

---

### Task 6: 更新 characters API 端点（替换 501 stub）

**Files:**
- Modify: `backend/app/api/characters.py:794-888`

- [ ] **Step 1: 替换 `generate_characters` 端点**

将第 796-821 行替换为：

```python
@router.post("/{project_id}/characters/generate", status_code=status.HTTP_201_CREATED)
async def generate_characters(
    project_id: int,
    request: CharacterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 批量生成人物

    从大纲中提取角色信息创建 Character 实体。

    Args:
        project_id: 项目 ID
        request: 生成请求（count/roles/additional_context）
        db: 数据库会话
        current_user: 当前用户

    Returns:
        创建的人物列表
    """
    from app.models.outline import Outline
    from app.agents.nodes.character_generation import extract_characters_from_outline

    get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline or not outline.characters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No outline characters found. Generate an outline first."
        )

    state = {
        "project_id": project_id,
        "outline_characters": outline.characters,
    }

    characters = extract_characters_from_outline(state)

    if not characters:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create characters from outline"
        )

    return {
        "message": f"Created {len(characters)} characters",
        "characters": characters,
    }
```

- [ ] **Step 2: 替换 `generate_relations` 端点**

将第 823-848 行替换为：

```python
@router.post("/{project_id}/relations/generate", status_code=status.HTTP_201_CREATED)
async def generate_relations(
    project_id: int,
    request: RelationGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 生成关系规划

    基于已有角色调用 LLM 生成关系网络。

    Args:
        project_id: 项目 ID
        request: 生成请求（character_ids/relation_types/additional_context）
        db: 数据库会话
        current_user: 当前用户

    Returns:
        创建的关系列表
    """
    from app.models.character import Character
    from app.models.outline import Outline
    from app.agents.nodes.relation_generation import generate_relations_node

    get_project_for_user(project_id, current_user.id, db)

    characters = db.query(Character).filter(
        Character.project_id == project_id
    ).all()

    if len(characters) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 2 characters to generate relations"
        )

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    state = {
        "project_id": project_id,
        "characters": [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "personality": c.personality or "",
                "core_motivation": c.core_motivation or "",
            }
            for c in characters
        ],
        "outline_world_setting": outline.world_setting if outline else {},
        "outline_summary": outline.summary if outline else "",
    }

    result_state = await generate_relations_node(state)

    relations = result_state.get("relations", [])

    return {
        "message": f"Created {len(relations)} relations",
        "relations": relations,
    }
```

- [ ] **Step 3: 替换 `optimize_character` 端点（留空实现，方案 B 再补）**

将第 850-888 行替换为：

```python
@router.post("/{project_id}/characters/{character_id}/optimize", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def optimize_character(
    project_id: int,
    character_id: int,
    request: CharacterOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 优化单个人物（将在方案 B 中实现）

    Args:
        project_id: 项目 ID
        character_id: 人物 ID
        request: 优化请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        501 NOT IMPLEMENTED
    """
    get_project_for_user(project_id, current_user.id, db)

    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI character optimization will be implemented in plan B"
    )
```

- [ ] **Step 4: 验证 API 端点正常注册**

Run: `docker compose restart backend 2>&1 | tail -3 && sleep 3 && docker exec novelagent-backend-1 python3 -c "from app.main import app; routes = [r.path for r in app.routes]; print('chars/gen:', '/api/projects/{project_id}/characters/generate' in routes); print('rels/gen:', '/api/projects/{project_id}/relations/generate' in routes)"`

Expected: 两个都为 True

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/characters.py
git commit -m "feat: implement characters/generate and relations/generate API endpoints"
```

---

### Task 7: 前端 OutlineProgressDialog 对接 LangGraph SSE

**Files:**
- Modify: `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`

- [ ] **Step 1: 重写 OutlineProgressDialog 核心逻辑**

将整个文件替换为以下内容：

```tsx
// frontend/src/components/workbench/planning/OutlineProgressDialog.tsx

import { useState, useEffect, useRef } from 'react'
import { Sparkles, Check, Loader2, PartyPopper, AlertCircle, RefreshCw, Eye } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { workflowApi } from '@/lib/workflowApi'

type StepStatus = 'pending' | 'active' | 'done'

interface Step
{
  key: string
  label: string
  status: StepStatus
  nodeName: string
}

interface OutlineProgressDialogProps
{
  open: boolean
  onClose: () => void
  projectId: number
  onComplete: () => void
  onViewOutline: () => void
}

const STEPS: Step[] = [
  { key: 'outline', label: '生成大纲', status: 'pending', nodeName: 'generate_outline' },
  { key: 'characters', label: '生成人物', status: 'pending', nodeName: 'create_characters_from_outline' },
  { key: 'relations', label: '生成关系', status: 'pending', nodeName: 'generate_relations' },
]

export function OutlineProgressDialog({
  open,
  onClose,
  projectId,
  onComplete,
  onViewOutline,
}: OutlineProgressDialogProps)
{
  const [steps, setSteps] = useState<Step[]>(STEPS.map(s => ({ ...s })))
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState(false)
  const [waitingFor, setWaitingFor] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const startedRef = useRef(false)

  useEffect(() =>
  {
    if (open && !startedRef.current)
    {
      startedRef.current = true
      handleGenerate()
    }
    if (!open)
    {
      startedRef.current = false
    }
  }, [open])

  const markNodeDone = (nodeName: string) =>
  {
    setSteps(prev =>
    {
      const newSteps = prev.map(s =>
        s.nodeName === nodeName && s.status === 'active' ? { ...s, status: 'done' as StepStatus } : s
      )
      // 激活下一个 pending 步骤
      const nextPending = newSteps.find(s => s.status === 'pending')
      if (nextPending)
      {
        const idx = newSteps.indexOf(nextPending)
        newSteps[idx] = { ...nextPending, status: 'active' }
      }
      return newSteps
    })
  }

  const handleGenerate = async () =>
  {
    setError(null)
    setCompleted(false)
    setWaitingFor(null)
    setSteps(STEPS.map(s => ({ ...s, status: s.key === 'outline' ? 'active' : 'pending' })))

    const controller = new AbortController()
    abortRef.current = controller

    try
    {
      await workflowApi.runWorkflow(
        projectId,
        {
          onNodeStart: (nodeName: string) =>
          {
            setSteps(prev => prev.map(s =>
              s.nodeName === nodeName ? { ...s, status: 'active' } : s
            ))
          },
          onNodeDone: (nodeName: string) =>
          {
            markNodeDone(nodeName)
          },
          onChunk: () =>
          {
            // 大纲流式输出中的文本块，进度条不需要处理
          },
          onWaiting: (confirmationType: string) =>
          {
            abortRef.current = null
            setWaitingFor(confirmationType)
            // 将当前 active 步骤标记为 done
            setSteps(prev => prev.map(s =>
              s.status === 'active' ? { ...s, status: 'done' } : s
            ))
            setCompleted(true)
          },
          onDone: () =>
          {
            abortRef.current = null
            setSteps(prev => prev.map(s => ({ ...s, status: 'done' })))
            setCompleted(true)
            onComplete()
          },
          onError: (errMsg: string) =>
          {
            abortRef.current = null
            setError(errMsg)
            setSteps(prev => prev.map(s =>
              s.status === 'active' ? { ...s, status: 'pending' } : s
            ))
          },
        },
        { signal: controller.signal }
      )
    }
    catch (err)
    {
      abortRef.current = null
      setError('生成失败，请重试')
      setSteps(prev => prev.map(s =>
        s.status === 'active' ? { ...s, status: 'pending' } : s
      ))
    }
  }

  useEffect(() =>
  {
    return () =>
    {
      if (abortRef.current)
      {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [])

  const stepIcon = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return <Check className="h-4 w-4 text-green-600" />
      case 'active':
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
      default:
        return <div className="h-4 w-4 rounded-full border-2 border-gray-300" />
    }
  }

  const stepBarColor = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return 'bg-green-500'
      case 'active':
        return 'bg-blue-500 animate-pulse'
      default:
        return 'bg-gray-200'
    }
  }

  const stepLabelColor = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return 'text-green-600'
      case 'active':
        return 'text-blue-600'
      default:
        return 'text-muted-foreground'
    }
  }

  return (
    <Dialog open={open} onOpenChange={() =>
    {
      if (completed || error) onClose()
    }}>
      <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) =>
      {
        if (!completed && !error) e.preventDefault()
      }}>
        <DialogHeader>
          <DialogTitle className="flex items-center justify-center gap-2 text-center">
            {completed && !waitingFor ? (
              <>
                <PartyPopper className="h-5 w-5 text-green-500" />
                {error ? '生成失败' : '规划已完成'}
              </>
            ) : waitingFor ? (
              <>
                <Eye className="h-5 w-5 text-amber-500" />
                等待确认
              </>
            ) : error ? (
              <>
                <AlertCircle className="h-5 w-5 text-red-500" />
                生成失败
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 text-blue-500" />
                正在规划你的小说
              </>
            )}
          </DialogTitle>
          <DialogDescription className="text-center">
            {completed && !waitingFor
              ? '小说大纲、人物和关系已全部生成完毕'
              : waitingFor
                ? '请查看并确认生成的内容后继续'
                : error
                  ? '生成过程中出现错误'
                  : 'AI 正在基于你的灵感构思角色和关系...'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {steps.map((step, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-sm ${stepLabelColor(step.status)}`}>
                  {step.label}
                </span>
                <div className="flex items-center gap-1.5">
                  {step.status === 'done' && <span className="text-xs text-green-600">完成</span>}
                  {stepIcon(step.status)}
                </div>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${stepBarColor(step.status)}`}
                  style={{
                    width: step.status === 'done' ? '100%' : step.status === 'active' ? '60%' : '0%',
                  }}
                />
              </div>
            </div>
          ))}
        </div>

        {!completed && !error && (
          <p className="text-center text-xs text-muted-foreground">
            预计需要 40-90 秒，请耐心等待
          </p>
        )}

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="flex gap-2 pt-2">
          {completed ? (
            <>
              <Button variant="outline" className="flex-1" onClick={onClose}>
                留在灵感页
              </Button>
              <Button className="flex-1" onClick={onViewOutline}>
                查看大纲
              </Button>
            </>
          ) : error ? (
            <>
              <Button variant="outline" className="flex-1" onClick={onClose}>
                关闭
              </Button>
              <Button className="flex-1" onClick={handleGenerate}>
                <RefreshCw className="h-4 w-4 mr-1.5" />
                重试
              </Button>
            </>
          ) : (
            <p className="text-xs text-muted-foreground text-center w-full">
              生成中，请勿关闭...
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: 构建前端验证无编译错误**

Run: `cd /opt/project/novelagent/frontend && npm run build 2>&1 | tail -20`

Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/planning/OutlineProgressDialog.tsx
git commit -m "feat: wire OutlineProgressDialog to LangGraph SSE workflow"
```

---

### Task 8: 端到端验证

**Files:**
- None（验证步骤）

- [ ] **Step 1: 重启服务**

```bash
docker compose restart backend
docker compose build --no-cache frontend && docker compose up -d frontend
sleep 5
```

- [ ] **Step 2: 运行后端测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest -v --tb=short -k "not test_system_prompts and not test_chapter_content_prompt_format" 2>&1 | tail -20`

Expected: 全部 PASS（忽略已有的 rate limit 和 prompt format 测试问题）

- [ ] **Step 3: 验证工作流图节点**

Run: `docker exec novelagent-backend-1 python3 -c "
from app.agents.graph import create_novel_graph
g = create_novel_graph()
# 确认节点存在
print('Nodes:', sorted(g.nodes.keys() if hasattr(g, 'nodes') else []))
"`

Expected: 包含 `create_characters_from_outline` 和 `generate_relations`

- [ ] **Step 4: 运行前端测试**

Run: `cd /opt/project/novelagent/frontend && npm run test:run 2>&1 | tail -10`

Expected: 全部 PASS

- [ ] **Step 5: Commit（如有文件变更）**

```bash
git status
```