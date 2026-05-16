# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-05-14

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** novelagent
- **Description:** AI 小说创作 Agent 系统 - 三 Agent 协作完成小说创作流程
- **LangGraph 工作流暂停机制：** 节点需要设置 `waiting_for_confirmation=True` 和 `confirmation_type` 才能让条件路由函数（如 `route_after_relations`）返回 `"wait_confirm"` 并路由到 `END`。否则工作流会继续执行后续节点。
- **SSE 流式完成信号：** `waiting` 事件表示工作流暂停，前端需要处理此事件作为当前阶段完成的信号，同时后端应在 `waiting` 后发送 `done` 事件确保前端收到完成通知。
- **LangGraph 图入口点问题：** `graph.astream_events(initial_state, config)` 始终从图的入口点（entry point）开始新执行，无论是否有检查点。不能用它来只执行图中某个特定节点。要执行特定节点，应使用子图（sub-graph）或直接调用节点函数。
- **build_initial_state 必须传 db 参数：** 调用 `build_initial_state` 时必须传入 `db=db` 参数，否则角色、关系、演变计划等数据不会被预加载，生成的章节内容会缺少人物设定和关系上下文。
- **前端 SSE 流状态管理：** 当需要"切换标签页保留进度"时，应将 SSE 流管理和生成状态提升到 Zustand store 层，而非仅提升状态。删除组件卸载时的 abort 调用，让 SSE 流在 store 层管理。这样组件卸载后 SSE 流继续运行，切回来时从 store 恢复进度。使用 useShallow selector 避免 store 变化触发不必要重渲染。
- **LLM 模型配置必须持久化到 workflow_states 表：** 工作流运行 Req 带来的 llm_config_id/llm_model_name 必须持久化到 DB，后续的审核/正文生成 SSE 端点从 DB 读取而不是让前端每次传递。符合 LangGraph 框架规范的模式：LLM 配置作为工作流状态的一部分存储，所有节点和端点从统一状态读取。
- **SSE 单节点端点不要覆盖 build_initial_state 返回的 written_chapters：** `build_initial_state(db=db)` 已从 DB 加载所有已写章节，review/rewrite 端点不应再覆盖为仅当前章节。覆盖会丢失前文上下文（角色演变、情节推进等）。如需确保当前章节在列表中，用追加而非替换。
- **重写 SSE 端点必须传递 max_tokens：** 重写输出是完整章节（3000+字），默认 max_tokens=4096 会导致截断。应使用 `_calc_max_tokens(target_words)` 动态计算，与 generate 端点一致。

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- [2026-05-09] **FastAPI 端点参数类型错误：** API 端点的 request body 参数必须使用 Pydantic BaseModel，不要用 `request: Request` (FastAPI 的 Request 对象) 来访问自定义字段如 `llm_config_id`。Request 对象只有 HTTP 相关属性，没有自定义字段。正确做法：创建对应的 Pydantic schema（如 ChapterGenerateRequest），让 FastAPI 自动解析 JSON body。
- [2026-05-09] **SSE 流式端点不应预先创建空 DB 记录：** generate_chapter 等端点不应在流开始前创建空 Chapter 记录（content=NULL）。如果流中断，空记录会残留。正确模式：在流完成后的 stream_generator 内部原子性创建/更新记录，与 create_chapter_outlines 的模式一致。
- [2026-05-09] **SSE 流式端点 DB 保存必须使用独立 Session：** 请求级 db 会话（Depends(get_db)）在长 LLM 流式操作后可能失效，且 get_db().finally 会 rollback+close。正确模式：在 stream_generator 内部用 SessionLocal() 创建独立会话，finally 中 close。
- [2026-05-09] **LLM 章节生成必须根据 target_words 动态计算 max_tokens：** 默认 max_tokens=4096 远不够 3000 中文字章节（需 8000+ token）。使用 _calc_max_tokens(target_words) = max(target_words * 2.5 + 512, 8192)。
- [2026-05-09] **generate_chapter_content_stream 必须传递 previous_ending：** 流式版本从 state.written_chapters 获取前章结尾，不能硬编码空字符串。
- [2026-05-09] **前端 loadContent 须做 HTML 格式化：** DB 存储原始文本（\n 分隔），前端显示需转为 HTML（<p> 标签）。loadContent 直接用 chapter.content 会丢失段落格式。
- [2026-05-09] **LLM chat/chat_stream 必须防护 choices 空列表：** 某些 OpenAI 兼容 API 返回 choices=[] 的 chunk（usage chunk、ping chunk 等），chat() 的 response.choices[0] 和 chat_stream() 的 chunk.choices[0] 都必须在访问前检查列表非空。否则抛出裸 IndexError "list index out of range"，所有 LLM 调用全部崩溃且无上下文信息。
- [2026-05-10] **outline_generation_node 必须设置足够 max_tokens：** 大纲输出包含标题/概述/世界观/人物设定/情节节点/情感曲线等多个板块，默认 max_tokens=4096 远不够（需 8192+），否则 LLM 截断导致标题等字段解析失败。
- [2026-05-10] **parse_outline 标题正则必须支持 ### 标题：** prompt 模板（OUTLINE_GENERATION_PROMPT）使用 ### 三级标题格式，LLM 输出 `### 一、标题` 形式。正则必须使用 `#{1,6}` 而非 `#` 或 `##` 才能匹配。
- **LLM 自由文本输出正则必须防御格式变异：** LLM 输出格式不稳定，正则必须：(1) 用 `\n+` 而非 `\n` 匹配标题和内容之间的空行；(2) 用 `\*{0,2}` 处理加粗标记 `**...**`；(3) 字符串清理顺序必须先删外层包裹再删内层，如先删 `**` 再删 `《》`；(4) 添加"标题在下一行"的回退正则。
- [2026-05-12] **replan 端点必须同步保存前端灵感数据：** 重新规划时前端表单数据（collected_info、inspiration_template）必须通过 replan 请求传到后端，在重置大纲字段之前保存。否则前端数据丢失、后端用旧数据生成。
- [2026-05-15] **防抖自动保存必须用 formStateRef 模式：** useCallback 闭包会捕获表单状态的旧值，导致防抖回调发送过期数据。正确做法：用 useRef 追踪最新表单状态，防抖回调从 ref 读取。triggerAutoSave 只依赖 onUpdate，不依赖表单状态字段。
- [2026-05-15] **后端 update models 必须保留 health_status：** 前端传来的 models 不包含服务端权威的 health_status/health_latency（这些是健康检查写入的），后端 update 时必须从 DB 中已有 models 读取并保留，否则覆盖健康检查结果。
- [2026-05-15] **get_system_prompt 必须处理 dict 格式默认值：** `DEFAULT_PROMPTS` 中 `chapter_content_generation`/`review`/`rewrite` 是 dict 格式 `{"system": ..., "user": ...}`。`get_system_prompt` 回退默认值时必须提取 "user" 部分，否则返回 dict 导致下游 `.format()` 报错 `'dict' object has no attribute 'format'`。

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-05-14] **React 派生状态与本地状态冲突：** 当组件同时有 prop 派生状态（如 initialReviewResult→reviewResult）和本地 SSE 设置的状态时，useEffect 同步两者会导致竞态条件。SSE done 事件设置本地状态后，onReviewComplete 更新父状态触发 prop 变化，useEffect 再次执行覆盖 SSE 结果。正确做法：用 ref 追踪 SSE 是否已设置结果，useEffect 仅在 SSE 未设置时从 prop 同步（处理异步加载 null→非null 场景）。
- [2026-05-14] **useMemo 缓存 map 函数产生的 prop：** mapReviewResult() 每次调用创建新对象引用，作为 prop 传递时导致子组件 useEffect 在每次父渲染时触发。应用 useMemo 缓存，依赖项为原始数据而非整个父状态。
- [2026-05-14] **模型配置统一 models 列表：** 取消 provider_type（single/coding_plan）的前端分支判断，所有配置统一遍历 config.models。旧 single 类型数据由后端 build_config_response 自动生成单元素 models 列表。InspirationPanel 不再按 provider_type 分支。
- [2026-05-14] **reasoning_effort 使用 OpenAI 标准 xhigh：** 最高思考强度值用 "xhigh" 而非 "max"，遵循 OpenAI API 标准。值为 None 或 "none" 时不传给 API。
- [2026-05-14] **后端重启才能加载代码变更：** 后端挂载了宿主机目录（volume mount），但 Python 进程已加载的模块不会自动更新。修改后端代码后需要 `docker compose restart backend` 才能生效。

## Do-Not-Repeat

- [2026-05-14] **JSON 解析不要用贪婪正则 \{[\s\S]*\}：** 此正则匹配从第一个 { 到最后一个 }，LLM 返回多对象或额外文本时匹配跨对象导致 JSON 解析失败。正确做法：逐层匹配花括号，找到第一个含审核字段（passed）的有效 JSON 对象。同时支持 markdown 代码块提取。
- [2026-05-14] **LLM 字段名不固定：** LLM 返回的 JSON 可能使用 feedback 而非 suggestions、problems 而非 issues 等变体。解析函数应兼容常见字段名变体，不要假设字段名固定。
