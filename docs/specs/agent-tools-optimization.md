# Agent 工具体系优化 Spec

**状态**：✅ 已完成

**范围**：确认有价值的优化项
- ✅ P0-2: generate_outline 的 world_setting_summary 死参数
- ✅ P0-3: advance_phase 并发创建多行 WorkflowState（根因修复：unique 约束 + upsert）
- ✅ P0-4: generate_chapter_content 吞异常
- ✅ P1-8: create_timeline_entry 可能重复创建
- ✅ P1-10: review/rewrite 内部 LLM max_tokens 不受管控

**排除**：P0-1（低价值）、P1-6（低价值）、P1-7（不应处理）

---

## 完成情况

| # | 问题 | 状态 | 修改文件 |
|---|------|------|----------|
| P0-2 | 死参数 | ✅ 完成 | `generate_outline.py` |
| P0-3 | 并发多行 | ✅ 根因修复 | `workflow_state.py`（unique约束）、`workflow.py`（upsert）、`advance_phase.py`（移除双重检查）、`projects.py`（统一upsert）、alembic迁移 |
| P0-4 | 吞异常 | ✅ 完成 | `generate_chapter_content.py` |
| P1-8 | 去重 | ✅ 完成 | `timeline_entry.py` |
| P1-10 | max_tokens 管控 | ✅ 完成 | `chapter_quality.py`, `review_chapter.py`, `rewrite_chapter.py` |

---

## P0-3 根因修复详情

**问题**：`advance_phase` 在并发调用时可能创建多行 `WorkflowState`（同一 `project_id` 重复行），导致 `.first()` 返回不确定的行。

**根因**：`WorkflowState.project_id` 没有 unique 约束，数据库层面不保证唯一性。之前的双重重检查模式（`rollback()` → `begin()` → re-query）本身存在竞态窗口，属于补丁式修复。

**修复方案**：
1. `WorkflowState.project_id` 添加 `unique=True` 约束
2. Alembic 迁移：去重现有重复行 + 创建 unique 约束
3. `get_or_create_workflow_state` 改为 upsert：
   - PostgreSQL: `INSERT ... ON CONFLICT DO NOTHING` 原子操作
   - SQLite(测试): query + insert + IntegrityError 回退
4. `advance_phase.py` 移除双重检查模式，使用 `get_or_create_workflow_state`
5. `projects.py` 中直接 `WorkflowState()` 创建统一改为 `get_or_create_workflow_state`

---

## 测试结果

```
170 passed, 14 skipped
```

新增测试文件：`test_workflow_upsert.py`（7 个测试覆盖 upsert 行为、unique 约束、幂等性）
