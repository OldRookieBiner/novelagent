# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-05-07

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** novelagent
- **Description:** AI 小说创作 Agent 系统 - 三 Agent 协作完成小说创作流程
- **LangGraph 工作流暂停机制：** 节点需要设置 `waiting_for_confirmation=True` 和 `confirmation_type` 才能让条件路由函数（如 `route_after_relations`）返回 `"wait_confirm"` 并路由到 `END`。否则工作流会继续执行后续节点。
- **SSE 流式完成信号：** `waiting` 事件表示工作流暂停，前端需要处理此事件作为当前阶段完成的信号，同时后端应在 `waiting` 后发送 `done` 事件确保前端收到完成通知。
- **LangGraph 图入口点问题：** `graph.astream_events(initial_state, config)` 始终从图的入口点（entry point）开始新执行，无论是否有检查点。不能用它来只执行图中某个特定节点。要执行特定节点，应使用子图（sub-graph）或直接调用节点函数。
- **build_initial_state 必须传 db 参数：** 调用 `build_initial_state` 时必须传入 `db=db` 参数，否则角色、关系、演变计划等数据不会被预加载，生成的章节内容会缺少人物设定和关系上下文。

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

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->
