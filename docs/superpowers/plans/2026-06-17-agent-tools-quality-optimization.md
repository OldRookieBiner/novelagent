# Agent 工具质量优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 5 对 create/update 工具合并、消除 N+1 查询、集中硬编码工具名常量、封装 advance_phase 的 DB session

**Architecture:** 4 项优化按依赖顺序执行：先建基础设施（Store 方法 + 工具函数），再改造工具（合并 create/update），再改基础设施代码（常量集中 + WorkflowStore），最后更新前端和测试

**Tech Stack:** Python 3.11+, FastAPI, LangChain @tool, SQLAlchemy, pytest, React + TypeScript (frontend)

## Global Constraints

- 所有对话和注释使用中文
- 后端代码风格：snake_case, Allman 大括号, 中文注释
- 前端代码风格：camelCase, lucide-react 图标
- 后端改 Python 源码后需 `docker compose restart backend`
- 前端改 TS 源码后需 `docker compose build --no-cache frontend && docker compose up -d frontend`
- 测试：`docker exec novelagent-backend-1 pytest -v`
- 参数默认值规则：
  - 普通字符串/整数字段：update 路径可选字段默认 `None`，create 路径用 `if val:` 过滤，update 路径用 `if v is not None` 过滤
  - JSON 字符串参数（must_happen, questions_to_*, characters, related_characters 等）：同样默认 `None`，create 路径用 `or "[]"` 兜底，update 路径用 `if v is not None` 过滤。禁止用 `"[]"` 默认值——`"[]"` 非 None 会导致 update 路径无法区分"Agent 没传"和"Agent 想清空"
- REST API 层 (`api/`) 和 Store 方法名不在合并范围，不受影响
- 禁止打补丁式修复——发现 bug 定位根因

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/app/agents/services/stores/plot_store.py` | 新增 3 个 get_by_id 方法 |
| 修改 | `backend/app/agents/tools/utils.py` | 新增 build_changes_diff，修复 _get_current_value N+1 |
| 修改 | `backend/app/agents/tools/creation/character.py` | 合并 create_character + update_character |
| 修改 | `backend/app/agents/tools/creation/foreshadowing.py` | 合并 create_foreshadowing + update_foreshadowing |
| 修改 | `backend/app/agents/tools/creation/plot_block.py` | 合并 create_plot_block + update_plot_block |
| 修改 | `backend/app/agents/tools/creation/subplot.py` | 合并 create_subplot + update_subplot |
| 修改 | `backend/app/agents/tools/creation/plot_question.py` | 合并 create_plot_question + update_plot_question |
| 修改 | `backend/app/agents/tools/creation/delete_plot_block.py` | 修复 N+1，更新 hint 文本 |
| 删除 | `backend/app/agents/tools/creation/update_character.py` | 已合并到 character.py |
| 删除 | `backend/app/agents/tools/creation/update_foreshadowing.py` | 已合并到 foreshadowing.py |
| 删除 | `backend/app/agents/tools/creation/update_plot_block.py` | 已合并到 plot_block.py |
| 删除 | `backend/app/agents/tools/creation/update_subplot.py` | 已合并到 subplot.py |
| 删除 | `backend/app/agents/tools/creation/update_plot_question.py` | 已合并到 plot_question.py |
| 修改 | `backend/app/agents/tools/creation/__init__.py` | 移除 5 个 update_* import |
| 修改 | `backend/app/agents/tools/registry.py` | 移除 5 个 update_* import，新增 PERCEPTION_TOOL_NAMES / WRITING_TOOL_NAMES |
| 修改 | `backend/app/agents/agent_graph.py` | 引用常量替换硬编码 |
| 新建 | `backend/app/agents/services/stores/workflow_store.py` | WorkflowStore 类 |
| 修改 | `backend/app/agents/services/stores/__init__.py` | 新增 WorkflowStore import |
| 修改 | `backend/app/agents/services/knowledge_base.py` | 新增 self.workflows 属性 |
| 修改 | `backend/app/agents/tools/creation/advance_phase.py` | 简化为调用 kb.workflows |
| 修改 | `frontend/src/components/workbench/AgentChatPanel.tsx` | 更新工具名映射 |
| 修改 | `backend/tests/test_agent_tools.py` | 更新 import 和测试用例 |

---

### Task 1: PlotStore 新增 3 个 get_by_id 方法

**Files:**
- 修改: `backend/app/agents/services/stores/plot_store.py`
- 测试: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: 无（独立基础任务）
- Produces: `PlotStore.get_plot_block_by_id(id: int) -> dict | None`, `PlotStore.get_subplot_by_id(id: int) -> dict | None`, `PlotStore.get_plot_question_by_id(id: int) -> dict | None`

- [ ] **Step 1: 写 PlotStore 新增方法的测试**

在 `backend/tests/test_agent_tools.py` 末尾新增测试类，测试 3 个 get_by_id 方法的正常返回和 None 返回。使用 mock KnowledgeBaseService 的方式（与现有测试模式一致），验证方法被正确调用。

```python
class TestPlotStoreGetById:
    """PlotStore get_by_id 方法测试"""

    def test_get_plot_block_by_id_returns_dict(self):
        from app.agents.services.stores.plot_store import PlotStore
        store = PlotStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_obj = MagicMock()
            mock_obj.id = 1
            mock_obj.title = "test"
            mock_obj.chapter_start = 1
            mock_obj.chapter_end = 5
            mock_obj.project_id = 1
            mock_db.query.return_value.filter.return_value.first.return_value = mock_obj
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            mock_session.return_value.readonly = True
            result = store.get_plot_block_by_id(1)
            assert result is not None
            assert result["id"] == 1

    def test_get_plot_block_by_id_not_found(self):
        from app.agents.services.stores.plot_store import PlotStore
        store = PlotStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            result = store.get_plot_block_by_id(999)
            assert result is None

    def test_get_subplot_by_id_not_found(self):
        from app.agents.services.stores.plot_store import PlotStore
        store = PlotStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            result = store.get_subplot_by_id(999)
            assert result is None

    def test_get_plot_question_by_id_not_found(self):
        from app.agents.services.stores.plot_store import PlotStore
        store = PlotStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            result = store.get_plot_question_by_id(999)
            assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestPlotStoreGetById -v`
Expected: FAIL（方法不存在）

- [ ] **Step 3: 在 PlotStore 中实现 3 个方法**

在 `backend/app/agents/services/stores/plot_store.py` 的 `PlotStore` 类中添加 3 个方法，位于对应的 `list_*` 方法之后。每个方法模式一致：

```python
    def get_plot_block_by_id(self, id: int) -> Optional[dict]:
        """按 ID 获取单个情节块, 不存在返回 None"""
        with self.session(readonly=True) as db:
            obj = db.query(PlotBlock).filter(
                PlotBlock.id == id,
                PlotBlock.project_id == self.project_id,
            ).first()
            return self._to_dict(obj)
```

```python
    def get_plot_question_by_id(self, id: int) -> Optional[dict]:
        """按 ID 获取单个问题, 不存在返回 None"""
        with self.session(readonly=True) as db:
            obj = db.query(PlotQuestion).filter(
                PlotQuestion.id == id,
                PlotQuestion.project_id == self.project_id,
            ).first()
            return self._to_dict(obj)
```

```python
    def get_subplot_by_id(self, id: int) -> Optional[dict]:
        """按 ID 获取单个支线, 不存在返回 None"""
        with self.session(readonly=True) as db:
            obj = db.query(Subplot).filter(
                Subplot.id == id,
                Subplot.project_id == self.project_id,
            ).first()
            return self._to_dict(obj)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestPlotStoreGetById -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/services/stores/plot_store.py backend/tests/test_agent_tools.py
git commit -m "feat(db): add get_by_id methods to PlotStore for N+1 elimination"
```

### Task 2: 新增 build_changes_diff 工具函数 + 修复 _get_current_value N+1

**Files:**
- 修改: `backend/app/agents/tools/utils.py`

**Interfaces:**
- Consumes: 无
- Produces: `build_changes_diff(before: dict, update_data: dict) -> dict`（供 Task 3-6 的合并工具使用）

- [ ] **Step 1: 写 build_changes_diff 的测试**

在 `backend/tests/test_agent_tools.py` 末尾新增：

```python
class TestBuildChangesDiff:
    """build_changes_diff 工具函数测试"""

    def test_no_changes(self):
        from app.agents.tools.utils import build_changes_diff
        before = {"name": "Alice", "role": "hero"}
        update_data = {"name": "Alice", "role": "hero"}
        result = build_changes_diff(before, update_data)
        assert result == {}

    def test_some_changes(self):
        from app.agents.tools.utils import build_changes_diff
        before = {"name": "Alice", "role": "hero", "personality": "brave"}
        update_data = {"name": "Alice", "role": "villain", "personality": "brave"}
        result = build_changes_diff(before, update_data)
        assert "role" in result
        assert result["role"]["before"] == "hero"
        assert result["role"]["after"] == "villain"
        assert "name" not in result

    def test_new_field(self):
        from app.agents.tools.utils import build_changes_diff
        before = {"name": "Alice"}
        update_data = {"name": "Alice", "personality": "brave"}
        result = build_changes_diff(before, update_data)
        assert "personality" in result
        assert result["personality"]["before"] is None
        assert result["personality"]["after"] == "brave"

    def test_list_comparison(self):
        """JSON 列反序列化后可正确比较"""
        from app.agents.tools.utils import build_changes_diff
        before = {"must_happen": ["event1", "event2"]}
        update_data = {"must_happen": ["event1", "event3"]}
        result = build_changes_diff(before, update_data)
        assert "must_happen" in result
        assert result["must_happen"]["before"] == ["event1", "event2"]
        assert result["must_happen"]["after"] == ["event1", "event3"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestBuildChangesDiff -v`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 在 utils.py 中实现 build_changes_diff**

在 `backend/app/agents/tools/utils.py` 的 `parse_json_param` 函数之后添加：

```python
def build_changes_diff(before: dict, update_data: dict) -> dict:
    """对比 before 和 update_data, 返回 {field: {before, after}} 格式的变更记录.

    只包含实际发生变化的字段(before[key] != update_data[key]).

    前置条件: 调用方应确保 update_data 中不含 None 值(由 if v is not None 过滤),
    如果 update_data 残留 None 值, before 中对应的非 None 值将被记录为变更.

    依赖 SQLAlchemy JSON 列的自动反序列化, before 和 update_data 中的
    list/dict 类型可直接用 != 比较(比较元素值而非引用).
    """
    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}
    return changes
```

- [ ] **Step 4: 修复 _get_current_value 的 N+1 查询**

在 `backend/app/agents/tools/utils.py` 的 `_get_current_value` 函数中，将 character 分支从 list 遍历改为直接查询：

旧代码：
```python
    elif target_type == "character":
        chars = kb.characters.list_characters()
        for c in chars:
            if c["id"] == target_id:
                return c
```

新代码：
```python
    elif target_type == "character":
        char = kb.characters.get_character(target_id)
        if char:
            return char
    # relation 分支暂保留 list 遍历:
    # 1) 关系数量通常很少, N+1 影响小; 2) CharacterStore 无 get_relation(id)
    # 后续如需优化可新增 CharacterStore.get_relation(id)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestBuildChangesDiff -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/agents/tools/utils.py backend/tests/test_agent_tools.py
git commit -m "feat(tools): add build_changes_diff and fix _get_current_value N+1"
```

### Task 3: 合并 create_character + update_character

**Files:**
- 修改: `backend/app/agents/tools/creation/character.py`
- 删除: `backend/app/agents/tools/creation/update_character.py`
- 修改: `backend/app/agents/tools/creation/__init__.py`
- 修改: `backend/app/agents/tools/registry.py`

**Interfaces:**
- Consumes: `kb.characters.get_character(id)` (已有), `kb.characters.update_character(id, data)` (已有), `build_changes_diff()` (Task 2)
- Produces: 合并后的 `create_character` 工具（支持 `character_id` 参数双模式）

- [ ] **Step 1: 写合并后 create_character 的测试**

在 `backend/tests/test_agent_tools.py` 末尾新增：

```python
class TestCreateCharacterMerge:
    """合并后 create_character 双模式测试"""

    @patch("app.agents.tools.creation.character._kb")
    def test_create_mode_requires_name_and_role(self, mock_kb_cls):
        """create 路径: 缺少 name 或 role 返回 error"""
        from app.agents.tools.creation.character import create_character
        import asyncio
        result = asyncio.run(create_character.ainvoke({"name": "", "role": ""}))
        assert "error" in result

    @patch("app.agents.tools.creation.character._kb")
    def test_create_mode_success(self, mock_kb_cls):
        """create 路径: 正常创建角色"""
        from app.agents.tools.creation.character import create_character
        import asyncio
        mock_kb = MagicMock()
        mock_kb.characters.create_character.return_value = {"id": 1, "name": "Alice", "role": "hero"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_character.ainvoke({"name": "Alice", "role": "hero"}))
        assert result["action"] == "created"
        assert result["id"] == 1

    @patch("app.agents.tools.creation.character._kb")
    def test_update_mode_with_character_id(self, mock_kb_cls):
        """update 路径: 传入 character_id 进入更新模式"""
        from app.agents.tools.creation.character import create_character
        import asyncio
        mock_kb = MagicMock()
        mock_kb.characters.get_character.return_value = {"id": 5, "name": "Alice", "role": "hero", "personality": "brave"}
        mock_kb.characters.update_character.return_value = {"id": 5, "name": "Alice", "role": "villain", "personality": "brave"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_character.ainvoke({"character_id": 5, "role": "villain"}))
        assert "updated_fields" in result
        mock_kb.characters.get_character.assert_called_once_with(5)

    @patch("app.agents.tools.creation.character._kb")
    def test_update_mode_not_found(self, mock_kb_cls):
        """update 路径: character_id 不存在返回 error"""
        from app.agents.tools.creation.character import create_character
        import asyncio
        mock_kb = MagicMock()
        mock_kb.characters.get_character.return_value = None
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_character.ainvoke({"character_id": 999, "name": "Alice"}))
        assert "error" in result

    @patch("app.agents.tools.creation.character._kb")
    def test_update_mode_none_default_not_written(self, mock_kb_cls):
        """update 路径: None 默认值不写入 update_data"""
        from app.agents.tools.creation.character import create_character
        import asyncio
        mock_kb = MagicMock()
        mock_kb.characters.get_character.return_value = {"id": 5, "name": "Alice", "role": "hero"}
        mock_kb.characters.update_character.return_value = {"id": 5, "name": "Alice", "role": "hero"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_character.ainvoke({"character_id": 5, "role": "hero"}))
        call_args = mock_kb.characters.update_character.call_args
        update_data = call_args[0][1]
        # personality 等未传字段应为 None 默认值, 不应出现在 update_data 中
        assert "personality" not in update_data
        assert "catchphrase" not in update_data
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreateCharacterMerge -v`
Expected: FAIL（character.py 尚未合并）

- [ ] **Step 3: 改写 character.py 为合并版本**

将 `backend/app/agents/tools/creation/character.py` 完整替换为：

```python
"""创建/更新角色工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff


@tool
async def create_character(
    character_id: int = 0,
    name: str = "",
    role: str = "",
    personality: str | None = None,
    catchphrase: str | None = None,
    habit_action: str | None = None,
    deep_fear: str | None = None,
    core_motivation: str | None = None,
    growth_arc: str | None = None,
    appearance: str | None = None,
    backstory: str | None = None,
    signature_item: str | None = None,
) -> dict:
    """创建新角色或更新已有角色. 提供 character_id 时为更新模式.

    - character_id=0(默认): 创建新角色(name 和 role 必填)
    - character_id>0: 更新指定 ID 的角色. None 表示不修改, 空字符串 "" 表示清空字段

    Args:
        character_id: 角色 ID(非零时更新已有角色)
        name: 角色名
        role: 角色定位 - 可选值: 主角, 核心反派, 重要配角, 配角
        personality: 性格特征描述
        catchphrase: 口头禅或典型语言风格
        habit_action: 习惯动作或姿态
        deep_fear: 深层恐惧
        core_motivation: 驱动角色行动的核心动机
        growth_arc: 成长弧线/角色发展轨迹
        appearance: 外貌描写
        backstory: 背景故事
        signature_item: 标志性物品或配饰
    """
    kb = _kb()

    if character_id:
        # --- 更新路径 ---
        before = kb.characters.get_character(character_id)
        if not before:
            return {"error": f"角色 ID {character_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "name", "role", "personality", "catchphrase", "habit_action",
            "deep_fear", "core_motivation", "growth_arc", "appearance",
            "backstory", "signature_item",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "character_id": character_id}

        updated = kb.characters.update_character(character_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "character_id": character_id,
            "name": updated.get("name", before.get("name")),
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"角色「{updated.get('name')}」已更新 {len(changes)} 个字段",
        }
    else:
        # --- 创建路径 ---
        if not name or not role:
            return {"error": "创建角色时 name 和 role 为必填字段"}

        data = {"name": name, "role": role}
        for key, val in [
            ("personality", personality), ("catchphrase", catchphrase),
            ("habit_action", habit_action), ("deep_fear", deep_fear),
            ("core_motivation", core_motivation), ("growth_arc", growth_arc),
            ("appearance", appearance), ("backstory", backstory),
            ("signature_item", signature_item),
        ]:
            if val:
                data[key] = val
        char = kb.characters.create_character(data)
        return {
            "action": "created",
            "id": char["id"],
            "name": char["name"],
            "role": char["role"],
            "message": f"角色「{name}」已创建并写入知识库",
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreateCharacterMerge -v`
Expected: PASS

- [ ] **Step 5: 删除 update_character.py**

```bash
rm backend/app/agents/tools/creation/update_character.py
```

- [ ] **Step 6: 更新 __init__.py — 移除 update_character import**

在 `backend/app/agents/tools/creation/__init__.py` 中删除 `update_character` 的 import 行。

- [ ] **Step 7: 更新 registry.py — 移除 update_character import 和列表条目**

在 `backend/app/agents/tools/registry.py` 中：
1. 删除 `from app.agents.tools.creation import (...)` 中的 `update_character`
2. 从 `_STRUCTURE_EXTRA` 列表中移除 `update_character`

- [ ] **Step 8: 运行全量测试确认无破坏**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: PASS（可能有 test_change_workflow 的 import 失败，后续 Task 7 统一修复）

- [ ] **Step 9: 提交**

```bash
git add -A
git commit -m "feat(tools): merge update_character into create_character with dual-mode"
```

### Task 4: 合并 create_plot_question + update_plot_question

**Files:**
- 修改: `backend/app/agents/tools/creation/plot_question.py`
- 删除: `backend/app/agents/tools/creation/update_plot_question.py`

**Interfaces:**
- Consumes: `kb.plots.get_plot_question_by_id(id)` (Task 1), `kb.plots.update_plot_question(id, data)` (已有), `build_changes_diff()` (Task 2)
- Produces: 合并后的 `create_plot_question` 工具（支持 `question_id` 参数双模式）

- [ ] **Step 1: 写合并后 create_plot_question 的测试**

```python
class TestCreatePlotQuestionMerge:
    """合并后 create_plot_question 双模式测试"""

    @patch("app.agents.tools.creation.plot_question._kb")
    def test_create_mode_requires_question_text(self, mock_kb_cls):
        """create 路径: 缺少 question_text 返回 error"""
        from app.agents.tools.creation.plot_question import create_plot_question
        import asyncio
        result = asyncio.run(create_plot_question.ainvoke({"question_text": ""}))
        assert "error" in result

    @patch("app.agents.tools.creation.plot_question._kb")
    def test_update_mode_with_question_id(self, mock_kb_cls):
        """update 路径: 传入 question_id 进入更新模式"""
        from app.agents.tools.creation.plot_question import create_plot_question
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.get_plot_question_by_id.return_value = {"id": 3, "question_text": "谁杀了X?", "status": "pending"}
        mock_kb.plots.update_plot_question.return_value = {"id": 3, "question_text": "谁杀了X?", "status": "answered"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_plot_question.ainvoke({"question_id": 3, "status": "answered"}))
        assert "updated_fields" in result
        mock_kb.plots.get_plot_question_by_id.assert_called_once_with(3)

    @patch("app.agents.tools.creation.plot_question._kb")
    def test_update_mode_not_found(self, mock_kb_cls):
        """update 路径: question_id 不存在返回 error"""
        from app.agents.tools.creation.plot_question import create_plot_question
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.get_plot_question_by_id.return_value = None
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_plot_question.ainvoke({"question_id": 999, "question_text": "test"}))
        assert "error" in result

    @patch("app.agents.tools.creation.plot_question._kb")
    def test_update_only_fields_not_in_create(self, mock_kb_cls):
        """update 路径的独有字段(answered_in_chapter, status)在 create 路径不使用"""
        from app.agents.tools.creation.plot_question import create_plot_question
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.get_plot_question_by_id.return_value = {"id": 3, "question_text": "Q", "status": "pending"}
        mock_kb.plots.update_plot_question.return_value = {"id": 3, "question_text": "Q", "status": "answered", "answered_in_chapter": 5}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_plot_question.ainvoke({"question_id": 3, "answered_in_chapter": 5}))
        call_args = mock_kb.plots.update_plot_question.call_args
        update_data = call_args[0][1]
        assert "answered_in_chapter" in update_data
        assert "status" not in update_data  # 未传, 不在 update_data 中
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreatePlotQuestionMerge -v`
Expected: FAIL

- [ ] **Step 3: 改写 plot_question.py 为合并版本**

将 `backend/app/agents/tools/creation/plot_question.py` 完整替换为：

```python
"""创建/更新问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff


@tool
async def create_plot_question(
    question_id: int = 0,
    question_text: str = "",
    raised_in_chapter: int | None = None,
    plot_block_id: int | None = None,
    # 以下仅 update 路径
    answered_in_chapter: int | None = None,
    status: str | None = None,
) -> dict:
    """创建新问题或更新已有问题. 提供 question_id 时为更新模式.

    - question_id=0(默认): 创建新问题(question_text 必填)
    - question_id>0: 更新指定 ID 的问题. None 表示不修改

    Args:
        question_id: 问题 ID(非零时更新已有问题)
        question_text: 问题内容
        raised_in_chapter: 提出问题的章节号
        plot_block_id: 所属情节块 ID
        answered_in_chapter: 回答问题的章节号(仅更新模式)
        status: 新状态 - "pending"(待回答), "answered"(已回答), "closed"(已关闭)(仅更新模式)
    """
    kb = _kb()

    if question_id:
        # --- 更新路径 ---
        before = kb.plots.get_plot_question_by_id(question_id)
        if not before:
            return {"error": f"问题链 ID {question_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "question_text", "raised_in_chapter", "plot_block_id",
            "answered_in_chapter", "status",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "question_id": question_id}

        updated = kb.plots.update_plot_question(question_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "question_id": question_id,
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"问题链 {question_id} 已更新({', '.join(changes.keys())})",
        }
    else:
        # --- 创建路径 ---
        if not question_text:
            return {"error": "创建问题时 question_text 为必填字段"}

        data = {"question_text": question_text, "status": "pending"}
        if raised_in_chapter is not None:
            data["raised_in_chapter"] = raised_in_chapter
        if plot_block_id is not None:
            data["plot_block_id"] = plot_block_id

        q = kb.plots.create_plot_question(data)
        return {
            "action": "created",
            "id": q["id"],
            "question_text": question_text[:80],
            "message": f"问题「{question_text[:60]}」已创建并写入知识库",
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreatePlotQuestionMerge -v`
Expected: PASS

- [ ] **Step 5: 删除 update_plot_question.py**

```bash
rm backend/app/agents/tools/creation/update_plot_question.py
```

- [ ] **Step 6: 更新 __init__.py 和 registry.py**

同 Task 3 的 Step 6-7 模式：在 `creation/__init__.py` 删除 `update_plot_question` import，在 `registry.py` 删除 import 和 `_STRUCTURE_EXTRA` 中的条目。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat(tools): merge update_plot_question into create_plot_question with dual-mode"
```

### Task 5: 合并 create_subplot + update_subplot

**Files:**
- 修改: `backend/app/agents/tools/creation/subplot.py`
- 删除: `backend/app/agents/tools/creation/update_subplot.py`

**Interfaces:**
- Consumes: `kb.plots.get_subplot_by_id(id)` (Task 1), `kb.plots.update_subplot(id, data)` (已有), `build_changes_diff()` (Task 2)
- Produces: 合并后的 `create_subplot` 工具（支持 `subplot_id` 参数双模式）

- [ ] **Step 1: 写合并后 create_subplot 的测试**

```python
class TestCreateSubplotMerge:
    """合并后 create_subplot 双模式测试"""

    @patch("app.agents.tools.creation.subplot._kb")
    def test_create_mode_default_status(self, mock_kb_cls):
        """create 路径: current_status 默认 developing"""
        from app.agents.tools.creation.subplot import create_subplot
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.create_subplot.return_value = {"id": 1, "name": "支线A", "current_status": "developing"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_subplot.ainvoke({"name": "支线A"}))
        assert result["action"] == "created"
        call_data = mock_kb.plots.create_subplot.call_args[0][0]
        assert call_data["current_status"] == "developing"

    @patch("app.agents.tools.creation.subplot._kb")
    def test_create_mode_custom_status(self, mock_kb_cls):
        """create 路径: current_status 可自定义"""
        from app.agents.tools.creation.subplot import create_subplot
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.create_subplot.return_value = {"id": 1, "name": "支线A", "current_status": "active"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_subplot.ainvoke({"name": "支线A", "current_status": "active"}))
        call_data = mock_kb.plots.create_subplot.call_args[0][0]
        assert call_data["current_status"] == "active"

    @patch("app.agents.tools.creation.subplot._kb")
    def test_update_mode_none_not_written(self, mock_kb_cls):
        """update 路径: None 默认值不写入 update_data"""
        from app.agents.tools.creation.subplot import create_subplot
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.get_subplot_by_id.return_value = {"id": 5, "name": "支线A", "current_status": "developing"}
        mock_kb.plots.update_subplot.return_value = {"id": 5, "name": "支线A", "current_status": "resolved"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_subplot.ainvoke({"subplot_id": 5, "current_status": "resolved"}))
        call_args = mock_kb.plots.update_subplot.call_args
        update_data = call_args[0][1]
        assert "name" not in update_data  # 未传, 默认 None, 不写入
        assert "current_status" in update_data
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreateSubplotMerge -v`
Expected: FAIL

- [ ] **Step 3: 改写 subplot.py 为合并版本**

将 `backend/app/agents/tools/creation/subplot.py` 完整替换为：

```python
"""创建/更新支线工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff, parse_json_param


@tool
async def create_subplot(
    subplot_id: int = 0,
    name: str = "",
    characters: str | None = None,
    current_status: str | None = None,
    raised_in_chapter: int | None = None,
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
    """创建新支线或更新已有支线. 提供 subplot_id 时为更新模式.

    - subplot_id=0(默认): 创建新支线(name 必填, current_status 默认 developing)
    - subplot_id>0: 更新指定 ID 的支线. None 表示不修改

    Args:
        subplot_id: 支线 ID(非零时更新已有支线)
        name: 支线名称
        characters: JSON 字符串列表, 参与角色名(默认 [])
        current_status: 支线状态 - "developing"/"active"/"resolved"/"abandoned"
        raised_in_chapter: 支线提出的章节号
        planned_intersection_chapter: 计划与主线交汇的章节号
        expected_resolution_chapter: 预期解决的章节号
    """
    kb = _kb()

    if subplot_id:
        # --- 更新路径 ---
        before = kb.plots.get_subplot_by_id(subplot_id)
        if not before:
            return {"error": f"支线 ID {subplot_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "name", "current_status", "expected_resolution_chapter",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "subplot_id": subplot_id}

        updated = kb.plots.update_subplot(subplot_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "subplot_id": subplot_id,
            "name": updated.get("name", before.get("name")),
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"支线「{updated.get('name', before.get('name'))}」已更新",
        }
    else:
        # --- 创建路径 ---
        if not name:
            return {"error": "创建支线时 name 为必填字段"}

        chars, chars_warn = parse_json_param(characters or "[]", [], "characters")

        # 注意: Subplot 模型 current_status 默认值是 "hint", 但工具层统一用 "developing"
        # 这是已有不一致, create 路径始终用 "developing" 覆盖模型默认值, 不在本次修复范围
        effective_status = current_status or "developing"
        data = {"name": name, "characters": chars, "current_status": effective_status}
        if raised_in_chapter is not None:
            data["raised_in_chapter"] = raised_in_chapter
        if planned_intersection_chapter is not None:
            data["planned_intersection_chapter"] = planned_intersection_chapter
        if expected_resolution_chapter is not None:
            data["expected_resolution_chapter"] = expected_resolution_chapter

        s = kb.plots.create_subplot(data)
        return {
            "action": "created",
            "id": s["id"],
            "name": name,
            "message": f"支线「{name}」已创建并写入知识库",
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreateSubplotMerge -v`
Expected: PASS

- [ ] **Step 5: 删除 update_subplot.py，更新 __init__.py 和 registry.py**

同 Task 3 的模式。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat(tools): merge update_subplot into create_subplot with dual-mode"
```

### Task 6: 合并 create_plot_block + update_plot_block

**Files:**
- 修改: `backend/app/agents/tools/creation/plot_block.py`
- 删除: `backend/app/agents/tools/creation/update_plot_block.py`

**Interfaces:**
- Consumes: `kb.plots.get_plot_block_by_id(id)` (Task 1), `kb.plots.update_plot_block(id, data)` (已有), `build_changes_diff()` (Task 2), `parse_json_param()` (已有)
- Produces: 合并后的 `create_plot_block` 工具（支持 `plot_block_id` 参数双模式，含 `completion_summary` 仅 update 路径字段）

- [ ] **Step 1: 写合并后 create_plot_block 的测试**

```python
class TestCreatePlotBlockMerge:
    """合并后 create_plot_block 双模式测试"""

    @patch("app.agents.tools.creation.plot_block._kb")
    def test_create_mode_requires_title_and_chapters(self, mock_kb_cls):
        """create 路径: 缺少 title 或 chapter_start/end 返回 error"""
        from app.agents.tools.creation.plot_block import create_plot_block
        import asyncio
        result = asyncio.run(create_plot_block.ainvoke({"title": ""}))
        assert "error" in result

    @patch("app.agents.tools.creation.plot_block._kb")
    def test_update_mode_completion_summary_only_in_update(self, mock_kb_cls):
        """update 路径: completion_summary 仅在 update 路径可用"""
        from app.agents.tools.creation.plot_block import create_plot_block
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.get_plot_block_by_id.return_value = {"id": 3, "title": "第一幕", "chapter_start": 1, "chapter_end": 10}
        mock_kb.plots.update_plot_block.return_value = {"id": 3, "title": "第一幕", "chapter_start": 1, "chapter_end": 10, "completion_summary": "已完成"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_plot_block.ainvoke({"plot_block_id": 3, "completion_summary": "已完成"}))
        call_args = mock_kb.plots.update_plot_block.call_args
        update_data = call_args[0][1]
        assert "completion_summary" in update_data

    @patch("app.agents.tools.creation.plot_block._kb")
    def test_update_mode_json_params(self, mock_kb_cls):
        """update 路径: JSON 参数(must_happen 等)正确处理"""
        from app.agents.tools.creation.plot_block import create_plot_block
        import asyncio
        mock_kb = MagicMock()
        mock_kb.plots.get_plot_block_by_id.return_value = {"id": 3, "title": "第一幕", "must_happen": []}
        mock_kb.plots.update_plot_block.return_value = {"id": 3, "title": "第一幕", "must_happen": ["event1"]}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_plot_block.ainvoke({"plot_block_id": 3, "must_happen": "[\"event1\"]"}))
        call_args = mock_kb.plots.update_plot_block.call_args
        update_data = call_args[0][1]
        assert "must_happen" in update_data
        assert update_data["must_happen"] == ["event1"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreatePlotBlockMerge -v`
Expected: FAIL

- [ ] **Step 3: 改写 plot_block.py 为合并版本**

将 `backend/app/agents/tools/creation/plot_block.py` 完整替换为（注意 JSON 参数在 create 路径保留 `"[]"` 默认值，update 路径用 `None` 表示不修改）：

```python
"""创建/更新情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def create_plot_block(
    plot_block_id: int = 0,
    title: str = "",
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    must_happen: str | None = None,
    questions_to_raise: str | None = None,
    questions_to_answer: str | None = None,
    expected_mood: str | None = None,
    completion_summary: str | None = None,
) -> dict:
    """创建新情节块或更新已有情节块. 提供 plot_block_id 时为更新模式.

    - plot_block_id=0(默认): 创建新情节块(title, chapter_start, chapter_end 必填)
    - plot_block_id>0: 更新指定 ID 的情节块. None 表示不修改

    Args:
        plot_block_id: 情节块 ID(非零时更新已有情节块)
        title: 情节块标题
        chapter_start: 起始章节号
        chapter_end: 结束章节号
        must_happen: JSON 字符串列表, 必须发生的事件
        questions_to_raise: JSON 字符串列表, 需要提出的问题
        questions_to_answer: JSON 字符串列表, 需要回答的问题
        expected_mood: 预期情绪基调
        completion_summary: 完成总结(仅更新模式)
    """
    kb = _kb()

    if plot_block_id:
        # --- 更新路径 ---
        before = kb.plots.get_plot_block_by_id(plot_block_id)
        if not before:
            return {"error": f"情节块 ID {plot_block_id} 不存在"}

        update_data = {}
        warnings = []

        for field in ("title", "chapter_start", "chapter_end", "expected_mood", "completion_summary"):
            value = locals()[field]
            if value is not None:
                update_data[field] = value

        # 处理 JSON 参数: None = 不修改, 非 None = 解析后写入(含 "[]" 清空)
        if must_happen is not None:
            parsed, warn = parse_json_param(must_happen, [], "must_happen")
            update_data["must_happen"] = parsed
            if warn:
                warnings.append(warn)

        if questions_to_raise is not None:
            parsed, warn = parse_json_param(questions_to_raise, [], "questions_to_raise")
            update_data["questions_to_raise"] = parsed
            if warn:
                warnings.append(warn)

        if questions_to_answer is not None:
            parsed, warn = parse_json_param(questions_to_answer, [], "questions_to_answer")
            update_data["questions_to_answer"] = parsed
            if warn:
                warnings.append(warn)

        if not update_data:
            return {"message": "无字段需要更新", "plot_block_id": plot_block_id}

        updated = kb.plots.update_plot_block(plot_block_id, update_data)

        result = {
            "plot_block_id": plot_block_id,
            "title": updated.get("title", before.get("title")),
            "updated_fields": list(update_data.keys()),
            "message": f"情节块「{updated.get('title', before.get('title'))}」已更新",
        }
        if warnings:
            result["param_parse_warnings"] = warnings
        return result
    else:
        # --- 创建路径 ---
        if not title or chapter_start is None or chapter_end is None:
            return {"error": "创建情节块时 title, chapter_start, chapter_end 为必填字段"}

        must, must_warn = parse_json_param(must_happen or "[]", [], "must_happen")
        raise_q, raise_q_warn = parse_json_param(questions_to_raise or "[]", [], "questions_to_raise")
        answer_q, answer_q_warn = parse_json_param(questions_to_answer or "[]", [], "questions_to_answer")

        data = {
            "title": title,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "must_happen": must,
            "questions_to_raise": raise_q,
            "questions_to_answer": answer_q,
        }
        if expected_mood:
            data["expected_mood"] = expected_mood

        block = kb.plots.create_plot_block(data)
        return {
            "action": "created",
            "id": block["id"],
            "title": title,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "message": f"情节块「{title}」已创建并写入知识库",
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreatePlotBlockMerge -v`
Expected: PASS

- [ ] **Step 5: 删除 update_plot_block.py，更新 __init__.py 和 registry.py**

同 Task 3 的模式。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat(tools): merge update_plot_block into create_plot_block with dual-mode"
```

### Task 7: 合并 create_foreshadowing + update_foreshadowing（三模式路由）

**Files:**
- 修改: `backend/app/agents/tools/creation/foreshadowing.py`
- 删除: `backend/app/agents/tools/creation/update_foreshadowing.py`

**Interfaces:**
- Consumes: `kb.foreshadowings.get(id)` (已有), `kb.foreshadowings.update(id, data)` (已有), `build_changes_diff()` (Task 2), `parse_json_param()` (已有)
- Produces: 合并后的 `create_foreshadowing` 工具（支持创建/单条更新/批量更新三模式）

- [ ] **Step 1: 写合并后 create_foreshadowing 的测试**

```python
class TestCreateForeshadowingMerge:
    """合并后 create_foreshadowing 三模式测试"""

    @patch("app.agents.tools.creation.foreshadowing._kb")
    def test_create_mode_requires_content(self, mock_kb_cls):
        """create 路径: 缺少 content 返回 error"""
        from app.agents.tools.creation.foreshadowing import create_foreshadowing
        import asyncio
        result = asyncio.run(create_foreshadowing.ainvoke({"content": ""}))
        assert "error" in result

    @patch("app.agents.tools.creation.foreshadowing._kb")
    def test_single_update_mode(self, mock_kb_cls):
        """单条更新: foreshadowing_id > 0"""
        from app.agents.tools.creation.foreshadowing import create_foreshadowing
        import asyncio
        mock_kb = MagicMock()
        mock_kb.foreshadowings.get.return_value = {"id": 7, "content": "伏笔A", "level": "hint", "status": "active"}
        mock_kb.foreshadowings.update.return_value = {"id": 7, "content": "伏笔A", "level": "strengthened", "status": "active"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_foreshadowing.ainvoke({"foreshadowing_id": 7, "level": "strengthened"}))
        assert "changes" in result or "updated_fields" in result

    @patch("app.agents.tools.creation.foreshadowing._kb")
    def test_batch_update_mode(self, mock_kb_cls):
        """批量更新: foreshadowing_ids 非空"""
        from app.agents.tools.creation.foreshadowing import create_foreshadowing
        import asyncio
        mock_kb = MagicMock()
        mock_kb.foreshadowings.get.return_value = {"id": 1, "content": "伏笔", "status": "active"}
        mock_kb.foreshadowings.update.return_value = {"id": 1, "content": "伏笔", "status": "reclaimed"}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_foreshadowing.ainvoke({"foreshadowing_ids": "[1,2,3]", "status": "reclaimed"}))
        assert "updated" in result or "total_updated" in result

    @patch("app.agents.tools.creation.foreshadowing._kb")
    def test_conflict_both_ids(self, mock_kb_cls):
        """冲突: 同时提供 foreshadowing_id 和 foreshadowing_ids"""
        from app.agents.tools.creation.foreshadowing import create_foreshadowing
        import asyncio
        result = asyncio.run(create_foreshadowing.ainvoke({"foreshadowing_id": 7, "foreshadowing_ids": "[1,2]"}))
        assert "error" in result

    @patch("app.agents.tools.creation.foreshadowing._kb")
    def test_update_only_fields_not_in_create(self, mock_kb_cls):
        """update 独有字段(status, appearance_count, resolved_chapter)在 create 路径不使用"""
        from app.agents.tools.creation.foreshadowing import create_foreshadowing
        import asyncio
        mock_kb = MagicMock()
        mock_kb.foreshadowings.get.return_value = {"id": 7, "content": "伏笔", "status": "active"}
        mock_kb.foreshadowings.update.return_value = {"id": 7, "content": "伏笔", "status": "reclaimed", "resolved_chapter": 10}
        mock_kb_cls.return_value = mock_kb
        result = asyncio.run(create_foreshadowing.ainvoke({"foreshadowing_id": 7, "status": "reclaimed", "resolved_chapter": 10}))
        call_args = mock_kb.foreshadowings.update.call_args
        update_data = call_args[0][1]
        assert "status" in update_data
        assert "resolved_chapter" in update_data
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreateForeshadowingMerge -v`
Expected: FAIL

- [ ] **Step 3: 改写 foreshadowing.py 为合并版本**

将 `backend/app/agents/tools/creation/foreshadowing.py` 完整替换为：

```python
"""创建/更新伏笔工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff, parse_json_param


@tool
async def create_foreshadowing(
    foreshadowing_id: int = 0,
    foreshadowing_ids: str = "",
    content: str = "",
    level: str | None = None,
    planted_chapter: int | None = None,
    expected_resolve_chapter: int | None = None,
    related_characters: str | None = None,
    # 以下仅 update 路径
    status: str | None = None,
    appearance_count: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
    """创建新伏笔或更新已有伏笔. 支持 create/单条 update/批量 update 三种模式.

    - foreshadowing_id=0 且 foreshadowing_ids 为空: 创建新伏笔(content 必填)
    - foreshadowing_id>0: 单条更新
    - foreshadowing_ids 非空(如 "[1,3,5]"): 批量更新(status 必填)

    Args:
        foreshadowing_id: 伏笔 ID(单条更新模式)
        foreshadowing_ids: JSON 字符串列表, 伏笔 ID 列表(批量模式)
        content: 伏笔内容描述
        level: 等级 - "hint"(暗示)/"strengthened"(强化)/"revealed"(揭示)
        planted_chapter: 埋设伏笔的章节号
        expected_resolve_chapter: 预期回收伏笔的章节号
        related_characters: JSON 字符串列表, 关联角色名
        status: 状态 - "active"/"pending_reclaim"/"reclaimed"(仅更新模式)
        appearance_count: 出现次数(仅更新模式)
        resolved_chapter: 实际回收章节号(仅更新模式)
    """
    kb = _kb()

    # 解析 foreshadowing_ids(提前解析, 用于冲突检查和模式判断)
    parsed_ids = None
    if foreshadowing_ids:
        parsed_ids, ids_warn = parse_json_param(foreshadowing_ids, [], "foreshadowing_ids")
        if ids_warn:
            return {"error": f"foreshadowing_ids 参数解析失败: {ids_warn}"}

    # 双参数冲突检查
    if foreshadowing_id and parsed_ids:
        return {"error": "不能同时提供 foreshadowing_id 和 foreshadowing_ids, 请选择单条或批量模式"}

    # --- 批量更新模式 ---
    if parsed_ids:
        return _batch_update(kb, parsed_ids, status, resolved_chapter)

    # --- 单条更新模式 ---
    if foreshadowing_id:
        before = kb.foreshadowings.get(foreshadowing_id)
        if not before:
            return {"error": f"伏笔 ID {foreshadowing_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "level", "status", "content", "appearance_count",
            "expected_resolve_chapter", "resolved_chapter",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "foreshadowing_id": foreshadowing_id}

        updated = kb.foreshadowings.update(foreshadowing_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "foreshadowing_id": foreshadowing_id,
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"伏笔 {foreshadowing_id} 已更新({', '.join(changes.keys())})",
        }

    # --- 创建模式 ---
    if not content:
        return {"error": "创建伏笔时 content 为必填字段"}

    characters, characters_warn = parse_json_param(related_characters or "[]", [], "related_characters")

    data = {
        "content": content,
        "level": level or "hint",
        "related_characters": characters,
    }
    if planted_chapter is not None:
        data["planted_chapter"] = planted_chapter
    if expected_resolve_chapter is not None:
        data["expected_resolve_chapter"] = expected_resolve_chapter

    f = kb.foreshadowings.create(data)
    return {
        "action": "created",
        "id": f["id"],
        "content": content[:80],
        "level": level or "hint",
        "message": "伏笔已创建并写入知识库",
    }


def _batch_update(kb, ids: list, status: str | None, resolved_chapter: int | None) -> dict:
    """批量更新伏笔状态"""
    if not ids:
        return {"error": "foreshadowing_ids 不能为空"}

    if not status:
        return {"error": "批量模式必须提供 status 参数"}

    valid_statuses = {"active", "pending_reclaim", "reclaimed"}
    if status not in valid_statuses:
        return {"error": f"status 必须是 {valid_statuses} 之一, 收到: {status}"}

    updated = []
    not_found = []
    errors = []

    update_data = {"status": status}
    if status == "reclaimed" and resolved_chapter:
        update_data["resolved_chapter"] = resolved_chapter

    for fs_id in ids:
        try:
            existing = kb.foreshadowings.get(fs_id)
            if not existing:
                not_found.append(fs_id)
            else:
                kb.foreshadowings.update(fs_id, update_data)
                updated.append(fs_id)
        except Exception as e:
            errors.append({"foreshadowing_id": fs_id, "error": str(e)})

    return {
        "updated": updated,
        "not_found": not_found,
        "errors": errors,
        "total_requested": len(ids),
        "total_updated": len(updated),
        "new_status": status,
        "message": f"已将 {len(updated)} 个伏笔状态更新为「{status}」" if updated else "没有伏笔被更新",
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCreateForeshadowingMerge -v`
Expected: PASS

- [ ] **Step 5: 删除 update_foreshadowing.py，更新 __init__.py 和 registry.py**

同 Task 3 的模式。注意 `update_foreshadowing` 在 `_WRITING_EXTRA` 中，需从该列表移除。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat(tools): merge update_foreshadowing into create_foreshadowing with tri-mode routing"
```

### Task 8: 修复 delete_plot_block 的 N+1 + hint 文本更新

**Files:**
- 修改: `backend/app/agents/tools/creation/delete_plot_block.py`

**Interfaces:**
- Consumes: `kb.plots.get_plot_block_by_id(id)` (Task 1)
- Produces: 无新接口

- [ ] **Step 1: 在 delete_plot_block.py 中替换 N+1 查询**

将第 20-25 行的 list 遍历：

```python
    blocks = kb.plots.list_plot_blocks()
    target = None
    for b in blocks:
        if b["id"] == plot_block_id:
            target = b
            break
```

替换为：

```python
    target = kb.plots.get_plot_block_by_id(plot_block_id)
```

- [ ] **Step 2: 更新 hint 文本**

将 hint 中的 `"使用 update_plot_question 工具将问题标记为已回答"` 替换为 `"使用 create_plot_question(question_id=...) 工具将问题标记为已回答"`。

- [ ] **Step 3: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/agents/tools/creation/delete_plot_block.py
git commit -m "fix(tools): fix N+1 in delete_plot_block and update hint text for merged tools"
```

---

### Task 9: 硬编码工具名常量集中（PERCEPTION_TOOL_NAMES / WRITING_TOOL_NAMES）

**Files:**
- 修改: `backend/app/agents/tools/registry.py`
- 修改: `backend/app/agents/agent_graph.py`

**Interfaces:**
- Consumes: 无
- Produces: `PERCEPTION_TOOL_NAMES` 和 `WRITING_TOOL_NAMES` frozenset 常量

- [ ] **Step 1: 写常量集中测试**

```python
class TestToolNameConstants:
    """工具名常量测试"""

    def test_perception_tool_names_is_frozenset(self):
        from app.agents.tools.registry import PERCEPTION_TOOL_NAMES
        assert isinstance(PERCEPTION_TOOL_NAMES, frozenset)

    def test_perception_tool_names_contains_all_six(self):
        from app.agents.tools.registry import PERCEPTION_TOOL_NAMES
        expected = {"knowledge_search", "foreshadowing_check",
                     "consistency_scan", "style_analysis",
                     "rhythm_analysis", "progress_report"}
        assert PERCEPTION_TOOL_NAMES == expected

    def test_writing_tool_names_excludes_perception(self):
        from app.agents.tools.registry import WRITING_TOOL_NAMES, PERCEPTION_TOOL_NAMES
        assert PERCEPTION_TOOL_NAMES.isdisjoint(WRITING_TOOL_NAMES)

    def test_writing_tool_names_subset_of_all_tools(self):
        from app.agents.tools.registry import WRITING_TOOL_NAMES, AGENT_TOOLS
        all_names = {t.name for t in AGENT_TOOLS}
        assert WRITING_TOOL_NAMES.issubset(all_names)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestToolNameConstants -v`
Expected: FAIL（常量不存在）

- [ ] **Step 3: 在 registry.py 中新增常量**

在 `backend/app/agents/tools/registry.py` 的 `REVISION_TOOLS` 定义之后、`TOOL_COST_TIER` 之前，添加：

```python
# 感知工具名集合 - 用于缓存/hooks/成本控制的统一判定
PERCEPTION_TOOL_NAMES = frozenset({
    "knowledge_search", "foreshadowing_check",
    "consistency_scan", "style_analysis",
    "rhythm_analysis", "progress_report",
})

# 写入工具名集合 - 执行后使感知缓存失效
WRITING_TOOL_NAMES = frozenset({
    name for name in (t.name for t in WRITING_TOOLS)
    if name not in PERCEPTION_TOOL_NAMES
})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestToolNameConstants -v`
Expected: PASS

- [ ] **Step 5: 在 agent_graph.py 中引用常量替换硬编码**

在 `backend/app/agents/agent_graph.py` 的 `_wrap_tool_with_hooks_and_cache` 函数中：

将：
```python
    is_perception = tool_name in (
        "knowledge_search", "foreshadowing_check",
        "consistency_scan", "style_analysis",
        "rhythm_analysis", "progress_report",
    )
```

替换为：
```python
    from app.agents.tools.registry import PERCEPTION_TOOL_NAMES
    is_perception = tool_name in PERCEPTION_TOOL_NAMES
```

将缓存失效的硬编码列表：
```python
                cache.invalidate_by_prefix([
                    "knowledge_search:", "consistency_scan:",
                    "style_analysis:", "rhythm_analysis:",
                    "progress_report:", "foreshadowing_check:",
                ])
```

替换为：
```python
                from app.agents.tools.registry import PERCEPTION_TOOL_NAMES
                cache.invalidate_by_prefix([f"{name}:" for name in PERCEPTION_TOOL_NAMES])
```

注意：将 import 语句移到文件顶部更规范。在 `agent_graph.py` 顶部已有的 `from app.agents.tools import ...` 附近添加：
```python
from app.agents.tools.registry import PERCEPTION_TOOL_NAMES
```

- [ ] **Step 6: 运行全量测试**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/agents/tools/registry.py backend/app/agents/agent_graph.py backend/tests/test_agent_tools.py
git commit -m "refactor(tools): centralize perception/writing tool name constants in registry"
```

---

### Task 10: WorkflowStore 封装 + advance_phase 简化

**Files:**
- 新建: `backend/app/agents/services/stores/workflow_store.py`
- 修改: `backend/app/agents/services/stores/__init__.py`
- 修改: `backend/app/agents/services/knowledge_base.py`
- 修改: `backend/app/agents/tools/creation/advance_phase.py`

**Interfaces:**
- Consumes: `get_or_create_workflow_state(db, project_id)` (已有), `WorkflowState` 模型 (已有)
- Produces: `WorkflowStore.get_current_phase() -> str`, `WorkflowStore.advance(direction, expected_current) -> dict`, `kb.workflows` 属性

- [ ] **Step 1: 写 WorkflowStore 的测试**

```python
class TestWorkflowStore:
    """WorkflowStore 测试"""

    def test_get_current_phase_returns_string(self):
        from app.agents.services.stores.workflow_store import WorkflowStore
        store = WorkflowStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_ws = MagicMock()
            mock_ws.stage = "incubation"
            # 模拟 get_or_create_workflow_state
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            with patch("app.agents.services.stores.workflow_store.get_or_create_workflow_state", return_value=mock_ws):
                result = store.get_current_phase()
                assert result == "incubation"

    def test_advance_returns_dict(self):
        from app.agents.services.stores.workflow_store import WorkflowStore
        store = WorkflowStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_ws = MagicMock()
            mock_ws.stage = "incubation"
            mock_db.refresh.return_value = None  # with_for_update
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            with patch("app.agents.services.stores.workflow_store.get_or_create_workflow_state", return_value=mock_ws):
                result = store.advance("forward", expected_current="incubation")
                assert "current_phase" in result
                assert "new_phase" in result
                assert "advanced" in result
                assert "conflict" in result

    def test_advance_detects_conflict(self):
        from app.agents.services.stores.workflow_store import WorkflowStore
        store = WorkflowStore(project_id=1)
        with patch.object(store, 'session') as mock_session:
            mock_db = MagicMock()
            mock_ws = MagicMock()
            mock_ws.stage = "writing"  # 已被并发推进
            mock_db.refresh.return_value = None
            mock_db.rollback.return_value = None
            mock_session.return_value.__enter__ = lambda s: mock_db
            mock_session.return_value.__exit__ = lambda s, *a: None
            with patch("app.agents.services.stores.workflow_store.get_or_create_workflow_state", return_value=mock_ws):
                result = store.advance("forward", expected_current="incubation")
                assert result["conflict"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestWorkflowStore -v`
Expected: FAIL（文件不存在）

- [ ] **Step 3: 新建 WorkflowStore**

创建 `backend/app/agents/services/stores/workflow_store.py`：

```python
"""工作流阶段存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.utils.workflow import get_or_create_workflow_state

logger = logging.getLogger(__name__)


class WorkflowStore(_BaseStore):
    """工作流阶段读写"""

    def get_current_phase(self) -> str:
        """获取当前阶段(无锁读取).

        返回 Phase enum 的 value 字符串, 如 "incubation".
        不存在时创建默认行(Phase.INCUBATION).
        内部调用 get_or_create_workflow_state 复用现有 upsert 逻辑.
        """
        with self.session(readonly=True) as db:
            ws = get_or_create_workflow_state(db, self.project_id)
            return ws.stage

    def advance(
        self,
        direction: str,
        expected_current: str | None = None,
    ) -> dict:
        """推进或回退阶段(带行锁).

        Args:
            direction: "forward" | "backward"
            expected_current: 乐观锁 - 如果不为 None 且与实际阶段不同,
                              返回冲突错误而不写入

        Returns:
            {
                "current_phase": str,       # 变更前阶段
                "new_phase": str,           # 变更后阶段
                "advanced": bool,           # 是否实际发生阶段变更
                "conflict": bool,           # 是否检测到并发冲突
            }
        """
        with self.session() as db:
            ws = get_or_create_workflow_state(db, self.project_id)

            # 获取行锁后确认阶段
            db.refresh(ws, with_for_update=True)
            actual_phase = ws.stage

            if expected_current is not None and actual_phase != expected_current:
                # 并发冲突: rollback 后显式 commit 空事务
                # 原因: self.session() 正常退出时会 db.commit()
                # rollback 后的 commit 是 no-op, 但语义更清晰
                db.rollback()
                db.commit()
                return {
                    "current_phase": actual_phase,
                    "new_phase": actual_phase,
                    "advanced": False,
                    "conflict": True,
                }

            # 计算目标阶段
            current_phase = actual_phase
            # 使用字符串 key/value 而非 Phase 枚举
            # 原因: ws.stage 从 DB 读出是纯字符串, 返回值也应为字符串
            # Phase(str, Enum) 虽然字符串可匹配枚举 key, 但 new_phase 会是枚举值
            # 导致返回值中 current_phase/suggested_phase 类型不一致
            if direction == "forward":
                forward_map = {
                    "incubation": "structure",
                    "structure": "writing",
                    "writing": "revision",
                }
                new_phase = forward_map.get(current_phase, current_phase)
            else:
                backward_map = {
                    "writing": "structure",
                    "structure": "incubation",
                }
                new_phase = backward_map.get(current_phase, current_phase)

            if new_phase != current_phase:
                ws.stage = new_phase
                # session 上下文管理器会在正常退出时 commit

            return {
                "current_phase": current_phase,
                "new_phase": new_phase,
                "advanced": new_phase != current_phase,
                "conflict": False,
            }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestWorkflowStore -v`
Expected: PASS

- [ ] **Step 5: 更新 stores/__init__.py**

在 `backend/app/agents/services/stores/__init__.py` 中添加：

```python
from app.agents.services.stores.workflow_store import WorkflowStore
```

并在 `__all__` 列表中添加 `"WorkflowStore"`。

- [ ] **Step 6: 更新 KnowledgeBaseService**

在 `backend/app/agents/services/knowledge_base.py` 的 `__init__` 方法中添加：

```python
from app.agents.services.stores import WorkflowStore
# ... 在 __init__ 中:
        self.workflows = WorkflowStore(project_id)
```

（import 移到文件顶部）

- [ ] **Step 7: 简化 advance_phase.py**

将 `backend/app/agents/tools/creation/advance_phase.py` 完整替换为：

```python
"""推进阶段工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb


@tool
async def advance_phase(direction: str = "forward") -> dict:
    """推进或回退创作阶段.

    direction="forward": 根据知识库完整度判断是否可以进入下一阶段.
    direction="backward": 回退到上一阶段(Writing->Structure, Structure->Incubation).

    Args:
        direction: 方向 - "forward"(推进) 或 "backward"(回退)
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    kb = _kb()

    # 阶段标签: 使用字符串 key 与 current_phase 类型一致
    phase_labels = {
        "incubation": "创意孵化",
        "structure": "结构设计",
        "writing": "写作中",
        "revision": "修订中",
    }

    # 1. 读取当前阶段
    current_phase = kb.workflows.get_current_phase()

    # 2. 计算目标阶段(逻辑不变, 仍在工具层)
    if direction == "backward":
        # 使用字符串 key/value 而非 Phase 枚举, 与 WorkflowStore.advance() 保持一致
        backward_map = {
            "writing": "structure",
            "structure": "incubation",
        }
        if current_phase not in backward_map:
            return {
                "current_phase": current_phase,
                "suggested_phase": current_phase,
                "advanced": False,
                "direction": direction,
                "reason": f"当前阶段「{phase_labels.get(current_phase, current_phase)}」不可回退",
                "current_phase_label": phase_labels.get(current_phase, current_phase),
                "suggested_phase_label": phase_labels.get(current_phase, current_phase),
            }
        suggested_phase = backward_map[current_phase]
        reason = f"从「{phase_labels.get(current_phase, current_phase)}」回退到「{phase_labels.get(suggested_phase, suggested_phase)}」"
    else:
        suggested_phase, reason = _evaluate_forward(current_phase, kb)

    # 3. 执行带锁写入
    advanced = suggested_phase != current_phase
    if advanced:
        result = kb.workflows.advance(direction, expected_current=current_phase)
        if result.get("conflict"):
            actual = result.get("current_phase", current_phase)
            return {
                "current_phase": actual,
                "suggested_phase": suggested_phase,
                "advanced": False,
                "direction": direction,
                "reason": "并发更新检测: 阶段已被其他请求更新",
                "current_phase_label": phase_labels.get(actual, actual),
                "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
            }

    return {
        "current_phase": current_phase,
        "suggested_phase": suggested_phase,
        "advanced": advanced,
        "direction": direction,
        "reason": reason,
        "current_phase_label": phase_labels.get(current_phase, current_phase),
        "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
    }


def _evaluate_forward(current_phase: str, kb) -> tuple:
    """评估推进条件, 返回 (suggested_phase, reason).

    current_phase 和返回值均为字符串(如 "incubation"/"structure"),
    与 WorkflowStore 和 advance_phase 工具层保持一致.
    """
    outline = kb.outlines.get()
    characters = kb.characters.list_characters()
    world_setting = kb.world_setting.get()
    plot_blocks = kb.plots.list_plot_blocks()
    timeline = kb.timelines.list_timeline()

    suggested_phase = current_phase
    reason = ""

    if current_phase == "incubation":
        has_outline = outline and (outline.get("title") or outline.get("summary"))
        has_characters = len(characters) >= 1
        has_world = world_setting is not None
        if has_outline and has_characters and has_world:
            suggested_phase = "structure"
            reason = "大纲、人物、世界观已就绪, 可进入结构设计阶段"
        else:
            missing = []
            if not has_outline:
                missing.append("大纲")
            if not has_characters:
                missing.append("人物")
            if not has_world:
                missing.append("世界观")
            reason = f"孵化阶段尚未完成, 缺少: {'、'.join(missing)}"

    elif current_phase == "structure":
        has_blocks = len(plot_blocks) >= 1
        if has_blocks:
            suggested_phase = "writing"
            reason = "情节块已规划, 可进入写作阶段"
        else:
            reason = "结构阶段尚未完成, 缺少情节块规划"

    elif current_phase == "writing":
        total_chapters = 0
        if outline:
            total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0
        written = len(timeline) if timeline else 0
        if total_chapters > 0 and written >= total_chapters:
            suggested_phase = "revision"
            reason = f"全部 {total_chapters} 章已写完, 可进入修订阶段"
        else:
            reason = f"写作阶段进行中({written}/{total_chapters} 章)"

    elif current_phase == "revision":
        reason = "已在修订阶段"

    return suggested_phase, reason
```

- [ ] **Step 8: 运行全量测试**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: PASS

- [ ] **Step 9: 提交**

```bash
git add -A
git commit -m "refactor(workflow): create WorkflowStore and simplify advance_phase tool"
```

---

### Task 11: 前端 AgentChatPanel 工具名映射更新

**Files:**
- 修改: `frontend/src/components/workbench/AgentChatPanel.tsx`

**Interfaces:**
- Consumes: 无
- Produces: 无

- [ ] **Step 1: 更新工具名映射表**

在 `frontend/src/components/workbench/AgentChatPanel.tsx` 约 60-70 行的工具名映射表中：

1. 删除 5 条 update_* 映射：
   - `update_character: '更新角色'`
   - `update_plot_block: '更新情节块'`
   - `update_plot_question: '更新情节问题'`
   - `update_subplot: '更新支线'`
   - `update_foreshadowing: '更新伏笔'`

2. 修改 create_* 工具的标签逻辑：当工具返回值含 `updated_fields` 或 `changes` 时，前端显示"更新xxx"而非"创建xxx"。

在映射表下方添加辅助函数：

```typescript
/** 根据 create_* 工具的返回值判断显示"创建"还是"更新"
 *  注意: result 在工具调用开始时不可用(此时显示"创建xxx"),
 *  工具完成后需更新标签为"更新xxx"(基于返回值中的 updated_fields/changes).
 *  调用方需在 SSE 流的 tool_result 事件中重新调用此函数更新标签.
 */
function getToolLabel(toolName: string, result?: Record<string, unknown>): string
{
  const baseLabels: Record<string, string> = {
    create_character: '角色',
    create_foreshadowing: '伏笔',
    create_plot_block: '情节块',
    create_subplot: '支线',
    create_plot_question: '情节问题',
  }
  if (baseLabels[toolName] && result) {
    const isUpdate = 'updated_fields' in result || 'changes' in result
    return isUpdate ? `更新${baseLabels[toolName]}` : `创建${baseLabels[toolName]}`
  }
  return TOOL_NAME_LABELS[toolName] || toolName
}
```

3. 更新所有使用 `TOOL_NAME_LABELS[toolName]` 的地方改为调用 `getToolLabel(toolName, result)`。

- [ ] **Step 2: 前端 lint 检查**

Run: `cd frontend && npm run lint`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(frontend): update AgentChatPanel tool name labels for merged create/update tools"
```

---

### Task 12: 测试更新 + 全量验证

**Files:**
- 修改: `backend/tests/test_agent_tools.py`
- 修改: `backend/tests/test_change_workflow.py`

**Interfaces:**
- Consumes: 所有之前 Task 的产出
- Produces: 无

- [ ] **Step 1: 修复 test_agent_tools.py 中对 update_* 工具的引用**

扫描 `test_agent_tools.py` 中所有对已删除 `update_*` 工具的 import 和引用，更新为合并后的 `create_*` 工具。关键修改：

1. 删除 `from app.agents.tools.creation.update_subplot import update_subplot` 等 import
2. `test_update_subplot_params_match_model` 测试：改为验证合并后的 `create_subplot` 在 update 模式下的参数名
3. `test_update_plot_question_params_match_model` 测试：同上
4. `test_update_plot_block_no_chapter_range` 测试：同上
5. 更新 `TestForeshadowingBatchUpdate` 类中的 import 路径从 `update_foreshadowing` 改为 `foreshadowing`

- [ ] **Step 2: 修复 test_change_workflow.py 中的引用**

扫描 `test_change_workflow.py` 中 `update_character` 相关的测试用例，确保 Store 方法名 `kb.characters.update_character()` 不受影响（这是 Store 层，不是 Agent 工具）。

- [ ] **Step 3: 更新 TestToolRegistration 中的工具计数**

`test_writing_tools_has_all_tools` 断言 `>= 20`，删除 5 个工具后应为 `>= 15`。更新：

```python
    def test_writing_tools_has_all_tools(self):
        assert len(WRITING_TOOLS) >= 15, f'Expected at least 15 tools, got {len(WRITING_TOOLS)}'
```

同时更新 `test_incubation_tools_subset` 和 `test_structure_tools_subset` 的计数。

- [ ] **Step 4: 运行后端全量测试**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: 全部 PASS

- [ ] **Step 5: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: 全部 PASS

- [ ] **Step 6: 重建并重启服务**

```bash
docker compose restart backend
docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "test(tools): update test suite for merged create/update tools"
```

---

### Task 13: 最终验收

**Files:**
- 无新增修改

- [ ] **Step 1: 验证工具数从 33 降至 28**

```bash
docker exec novelagent-backend-1 python3 -c "
from app.agents.tools.registry import AGENT_TOOLS
print(f'Tool count: {len(AGENT_TOOLS)}')
names = [t.name for t in AGENT_TOOLS]
for n in sorted(names):
    print(f'  {n}')
# 确认没有 update_* 工具
update_tools = [n for n in names if n.startswith('update_')]
assert not update_tools, f'Found update tools: {update_tools}'
print('OK: no update_* tools found')
"
```

Expected: 28 个工具，无 `update_*` 工具

- [ ] **Step 2: 验证 PERCEPTION_TOOL_NAMES 和 WRITING_TOOL_NAMES**

```bash
docker exec novelagent-backend-1 python3 -c "
from app.agents.tools.registry import PERCEPTION_TOOL_NAMES, WRITING_TOOL_NAMES
print(f'Perception: {PERCEPTION_TOOL_NAMES}')
print(f'Writing: {len(WRITING_TOOL_NAMES)} tools')
assert PERCEPTION_TOOL_NAMES.isdisjoint(WRITING_TOOL_NAMES)
print('OK: perception and writing sets are disjoint')
"
```

- [ ] **Step 3: 验证 advance_phase 不再直接使用 SessionLocal**

```bash
rg "from app.database import SessionLocal" backend/app/agents/tools/creation/advance_phase.py
```

Expected: 无匹配（SessionLocal 不应出现在 advance_phase.py 中）

- [ ] **Step 4: 验证前端工具名映射**

```bash
rg "update_character|update_plot_block|update_plot_question|update_subplot|update_foreshadowing" frontend/src/
```

Expected: 无匹配

- [ ] **Step 5: 运行全量后端测试最终确认**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: 全部 PASS

- [ ] **Step 6: 标记验收通过**

所有 spec 验收标准检查完毕后，在此步骤打勾。
