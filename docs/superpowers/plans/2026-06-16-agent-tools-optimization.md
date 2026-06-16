# Agent 工具优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 工具从 43 个精简至 35 个，消除功能重叠，引入程序化成本控制

**Architecture:** 合并 5 组语义重叠工具（8 个删除 → 1 个新建），修复 expand_world_setting 控制流重叠，新增 cost_tier 元数据分类和 BudgetTracker 动态降级机制。所有变更保持向后兼容的导入层。

**Tech Stack:** Python 3.12 / LangChain Tools / FastAPI / pytest

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 删除 | `tools/creation/timeline_entry.py` | 已被 record_chapter_meta 包含 |
| 删除 | `tools/creation/batch_update_foreshadowing_status.py` | 将并入 update_foreshadowing |
| 删除 | `tools/creation/batch_confirm_outlines.py` | 将并入 generate_chapter_outline |
| 删除 | `tools/perception/check_chapter_transition.py` | 将并入 consistency_scan |
| 删除 | `tools/perception/consistency_check.py` | 将并入 consistency_scan |
| 删除 | `tools/assist/suggest_foreshadowing.py` | 将并入 suggest_writing_direction |
| 删除 | `tools/assist/suggest_plot_twist.py` | 将并入 suggest_writing_direction |
| 删除 | `tools/assist/writer_block_assist.py` | 将并入 suggest_writing_direction |
| 新增 | `tools/assist/suggest_writing_direction.py` | 合并三个辅助建议工具 |
| 修改 | `tools/creation/record_chapter_meta.py` | docstring 补充 |
| 修改 | `tools/creation/update_foreshadowing.py` | 新增 foreshadowing_ids 参数 |
| 修改 | `tools/creation/generate_chapter_outline.py` | 新增 batch_chapter_numbers 参数 |
| 修改 | `tools/perception/consistency_scan.py` | 新增 mode/chapter_a/chapter_b/chapter_number 参数 |
| 修改 | `tools/assist/expand_world_setting.py` | 冲突时返回提示而非自行创建变更提议 |
| 修改 | `tools/registry.py` | 更新导入、工具集、新增 TOOL_COST_TIER |
| 修改 | `tools/registry_v2.py` | 更新工具名引用 |
| 修改 | `agents/agent_graph.py` | 更新 wrapper + 计数器 + BudgetTracker 集成 |
| 修改 | `agents/agent_context.py` | BudgetTracker 新增字段和方法 |
| 修改 | `tools/utils.py` | 新增 _truncate_result |
| 修改 | `tools/perception/__init__.py` | 移除旧导出 |
| 修改 | `tools/creation/__init__.py` | 移除旧导出 |
| 修改 | `tools/assist/__init__.py` | 移除旧导出 + 新增 |
| 修改 | `tools/__init__.py` | 移除旧导入 |
| 修改 | `agents/agent_tools.py` | 移除旧导入 |
| 修改 | `tests/test_agent_tools.py` | 更新导入和断言 |

---

## Task 1: BudgetTracker 增强 — 新增 llm_tool_tokens_used 和 should_throttle_llm_tool

**Files:**
- Modify: `backend/app/agents/agent_context.py` (BudgetTracker 类, ~L28-40)
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestBudgetTrackerEnhancement:
    """BudgetTracker 增强功能测试"""

    def test_llm_tool_tokens_used_default_zero(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        assert tracker.llm_tool_tokens_used == 0

    def test_should_throttle_below_threshold(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        tracker.used = 7000  # 30% 剩余
        assert not tracker.should_throttle_llm_tool()

    def test_should_throttle_at_threshold(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        tracker.used = 8200  # 18% 剩余
        assert tracker.should_throttle_llm_tool()

    def test_should_throttle_max_zero(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=0)
        assert not tracker.should_throttle_llm_tool()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestBudgetTrackerEnhancement -v`
Expected: FAIL — `AttributeError: 'BudgetTracker' object has no attribute 'llm_tool_tokens_used'`

- [ ] **Step 3: 实现 BudgetTracker 增强**

在 `backend/app/agents/agent_context.py` 的 `BudgetTracker` 类中修改：

```python
class BudgetTracker:
    """Token budget tracker"""

    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0
        self.llm_tool_tokens_used = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max

    def add(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max - self.used)

    def should_throttle_llm_tool(self) -> bool:
        """当剩余预算 < 20% 时，建议节流 LLM 工具"""
        if self.max <= 0:
            return False
        remaining = 1 - (self.used / self.max)
        return remaining < 0.2
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestBudgetTrackerEnhancement -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/agent_context.py backend/tests/test_agent_tools.py
git commit -m "feat(workflow): add llm_tool_tokens_used and should_throttle_llm_tool to BudgetTracker"
```

---

## Task 2: 工具元数据分类 — cost_tier + get_cost_tier

**Files:**
- Modify: `backend/app/agents/tools/registry.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestCostTier:
    """工具元数据分类测试"""

    def test_llm_tools_have_cost_tier(self):
        from app.agents.tools.registry import TOOL_COST_TIER, get_cost_tier
        assert get_cost_tier("review_chapter") == "llm"
        assert get_cost_tier("rewrite_chapter") == "llm"

    def test_rule_tools_have_cost_tier(self):
        from app.agents.tools.registry import get_cost_tier
        for name in ("consistency_scan", "rhythm_analysis", "style_analysis",
                     "foreshadowing_check", "progress_report"):
            assert get_cost_tier(name) == "rule", f"{name} should be rule"

    def test_db_tools_default(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("knowledge_search") == "db"
        assert get_cost_tier("create_character") == "db"
        assert get_cost_tier("generate_chapter_content") == "db"

    def test_unknown_tool_defaults_to_db(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("nonexistent_tool") == "db"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCostTier -v`
Expected: FAIL — `ImportError: cannot import name 'TOOL_COST_TIER'`

- [ ] **Step 3: 实现 cost_tier 和 get_cost_tier**

在 `backend/app/agents/tools/registry.py` 末尾添加：

```python
# 工具元数据分类 — 仅程序化使用，不注入 system prompt
TOOL_COST_TIER = {
    "review_chapter": "llm",
    "rewrite_chapter": "llm",
    "consistency_scan": "rule",
    "rhythm_analysis": "rule",
    "style_analysis": "rule",
    "foreshadowing_check": "rule",
    "progress_report": "rule",
}


def get_cost_tier(tool_name: str) -> str:
    """查询工具的 cost_tier，未标注默认 db"""
    return TOOL_COST_TIER.get(tool_name, "db")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCostTier -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/tools/registry.py backend/tests/test_agent_tools.py
git commit -m "feat(workflow): add cost_tier metadata and get_cost_tier for tool classification"
```

---

## Task 3: _truncate_result 工具函数

**Files:**
- Modify: `backend/app/agents/tools/utils.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestTruncateResult:
    """感知工具输出截短测试"""

    def test_truncate_dict_with_list(self):
        from app.agents.tools.utils import _truncate_result
        data = {"items": list(range(10)), "name": "test"}
        result = _truncate_result(data, max_items=3, max_str_len=100)
        assert len(result["items"]) == 3
        assert result["name"] == "test"

    def test_truncate_dict_with_long_string(self):
        from app.agents.tools.utils import _truncate_result
        data = {"text": "a" * 200}
        result = _truncate_result(data, max_items=5, max_str_len=50)
        assert len(result["text"]) <= 50
        assert result["text"].endswith("...")

    def test_truncate_nested_dict(self):
        from app.agents.tools.utils import _truncate_result
        data = {"outer": {"inner_list": [1, 2, 3, 4, 5], "inner_str": "hello"}}
        result = _truncate_result(data, max_items=2, max_str_len=100)
        assert len(result["outer"]["inner_list"]) == 2
        assert result["outer"]["inner_str"] == "hello"

    def test_truncate_list_directly(self):
        from app.agents.tools.utils import _truncate_result
        data = [1, 2, 3, 4, 5, 6, 7]
        result = _truncate_result(data, max_items=3, max_str_len=100)
        assert len(result) == 3

    def test_truncate_short_data_unchanged(self):
        from app.agents.tools.utils import _truncate_result
        data = {"items": [1, 2], "name": "hi"}
        result = _truncate_result(data, max_items=5, max_str_len=100)
        assert result == data

    def test_truncate_non_collection_passthrough(self):
        from app.agents.tools.utils import _truncate_result
        assert _truncate_result(42, max_items=5, max_str_len=100) == 42
        assert _truncate_result(None, max_items=5, max_str_len=100) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestTruncateResult -v`
Expected: FAIL — `ImportError: cannot import name '_truncate_result'`

- [ ] **Step 3: 实现 _truncate_result**

在 `backend/app/agents/tools/utils.py` 末尾添加：

```python
def _truncate_result(data, max_items: int = 5, max_str_len: int = 100):
    """递归截短工具返回值中的列表和长字符串。

    用于预算紧张时压缩感知工具输出，节省上下文空间。
    列表截到 max_items 项，字符串截到 max_str_len 字符。
    """
    if isinstance(data, dict):
        return {
            k: _truncate_result(v, max_items, max_str_len)
            for k, v in data.items()
        }
    if isinstance(data, list):
        truncated = [_truncate_result(item, max_items, max_str_len) for item in data[:max_items]]
        if len(data) > max_items:
            truncated.append(f"... 还有 {len(data) - max_items} 项")
        return truncated
    if isinstance(data, str) and len(data) > max_str_len:
        return data[:max_str_len] + "..."
    return data
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestTruncateResult -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/tools/utils.py backend/tests/test_agent_tools.py
git commit -m "feat(workflow): add _truncate_result for perception tool output compression"
```


---

## Task 4: consistency_scan 合并 — check_chapter_transition + consistency_check → consistency_scan

**Files:**
- Modify: `backend/app/agents/tools/perception/consistency_scan.py`
- Delete: `backend/app/agents/tools/perception/check_chapter_transition.py`
- Delete: `backend/app/agents/tools/perception/consistency_check.py`
- Modify: `backend/app/agents/tools/perception/__init__.py`
- Test: `backend/tests/test_agent_tools.py`

这是最复杂的合并任务。consistency_scan 新增 `mode` 参数和三个子模式。

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestConsistencyScanMerge:
    """consistency_scan 合并后三种模式测试"""

    def _make_mock_kb(self):
        """构建模拟 KB 对象"""
        kb = MagicMock()
        kb.timelines.list_timeline.return_value = [
            {"chapter_number": 1, "summary": "开场", "emotion_tag": "平静", "tension_score": 2},
            {"chapter_number": 2, "summary": "冲突", "emotion_tag": "紧张", "tension_score": 4},
            {"chapter_number": 3, "summary": "转折", "emotion_tag": "绝望", "tension_score": 5},
            {"chapter_number": 4, "summary": "缓和", "emotion_tag": "温馨", "tension_score": 2},
        ]
        kb.characters.list_characters.return_value = [
            {"id": 1, "name": "张三", "role": "主角", "core_motivation": "复仇", "deep_fear": "被遗弃"},
        ]
        kb.world_setting.get.return_value = {
            "tiered_settings": {"red": ["魔法不可逆转"]},
        }
        kb.foreshadowings.list_foreshadowings.return_value = []
        kb.chapters.get_by_number.return_value = {"content": "测试内容"}
        kb.outlines.get_chapter_outline.return_value = {
            "scene": "城市", "characters": "张三", "emotional_arc": "平静→紧张",
        }
        return kb

    @patch("app.agents.tools.perception.consistency_scan._kb")
    def test_mode_full_returns_issues(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            consistency_scan.ainvoke({"mode": "full"})
        )
        assert "issues" in result
        assert result["mode"] == "full"

    @patch("app.agents.tools.perception.consistency_scan._kb")
    def test_mode_transition_checks_chapter衔接(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            consistency_scan.ainvoke({"mode": "transition", "chapter_number": 2})
        )
        assert "issues" in result
        assert result["mode"] == "transition"

    @patch("app.agents.tools.perception.consistency_scan._kb")
    def test_mode_compare_checks_cross_analysis(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            consistency_scan.ainvoke({"mode": "compare", "chapter_a": 1, "chapter_b": 2})
        )
        assert "issues" in result
        assert result["mode"] == "compare"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestConsistencyScanMerge -v`
Expected: FAIL — consistency_scan 不接受 mode 参数

- [ ] **Step 3: 实现 consistency_scan 合并**

修改 `backend/app/agents/tools/perception/consistency_scan.py`，将整体结构改为三种模式。完整替换文件内容：

```python
"""一致性扫描工具（合并版）

合并原 consistency_scan、consistency_check、check_chapter_transition 三工具。
支持三种模式：full（全书扫描）、transition（章节衔接）、compare（两章比对）。
不调用 LLM，纯规则扫描。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param, _extract_names, _extract_times


@tool
async def consistency_scan(
    mode: str = "full",
    # full 模式参数
    check_types: str = "all",
    chapter_range: str = "recent",
    max_issues: int = 20,
    # transition 模式参数
    chapter_number: int = 0,
    # compare 模式参数
    chapter_a: int = 0,
    chapter_b: int = 0,
    aspect: str = "all",
) -> dict:
    """一致性扫描工具。支持三种模式检测一致性问题。

    - mode="full"：全书一致性扫描（默认），检测角色行为矛盾、时间线矛盾、设定引用矛盾
    - mode="transition"：章节衔接检查，分析上一章结尾与当前章大纲的连贯性
    - mode="compare"：两章比对检查，交叉分析角色行为和时间线一致性

    不调用 LLM，纯规则扫描。

    Args:
        mode: 扫描模式 - "full"(全书扫描), "transition"(章节衔接), "compare"(两章比对)
        check_types: [full] 检查类型 - "character", "timeline", "setting", "foreshadowing", 或 "all"
        chapter_range: [full] 扫描范围 - "recent"(最近20章), "all"(全书), 或 JSON 列表如 "[1,5,10]"
        max_issues: [full] 最多返回的矛盾数量（默认 20）
        chapter_number: [transition] 当前章节号（将检查第 N-1 章到第 N 章的衔接）
        chapter_a: [compare] 第一个章节号
        chapter_b: [compare] 第二个章节号
        aspect: [compare] 检查方面 - "character", "timeline", "setting", 或 "all"
    """
    if mode == "transition":
        return await _scan_transition(chapter_number)
    elif mode == "compare":
        return await _scan_compare(chapter_a, chapter_b, aspect)
    else:
        return await _scan_full(check_types, chapter_range, max_issues)


async def _scan_full(check_types: str, chapter_range: str, max_issues: int) -> dict:
    """全书一致性扫描（原 consistency_scan 逻辑）"""
    kb = _kb()
    issues = []

    # 解析章节范围
    chapter_nums = None
    if chapter_range not in ("recent", "all"):
        chapter_nums, warn = parse_json_param(chapter_range, [], "chapter_range")

    # 获取数据
    timeline = kb.timelines.list_timeline()
    chars = kb.characters.list_characters()
    ws = kb.world_setting.get()

    # 确定扫描范围
    recent_n = 20
    if chapter_range == "recent" and timeline:
        scan_timeline = timeline[:recent_n]
    elif chapter_nums:
        scan_timeline = [t for t in timeline if t.get("chapter_number") in chapter_nums]
    else:
        scan_timeline = timeline

    scan_chapter_numbers = list(set(t.get("chapter_number", 0) for t in scan_timeline))
    scan_chapter_numbers.sort()

    # 1. 角色行为矛盾检测
    if check_types in ("all", "character") and scan_timeline:
        emotion_by_chapter = {}
        for t in scan_timeline:
            ch = t.get("chapter_number")
            tag = t.get("emotion_tag", "")
            if ch and tag:
                emotion_by_chapter[ch] = tag

        sorted_chapters = sorted(emotion_by_chapter.keys())

        # 情绪凝固检测
        if len(sorted_chapters) >= 3:
            same_count = 1
            start_ch = sorted_chapters[0]
            for i in range(1, len(sorted_chapters)):
                if emotion_by_chapter[sorted_chapters[i]] == emotion_by_chapter[sorted_chapters[i-1]]:
                    same_count += 1
                else:
                    if same_count >= 3:
                        issues.append({
                            "type": "emotion_stagnation",
                            "chapters": list(range(start_ch, sorted_chapters[i-1] + 1)),
                            "detail": f"情绪凝固：第{start_ch}-{sorted_chapters[i-1]}章连续 {same_count} 章情绪相同「{emotion_by_chapter[start_ch]}」",
                            "confidence": "medium",
                        })
                    same_count = 1
                    start_ch = sorted_chapters[i]
            if same_count >= 3:
                issues.append({
                    "type": "emotion_stagnation",
                    "chapters": list(range(start_ch, sorted_chapters[-1] + 1)),
                    "detail": f"情绪凝固：第{start_ch}-{sorted_chapters[-1]}章连续 {same_count} 章情绪相同「{emotion_by_chapter[start_ch]}」",
                    "confidence": "medium",
                })

        # 情绪跳跃检测
        negative_tags = {"紧张", "悲痛", "恐惧", "绝望", "愤怒"}
        positive_tags = {"欢快", "温馨", "轻松", "平静", "释然"}
        for i in range(1, len(sorted_chapters)):
            prev_tag = emotion_by_chapter[sorted_chapters[i - 1]]
            curr_tag = emotion_by_chapter[sorted_chapters[i]]
            if prev_tag in negative_tags and curr_tag in positive_tags:
                issues.append({
                    "type": "emotion_jump_negative_to_positive",
                    "chapters": [sorted_chapters[i - 1], sorted_chapters[i]],
                    "detail": f"情绪跳跃(负→正)：第{sorted_chapters[i-1]}章「{prev_tag}」→ 第{sorted_chapters[i]}章「{curr_tag}」",
                    "confidence": "medium",
                })
            elif prev_tag in positive_tags and curr_tag in negative_tags:
                issues.append({
                    "type": "emotion_jump_positive_to_negative",
                    "chapters": [sorted_chapters[i - 1], sorted_chapters[i]],
                    "detail": f"情绪跳跃(正→负)：第{sorted_chapters[i-1]}章「{prev_tag}」→ 第{sorted_chapters[i]}章「{curr_tag}」",
                    "confidence": "medium",
                })

    # 2. 时间线矛盾检测
    if check_types in ("all", "timeline") and scan_timeline:
        chapter_order = []
        for t in scan_timeline:
            ch = t.get("chapter_number")
            if ch is not None:
                chapter_order.append((ch, t.get("summary", "")))

        for i in range(1, len(chapter_order)):
            if chapter_order[i][0] <= chapter_order[i - 1][0]:
                issues.append({
                    "type": "timeline_order",
                    "chapters": [chapter_order[i - 1][0], chapter_order[i][0]],
                    "detail": f"时间线章节号顺序异常：{chapter_order[i-1][0]} → {chapter_order[i][0]}",
                    "confidence": "high",
                })

    # 3. 伏笔检查
    if check_types in ("all", "foreshadowing"):
        all_fs = kb.foreshadowings.list_foreshadowings()
        for fs in all_fs:
            planted = fs.get("planted_chapter")
            expected = fs.get("expected_resolve_chapter")
            status = fs.get("status")

            if planted and expected and planted > expected:
                issues.append({
                    "type": "foreshadowing_impossible_timing",
                    "chapters": [planted, expected],
                    "detail": f"伏笔「{(fs.get('content') or '')[:30]}」提出章节{planted} > 预期解决章节{expected}",
                    "confidence": "high",
                })

            if status == "active" and expected:
                latest_ch = max((t.get("chapter_number", 0) for t in timeline), default=0)
                if latest_ch - expected >= 5:
                    issues.append({
                        "type": "foreshadowing_overdue",
                        "chapters": [planted, expected],
                        "detail": f"伏笔「{(fs.get('content') or '')[:30]}」已超期{latest_ch - expected}章未回收",
                        "confidence": "medium",
                    })

            if status == "reclaimed" and not fs.get("resolved_chapter"):
                issues.append({
                    "type": "foreshadowing_missing_resolve_chapter",
                    "chapters": [planted],
                    "detail": f"伏笔「{(fs.get('content') or '')[:30]}」状态为reclaimed但未记录回收章节",
                    "confidence": "low",
                })

    # 4. 设定引用矛盾检测
    if check_types in ("all", "setting") and ws:
        red_rules = (ws.get("tiered_settings") or {}).get("red", [])
        if red_rules and scan_chapter_numbers:
            for ch_num in scan_chapter_numbers:
                try:
                    chapter = kb.chapters.get_by_number(ch_num)
                    if chapter and chapter.get("content"):
                        ch_content = chapter["content"]
                        for rule in red_rules[:5]:
                            rule_text = rule if isinstance(rule, str) else rule.get("text", "")
                            if rule_text and len(rule_text) >= 6 and rule_text in ch_content:
                                issues.append({
                                    "type": "setting_reference",
                                    "chapters": [ch_num],
                                    "detail": f"第{ch_num}章引用了红色设定「{rule_text[:30]}」，请检查是否遵守",
                                    "confidence": "high",
                                    "rule_preview": rule_text[:60],
                                })
                except Exception:
                    pass

    # 截断结果
    total_issues = len(issues)
    issues = issues[:max_issues]

    result = {
        "mode": "full",
        "scan_chapters": len(scan_chapter_numbers),
        "chapter_range": chapter_range,
        "check_types": check_types,
        "issues_found": total_issues,
        "issues": issues,
        "message": f"扫描 {len(scan_chapter_numbers)} 章，发现 {total_issues} 个疑似矛盾" if total_issues else f"扫描 {len(scan_chapter_numbers)} 章，未发现明显矛盾",
    }
    if total_issues > max_issues:
        result["truncated"] = True
        result["note"] = f"实际发现 {total_issues} 个问题，仅返回前 {max_issues} 个"
    return result


async def _scan_transition(chapter_number: int) -> dict:
    """章节衔接检查（原 check_chapter_transition 逻辑）"""
    kb = _kb()

    if chapter_number < 2:
        return {"error": "至少需要第 2 章才能检查衔接（需要上一章作为参照）", "mode": "transition"}

    prev_chapter = kb.chapters.get_by_number(chapter_number - 1)
    if not prev_chapter or not prev_chapter.get("content"):
        return {"error": f"第 {chapter_number - 1} 章内容不存在，无法检查衔接", "mode": "transition"}

    prev_content = prev_chapter["content"]
    prev_closing = prev_content[-500:] if len(prev_content) > 500 else prev_content

    current_outline = kb.outlines.get_chapter_outline(chapter_number)
    if not current_outline:
        return {"error": f"第 {chapter_number} 章大纲不存在，请先创建大纲", "mode": "transition"}

    timeline = kb.timelines.list_timeline()
    prev_timeline = None
    for t in timeline:
        if t.get("chapter_number") == chapter_number - 1:
            prev_timeline = t
            break

    issues = []

    # 1. 情绪跳跃检测
    prev_emotion = prev_timeline.get("emotion_tag", "") if prev_timeline else ""
    curr_emotion_arc = current_outline.get("emotional_arc", "")
    if prev_emotion and curr_emotion_arc:
        negative_tags = {"紧张", "悲痛", "恐惧", "绝望", "愤怒", "悬疑"}
        positive_tags = {"欢快", "温馨", "轻松", "平静", "释然", "日常"}
        if prev_emotion in negative_tags:
            if any(tag in curr_emotion_arc for tag in positive_tags):
                opening_words = curr_emotion_arc.split("→")[0] if "→" in curr_emotion_arc else curr_emotion_arc[:20]
                issues.append({
                    "type": "emotion_jump",
                    "detail": f"上一章结尾情绪「{prev_emotion}」，当前章情绪弧线以「{opening_words}」开场，缺少过渡",
                    "suggestion": f"建议在第{chapter_number}章开场加入从「{prev_emotion}」到新情绪的过渡描写",
                })

    # 预提取角色名
    closing_names = set(_extract_names(prev_closing, kb)) if prev_closing else set()
    outline_chars_str = current_outline.get("characters", "")
    outline_names = set(_extract_names(outline_chars_str, kb)) if outline_chars_str else set()

    # 2. 场景切换检测
    curr_scene = current_outline.get("scene", "")
    if prev_closing and curr_scene:
        scene_names = set(_extract_names(curr_scene, kb))
        missing_in_scene = closing_names - scene_names
        if missing_in_scene and len(closing_names) <= 3:
            issues.append({
                "type": "scene_transition",
                "detail": f"上一章结尾的角色 {missing_in_scene} 未出现在当前章场景「{curr_scene[:30]}」中",
                "suggestion": f"建议在章节开头简短交代场景切换，或说明角色 {missing_in_scene} 的去向",
                "severity": "info",
            })

    # 3. 角色凭空变化检测
    if closing_names or outline_names:
        disappeared = closing_names - outline_names
        if disappeared and len(disappeared) <= 3:
            issues.append({
                "type": "character_disappear",
                "detail": f"上一章结尾出现的角色 {disappeared} 在当前章大纲中未提及",
                "suggestion": f"建议在当前章开头简短交代角色 {disappeared} 的去向",
            })

        new_chars = outline_names - closing_names
        if new_chars:
            issues.append({
                "type": "character_appear",
                "detail": f"当前章大纲中新增角色 {new_chars}，上一章结尾未出现",
                "suggestion": "建议在章节中为这些角色的出现安排合理的引入",
                "severity": "info",
            })

    result = {
        "mode": "transition",
        "chapter_number": chapter_number,
        "previous_chapter": chapter_number - 1,
        "issues_found": len(issues),
        "issues": issues,
        "prev_closing_preview": prev_closing[-200:] if len(prev_closing) > 200 else prev_closing,
        "current_outline_scene": current_outline.get("scene", ""),
    }

    if not issues:
        result["message"] = f"第{chapter_number-1}章到第{chapter_number}章衔接良好"
    else:
        result["message"] = f"发现 {len(issues)} 个衔接问题，请检查"

    return result


async def _scan_compare(chapter_a: int, chapter_b: int, aspect: str) -> dict:
    """两章比对检查（原 consistency_check 逻辑）"""
    kb = _kb()
    result = {"mode": "compare", "chapters_compared": [chapter_a, chapter_b], "issues": []}

    chapter_a_obj = kb.chapters.get_by_number(chapter_a)
    chapter_b_obj = kb.chapters.get_by_number(chapter_b)
    content_a = chapter_a_obj.get("content", "") if chapter_a_obj else ""
    content_b = chapter_b_obj.get("content", "") if chapter_b_obj else ""

    if aspect in ("all", "character"):
        appearing_names = set()
        if content_a:
            appearing_names.update(_extract_names(content_a, kb))
        if content_b:
            appearing_names.update(_extract_names(content_b, kb))

        all_chars = kb.characters.list_characters()
        constraints = []
        for char in all_chars:
            if appearing_names and char["name"] not in appearing_names:
                continue
            constraints.append({
                "name": char["name"],
                "deep_fear": char.get("deep_fear") or "",
                "core_motivation": char.get("core_motivation") or "",
            })
        result["character_constraints"] = constraints

    if aspect in ("all", "timeline"):
        timeline = kb.timelines.list_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = timeline

    if aspect in ("all", "setting"):
        ws = kb.world_setting.get()
        if ws:
            result["world_setting_red"] = (ws.get("tiered_settings") or {}).get("red", [])

    # 章节内容交叉分析
    if aspect in ("all", "character", "timeline"):
        if content_a and content_b:
            names_a = set(_extract_names(content_a, kb))
            names_b = set(_extract_names(content_b, kb))
            common_names = names_a & names_b

            times_a = set(_extract_times(content_a))
            times_b = set(_extract_times(content_b))
            common_times = times_a & times_b

            cross_analysis = {
                "chapter_a_length": len(content_a),
                "chapter_b_length": len(content_b),
                "names_in_a": len(names_a),
                "names_in_b": len(names_b),
                "common_names": list(common_names)[:20],
                "times_in_a": len(times_a),
                "times_in_b": len(times_b),
                "common_times": list(common_times)[:10],
            }

            if common_names and aspect in ("all", "character"):
                cross_analysis["character_overlap_note"] = (
                    f"两章共同出现 {len(common_names)} 个角色名，请检查行为是否一致"
                )
            if common_times and aspect in ("all", "timeline"):
                cross_analysis["timeline_overlap_note"] = (
                    f"两章共同出现 {len(common_times)} 个时间表达，请检查时间线是否一致"
                )

            result["cross_analysis"] = cross_analysis
        else:
            result["cross_analysis"] = {
                "note": "一章或两章内容不存在，无法进行内容交叉分析"
            }

    if not result["issues"]:
        result["message"] = "未发现明显的逻辑矛盾。请提供具体的矛盾描述，我可以帮你进一步分析。"
    return result
```

- [ ] **Step 4: 更新 perception/__init__.py**

修改 `backend/app/agents/tools/perception/__init__.py`：

```python
"""感知工具（6个）— 只读查询"""

from .knowledge_search import knowledge_search
from .foreshadowing_check import foreshadowing_check
from .style_analysis import style_analysis
from .progress_report import progress_report
from .rhythm_analysis import rhythm_analysis
from .consistency_scan import consistency_scan
```

- [ ] **Step 5: 删除旧工具文件**

```bash
rm backend/app/agents/tools/perception/check_chapter_transition.py
rm backend/app/agents/tools/perception/consistency_check.py
```

- [ ] **Step 6: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS（注意：旧测试中引用 consistency_check 和 check_chapter_transition 的断言需要更新，在 Task 8 统一处理）

- [ ] **Step 7: 提交**

```bash
git add -A backend/app/agents/tools/perception/
git commit -m "refactor(workflow): merge check_chapter_transition and consistency_check into consistency_scan with mode param"
```


---

## Task 5: update_foreshadowing 合并 — batch_update_foreshadowing_status 并入

**Files:**
- Modify: `backend/app/agents/tools/creation/update_foreshadowing.py`
- Delete: `backend/app/agents/tools/creation/batch_update_foreshadowing_status.py`
- Modify: `backend/app/agents/tools/creation/__init__.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestUpdateForeshadowingMerge:
    """update_foreshadowing 合并批量更新测试"""

    @patch("app.agents.tools.creation.update_foreshadowing._kb")
    def test_single_update_unchanged(self, mock_kb_fn):
        mock_kb = MagicMock()
        mock_kb.foreshadowings.get.return_value = {"id": 1, "status": "active"}
        mock_kb.foreshadowings.update.return_value = {"id": 1, "status": "pending_reclaim"}
        mock_kb_fn.return_value = mock_kb
        from app.agents.tools.creation.update_foreshadowing import update_foreshadowing
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            update_foreshadowing.ainvoke({"foreshadowing_id": 1, "status": "pending_reclaim"})
        )
        assert "updated_fields" in result

    @patch("app.agents.tools.creation.update_foreshadowing._kb")
    def test_batch_update_via_foreshadowing_ids(self, mock_kb_fn):
        mock_kb = MagicMock()
        mock_kb.foreshadowings.get.return_value = {"id": 1, "status": "active"}
        mock_kb.foreshadowings.update.return_value = {"id": 1, "status": "reclaimed"}
        mock_kb_fn.return_value = mock_kb
        from app.agents.tools.creation.update_foreshadowing import update_foreshadowing
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            update_foreshadowing.ainvoke({
                "foreshadowing_ids": "[1,2,3]",
                "status": "reclaimed",
                "resolved_chapter": 5,
            })
        )
        assert "batch_result" in result

    @patch("app.agents.tools.creation.update_foreshadowing._kb")
    def test_both_ids_params_conflict(self, mock_kb_fn):
        mock_kb = MagicMock()
        mock_kb_fn.return_value = mock_kb
        from app.agents.tools.creation.update_foreshadowing import update_foreshadowing
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            update_foreshadowing.ainvoke({
                "foreshadowing_id": 1,
                "foreshadowing_ids": "[1,2,3]",
                "status": "reclaimed",
            })
        )
        assert "error" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestUpdateForeshadowingMerge -v`
Expected: FAIL — update_foreshadowing 不接受 foreshadowing_ids 参数

- [ ] **Step 3: 实现 update_foreshadowing 合并**

替换 `backend/app/agents/tools/creation/update_foreshadowing.py`：

```python
"""更新伏笔状态工具

合并原 update_foreshadowing 和 batch_update_foreshadowing_status。
支持单个更新（foreshadowing_id）和批量更新（foreshadowing_ids）。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def update_foreshadowing(
    foreshadowing_id: int = 0,
    foreshadowing_ids: str = "[]",
    level: str | None = None,
    status: str | None = None,
    content: str | None = None,
    appearance_count: int | None = None,
    expected_resolve_chapter: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
    """更新伏笔状态或属性。支持单个更新和批量更新。

    单个更新：传入 foreshadowing_id + 要更新的字段。
    批量更新：传入 foreshadowing_ids（JSON 列表）+ status + 可选 resolved_chapter。
    两个 ID 参数不能同时传入。

    Args:
        foreshadowing_id: 单个伏笔 ID（与 foreshadowing_ids 互斥）
        foreshadowing_ids: JSON 字符串列表，批量更新的伏笔 ID（如 "[1,3,5]"）
        level: 新等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)
        status: 新状态 - "active", "pending_reclaim", "reclaimed"
        content: 伏笔内容
        appearance_count: 出现次数
        expected_resolve_chapter: 预期回收章节号
        resolved_chapter: 实际回收章节号
    """
    kb = _kb()

    # 解析批量 ID
    batch_ids, batch_warn = parse_json_param(foreshadowing_ids, [], "foreshadowing_ids")
    if batch_warn:
        return {"error": f"foreshadowing_ids 参数解析失败: {batch_warn}"}

    # 参数互斥检查
    if foreshadowing_id > 0 and batch_ids:
        return {"error": "foreshadowing_id 和 foreshadowing_ids 不能同时传入，请选择一种方式"}

    # 批量更新模式
    if batch_ids:
        valid_statuses = {"active", "pending_reclaim", "reclaimed"}
        if not status or status not in valid_statuses:
            return {"error": f"批量更新必须指定有效的 status（{valid_statuses}），收到: {status}"}

        update_data = {"status": status}
        if status == "reclaimed" and resolved_chapter:
            update_data["resolved_chapter"] = resolved_chapter

        updated = []
        not_found = []
        errors = []

        for fs_id in batch_ids:
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
            "batch_result": True,
            "updated": updated,
            "not_found": not_found,
            "errors": errors,
            "total_requested": len(batch_ids),
            "total_updated": len(updated),
            "new_status": status,
            "message": f"已将 {len(updated)} 个伏笔状态更新为「{status}」" if updated else "没有伏笔被更新",
        }

    # 单个更新模式
    if foreshadowing_id <= 0:
        return {"error": "请传入 foreshadowing_id（单个更新）或 foreshadowing_ids（批量更新）"}

    before = kb.foreshadowings.get(foreshadowing_id)
    if not before:
        return {"error": f"伏笔 ID {foreshadowing_id} 不存在"}

    update_data = {}
    for field in ("level", "status", "content", "appearance_count",
                  "expected_resolve_chapter", "resolved_chapter"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    if not update_data:
        return {"message": "无字段需要更新", "foreshadowing_id": foreshadowing_id}

    kb.foreshadowings.update(foreshadowing_id, update_data)

    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}

    return {
        "foreshadowing_id": foreshadowing_id,
        "updated_fields": list(changes.keys()),
        "changes": changes,
        "message": f"伏笔 {foreshadowing_id} 已更新（{', '.join(changes.keys())}）",
    }
```

- [ ] **Step 4: 更新 creation/__init__.py**

修改 `backend/app/agents/tools/creation/__init__.py`，移除 `batch_update_foreshadowing_status` 的导入：

```python
"""创作工具（23个）— 直接写入知识库"""

from .world_setting import create_world_setting
from .character import create_character
from .relation import create_relation
from .subplot import create_subplot
from .plot_question import create_plot_question
from .style_constraints import create_style_constraints
from .foreshadowing import create_foreshadowing
from .plot_block import create_plot_block
from .generate_outline import generate_outline
from .generate_chapter_outline import generate_chapter_outline
from .generate_chapter_content import generate_chapter_content
from .generate_story_seed import generate_story_seed
from .generate_world_setting_complete import generate_world_setting_complete
from .review_chapter import review_chapter
from .rewrite_chapter import rewrite_chapter
from .advance_phase import advance_phase
from .evolution_plan import create_evolution_plan
# 更新/删除工具
from .update_character import update_character
from .update_plot_block import update_plot_block
from .update_subplot import update_subplot
from .update_plot_question import update_plot_question
from .update_foreshadowing import update_foreshadowing
from .delete_plot_block import delete_plot_block
from .record_chapter_meta import record_chapter_meta
```

- [ ] **Step 5: 删除旧文件**

```bash
rm backend/app/agents/tools/creation/batch_update_foreshadowing_status.py
```

- [ ] **Step 6: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestUpdateForeshadowingMerge -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add -A backend/app/agents/tools/creation/
git commit -m "refactor(workflow): merge batch_update_foreshadowing_status into update_foreshadowing"
```

---

## Task 6: generate_chapter_outline 合并 — batch_confirm_outlines 并入

**Files:**
- Modify: `backend/app/agents/tools/creation/generate_chapter_outline.py`
- Delete: `backend/app/agents/tools/creation/batch_confirm_outlines.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestGenerateChapterOutlineMerge:
    """generate_chapter_outline 合并批量确认测试"""

    @patch("app.agents.tools.creation.generate_chapter_outline._kb")
    def test_single_outline_unchanged(self, mock_kb_fn):
        mock_kb = MagicMock()
        mock_kb.outlines.get_chapter_outline.return_value = None
        mock_kb.outlines.create_chapter_outline.return_value = {"id": 1}
        mock_kb_fn.return_value = mock_kb
        from app.agents.tools.creation.generate_chapter_outline import generate_chapter_outline
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            generate_chapter_outline.ainvoke({
                "chapter_number": 1,
                "title": "测试章节",
            })
        )
        assert result["action"] in ("created", "updated")

    @patch("app.agents.tools.creation.generate_chapter_outline._kb")
    def test_batch_confirm_via_batch_chapter_numbers(self, mock_kb_fn):
        mock_kb = MagicMock()
        mock_kb.outlines.get_chapter_outline.return_value = {
            "chapter_number": 1, "confirmed": False,
        }
        mock_kb.outlines.update_chapter_outline.return_value = None
        mock_kb_fn.return_value = mock_kb
        from app.agents.tools.creation.generate_chapter_outline import generate_chapter_outline
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            generate_chapter_outline.ainvoke({
                "chapter_number": 0,
                "title": "",
                "batch_chapter_numbers": "[1,2,3]",
            })
        )
        assert "batch_result" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestGenerateChapterOutlineMerge -v`
Expected: FAIL — generate_chapter_outline 不接受 batch_chapter_numbers 参数

- [ ] **Step 3: 实现 generate_chapter_outline 合并**

替换 `backend/app/agents/tools/creation/generate_chapter_outline.py`：

```python
"""生成章节大纲工具

合并原 generate_chapter_outline 和 batch_confirm_outlines。
支持单章大纲生成（默认）和批量确认（batch_chapter_numbers）。
"""
import logging

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb, parse_json_param

logger = logging.getLogger(__name__)


@tool
async def generate_chapter_outline(
    chapter_number: int,
    title: str,
    scene: str = "",
    characters: str = "",
    plot: str = "",
    conflict: str = "",
    turning_point: str = "",
    hook: str = "",
    transition: str = "",
    ending: str = "",
    target_words: int = 3000,
    opening_state: str = "",
    emotional_arc: str = "",
    key_scenes: str = "[]",
    pacing_note: str = "",
    batch_chapter_numbers: str = "[]",
) -> dict:
    """生成或更新特定章节的大纲。支持单章和批量确认模式。

    单章模式（默认）：传入 chapter_number + title 等字段创建或更新大纲。
    批量确认模式：传入 batch_chapter_numbers（JSON 列表如 "[1,2,3]"），
    将指定章节的大纲标记为已确认。此时 chapter_number 和 title 参数被忽略。

    Args:
        chapter_number: 章节号
        title: 章节标题
        scene: 场景设定
        characters: 出场角色
        plot: 关键情节点
        conflict: 主要冲突
        turning_point: 转折点
        hook: 章末悬念钩子
        transition: 到下一章的过渡
        ending: 章节结尾描写
        target_words: 目标字数（默认 3000）
        opening_state: 章节开场状态
        emotional_arc: 情感轨迹
        key_scenes: JSON 字符串列表，关键场景
        pacing_note: 节奏指引
        batch_chapter_numbers: JSON 字符串列表，批量确认的章节号（如 "[1,2,3]"）
    """
    kb = _kb()

    # 批量确认模式
    batch_nums, batch_warn = parse_json_param(batch_chapter_numbers, [], "batch_chapter_numbers")
    if batch_warn:
        return {"error": f"batch_chapter_numbers 参数解析失败: {batch_warn}"}

    if batch_nums:
        confirmed = []
        not_found = []
        already_confirmed = []
        errors = []

        for ch_num in batch_nums:
            try:
                outline = kb.outlines.get_chapter_outline(ch_num)
                if not outline:
                    not_found.append(ch_num)
                elif outline.get("confirmed"):
                    already_confirmed.append(ch_num)
                else:
                    kb.outlines.update_chapter_outline(ch_num, {"confirmed": True})
                    confirmed.append(ch_num)
            except Exception as e:
                errors.append({"chapter_number": ch_num, "error": str(e)})

        result = {
            "batch_result": True,
            "confirmed": confirmed,
            "already_confirmed": already_confirmed,
            "not_found": not_found,
            "errors": errors,
            "total_requested": len(batch_nums),
            "total_confirmed": len(confirmed),
            "message": f"已确认 {len(confirmed)} 个章节大纲" if confirmed else "没有新的章节大纲需要确认",
        }
        if not_found:
            result["hint"] = f"章节 {not_found} 大纲不存在，请先用 generate_chapter_outline 创建"
        return result

    # 单章大纲生成/更新模式
    scenes, scenes_warn = parse_json_param(key_scenes, [], "key_scenes")

    existing = kb.outlines.get_chapter_outline(chapter_number)

    if existing:
        update_data = {"title": title, "confirmed": False}
        if scene:
            update_data["scene"] = scene
        if characters:
            update_data["characters"] = characters
        if plot:
            update_data["plot"] = plot
        if conflict:
            update_data["conflict"] = conflict
        if turning_point:
            update_data["turning_point"] = turning_point
        if hook:
            update_data["hook"] = hook
        if transition:
            update_data["transition"] = transition
        if ending:
            update_data["ending"] = ending
        update_data["target_words"] = target_words
        if opening_state:
            update_data["opening_state"] = opening_state
        if emotional_arc:
            update_data["emotional_arc"] = emotional_arc
        if scenes:
            update_data["key_scenes"] = scenes
        if pacing_note:
            update_data["pacing_note"] = pacing_note
        kb.outlines.update_chapter_outline(chapter_number, update_data)
        action = "updated"
    else:
        data = {
            "chapter_number": chapter_number,
            "title": title,
            "target_words": target_words,
            "confirmed": False,
        }
        if scene:
            data["scene"] = scene
        if characters:
            data["characters"] = characters
        if plot:
            data["plot"] = plot
        if conflict:
            data["conflict"] = conflict
        if turning_point:
            data["turning_point"] = turning_point
        if hook:
            data["hook"] = hook
        if transition:
            data["transition"] = transition
        if ending:
            data["ending"] = ending
        if opening_state:
            data["opening_state"] = opening_state
        if emotional_arc:
            data["emotional_arc"] = emotional_arc
        if scenes:
            data["key_scenes"] = scenes
        if pacing_note:
            data["pacing_note"] = pacing_note
        kb.outlines.create_chapter_outline(data)
        action = "created"

    return {
        "action": action,
        "chapter_number": chapter_number,
        "title": title,
        "confirmed": False,
        "message": f"第{chapter_number}章「{title}」大纲已{action}，请审查后确认",
    }
```

- [ ] **Step 4: 删除旧文件**

```bash
rm backend/app/agents/tools/creation/batch_confirm_outlines.py
```

- [ ] **Step 5: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestGenerateChapterOutlineMerge -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add -A backend/app/agents/tools/creation/
git commit -m "refactor(workflow): merge batch_confirm_outlines into generate_chapter_outline"
```


---

## Task 7: suggest_writing_direction 合并 + expand_world_setting 修复

**Files:**
- Create: `backend/app/agents/tools/assist/suggest_writing_direction.py`
- Delete: `backend/app/agents/tools/assist/suggest_foreshadowing.py`
- Delete: `backend/app/agents/tools/assist/suggest_plot_twist.py`
- Delete: `backend/app/agents/tools/assist/writer_block_assist.py`
- Modify: `backend/app/agents/tools/assist/expand_world_setting.py`
- Modify: `backend/app/agents/tools/assist/__init__.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestSuggestWritingDirection:
    """suggest_writing_direction 合并测试"""

    def _make_mock_kb(self):
        kb = MagicMock()
        kb.plots.get_current_plot_block.return_value = {
            "id": 1, "title": "暗潮涌动",
            "chapter_start": 1, "chapter_end": 5,
            "questions_to_raise": ["谁是内鬼？"],
            "must_happen": ["揭示线索"],
        }
        kb.foreshadowings.list_foreshadowings.return_value = [
            {"id": 1, "status": "active", "content": "神秘信件", "planted_chapter": 1,
             "expected_resolve_chapter": 5},
        ]
        kb.foreshadowings.list_pending.return_value = [
            {"id": 2, "content": "暗号解读", "expected_resolve_chapter": 3},
        ]
        kb.foreshadowings.list_overdue.return_value = []
        kb.characters.list_characters.return_value = [
            {"id": 1, "name": "张三", "role": "主角",
             "core_motivation": "找出真相", "deep_fear": "被背叛", "growth_arc": "觉醒"},
        ]
        kb.timelines.list_timeline.return_value = [
            {"chapter_number": 1, "tension_score": 3, "emotion_tag": "紧张"},
            {"chapter_number": 2, "tension_score": 2, "emotion_tag": "日常"},
        ]
        kb.chapters.get_by_number.return_value = {"content": "测试内容"}
        kb.plots.get_questions_for_chapter.return_value = [
            {"id": 1, "question_text": "谁在幕后操纵？"},
        ]
        return kb

    @patch("app.agents.tools.assist.suggest_writing_direction._kb")
    def test_focus_foreshadowing(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.assist.suggest_writing_direction import suggest_writing_direction
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            suggest_writing_direction.ainvoke({"current_chapter": 3, "focus": "foreshadowing"})
        )
        assert result["focus"] == "foreshadowing"
        assert len(result["suggestions"]) > 0

    @patch("app.agents.tools.assist.suggest_writing_direction._kb")
    def test_focus_twist(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.assist.suggest_writing_direction import suggest_writing_direction
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            suggest_writing_direction.ainvoke({"current_chapter": 3, "focus": "twist"})
        )
        assert result["focus"] == "twist"
        assert len(result["suggestions"]) > 0

    @patch("app.agents.tools.assist.suggest_writing_direction._kb")
    def test_focus_block(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.assist.suggest_writing_direction import suggest_writing_direction
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            suggest_writing_direction.ainvoke({"current_chapter": 3, "focus": "block"})
        )
        assert result["focus"] == "block"
        assert len(result["suggestions"]) > 0

    @patch("app.agents.tools.assist.suggest_writing_direction._kb")
    def test_focus_auto(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.assist.suggest_writing_direction import suggest_writing_direction
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            suggest_writing_direction.ainvoke({"current_chapter": 3, "focus": "auto"})
        )
        assert result["focus"] == "auto"
        assert len(result["suggestions"]) > 0


class TestExpandWorldSettingFix:
    """expand_world_setting 控制流修复测试"""

    @patch("app.agents.tools.assist.expand_world_setting._kb")
    def test_severe_conflict_returns_hint_not_change(self, mock_kb_fn):
        """严重冲突时应返回提示而非自行创建变更提议"""
        mock_kb = MagicMock()
        mock_kb.world_setting.get.return_value = {
            "id": 1,
            "tiered_settings": {"red": ["魔法不可逆转"]},
        }
        mock_kb.search_chapters_for_references.return_value = [{"chapter_number": 1}]
        mock_kb_fn.return_value = mock_kb
        from app.agents.tools.assist.expand_world_setting import expand_world_setting
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            expand_world_setting.ainvoke({
                "aspect": "rule",
                "description": "逆转魔法效果",
            })
        )
        assert result["impact_level"] == "severe"
        assert "change_id" not in result
        assert "请调用 propose_setting_change" in result.get("suggestion", "") or "变更提议" in result.get("suggestion", "")
        # 确认没有调用 kb.changes.create
        mock_kb.changes.create.assert_not_called()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestSuggestWritingDirection tests/test_agent_tools.py::TestExpandWorldSettingFix -v`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 创建 suggest_writing_direction.py**

创建 `backend/app/agents/tools/assist/suggest_writing_direction.py`：

```python
"""写作方向建议工具

合并原 suggest_foreshadowing、suggest_plot_twist、writer_block_assist。
通过 focus 参数选择建议方向，auto 模式智能选择最需要的方向。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb
from app.utils.text import tokenize_chinese


_SUGGEST_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "吗",
}


@tool
async def suggest_writing_direction(
    current_chapter: int,
    focus: str = "auto",
) -> dict:
    """基于当前章节状态建议写作方向。

    根据焦点模式提供不同的建议：
    - foreshadowing：伏笔建议，分析情节块和未追踪的神秘元素
    - twist：反转建议，分析角色动机冲突和读者预期
    - block：卡壳辅助，基于伏笔和问题链提供具体写作方向
    - auto：智能选择，有超期伏笔优先伏笔，张力低优先反转，否则返回合并摘要

    Args:
        current_chapter: 当前章节号
        focus: 建议焦点 - "foreshadowing"(伏笔), "twist"(反转), "block"(卡壳辅助), "auto"(智能选择)
    """
    kb = _kb()

    if focus == "foreshadowing":
        return await _suggest_foreshadowing(kb, current_chapter)
    elif focus == "twist":
        return await _suggest_twist(kb, current_chapter)
    elif focus == "block":
        return await _suggest_block(kb, current_chapter)
    else:
        return await _suggest_auto(kb, current_chapter)


async def _suggest_foreshadowing(kb, current_chapter: int) -> dict:
    """伏笔建议逻辑（原 suggest_foreshadowing）"""
    block = kb.plots.get_current_plot_block(current_chapter)
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    active = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]

    if not block:
        return {"focus": "foreshadowing", "current_chapter": current_chapter,
                "suggestion": "当前没有情节块信息，建议先完成结构设计", "suggestions": []}

    suggestions = []
    for question in (block.get("questions_to_raise") or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
            "reasoning": "此问题是当前情节块需要提出的关键问题，在提出前埋下伏笔可以增加悬念",
        })

    if len(active) < 3 and block.get("chapter_end") and block.get("chapter_start"):
        span = block["chapter_end"] - block["chapter_start"]
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
                "reasoning": "长情节块中伏笔密度不足会导致读者缺乏悬念感，建议每 2-3 章至少有 1 个活跃伏笔",
            })

    # 未解释现象扫描
    unexplained = []
    recent_chapters = []
    for ch_offset in range(3):
        ch_num = current_chapter - ch_offset
        if ch_num > 0:
            ch = kb.chapters.get_by_number(ch_num)
            if ch and ch.get("content"):
                recent_chapters.append((ch_num, ch["content"]))

    if recent_chapters:
        tracked_contents = set()
        for f in active:
            content = f.get("content", "")
            if content:
                for word in content.split("，")[:3]:
                    if len(word) >= 2:
                        tracked_contents.add(word)

        word_freq = {}
        for ch_num, content in recent_chapters:
            tokens = tokenize_chinese(content)
            for token in tokens:
                if len(token) >= 3:
                    word_freq[token] = word_freq.get(token, 0) + 1

        for word, freq in sorted(word_freq.items(), key=lambda x: -x[1]):
            if freq >= 2 and word not in tracked_contents:
                unexplained.append({"element": word, "occurrences": freq})
                if len(unexplained) >= 3:
                    break

        for ue in unexplained:
            suggestions.append({
                "type": "未解释现象",
                "content": f"「{ue['element']}」在最近章节出现了 {ue['occurrences']} 次但未被追踪为伏笔",
                "reasoning": "反复出现的元素适合作为伏笔对象——读者会自然期待它有意义，将其正式纳入伏笔追踪体系可以增强叙事一致性",
            })

    return {
        "focus": "foreshadowing",
        "current_chapter": current_chapter,
        "plot_block": block.get("title") if block else None,
        "active_foreshadowings": len(active),
        "suggestions": suggestions,
    }


async def _suggest_twist(kb, current_chapter: int) -> dict:
    """反转建议逻辑（原 suggest_plot_twist）"""
    timeline = kb.timelines.list_timeline()
    foreshadowings = kb.foreshadowings.list_foreshadowings(status="active")
    characters = kb.characters.list_characters()
    block = kb.plots.get_current_plot_block(current_chapter)

    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.get("tension_score"):
                recent_tension.append(t["tension_score"])

    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    twist_types = []

    # 节奏驱动反转
    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    # 伏笔误导
    if len(foreshadowings) >= 2:
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowing_ids": [f["id"] for f in foreshadowings[:3]],
        })

    # 多角色分析
    main_chars = [c for c in characters if c.get("role") in ("主角", "核心反派", "重要配角")]
    char_twists = []
    for c in main_chars[:3]:
        core_mot = c.get("core_motivation", "")
        deep_fear = c.get("deep_fear", "")
        growth_arc = c.get("growth_arc", "")
        if core_mot or deep_fear:
            twist_direction = ""
            if deep_fear and growth_arc:
                twist_direction = f"让「{c['name']}」的成长弧线突然受挫——其深层恐惧「{deep_fear[:20]}」被触发，迫使面对最不想面对的处境"
            elif core_mot:
                twist_direction = f"揭示「{c['name']}」的真正动机与表面不同——核心动机「{core_mot[:20]}」背后隐藏更深的目的"
            if twist_direction:
                char_twists.append({
                    "type": "角色反转",
                    "character_id": c["id"],
                    "character_name": c["name"],
                    "character_role": c.get("role", ""),
                    "direction": twist_direction,
                })

    twist_types.extend(char_twists)

    # 读者预期反转
    reader_expectation_twists = []
    for f in foreshadowings[:3]:
        content = f.get("content", "")
        expected_resolve = f.get("expected_resolve_chapter")
        if content and expected_resolve and expected_resolve > current_chapter:
            reader_expectation_twists.append({
                "type": "读者预期反转",
                "foreshadowing_id": f["id"],
                "foreshadowing_preview": content[:60],
                "direction": f"伏笔「{content[:30]}」引导读者期待一个方向，实际揭示时走向相反方向——制造意外但合理的效果",
            })
    twist_types.extend(reader_expectation_twists)

    return {
        "focus": "twist",
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:5],
    }


async def _suggest_block(kb, current_chapter: int) -> dict:
    """卡壳辅助逻辑（原 writer_block_assist）"""
    pending = kb.foreshadowings.list_pending()
    overdue = kb.foreshadowings.list_overdue(current_chapter)
    questions = kb.plots.get_questions_for_chapter(current_chapter)
    block = kb.plots.get_current_plot_block(current_chapter)

    suggestions = []

    if overdue:
        f = overdue[0]
        content_preview = f.get("content", "")[:50]
        suggestions.append({
            "direction": "回收超期伏笔",
            "detail": f"伏笔「{content_preview}」已超过预期回收章节，可以在本章回收",
            "foreshadowing_id": f["id"],
        })

    if questions:
        q = questions[0]
        question_preview = q.get("question_text", "")[:50]
        suggestions.append({
            "direction": "回答待解问题",
            "detail": f"问题「{question_preview}」可以在本章回答",
            "question_id": q["id"],
        })

    if block:
        must_happen = block.get("must_happen") or []
        if must_happen:
            block_title = block.get("title", "")
            suggestions.append({
                "direction": "推进情节块",
                "detail": f"当前情节块「{block_title}」必须事件：{must_happen[0][:50] if must_happen else '无'}",
                "plot_block_id": block["id"],
            })

    if not suggestions:
        suggestions.append({
            "direction": "自由发挥",
            "detail": "当前没有紧迫的伏笔或问题链需要处理，可以自由推进剧情",
        })

    return {
        "focus": "block",
        "current_chapter": current_chapter,
        "suggestions": suggestions,
        "pending_foreshadowings": len(pending),
        "pending_questions": len(questions),
    }


async def _suggest_auto(kb, current_chapter: int) -> dict:
    """智能选择模式：有超期伏笔优先伏笔，张力低优先反转，否则返回合并摘要"""
    overdue = kb.foreshadowings.list_overdue(current_chapter)
    timeline = kb.timelines.list_timeline()
    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.get("tension_score"):
                recent_tension.append(t["tension_score"])
    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    # 有超期伏笔 → 伏笔建议
    if overdue:
        result = await _suggest_foreshadowing(kb, current_chapter)
        result["auto_reason"] = "检测到超期伏笔，优先建议伏笔方向"
        return result

    # 张力低 → 反转建议
    if avg_tension < 3:
        result = await _suggest_twist(kb, current_chapter)
        result["auto_reason"] = f"最近平均张力 {avg_tension:.1f} 偏低，优先建议反转方向"
        return result

    # 否则返回三类合并摘要
    fs_result = await _suggest_foreshadowing(kb, current_chapter)
    twist_result = await _suggest_twist(kb, current_chapter)
    block_result = await _suggest_block(kb, current_chapter)

    merged = []
    for s in (fs_result.get("suggestions") or [])[:2]:
        s["source"] = "foreshadowing"
        merged.append(s)
    for s in (twist_result.get("suggestions") or [])[:2]:
        s["source"] = "twist"
        merged.append(s)
    for s in (block_result.get("suggestions") or [])[:2]:
        s["source"] = "block"
        merged.append(s)

    return {
        "focus": "auto",
        "auto_reason": "无紧迫问题，返回三类方向的合并摘要",
        "current_chapter": current_chapter,
        "suggestions": merged,
        "foreshadowing_count": fs_result.get("active_foreshadowings", 0),
        "avg_tension": round(avg_tension, 1),
    }
```

- [ ] **Step 4: 修复 expand_world_setting.py**

修改 `backend/app/agents/tools/assist/expand_world_setting.py`，将冲突时创建变更提议的逻辑改为返回提示。替换 `if impact_level == "severe":` 分支：

```python
    # 严重冲突时返回提示，引导 Agent 调用 propose_setting_change
    if impact_level == "severe":
        return {
            "aspect": aspect,
            "description": description,
            "impact_level": impact_level,
            "impact_detail": impact_detail,
            "affected_chapters": len(affected),
            "contradictions": contradictions,
            "suggestion": "扩展与🔴设定严重冲突，请调用 propose_setting_change 创建变更提议，由用户确认后再扩展",
            "requires_approval": True,
        }
```

- [ ] **Step 5: 更新 assist/__init__.py**

```python
"""创作辅助工具（2个）— 辅助创意决策"""

from .suggest_writing_direction import suggest_writing_direction
from .expand_world_setting import expand_world_setting
```

- [ ] **Step 6: 删除旧工具文件**

```bash
rm backend/app/agents/tools/assist/suggest_foreshadowing.py
rm backend/app/agents/tools/assist/suggest_plot_twist.py
rm backend/app/agents/tools/assist/writer_block_assist.py
```

- [ ] **Step 7: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestSuggestWritingDirection tests/test_agent_tools.py::TestExpandWorldSettingFix -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add -A backend/app/agents/tools/assist/
git commit -m "refactor(workflow): merge suggest_foreshadowing/suggest_plot_twist/writer_block_assist into suggest_writing_direction; fix expand_world_setting control flow"
```


---

## Task 8: 注册表 + 导出层 + 测试更新 — 统一整合

**Files:**
- Modify: `backend/app/agents/tools/registry.py` — 更新导入、工具集、新增 cost_tier（已在 Task 2 部分完成，此处完善工具集更新）
- Modify: `backend/app/agents/tools/registry_v2.py`
- Modify: `backend/app/agents/tools/__init__.py`
- Modify: `backend/app/agents/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`
- Delete: `backend/app/agents/tools/creation/timeline_entry.py`

这是收尾任务，统一更新所有注册和导出。

- [ ] **Step 1: 删除 timeline_entry.py**

```bash
rm backend/app/agents/tools/creation/timeline_entry.py
```

- [ ] **Step 2: 更新 record_chapter_meta.py docstring**

在 `backend/app/agents/tools/creation/record_chapter_meta.py` 的工具 docstring 中补充说明：

将 docstring 第一行从：
```
记录章节的追踪元数据（时间线、伏笔、节奏评分等）。
```
改为：
```
记录章节的追踪元数据（时间线、伏笔、节奏评分等）。

这是记录章节追踪数据的唯一入口，包含时间线 upsert、伏笔创建和回收。
```

- [ ] **Step 3: 更新 registry.py — 导入和工具集**

替换 `backend/app/agents/tools/registry.py` 全部内容：

```python
"""工具注册表 — 按阶段注册可用工具

模块级常量，确保阶段工具集合满足递进关系：
INCUBATION_TOOLS ⊆ STRUCTURE_TOOLS ⊆ WRITING_TOOLS ⊆ REVISION_TOOLS
使用列表拼接保证递进关系，新阶段只需添加增量工具。

合并后工具数：43 → 35
"""

from app.agents.tools.perception import (
    knowledge_search,
    foreshadowing_check,
    consistency_scan,
    style_analysis,
    progress_report,
    rhythm_analysis,
)
from app.agents.tools.modification import (
    apply_change,
    reject_change,
    list_proposed_changes,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
)
from app.agents.tools.assist import (
    suggest_writing_direction,
    expand_world_setting,
)
from app.agents.tools.creation import (
    create_evolution_plan,
    create_world_setting,
    create_character,
    create_relation,
    create_subplot,
    create_plot_question,
    create_style_constraints,
    create_foreshadowing,
    create_plot_block,
    generate_outline,
    generate_chapter_outline,
    generate_chapter_content,
    generate_story_seed,
    generate_world_setting_complete,
    review_chapter,
    rewrite_chapter,
    advance_phase,
    update_character,
    update_plot_block,
    update_subplot,
    update_plot_question,
    update_foreshadowing,
    delete_plot_block,
    record_chapter_meta,
)

# 孵化阶段
INCUBATION_TOOLS = [
    advance_phase,
    knowledge_search,
    progress_report,
    expand_world_setting,
    generate_outline,
    generate_story_seed,
    generate_world_setting_complete,
    create_world_setting,
    create_character,
    create_relation,
    create_evolution_plan,
    create_style_constraints,
    create_foreshadowing,
]

# 结构阶段增量
_STRUCTURE_EXTRA = [
    foreshadowing_check,
    review_chapter,
    rewrite_chapter,
    rhythm_analysis,
    suggest_writing_direction,
    generate_chapter_outline,
    propose_outline_adjustment,
    create_plot_block,
    create_plot_question,
    create_subplot,
    update_character,
    update_plot_block,
    update_plot_question,
    delete_plot_block,
    apply_change,
    reject_change,
    list_proposed_changes,
]

# 写作阶段增量
_WRITING_EXTRA = [
    consistency_scan,
    style_analysis,
    generate_chapter_content,
    propose_setting_change,
    propose_chapter_rewrite,
    record_chapter_meta,
    update_subplot,
    update_foreshadowing,
]

STRUCTURE_TOOLS = INCUBATION_TOOLS + _STRUCTURE_EXTRA
WRITING_TOOLS = STRUCTURE_TOOLS + _WRITING_EXTRA
REVISION_TOOLS = WRITING_TOOLS

AGENT_TOOLS = WRITING_TOOLS

# 工具元数据分类 — 仅程序化使用，不注入 system prompt
TOOL_COST_TIER = {
    "review_chapter": "llm",
    "rewrite_chapter": "llm",
    "consistency_scan": "rule",
    "rhythm_analysis": "rule",
    "style_analysis": "rule",
    "foreshadowing_check": "rule",
    "progress_report": "rule",
}


def get_cost_tier(tool_name: str) -> str:
    """查询工具的 cost_tier，未标注默认 db"""
    return TOOL_COST_TIER.get(tool_name, "db")
```

- [ ] **Step 4: 更新 registry_v2.py**

替换 `backend/app/agents/tools/registry_v2.py` 中 `_LARGE_PROJECT_TOOL_NAMES`：

```python
# 大型项目额外启用的工具名
_LARGE_PROJECT_TOOL_NAMES = {"consistency_scan"}
```

- [ ] **Step 5: 更新 tools/__init__.py**

替换 `backend/app/agents/tools/__init__.py`：

```python
"""Agent 工具统一导出

所有 35 个工具 + 阶段常量 + 内部函数。
"""

# 感知工具
from app.agents.tools.perception import (
    knowledge_search,
    foreshadowing_check,
    consistency_scan,
    style_analysis,
    progress_report,
    rhythm_analysis,
)
# 修改工具
from app.agents.tools.modification import (
    apply_change,
    reject_change,
    list_proposed_changes,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
)
# 创作辅助
from app.agents.tools.assist import (
    suggest_writing_direction,
    expand_world_setting,
)
# 创作工具
from app.agents.tools.creation import (
    create_world_setting,
    create_character,
    create_relation,
    create_subplot,
    create_plot_question,
    create_style_constraints,
    create_foreshadowing,
    create_plot_block,
    generate_outline,
    generate_chapter_content,
    generate_story_seed,
    generate_world_setting_complete,
    review_chapter,
    rewrite_chapter,
    advance_phase,
)
# 阶段工具列表
from app.agents.tools.registry import (
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    AGENT_TOOLS,
)
# 内部函数（测试兼容）
from app.agents.tools.utils import _kb, _extract_keywords, _grade_impact
```

- [ ] **Step 6: 更新 agent_tools.py 向后兼容层**

替换 `backend/app/agents/agent_tools.py`：

```python
"""向后兼容层 — 所有导入已迁移到 app.agents.tools

此文件保留为兼容层，确保旧导入路径仍然可用。
新代码应使用 from app.agents.tools import ...
"""

from app.agents.tools import (
    # 感知工具
    knowledge_search,
    foreshadowing_check,
    consistency_scan,
    style_analysis,
    progress_report,
    rhythm_analysis,
    # 修改工具
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    # 创作辅助
    suggest_writing_direction,
    expand_world_setting,
    # 创作工具
    create_world_setting,
    create_character,
    create_relation,
    create_evolution_plan,
    create_subplot,
    create_plot_question,
    create_style_constraints,
    create_foreshadowing,
    create_plot_block,
    generate_outline,
    generate_chapter_content,
    generate_story_seed,
    generate_world_setting_complete,
    review_chapter,
    rewrite_chapter,
    advance_phase,
    # 阶段工具列表
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    AGENT_TOOLS,
    # 内部函数
    _kb,
    _extract_keywords,
    _grade_impact,
)
```

- [ ] **Step 7: 更新 tests/test_agent_tools.py**

替换 `backend/tests/test_agent_tools.py` 中的导入和测试断言：

```python
"""Unit tests for cognitive tools (agent_tools.py)

Tests tool registration, helper functions, and impact grading.
合并后工具数：43 → 35
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.tools import (
    knowledge_search,
    foreshadowing_check,
    consistency_scan,
    style_analysis,
    progress_report,
    rhythm_analysis,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    suggest_writing_direction,
    expand_world_setting,
    AGENT_TOOLS,
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    _extract_keywords,
    _grade_impact,
)


class TestToolRegistration:
    """Verify all cognitive tools are properly registered."""

    def test_writing_tools_count(self):
        """合并后 WRITING_TOOLS 应有 35 个工具"""
        assert len(WRITING_TOOLS) == 35, f'Expected 35 tools, got {len(WRITING_TOOLS)}'

    def test_incubation_tools_subset(self):
        assert len(INCUBATION_TOOLS) >= 8, f'Expected at least 8 tools, got {len(INCUBATION_TOOLS)}'
        assert knowledge_search in INCUBATION_TOOLS

    def test_structure_tools_subset(self):
        assert len(STRUCTURE_TOOLS) >= 10, f'Expected at least 10 tools, got {len(STRUCTURE_TOOLS)}'
        assert propose_outline_adjustment in STRUCTURE_TOOLS

    def test_all_tools_have_names(self):
        for tool in AGENT_TOOLS:
            assert tool.name, f"Tool {tool} missing name"
            assert tool.description, f"Tool {tool.name} missing description"

    def test_perception_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["knowledge_search", "foreshadowing_check", "consistency_scan",
                         "style_analysis", "progress_report", "rhythm_analysis"]:
            assert expected in names, f"Missing perception tool: {expected}"

    def test_merged_tools_not_present(self):
        """已合并的工具不应出现在工具列表中"""
        names = [t.name for t in AGENT_TOOLS]
        for removed in [
            "consistency_check", "check_chapter_transition",
            "create_timeline_entry", "batch_update_foreshadowing_status",
            "batch_confirm_outlines",
            "suggest_foreshadowing", "suggest_plot_twist", "writer_block_assist",
        ]:
            assert removed not in names, f"Removed tool still present: {removed}"

    def test_new_merged_tools_are_present(self):
        names = [t.name for t in AGENT_TOOLS]
        assert "consistency_scan" in names
        assert "suggest_writing_direction" in names

    def test_modification_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["propose_setting_change", "propose_outline_adjustment", "propose_chapter_rewrite"]:
            assert expected in names, f"Missing modification tool: {expected}"

    def test_assist_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["suggest_writing_direction", "expand_world_setting"]:
            assert expected in names, f"Missing assist tool: {expected}"


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_extract_keywords_from_description(self):
        keywords = _extract_keywords({}, {}, "主角的魔法限制被修改")
        assert len(keywords) > 0

    def test_grade_impact_none(self):
        level, detail = _grade_impact([], "world_setting", {}, {})
        assert level == "none"

    def test_grade_impact_minor(self):
        affected = [{"matching_paragraphs": [{"index": 0, "text": "test"}]}]
        level, detail = _grade_impact(affected, "character", {}, {})
        assert level == "minor"

    def test_grade_impact_moderate(self):
        affected = [
            {"matching_paragraphs": [{"index": i, "text": f"para {i}"} for i in range(3)]},
            {"matching_paragraphs": [{"index": 0, "text": "test"}]},
        ]
        level, detail = _grade_impact(affected, "world_setting", {}, {})
        assert level == "moderate"

    def test_grade_impact_severe(self):
        affected = [{"matching_paragraphs": [{"index": i, "text": f"para {i}"} for i in range(10)]} for _ in range(5)]
        level, detail = _grade_impact(affected, "world_setting", {}, {})
        assert level == "severe"


class TestToolContext:
    """Test tool context integration."""

    def test_project_id_contextvar(self):
        from app.agents.tool_context import set_tool_context, reset_tool_context, get_project_id

        assert get_project_id() is None
        tokens = set_tool_context(project_id=42)
        assert get_project_id() == 42
        reset_tool_context(tokens)
        assert get_project_id() is None

    def test_kb_raises_without_project_id(self):
        from app.agents.tools import _kb
        with pytest.raises(ValueError, match="project_id not set"):
            _kb()


class TestPhaseSubsetRelation:
    """验证阶段工具集合满足递进子集关系。"""

    def test_incubation_subset_of_structure(self):
        inc_names = {t.name for t in INCUBATION_TOOLS}
        str_names = {t.name for t in STRUCTURE_TOOLS}
        assert inc_names.issubset(str_names), f"孵化工具不在结构阶段中: {inc_names - str_names}"

    def test_structure_subset_of_writing(self):
        str_names = {t.name for t in STRUCTURE_TOOLS}
        wrt_names = {t.name for t in WRITING_TOOLS}
        assert str_names.issubset(wrt_names), f"结构工具不在写作阶段中: {str_names - wrt_names}"

    def test_no_duplicate_tool_names(self):
        for name, tools in [("INCUBATION", INCUBATION_TOOLS), ("STRUCTURE", STRUCTURE_TOOLS), ("WRITING", WRITING_TOOLS)]:
            names = [t.name for t in tools]
            dupes = [n for n in names if names.count(n) > 1]
            assert not dupes, f"{name} 有重复工具: {dupes}"


class TestBudgetTrackerEnhancement:
    """BudgetTracker 增强功能测试"""

    def test_llm_tool_tokens_used_default_zero(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        assert tracker.llm_tool_tokens_used == 0

    def test_should_throttle_below_threshold(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        tracker.used = 7000
        assert not tracker.should_throttle_llm_tool()

    def test_should_throttle_at_threshold(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        tracker.used = 8200
        assert tracker.should_throttle_llm_tool()

    def test_should_throttle_max_zero(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=0)
        assert not tracker.should_throttle_llm_tool()


class TestCostTier:
    """工具元数据分类测试"""

    def test_llm_tools_have_cost_tier(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("review_chapter") == "llm"
        assert get_cost_tier("rewrite_chapter") == "llm"

    def test_rule_tools_have_cost_tier(self):
        from app.agents.tools.registry import get_cost_tier
        for name in ("consistency_scan", "rhythm_analysis", "style_analysis",
                     "foreshadowing_check", "progress_report"):
            assert get_cost_tier(name) == "rule", f"{name} should be rule"

    def test_db_tools_default(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("knowledge_search") == "db"
        assert get_cost_tier("create_character") == "db"

    def test_unknown_tool_defaults_to_db(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("nonexistent_tool") == "db"


class TestTruncateResult:
    """感知工具输出截短测试"""

    def test_truncate_dict_with_list(self):
        from app.agents.tools.utils import _truncate_result
        data = {"items": list(range(10)), "name": "test"}
        result = _truncate_result(data, max_items=3, max_str_len=100)
        assert len(result["items"]) == 3
        assert result["name"] == "test"

    def test_truncate_dict_with_long_string(self):
        from app.agents.tools.utils import _truncate_result
        data = {"text": "a" * 200}
        result = _truncate_result(data, max_items=5, max_str_len=50)
        assert len(result["text"]) <= 50
        assert result["text"].endswith("...")

    def test_truncate_nested_dict(self):
        from app.agents.tools.utils import _truncate_result
        data = {"outer": {"inner_list": [1, 2, 3, 4, 5], "inner_str": "hello"}}
        result = _truncate_result(data, max_items=2, max_str_len=100)
        assert len(result["outer"]["inner_list"]) == 2
        assert result["outer"]["inner_str"] == "hello"

    def test_truncate_list_directly(self):
        from app.agents.tools.utils import _truncate_result
        data = [1, 2, 3, 4, 5, 6, 7]
        result = _truncate_result(data, max_items=3, max_str_len=100)
        assert len(result) == 3

    def test_truncate_short_data_unchanged(self):
        from app.agents.tools.utils import _truncate_result
        data = {"items": [1, 2], "name": "hi"}
        result = _truncate_result(data, max_items=5, max_str_len=100)
        assert result == data

    def test_truncate_non_collection_passthrough(self):
        from app.agents.tools.utils import _truncate_result
        assert _truncate_result(42, max_items=5, max_str_len=100) == 42
        assert _truncate_result(None, max_items=5, max_str_len=100) is None
```

- [ ] **Step 8: 运行完整测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS — 所有测试通过

- [ ] **Step 9: 重启后端确认导入无误**

Run: `docker compose restart backend && docker compose logs backend --tail=20`
Expected: 后端正常启动，无 ImportError

- [ ] **Step 10: 提交**

```bash
git add -A
git commit -m "refactor(workflow): update registry, exports, and tests for tool merge (43→35)"
```


---

## Task 9: agent_graph.py 成本控制 — 计数器 + BudgetTracker 集成 + 感知工具截短

**Files:**
- Modify: `backend/app/agents/agent_graph.py`
- Modify: `backend/app/agents/tool_context.py` — 新增 LLM 调用计数器 contextvar
- Test: `backend/tests/test_agent_tools.py`

这是核心的成本控制任务，在 wrapper 中集成三种机制。

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_tools.py` 末尾新增测试类：

```python
class TestCostControlMechanisms:
    """成本控制机制测试"""

    def test_llm_call_counter_default(self):
        from app.agents.tool_context import get_llm_call_count, reset_llm_call_count
        reset_llm_call_count()
        assert get_llm_call_count() == 0

    def test_llm_call_counter_increment(self):
        from app.agents.tool_context import increment_llm_call_count, get_llm_call_count, reset_llm_call_count
        reset_llm_call_count()
        increment_llm_call_count()
        assert get_llm_call_count() == 1
        increment_llm_call_count()
        assert get_llm_call_count() == 2
        reset_llm_call_count()
        assert get_llm_call_count() == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCostControlMechanisms -v`
Expected: FAIL — `ImportError: cannot import name 'get_llm_call_count'`

- [ ] **Step 3: 在 tool_context.py 新增 LLM 调用计数器**

在 `backend/app/agents/tool_context.py` 末尾添加：

```python
# 单次 SSE 请求内的 LLM 工具调用计数器
_llm_call_count: ContextVar[int] = ContextVar("llm_call_count", default=0)


def get_llm_call_count() -> int:
    """获取当前请求的 LLM 工具调用计数"""
    return _llm_call_count.get()


def increment_llm_call_count() -> int:
    """递增 LLM 工具调用计数，返回递增后的值"""
    current = _llm_call_count.get()
    new_val = current + 1
    _llm_call_count.set(new_val)
    return new_val


def reset_llm_call_count() -> None:
    """重置 LLM 工具调用计数（每次 SSE 请求开始时调用）"""
    _llm_call_count.set(0)
```

- [ ] **Step 4: 运行计数器测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py::TestCostControlMechanisms -v`
Expected: PASS

- [ ] **Step 5: 更新 agent_graph.py 的 wrapper**

替换 `backend/app/agents/agent_graph.py` 中 `_wrap_tool_with_hooks_and_cache` 函数和 `create_agent_graph` 函数：

```python
def _wrap_tool_with_hooks_and_cache(tool):
    """包装工具函数，添加缓存检查、成本控制和 post-hook 调用。

    三层成本控制（优先级从高到低）：
    1. BudgetTracker 降级 — 预算不足时拦截 LLM 工具
    2. 计数器 — 单轮连续 LLM 调用超限时拦截
    3. 感知工具输出截短 — 预算紧张时压缩输出

    缓存：感知类工具命中缓存时直接返回。
    Hooks：写入类工具成功后触发自动检查链。
    """
    from app.agents.tools.registry import get_cost_tier
    from app.agents.tools.utils import _truncate_result

    original_fn = tool.coroutine if hasattr(tool, 'coroutine') else None
    if original_fn is None:
        return tool

    tool_name = tool.name
    is_perception = tool_name in (
        "knowledge_search", "foreshadowing_check",
        "consistency_scan", "style_analysis",
        "rhythm_analysis", "progress_report",
    )

    async def wrapped_fn(*args, **kwargs):
        cost_tier = get_cost_tier(tool_name)

        # ---- 成本控制 1: BudgetTracker 降级 ----
        if cost_tier == "llm":
            cache = get_tool_cache()
            if cache and hasattr(cache, '_budget_tracker'):
                bt = cache._budget_tracker
                if bt and bt.should_throttle_llm_tool():
                    return {
                        "skipped": True,
                        "reason": "Token 预算不足（剩余 < 20%），建议先使用感知工具收集信息",
                        "tool_name": tool_name,
                    }

        # ---- 成本控制 2: 连续 LLM 调用计数器 ----
        _MAX_LLM_CALLS_PER_TURN = 3
        if cost_tier == "llm":
            from app.agents.tool_context import get_llm_call_count, increment_llm_call_count
            current_count = get_llm_call_count()
            if current_count >= _MAX_LLM_CALLS_PER_TURN:
                return {
                    "skipped": True,
                    "reason": f"本轮已调用 {current_count} 次 LLM 工具，达到上限。建议先使用感知工具收集信息，下轮再调用。",
                    "tool_name": tool_name,
                }
            increment_llm_call_count()

        # ---- 缓存检查（仅感知工具）----
        if is_perception:
            cache = get_tool_cache()
            if cache:
                cached = cache.get(tool_name, kwargs)
                if cached is not None:
                    logger.debug("Tool cache hit: %s", tool_name)
                    return cached

        # ---- 执行原始工具 ----
        result = await original_fn(*args, **kwargs)

        # ---- 成本控制 3: 感知工具输出截短 ----
        if is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache and hasattr(cache, '_budget_tracker'):
                bt = cache._budget_tracker
                if bt and bt.should_throttle_llm_tool():
                    result = _truncate_result(result, max_items=5, max_str_len=100)

        # ---- LLM 工具 token 消耗追踪 ----
        if cost_tier == "llm" and isinstance(result, dict):
            cache = get_tool_cache()
            if cache and hasattr(cache, '_budget_tracker'):
                bt = cache._budget_tracker
                if bt and "token_usage" in result:
                    try:
                        bt.llm_tool_tokens_used += result["token_usage"].get("total_tokens", 0)
                    except (TypeError, AttributeError):
                        pass

        # ---- 缓存写入（仅感知工具）----
        if is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache:
                cache.set(tool_name, kwargs, result)

        # ---- 缓存失效（写入工具执行后）----
        if not is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache:
                cache.invalidate_by_prefix([
                    "knowledge_search:", "consistency_scan:",
                    "style_analysis:", "rhythm_analysis:",
                    "progress_report:", "foreshadowing_check:",
                ])

        # ---- Post-hooks ----
        if isinstance(result, dict) and "error" not in result:
            pid = get_project_id()
            if pid is not None:
                try:
                    result = await run_post_hooks(tool_name, result, pid)
                except Exception as e:
                    logger.warning("Post-hook chain failed for %s: %s", tool_name, e)

        return result

    tool.coroutine = wrapped_fn
    return tool


def create_agent_graph(
    model_config_id: int | None = None,
    user_id: int | None = None,
    phase: str | None = None,
    model_name: str | None = None,
    max_output_tokens: int | None = None,
    project_id: int | None = None,
):
    """创建 Free Operation Agent 图实例。

    Args:
        model_config_id: 模型配置 ID
        user_id: 用户 ID
        phase: 当前创作阶段（决定可用工具集）
        model_name: 指定模型名称
        max_output_tokens: 输出 token 上限
        project_id: 项目 ID（用于动态工具注册表）
    """
    llm_service = resolve_llm_service(model_config_id, user_id, model_name)
    llm = _get_llm_from_service(llm_service, phase, max_output_tokens)

    # 选择工具集
    if project_id and phase:
        try:
            registry = ToolRegistry(project_id, phase)
            tools = registry.get_tools()
        except Exception:
            logger.warning("动态注册表失败，降级为静态注册表")
            tools = _PHASE_TOOLS.get(phase, WRITING_TOOLS)
    else:
        tools = _PHASE_TOOLS.get(phase, WRITING_TOOLS)

    # 包装工具：添加缓存 + 成本控制 + hooks
    tools = [_wrap_tool_with_hooks_and_cache(t) for t in tools]

    # 初始化请求级缓存
    cache = ToolResultCache()
    set_tool_cache(cache)

    # 重置 LLM 调用计数器
    from app.agents.tool_context import reset_llm_call_count
    reset_llm_call_count()

    graph = create_react_agent(
        model=llm,
        tools=tools,
    )
    return graph
```

注意：`is_perception` 列表已更新（移除了 `consistency_check` 和 `check_chapter_transition`，保留 `consistency_scan`），缓存失效前缀也同步移除了旧工具名。

- [ ] **Step 6: 运行完整测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 7: 重启后端确认导入无误**

Run: `docker compose restart backend && docker compose logs backend --tail=20`
Expected: 后端正常启动

- [ ] **Step 8: 提交**

```bash
git add backend/app/agents/agent_graph.py backend/app/agents/tool_context.py backend/tests/test_agent_tools.py
git commit -m "feat(workflow): integrate cost control — LLM call counter, BudgetTracker throttling, perception truncation"
```

---

## Task 10: 最终验证 — 全量测试 + 回归检查

**Files:**
- All modified files

- [ ] **Step 1: 运行全量后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试通过

- [ ] **Step 2: 运行前端 lint**

Run: `cd frontend && npm run lint`
Expected: 无新增错误

- [ ] **Step 3: 重启后端并验证 API 可达**

Run: `docker compose restart backend && sleep 3 && curl -s http://localhost:8000/health | head -1`
Expected: 后端正常响应

- [ ] **Step 4: 确认工具数量**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.tools.registry import AGENT_TOOLS; print(f'Tools: {len(AGENT_TOOLS)}'); print([t.name for t in AGENT_TOOLS])"`
Expected: `Tools: 35`，列表中不包含已删除的工具名

- [ ] **Step 5: 最终提交（如有遗留修正）**

```bash
git add -A
git commit -m "test(workflow): final verification — 35 tools, all tests pass"
```


---

## 补充：BudgetTracker 的请求级 ContextVar

Task 9 中 wrapper 访问 BudgetTracker 的方式需要修正。BudgetTracker 不能挂在 cache._budget_tracker 上（从未设置），应作为独立 ContextVar 在 tool_context.py 中管理。

在 Task 9 Step 3（tool_context.py 新增 LLM 调用计数器）中，**同时新增** BudgetTracker 的 ContextVar：

```python
# 请求级 BudgetTracker（用于成本控制）
_current_budget_tracker: ContextVar["BudgetTracker | None"] = ContextVar("budget_tracker", default=None)


def get_budget_tracker():
    """获取当前请求的 BudgetTracker"""
    return _current_budget_tracker.get()


def set_budget_tracker(tracker) -> None:
    """设置当前请求的 BudgetTracker"""
    _current_budget_tracker.set(tracker)
```

在 Task 9 Step 5（更新 agent_graph.py wrapper）中，将所有 `cache._budget_tracker` 替换为 `get_budget_tracker()`：

```python
# 成本控制 1: BudgetTracker 降级
if cost_tier == "llm":
    from app.agents.tool_context import get_budget_tracker
    bt = get_budget_tracker()
    if bt and bt.should_throttle_llm_tool():
        return {
            "skipped": True,
            "reason": "Token 预算不足（剩余 < 20%），建议先使用感知工具收集信息",
            "tool_name": tool_name,
        }

# 成本控制 3: 感知工具输出截短
if is_perception and isinstance(result, dict) and "error" not in result:
    from app.agents.tool_context import get_budget_tracker
    bt = get_budget_tracker()
    if bt and bt.should_throttle_llm_tool():
        result = _truncate_result(result, max_items=5, max_str_len=100)

# LLM 工具 token 消耗追踪
if cost_tier == "llm" and isinstance(result, dict):
    from app.agents.tool_context import get_budget_tracker
    bt = get_budget_tracker()
    if bt and "token_usage" in result:
        try:
            bt.llm_tool_tokens_used += result["token_usage"].get("total_tokens", 0)
        except (TypeError, AttributeError):
            pass
```

在 `create_agent_graph` 中初始化 BudgetTracker（与 cache 一起）：

```python
    # 初始化请求级缓存
    cache = ToolResultCache()
    set_tool_cache(cache)

    # 初始化请求级 BudgetTracker（默认 12000 token，实际由 SSE 端点覆盖）
    from app.agents.agent_context import BudgetTracker
    from app.agents.tool_context import set_budget_tracker, reset_llm_call_count
    set_budget_tracker(BudgetTracker(max_tokens=12000))

    # 重置 LLM 调用计数器
    reset_llm_call_count()
```

SSE 端点（`api/agent.py`）在创建 agent 前应设置实际预算值，此处 12000 仅作 fallback。SSE 端点的更新不在本计划范围内，但 BudgetTracker.max 可在 SSE 流开始时通过 `set_budget_tracker(BudgetTracker(max_tokens=actual_window))` 覆盖。

---

## 补充测试：BudgetTracker ContextVar

在 Task 9 Step 1 的 `TestCostControlMechanisms` 类中**新增**测试：

```python
    def test_budget_tracker_contextvar(self):
        from app.agents.tool_context import set_budget_tracker, get_budget_tracker
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=5000)
        set_budget_tracker(tracker)
        assert get_budget_tracker() is tracker
        assert get_budget_tracker().max == 5000
```

---

## 补充：Task 8 最终 __init__.py 统一更新

Task 8 Step 3 更新 registry.py 后，需同步确保所有 __init__.py 的导出与 registry.py 的导入一致。在 Task 8 Step 5（更新 tools/__init__.py）之前，先更新各子包的 __init__.py：

**perception/__init__.py**（已在 Task 4 Step 4 更新，此处确认）：

```python
"""感知工具（6个）— 只读查询"""

from .knowledge_search import knowledge_search
from .foreshadowing_check import foreshadowing_check
from .style_analysis import style_analysis
from .progress_report import progress_report
from .rhythm_analysis import rhythm_analysis
from .consistency_scan import consistency_scan
```

**creation/__init__.py**（合并 Task 5/6 的部分更新 + 移除 timeline_entry）：

```python
"""创作工具（23个）— 直接写入知识库"""

from .world_setting import create_world_setting
from .character import create_character
from .relation import create_relation
from .subplot import create_subplot
from .plot_question import create_plot_question
from .style_constraints import create_style_constraints
from .foreshadowing import create_foreshadowing
from .plot_block import create_plot_block
from .generate_outline import generate_outline
from .generate_chapter_outline import generate_chapter_outline
from .generate_chapter_content import generate_chapter_content
from .generate_story_seed import generate_story_seed
from .generate_world_setting_complete import generate_world_setting_complete
from .review_chapter import review_chapter
from .rewrite_chapter import rewrite_chapter
from .advance_phase import advance_phase
from .evolution_plan import create_evolution_plan
# 更新/删除工具
from .update_character import update_character
from .update_plot_block import update_plot_block
from .update_subplot import update_subplot
from .update_plot_question import update_plot_question
from .update_foreshadowing import update_foreshadowing
from .delete_plot_block import delete_plot_block
from .record_chapter_meta import record_chapter_meta
```

**assist/__init__.py**（已在 Task 7 Step 5 更新，此处确认）：

```python
"""创作辅助工具（2个）— 辅助创意决策"""

from .suggest_writing_direction import suggest_writing_direction
from .expand_world_setting import expand_world_setting
```
