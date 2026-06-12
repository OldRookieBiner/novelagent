# NovelAgent 领域术语

## 知识库 (Knowledge Base)

一个项目的所有结构化创作素材的集合，包括大纲、世界观、角色、伏笔、风格约束等。通过 KnowledgeBaseService 统一读写。

### 知识库实体

| 术语 | 说明 | ORM 模型 |
|------|------|----------|
| 大纲 (Outline) | 项目整体故事结构 | Outline |
| 章节大纲 (Chapter Outline) | 单章的写作蓝图 | ChapterOutline |
| 世界观 (World Setting) | 故事世界的设定 | WorldSetting |
| 角色 (Character) | 故事人物 | Character |
| 关系 (Relation) | 两角色间的关系 | Relation |
| 演变规划 (Evolution Plan) | 关系在特定章节的预期变化 | EvolutionPlan |
| 演变记录 (Evolution Record) | 关系实际发生的变化 | EvolutionRecord |
| 情节块 (Plot Block) | 跨章节的情节段落 | PlotBlock |
| 问题链 (Plot Question) | 悬念问题及其回答状态 | PlotQuestion |
| 支线 (Subplot) | 独立于主线的副线故事 | Subplot |
| 伏笔 (Foreshadowing) | 需要埋设和回收的叙事线索 | Foreshadowing |
| 时间线 (Timeline) | 章节级别的事件和情感记录 | TimelineEntry |
| 场景条目 (Scene Entry) | 单个场景的记录 | SceneEntry |
| 风格约束 (Style Constraints) | 写作风格规则和禁忌 | StyleConstraints |
| 风格快照 (Style Snapshot) | 单章的风格统计指标 | StyleSnapshot |
| 设定变更 (Setting Change) | 待审批的知识库修改提案 | SettingChange |
| 章节正文 (Chapter) | 章节的实际写作内容 | Chapter |
| 卷 (Volume) | 跨卷结构中的单卷 | Volume |
| 跨卷伏笔 (Cross-Volume Foreshadowing) | 跨卷范围的伏笔 | CrossVolumeForeshadowing |
| 跨卷支线 (Cross-Volume Subplot) | 跨卷范围的支线 | CrossVolumeSubplot |
| 角色变化日志 (Character Change Log) | 角色在卷间的变化记录 | CharacterChangeLog |
| 故事种子 (Story Seed) | 项目的核心叙事概念 | Project.story_seed |

### Store（知识库实体存储）

按领域实体分组的读写模块。每个 Store 管理一组内聚的实体，返回 dict 而非 ORM 对象。Store 之间不共享 session。调用方通过 KnowledgeBaseService facade 的属性式访问使用 Store。

| Store | 管理的实体 | 单实例 |
|-------|-----------|--------|
| OutlineStore | 大纲, 章节大纲 | 大纲是单实例 |
| WorldSettingStore | 世界观 | 是 |
| CharacterStore | 角色, 关系, 演变规划, 演变记录 | 否 |
| PlotStore | 情节块, 问题链, 支线 | 否 |
| ForeshadowingStore | 伏笔 | 否 |
| StyleStore | 风格约束, 风格快照 | 风格约束是单实例 |
| TimelineStore | 时间线, 场景条目 | 否 |
| VolumeStore | 卷, 跨卷伏笔, 跨卷支线, 角色变化日志 | 否 |
| ChapterStore | 章节正文 | 否 |
| ChangeStore | 设定变更 | 否 |

单实例 Store 提供 `update(data)` 无 id 方法——每个项目只有一个实例，Store 内部按 project_id 定位。

### Phase（创作阶段）

INCUBATION → STRUCTURE → WRITING → REVISION，决定 Agent 可用工具集和上下文优先级。

### 编排方法（KB facade）

跨 Store 的原子操作，由 KnowledgeBaseService facade 提供。内部用一个 session 完成所有写入，保证原子性。

| 方法 | 涉及的 Store |
|------|-------------|
| write_chapter_with_tracking | OutlineStore + ChapterStore + TimelineStore + ForeshadowingStore + StyleStore |
| batch_read_for_index | 所有 Store（只读） |
| batch_read_volume_for_index | VolumeStore + TimelineStore + ForeshadowingStore + SceneEntry |
| validate_prerequisites | OutlineStore + CharacterStore + WorldSettingStore + ForeshadowingStore + StyleStore + PlotStore + ChapterStore + TimelineStore |
| search_chapters_for_references | OutlineStore + ChapterStore |

### 章节品控 (Chapter Quality)

章节级别的质量审核与重写服务。深模块——调用方只需传入 chapter_number 和 LLM 实例，内部完成 KB 读取、上下文组装、LLM 调用、结果解析、DB 写入。

| 方法 | 说明 |
|------|------|
| review(chapter_number) | 6 维度审核，结果通过 ChapterStore 持久化 |
| rewrite(chapter_number) | 读上次审核反馈，重写章节，清空审核状态 |
| review_and_rewrite(chapter_number) | 审核不通过时自动重写再审核（内部方法，不暴露为 @tool） |

ChapterStore 扩展方法（支撑章节品控的写入路径）：

| 方法 | 说明 |
|------|------|
| save_review_result | 保存审核通过/未通过、反馈文本、结构化结果 |
| save_rewrite_result | 保存重写正文，清空审核状态，递增 rewrite_count |
