# 上下文机制优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 NovelAgent 的上下文组装路径，接入 BudgetAllocator 动态预算分配 + context_strategy 前文策略 + 跨请求缓存，使 1M 窗口利用率从 ~1.2% 提升到 50-70%。

**Architecture:** 三层架构 — BudgetAllocator（预算分配）→ ProjectContextAssembler（数据组装 + 前文策略集成）→ agent.py（prompt 填充）。渐进重构，每步可独立验证，保持系统可部署。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / contextvars / functools.lru_cache

---

## File Structure

| 文件 | 职责 | 状态 |
|------|------|------|
| `backend/app/agents/constants.py` | 新增 `PHASE_BUDGET_RATIOS` 常量 | 修改 |
| `backend/app/agents/token_budget.py` | `estimate_tokens` 系数 0.72/0.36 | 修改 |
| `backend/app/agents/budget_allocator.py` | BudgetAllocator 预算分配器 | 新增 |
| `backend/app/agents/context_cache.py` | 跨请求 LRU 缓存 + version_tag | 新增 |
| `backend/app/agents/tool_context.py` | 新增 `_loaded_keys` ContextVar | 修改 |
| `backend/app/agents/context_strategy.py` | `select_strategy()` 动态策略选择 | 修改 |
| `backend/app/agents/services/knowledge_base.py` | 新增 `batch_read_for_context()` | 修改 |
| `backend/app/agents/agent_context.py` | 重构为 `ProjectContextAssembler` | 修改 |
| `backend/app/api/agent.py` | 调用点迁移 | 修改 |
| `backend/app/agents/tools/perception/knowledge_search.py` | 感知 `_loaded_keys` 附加提示 | 修改 |
| `backend/tests/test_token_budget.py` | 更新系数断言 | 修改 |
| `backend/tests/test_budget_allocator.py` | BudgetAllocator 单元测试 | 新增 |
| `backend/tests/test_context_cache.py` | ContextCache 单元测试 | 新增 |
| `backend/tests/test_context_strategy.py` | 新增 `select_strategy` 测试 | 修改 |
| `backend/tests/test_agent_context.py` | ProjectContextAssembler 集成测试 | 新增 |

---


### Task 1: Token 估算系数更新

**Files:**
- Modify: `backend/app/agents/token_budget.py:27-34`
- Modify: `backend/tests/test_token_budget.py:7-9`

- [ ] **Step 1: 更新 test_token_budget.py 中的中文估算断言**

将 `test_estimate_tokens_chinese` 的预期值从 `4 * 2` 改为 `4 * 0.72`：

```python
def test_estimate_tokens_chinese():
    text = "你好世界"  # 4 个中文字
    result = estimate_tokens(text)
    assert result == max(int(4 * 0.72), 1)  # 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_token_budget.py::test_estimate_tokens_chinese -v`
Expected: FAIL — 断言 8 != 2

- [ ] **Step 3: 更新 estimate_tokens 系数**

在 `backend/app/agents/token_budget.py` 中修改 `estimate_tokens` 函数：

```python
def estimate_tokens(text: str) -> int:
    """估算文本的 token 数

    基于 DeepSeek V4 分词器参数，保守系数 1.2：
    中文约 0.6 token/字 × 1.2 = 0.72 token/字
    英文约 0.3 token/char × 1.2 = 0.36 token/char
    非空文本最少返回 1，避免 0 值导致上下文策略误判为无内容。
    """
    if not text:
        return 0
    chinese_chars = len(_CJK_RE.findall(text))
    other_chars = len(text) - chinese_chars
    return max(int(chinese_chars * 0.72 + other_chars * 0.36), 1)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_token_budget.py -v`
Expected: ALL PASS

- [ ] **Step 5: 运行相关回归测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py tests/test_tool_cache.py -v`
Expected: ALL PASS（策略测试内部用 estimate_tokens 计算预算截断，新系数不影响逻辑正确性）

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/token_budget.py backend/tests/test_token_budget.py
git commit -m "feat(token_budget): 更新估算系数为 DeepSeek V4 × 1.2 (0.72/0.36)"
```


### Task 2: PHASE_BUDGET_RATIOS 常量 + BudgetAllocator

**Files:**
- Modify: `backend/app/agents/constants.py` — 新增 `PHASE_BUDGET_RATIOS`
- Create: `backend/app/agents/budget_allocator.py`
- Create: `backend/tests/test_budget_allocator.py`

- [ ] **Step 1: 在 constants.py 末尾新增 PHASE_BUDGET_RATIOS**

```python
# ========== 预算分配比例 ==========
# 按 Phase 分配 context_window 剩余预算（扣除 output/safety/system 固定项后）
# 格式: (history_ratio, previous_text_ratio, project_data_ratio)
PHASE_BUDGET_RATIOS = {
    Phase.INCUBATION.value: (0.60, 0.00, 0.40),
    Phase.STRUCTURE.value:  (0.40, 0.00, 0.60),
    Phase.WRITING.value:    (0.10, 0.70, 0.20),
    Phase.REVISION.value:   (0.20, 0.40, 0.40),
}
```

- [ ] **Step 2: 写 BudgetAllocator 失败测试**

创建 `backend/tests/test_budget_allocator.py`：

```python
"""BudgetAllocator 单元测试"""
import pytest
from app.agents.budget_allocator import BudgetAllocator, BudgetAllocation
from app.agents.constants import Phase


class TestBudgetAllocator:
    def test_writing_1m_window(self):
        """1M 窗口 WRITING 阶段预算分配"""
        alloc = BudgetAllocator.allocate(1_000_000, Phase.WRITING.value)
        # 固定项
        assert alloc.output_budget == 50_000
        assert alloc.safety_margin == 100_000
        assert alloc.system_prompt_budget == 20_000
        # 剩余 830_000
        assert alloc.history_budget == int(830_000 * 0.10)
        assert alloc.previous_text_budget == int(830_000 * 0.70)
        assert alloc.project_data_budget == int(830_000 * 0.20)
        # 总和不超 context_window
        total = (alloc.output_budget + alloc.safety_margin +
                 alloc.system_prompt_budget + alloc.history_budget +
                 alloc.previous_text_budget + alloc.project_data_budget)
        assert total <= 1_000_000

    def test_incubation_previous_text_is_zero(self):
        """孵化阶段前文预算为 0"""
        alloc = BudgetAllocator.allocate(128_000, Phase.INCUBATION.value)
        assert alloc.previous_text_budget == 0

    def test_small_window_no_negative(self):
        """极小窗口不产生负值"""
        alloc = BudgetAllocator.allocate(8192, Phase.WRITING.value)
        assert alloc.history_budget >= 0
        assert alloc.previous_text_budget >= 0
        assert alloc.project_data_budget >= 0

    def test_output_budget_capped_at_50k(self):
        """输出预算上限 50K"""
        alloc = BudgetAllocator.allocate(2_000_000, Phase.WRITING.value)
        assert alloc.output_budget == 50_000

    def test_output_budget_5_percent_for_small_window(self):
        """小窗口输出预算为 5%"""
        alloc = BudgetAllocator.allocate(100_000, Phase.WRITING.value)
        assert alloc.output_budget == 5_000

    def test_invalid_phase_raises(self):
        """无效阶段抛异常"""
        with pytest.raises(ValueError):
            BudgetAllocator.allocate(128_000, "unknown_phase")

    def test_allocation_dataclass_fields(self):
        """BudgetAllocation 包含所有预期字段"""
        alloc = BudgetAllocator.allocate(128_000, Phase.STRUCTURE.value)
        assert hasattr(alloc, "output_budget")
        assert hasattr(alloc, "safety_margin")
        assert hasattr(alloc, "system_prompt_budget")
        assert hasattr(alloc, "history_budget")
        assert hasattr(alloc, "previous_text_budget")
        assert hasattr(alloc, "project_data_budget")
        assert hasattr(alloc, "context_window")
        assert hasattr(alloc, "phase")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_budget_allocator.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: 实现 BudgetAllocator**

创建 `backend/app/agents/budget_allocator.py`：

```python
"""预算分配器 — 根据模型上下文窗口和阶段分配 token 预算"""

from dataclasses import dataclass

from app.agents.constants import PHASE_BUDGET_RATIOS


@dataclass(frozen=True)
class BudgetAllocation:
    """预算分配结果"""
    output_budget: int
    safety_margin: int
    system_prompt_budget: int
    history_budget: int
    previous_text_budget: int
    project_data_budget: int
    context_window: int
    phase: str


class BudgetAllocator:
    """根据 context_window + phase 分配 token 预算

    第一步：扣除固定项（output 5% 上限 50K, safety 10%, system 2%）
    第二步：按 PHASE_BUDGET_RATIOS 分配剩余预算
    """

    # 固定项比例
    OUTPUT_RATIO = 0.05
    OUTPUT_CAP = 50_000
    SAFETY_RATIO = 0.10
    SYSTEM_RATIO = 0.02

    @classmethod
    def allocate(cls, context_window: int, phase: str) -> BudgetAllocation:
        """分配 token 预算

        Args:
            context_window: 模型上下文窗口大小
            phase: 当前阶段（Phase.value）

        Returns:
            BudgetAllocation 各项预算

        Raises:
            ValueError: phase 不在 PHASE_BUDGET_RATIOS 中
        """
        if phase not in PHASE_BUDGET_RATIOS:
            raise ValueError(f"未知阶段: {phase}，有效值: {list(PHASE_BUDGET_RATIOS.keys())}")

        # 第一步：扣除固定项
        output_budget = min(int(context_window * cls.OUTPUT_RATIO), cls.OUTPUT_CAP)
        safety_margin = int(context_window * cls.SAFETY_RATIO)
        system_prompt_budget = int(context_window * cls.SYSTEM_RATIO)

        remaining = context_window - output_budget - safety_margin - system_prompt_budget
        remaining = max(remaining, 0)

        # 第二步：按阶段比例分配
        history_ratio, previous_ratio, project_data_ratio = PHASE_BUDGET_RATIOS[phase]

        return BudgetAllocation(
            output_budget=output_budget,
            safety_margin=safety_margin,
            system_prompt_budget=system_prompt_budget,
            history_budget=int(remaining * history_ratio),
            previous_text_budget=int(remaining * previous_ratio),
            project_data_budget=int(remaining * project_data_ratio),
            context_window=context_window,
            phase=phase,
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_budget_allocator.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/constants.py backend/app/agents/budget_allocator.py backend/tests/test_budget_allocator.py
git commit -m "feat(budget): 新增 PHASE_BUDGET_RATIOS 常量和 BudgetAllocator"
```


### Task 3: 跨请求缓存 (ContextCache)

**Files:**
- Modify: `backend/app/agents/services/stores/base.py` — 新增 `_bump_version`
- Create: `backend/app/agents/context_cache.py`
- Create: `backend/tests/test_context_cache.py`

- [ ] **Step 1: 在 _BaseStore 中新增 version_tag 管理**

在 `backend/app/agents/services/stores/base.py` 的 `_BaseStore` 类中添加类级别版本追踪：

```python
import threading

# 类级别版本号注册表：data_type -> 版本号
_version_registry: dict[str, int] = {}
_version_lock = threading.Lock()


class _BaseStore:
    # ... 现有代码 ...

    @classmethod
    def _bump_version(cls, data_type: str) -> None:
        """写入操作后调用，使对应数据类型的缓存失效"""
        with _version_lock:
            _version_registry[data_type] = _version_registry.get(data_type, 0) + 1

    @classmethod
    def get_version(cls, data_type: str) -> int:
        """获取数据类型的当前版本号"""
        with _version_lock:
            return _version_registry.get(data_type, 0)
```

- [ ] **Step 2: 写 ContextCache 失败测试**

创建 `backend/tests/test_context_cache.py`：

```python
"""ContextCache 单元测试"""
import time
import pytest
from app.agents.context_cache import ContextCache


class TestContextCache:
    def test_cache_miss_returns_none(self):
        """缓存未命中返回 None"""
        cache = ContextCache()
        assert cache.get(1, "world_setting", 0) is None

    def test_cache_hit_returns_value(self):
        """缓存命中返回值"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"core_concept": "魔法"})
        result = cache.get(1, "world_setting", 0)
        assert result == {"core_concept": "魔法"}

    def test_version_change_causes_miss(self):
        """version_tag 变化导致缓存未命中"""
        cache = ContextCache()
        cache.set(1, "world_setting", 1, {"core_concept": "旧"})
        result = cache.get(1, "world_setting", 2)
        assert result is None

    def test_different_project_isolated(self):
        """不同项目的缓存隔离"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"core_concept": "A"})
        cache.set(2, "world_setting", 0, {"core_concept": "B"})
        assert cache.get(1, "world_setting", 0) == {"core_concept": "A"}
        assert cache.get(2, "world_setting", 0) == {"core_concept": "B"}

    def test_invalidate_specific_data_type(self):
        """使特定数据类型的缓存失效"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"a": 1})
        cache.set(1, "characters", 0, [{"name": "张三"}])
        cache.invalidate(1, "world_setting")
        assert cache.get(1, "world_setting", 0) is None
        assert cache.get(1, "characters", 0) == [{"name": "张三"}]

    def test_ttl_expiry(self):
        """TTL 过期后缓存失效"""
        cache = ContextCache(ttl_seconds=0.1)
        cache.set(1, "world_setting", 0, {"a": 1})
        time.sleep(0.15)
        assert cache.get(1, "world_setting", 0) is None

    def test_uncacheable_types_not_stored(self):
        """不缓存的类型 set 后 get 仍返回 None"""
        cache = ContextCache()
        cache.set(1, "chapters", 0, [{"content": "很长"}])
        assert cache.get(1, "chapters", 0) is None

    def test_invalidate_all_for_project(self):
        """使项目所有缓存失效"""
        cache = ContextCache()
        cache.set(1, "world_setting", 0, {"a": 1})
        cache.set(1, "characters", 0, [{"name": "张三"}])
        cache.invalidate_all(1)
        assert cache.get(1, "world_setting", 0) is None
        assert cache.get(1, "characters", 0) is None
```

- [ ] **Step 3: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_cache.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: 实现 ContextCache**

创建 `backend/app/agents/context_cache.py`：

```python
"""跨请求 LRU 缓存 — 同项目连续对话时减少 DB 查询

缓存层：进程内 dict，key = (project_id, data_type, version_tag)
version_tag：由 _BaseStore._bump_version 管理，写入时 +1
TTL：默认 60 秒自动过期
不缓存：章节正文、伏笔状态（变化频率高）
"""

import time
import threading
from typing import Any

# 不缓存的数据类型（变化频率高或数据量过大）
_UNCACHEABLE_TYPES = frozenset({"chapters", "foreshadowing_status", "chapter_outlines"})


class ContextCache:
    """跨请求 LRU 缓存"""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 200):
        self._store: dict[tuple[int, str, int], tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, project_id: int, data_type: str, version_tag: int) -> Any | None:
        """获取缓存值，未命中或过期返回 None"""
        if data_type in _UNCACHEABLE_TYPES:
            return None

        key = (project_id, data_type, version_tag)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, project_id: int, data_type: str, version_tag: int, value: Any) -> None:
        """设置缓存值"""
        if data_type in _UNCACHEABLE_TYPES:
            return

        key = (project_id, data_type, version_tag)
        with self._lock:
            if len(self._store) >= self._max_size:
                self._evict_oldest()
            self._store[key] = (value, time.time())

    def invalidate(self, project_id: int, data_type: str) -> None:
        """使指定项目+数据类型的所有版本缓存失效"""
        with self._lock:
            keys_to_remove = [
                k for k in self._store
                if k[0] == project_id and k[1] == data_type
            ]
            for k in keys_to_remove:
                del self._store[k]

    def invalidate_all(self, project_id: int) -> None:
        """使指定项目的所有缓存失效"""
        with self._lock:
            keys_to_remove = [
                k for k in self._store if k[0] == project_id
            ]
            for k in keys_to_remove:
                del self._store[k]

    def _evict_oldest(self) -> None:
        """驱逐最旧的缓存条目"""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]


# 全局单例
context_cache = ContextCache()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_cache.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/services/stores/base.py backend/app/agents/context_cache.py backend/tests/test_context_cache.py
git commit -m "feat(cache): 新增 ContextCache 跨请求缓存和 _bump_version 版本管理"
```


### Task 4: batch_read_for_context()

**Files:**
- Modify: `backend/app/agents/services/knowledge_base.py` — 新增方法

- [ ] **Step 1: 在 KnowledgeBaseService 中新增 batch_read_for_context()**

在 `knowledge_base.py` 的 `batch_read_for_index()` 方法之后添加：

```python
    def batch_read_for_context(self, current_chapter_number: int | None = None) -> dict:
        """单次 session 批量读取上下文构建所需的全部数据

        与 batch_read_for_index 的区别：
        - 包含章节正文（index 版本不含，太长）
        - 包含上一章结尾片段
        - 包含变更记录
        - 包含章节大纲（index 版本不含）
        - 不包含场景清单（index 版本需要）
        """
        from app.agents.services.stores.base import _BaseStore

        with self.session(readonly=True) as db:
            plots_data = self.plots._read_all_with_session(db)
            timelines_data = self.timelines._read_all_with_session(db)

            # 章节：含正文
            chapters = self.chapters._read_all_with_session(db)

            # 章节大纲
            chapter_outlines = self.outlines._read_chapter_outlines_with_session(db)

            # 变更记录
            changes = self.changes._read_all_with_session(db)

            # 上一章结尾
            previous_closing = None
            if current_chapter_number and current_chapter_number > 1:
                prev = self.chapters._read_by_number_with_session(db, current_chapter_number - 1)
                if prev and prev.get("content"):
                    content = prev["content"]
                    previous_closing = content[-500:] if len(content) > 500 else content

            return {
                "world_setting": self.world_setting._read_with_session(db),
                "characters": self.characters._read_all_characters_with_session(db),
                "relations": self.characters._read_all_relations_with_session(db),
                "style_constraints": self.styles._read_constraints_with_session(db),
                "outline": self.outlines._read_with_session(db),
                "chapter_outlines": chapter_outlines,
                "plot_blocks": plots_data.get("plot_blocks", []),
                "plot_questions": plots_data.get("plot_questions", []),
                "subplots": plots_data.get("subplots", []),
                "foreshadowings": self.foreshadowings._read_all_with_session(db),
                "timeline": timelines_data.get("timeline", []),
                "style_snapshots": [],
                "chapters": chapters,
                "changes": changes,
                "previous_closing": previous_closing,
            }
```

- [ ] **Step 2: 在需要的 Store 中补充 _read_all_with_session / _read_by_number_with_session**

检查各 Store 是否已有 `_read_all_with_session` 方法（`chapter_store.py`、`outline_store.py`、`change_store.py`）。如没有，在各 Store 中新增。典型模式：

```python
    def _read_all_with_session(self, db) -> list[dict]:
        """单次 session 内批量读取全部章节（含 chapter_number 和 title）

        Chapter 模型没有 project_id，需通过 ChapterOutline JOIN 查询。
        """
        from app.models.chapter import Chapter as ChapterModel
        from app.models.outline import ChapterOutline

        results = []
        outlines = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == self.project_id,
        ).order_by(ChapterOutline.chapter_number).all()

        outline_ids = [co.id for co in outlines]
        chapters_map = {}
        if outline_ids:
            chapters = db.query(ChapterModel).filter(
                ChapterModel.chapter_outline_id.in_(outline_ids),
            ).all()
            chapters_map = {ch.chapter_outline_id: ch for ch in chapters}

        for co in outlines:
            chapter = chapters_map.get(co.id)
            if chapter:
                result = self._to_dict(chapter)
                result["chapter_number"] = co.chapter_number
                result["title"] = co.title
                results.append(result)

        return results
```

对于 `outline_store.py`，需要新增 `_read_chapter_outlines_with_session`：

```python
    def _read_chapter_outlines_with_session(self, db: Session) -> list[dict]:
        """单次 session 内批量读取全部章节大纲"""
        objs = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == self.project_id
        ).order_by(ChapterOutline.chapter_number).all()
        return self._to_dict_list(objs)
```

对于 `change_store.py`，需要新增 `_read_all_with_session`：

```python
    def _read_all_with_session(self, db) -> list[dict]:
        """单次 session 内批量读取全部变更记录"""
        from app.models.setting_change import SettingChange
        objs = db.query(SettingChange).filter(
            SettingChange.project_id == self.project_id
        ).order_by(SettingChange.id.desc()).all()
        return self._to_dict_list(objs)
```

对于 `chapter_store.py`，需要新增 `_read_all_with_session` 和 `_read_by_number_with_session`：

```python
    def _read_by_number_with_session(self, db: Session, chapter_number: int) -> dict | None:
        """单次 session 内按章节号读取"""
        obj = db.query(Chapter).filter(
            Chapter.project_id == self.project_id,
            Chapter.chapter_number == chapter_number,
        ).first()
        return self._to_dict(obj)
```

- [ ] **Step 3: 运行现有测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=30`
Expected: ALL PASS — 新增方法不影响现有逻辑

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/services/knowledge_base.py backend/app/agents/services/stores/chapter_store.py backend/app/agents/services/stores/outline_store.py backend/app/agents/services/stores/change_store.py
git commit -m "feat(kb): 新增 batch_read_for_context 和 Store _read_all_with_session 方法"
```


### Task 5: context_strategy 动态策略选择

**Files:**
- Modify: `backend/app/agents/context_strategy.py` — 新增 `select_strategy()`
- Modify: `backend/tests/test_context_strategy.py` — 新增测试

- [ ] **Step 1: 写 select_strategy 失败测试**

在 `backend/tests/test_context_strategy.py` 中新增类：

```python
class TestSelectStrategy:
    def test_full_fits_within_80_percent_budget(self):
        """前文总量 ≤ 80% 预算时选择 Full"""
        strategy = select_strategy(
            written_chapters=[
                {"chapter_number": 1, "title": "短章", "content": "短"},
            ],
            current_chapter=2,
            token_budget=100000,
        )
        assert isinstance(strategy, FulltextContentStrategy)

    def test_hybrid_when_full_exceeds_budget(self):
        """Full 放不下时降级到 Hybrid"""
        # 5 章，每章约 720 token（1000 中文字 × 0.72）
        chapters = [
            {"chapter_number": i, "title": f"第{i}章", "content": "中" * 1000}
            for i in range(1, 6)
        ]
        # 预算只够放 2 章（80% of 3000 = 2400），Full 放不下
        strategy = select_strategy(
            written_chapters=chapters,
            current_chapter=6,
            token_budget=3000,
        )
        assert isinstance(strategy, HybridContentStrategy)

    def test_summary_when_hybrid_also_exceeds(self):
        """Hybrid 也放不下时降级到 Summary"""
        # 大量章节，预算极小
        chapters = [
            {"chapter_number": i, "title": f"第{i}章", "content": "中" * 2000}
            for i in range(1, 20)
        ]
        strategy = select_strategy(
            written_chapters=chapters,
            current_chapter=20,
            token_budget=500,
        )
        assert isinstance(strategy, SummaryContentStrategy)

    def test_user_override_fulltext(self):
        """用户指定 fulltext 时强制使用"""
        chapters = [
            {"chapter_number": i, "title": f"第{i}章", "content": "中" * 2000}
            for i in range(1, 20)
        ]
        strategy = select_strategy(
            written_chapters=chapters,
            current_chapter=20,
            token_budget=500,
            strategy_name="fulltext",
        )
        assert isinstance(strategy, FulltextContentStrategy)

    def test_user_override_hybrid(self):
        """用户指定 hybrid 时强制使用"""
        strategy = select_strategy(
            written_chapters=[{"chapter_number": 1, "title": "章", "content": "短"}],
            current_chapter=2,
            token_budget=100000,
            strategy_name="hybrid",
        )
        assert isinstance(strategy, HybridContentStrategy)

    def test_user_override_summary(self):
        """用户指定 summary 时强制使用"""
        strategy = select_strategy(
            written_chapters=[{"chapter_number": 1, "title": "章", "content": "短"}],
            current_chapter=2,
            token_budget=100000,
            strategy_name="summary",
        )
        assert isinstance(strategy, SummaryContentStrategy)

    def test_no_chapters_returns_fulltext(self):
        """无前文章节时返回 Fulltext（build_previous_context 会返回"没有前文"）"""
        strategy = select_strategy(
            written_chapters=[],
            current_chapter=1,
            token_budget=100000,
        )
        assert isinstance(strategy, FulltextContentStrategy)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py::TestSelectStrategy -v`
Expected: FAIL — ImportError

- [ ] **Step 3: 在 context_strategy.py 中实现 select_strategy()**

在 `context_strategy.py` 文件末尾、`get_context_strategy()` 之后添加：

```python
def select_strategy(
    written_chapters: list[dict],
    current_chapter: int,
    token_budget: int,
    strategy_name: str | None = None,
    chapter_outlines: list[dict] | None = None,
) -> ContextStrategy:
    """根据 token 预算动态选择前文策略

    策略选择逻辑：
    1. 用户手动指定 → 直接使用
    2. 全部已写章节 token 总量 ≤ 前文预算 80% → Full（放得下就全放）
    3. Full 放不下 → Hybrid（近章全文 + 远章概要）
    4. Hybrid 也放不下（近章全文就超 60% 预算）→ Summary

    Args:
        written_chapters: 已写章节列表（含 content）
        current_chapter: 当前章节号
        token_budget: 前文上下文的 token 预算
        strategy_name: 用户手动指定的策略名
        chapter_outlines: 章节大纲列表（Hybrid 策略需要）
    """
    # 用户手动覆盖
    if strategy_name and strategy_name in _STRATEGY_MAP:
        return _STRATEGY_MAP[strategy_name]()

    if not written_chapters:
        return FulltextContentStrategy()

    # 计算 Full 策略所需 token
    full_tokens = 0
    for ch in written_chapters:
        ch_num = ch.get("chapter_number", 0)
        if ch_num >= current_chapter:
            continue
        content = ch.get("content", "")
        if not content:
            continue
        title = ch.get("title", "")
        full_tokens += estimate_tokens(f"第{ch_num}章《{title}》\n{content}")

    # Full 放得下
    if full_tokens <= token_budget * 0.8:
        return FulltextContentStrategy()

    # Hybrid：检查近章全文是否能放进 60% 预算
    fulltext_budget = int(token_budget * 0.6)
    recent_tokens = 0
    for ch in reversed(written_chapters):
        ch_num = ch.get("chapter_number", 0)
        if ch_num >= current_chapter:
            continue
        content = ch.get("content", "")
        if not content:
            continue
        title = ch.get("title", "")
        part_tokens = estimate_tokens(f"第{ch_num}章《{title}》\n{content}")
        recent_tokens += part_tokens
        if recent_tokens > fulltext_budget:
            # 近章全文都放不进 60% 预算 → 降级 Summary
            return SummaryContentStrategy()

    return HybridContentStrategy()
```

- [ ] **Step 4: 在 test_context_strategy.py 中更新 import**

在测试文件顶部的 import 中添加 `select_strategy`：

```python
from app.agents.context_strategy import (
    FulltextContentStrategy,
    HybridContentStrategy,
    SummaryContentStrategy,
    get_context_strategy,
    select_strategy,
)
```

- [ ] **Step 5: 运行全部 context_strategy 测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/context_strategy.py backend/tests/test_context_strategy.py
git commit -m "feat(context_strategy): 新增 select_strategy 基于 token 预算动态选择策略"
```


### Task 6: _loaded_keys ContextVar

**Files:**
- Modify: `backend/app/agents/tool_context.py` — 新增 ContextVar 和存取函数

- [ ] **Step 1: 在 tool_context.py 中新增 _loaded_keys**

在 `_current_tool_cache` 定义之后添加：

```python
# 预加载数据声明 — ProjectContextAssembler 构建完 context 后设置
# 值为 list[str]，如 ["world_setting", "characters_index", "style_constraints"]
# knowledge_search 据此附加提示信息，但不截断输出
_current_loaded_keys: ContextVar[list[str] | None] = ContextVar("loaded_keys", default=None)


def set_loaded_keys(keys: list[str]) -> None:
    """设置当前请求的预加载数据类型列表"""
    _current_loaded_keys.set(keys)


def get_loaded_keys() -> list[str] | None:
    """获取当前请求的预加载数据类型列表"""
    return _current_loaded_keys.get()
```

同时更新 `set_tool_context` 和 `reset_tool_context`，让 loaded_keys 跟随请求生命周期：

在 `set_tool_context` 的 tokens 列表中追加：

```python
def set_tool_context(
    model_config_id: int | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
):
    """Set tool context for the current request, return reset tokens"""
    tokens = []
    if model_config_id is not None:
        tokens.append(_current_model_config_id.set(model_config_id))
    if user_id is not None:
        tokens.append(_current_user_id.set(user_id))
    if project_id is not None:
        tokens.append(_current_project_id.set(project_id))
    # 重置 loaded_keys（新请求开始时为空）
    tokens.append(_current_loaded_keys.set(None))
    return tokens
```

- [ ] **Step 2: 运行现有测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/test_tool_cache.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tool_context.py
git commit -m "feat(tool_context): 新增 _loaded_keys ContextVar 用于预加载数据声明"
```


### Task 7: ProjectContextAssembler 重构

**Files:**
- Modify: `backend/app/agents/agent_context.py` — 完全重构
- Create: `backend/tests/test_agent_context.py`

**说明：** 这是核心重构任务。`build_agent_context` 和 `build_lightweight_context` 被替换为 `ProjectContextAssembler` 类。保留 `BudgetTracker` 作为内部类。保留 `build_agent_context` 函数签名作为向后兼容的 thin wrapper（`chapter_quality.py` 等调用方不立即迁移）。

- [ ] **Step 1: 写 ProjectContextAssembler 失败测试**

创建 `backend/tests/test_agent_context.py`：

```python
"""ProjectContextAssembler 单元测试"""
import pytest
from unittest.mock import patch, MagicMock
from app.agents.agent_context import ProjectContextAssembler
from app.agents.constants import Phase


class TestProjectContextAssembler:
    def _mock_kb(self):
        """创建 mock KnowledgeBaseService"""
        kb = MagicMock()
        kb.batch_read_for_context.return_value = {
            "world_setting": {"core_concept": "魔法世界", "tiered_settings": {"red": ["禁止施法"]}, "key_locations": ["王城"]},
            "characters": [{"id": 1, "name": "张三", "role": "主角", "core_motivation": "复仇", "personality": "坚韧"}],
            "relations": [],
            "style_constraints": {"taboo_words": ["不禁"], "forbidden_patterns": [], "abstract_rules": []},
            "outline": {"title": "测试小说", "chapter_count_confirmed": 10, "summary": "测试摘要"},
            "chapter_outlines": [{"chapter_number": 1, "title": "第一章", "plot": "起风了", "scene": "", "characters": "", "conflict": "", "hook": "", "turning_point": "", "transition": "", "ending": "", "opening_state": "", "emotional_arc": "", "key_scenes": [], "pacing_note": "", "target_words": 3000, "confirmed": True}],
            "plot_blocks": [{"id": 1, "title": "第一幕", "chapter_start": 1, "chapter_end": 5, "expected_mood": "紧张"}],
            "plot_questions": [],
            "subplots": [],
            "foreshadowings": [{"id": 1, "content": "伏笔", "planted_chapter": 1, "expected_resolve_chapter": 5, "status": "planted"}],
            "timeline": [{"chapter_number": 1, "summary": "第一章概要", "emotion_tag": "紧张"}],
            "style_snapshots": [],
            "chapters": [{"chapter_number": 1, "title": "第一章", "content": "风起了。" * 100}],
            "changes": [],
            "previous_closing": "风起了。" * 50,
        }
        kb.validate_prerequisites.return_value = {"blocked": [], "warnings": [], "validated": True}
        return kb

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_phase_includes_previous_text(self, MockKB):
        """WRITING 阶段输出包含 previous_text"""
        MockKB.return_value = self._mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        assert "project_data" in result
        assert "previous_text" in result
        assert result["previous_text"] != ""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_incubation_phase_no_previous_text(self, MockKB):
        """INCUBATION 阶段前文预算为 0，不加载 previous_text"""
        MockKB.return_value = self._mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.INCUBATION.value,
            current_chapter_number=None,
        )
        assert result.get("previous_text", "") == ""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_output_contains_loaded_keys(self, MockKB):
        """输出包含 loaded_keys 列表"""
        MockKB.return_value = self._mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        assert "loaded_keys" in result
        assert isinstance(result["loaded_keys"], list)

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_lightweight_mode_for_small_window(self, MockKB):
        """极小窗口触发轻量模式"""
        MockKB.return_value = self._mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=4096,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        assert result.get("_mode") == "lightweight"

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_budget_used_tracked(self, MockKB):
        """输出包含预算使用追踪"""
        MockKB.return_value = self._mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        assert "_budget_used" in result
        assert "_budget_max" in result

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_fulltext_strategy_no_duplicate_closing(self, MockKB):
        """Full 策略时不重复加载 previous_chapter_closing"""
        mock_kb = self._mock_kb()
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=1000000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        # project_data 中不应包含 previous_chapter_closing（已被 previous_text 包含）
        assert "previous_chapter_closing" not in result.get("project_data", {})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_context.py -v`
Expected: FAIL — ImportError (ProjectContextAssembler 不存在)

- [ ] **Step 3: 重写 agent_context.py**

完整替换 `backend/app/agents/agent_context.py`。核心结构：

```python
"""Phase-aware context builder — ProjectContextAssembler

统一上下文组装入口，整合 BudgetAllocator + context_strategy + 跨请求缓存。
取代旧版 build_agent_context / build_lightweight_context。
"""

import json
import logging

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.token_budget import estimate_tokens
from app.agents.constants import Phase
from app.agents.budget_allocator import BudgetAllocator
from app.agents.context_cache import context_cache
from app.agents.context_strategy import select_strategy
from app.agents.services.stores.base import _BaseStore

logger = logging.getLogger(__name__)


class BudgetTracker:
    """Token budget tracker — 逐项控制预算"""

    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max

    def add(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max - self.used)


# 轻量模式阈值：context_window 的 5% 以下触发
_LIGHTWEIGHT_RATIO = 0.05


class ProjectContextAssembler:
    """统一上下文组装器

    三层职责：
    1. BudgetAllocator 分配预算
    2. _load_phase_data 加载项目数据（精简预加载）
    3. _load_previous_context 调用 context_strategy 组装前文
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.kb = KnowledgeBaseService(project_id)

    # 可缓存的数据类型
    _CACHEABLE_TYPES = {"world_setting", "characters", "relations", "style_constraints", "outline"}

    def _load_with_cache(self, current_chapter_number: int | None) -> dict:
        """加载数据，可缓存类型优先查缓存，miss 时走批量读取后写缓存

        缓存策略：
        - 先查缓存，记录命中/未命中的数据类型
        - 走一次 batch_read_for_context（始终需要不可缓存数据如 chapters/timeline）
        - 对未命中类型写入缓存
        - 用缓存命中数据覆盖 batch_read 结果（缓存基于 version_tag，
          命中说明数据未变化，可安全覆盖）
        """
        from app.agents.services.stores.base import _BaseStore

        # 尝试从缓存命中
        cached_data = {}
        cache_miss_types = []
        for data_type in self._CACHEABLE_TYPES:
            version = _BaseStore.get_version(data_type)
            cached = context_cache.get(self.project_id, data_type, version)
            if cached is not None:
                cached_data[data_type] = cached
            else:
                cache_miss_types.append(data_type)

        # 始终需要 batch_read（不可缓存数据如 chapters/timeline 每次都需最新值）
        raw = self.kb.batch_read_for_context(current_chapter_number)

        # 对未命中类型写入缓存
        for data_type in cache_miss_types:
            if data_type in raw and raw[data_type] is not None:
                version = _BaseStore.get_version(data_type)
                context_cache.set(self.project_id, data_type, version, raw[data_type])

        # 用缓存命中数据覆盖 batch_read 结果
        # 缓存命中意味着 version_tag 未变 → 数据与 DB 一致，可直接使用
        for data_type, cached_value in cached_data.items():
            raw[data_type] = cached_value

        return raw

    def build(
        self,
        context_window: int,
        phase: str,
        current_chapter_number: int | None = None,
        strategy_name: str | None = None,
    ) -> dict:
        """构建阶段感知的完整上下文

        Args:
            context_window: 模型上下文窗口大小
            phase: 当前阶段 (Phase.value)
            current_chapter_number: 当前章节号
            strategy_name: 用户手动指定的前文策略名

        Returns:
            dict 包含 project_data, previous_text, loaded_keys, 预算追踪
        """
        # 极小窗口走轻量模式
        allocation = BudgetAllocator.allocate(context_window, phase)
        if context_window <= 4096 or allocation.project_data_budget <= 2000:
            return self._build_lightweight(context_window, phase, current_chapter_number)

        # 尝试从缓存获取可缓存数据，miss 时走批量读取
        raw_data = self._load_with_cache(current_chapter_number)

        # 加载项目数据
        project_data = self._load_phase_data(raw_data, phase, allocation, current_chapter_number)

        # 加载前文
        previous_text = self._load_previous_context(
            raw_data, phase, allocation, current_chapter_number, strategy_name,
        )

        # 去重：如果 previous_text 非空（包含前文章节），则 project_data 中不需要 previous_chapter_closing
        if previous_text and "previous_chapter_closing" in project_data:
            del project_data["previous_chapter_closing"]

        # 总量溢出保护：project_data + previous_text 不超过 context_window 扣除固定项
        max_total = context_window - allocation.output_budget - allocation.safety_margin - allocation.system_prompt_budget
        project_data_str = json.dumps(project_data, ensure_ascii=False, default=str)
        total_used = estimate_tokens(project_data_str) + estimate_tokens(previous_text)
        if total_used > max_total:
            # 自动压缩：按 Important → Critical 反序裁剪（保留 Critical 数据）
            compressible_keys = [k for k in list(project_data.keys())[::-1]
                                 if k not in ("current_chapter_outline", "style_constraints", "prerequisites")]
            for key in compressible_keys:
                if total_used <= max_total:
                    break
                removed = project_data.pop(key, None)
                if removed is not None:
                    removed_str = json.dumps(removed, ensure_ascii=False, default=str)
                    total_used -= estimate_tokens(removed_str)
            # 重新计算
            project_data_str = json.dumps(project_data, ensure_ascii=False, default=str)
            total_used = estimate_tokens(project_data_str) + estimate_tokens(previous_text)

        loaded_keys = list(project_data.keys())

        return {
            "project_data": project_data,
            "previous_text": previous_text,
            "loaded_keys": loaded_keys,
            "_budget_used": estimate_tokens(json.dumps(project_data, ensure_ascii=False, default=str)),
            "_budget_max": context_window,
        }

    def _load_phase_data(
        self, raw_data: dict, phase: str, allocation, current_chapter_number: int | None,
    ) -> dict:
        """根据阶段和预算裁剪项目数据"""
        budget = BudgetTracker(allocation.project_data_budget)
        context: dict = {}

        if phase == Phase.INCUBATION.value:
            self._load_incubation_data(raw_data, budget, context)
        elif phase == Phase.STRUCTURE.value:
            self._load_structure_data(raw_data, budget, context)
        elif phase == Phase.WRITING.value:
            self._load_writing_data(raw_data, budget, context, current_chapter_number)
        elif phase == Phase.REVISION.value:
            self._load_revision_data(raw_data, budget, context)

        return context

    def _load_incubation_data(self, raw: dict, budget: BudgetTracker, ctx: dict):
        outline = raw.get("outline")
        if outline:
            data = {"title": outline.get("title", ""), "summary": (outline.get("summary") or "")[:100]}
            tokens = estimate_tokens(json.dumps(data, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["outline_index"] = data
                budget.add(tokens)

        ws = raw.get("world_setting")
        if ws:
            data_json = json.dumps(ws, ensure_ascii=False)
            if budget.can_add(estimate_tokens(data_json)):
                ctx["world_setting"] = ws
                budget.add(estimate_tokens(data_json))

    def _load_structure_data(self, raw: dict, budget: BudgetTracker, ctx: dict):
        # 角色索引
        chars = raw.get("characters", [])
        char_list = []
        for c in chars:
            info = {"id": c["id"], "name": c["name"], "role": c.get("role", ""), "core_motivation": c.get("core_motivation") or ""}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                char_list.append(info)
                budget.add(tokens)
        ctx["characters"] = char_list

        # 情节块
        blocks = raw.get("plot_blocks", [])
        block_list = []
        for b in blocks:
            info = {"id": b["id"], "title": b["title"], "chapter_start": b["chapter_start"], "chapter_end": b.get("chapter_end"), "expected_mood": b.get("expected_mood")}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                block_list.append(info)
                budget.add(tokens)
        ctx["plot_blocks"] = block_list

        # 伏笔概览
        fs_list = raw.get("foreshadowings", [])
        fs_mini = []
        for f in fs_list:
            info = {"id": f["id"], "content": (f.get("content") or "")[:60], "planted_chapter": f.get("planted_chapter"), "expected_resolve_chapter": f.get("expected_resolve_chapter"), "status": f.get("status")}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                fs_mini.append(info)
                budget.add(tokens)
        ctx["foreshadowings"] = fs_mini

    def _load_writing_data(self, raw: dict, budget: BudgetTracker, ctx: dict, chapter_number: int | None):
        # 角色索引（含 personality[:100]）
        chars = raw.get("characters", [])
        char_list = []
        for c in chars:
            info = {"id": c["id"], "name": c["name"], "role": c.get("role", ""), "core_motivation": c.get("core_motivation") or "", "personality": (c.get("personality") or "")[:100]}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                char_list.append(info)
                budget.add(tokens)
        ctx["characters"] = char_list

        # 世界观精简版
        ws = raw.get("world_setting")
        if ws:
            data = {"core_concept": ws.get("core_concept") or "", "red_settings": (ws.get("tiered_settings") or {}).get("red", []), "key_locations": ws.get("key_locations") or []}
            tokens = estimate_tokens(json.dumps(data, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["world_setting"] = data
                budget.add(tokens)

        # 伏笔：pending_reclaim 和 overdue 需要从批量数据中计算
        all_fs = raw.get("foreshadowings", [])
        # pending_reclaim 状态的伏笔（对应旧版 kb.foreshadowings.list_pending()）
        pending_fs = [f for f in all_fs if f.get("status") == "pending_reclaim"]
        ctx["pending_foreshadowings"] = [{"id": f["id"], "content": (f.get("content") or "")[:60], "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in pending_fs]
        # overdue：active 或 pending_reclaim 且 expected_resolve_chapter < 当前章节
        # 对应旧版 kb.foreshadowings.list_overdue(chapter_number)
        if chapter_number:
            overdue_fs = [f for f in all_fs
                          if f.get("status") in ("active", "pending_reclaim")
                          and (f.get("expected_resolve_chapter") or 999999) < chapter_number]
            ctx["overdue_foreshadowings"] = [{"id": f["id"], "content": (f.get("content") or "")[:60], "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in overdue_fs]

        # 风格约束
        style = raw.get("style_constraints")
        if style:
            data = {"taboo_words": style.get("taboo_words") or [], "forbidden_patterns": style.get("forbidden_patterns") or [], "abstract_rules": style.get("abstract_rules") or []}
            tokens = estimate_tokens(json.dumps(data, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["style_constraints"] = data
                budget.add(tokens)

        # 当前章节大纲
        if chapter_number:
            outlines = raw.get("chapter_outlines", [])
            co = next((o for o in outlines if o.get("chapter_number") == chapter_number), None)
            if co:
                ctx["current_chapter_outline"] = co
                budget.add(estimate_tokens(json.dumps(co, ensure_ascii=False)))

        # 上一章结尾（仅在非 Full 策略时单独加载，Full 策略由 previous_text 包含）
        # 去重逻辑在 build() 层处理，这里先加载，后续由策略决定是否剔除
        closing = raw.get("previous_closing")
        if closing:
            closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
            tokens = estimate_tokens(closing_json)
            if budget.can_add(tokens):
                ctx["previous_chapter_closing"] = closing.strip()
                budget.add(tokens)

        # 当前情节块
        if chapter_number:
            blocks = raw.get("plot_blocks", [])
            for b in blocks:
                start = b.get("chapter_start", 0)
                end = b.get("chapter_end") or 999999
                if start <= chapter_number <= end:
                    ctx["current_plot_block"] = {"title": b.get("title"), "expected_mood": b.get("expected_mood"), "must_happen": b.get("must_happen") or []}
                    break

        # 最近的变更决策
        changes = raw.get("changes", [])
        applied = [c for c in changes if c.get("status") == "applied"]
        if applied:
            decision_list = []
            for d in applied[:5]:
                decision_list.append({
                    "target_type": d.get("target_type"),
                    "decision": d.get("author_decision", "unknown"),
                    "summary": (d.get("description") or "")[:80],
                })
            decision_json = json.dumps(decision_list, ensure_ascii=False)
            decision_tokens = estimate_tokens(decision_json)
            if budget.can_add(decision_tokens):
                ctx["recent_decisions"] = decision_list
                budget.add(decision_tokens)

        # 当前章的情节问题
        if chapter_number:
            questions = raw.get("plot_questions", [])
            chapter_qs = [q for q in questions if q.get("chapter_number") == chapter_number]
            ctx["questions_for_chapter"] = [
                {"id": q["id"], "question": (q.get("question_text") or "")[:60]}
                for q in chapter_qs
            ]

        # 时间线最近 5 条
        timeline = raw.get("timeline", [])
        if timeline:
            recent = timeline[:5]
            ctx["recent_timeline"] = [
                {"chapter": t.get("chapter_number"), "summary": (t.get("summary") or "")[:80], "emotion_tag": t.get("emotion_tag")}
                for t in recent
            ]

        # 关系演变规划
        if chapter_number:
            relations = raw.get("relations", [])
            # 从 raw_data 中的 plot 数据提取 evolution plans
            # 注意：batch_read_for_context 未包含 evolution_plans 数据
            # 此处产生 1 次额外 DB 查询（对比旧版 ~20 次，已大幅减少）
            # 未来优化：在 CharacterStore 新增 _read_evolution_plans_with_session(db)，
            # 并在 batch_read_for_context 中调用，可完全消除额外查询
            pending_plans = self.kb.characters.list_evolution_plans_triggering_at(chapter_number)
            if pending_plans:
                evolution_cues = []
                rel_map = {r["id"]: r for r in relations}
                char_list = raw.get("characters", [])
                char_map = {c["id"]: c["name"] for c in char_list}
                for plan in pending_plans:
                    rel = rel_map.get(plan.get("relation_id"), {})
                    char_a_name = char_map.get(rel.get("character_a_id"), "?")
                    char_b_name = char_map.get(rel.get("character_b_id"), "?")
                    cue = (
                        f"第{plan.get('trigger_chapter')}章，{char_a_name}和{char_b_name}的关系将发生变化："
                        f"{plan.get('status_before') or '待定'} → {plan.get('status_after', '未知')}，"
                        f"信任度 {plan.get('trust_before') or 50} → {plan.get('trust_after') or 50}。"
                        f"事件：{plan.get('event_description', '')}"
                    )
                    evolution_cues.append(cue)
                cues_json = json.dumps(evolution_cues, ensure_ascii=False)
                cues_tokens = estimate_tokens(cues_json)
                if budget.can_add(cues_tokens):
                    ctx["relation_evolution_cues"] = evolution_cues
                    budget.add(cues_tokens)

        # 前置条件校验（从批量数据中校验，避免额外 DB 查询）
        prereq = self._validate_prerequisites_from_raw(raw, chapter_number)
        ctx["prerequisites"] = prereq

    def _validate_prerequisites_from_raw(self, raw: dict, chapter_number: int | None) -> dict:
        """从批量读取结果校验前置条件，避免额外 DB 查询

        与 kb.validate_prerequisites 逻辑一致，但数据来源为 raw_data 而非独立 DB 查询。
        """
        blocked = []
        warnings = []

        # 1. 章节大纲
        if chapter_number:
            outlines = raw.get("chapter_outlines", [])
            co = next((o for o in outlines if o.get("chapter_number") == chapter_number), None)
            if not co:
                blocked.append({"type": "chapter_outline_missing", "chapter": chapter_number,
                                "message": f"第{chapter_number}章大纲不存在", "severity": "error"})
            elif not co.get("confirmed"):
                blocked.append({"type": "outline_unconfirmed", "chapter": chapter_number,
                                "message": f"第{chapter_number}章大纲尚未确认", "severity": "error"})

        # 2. 角色
        chars = raw.get("characters", [])
        if not chars:
            blocked.append({"type": "character_missing", "message": "项目中没有任何角色", "severity": "error"})

        # 3. 世界观
        ws = raw.get("world_setting")
        if not ws or not ws.get("core_concept"):
            blocked.append({"type": "world_setting_missing", "message": "项目世界观尚未完善", "severity": "error"})

        # 4. 伏笔
        fs_list = raw.get("foreshadowings", [])
        if not fs_list:
            warnings.append({"type": "foreshadowing_empty", "message": "当前无伏笔记录", "severity": "warning"})

        # 5. 风格约束
        style = raw.get("style_constraints")
        if not style:
            warnings.append({"type": "style_constraints_missing", "message": "尚未设置风格约束", "severity": "warning"})

        # 6. 情节块
        blocks = raw.get("plot_blocks", [])
        if not blocks:
            warnings.append({"type": "plot_block_empty", "message": "尚未创建情节块", "severity": "warning"})

        # 7. 上一章结尾
        if chapter_number and chapter_number > 1:
            closing = raw.get("previous_closing")
            if not closing:
                warnings.append({"type": "previous_chapter_empty", "chapter": chapter_number - 1,
                                 "message": f"第{chapter_number - 1}章尚无正文", "severity": "warning"})

        # 8. 关系演变（简化检查，不额外查 DB）
        # relations 数据已在 raw 中，但 evolution plans 需额外查询
        # 此处只做简单提示
        relations = raw.get("relations", [])
        has_plans = any(r.get("plans") for r in relations if isinstance(r.get("plans"), list) and r["plans"])
        if not has_plans:
            warnings.append({"type": "relation_evolution_empty", "message": "尚未创建关系演变规划", "severity": "warning"})

        # 9. 时间线
        timeline = raw.get("timeline", [])
        if not timeline:
            warnings.append({"type": "timeline_empty", "message": "尚未创建时间线记录", "severity": "warning"})

        return {"blocked": blocked, "warnings": warnings, "validated": True}

    def _load_revision_data(self, raw: dict, budget: BudgetTracker, ctx: dict):
        # 世界观精简版
        ws = raw.get("world_setting")
        if ws:
            ws_mini = {"core_concept": ws.get("core_concept", ""), "red_settings": (ws.get("tiered_settings") or {}).get("red", []), "key_locations": ws.get("key_locations", [])}
            tokens = estimate_tokens(json.dumps(ws_mini, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["world_setting"] = ws_mini
                budget.add(tokens)

        # 角色索引
        chars = raw.get("characters", [])
        chars_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
        tokens = estimate_tokens(json.dumps(chars_index, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["characters"] = chars_index
            budget.add(tokens)

        # 伏笔
        fs_list = raw.get("foreshadowings", [])
        fs_mini = [{"id": f["id"], "content": (f.get("content") or "")[:60], "status": f.get("status"), "planted_chapter": f.get("planted_chapter"), "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in fs_list]
        tokens = estimate_tokens(json.dumps(fs_mini, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["foreshadowings"] = fs_mini
            budget.add(tokens)

        # 时间线
        timeline = raw.get("timeline", [])
        recent = timeline[:20]
        tl_mini = [{"chapter_number": t.get("chapter_number"), "summary": (t.get("summary") or "")[:80], "emotion_tag": t.get("emotion_tag")} for t in recent]
        tokens = estimate_tokens(json.dumps(tl_mini, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["timeline"] = tl_mini
            budget.add(tokens)

        # 风格约束
        style = raw.get("style_constraints")
        if style:
            tokens = estimate_tokens(json.dumps(style, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["style_constraints"] = style
                budget.add(tokens)

    def _load_previous_context(
        self, raw: dict, phase: str, allocation, chapter_number: int | None, strategy_name: str | None,
    ) -> str:
        """调用 context_strategy 组装前文"""
        if allocation.previous_text_budget <= 0 or not chapter_number or chapter_number <= 1:
            return ""

        chapters = raw.get("chapters", [])
        # 过滤出当前章节之前且有内容的章节
        written = [ch for ch in chapters if ch.get("chapter_number", 0) < chapter_number and ch.get("content")]

        if not written:
            return ""

        chapter_outlines = raw.get("chapter_outlines", [])

        strategy = select_strategy(
            written_chapters=written,
            current_chapter=chapter_number,
            token_budget=allocation.previous_text_budget,
            strategy_name=strategy_name,
            chapter_outlines=chapter_outlines,
        )

        return strategy.build_previous_context(
            written_chapters=written,
            current_chapter=chapter_number,
            chapter_outlines=chapter_outlines,
            token_budget=allocation.previous_text_budget,
        )

    def _build_lightweight(
        self, context_window: int, phase: str, current_chapter_number: int | None,
    ) -> dict:
        """轻量模式 — 只加载核心索引"""
        kb = self.kb
        max_tokens = max(int(context_window * _LIGHTWEIGHT_RATIO), 2000)
        budget = BudgetTracker(max_tokens)
        context: dict = {}

        outline = kb.outlines.get()
        if outline:
            outline_index = {"title": outline.get("title") or "未命名", "chapter_count": outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0, "summary": (outline.get("summary") or "")[:100]}
            context["outline_index"] = outline_index
            budget.add(estimate_tokens(json.dumps(outline_index, ensure_ascii=False)))

        chars = kb.characters.list_characters()
        char_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
        context["character_index"] = char_index
        budget.add(estimate_tokens(json.dumps(char_index, ensure_ascii=False)))

        context["phase"] = phase
        if current_chapter_number:
            context["current_chapter_number"] = current_chapter_number

        ws = kb.world_setting.get()
        if ws:
            red = (ws.get("tiered_settings") or {}).get("red", [])
            if red:
                context["critical_rules"] = red[:3]
                budget.add(estimate_tokens(json.dumps(red[:3], ensure_ascii=False)))

        if phase in (Phase.WRITING.value, Phase.REVISION.value) and current_chapter_number:
            try:
                co = kb.outlines.get_chapter_outline(current_chapter_number)
                if co:
                    co_data = {"chapter_number": co.get("chapter_number"), "title": co.get("title") or "", "scene": co.get("scene") or "", "characters": co.get("characters") or "", "emotional_arc": co.get("emotional_arc") or "", "key_scenes": co.get("key_scenes") or [], "target_words": co.get("target_words")}
                    co_json = json.dumps(co_data, ensure_ascii=False)
                    if budget.can_add(estimate_tokens(co_json)):
                        context["current_chapter_outline"] = co_data
                        budget.add(estimate_tokens(co_json))
            except Exception:
                pass

            if current_chapter_number > 1:
                prev = kb.chapters.get_by_number(current_chapter_number - 1)
                if prev and prev.get("content"):
                    closing = prev["content"][-300:]
                    closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
                    if budget.can_add(estimate_tokens(closing_json)):
                        context["previous_chapter_closing"] = closing.strip()
                        budget.add(estimate_tokens(closing_json))

        return {
            "project_data": context,
            "previous_text": "",
            "loaded_keys": list(context.keys()),
            "_budget_used": budget.used,
            "_budget_max": budget.max,
            "_mode": "lightweight",
        }


# ========== 向后兼容 ==========

def build_agent_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
    context_window: int | None = None,
) -> dict:
    """向后兼容入口 — agent.py 过渡期使用

    Args:
        context_window: 模型上下文窗口大小。优先使用此参数。
            如未提供，使用 get_context_window() 获取。
        max_tokens: 已废弃，仅当 context_window 未提供时用作 fallback。
    """
    from app.agents.token_budget import get_context_window as _get_context_window
    window = context_window or _get_context_window()

    assembler = ProjectContextAssembler(project_id)
    result = assembler.build(
        context_window=window,
        phase=phase,
        current_chapter_number=current_chapter_number,
    )
    # 返回旧格式（project_data 展平）
    flat = dict(result.get("project_data", {}))
    flat["_budget_used"] = result.get("_budget_used", 0)
    flat["_budget_max"] = result.get("_budget_max", 0)
    if result.get("_mode"):
        flat["_mode"] = result["_mode"]
    return flat
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_context.py -v`
Expected: ALL PASS

- [ ] **Step 5: 运行回归测试确认不破坏 chapter_quality.py 等调用方**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/agent_context.py backend/tests/test_agent_context.py
git commit -m "refactor(agent_context): 重构为 ProjectContextAssembler 统一上下文组装"
```


### Task 8: agent.py 调用点迁移

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 更新 agent.py 中的 import 和调用**

修改 `backend/app/api/agent.py`：

1. 替换 import：
```python
# 旧
from app.agents.agent_context import build_agent_context
# 新
from app.agents.agent_context import ProjectContextAssembler
```

2. 替换 `agent_chat` 中的调用点（约 L220 附近）：

```python
    # 旧
    context = build_agent_context(
        project_id,
        phase=phase,
        current_chapter_number=req.current_chapter_number,
    )

    # 新
    assembler = ProjectContextAssembler(project_id)
    context_result = assembler.build(
        context_window=context_window,
        phase=phase,
        current_chapter_number=req.current_chapter_number,
    )

    # 构建 context_block：分离 project_data 和 previous_text
    project_data_block = json.dumps(context_result["project_data"], ensure_ascii=False, default=str)
    previous_text = context_result.get("previous_text", "")
```

3. 更新 system prompt 组装（在 `system_content` 构建处）：

```python
    # 组装 system prompt
    phase_label = PHASE_LABELS.get(phase, "未知阶段")

    # 构建前置条件警告
    prereq = context_result.get("project_data", {}).get("prerequisites", {})
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

    # previous_text 独立段落
    previous_section = ""
    if previous_text:
        previous_section = f"\n\n## 前文上下文\n\n{previous_text}"

    system_content = AGENT_SYSTEM_PROMPT.format(
        phase_label=phase_label,
        project_name=project.name,
        context_block=project_data_block,
        context_prerequisites_warning=context_prerequisites_warning,
    ) + previous_section
```

4. 更新 `context_window` 压缩逻辑（当 system 消息超预算时）：

```python
    # Calculate history budget and truncate
    system_used = estimate_tokens(system_content)
    history_budget = int(context_window * 0.7) - system_used
    if history_budget <= 0:
        # 系统消息占用过多 — 压缩为精简版
        slim_data = {
            k: v for k, v in context_result.get("project_data", {}).items()
            if k in ("outline", "style_constraints", "current_plot_block",
                      "pending_foreshadowings", "overdue_foreshadowings")
        }
        slim_block = json.dumps(slim_data, ensure_ascii=False, default=str)
        system_content = AGENT_SYSTEM_PROMPT.format(
            phase_label=phase_label,
            project_name=project.name,
            context_block=slim_block,
            context_prerequisites_warning=context_prerequisites_warning,
        )
        system_used = estimate_tokens(system_content)
        min_history = estimate_tokens(req.message) * 4
        history_budget = max(min_history, int(context_window * 0.3) - system_used)
```

5. 在 `set_tool_context` 之后设置 `loaded_keys`：

```python
    # Set tool context (including project_id for cognitive tools)
    context_tokens = set_tool_context(
        model_config_id=req.model_config_id,
        user_id=current_user.id,
        project_id=project_id,
    )

    # 设置预加载数据声明
    from app.agents.tool_context import set_loaded_keys
    loaded_keys = context_result.get("loaded_keys", [])
    if loaded_keys:
        set_loaded_keys(loaded_keys)
```

- [ ] **Step 2: 运行测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 3: 手动冒烟测试**

重启后端：`docker compose restart backend`，然后在浏览器中打开项目，发送 Agent 消息，确认正常响应。

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "refactor(agent): 迁移调用点到 ProjectContextAssembler，传递 context_window"
```


### Task 9: knowledge_search 感知 _loaded_keys

**Files:**
- Modify: `backend/app/agents/tools/perception/knowledge_search.py`

- [ ] **Step 1: 在 knowledge_search 中附加预加载提示**

在 `knowledge_search.py` 中，函数末尾 `return` 之前，检查 `_loaded_keys` 并在结果中附加提示：

1. 新增 import：
```python
from app.agents.tool_context import get_loaded_keys
```

2. 在 `filtered = {k: v for k, v in results.items() if v}` 之后、`if not filtered:` 之前，插入：

```python
    # 感知预加载数据：附加提示信息，不截断不拒绝输出
    loaded_keys = get_loaded_keys()
    if loaded_keys and filtered:
        preloaded_in_result = []
        key_mapping = {
            "world_setting": "world_setting",
            "characters": "characters",
            "style_constraints": "style_constraints",
        }
        for ctx_key, result_key in key_mapping.items():
            if ctx_key in loaded_keys and result_key in filtered:
                preloaded_in_result.append(result_key)
        if preloaded_in_result:
            filtered["_preloaded_hint"] = f"以下数据的基础信息已在项目上下文中预加载：{', '.join(preloaded_in_result)}。此处返回完整版本供参考。"
```

- [ ] **Step 2: 运行测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/perception/knowledge_search.py
git commit -m "feat(knowledge_search): 感知 _loaded_keys 附加预加载提示"
```


### Task 10: 去重规则 + Store 写操作 _bump_version

**Files:**
- Modify: `backend/app/agents/agent_context.py` — Full 策略去重 previous_chapter_closing
- Modify: Store 写操作调用 `_bump_version`

- [ ] **Step 1: 去重逻辑已在 Task 7 的 build() 中实现**

去重规则：如果 `previous_text` 非空，则 `project_data` 中的 `previous_chapter_closing` 已被前文包含，自动删除。此逻辑已在 Task 7 的 `build()` 方法中实现，无需重复添加。

- [ ] **Step 2: 在 Store 写操作中调用 _bump_version**

需要在以下 Store 的写方法中添加 `_bump_version` 调用：

| Store | 写方法 | data_type |
|-------|--------|-----------|
| `WorldSettingStore` | `update_by_id`, `create` | `"world_setting"` |
| `CharacterStore` | `create_character`, `update_character` | `"characters"` |
| `StyleStore` | `update_constraints_by_id`, `create_constraints` | `"style_constraints"` |
| `OutlineStore` | `update`, `create` | `"outline"` |

典型模式（以 `world_setting_store.py` 为例）：

```python
    def update_by_id(self, setting_id: int, data: dict) -> dict | None:
        modified = False
        with self.session() as db:
            obj = db.query(WorldSetting).filter(
                WorldSetting.id == setting_id,
                WorldSetting.project_id == self.project_id,
            ).first()
            if obj:
                for key, value in data.items():
                    if hasattr(obj, key):
                        setattr(obj, key, value)
                modified = True
        # 仅在实际发生写入时 bump version
        # session() 的 __exit__ 在无异常时 commit，异常时 rollback 并 re-raise
        # 因此 _bump_version 只在 commit 成功后执行
        if modified:
            self._bump_version("world_setting")
        return self.get()
```

在每个写方法的 `with self.session()` 块之后，添加 `self._bump_version(data_type)` 调用。

- [ ] **Step 3: 运行全部测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/agent_context.py backend/app/agents/services/stores/world_setting_store.py backend/app/agents/services/stores/character_store.py backend/app/agents/services/stores/style_store.py backend/app/agents/services/stores/outline_store.py
git commit -m "feat: 去重 previous_chapter_closing + Store 写操作 _bump_version"
```


### Task 11: 端到端验证 + 清理

**Files:**
- 全部测试文件

- [ ] **Step 1: 运行完整测试套件**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --timeout=60`
Expected: ALL PASS

- [ ] **Step 2: 验证 BudgetAllocator 在各窗口大小下的行为**

手动验证：
```python
from app.agents.budget_allocator import BudgetAllocator
from app.agents.constants import Phase

# 1M 窗口
alloc = BudgetAllocator.allocate(1_000_000, Phase.WRITING.value)
print(f"1M WRITING: history={alloc.history_budget}, prev={alloc.previous_text_budget}, proj={alloc.project_data_budget}")

# 128K 窗口
alloc = BudgetAllocator.allocate(128000, Phase.WRITING.value)
print(f"128K WRITING: history={alloc.history_budget}, prev={alloc.previous_text_budget}, proj={alloc.project_data_budget}")

# 8K 窗口
alloc = BudgetAllocator.allocate(8192, Phase.WRITING.value)
print(f"8K WRITING: history={alloc.history_budget}, prev={alloc.previous_text_budget}, proj={alloc.project_data_budget}")
```

Expected:
- 1M: history=83K, prev=581K, proj=166K
- 128K: history=10.6K, prev=74.4K, proj=21.2K
- 8K: 均为非负小值

- [ ] **Step 3: 验证 context_strategy 动态策略选择**

```python
from app.agents.context_strategy import select_strategy, FulltextContentStrategy, HybridContentStrategy, SummaryContentStrategy

# 短篇 — Full
s = select_strategy([{"chapter_number": 1, "content": "短"}], 2, 100000)
assert isinstance(s, FulltextContentStrategy)

# 长篇 + 有限预算 — Hybrid
chapters = [{"chapter_number": i, "content": "中" * 1000} for i in range(1, 10)]
s = select_strategy(chapters, 10, 3000)
assert isinstance(s, HybridContentStrategy)

# 极端 — Summary
s = select_strategy(chapters, 10, 500)
assert isinstance(s, SummaryContentStrategy)
```

- [ ] **Step 4: 重启后端 + 手动冒烟测试**

```bash
docker compose restart backend
```

在浏览器中：
1. 打开已有项目
2. 切换到 WRITING 阶段
3. 发送一条 Agent 消息（如"写一段正文"）
4. 确认 Agent 正常响应，system prompt 中包含前文上下文
5. 使用 knowledge_search 工具搜索"角色"
6. 确认返回结果中包含 `_preloaded_hint` 提示

- [ ] **Step 5: 最终 Commit（如有修复）**

```bash
git add -A
git commit -m "test: 端到端验证通过"
```


---

## 审查修正记录

> 日期：2026-06-16
> 对照源码审查所有优化项的正确性，修复发现的问题

### 修正摘要

| # | 问题 | 修正位置 | 修正内容 |
|---|------|---------|---------|
| R1 | `outline_store._read_all_outlines_with_session` 方法名错误 | Task 4 | 改为 `_read_chapter_outlines_with_session`（与实际方法名一致） |
| R2 | `chapter_store._read_all_with_session` 不存在，且 Chapter 模型无 `project_id` 列 | Task 4 Step 2 | 新增此方法，使用 JOIN ChapterOutline 查询 |
| R3 | `change_store._read_all_with_session` 不存在 | Task 4 Step 2 | 新增此方法 |
| R4 | `batch_read_for_context` 用 `hasattr` 静默降级 | Task 4 Step 1 | 移除 `hasattr`，改为 Task 4 Step 2 保证方法存在后直接调用，缺少则抛异常（符合"不打补丁"原则） |
| R5 | `_load_writing_data` 缺失 `recent_decisions`、`questions_for_chapter`、`recent_timeline`、`relation_evolution_cues` | Task 7 | 补充所有缺失字段，与源码 `_load_writing_context` 对齐 |
| R6 | `_load_writing_data` 调用 `self.kb.validate_prerequisites()` 破坏批量读取优化 | Task 7 | 新增 `_validate_prerequisites_from_raw()` 方法，从批量数据校验，不创建新 DB session |
| R7 | `build_agent_context` 向后兼容包装器用 `max_tokens * 8` 魔数 | Task 7 | 改为接受 `context_window` 参数，默认从 `get_context_window()` 获取 |
| R8 | ContextCache 定义但未在 ProjectContextAssembler 中使用 | Task 7 | 新增 `_load_with_cache()` 方法，缓存可缓存数据类型 |
| R9 | `_bump_version` 在无实际写入时仍递增 | Task 10 | 增加 `modified` 标志，仅在实际写入数据时才 bump version |
| R10 | 不验证 project_data + previous_text 总量是否超 context_window | Task 7 | 在 `build()` 返回前增加总量检查，超限时自动压缩 Important 数据 |
| R11 | `_load_writing_data` 伏笔逻辑错误：`status="overdue"` 不是有效状态 | Task 7 | 修正伏笔过滤逻辑，与源码 `list_pending()`/`list_overdue()` 对齐 |
| R12 | `_load_with_cache` 缓存命中数据未覆盖 batch_read 结果 | Task 7 | 始终走 batch_read，但缓存命中数据覆盖 raw 中的对应字段 |
