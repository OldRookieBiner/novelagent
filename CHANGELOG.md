# Changelog

All notable changes to this project will be documented in this file.

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
