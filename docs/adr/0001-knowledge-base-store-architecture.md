# ADR-0001: KnowledgeBaseService Store 拆分架构

## 状态

已接受

## 背景

KnowledgeBaseService 是一个 1396 行、64 个方法的 God Module，管理 ~15 种 ORM 模型的 CRUD。所有读方法返回 detached ORM 对象，导致 3 个调用方各自维护独立的 `_serialize()` 实现。写操作的工具文件手写 `SessionLocal()` + try/commit/rollback/close 模板（17 处）。`agent_context.py` 因 KB 缺少组合查询接口而直接访问 ORM 模型。

## 决策

### 1. 按领域实体拆分为 Store

KnowledgeBaseService 拆分为 10 个 Store + 1 个 thin facade：

| Store | 管理的模型 |
|-------|-----------|
| OutlineStore | Outline, ChapterOutline |
| WorldSettingStore | WorldSetting |
| CharacterStore | Character, Relation, EvolutionPlan, EvolutionRecord |
| PlotStore | PlotBlock, PlotQuestion, Subplot |
| ForeshadowingStore | Foreshadowing |
| StyleStore | StyleConstraints, StyleSnapshot |
| TimelineStore | TimelineEntry, SceneEntry |
| VolumeStore | Volume, CrossVolumeForeshadowing, CrossVolumeSubplot, CharacterChangeLog |
| ChapterStore | Chapter |
| ChangeStore | SettingChange |

ChapterOutline 归 OutlineStore 管理（而非 ChapterStore），因为其语义是"大纲视角的章节蓝图"。ChapterStore 需要章节大纲数据时，通过 OutlineStore 的内部方法获取。

### 2. Store 返回 dict，不返回 ORM 对象

- 所有读方法返回 `dict | list[dict] | None`
- 序列化在 Store 内部完成，去掉 `created_at`/`updated_at`
- 调用方不再需要 `_serialize()`、不再接触 detached ORM
- `DetachedInstanceError` 作为 bug 类目从系统中消除
- Pydantic V2 的 `model_validate(dict)` 自动处理 dict → response_model 映射，API 端点的 schema 和 response_model 声明无需修改

### 3. Session 管理统一用 `session()` 上下文管理器

- 废弃 `_get_db()` + `_close_db_read/write()` 旧模式
- 所有 Store 方法内部使用 `session()` 上下文管理器
- Store 暴露 `_*_with_session(db)` 内部方法，仅供 KB facade 的编排方法和批量读使用
- `_with_session` 以 `_` 前缀标记内部使用，代码审查时检查调用范围

### 4. 多表写入走 KB 编排方法，单 session 保证原子性

- 单表写入：直接调 Store（如 `kb.characters.create_character(data)`）
- 多表写入：KB 提供编排方法（如 `kb.write_chapter_with_tracking(...)`），内部用一个 session 完成所有操作
- 不接受多 session 各写各的作为默认模式
- 部分写入的不一致状态从可能发生变为不可能

### 5. 批量读共享 session

- 各 Store 提供 `_read_all_with_session(db)` 内部方法
- KB 的 `batch_read_for_index()` 在一个 `session(readonly=True)` 里依次调用
- 避免索引构建时的 N 次 session 开销

### 6. `validate_prerequisites` 迁入 KB

- 从 `agent_context.py` 迁移到 KB facade
- 利用各 Store 的内部方法，一次 session 完成所有检查
- `agent_context.py` 不再 import 任何 ORM 模型

### 7. `estimate_tokens` 统一到 `token_budget.py`

- 删除 `agent_context.py` 中的 `estimate_tokens` 重复定义
- 所有 token 估算统一引用 `token_budget.estimate_tokens`
- 保留 `token_budget.py` 的算法（CJK ×2 + 其他 ×0.5），因为偏低比偏高更安全——偏高会导致 context 预算过早截断

### 8. 单实例 Store 的无 id 更新方法

- OutlineStore、WorldSettingStore、StyleStore 各只有一个实例（per project）
- 提供无 id 的 `update(data)` 方法，消除调用方"先读再取 id"的两步操作
- 同时保留 `update_by_id(id, data)` 供 API 端点和 impact decision 场景使用
- OutlineStore 额外提供 `upsert(data)` 供初始化流程使用

### 9. 属性式 Store 访问

- 调用方通过 `kb.characters.list_characters()` 访问 Store
- 不在 KB 上提供 60+ 个便捷转发方法（如 `kb.list_characters()`）
- 不保留旧式便捷方法——迁移时直接改为 Store 属性式访问，不留中间态

### 10. 字段裁剪和内容截断在调用方完成

- Store 返回全量 dict，不替调用方做字段筛选或内容截断
- agent_context.py 的伏笔截断（60 字）、character 字段挑选等逻辑保留在 agent_context 层面
- 这是 token budget 逻辑的职责，不是 Store 的职责

## 后果

### 正面

- `_serialize` 从 3 处降为 0 处
- DB session 生命周期模板从 17 处降为 1 处（`session()` 上下文管理器）
- 新增实体的开发成本从 ~300 行/4 文件降为 ~80 行/2 文件
- `DetachedInstanceError` 从可能发生变为结构上不可能
- 部分写入的不一致状态从可能发生变为不可能（原子写入）
- 测试 setup 代码减少约 60-70%（mock dict vs mock ORM 链）
- 单实例 Store 的 `update(data)` 消除先读再取 id 的两步操作
- API 端点的 Pydantic schema 和 response_model 无需修改

### 负面

- 一次性改动量大：KB 1396 行拆分 + 所有调用方适配
- Store 的 `_with_session` 内部方法打破了"Store 自己管 session"的纯粹性，但仅限于 KB facade 内部使用
- 需要分阶段迁移

### 迁移策略

分 2 个阶段（原 3 阶段简化为 2）：

**阶段 1：Store 骨架 + dict 返回**

- 创建 `_BaseStore`（含 `session()` 上下文管理器）和 10 个 Store 类
- Store 的读方法直接返回 dict，写方法返回 dict
- KB facade 委托给 Store，属性式访问
- 同步更新所有调用方（agent_context、tools、API、services），从 `kb.get_xxx()` 改为 `kb.xxx_store.xxx()`
- 删除 `_serialize` 重复、`_get_db`/`_close_db_*` 旧方法、`estimate_tokens` 重复
- 迁移 `validate_prerequisites` 到 KB facade

**阶段 2：清理工具内的直接 DB 访问**

- 把工具文件中的 `SessionLocal()` + try/commit/rollback/close 替换为 KB 编排方法
- `generate_chapter_content` 改用 `kb.write_chapter_with_tracking()`
- `generate_chapter_outline` 改用 `kb.outlines.create_chapter_outline()` / `update_chapter_outline()`
- `review_chapter` 改用 KB 方法
- 删除 `agent_context.py` 中剩余的直接 DB 访问

阶段 2 可以在阶段 1 完成后独立推进，不阻塞阶段 1 的交付。
