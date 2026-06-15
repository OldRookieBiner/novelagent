# Agent 工具体系优化实施计划

**状态**：✅ 已完成

---

## 完成的任务

| 里程碑 | 任务 | 状态 |
|--------|------|------|
| M1 | P0-2 generate_outline 死参数 | ✅ |
| M1 | P0-4 generate_chapter_content 吞异常 | ✅ |
| M2 | P0-3 advance_phase 并发多行（根因修复） | ✅ |
| M1 | P1-8 create_timeline_entry 去重 | ✅ |
| M3 | P1-10 review/rewrite max_tokens 管控 | ✅ |

---

## P0-3 实施步骤

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | `WorkflowState.project_id` 添加 `unique=True` | ✅ |
| 2 | 创建 alembic 迁移（去重 + unique 约束） | ✅ |
| 3 | 重写 `get_or_create_workflow_state` 使用 PostgreSQL upsert | ✅ |
| 4 | 重写 `advance_phase.py` 移除双重检查模式 | ✅ |
| 5 | `projects.py` 统一使用 `get_or_create_workflow_state` | ✅ |
| 6 | 新增 `test_workflow_upsert.py` 测试覆盖 | ✅ |
| 7 | 运行测试 170 passed, 14 skipped | ✅ |
| 8 | 运行 alembic migration + 重启后端 | ✅ |

---

## 测试

```bash
docker exec 95782fda6575_novelagent-backend-1 pytest -v
# 结果：170 passed, 14 skipped
```

---

## 改动后重建

```bash
docker compose restart backend
docker exec 95782fda6575_novelagent-backend-1 alembic upgrade head
```
