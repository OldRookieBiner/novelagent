# ProjectCard 重设计 — 交接摘要

## 状态
设计已完成，计划已写好并经过两轮审查修复，等待执行。

## 设计决策
项目卡片从旧布局（内部4阶段标签+章节进度条+字数+日期）改为：
- **项目名 + 连载中/已完结标签**（is_completed 由后端计算：chapter_count>0 且 completed_chapters==chapter_count）
- **已写字数**（大号加粗）
- **当前章节**（workflow_state.current_chapter，新项目显示 "—"）
- **更新时间**（带时分）
- 保留继续+删除按钮

移除：内部Phase标签、进度条、章节比例、目标字数、AI处理中状态。

## 已审查修复的问题
1. is_completed 判断：用 `chapter_count>0 && completed_chapters==chapter_count` 而非 `progress_percentage===100`，防止新项目误判
2. 列表刷新：visibilitychange + useRef 避免 stale closure
3. handleDeleteProject：改为函数式 state 更新 `setProjects(prev => ...)`
4. chapterDisplay：用 `currentChapter > 0` 显式比较
5. 补充 API 端到端测试

## 执行计划
6个Task，详见 docs/superpowers/plans/2026-06-16-project-card-redesign.md

| Task | 内容 | 关键文件 |
|------|------|----------|
| 1 | 后端 schema + API + 测试 | schemas/project.py, api/projects.py, tests/test_project_detail.py |
| 2 | 前端类型定义 | types/index.ts |
| 3 | ProjectCard 重写 | components/common/ProjectCard.tsx |
| 4 | 骨架屏更新 | components/ui/skeleton.tsx |
| 5 | Home.tsx 刷新+state修复 | pages/Home.tsx, pages/__tests__/Home.test.tsx |
| 6 | 集成验证 | — |

## 视觉伴侣
brainstorm 服务器已停，session 数据在 .superpowers/brainstorm/ 下（已 gitignore）。
