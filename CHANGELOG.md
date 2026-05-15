# Changelog

All notable changes to this project will be documented in this file.

## v0.8.10 - 2026-05-15

### 新功能

- **模型配置编辑模式防抖自动保存** - 编辑已有模型配置时，字段变更 500ms 后自动保存到后端，无需手动点击保存按钮
  - 使用 `formStateRef` + `dirtyFieldsRef` 模式避免 React 闭包陷阱，仅发送变更字段
  - 新建模式保持底部"添加配置"按钮，编辑模式无底部栏
  - 创建和更新使用独立的 `handleCreateModel` / `handleUpdateModel`，类型分别为 `ModelConfigCreate` / `ModelConfigUpdate`

- **灵感页模型下拉按配置名称分组** - AI 模型选择器按用户自定义的配置显示名称（`config.name`）分组，替代按 `provider` 硬编码分组
  - 删除 `providerNames` 硬编码映射，同一 provider 下多个配置可独立区分

- **健康检查并发测试所有模型** - 点击"健康检查"按钮后并发测试该配置下所有已添加模型，替代仅测试第一个模型
  - 后端 `asyncio.gather` 并发测试，逐模型 30s 超时 + 总 60s 超时
  - 逐模型 `health_status` / `health_latency` 写回 `config.models` JSON
  - 顶层 `health_status` 改为聚合值（全部健康 → healthy，任一异常 → unhealthy）
  - 前端 ModelCard 显示每个模型的健康状态指示器（绿色圆点+延迟 / 红色圆点+异常）

### 优化

- **LLM 服务从模型配置读取参数** - `get_llm_service_from_config` 改为通过 model id/name 匹配 ModelItem，从中读取 temperature 和 reasoning_effort，替代两次遍历
- **后端 update 保留健康状态** - `update_model_config` 更新 models 列表时保留已有模型的 `health_status` / `health_latency`，不被前端传来的值覆盖
- **API 类型统一** - `modelConfigsApi.checkHealth` 返回类型从内联重复定义改为使用 `HealthCheckResponse` 类型
- **datetime 弃用修复** - 健康检查时间戳从 `datetime.utcnow()` 改为 `datetime.now(timezone.utc)`
- **静默刷新分离** - 新增 `refreshModelConfigs`（不带 loading 状态），自动保存后使用静默刷新，避免 `configsLoading=true` 导致组件卸载

### 修复

- **获取模型弹窗无法滚动** - ScrollArea 的 `max-h-[280px]` 改为 `h-[280px]`。根因：CSS `height: 100%` 无法对 `max-height` 求值，Radix ScrollArea Viewport 高度解析为 auto，内部滚动永不触发
- **模型配置左栏边框未完全包围** - ModelConfigPanel 外层 div 添加 `h-full`。根因：子组件 `h-full` 无法对 `min-height` 求值，sidebar 高度仅为内容高度
- **获取模型弹窗点击添加后自动关闭** - `handleUpdateModel` 改用 `refreshModelConfigs` 替代 `loadModelConfigs`。根因：`loadModelConfigs` 设置 `configsLoading=true`，导致 `ModelConfigPanel` 切换到 LoadingSpinner，`ModelConfigDetail` 卸载，`fetchDialogOpen` 状态丢失
- **models handler 在 state updater 内执行副作用** - 五个 models handler 从 `setModels(prev => { 副作用; return updated })` 改为先计算 `updated` 再 `setModels(updated)` + 外部副作用，符合 React 纯函数规则

### 测试

- 新增 `test_model_config_health_all.py`（3 个测试）：ModelHealthResult schema、HealthCheckResponse 含 model_results、向后兼容

## v0.8.9 - 2026-05-14

### 新功能

- **章节重写 SSE 端点** - 新增 `POST /chapters/{id}/rewrite` SSE 流式重写端点
  - 重写时携带已写章节上下文和审核结果，LLM 可参考审核意见改写
  - 重写请求支持 `max_tokens` 参数，默认按目标字数动态计算
  - 前端 AIAssistantPanel 新增"重写"按钮，一键根据审核意见重写章节

- **SSE 心跳保活** - 新增 `format_heartbeat` 工具函数，审核 SSE 流使用注释行心跳保持连接
  - 审核 SSE 不再发送 chunk 事件，改用心跳注释行防止代理/网关超时断连

### 优化

- **审核 JSON 解析增强** - 3 策略解析：markdown 代码块提取 → 花括号逐层匹配 → 旧格式正则回退
  - 兼容 LLM 输出的多种 JSON 字段名（feedback/改进建议/problems）
  - 修复 LLM 返回多个 JSON 对象或包裹在代码块中时解析失败的问题

- **审核/重写上下文保留** - 修复重写时丢失 written_chapters 上下文的问题
  - `_build_rewrite_messages` 现在完整传入已写章节内容，确保重写时与前文风格一致

- **前端审核状态管理** - 修复 SSE 审核结果被 prop 数据覆盖的问题
  - 新增 `sseResultSetRef` 追踪 SSE 是否已设置结果，防止异步加载的 prop 数据覆盖实时结果
  - WritingPanel 中 `initialReviewResult` 使用 useMemo 缓存，避免不必要的重渲染

### 修复

- **SSE 流清理** - 组件卸载时正确中止进行中的 SSE 流，防止内存泄漏和状态错乱

### 测试

- 新增审核 SSE 事件格式测试（test_review.py）
- 新增重写 SSE 端点测试（test_rewrite.py）
- 新增 JSON 解析边界测试：feedback 字段、多对象、markdown 代码块

## v0.8.8 - 2026-05-14

### 优化

- **审核/重写消息结构优化** - 审核和重写节点采用与章节正文相同的 system/user 双层消息结构，提升 LLM 对角色定位和写作规则的遵循度
  - `_build_review_messages()` 和 `_build_rewrite_messages()` 改为同步函数，返回 {"system": ..., "user": ...} 结构
  - Review/Rewrite prompts 从 DB 加载后自动适配 dict 格式
  - 修复 review SSE 端点使用 `_build_review_messages` 的一致性问题
  - 修复 rewrite 节点 `_build_rewrite_messages` 异步调用问题

- **上下文传递优化** - 优化审核/重写节点传递前文上下文的方式
  - 新增 `context_strategy.py` 中的辅助函数用于构建前文上下文
  - 前端灵感面板新增小说长度选项（短篇/中篇/长篇/超长篇）

### 修复

- **写作面板修复** - 修复灵感面板相关 UI 问题
  - 修复 InspirationPanel 组件中的状态管理问题
  - 优化 inspiration.ts 中的数据处理逻辑

## v0.8.7 - 2026-05-12

### 修复

- **修复已规划项目重新规划报错"保存失败"** - 根因：replan 端点不接受 collected_info/inspiration_template，前端 handleReplan 不构建表单数据直接打开进度对话框。同时大纲标题为空导致 hasOutline=false，显示"开始规划"而非"重新规划"按钮，走 update_collected_info 路径被 outline.confirmed=True 拒绝
  - 后端 WorkflowReplanRequest 新增 collected_info/inspiration_template 字段，replan_workflow 端点在重置大纲前保存这些数据
  - 前端 handleReplan 构建与 handleConfirm 相同的 collectedInfo 数据存入 state，通过 OutlineProgressDialog → workflowApi.replanWorkflow 传到后端
  - OutlineProgressDialog 拆分 if(isReplan)/else 分支分别调用 replanWorkflow/runWorkflow

- **修复规划完成后大纲标题为空不显示** - 根因：LLM 输出格式为 `## 一、标题\n\n**《凡骨》**`，但正则不支持 `\n+` 多行间隔和 `\*{0,2}` 加粗标记，标题清理顺序错误（先删《》再删**导致残留）
  - RE_TITLE_CHAPTER 更新为支持 `\n+` 和 `**` 的模式
  - 新增 RE_TITLE_NEXT_LINE 匹配标题在下一行的格式
  - 标题清理顺序修正：先删 `**` 再删 `《》`
  - RE_SUMMARY_CHAPTER 同步支持多行间隔

- **章节大纲重新生成** - Phase 4 功能，支持保留大纲/人物/关系仅重新生成章节大纲
  - 后端新增 `POST /workflow/replan-chapter-outlines` 端点
  - 前端新增 ChapterOutlinePanel "重新生成章节大纲" 按钮和确认对话框
  - 前端灵感面板新增小说长度选项（短篇 3 万字 / 中篇 5 万字 / 长篇 10 万字 / 超长篇 20 万字）
  - 后端根据小说长度计算章节数和目标字数

### 测试

- 总计 221 测试通过（5 个预存失败与本次修复无关）

### 新功能

- **章节正文 System/User 双层消息** - 章节正文生成从单条 user message 拆分为 system + user 双层消息，LLM 对 system message 中的角色定位和写作规则遵循度显著提升
  - System message 包含：角色定位、写作原则、禁用词表、前文上下文、人物档案、世界观
  - User message 包含：章节大纲、前章结尾衔接、题材/字数/风格
  - `DEFAULT_PROMPTS["chapter_content_generation"]` 改为 `{"system": ..., "user": ...}` dict 格式
  - `_build_chapter_content_messages()` 统一构建双层消息，`_get_chapter_content_prompts()` 兼容旧格式

- **上下文策略模块** - 新增 ContextStrategy 策略模式，短篇自动将前文全文放入上下文（不再仅取最后 500 字）
  - 新建 `context_strategy.py`：ContextStrategy ABC + FulltextContentStrategy + get_context_strategy 工厂
  - 短篇（≤10万字）使用 Fulltext 策略，所有已写章节全文注入 system message
  - Hybrid/Summary 策略预留给中长篇（Phase 4）

- **审核输出 JSON 结构化** - 审核结果从自由文本标记格式改为 JSON 格式，解析更可靠
  - `parse_review_result()` 优先 JSON 解析，自动回退旧格式正则（`_parse_review_result_legacy`）
  - 新增 `outline_deviation`（大纲偏离度）审核维度，检查正文是否偏离章节大纲
  - `check_review_passed()` 新增大纲偏离度 ≤ 4 通过条件

### 重构

- **Prompt 加载统一为 state["_prompts"]** - 所有 7 个 LangGraph 节点从 `state["_prompts"]` 获取 prompt 模板，不再直接查询 DB，符合 LangGraph 合规性
  - 新增 `_build_prompts_dict()` 函数消除重复 prompt 构建代码
  - 新增 `_prompts: dict[str, str | dict]` 字段到 NovelState
  - 清理 `relation_generation.py` 中未使用的 `get_system_prompt` import

- **禁用词表独立模块** - 从 prompts.py 抽取 FORBIDDEN_WORDS、FORBIDDEN_PATTERNS、FORBIDDEN_RULES 到 `constants.py`，prompt 模板通过格式化函数注入

- **字数机制改为最低字数** - `parse_words_per_chapter` 返回 min_words 而非区间，章节内容 prompt 使用 min_words/suggested_max 替代 target_words

- **written_chapters 补充 title 字段** - `build_initial_state()` 中 written_chapters 新增 title，支持上下文策略格式化输出

### 测试

- 新增 test_context_strategy.py（7 个测试）：空前文、单章/多章、排除当前章、跳过空内容、策略选择
- 新增 test_review.py JSON 解析测试（7 个新测试）：JSON 通过/失败、前后文字、无效回退、legacy outline_deviation
- 更新 test_agents.py：chapter_content prompt 测试适配 dict 格式
- 更新 test_prompt_loader.py：dict 格式 prompt 长度检查兼容
- 更新 test_system_prompts.py：API 返回 user 模板而非 dict
- 总计 221 测试通过

## v0.8.5 - 2026-05-11

### 新功能

- **重新生成规划** - 支持重新生成大纲、人物和关系，解决规划失败无法重试和对结果不满意无法重新生成的问题
  - 后端新增 `POST /workflow/replan` 端点，清理旧数据后重新启动工作流
  - 后端新增 `POST /workflow/cleanup` 端点，修复前端重试时清理静默失败的问题
  - 前端灵感面板在规划完成后显示"重新规划"按钮
  - 点击后弹出确认对话框，确认后清理旧数据并重新生成
  - OutlineProgressDialog 支持 isReplan 模式，标题显示"正在重新规划"

### 优化

- **workflowApi 新增 replanWorkflow 方法** - 前端调用重新规划端点的统一方法

## v0.8.4 - 2026-05-10

### 重构

- **设置页面全面重构** - 采用全屏布局 + 侧边栏导航，统一设计风格
  - 侧边栏可折叠，显示"智能体"、"模型配置"、"提示词"标签页
  - ModelConfigDialog 支持 fetchModels 获取所有提供商的模型列表
  - ModelConfigItem 显示单类型模型的标签（如 o1、o3-mini）
  - 模型配置响应为空时回退到 model_name 字段
  - ProviderInfo 类型新增 models_api 字段
  - AGENT_TABS 完成所有标签页配置

## v0.8.3 - 2026-05-10

### 修复

- **修复章节审核点击"开始审核"后报错"审核失败"** - 根因：审核端点使用同步请求-响应模式，前端 30 秒超时被 AbortController 中止。将审核端点从同步 JSON 改为 SSE 流式模式（与章节生成一致），支持实时预览审核文本和取消审核
- **修复章节正文生成不完整截断问题** - LLM `max_tokens` 默认 4096 远不够 3000 中文章节所需，新增 `_calc_max_tokens` 按 2.5 倍计算（最低 8192），`chat_stream` 添加 `finish_reason=length` 截断检测
- **修复章节正文生成后不自动保存** - 后端将 Chapter 创建移到流内部原子性写入（创建或更新），不再预先创建空记录；前端生成后设置 `saved=true`
- **修复章节大纲生成完毕后报错"生成失败: network error"** - `createSSEStream` 收到 done 事件后立即退出循环避免网络误报错；后端 progress 事件发送完整章节大纲数据
- **修复 LLM choices 空列表 IndexError** - `chat()` 方法添加 `response.choices` 空列表防护，替代裸 IndexError；`chat_stream()` 同步修复
- **修复章节正文页面 AI 生成按钮报错** - 创建 `ChapterGenerateRequest` Pydantic schema 替代 FastAPI Request 对象，正确解析 `llm_config_id`；`review_chapter` 改用 LangGraph 节点函数
- **修复章节大纲只显示标题无场景/情节等字段** - 后端 progress 事件发送完整字段，前端使用后端返回的完整字段创建章节

### 优化

- **审核端点 SSE 流式改造** - 审核过程实时输出文本（chunk 事件），完成后发送结构化结果（done 事件），使用独立 Session 保存审核结果
- **章节正文 DB 写入独立 Session** - 使用 SessionLocal 创建独立会话，避免请求级 Session 在长流式操作期间失效
- **章节正文生成传入前章结尾** - `generate_chapter_content_stream` 从 state 获取 `previous_ending`，提升章节连贯性
- **后端架构优化** - 新增 `chapter_service`、`outline_service`、`workflow_orchestrator` 服务层，提取业务逻辑；`build_initial_state` 支持预加载角色/关系数据
- **LLM 服务异步化** - 新增 `get_llm_from_state_async`，在 async 节点中使用线程池执行同步 DB 操作，避免阻塞事件循环
- **前端 SSE 解析增强** - `createSSEStream` 支持 done 事件后优雅退出，避免连接关闭时的网络错误误报

## v0.8.2 - 2026-05-07

### 修复

- **修复章节大纲生成 SSE error 事件被忽略** - LLM 调用失败时前端无法感知错误，导致界面卡在"生成中"状态
- **修复章节大纲列表不实时更新** - 生成章节大纲时，章节列表在完成后才刷新，现在每完成一章立即显示
- **修复项目卡片"继续"按钮在当前页跳转** - 改为新标签页打开工作台

### 优化

- **模型选择全局同步** - 灵感面板选择的模型同步到章节大纲面板和章节正文面板，全局统一使用
- **章节大纲持久化统一** - 新增 `persist_chapter_outlines`，章节大纲生成持久化走 `workflow_persistence` 模块，符合 LangGraph 框架规范

## v0.8.1 - 2026-05-06

### 修复

- **修复项目列表排序混乱** - API 查询添加 `order_by(updated_at.desc())`，按最近更新排序
- **修复 SQLAlchemy 并发连接错误** - Checkpointer 改为独立 SessionLocal()，不再共享外部 db session，消除线程池并发操作同一连接池导致的 `isce` 错误
- **修复 logger 未定义错误** - workflow.py 模块顶部添加 logger 定义
- **修复关系生成节点角色 ID 缺失** - `generate_relations_node` 改为从数据库直接查询角色（带 id），解决 state 中角色缺少数据库 id 导致 name→id 映射失败的问题

## v0.8.0 - 2026-05-03

### 新功能

- **全新工作台页面** - 统一的写作工作台，替代旧的分散页面
  - Tab 布局：灵感采集、大纲、人物设定、人物关系、章节大纲、写作、审核
  - 可折叠面板，最大化编辑空间
  - 全局 Header 导航，返回按钮和项目列表入口
  - 面板状态自动保存，Tab 切换不丢失数据
- **人物设定模块** - 从大纲自动生成人物，支持手动创建和编辑
- **人物关系模块** - AI 自动生成人物关系图谱，支持手动创建和编辑关系
- **LangGraph 工作流全面升级**
  - 自动化大纲→人物→关系生成流程（无需逐步确认）
  - 大纲生成集成 SSE 进度对话框
  - LangGraph v1 检查点 API 迁移
- **TipTap 富文本编辑器** - 写作面板从纯文本升级为富文本编辑
- **灵感采集界面重构** - 左右分栏布局，实时 Prompt 模板预览，快速模板，步骤引导
- **首页重新设计** - 全局 Header、自适应网格、项目卡片新样式、创建项目对话框
- **章节大纲面板升级** - 进度条、一键确认全部、状态图标、统计卡片
- **写作面板优化** - 章节状态图标、键盘快捷键、骨架屏加载

### 优化

- **代码质量大幅提升**
  - 前端组件拆分：Settings、Writing、CharacterSetting 拆分为独立组件
  - 后端共享工具函数：提取节点通用逻辑，减少重复代码
  - 类型安全增强：窄化类型、移除不安全断言
  - React 性能优化：React.memo 和 useCallback 减少不必要渲染
- **UI 交互优化**
  - 统一 Loading 状态组件
  - 统一 Toast 错误提示
  - 大纲面板分组卡片布局，手动 AI 分析触发
  - 审核面板简化，移除写作辅助标签
- **大纲解析增强** - 支持多种 AI 输出格式，自动清理星号标记，解析失败时保留已有数据
- **SSE 流式处理增强** - 统一 chunk 格式、错误解析修复、重试前清理、空面板安全检查
- **工作流稳定性** - 空大纲自动终止、随机 thread_id、清理端点、plot_points 有效性校验
- **API 重构** - 确认端点使用 PUT 语义，移除废弃的 info_collection_chat 端点

### 修复

- 修复 SSE 事件对象解析错误（node_start/node_done/waiting）
- 修复 LangGraph v1 检查点兼容性问题（async aget_tuple/aput）
- 修复大纲进度对话框节点名称匹配问题
- 修复关系生成后 SSE 继续推送的问题
- 修复人物/关系节点缺少 waiting_for_confirmation 状态
- 修复工作流恢复功能
- 修复字数统计 HTML 标签计数问题（DOMPurify 净化）
- 修复 InspirationPanel 模板初始化、闭包过期、草稿清理问题
- 修复 TipTap 编辑器 key prop 缺失
- 修复主题色进度条适配、响应式网格列数

### 测试

- 新增页面集成测试：Login、Home、Settings
- 新增组件测试：CharacterList、ChapterNav、ChapterEditor
- 新增 Hook 测试：useCharacters、useSettings、useWriting
- 新增后端单元测试：依赖注入工具、节点工具函数
- 新增工作流测试：大纲失败中止、SSE 错误事件格式、plot_points 有效性、Prompt 加载回退

## v0.7.2 - 2026-04-28

### 新功能

- **灵感采集选项全面扩展**
  - 新增年代设定：古代、现代、未来、架空
  - 新增流派设定：脑洞文、废柴流、凡人流、洪荒流、无限流、种田文、争霸文、无敌流、苟道流、诸天流、系统流、直播流、自定义
  - 小说类型扩展至 13 种：玄幻、都市、仙侠、言情、历史、悬疑、科幻、游戏、奇幻、军事、灵异、竞技、同人
  - 世界观选项扩展至 15 种：新增仙侠世界、西幻大陆、末世废土、都市异能、宫廷宅斗、武侠江湖、星际帝国、游戏世界、灵异悬疑等
  - 主角设定拆分：男频显示男主人设，女频显示女主人设

### 优化

- **小说类型按热度重新排序**：玄幻、都市、仙侠、言情、历史、悬疑、科幻、游戏、奇幻、军事、灵异、竞技、同人
- **小说类型图标完善**：为所有 13 种类型添加图标
- **男频/女频选项分离**：代码结构支持差异化扩展，便于后续定制
- **表单交互优化**：切换目标读者时自动清除不相关的字段

### 修复

- 修复切换目标读者后旧字段值残留问题

## v0.7.1 - 2026-04-27

### 重构
- **简化智能体 Prompt 系统** - 移除项目级自定义 Prompt，仅保留系统级 Prompt 模板
- **设置页面 UI 优化** - "智能体管理"标签页，编辑框高度自适应屏幕，变量释义悬停显示

### 功能优化
- **5 个智能体 Prompt 全面优化**
  - 大纲生成：增加伏笔标记、人设深度、世界观扩展、题材适配指南
  - 章节大纲生成：增加延续性标注、伏笔跟踪、章节位置策略
  - 正文生成：扩充禁用词列表、增加自检清单、强化反 AI 味训练
  - 审核：新增大纲偏离度维度、细化评分标准
  - 重写：增加渐进式修改策略、自检清单
- **动态字数支持** - 正文生成 Prompt 使用 `{target_words}` 变量，根据灵感采集的目标字数动态调整

### 文档
- **CLAUDE.md 新增 Docker 操作安全约束** - 保护服务器运行环境不被误删

### 修复
- 修复 system_prompt schema 缺少 target_words 变量描述
- 修复后端容器未加载最新代码问题

## v0.7.0 - 2026-04-26

### Features
- **日志基础设施** - 可配置日志级别，全链路日志记录
- **统一错误处理** - 全局异常处理器，标准化错误响应格式
- **HttpOnly Cookie 认证** - Session Token 安全增强，防范 XSS 攻击
- **前端错误边界** - React ErrorBoundary 组件，友好的错误提示界面

### Fixes
- 修复限流中间件响应格式错误（使用 JSONResponse 替代 HTTPException）
- 修复 written_chapters 重复追加 bug（自定义 reducer 替换同章节号内容）
- 修复同步数据库调用阻塞事件循环问题（ThreadPoolExecutor 异步化）
- 修复前端 TypeScript 未使用变量警告

### Testing
- 新增 test_checkpointer.py - 检查点保存器测试（11 个测试）
- 新增 test_review.py - 审核节点测试（13 个测试）
- 新增 test_rewrite.py - 重写节点测试（10 个测试）
- 总计 113 个测试通过

### Improvements
- 检查点自动清理策略（每项目保留最新 20 个）
- 前端 Cookie 认证支持（credentials: include）
- 移除未使用的前端代码和导入
- 数据库查询优化（joinedload 防止 N+1 问题）

## v0.6.4 - 2026-04-24

### Features
- **多模型配置支持** - 支持配置多个 AI 模型，灵活切换
- **Coding Plan 类型 API** - 支持百度千帆、火山方舟、联通云等套餐类型 API
- **灵感采集页模型选择** - 生成内容时可选使用哪个模型
- **预设提供商配置** - DeepSeek、百度千帆、火山方舟、联通云一键配置

### Fixes
- 移除章节正文结尾的 LLM 生成数字（如字数统计）
- Writing 页面按钮调整：移除重复的 AI 生成按钮

### Improvements
- 使用 Sonner Toast 替换浏览器 alert 弹窗，更好的用户体验
- 重构模型配置页面，支持单模型和 Coding Plan 两种类型展示

## v0.6.2 - 2026-04-18

### Features
- LangGraph 工作流集成
- SSE 流式传输
- 暂停/恢复功能
- 工作流模式（逐步确认、智能混合、全自动）

## v0.2.0 - 2024-12-01

### Features
- Web 应用架构
- React + FastAPI + PostgreSQL
- 用户认证
- 项目管理
- 大纲生成
- 章节写作
- 审核功能
