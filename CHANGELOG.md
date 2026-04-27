# Changelog

All notable changes to this project will be documented in this file.

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
