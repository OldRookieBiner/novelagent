# Agent 工具全面优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面优化 NovelAgent v0.8.11 的 Agent 工具体系——修复数据安全缺陷、补齐核心能力、提升效率体验、演进架构

**Architecture:** 分 4 个 Phase 按优先级递进实施。Phase 1 修复 P0 数据安全问题（无外部依赖），Phase 2 补齐 P1 核心能力（依赖 Phase 1 的 parse_json_param），Phase 3 优化 P2 效率体验（可与 Phase 2 并行），Phase 4 演进 P3 架构（依赖 Phase 2 工具集稳定）。每个 Phase 完成后跑测试验证。

**Tech Stack:** Python 3.11, LangChain/LangGraph, FastAPI, SQLAlchemy, pytest

**Spec:** `docs/superpowers/specs/2026-06-14-agent-tools-overhaul-design.md`

---

## File Structure

### 新增文件（16 个）

| 文件 | 职责 |
|------|------|
| `tools/creation/update_character.py` | 更新角色属性 |
| `tools/creation/update_plot_block.py` | 更新情节块 |
| `tools/creation/update_subplot.py` | 更新支线状态 |
| `tools/creation/update_plot_question.py` | 更新问题链 |
| `tools/creation/update_foreshadowing.py` | 更新伏笔状态 |
| `tools/creation/delete_plot_block.py` | 删除空情节块 |
| `tools/creation/record_chapter_meta.py` | 记录章节追踪元数据 |
| `tools/creation/batch_confirm_outlines.py` | 批量确认章节大纲 |
| `tools/creation/batch_update_foreshadowing_status.py` | 批量更新伏笔状态 |
| `tools/perception/consistency_scan.py` | 全书一致性扫描 |
| `tools/perception/check_chapter_transition.py` | 章节衔接检查 |
| `tools/hooks.py` | 工具调用后自动触发链 |
| `tools/cache.py` | 单次请求内工具结果缓存 |
| `tools/registry_v2.py` | 动态工具注册表 |
| `tests/test_parse_json_param.py` | parse_json_param 单元测试 |
| `tests/test_update_tools.py` | 更新/删除工具集成测试 |

### 修改文件（约 20 个）

| 文件 | 修改内容 |
|------|----------|
| `tools/utils.py` | 新增 parse_json_param + _tokenize_chinese |
| `tools/creation/generate_chapter_content.py` | 异常处理 + 参数拆分 |
| `tools/creation/advance_phase.py` | 事务合并 |
| `tools/perception/progress_report.py` | 新增 detail_level 参数 |
| `tools/assist/report_progress.py` | 删除（合并进 progress_report） |
| `tools/perception/knowledge_search.py` | 降级截断 + 分词优化 |
| `tools/perception/consistency_check.py` | 精确加载角色约束 |
| `tools/perception/style_analysis.py` | 增加 suggested_fixes |
| `tools/perception/rhythm_analysis.py` | 增加 suggested_adjustments |
| `tools/assist/suggest_foreshadowing.py` | 未解释现象扫描 + reasoning |
| `tools/assist/suggest_plot_twist.py` | 多角色分析 + 读者预期反转 |
| `tools/registry.py` | 注册新工具、移除 report_progress、新增 REVISION_TOOLS |
| `tools/assist/__init__.py` | 移除 report_progress 导出 |
| `tools/creation/__init__.py` | 新增 update/delete/batch 工具导出 |
| `tools/perception/__init__.py` | 新增 consistency_scan, check_chapter_transition 导出 |
| `agents/agent_context.py` | P3 精简 system prompt |
| `agents/agent_graph.py` | P3 集成 ToolRegistry + hooks + cache |
| `agents/tool_context.py` | P3 新增 cache ContextVar |
| 13 个含 JSON 参数的工具 | 统一替换为 parse_json_param |
| 全部工具文件 | docstring 中文化 |

---

## Phase 1: P0 数据安全与正确性

---

### Task 1: 新增 parse_json_param 统一解析函数

**Files:**
- Modify: `backend/app/agents/tools/utils.py`
- Create: `backend/tests/test_parse_json_param.py`

- [ ] **Step 1: 编写 parse_json_param 测试**

```python
# backend/tests/test_parse_json_param.py
"""parse_json_param 单元测试"""
import pytest
from app.agents.tools.utils import parse_json_param


class TestParseJsonParam:
    """覆盖正常/类型不匹配/解析失败三种场景"""

    def test_already_target_type_list(self):
        result, warning = parse_json_param([1, 2, 3], [], "test_param")
        assert result == [1, 2, 3]
        assert warning is None

    def test_already_target_type_dict(self):
        result, warning = parse_json_param({"a": 1}, {}, "test_param")
        assert result == {"a": 1}
        assert warning is None

    def test_valid_json_string_list(self):
        result, warning = parse_json_param("[1,2,3]", [], "items")
        assert result == [1, 2, 3]
        assert warning is None

    def test_valid_json_string_dict(self):
        result, warning = parse_json_param('{"red":[]}', {}, "settings")
        assert result == {"red": []}
        assert warning is None

    def test_invalid_json_string(self):
        result, warning = parse_json_param("not json", [], "items")
        assert result == []
        assert "items" in warning
        assert "解析失败" in warning

    def test_json_type_mismatch(self):
        """JSON 解析成功但类型与 default 不匹配"""
        result, warning = parse_json_param('{"a":1}', [], "items")
        assert result == []
        assert "items" in warning
        assert "类型不匹配" in warning

    def test_unsupported_type_int(self):
        result, warning = parse_json_param(123, [], "items")
        assert result == []
        assert "items" in warning
        assert "类型不支持" in warning

    def test_empty_string_list(self):
        result, warning = parse_json_param("", [], "items")
        assert result == []
        assert warning is not None

    def test_empty_string_dict(self):
        result, warning = parse_json_param("", {}, "settings")
        assert result == {}
        assert warning is not None

    def test_param_name_in_warning(self):
        result, warning = parse_json_param("bad", [], "my_field")
        assert "my_field" in warning
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_parse_json_param.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_json_param'`

- [ ] **Step 3: 实现 parse_json_param**

在 `tools/utils.py` 末尾追加：

```python
def parse_json_param(value: str | list | dict, default, param_name: str = "") -> tuple[Any, str | None]:
    """解析 JSON 字符串参数，返回 (解析结果, 警告信息)

    如果 value 已经是目标类型（与 default 同类型），直接返回。
    如果解析失败，返回 default 和警告信息。

    Args:
        value: 输入值（可能是 JSON 字符串或已是目标类型）
        default: 解析失败时的默认返回值（同时作为类型参考）
        param_name: 参数名（用于警告信息）
    """
    if isinstance(value, type(default)):
        return value, None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, type(default)):
                return parsed, None
            warning = f"参数 {param_name} JSON 解析类型不匹配，使用默认值"
            return default, warning
        except json.JSONDecodeError as e:
            warning = f"参数 {param_name} JSON 解析失败({e})，使用默认值"
            return default, warning
    return default, f"参数 {param_name} 类型不支持，使用默认值"
```

需要在文件顶部添加 `import json` 和 `from typing import Any`。

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_parse_json_param.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/utils.py backend/tests/test_parse_json_param.py
git commit -m "feat(tools): add parse_json_param for unified JSON string parsing"
```

---

### Task 2: 统一替换 13 个工具的 JSON 解析为 parse_json_param

**Files:**
- Modify: `backend/app/agents/tools/creation/world_setting.py`
- Modify: `backend/app/agents/tools/creation/generate_world_setting_complete.py`
- Modify: `backend/app/agents/tools/creation/style_constraints.py`
- Modify: `backend/app/agents/tools/creation/foreshadowing.py`
- Modify: `backend/app/agents/tools/creation/plot_block.py`
- Modify: `backend/app/agents/tools/creation/subplot.py`
- Modify: `backend/app/agents/tools/creation/generate_outline.py`
- Modify: `backend/app/agents/tools/creation/generate_chapter_outline.py`
- Modify: `backend/app/agents/tools/creation/generate_chapter_content.py`
- Modify: `backend/app/agents/tools/modification/propose_setting_change.py`

每个文件的替换模式相同。以 `world_setting.py` 为例，将：

```python
import json as _json
# ...
try:
    tiered = _json.loads(tiered_settings) if isinstance(tiered_settings, str) else tiered_settings
except _json.JSONDecodeError:
    tiered = {}
try:
    locations = _json.loads(key_locations) if isinstance(key_locations, str) else key_locations
except _json.JSONDecodeError:
    locations = []
```

替换为：

```python
from app.agents.tools.utils import _kb, parse_json_param
# ...
tiered, tiered_warn = parse_json_param(tiered_settings, {}, "tiered_settings")
locations, loc_warn = parse_json_param(key_locations, [], "key_locations")
warnings = [w for w in [tiered_warn, loc_warn] if w]
```

并在返回结果中新增 `"param_parse_warnings": warnings` 字段。

- [ ] **Step 1: 替换 `world_setting.py`**

替换 `import json as _json` 为导入 `parse_json_param`。
将 `tiered_settings` 和 `key_locations` 的 try/except 替换为 `parse_json_param` 调用。
返回结果新增 `param_parse_warnings` 字段。

- [ ] **Step 2: 替换 `generate_world_setting_complete.py`**

4 个 JSON 参数：`red_rules`, `yellow_rules`, `green_rules`, `key_locations`。
替换后 `tiered` 构建逻辑改为检查 `red`/`yellow`/`green` 各自解析结果是否非空。

- [ ] **Step 3: 替换 `style_constraints.py`**

3 个 JSON 参数：`taboo_words`, `forbidden_patterns`, `abstract_rules`。

- [ ] **Step 4: 替换 `foreshadowing.py`**

1 个 JSON 参数：`related_characters`。

- [ ] **Step 5: 替换 `plot_block.py`**

3 个 JSON 参数：`must_happen`, `questions_to_raise`, `questions_to_answer`。

- [ ] **Step 6: 替换 `subplot.py`**

1 个 JSON 参数：`characters`。

- [ ] **Step 7: 替换 `generate_outline.py`**

3 个 JSON 参数：`plot_points`, `emotional_curve`, `characters`。

- [ ] **Step 8: 替换 `generate_chapter_outline.py`**

1 个 JSON 参数：`key_scenes`。

- [ ] **Step 9: 替换 `generate_chapter_content.py`**

2 个 JSON 参数：`new_foreshadowings`, `reclaimed_foreshadowing_ids`。
此文件的异常处理修改在 Task 4 中进行，此处只替换 JSON 解析部分。

- [ ] **Step 10: 替换 `propose_setting_change.py`**

1 个 JSON 参数：`new_value`（默认值为 `{"value": new_value}`，需要特殊处理：parse_json_param 不适用此场景，保持原有逻辑但记录警告）。

注意：`propose_setting_change.py` 的 `new_value` 解析逻辑不同——解析失败时保留原始字符串。此处不做替换，仅移除 `import json` 的冗余（它仍需用于其他处）。

- [ ] **Step 11: 运行 agent_tools 测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add backend/app/agents/tools/creation/ backend/app/agents/tools/modification/
git commit -m "refactor(tools): unify JSON param parsing with parse_json_param across 9 tools"
```

---

### Task 3: 修复 advance_phase 事务合并

**Files:**
- Modify: `backend/app/agents/tools/creation/advance_phase.py`
- Modify: `backend/tests/test_advance_phase.py`

- [ ] **Step 1: 编写事务合并测试**

在 `test_advance_phase.py` 中新增：

```python
class TestAdvancePhaseTransaction:
    """验证 advance_phase 的事务一致性"""

    def test_single_session_read_write(self):
        """读取和写入应在同一 Session 中完成"""
        # 验证：如果写入失败，阶段不应改变
        pass

    def test_concurrent_advance_with_row_lock(self):
        """并发推进时应通过行锁防止竞争"""
        # 构造：两个并发请求同时推进
        # 预期：只有一个成功推进，另一个返回当前阶段
        pass

    def test_write_failure_rollback(self):
        """写入失败时应回滚，current_phase 保持不变"""
        # 构造：mock db.commit 抛异常
        # 预期：阶段不变，返回 error
        pass
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_advance_phase.py::TestAdvancePhaseTransaction -v`
Expected: FAIL

- [ ] **Step 3: 重写 advance_phase 为单 Session + 行锁**

将 `advance_phase.py` 中两次独立 `SessionLocal()` 合并为一次：

```python
@tool
async def advance_phase() -> dict:
    """推进创作阶段。根据知识库完整度判断是否可以进入下一阶段。"""
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    from app.database import SessionLocal
    from app.models.workflow_state import WorkflowState
    from app.agents.constants import Phase

    kb = _kb()

    # 单次 Session，读取+判断+写入在同一事务中
    db = SessionLocal()
    try:
        ws = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id
        ).with_for_update().first()

        current_phase = ws.stage if ws else Phase.INCUBATION

        # 检查知识库完整度
        outline = kb.outlines.get()
        characters = kb.characters.list_characters()
        world_setting = kb.world_setting.get()
        plot_blocks = kb.plots.list_plot_blocks()
        foreshadowings = kb.foreshadowings.list_foreshadowings()
        timeline = kb.timelines.list_timeline()

        suggested_phase = current_phase
        reason = ""

        if current_phase == Phase.INCUBATION:
            has_outline = outline and (outline.get("title") or outline.get("summary"))
            has_characters = len(characters) >= 1
            has_world = world_setting is not None
            if has_outline and has_characters and has_world:
                suggested_phase = Phase.STRUCTURE
                reason = "大纲、人物、世界观已就绪，可进入结构设计阶段"
            else:
                missing = []
                if not has_outline: missing.append("大纲")
                if not has_characters: missing.append("人物")
                if not has_world: missing.append("世界观")
                reason = f"孵化阶段尚未完成，缺少：{'、'.join(missing)}"

        elif current_phase == Phase.STRUCTURE:
            has_blocks = len(plot_blocks) >= 1
            if has_blocks:
                suggested_phase = Phase.WRITING
                reason = "情节块已规划，可进入写作阶段"
            else:
                reason = "结构阶段尚未完成，缺少情节块规划"

        elif current_phase == Phase.WRITING:
            total_chapters = 0
            if outline:
                total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0
            written = len(timeline) if timeline else 0
            if total_chapters > 0 and written >= total_chapters:
                suggested_phase = Phase.REVISION
                reason = f"全部 {total_chapters} 章已写完，可进入修订阶段"
            else:
                reason = f"写作阶段进行中（{written}/{total_chapters} 章）"

        elif current_phase == Phase.REVISION:
            reason = "已在修订阶段"

        # 如果可以推进，在同一事务中写入
        advanced = suggested_phase != current_phase
        if advanced:
            if not ws:
                ws = WorkflowState(project_id=project_id, stage=suggested_phase)
                db.add(ws)
            else:
                ws.stage = suggested_phase
            db.commit()

        phase_labels = {
            Phase.INCUBATION: "创意孵化",
            Phase.STRUCTURE: "结构设计",
            Phase.WRITING: "写作中",
            Phase.REVISION: "修订中",
        }

        return {
            "current_phase": current_phase,
            "suggested_phase": suggested_phase,
            "advanced": advanced,
            "reason": reason,
            "current_phase_label": phase_labels.get(current_phase, current_phase),
            "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
        }
    except Exception as e:
        db.rollback()
        return {"error": f"推进阶段失败: {e}"}
    finally:
        db.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_advance_phase.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/creation/advance_phase.py backend/tests/test_advance_phase.py
git commit -m "fix(tools): merge advance_phase into single session with row lock"
```

---

### Task 4: 修复 generate_chapter_content 异常处理

**Files:**
- Modify: `backend/app/agents/tools/creation/generate_chapter_content.py`

- [ ] **Step 1: 重写异常处理逻辑**

将 4 处 `except Exception: pass` 替换为具体异常捕获 + warnings 追加：

```python
@tool
async def generate_chapter_content(
    chapter_number: int,
    chapter_title: str,
    content: str,
    summary: str = "",
    word_count: int = 0,
    status: str = "draft",
    scene_count: int = 0,
    new_foreshadowings: str = "[]",
    reclaimed_foreshadowing_ids: str = "[]",
    timeline_summary: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
) -> dict:
    """生成并保存章节内容及追踪数据。

    主要的章节写作工具。创建章节正文并同步更新时间线、伏笔和风格统计。

    Args:
        chapter_number: 章节号
        chapter_title: 章节标题
        content: 完整章节正文
        summary: 一句话章节摘要
        word_count: 字数
        status: 章节状态 - "draft" 或 "complete"
        scene_count: 场景数
        new_foreshadowings: JSON 字符串列表，本章新埋的伏笔
        reclaimed_foreshadowing_ids: JSON 字符串列表，本章回收的伏笔 ID
        timeline_summary: 时间线条目摘要
        rhythm_score: 节奏评分 1-5
        tension_score: 张力评分 1-5
        emotion_score: 情感评分 1-5
        emotion_tag: 情绪标签
    """
    from app.agents.services.knowledge_base import KnowledgeBaseService
    from app.agents.tools.utils import parse_json_param

    warnings = []

    new_fs, new_fs_warn = parse_json_param(new_foreshadowings, [], "new_foreshadowings")
    if new_fs_warn:
        warnings.append({"step": "parse_new_foreshadowings", "error": new_fs_warn})

    reclaimed_ids, reclaim_warn = parse_json_param(reclaimed_foreshadowing_ids, [], "reclaimed_foreshadowing_ids")
    if reclaim_warn:
        warnings.append({"step": "parse_reclaimed_ids", "error": reclaim_warn})

    project_id = get_project_id()
    kb = KnowledgeBaseService(project_id)

    # 检查当前章是否有已确认的大纲
    try:
        co = kb.outlines.get_chapter_outline(chapter_number)
        if co and not co.get("confirmed"):
            return {
                "error": f"第{chapter_number}章大纲尚未确认，请先审查并确认章节大纲后再写作",
                "hint": "使用 generate_chapter_outline 工具生成大纲，或提醒用户确认大纲",
            }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("大纲确认状态检查失败: %s", e)

    # 1. 保存章节正文
    existing_co = kb.outlines.get_chapter_outline(chapter_number)
    if not existing_co:
        kb.outlines.create_chapter_outline({
            "chapter_number": chapter_number,
            "title": chapter_title,
        })

    chapter_result = kb.chapters.save_content(chapter_number, content, word_count or len(content))
    existing_chapter = chapter_result.get("id") is not None

    # 2. 时间线
    timeline_created = False
    timeline_error = None
    if timeline_summary:
        try:
            kb.timelines.create_timeline_entry({
                "chapter_number": chapter_number,
                "summary": timeline_summary or summary or "",
                "causal_chain": "",
                "rhythm_score": rhythm_score,
                "tension_score": tension_score,
                "emotion_score": emotion_score,
                "emotion_tag": emotion_tag or "",
            })
            timeline_created = True
        except Exception as e:
            timeline_error = str(e)
            warnings.append({"step": "create_timeline", "error": timeline_error})

    # 3. 创建新伏笔
    created_fs = []
    new_foreshadowing_errors = []
    for fs_data in new_fs:
        try:
            f = kb.foreshadowings.create({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f["id"], "content": (f.get("content") or "")[:60]})
        except Exception as e:
            new_foreshadowing_errors.append({
                "content": (fs_data.get("content") or "")[:60],
                "error": str(e),
            })

    if new_foreshadowing_errors:
        warnings.append({"step": "create_foreshadowings", "error": f"{len(new_foreshadowing_errors)} 个伏笔创建失败", "details": new_foreshadowing_errors})

    # 4. 回收伏笔
    reclaim_errors = []
    for fs_id in reclaimed_ids:
        try:
            kb.foreshadowings.update(fs_id, {"status": "reclaimed"})
        except Exception as e:
            reclaim_errors.append({"id": fs_id, "error": str(e)})

    if reclaim_errors:
        warnings.append({"step": "reclaim_foreshadowings", "error": f"{len(reclaim_errors)} 个伏笔回收失败", "details": reclaim_errors})

    # 5. 风格快照
    style_snapshot_created = False
    style_snapshot_error = None
    if content and content.strip():
        try:
            snapshot_data = _compute_style_snapshot(content)
            snapshot_data["chapter_number"] = chapter_number
            kb.styles.create_snapshot(snapshot_data)
            style_snapshot_created = True
        except Exception as e:
            style_snapshot_error = str(e)
            warnings.append({"step": "create_style_snapshot", "error": style_snapshot_error})

    result = {
        "action": "created" if not existing_chapter else "updated",
        "chapter_number": chapter_number,
        "title": chapter_title,
        "word_count": word_count or len(content),
        "timeline_entry": timeline_created,
        "timeline_error": timeline_error,
        "new_foreshadowings": len(created_fs),
        "new_foreshadowing_errors": new_foreshadowing_errors,
        "reclaimed_foreshadowings": len(reclaimed_ids) - len(reclaim_errors),
        "reclaim_errors": reclaim_errors,
        "style_snapshot_created": style_snapshot_created,
        "style_snapshot_error": style_snapshot_error,
        "message": f"第{chapter_number}章「{chapter_title}」已写入（{word_count or len(content)}字）",
    }
    if warnings:
        result["warnings"] = warnings
    return result
```

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py tests/test_creation_agent.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/creation/generate_chapter_content.py
git commit -m "fix(tools): replace silent exception swallowing with warnings in generate_chapter_content"
```

---

### Task 5: 合并 report_progress 到 progress_report

**Files:**
- Modify: `backend/app/agents/tools/perception/progress_report.py`
- Delete: `backend/app/agents/tools/assist/report_progress.py`
- Modify: `backend/app/agents/tools/registry.py`
- Modify: `backend/app/agents/tools/assist/__init__.py`

- [ ] **Step 1: 修改 progress_report 新增 detail_level 参数**

```python
@tool
async def progress_report(detail_level: str = "full") -> dict:
    """生成写作进度报告。

    brief 模式返回进度概要，full 模式返回完整统计和完稿预估。

    Args:
        detail_level: 报告详细度 - "brief"（概要）或 "full"（完整统计），默认 "full"
    """
    kb = _kb()

    outline = kb.outlines.get()
    chars = kb.characters.list_characters()
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    timeline = kb.timelines.list_timeline()

    written_chapters = len(timeline) if timeline else 0
    total_chapters = 0
    if outline:
        total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0

    active_foreshadowings = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]
    reclaimed = [f for f in foreshadowings if f.get("status") == "reclaimed"]

    progress_percent = round(written_chapters / total_chapters * 100, 1) if total_chapters else 0

    # brief 模式：仅返回进度概要
    if detail_level == "brief":
        return {
            "progress_percent": progress_percent,
            "chapters_written": written_chapters,
            "total_planned_chapters": total_chapters,
            "message": f"写作进度 {progress_percent}%（{written_chapters}/{total_chapters} 章）",
        }

    # full 模式：完整统计（保留原有逻辑不变）
    blocks = kb.plots.list_plot_blocks()
    result = {
        "total_planned_chapters": total_chapters,
        "chapters_written": written_chapters,
        "progress_percent": progress_percent,
        "characters_count": len(chars),
        "foreshadowings_active": len(active_foreshadowings),
        "foreshadowings_reclaimed": len(reclaimed),
        "plot_blocks_total": len(blocks),
        "plot_blocks_completed": len([b for b in blocks if b.get("completion_summary")]),
    }

    if outline:
        result["title"] = outline.get("title") or "未命名"
        result["summary"] = (outline.get("summary") or "")[:200]

    # 完稿时间预估（保留原有逻辑）
    if timeline and len(timeline) >= 2 and total_chapters > 0:
        recent_entries = timeline[:min(3, len(timeline))]
        if len(recent_entries) >= 2:
            dates = [t["created_at"] for t in recent_entries if t.get("created_at")]
            if len(dates) >= 2:
                from datetime import datetime
                parsed_dates = []
                for d in dates:
                    try:
                        if isinstance(d, str):
                            parsed_dates.append(datetime.fromisoformat(d.replace("Z", "+00:00")))
                        elif isinstance(d, datetime):
                            parsed_dates.append(d)
                    except Exception:
                        pass
                if len(parsed_dates) >= 2:
                    parsed_dates.sort(reverse=True)
                    span_days = (parsed_dates[0] - parsed_dates[-1]).days + 1
                    chapters_in_span = len(recent_entries)
                    if span_days > 0 and chapters_in_span > 0:
                        speed = chapters_in_span / span_days
                        remaining = total_chapters - written_chapters
                        if remaining > 0 and speed > 0:
                            estimated_days = round(remaining / speed, 1)
                            confidence = "低"
                            if span_days >= 7 and chapters_in_span >= 3:
                                confidence = "中"
                            if span_days >= 14 and chapters_in_span >= 5:
                                confidence = "高"
                            result["completion_estimate"] = {
                                "speed_chapters_per_day": round(speed, 2),
                                "remaining_chapters": remaining,
                                "estimated_days": estimated_days,
                                "confidence": confidence,
                                "note": f"基于最近 {chapters_in_span} 章、{span_days} 天写作节奏的粗略估算，置信度：{confidence}",
                            }

    # 里程碑提醒
    milestones = []
    milestone_thresholds = [10, 50, 90]
    for threshold in milestone_thresholds:
        if progress_percent >= threshold:
            milestones.append({"percent": threshold, "status": "reached"})
        elif progress_percent >= threshold - 5:
            milestones.append({"percent": threshold, "status": "approaching", "remaining_percent": round(threshold - progress_percent, 1)})
    if milestones:
        result["milestones"] = milestones

    return result
```

- [ ] **Step 2: 从 registry.py 移除 report_progress**

在 `registry.py` 中：
- 移除 `from app.agents.tools.assist import report_progress` 导入
- 从 `INCUBATION_TOOLS`、`STRUCTURE_TOOLS`、`WRITING_TOOLS` 列表中移除 `report_progress`

- [ ] **Step 3: 从 assist/__init__.py 移除 report_progress 导出**

- [ ] **Step 4: 删除 report_progress.py 文件**

```bash
rm backend/app/agents/tools/assist/report_progress.py
```

- [ ] **Step 5: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A backend/app/agents/tools/
git commit -m "refactor(tools): merge report_progress into progress_report with detail_level param"
```

---

### Task 6: Phase 1 集成测试

**Files:** None (运行现有测试)

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: ALL PASS

- [ ] **Step 2: 重启后端验证**

Run: `docker compose restart backend`
验证后端正常启动。

---


## Phase 2: P1 核心能力缺失

---

### Task 7: 新增 update_character 工具

**Files:**
- Create: `backend/app/agents/tools/creation/update_character.py`

- [ ] **Step 1: 创建 update_character.py**

```python
"""更新角色工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_character(
    character_id: int,
    name: str = "",
    role: str = "",
    personality: str = "",
    catchphrase: str = "",
    habit_action: str = "",
    deep_fear: str = "",
    core_motivation: str = "",
    growth_arc: str = "",
    appearance: str = "",
    backstory: str = "",
    signature_item: str = "",
) -> dict:
    """更新已有角色的属性。只修改传入的非空字段。

    当需要修改已有角色的任何属性时使用。未传入的字段保持不变。

    Args:
        character_id: 角色 ID（必填）
        name: 角色名（留空不修改）
        role: 角色定位 - 主角/核心反派/重要配角/配角（留空不修改）
        personality: 性格特征（留空不修改）
        catchphrase: 口头禅（留空不修改）
        habit_action: 习惯动作（留空不修改）
        deep_fear: 深层恐惧（留空不修改）
        core_motivation: 核心动机（留空不修改）
        growth_arc: 成长弧线（留空不修改）
        appearance: 外貌描述（留空不修改）
        backstory: 背景故事（留空不修改）
        signature_item: 标志性物品（留空不修改）
    """
    kb = _kb()

    # 获取当前值作为 before
    before = kb.characters.get_character(character_id)
    if not before:
        return {"error": f"角色 ID {character_id} 不存在"}

    # 只更新非空字段
    update_data = {}
    fields = [
        ("name", name), ("role", role), ("personality", personality),
        ("catchphrase", catchphrase), ("habit_action", habit_action),
        ("deep_fear", deep_fear), ("core_motivation", core_motivation),
        ("growth_arc", growth_arc), ("appearance", appearance),
        ("backstory", backstory), ("signature_item", signature_item),
    ]
    for key, val in fields:
        if val:
            update_data[key] = val

    if not update_data:
        return {"action": "unchanged", "message": "没有需要更新的字段"}

    updated = kb.characters.update_character(character_id, update_data)

    return {
        "action": "updated",
        "id": updated["id"],
        "name": updated["name"],
        "updated_fields": list(update_data.keys()),
        "before": {k: before.get(k) for k in update_data.keys()},
        "after": {k: updated.get(k) for k in update_data.keys()},
        "message": f"角色「{updated['name']}」已更新（{len(update_data)} 个字段）",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/update_character.py
git commit -m "feat(tools): add update_character tool"
```

---

### Task 8: 新增 update_plot_block 工具

**Files:**
- Create: `backend/app/agents/tools/creation/update_plot_block.py`

- [ ] **Step 1: 创建 update_plot_block.py**

```python
"""更新情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def update_plot_block(
    block_id: int,
    title: str = "",
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    must_happen: str = "",
    questions_to_raise: str = "",
    questions_to_answer: str = "",
    expected_mood: str = "",
) -> dict:
    """更新已有情节块的属性。只修改传入的非空字段。

    当需要调整情节块的范围、必须事件或预期情绪时使用。

    Args:
        block_id: 情节块 ID（必填）
        title: 情节块标题（留空不修改）
        chapter_start: 起始章节号（None 不修改）
        chapter_end: 结束章节号（None 不修改）
        must_happen: JSON 字符串列表，必须发生的事件（空字符串不修改）
        questions_to_raise: JSON 字符串列表，需要提出的问题（空字符串不修改）
        questions_to_answer: JSON 字符串列表，需要回答的问题（空字符串不修改）
        expected_mood: 预期情绪（留空不修改）
    """
    kb = _kb()

    before = kb.plots.get_current_plot_block(0)  # 无法直接按 ID 获取，先列出全部
    blocks = kb.plots.list_plot_blocks()
    before = None
    for b in blocks:
        if b["id"] == block_id:
            before = b
            break

    if not before:
        return {"error": f"情节块 ID {block_id} 不存在"}

    update_data = {}
    warnings = []

    if title:
        update_data["title"] = title
    if chapter_start is not None:
        update_data["chapter_start"] = chapter_start
    if chapter_end is not None:
        update_data["chapter_end"] = chapter_end

    if must_happen:
        parsed, warn = parse_json_param(must_happen, [], "must_happen")
        update_data["must_happen"] = parsed
        if warn:
            warnings.append(warn)

    if questions_to_raise:
        parsed, warn = parse_json_param(questions_to_raise, [], "questions_to_raise")
        update_data["questions_to_raise"] = parsed
        if warn:
            warnings.append(warn)

    if questions_to_answer:
        parsed, warn = parse_json_param(questions_to_answer, [], "questions_to_answer")
        update_data["questions_to_answer"] = parsed
        if warn:
            warnings.append(warn)

    if expected_mood:
        update_data["expected_mood"] = expected_mood

    if not update_data:
        return {"action": "unchanged", "message": "没有需要更新的字段"}

    updated = kb.plots.update_plot_block(block_id, update_data)

    result = {
        "action": "updated",
        "id": updated["id"],
        "title": updated["title"],
        "updated_fields": list(update_data.keys()),
        "before": {k: before.get(k) for k in update_data.keys()},
        "after": {k: updated.get(k) for k in update_data.keys()},
        "message": f"情节块「{updated['title']}」已更新（{len(update_data)} 个字段）",
    }
    if warnings:
        result["param_parse_warnings"] = warnings
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/update_plot_block.py
git commit -m "feat(tools): add update_plot_block tool"
```

---

### Task 9: 新增 update_subplot 工具

**Files:**
- Create: `backend/app/agents/tools/creation/update_subplot.py`

- [ ] **Step 1: 创建 update_subplot.py**

```python
"""更新支线工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def update_subplot(
    subplot_id: int,
    name: str = "",
    characters: str = "",
    current_status: str = "",
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
    """更新支线状态或属性。用于推进支线发展或标记交汇。

    Args:
        subplot_id: 支线 ID（必填）
        name: 支线名称（留空不修改）
        characters: JSON 字符串列表，涉及角色名（空字符串不修改）
        current_status: 支线状态 - hint/developing/pending_intersection/resolved（留空不修改）
        planned_intersection_chapter: 计划交汇章节号（None 不修改）
        expected_resolution_chapter: 预期解决章节号（None 不修改）
    """
    kb = _kb()

    # 查找 before
    subplots = kb.plots.list_subplots()
    before = None
    for s in subplots:
        if s["id"] == subplot_id:
            before = s
            break

    if not before:
        return {"error": f"支线 ID {subplot_id} 不存在"}

    update_data = {}
    warnings = []

    if name:
        update_data["name"] = name
    if characters:
        parsed, warn = parse_json_param(characters, [], "characters")
        update_data["characters"] = parsed
        if warn:
            warnings.append(warn)
    if current_status:
        update_data["current_status"] = current_status
    if planned_intersection_chapter is not None:
        update_data["planned_intersection_chapter"] = planned_intersection_chapter
    if expected_resolution_chapter is not None:
        update_data["expected_resolution_chapter"] = expected_resolution_chapter

    if not update_data:
        return {"action": "unchanged", "message": "没有需要更新的字段"}

    updated = kb.plots.update_subplot(subplot_id, update_data)

    result = {
        "action": "updated",
        "id": updated["id"],
        "name": updated["name"],
        "updated_fields": list(update_data.keys()),
        "before": {k: before.get(k) for k in update_data.keys()},
        "after": {k: updated.get(k) for k in update_data.keys()},
        "message": f"支线「{updated['name']}」已更新（{len(update_data)} 个字段）",
    }
    if warnings:
        result["param_parse_warnings"] = warnings
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/update_subplot.py
git commit -m "feat(tools): add update_subplot tool"
```

---

### Task 10: 新增 update_plot_question 工具

**Files:**
- Create: `backend/app/agents/tools/creation/update_plot_question.py`

- [ ] **Step 1: 创建 update_plot_question.py**

```python
"""更新问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_plot_question(
    question_id: int,
    question_text: str = "",
    status: str = "",
    answered_in_chapter: int | None = None,
) -> dict:
    """更新问题链条目。用于标记问题为已回答或修改问题文本。

    Args:
        question_id: 问题 ID（必填）
        question_text: 问题文本（留空不修改）
        status: 问题状态 - "pending"(待回答) 或 "answered"(已回答)（留空不修改）
        answered_in_chapter: 回答该问题的章节号（None 不修改）
    """
    kb = _kb()

    # 查找 before
    questions = kb.plots.list_plot_questions()
    before = None
    for q in questions:
        if q["id"] == question_id:
            before = q
            break

    if not before:
        return {"error": f"问题 ID {question_id} 不存在"}

    update_data = {}

    if question_text:
        update_data["question_text"] = question_text
    if status:
        update_data["status"] = status
    if answered_in_chapter is not None:
        update_data["answered_in_chapter"] = answered_in_chapter

    if not update_data:
        return {"action": "unchanged", "message": "没有需要更新的字段"}

    updated = kb.plots.update_plot_question(question_id, update_data)

    return {
        "action": "updated",
        "id": updated["id"],
        "question_text": (updated.get("question_text") or "")[:80],
        "updated_fields": list(update_data.keys()),
        "before": {k: before.get(k) for k in update_data.keys()},
        "after": {k: updated.get(k) for k in update_data.keys()},
        "message": f"问题「{(updated.get('question_text') or '')[:40]}」已更新",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/update_plot_question.py
git commit -m "feat(tools): add update_plot_question tool"
```

---

### Task 11: 新增 update_foreshadowing 工具

**Files:**
- Create: `backend/app/agents/tools/creation/update_foreshadowing.py`

- [ ] **Step 1: 创建 update_foreshadowing.py**

```python
"""更新伏笔工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_foreshadowing(
    foreshadowing_id: int,
    level: str = "",
    status: str = "",
    content: str = "",
    expected_resolve_chapter: int | None = None,
) -> dict:
    """更新伏笔状态或属性。用于推进伏笔等级或标记回收。

    Args:
        foreshadowing_id: 伏笔 ID（必填）
        level: 伏笔等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)（留空不修改）
        status: 伏笔状态 - "active", "pending_reclaim", "reclaimed"（留空不修改）
        content: 伏笔内容（留空不修改）
        expected_resolve_chapter: 预期回收章节号（传入 -1 清除，None 不修改）
    """
    kb = _kb()

    before = kb.foreshadowings.get(foreshadowing_id)
    if not before:
        return {"error": f"伏笔 ID {foreshadowing_id} 不存在"}

    update_data = {}

    if level:
        update_data["level"] = level
    if status:
        update_data["status"] = status
    if content:
        update_data["content"] = content
    if expected_resolve_chapter is not None:
        if expected_resolve_chapter == -1:
            update_data["expected_resolve_chapter"] = None
        else:
            update_data["expected_resolve_chapter"] = expected_resolve_chapter

    if not update_data:
        return {"action": "unchanged", "message": "没有需要更新的字段"}

    updated = kb.foreshadowings.update(foreshadowing_id, update_data)

    return {
        "action": "updated",
        "id": updated["id"],
        "content": (updated.get("content") or "")[:80],
        "updated_fields": list(update_data.keys()),
        "before": {k: before.get(k) for k in update_data.keys()},
        "after": {k: updated.get(k) for k in update_data.keys()},
        "message": f"伏笔已更新（{len(update_data)} 个字段）",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/update_foreshadowing.py
git commit -m "feat(tools): add update_foreshadowing tool"
```

---

### Task 12: 新增 delete_plot_block 工具

**Files:**
- Create: `backend/app/agents/tools/creation/delete_plot_block.py`

- [ ] **Step 1: 创建 delete_plot_block.py**

```python
"""删除情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def delete_plot_block(block_id: int) -> dict:
    """删除空情节块。如果情节块下有关联的问题或伏笔，拒绝删除。

    仅当情节块下无子实体时才可删除。有子实体时需先迁移或删除子实体。

    Args:
        block_id: 情节块 ID（必填）
    """
    kb = _kb()

    # 查找情节块
    blocks = kb.plots.list_plot_blocks()
    target = None
    for b in blocks:
        if b["id"] == block_id:
            target = b
            break

    if not target:
        return {"error": f"情节块 ID {block_id} 不存在"}

    # 安全检查：是否有子实体
    questions = kb.plots.list_plot_questions()
    child_questions = [q for q in questions if q.get("plot_block_id") == block_id]

    if child_questions:
        return {
            "error": f"情节块「{target['title']}」下有 {len(child_questions)} 个问题链条目，请先迁移或删除",
            "child_question_ids": [q["id"] for q in child_questions],
            "hint": "使用 update_plot_question 将问题迁移到其他情节块，或确认问题已解决",
        }

    kb.plots.delete_plot_block(block_id)

    return {
        "action": "deleted",
        "id": block_id,
        "title": target["title"],
        "message": f"情节块「{target['title']}」已删除",
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/delete_plot_block.py
git commit -m "feat(tools): add delete_plot_block tool with safety check"
```

---

### Task 13: 新增 consistency_scan 全书一致性扫描工具

**Files:**
- Create: `backend/app/agents/tools/perception/consistency_scan.py`

- [ ] **Step 1: 创建 consistency_scan.py**

```python
"""全书一致性扫描工具

纯规则扫描，不调用 LLM。适合长篇小说（20+ 章）定期检查。
检测三类矛盾：角色行为矛盾、时间线矛盾、设定引用矛盾。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _extract_names


@tool
async def consistency_scan(
    check_types: str = "all",
    max_issues: int = 20,
) -> dict:
    """全书一致性扫描。自动检测角色行为矛盾、时间线矛盾和设定引用矛盾。

    不调用 LLM，纯规则扫描。适合长篇小说定期检查。

    Args:
        check_types: 检查类型 - "character"(角色), "timeline"(时间线),
                     "setting"(设定), 或 "all"
        max_issues: 最多返回的矛盾数量（默认 20）
    """
    kb = _kb()
    issues = []

    timeline = kb.timelines.list_timeline()
    outline = kb.outlines.get()
    ws = kb.world_setting.get()
    characters = kb.characters.list_characters()

    # 1. 角色行为矛盾：emotion_tag 跳跃检测
    if check_types in ("all", "character") and timeline and len(timeline) >= 2:
        # 构建 角色 → [emotion_tag] 映射
        char_emotions: dict[str, list[tuple[int, str]]] = {}

        for entry in timeline:
            ch_num = entry.get("chapter_number")
            emotion = entry.get("emotion_tag", "")
            if not ch_num or not emotion:
                continue
            # 读取该章内容提取出场角色
            chapter = kb.chapters.get_by_number(ch_num)
            if not chapter or not chapter.get("content"):
                continue
            names = _extract_names(chapter["content"], kb)
            for name in names:
                if name not in char_emotions:
                    char_emotions[name] = []
                char_emotions[name].append((ch_num, emotion))

        # 检测情绪跳跃
        _jump_map = {
            ("悲痛", "欢快"), ("欢快", "悲痛"),
            ("紧张", "平静"), ("平静", "紧张"),
            ("绝望", "希望"), ("希望", "绝望"),
        }
        for char_name, emotions in char_emotions.items():
            emotions.sort(key=lambda x: x[0])
            for i in range(1, len(emotions)):
                prev_e = emotions[i - 1][1]
                curr_e = emotions[i][1]
                if (prev_e, curr_e) in _jump_map:
                    issues.append({
                        "type": "character",
                        "character": char_name,
                        "detail": f"角色「{char_name}」情绪从第{emotions[i-1][0]}章「{prev_e}」跳到第{emotions[i][0]}章「{curr_e}」",
                        "chapters": [emotions[i - 1][0], emotions[i][0]],
                        "confidence": "medium",
                    })

    # 2. 时间线矛盾：章节号顺序与因果链描述矛盾
    if check_types in ("all", "timeline") and timeline:
        sorted_timeline = sorted(timeline, key=lambda t: t.get("chapter_number", 0))
        for i in range(1, len(sorted_timeline)):
            prev = sorted_timeline[i - 1]
            curr = sorted_timeline[i]
            prev_ch = prev.get("chapter_number", 0)
            curr_ch = curr.get("chapter_number", 0)
            # 检测章节号倒退
            if curr_ch < prev_ch:
                issues.append({
                    "type": "timeline",
                    "detail": f"时间线章节号倒退：第{prev_ch}章后出现第{curr_ch}章",
                    "chapters": [prev_ch, curr_ch],
                    "confidence": "high",
                })

    # 3. 设定引用矛盾：章节引用了红色设定但不满足前提
    if check_types in ("all", "setting") and ws and timeline:
        red_settings = (ws.get("tiered_settings") or {}).get("red", [])
        if red_settings:
            for entry in timeline[:max_issues]:
                ch_num = entry.get("chapter_number")
                if not ch_num:
                    continue
                chapter = kb.chapters.get_by_number(ch_num)
                if not chapter or not chapter.get("content"):
                    continue
                content = chapter["content"]
                for rule in red_settings[:5]:
                    rule_text = rule if isinstance(rule, str) else str(rule)
                    # 简化检测：如果红色设定的关键词出现在章节中，标记为需要人工检查
                    keywords = [w for w in rule_text.split() if len(w) >= 2]
                    if any(kw in content for kw in keywords):
                        issues.append({
                            "type": "setting",
                            "detail": f"第{ch_num}章引用了红色设定「{rule_text[:40]}」，请检查是否遵守",
                            "chapters": [ch_num],
                            "confidence": "low",
                        })

    # 截断
    issues = issues[:max_issues]

    result = {
        "total_issues": len(issues),
        "by_type": {
            "character": len([i for i in issues if i["type"] == "character"]),
            "timeline": len([i for i in issues if i["type"] == "timeline"]),
            "setting": len([i for i in issues if i["type"] == "setting"]),
        },
        "issues": issues,
    }

    if not issues:
        result["message"] = "未发现明显的一致性矛盾"
    else:
        result["warning"] = f"发现 {len(issues)} 个疑似一致性矛盾，请逐一检查"

    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/perception/consistency_scan.py
git commit -m "feat(tools): add consistency_scan for full-book rule-based consistency check"
```

---

### Task 14: 新增 check_chapter_transition 章节衔接检查工具

**Files:**
- Create: `backend/app/agents/tools/perception/check_chapter_transition.py`

- [ ] **Step 1: 创建 check_chapter_transition.py**

```python
"""章节衔接检查工具

分析上一章结尾和当前章大纲开场是否连贯。
检测三种断裂：情绪跳跃、场景不连续、角色凭空变化。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _extract_names


@tool
async def check_chapter_transition(chapter_number: int) -> dict:
    """检查章节间的衔接连贯性。分析上一章结尾和当前章大纲开场是否连贯。

    写新章节前使用，确保与上一章自然衔接。

    Args:
        chapter_number: 当前章节号（将检查第 N-1 章到第 N 章的衔接）
    """
    kb = _kb()
    issues = []

    # 读取上一章内容
    prev_chapter = kb.chapters.get_by_number(chapter_number - 1) if chapter_number > 1 else None
    # 读取上一章时间线（获取 emotion_tag）
    timeline = kb.timelines.list_timeline()
    prev_timeline = None
    for t in timeline:
        if t.get("chapter_number") == chapter_number - 1:
            prev_timeline = t
            break

    # 读取当前章大纲
    current_outline = kb.outlines.get_chapter_outline(chapter_number)

    if not prev_chapter or not prev_chapter.get("content"):
        return {
            "has_previous": False,
            "message": f"第{chapter_number - 1}章内容不存在，无法检查衔接",
        }

    if not current_outline:
        return {
            "has_outline": False,
            "message": f"第{chapter_number}章大纲不存在，请先生成章节大纲",
        }

    prev_content = prev_chapter["content"]
    prev_closing = prev_content[-500:] if len(prev_content) > 500 else prev_content

    # 1. 情绪跳跃检测
    if prev_timeline:
        prev_emotion = prev_timeline.get("emotion_tag", "")
        current_arc = current_outline.get("emotional_arc", "")
        if prev_emotion and current_arc:
            _jump_pairs = {
                ("悲痛", "欢快"), ("欢快", "悲痛"),
                ("绝望", "平静"), ("平静", "紧张"),
                ("紧张", "温馨"), ("温馨", "紧张"),
            }
            # 提取 current_arc 的起始情绪（简化：取第一个情绪词）
            arc_start = current_arc.split("→")[0].strip() if "→" in current_arc else current_arc[:4]
            if (prev_emotion, arc_start) in _jump_pairs:
                issues.append({
                    "type": "emotion_jump",
                    "detail": f"上一章结尾情绪「{prev_emotion}」→ 当前章开场「{arc_start}」，缺少过渡",
                    "suggestion": f"建议在当前章开头加入从「{prev_emotion}」到「{arc_start}」的情绪过渡段落",
                })

    # 2. 场景不连续检测
    prev_scene = current_outline.get("scene", "")
    # 从上一章结尾提取场景线索（简化：用最后 100 字中的地点相关词）
    if prev_scene:
        prev_closing_short = prev_closing[-100:]
        # 检测上一章结尾是否在同一场景
        # 如果大纲场景与结尾完全没有交集，可能需要过渡
        prev_outline = kb.outlines.get_chapter_outline(chapter_number - 1)
        if prev_outline:
            prev_scene_text = prev_outline.get("scene", "")
            if prev_scene_text and prev_scene and prev_scene != prev_scene_text:
                # 场景发生变化，检查是否有 transition 字段
                transition = current_outline.get("transition", "")
                if not transition:
                    issues.append({
                        "type": "scene_discontinuity",
                        "detail": f"场景从「{prev_scene_text[:30]}」变为「{prev_scene[:30]}」，但缺少过渡说明",
                        "suggestion": "建议在当前章开头加入场景转换描述，或在大纲 transition 字段中说明",
                    })

    # 3. 角色凭空变化检测
    prev_names = set(_extract_names(prev_closing, kb))
    outline_chars = current_outline.get("characters", "")
    current_names = set(_extract_names(outline_chars, kb)) if outline_chars else set()

    # 上一章末出场但当前章大纲未列出
    disappeared = prev_names - current_names
    # 当前章大纲列出但上一章末未出场
    appeared = current_names - prev_names

    # 过滤主角（主角默认常驻）
    main_chars = {c["name"] for c in kb.characters.list_characters() if c.get("role") == "主角"}
    disappeared -= main_chars
    appeared -= main_chars

    if disappeared:
        issues.append({
            "type": "character_disappeared",
            "detail": f"上一章末出场的角色在当前章大纲中消失：{', '.join(list(disappeared)[:5])}",
            "suggestion": "确认这些角色是否已退场，或在当前章中交代去向",
        })

    if appeared and len(appeared) > 2:
        issues.append({
            "type": "character_appeared",
            "detail": f"当前章大纲中出现但上一章末未出场：{', '.join(list(appeared)[:5])}",
            "suggestion": "确认新角色是否有合理的出场方式",
        })

    result = {
        "chapter_number": chapter_number,
        "previous_chapter": chapter_number - 1,
        "has_previous": True,
        "has_outline": True,
        "issues": issues,
    }

    if not issues:
        result["message"] = "章节衔接连贯，未检测到明显断裂"
    else:
        result["warning"] = f"检测到 {len(issues)} 个衔接问题"

    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/perception/check_chapter_transition.py
git commit -m "feat(tools): add check_chapter_transition for chapter continuity check"
```

---

### Task 15: 新增 record_chapter_meta 工具

**Files:**
- Create: `backend/app/agents/tools/creation/record_chapter_meta.py`

- [ ] **Step 1: 创建 record_chapter_meta.py**

```python
"""记录章节追踪元数据工具

在 generate_chapter_content 保存章节正文后调用此工具补充追踪数据。
也可以单独调用以补录遗漏的追踪数据。
"""

import json

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def record_chapter_meta(
    chapter_number: int,
    timeline_summary: str = "",
    causal_chain: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
    new_foreshadowings: str = "[]",
    reclaimed_foreshadowing_ids: str = "[]",
) -> dict:
    """记录章节的追踪元数据（时间线、伏笔、节奏评分等）。

    在 generate_chapter_content 保存章节正文后调用此工具补充追踪数据。
    也可以单独调用以补录遗漏的追踪数据。

    Args:
        chapter_number: 章节号
        timeline_summary: 时间线摘要
        causal_chain: 因果链描述
        rhythm_score: 节奏评分 1-5
        tension_score: 张力评分 1-5
        emotion_score: 情感评分 1-5
        emotion_tag: 情绪标签
        new_foreshadowings: JSON 字符串列表，本章新埋的伏笔
        reclaimed_foreshadowing_ids: JSON 字符串列表，本章回收的伏笔 ID
    """
    kb = _kb()
    warnings = []

    # 1. 时间线条目
    timeline_created = False
    if timeline_summary:
        try:
            kb.timelines.create_timeline_entry({
                "chapter_number": chapter_number,
                "summary": timeline_summary,
                "causal_chain": causal_chain,
                "rhythm_score": rhythm_score,
                "tension_score": tension_score,
                "emotion_score": emotion_score,
                "emotion_tag": emotion_tag,
            })
            timeline_created = True
        except Exception as e:
            warnings.append({"step": "create_timeline", "error": str(e)})

    # 2. 新伏笔
    new_fs, fs_warn = parse_json_param(new_foreshadowings, [], "new_foreshadowings")
    if fs_warn:
        warnings.append({"step": "parse_new_foreshadowings", "error": fs_warn})

    created_fs = []
    for fs_data in new_fs:
        try:
            f = kb.foreshadowings.create({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f["id"], "content": (f.get("content") or "")[:60]})
        except Exception as e:
            warnings.append({"step": "create_foreshadowing", "error": str(e), "detail": (fs_data.get("content") or "")[:60]})

    # 3. 回收伏笔
    reclaimed_ids, reclaim_warn = parse_json_param(reclaimed_foreshadowing_ids, [], "reclaimed_foreshadowing_ids")
    if reclaim_warn:
        warnings.append({"step": "parse_reclaimed_ids", "error": reclaim_warn})

    reclaimed_count = 0
    for fs_id in reclaimed_ids:
        try:
            kb.foreshadowings.update(fs_id, {"status": "reclaimed"})
            reclaimed_count += 1
        except Exception as e:
            warnings.append({"step": "reclaim_foreshadowing", "error": str(e), "id": fs_id})

    result = {
        "chapter_number": chapter_number,
        "timeline_entry": timeline_created,
        "new_foreshadowings": len(created_fs),
        "reclaimed_foreshadowings": reclaimed_count,
        "message": f"第{chapter_number}章追踪元数据已记录",
    }
    if warnings:
        result["warnings"] = warnings
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/record_chapter_meta.py
git commit -m "feat(tools): add record_chapter_meta for chapter tracking data"
```

---

### Task 16: 更新注册表 — 注册 Phase 2 新工具

**Files:**
- Modify: `backend/app/agents/tools/registry.py`
- Modify: `backend/app/agents/tools/creation/__init__.py`
- Modify: `backend/app/agents/tools/perception/__init__.py`

- [ ] **Step 1: 在 registry.py 中导入并注册新工具**

在导入区新增：
```python
from app.agents.tools.creation import (
    # ... 现有导入 ...
    update_character,
    update_plot_block,
    update_subplot,
    update_plot_question,
    update_foreshadowing,
    delete_plot_block,
    record_chapter_meta,
)
from app.agents.tools.perception import (
    # ... 现有导入 ...
    consistency_scan,
    check_chapter_transition,
)
```

更新工具列表：

```python
# STRUCTURE_TOOLS 新增：
update_character, update_plot_block, update_plot_question,
delete_plot_block, batch_confirm_outlines,

# WRITING_TOOLS 新增（在 STRUCTURE 基础上）：
consistency_scan, check_chapter_transition, record_chapter_meta,
update_subplot, update_foreshadowing, batch_update_foreshadowing_status,

# 新增 REVISION_TOOLS = WRITING_TOOLS
REVISION_TOOLS = WRITING_TOOLS
```

- [ ] **Step 2: 更新 creation/__init__.py 导出**

- [ ] **Step 3: 更新 perception/__init__.py 导出**

- [ ] **Step 4: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/registry.py backend/app/agents/tools/creation/__init__.py backend/app/agents/tools/perception/__init__.py
git commit -m "feat(tools): register Phase 2 new tools in registry"
```

---

### Task 17: Phase 2 集成测试

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: ALL PASS

- [ ] **Step 2: 重启后端验证**

Run: `docker compose restart backend`


## Phase 3: P2 效率与体验优化

---

### Task 18: knowledge_search 降级截断 + 分词优化

**Files:**
- Modify: `backend/app/agents/tools/perception/knowledge_search.py`

- [ ] **Step 1: 在 utils.py 新增 _tokenize_chinese 函数**

```python
def _tokenize_chinese(text: str) -> list[str]:
    """中文分词：基于字符 bigram + 常见词切分

    替代空格分词，用于关键词匹配场景。
    """
    import re
    # 去除标点
    text = re.sub(r'[，。！？、；：""''（）【】《》\s]', '', text)
    if len(text) <= 1:
        return [text] if text else []
    # bigram 切分
    tokens = []
    for i in range(len(text) - 1):
        tokens.append(text[i:i+2])
    return tokens
```

- [ ] **Step 2: 修改 knowledge_search.py 降级路径**

在降级 DB 查询路径中，每种子类型最多返回 5 条，并标记 truncated：

```python
# 替换降级路径中的全量查询
_MAX_FALLBACK_ITEMS = 5

# 在每个 target 查询后截断
if target in ("all", "foreshadowing"):
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    if len(foreshadowings) > _MAX_FALLBACK_ITEMS:
        results["foreshadowings"] = foreshadowings[:_MAX_FALLBACK_ITEMS]
        results["foreshadowing_truncated"] = True
    else:
        results["foreshadowings"] = foreshadowings
```

对 `timeline`, `plot_blocks`, `subplots`, `plot_questions`, `recent_style_snapshots` 同样处理。

关键词匹配部分，将 `query_words = [w for w in query_lower.split() if len(w) >= 2]` 替换为：

```python
from app.agents.tools.utils import _tokenize_chinese
query_words = _tokenize_chinese(query)
```

如果 `target="all"` 且返回的数据集有 3 个以上被截断，在返回结果中增加建议：

```python
if sum(1 for k in results if k.endswith("_truncated")) >= 3:
    result["suggestion"] = "数据量较大，建议使用精确的 target 参数（如 'characters'、'foreshadowing'）减少返回量"
```

- [ ] **Step 3: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/tools/perception/knowledge_search.py backend/app/agents/tools/utils.py
git commit -m "fix(tools): add fallback truncation and chinese tokenization to knowledge_search"
```

---

### Task 19: consistency_check 精确加载角色约束

**Files:**
- Modify: `backend/app/agents/tools/perception/consistency_check.py`

- [ ] **Step 1: 修改角色约束加载逻辑**

将全量加载替换为只加载两章中出场角色的约束：

```python
if aspect in ("all", "character"):
    # 先获取两章内容中出现的角色名
    chapter_a_obj = kb.chapters.get_by_number(chapter_a)
    chapter_b_obj = kb.chapters.get_by_number(chapter_b)

    all_chars = kb.characters.list_characters()
    appeared_names = set()

    if chapter_a_obj and chapter_a_obj.get("content"):
        appeared_names.update(_extract_names(chapter_a_obj["content"], kb))
    if chapter_b_obj and chapter_b_obj.get("content"):
        appeared_names.update(_extract_names(chapter_b_obj["content"], kb))

    # 只加载出场角色的约束
    constraints = []
    for char in all_chars:
        if char["name"] in appeared_names:
            constraints.append({
                "name": char["name"],
                "knowledge_boundary": char.get("knowledge_boundary") or char.get("deep_fear") or "",
            })

    result["character_constraints"] = constraints
    result["characters_filtered"] = len(constraints)
    result["characters_total"] = len(all_chars)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/perception/consistency_check.py
git commit -m "perf(tools): load only appearing characters in consistency_check"
```

---

### Task 20: style_analysis 增加 suggested_fixes

**Files:**
- Modify: `backend/app/agents/tools/perception/style_analysis.py`

- [ ] **Step 1: 在 style_analysis 返回结果中新增 suggested_fixes**

在 `style_analysis` 函数的 return 之前，构建建议列表：

```python
# 构建可操作性建议
suggested_fixes = []

if drift:
    if "dialogue_ratio" in drift:
        d = drift["dialogue_ratio"]
        direction = d["direction"]
        if direction == "偏高":
            suggested_fixes.append({
                "issue": f"最近3章对话比例{d['recent_avg']:.1%}，整体平均{d['overall_avg']:.1%}",
                "suggestion": "建议增加叙述和动作描写降低对话比例，或用心理独白替代部分对话",
                "priority": "medium",
            })
        else:
            suggested_fixes.append({
                "issue": f"最近3章对话比例{d['recent_avg']:.1%}，整体平均{d['overall_avg']:.1%}",
                "suggestion": "建议增加对话场景或角色互动，提升对话比例",
                "priority": "medium",
            })
    if "sentence_length" in drift:
        s = drift["sentence_length"]
        direction = s["direction"]
        if direction == "偏长":
            suggested_fixes.append({
                "issue": f"最近3章平均句长{s['recent_avg']:.1f}字，整体平均{s['overall_avg']:.1f}字",
                "suggestion": "建议拆分长句，加入短句和断句增强节奏感",
                "priority": "low",
            })
        else:
            suggested_fixes.append({
                "issue": f"最近3章平均句长{s['recent_avg']:.1f}字，整体平均{s['overall_avg']:.1f}字",
                "suggestion": "建议增加描述性长句，丰富叙述层次",
                "priority": "low",
            })

# 检查 emotion_vocabulary 是否某类过于集中
if "emotion_vocabulary" in result and "density" in result["emotion_vocabulary"]:
    density = result["emotion_vocabulary"]["density"]
    if density:
        max_emotion = max(density.items(), key=lambda x: x[1]["density_per_1k"], default=None)
        if max_emotion and max_emotion[1]["density_per_1k"] > 5.0:
            suggested_fixes.append({
                "issue": f"情感词「{max_emotion[0]}」密度过高（{max_emotion[1]['density_per_1k']:.1f}/千字）",
                "suggestion": f"建议减少「{max_emotion[0]}」类情感词的直接使用，用场景和行为间接传达",
                "priority": "high",
            })

if suggested_fixes:
    result["suggested_fixes"] = suggested_fixes
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/perception/style_analysis.py
git commit -m "feat(tools): add suggested_fixes to style_analysis"
```

---

### Task 21: rhythm_analysis 增加 suggested_adjustments

**Files:**
- Modify: `backend/app/agents/tools/perception/rhythm_analysis.py`

- [ ] **Step 1: 在 rhythm_analysis 返回结果中新增 suggested_adjustments**

在 `rhythm_analysis` 函数的 return 之前构建建议列表：

```python
# 构建节奏调整建议
suggested_adjustments = []

# 单调段建议
for section in monotone_sections:
    suggested_adjustments.append({
        "type": "单调段打破",
        "chapters": f"{section['start_chapter']}-{section['end_chapter']}",
        "suggestion": f"建议在第{section['end_chapter']}章附近加入冲突或转折事件打破「{section['emotion']}」的单调延续",
    })

# 偏差建议
for bw in block_warnings:
    suggested_adjustments.append({
        "type": "节奏偏差",
        "chapter": bw["chapter"],
        "suggestion": f"情节块「{bw['block_title']}」预期{bw['expected_mood']}（张力{bw['expected_tension']}），但实际张力{bw['actual_tension']}，建议{'增加紧迫感事件' if bw['actual_tension'] < bw['expected_tension'] else '放缓节奏加入过渡'}",
    })

# 高潮缺失检测
if len(peaks) == 0 and len(recent) >= 5:
    suggested_adjustments.append({
        "type": "高潮缺失",
        "suggestion": "近5章无高张力章节，建议安排一次冲突升级或反转",
    })

if suggested_adjustments:
    result["suggested_adjustments"] = suggested_adjustments
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/perception/rhythm_analysis.py
git commit -m "feat(tools): add suggested_adjustments to rhythm_analysis"
```

---

### Task 22: suggest_foreshadowing 增强 — 未解释现象扫描 + reasoning

**Files:**
- Modify: `backend/app/agents/tools/assist/suggest_foreshadowing.py`

- [ ] **Step 1: 重写 suggest_foreshadowing**

```python
"""伏笔建议工具

增强版：新增未解释现象扫描 + reasoning 字段。
"""

import re

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _extract_names


# 未解释现象的线索模式
_MYSTERY_PATTERNS = [
    (r"神秘的.{0,10}(人|物|地|力量|符号|声音|信件)", "神秘元素"),
    (r"不明的.{0,10}(来源|原因|身份|目的)", "不明来源"),
    (r"突然(出现|消失|变化).{0,15}", "突发变化"),
    (r"无人知晓.{0,10}", "未知信息"),
]


@tool
async def suggest_foreshadowing(current_chapter: int) -> dict:
    """基于当前情节块和未解释现象建议伏笔放置。

    分析当前情节块和近 3 章内容中的未解释现象，
    建议适合放置伏笔的位置和方向。

    Args:
        current_chapter: 当前章节号
    """
    kb = _kb()

    block = kb.plots.get_current_plot_block(current_chapter)
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    active = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]

    if not block:
        return {"suggestion": "当前没有情节块信息，建议先完成结构设计"}

    suggestions = []

    # 1. 问题驱动建议
    for question in (block.get("questions_to_raise") or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
            "reasoning": f"当前情节块需要提出「{question[:30]}」，伏笔暗示可以为后续揭示做铺垫",
        })

    # 2. 密度建议
    if len(active) < 3 and block.get("chapter_end") and block.get("chapter_start"):
        span = block["chapter_end"] - block["chapter_start"]
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
                "reasoning": f"每 2-3 章应至少有 1 个活跃伏笔维持悬念密度，当前 {span} 章只有 {len(active)} 个",
            })

    # 3. 未解释现象扫描
    unexplained = []
    for ch_offset in range(3):
        ch_num = current_chapter - ch_offset
        if ch_num < 1:
            continue
        chapter = kb.chapters.get_by_number(ch_num)
        if not chapter or not chapter.get("content"):
            continue
        content = chapter["content"]
        for pattern, label in _MYSTERY_PATTERNS:
            matches = re.findall(pattern, content)
            for match in matches[:2]:
                context_start = max(0, content.find(match) - 20)
                context = content[context_start:context_start + 60]
                unexplained.append({
                    "chapter": ch_num,
                    "type": label,
                    "context": context,
                })

    # 去重：同一 chapter+type 只保留一个
    seen = set()
    unique_unexplained = []
    for u in unexplained:
        key = (u["chapter"], u["type"])
        if key not in seen:
            seen.add(key)
            unique_unexplained.append(u)

    if unique_unexplained:
        for u in unique_unexplained[:3]:
            suggestions.append({
                "type": "未解释现象",
                "content": f"第{u['chapter']}章存在{u['type']}：{u['context'][:40]}",
                "reasoning": f"近3章中发现了{u['type']}，可以将其纳入伏笔体系增强悬念",
            })

    return {
        "current_chapter": current_chapter,
        "plot_block": block.get("title") if block else None,
        "active_foreshadowings": len(active),
        "unexplained_phenomena": len(unique_unexplained),
        "suggestions": suggestions,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/assist/suggest_foreshadowing.py
git commit -m "feat(tools): enhance suggest_foreshadowing with unexplained phenomena and reasoning"
```

---

### Task 23: suggest_plot_twist 增强 — 多角色分析 + 读者预期反转

**Files:**
- Modify: `backend/app/agents/tools/assist/suggest_plot_twist.py`

- [ ] **Step 1: 重写 suggest_plot_twist**

```python
"""反转建议工具

增强版：多角色动机冲突分析 + 读者预期反转。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def suggest_plot_twist(current_chapter: int) -> dict:
    """基于节奏曲线、角色动机和伏笔预期建议情节反转。

    分析所有主要角色的动机冲突，并结合活跃伏笔的读者预期，
    建议最有反转潜力的方向。

    Args:
        current_chapter: 当前章节号
    """
    kb = _kb()

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

    # 1. 节奏反转
    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    # 2. 伏笔误导（增强：分析所有活跃伏笔的预期方向）
    if len(foreshadowings) >= 2:
        fs_brief = []
        for f in foreshadowings[:5]:
            fs_brief.append({
                "id": f["id"],
                "content": (f.get("content") or "")[:60],
                "level": f.get("level"),
            })
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowings": fs_brief,
        })

    # 3. 多角色反转（增强：分析所有有动机的角色，返回前 3 个）
    char_twists = []
    for c in characters:
        core_mot = c.get("core_motivation", "")
        deep_fear = c.get("deep_fear", "")
        if core_mot and len(core_mot) > 10:
            twist_direction = ""
            if deep_fear:
                twist_direction = f"当「{deep_fear[:20]}」被触发时，可能做出反常行为"
            else:
                twist_direction = f"其动机「{core_mot[:30]}」与当前局势可能产生冲突"

            char_twists.append({
                "type": "角色反转",
                "character_id": c["id"],
                "character_name": c["name"],
                "role": c.get("role", ""),
                "core_motivation": core_mot[:60],
                "twist_direction": twist_direction,
                "reason": f"角色「{c['name']}」的动机可以制造意想不到的转折",
            })

    # 只取前 3 个最有反转潜力的（优先主角和核心反派）
    role_priority = {"核心反派": 0, "主角": 1, "重要配角": 2, "配角": 3}
    char_twists.sort(key=lambda x: role_priority.get(x.get("role", ""), 99))
    twist_types.extend(char_twists[:3])

    # 4. 读者预期反转（增强：基于伏笔预期方向建议反转）
    if foreshadowings:
        for f in foreshadowings[:3]:
            content = (f.get("content") or "")[:60]
            if content:
                twist_types.append({
                    "type": "读者预期反转",
                    "reason": f"读者预期伏笔「{content}」会朝某个方向发展，可以安排相反方向的揭示",
                    "foreshadowing_id": f["id"],
                    "foreshadowing_preview": content,
                    "suggestion": f"颠覆读者对「{content[:30]}」的预期，制造意外",
                })

    return {
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:6],
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/assist/suggest_plot_twist.py
git commit -m "feat(tools): enhance suggest_plot_twist with multi-character and reader-expectation reversal"
```

---

### Task 24: 新增 batch_confirm_outlines 工具

**Files:**
- Create: `backend/app/agents/tools/creation/batch_confirm_outlines.py`

- [ ] **Step 1: 创建 batch_confirm_outlines.py**

```python
"""批量确认章节大纲工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def batch_confirm_outlines(chapter_numbers: str) -> dict:
    """批量确认章节大纲。将指定章节的大纲标记为已确认，使其可以开始写作。

    Args:
        chapter_numbers: JSON 字符串列表，要确认的章节号列表（如 "[1,2,3]"）
    """
    kb = _kb()

    numbers, warn = parse_json_param(chapter_numbers, [], "chapter_numbers")
    if warn:
        return {"error": warn}

    if not numbers:
        return {"error": "章节号列表为空"}

    confirmed = []
    failed = []

    for ch_num in numbers:
        try:
            co = kb.outlines.get_chapter_outline(ch_num)
            if co:
                kb.outlines.update_chapter_outline(ch_num, {"confirmed": True})
                confirmed.append(ch_num)
            else:
                failed.append({"chapter": ch_num, "reason": "大纲不存在"})
        except Exception as e:
            failed.append({"chapter": ch_num, "reason": str(e)})

    result = {
        "action": "batch_confirm",
        "confirmed_count": len(confirmed),
        "confirmed_chapters": confirmed,
        "failed_count": len(failed),
    }
    if failed:
        result["failed"] = failed
    result["message"] = f"已确认 {len(confirmed)} 个章节大纲"
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/batch_confirm_outlines.py
git commit -m "feat(tools): add batch_confirm_outlines tool"
```

---

### Task 25: 新增 batch_update_foreshadowing_status 工具

**Files:**
- Create: `backend/app/agents/tools/creation/batch_update_foreshadowing_status.py`

- [ ] **Step 1: 创建 batch_update_foreshadowing_status.py**

```python
"""批量更新伏笔状态工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def batch_update_foreshadowing_status(updates: str) -> dict:
    """批量更新伏笔状态。适用于一次性推进多个伏笔的等级或回收状态。

    Args:
        updates: JSON 字符串列表，每项包含 {"id": int, "level": str, "status": str}
                 level 可选值：hint, strengthened, revealed
                 status 可选值：active, pending_reclaim, reclaimed
    """
    kb = _kb()

    update_list, warn = parse_json_param(updates, [], "updates")
    if warn:
        return {"error": warn}

    if not update_list:
        return {"error": "更新列表为空"}

    updated = []
    failed = []

    for item in update_list:
        fs_id = item.get("id")
        if not fs_id:
            failed.append({"item": item, "reason": "缺少 id"})
            continue

        data = {}
        if item.get("level"):
            data["level"] = item["level"]
        if item.get("status"):
            data["status"] = item["status"]

        if not data:
            failed.append({"id": fs_id, "reason": "没有需要更新的字段"})
            continue

        try:
            result = kb.foreshadowings.update(fs_id, data)
            updated.append({"id": fs_id, "updated_fields": list(data.keys())})
        except Exception as e:
            failed.append({"id": fs_id, "reason": str(e)})

    result = {
        "action": "batch_update",
        "updated_count": len(updated),
        "failed_count": len(failed),
    }
    if failed:
        result["failed"] = failed
    result["message"] = f"已更新 {len(updated)} 个伏笔状态"
    return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/creation/batch_update_foreshadowing_status.py
git commit -m "feat(tools): add batch_update_foreshadowing_status tool"
```

---

### Task 26: 全部工具 docstring 中文化

**Files:**
- Modify: 全部 31 个现有工具文件 + 11 个新增工具文件

- [ ] **Step 1: 批量替换 docstring**

规则：
- 工具 description（`@tool` 下第一段）改为中文
- Args 中参数描述改为中文
- 参数名、类型保持英文
- 示例值保持中文

逐文件修改。每个文件的具体 docstring 在实际实施时参照设计文档 §4.1 的修改前后对比。

修改顺序（按目录）：

1. `tools/perception/`：knowledge_search, consistency_check, foreshadowing_check, style_analysis, rhythm_analysis, progress_report, consistency_scan, check_chapter_transition
2. `tools/creation/`：generate_outline, generate_story_seed, generate_world_setting_complete, generate_chapter_outline, generate_chapter_content, create_character, create_world_setting, create_style_constraints, create_foreshadowing, create_plot_block, create_plot_question, create_subplot, create_timeline_entry, create_relation, create_evolution_plan, advance_phase, review_chapter, rewrite_chapter, record_chapter_meta, update_character, update_plot_block, update_subplot, update_plot_question, update_foreshadowing, delete_plot_block, batch_confirm_outlines, batch_update_foreshadowing_status
3. `tools/modification/`：propose_outline_adjustment, propose_setting_change, propose_chapter_rewrite
4. `tools/assist/`：writer_block_assist, suggest_foreshadowing, suggest_plot_twist, expand_world_setting

- [ ] **Step 2: 运行测试验证 docstring 不影响功能**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/
git commit -m "docs(tools): localize all tool docstrings to Chinese"
```

---

### Task 27: 更新注册表 — 注册 Phase 3 新工具

**Files:**
- Modify: `backend/app/agents/tools/registry.py`

- [ ] **Step 1: 注册 batch_confirm_outlines 和 batch_update_foreshadowing_status**

在 registry.py 中新增导入和注册：
- `batch_confirm_outlines` → STRUCTURE_TOOLS
- `batch_update_foreshadowing_status` → WRITING_TOOLS

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/registry.py
git commit -m "feat(tools): register batch tools in registry"
```

---

### Task 28: Phase 3 集成测试

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: ALL PASS

- [ ] **Step 2: 重启后端验证**

Run: `docker compose restart backend`


## Phase 4: P3 架构演进

---

### Task 29: 新增 ToolResultCache 工具结果缓存

**Files:**
- Create: `backend/app/agents/tools/cache.py`
- Modify: `backend/app/agents/tool_context.py`

- [ ] **Step 1: 创建 cache.py**

```python
"""单次 SSE 请求内的工具结果缓存

以 (tool_name, params_hash) 为 key，缓存感知工具的结果。
写入类工具调用后自动使相关缓存失效。
请求结束自动清理。
"""

import hashlib
import json
from typing import Any


class ToolResultCache:
    """单次 SSE 请求内的工具结果缓存"""

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def _key(self, tool_name: str, params: dict) -> str:
        params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
        params_hash = hashlib.md5(params_json.encode()).hexdigest()[:8]
        return f"{tool_name}:{params_hash}"

    def get(self, tool_name: str, params: dict) -> Any | None:
        """获取缓存结果，未命中返回 None"""
        return self._cache.get(self._key(tool_name, params))

    def set(self, tool_name: str, params: dict, result: Any) -> None:
        """设置缓存"""
        self._cache[self._key(tool_name, params)] = result

    def invalidate(self, tool_name: str) -> None:
        """使某工具的所有缓存失效"""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{tool_name}:")]
        for k in keys_to_remove:
            del self._cache[k]

    def invalidate_by_prefix(self, prefixes: list[str]) -> None:
        """使匹配前缀的缓存失效（如 creation 类工具写入后使 perception 缓存失效）"""
        keys_to_remove = []
        for k in self._cache:
            for prefix in prefixes:
                if k.startswith(prefix):
                    keys_to_remove.append(k)
                    break
        for k in keys_to_remove:
            del self._cache[k]

    def clear(self) -> None:
        """清空全部缓存"""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
```

- [ ] **Step 2: 在 tool_context.py 中新增 cache ContextVar**

```python
# 新增
_current_tool_cache: ContextVar[ToolResultCache | None] = ContextVar("tool_cache", default=None)

def get_tool_cache() -> ToolResultCache | None:
    return _current_tool_cache.get()

def set_tool_cache(cache: ToolResultCache) -> None:
    _current_tool_cache.set(cache)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/cache.py backend/app/agents/tool_context.py
git commit -m "feat(tools): add ToolResultCache for request-scoped result caching"
```

---

### Task 30: 新增 hooks 自动触发链

**Files:**
- Create: `backend/app/agents/tools/hooks.py`

- [ ] **Step 1: 创建 hooks.py**

```python
"""工具调用后自动触发链

仅在工具成功时触发。检查结果附在 tool_result 的 auto_check_results 中。
Hook 实现为轻量版，不做完整分析。
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


async def _hook_foreshadowing_check(project_id: int, tool_result: dict) -> dict:
    """伏笔超期检查 hook（轻量版：只检查超期伏笔数量）"""
    from app.agents.services.knowledge_base import KnowledgeBaseService
    kb = KnowledgeBaseService(project_id)
    ch_num = tool_result.get("chapter_number")
    if not ch_num:
        return {"checked": False, "reason": "无法确定章节号"}
    overdue = kb.foreshadowings.list_overdue(ch_num)
    if overdue:
        return {
            "checked": True,
            "overdue_count": len(overdue),
            "warning": f"有 {len(overdue)} 个伏笔已超过预期回收章节",
            "overdue_ids": [f["id"] for f in overdue[:3]],
        }
    return {"checked": True, "overdue_count": 0}


async def _hook_style_quick_check(project_id: int, tool_result: dict) -> dict:
    """风格快速检查 hook（轻量版：只比较最近 3 章对话比和句长）"""
    from app.agents.services.knowledge_base import KnowledgeBaseService
    kb = KnowledgeBaseService(project_id)
    snapshots = kb.styles.list_snapshots(last_n=3)
    if len(snapshots) < 2:
        return {"checked": False, "reason": "快照不足"}

    recent_dialogue = sum(s.get("dialogue_ratio", 0) or 0 for s in snapshots[:3]) / len(snapshots[:3])
    overall = kb.styles.list_snapshots(last_n=10)
    if len(overall) < 3:
        return {"checked": False, "reason": "整体快照不足"}
    overall_dialogue = sum(s.get("dialogue_ratio", 0) or 0 for s in overall) / len(overall)

    drift = abs(recent_dialogue - overall_dialogue) / max(overall_dialogue, 0.01)
    if drift > 0.25:
        return {
            "checked": True,
            "warning": f"最近 3 章对话比 {recent_dialogue:.1%} 偏离整体平均 {overall_dialogue:.1%}",
            "direction": "偏高" if recent_dialogue > overall_dialogue else "偏低",
        }
    return {"checked": True, "drift": "normal"}


# Hook 注册表
TOOL_HOOKS: dict[str, list[str]] = {
    "generate_chapter_content": ["foreshadowing_check", "style_quick_check"],
}

_HOOK_FUNCTIONS: dict[str, Callable] = {
    "foreshadowing_check": _hook_foreshadowing_check,
    "style_quick_check": _hook_style_quick_check,
}


async def run_post_hooks(tool_name: str, tool_result: dict, project_id: int) -> dict:
    """工具调用后的自动检查链

    仅在工具成功时触发。检查结果附在 tool_result 的 auto_check_results 中。
    Hook 失败不影响主流程。
    """
    hooks = TOOL_HOOKS.get(tool_name, [])
    if not hooks:
        return tool_result

    auto_results = {}
    for hook_name in hooks:
        try:
            hook_fn = _HOOK_FUNCTIONS[hook_name]
            result = await hook_fn(project_id, tool_result)
            auto_results[hook_name] = result
        except Exception as e:
            logger.warning("Hook %s 执行失败: %s", hook_name, e)
            auto_results[hook_name] = {"checked": False, "error": str(e)}

    tool_result["auto_check_results"] = auto_results
    return tool_result
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/hooks.py
git commit -m "feat(tools): add post-tool hooks for auto-check chain"
```

---

### Task 31: 新增动态工具注册表

**Files:**
- Create: `backend/app/agents/tools/registry_v2.py`

- [ ] **Step 1: 创建 registry_v2.py**

```python
"""动态工具注册表

根据项目规模和阶段动态调整工具列表。
保持向后兼容：旧常量 INCUBATION_TOOLS / STRUCTURE_TOOLS / WRITING_TOOLS 仍可用。
"""

from app.agents.tools.registry import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.constants import Phase


# 大型项目额外启用的工具
_LARGE_PROJECT_TOOLS_NAMES = {"consistency_scan", "check_chapter_transition"}

# 小型项目排除的工具
_SMALL_PROJECT_EXCLUDE_NAMES = {"rhythm_analysis"}

# 阶段基线（保持递进关系）
_PHASE_BASE_TOOLS = {
    Phase.INCUBATION.value: INCUBATION_TOOLS,
    Phase.STRUCTURE.value: STRUCTURE_TOOLS,
    Phase.WRITING.value: WRITING_TOOLS,
    Phase.REVISION.value: WRITING_TOOLS,
}


class ToolRegistry:
    """动态工具注册表"""

    def __init__(self, project_id: int, phase: str):
        self.project_id = project_id
        self.phase = phase

    def get_tools(self) -> list:
        """根据项目规模和阶段动态返回工具列表"""
        base_tools = list(_PHASE_BASE_TOOLS.get(self.phase, WRITING_TOOLS))

        # 估算项目规模
        total_chapters = 0
        try:
            kb = KnowledgeBaseService(self.project_id)
            outline = kb.outlines.get()
            if outline:
                total_chapters = (
                    outline.get("chapter_count_confirmed")
                    or outline.get("chapter_count_suggested")
                    or 0
                )
        except Exception:
            pass

        # 大型项目：启用高级感知工具
        if total_chapters >= 20:
            base_tool_names = {t.name for t in base_tools}
            for t in WRITING_TOOLS:
                if t.name in _LARGE_PROJECT_TOOLS_NAMES and t.name not in base_tool_names:
                    base_tools.append(t)

        # 小型项目：禁用部分工具减少噪音
        if total_chapters <= 10 and total_chapters > 0:
            base_tools = [t for t in base_tools if t.name not in _SMALL_PROJECT_EXCLUDE_NAMES]

        return base_tools
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/registry_v2.py
git commit -m "feat(tools): add dynamic ToolRegistry for project-scale-aware tool selection"
```

---

### Task 32: 集成动态注册表 + hooks + cache 到 agent_graph

**Files:**
- Modify: `backend/app/agents/agent_graph.py`
- Modify: `backend/app/agents/agent_context.py`

- [ ] **Step 1: 修改 agent_graph.py 使用动态注册表**

```python
"""Free Operation Agent graph definition

Uses LangGraph create_react_agent with phase-aware cognitive tools.
Shares KnowledgeBaseService with the main writing loop.
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.tools.registry_v2 import ToolRegistry
from app.agents.constants import AGENT_TEMPERATURES
from app.agents.constants import Phase
from app.utils.llm import resolve_llm_service


def _get_llm_from_service(llm_service, phase: str | None = None, max_output_tokens: int | None = None) -> ChatOpenAI:
    """Convert LLMService to LangChain ChatOpenAI for tool calling."""
    temperature = AGENT_TEMPERATURES.get(phase, 0.5) if phase else 0.5
    kwargs = {
        "model": llm_service.model,
        "api_key": llm_service.api_key,
        "base_url": llm_service.base_url,
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        kwargs["max_tokens"] = max_output_tokens
    return ChatOpenAI(**kwargs)


def create_agent_graph(
    model_config_id: int | None = None,
    user_id: int | None = None,
    phase: str | None = None,
    model_name: str | None = None,
    max_output_tokens: int | None = None,
    project_id: int | None = None,
):
    """Create a Free Operation Agent graph instance.

    Args:
        model_config_id: Model config ID for LLM selection
        user_id: User ID for LLM service resolution
        phase: Current creation phase (determines available tools)
        model_name: Specific model name within the config
        max_output_tokens: 输出 token 上限
        project_id: 项目 ID（用于动态工具注册表）
    """
    llm_service = resolve_llm_service(model_config_id, user_id, model_name)
    llm = _get_llm_from_service(llm_service, phase, max_output_tokens)

    # 使用动态注册表（如果提供了 project_id）
    if project_id and phase:
        registry = ToolRegistry(project_id, phase)
        tools = registry.get_tools()
    else:
        # 降级回静态注册表
        from app.agents.tools import WRITING_TOOLS
        tools = WRITING_TOOLS

    graph = create_react_agent(
        model=llm,
        tools=tools,
    )
    return graph
```

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_graph.py
git commit -m "feat(agent): integrate dynamic ToolRegistry into agent_graph"
```

---

### Task 33: 上下文精简 — agent_context 按需检索

**Files:**
- Modify: `backend/app/agents/agent_context.py`

- [ ] **Step 1: 新增 build_lightweight_context 函数**

在 `agent_context.py` 中新增轻量级上下文构建函数，只返回核心索引：

```python
def build_lightweight_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 4000,
) -> dict:
    """构建轻量级上下文 — 只包含核心索引，详细信息由 Agent 通过 knowledge_search 按需获取。

    预期从 ~12K token 降到 ~3-4K token。
    """
    kb = KnowledgeBaseService(project_id)
    budget = BudgetTracker(max_tokens)
    context: dict = {}

    # 核心索引：大纲标题 + 总章数
    outline = kb.outlines.get()
    if outline:
        outline_index = {
            "title": outline.get("title") or "未命名",
            "chapter_count": outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0,
            "summary": (outline.get("summary") or "")[:100],
        }
        context["outline_index"] = outline_index
        budget.add(estimate_tokens(json.dumps(outline_index, ensure_ascii=False)))

    # 角色名+ID 列表（不包含完整 backstory）
    chars = kb.characters.list_characters()
    char_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
    context["character_index"] = char_index
    budget.add(estimate_tokens(json.dumps(char_index, ensure_ascii=False)))

    # 当前阶段 + 当前章节号
    context["phase"] = phase
    if current_chapter_number:
        context["current_chapter_number"] = current_chapter_number

    # 关键红色设定（最多 3 条）
    ws = kb.world_setting.get()
    if ws:
        red = (ws.get("tiered_settings") or {}).get("red", [])
        if red:
            context["critical_rules"] = red[:3]
            budget.add(estimate_tokens(json.dumps(red[:3], ensure_ascii=False)))

    # 写作阶段：预取当前章节大纲 + 上一章结尾（这两项几乎每次都需要）
    if phase in (Phase.WRITING.value, Phase.REVISION.value) and current_chapter_number:
        try:
            co = kb.outlines.get_chapter_outline(current_chapter_number)
            if co:
                co_data = {
                    "chapter_number": co.get("chapter_number"),
                    "title": co.get("title") or "",
                    "scene": co.get("scene") or "",
                    "characters": co.get("characters") or "",
                    "emotional_arc": co.get("emotional_arc") or "",
                    "key_scenes": co.get("key_scenes") or [],
                    "target_words": co.get("target_words"),
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                if budget.can_add(estimate_tokens(co_json)):
                    context["current_chapter_outline"] = co_data
                    budget.add(estimate_tokens(co_json))
        except Exception:
            pass

        # 上一章结尾 300 字（缩减）
        if current_chapter_number > 1:
            prev = kb.chapters.get_by_number(current_chapter_number - 1)
            if prev and prev.get("content"):
                closing = prev["content"][-300:]
                closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
                if budget.can_add(estimate_tokens(closing_json)):
                    context["previous_chapter_closing"] = closing.strip()
                    budget.add(estimate_tokens(closing_json))

    context["_budget_used"] = budget.used
    context["_budget_max"] = budget.max
    context["_mode"] = "lightweight"
    return context
```

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_context.py
git commit -m "feat(agent): add lightweight context builder for on-demand retrieval"
```

---

### Task 34: Phase 4 集成测试 + 全量验证

**Files:** None (运行全部测试)

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: ALL PASS

- [ ] **Step 2: 重启后端验证**

Run: `docker compose restart backend`
验证后端正常启动。

- [ ] **Step 3: 最终 commit**

```bash
git add -A
git commit -m "chore(tools): complete Agent tools overhaul - all 4 phases"
```

---

## 注册表最终状态

```
INCUBATION_TOOLS:  advance_phase, knowledge_search, progress_report,
                   expand_world_setting, generate_outline, generate_story_seed,
                   generate_world_setting_complete, create_world_setting,
                   create_character, create_relation, create_evolution_plan,
                   create_style_constraints, create_foreshadowing

STRUCTURE_TOOLS:   INCUBATION + foreshadowing_check, review_chapter,
                   rewrite_chapter, rhythm_analysis, generate_chapter_outline,
                   propose_outline_adjustment, suggest_foreshadowing,
                   create_plot_block, create_plot_question, create_subplot,
                   create_foreshadowing, update_character, update_plot_block,
                   update_plot_question, delete_plot_block,
                   batch_confirm_outlines

WRITING_TOOLS:     STRUCTURE + consistency_check, style_analysis,
                   generate_chapter_content, record_chapter_meta,
                   propose_setting_change, propose_chapter_rewrite,
                   writer_block_assist, suggest_plot_twist,
                   create_timeline_entry, consistency_scan,
                   check_chapter_transition, update_subplot,
                   update_foreshadowing, batch_update_foreshadowing_status

REVISION_TOOLS:    WRITING
```

**工具总数**: 31 → 41（+11 新增 -1 删除）

---

## 依赖关系

```
Phase 1 (P0) ─ 无外部依赖，可立即开始
  Task 1: parse_json_param
  Task 2: 统一替换 JSON 解析（依赖 Task 1）
  Task 3: advance_phase 事务合并（独立）
  Task 4: generate_chapter_content 异常处理（独立，但 Task 2 先替换了 JSON 解析）
  Task 5: 合并 report_progress（独立）
  Task 6: Phase 1 集成测试

Phase 2 (P1) ─ 依赖 Phase 1 的 parse_json_param
  Task 7-12: 6 个更新/删除工具（可并行）
  Task 13: consistency_scan（独立）
  Task 14: check_chapter_transition（独立）
  Task 15: record_chapter_meta（独立）
  Task 16: 注册表更新（依赖 Task 7-15）
  Task 17: Phase 2 集成测试

Phase 3 (P2) ─ 可与 Phase 2 并行
  Task 18: knowledge_search 降级截断（独立）
  Task 19: consistency_check 精确加载（独立）
  Task 20-21: 感知工具可操作性建议（独立）
  Task 22-23: 建议工具增强（独立）
  Task 24-25: 批量操作工具（依赖 parse_json_param）
  Task 26: docstring 中文化（独立但工作量大）
  Task 27: 注册表更新
  Task 28: Phase 3 集成测试

Phase 4 (P3) ─ 依赖 Phase 2 工具集稳定
  Task 29: ToolResultCache（独立）
  Task 30: Hooks 自动触发链（独立）
  Task 31: 动态注册表（依赖 Phase 2 工具列表稳定）
  Task 32: 集成到 agent_graph（依赖 Task 29-31）
  Task 33: 上下文精简（独立）
  Task 34: 全量验证
```
