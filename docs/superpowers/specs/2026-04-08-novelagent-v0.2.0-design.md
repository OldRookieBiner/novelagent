# NovelAgent v0.2.0 设计文档

## 项目概述

**NovelAgent** - AI 小说创作 Web 应用，支持短/中篇小说（10万字以内）创作。

### 核心定位

- 从 CLI 转向 Web 应用
- 简化创作流程，降低使用门槛
- 保留 Agent 协作能力，提升交互体验

### 版本目标

| 版本 | 目标 |
|------|------|
| v0.1.x | CLI + 三 Agent 协作，验证可行性 |
| **v0.2.0** | Web 应用 + 简化流程 + LangGraph 重构 |

---

## 创作流程

### 简化版流程（v0.2.0）

```
信息收集 → 大纲 → Agent建议章节数 → 用户确认/调整 → 章节纲(一次性生成) → 正文 → 审核(可选)
```

### 对比 v0.1.x

| 环节 | v0.1.x | v0.2.0 |
|------|--------|--------|
| 层级 | 大纲→卷纲→单元纲→章节纲→正文 | 大纲→章节纲→正文 |
| 章节纲生成 | 逐单元生成 | 一次性生成所有 |
| 审核 | 强制，每次必审 | 可选，全程可开关 |
| 交互方式 | CLI 命令行 | Web 界面 |

---

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              React 18 + Vite                         │   │
│  │  shadcn/ui + Tailwind + Zustand + React Router       │   │
│  └────────────────────────┬────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────┘
                            │ HTTP/SSE
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 后端                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   认证层    │  │   API层     │  │  LangGraph  │         │
│  │Session+Cookie│  │  REST+SSE   │  │   Agent     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL                                │
│         用户 / 项目 / 大纲 / 章节 / 设置                      │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈详情

#### 前端

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | React | 18.x | UI 框架 |
| 构建工具 | Vite | 5.x | 快速构建 |
| UI 组件 | shadcn/ui | latest | 基于 Radix UI |
| 样式 | Tailwind CSS | 3.x | 原子化 CSS |
| 状态管理 | Zustand | 4.x | 轻量状态管理 |
| HTTP 请求 | fetch + hooks | - | 原生 + 封装 |
| 路由 | React Router | 6.x | 客户端路由 |
| 富文本编辑 | TipTap | 2.x | 可扩展编辑器 |

#### 后端

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | FastAPI | 0.109+ | 异步 Web 框架 |
| ORM | SQLAlchemy | 2.x | 数据库 ORM |
| 迁移 | Alembic | latest | 数据库迁移 |
| 认证 | Session + Cookie | - | 服务端会话 |
| 流式响应 | SSE | - | Server-Sent Events |
| Agent 框架 | LangGraph | latest | 状态图 Agent |

#### 基础设施

| 类别 | 技术 | 说明 |
|------|------|------|
| 数据库 | PostgreSQL 15+ | 主数据库 |
| 容器化 | Docker + Compose | 一键部署 |

---

## 功能模块

### 1. 用户认证

- 简单密码登录
- 无注册流程
- 默认账号密码（环境变量配置）
- Session + httpOnly Cookie

### 2. 项目管理

- 多项目支持
- 项目卡片列表（响应式，一行 3-4 个）
- 项目状态：大纲阶段 / 写作中 / 已完成 / 暂停
- 项目信息：
  - 名称
  - 当前阶段
  - 已完成章节 / 总章节
  - 总字数
  - 创建/更新时间

### 3. 大纲创作

#### 信息收集

- 对话式收集小说想法
- 必填信息：
  - 题材类型 (genre)
  - 核心主题 (theme)
  - 主角设定 (main_characters)
  - 世界设定 (world_setting)
  - 风格偏好 (style_preference)
- Agent 判断信息充足度
- 支持用户随时补充修改

#### 大纲生成

- 根据收集信息生成大纲
- 大纲格式：
  ```
  标题：[小说名称]
  概述：[200-300字故事概述]
  主要情节节点：
  1. [开篇事件]
  2. [关键转折点]
  ...
  N. [结局]
  ```
- 用户可修改大纲

#### 章节数建议

- Agent 根据大纲建议章节数
- 参考因素：
  - 情节节点数量
  - 风格节奏偏好
  - 每章合理字数（2000-3000字）
- 用户可确认或调整

#### 章节纲生成

- 一次性生成所有章节纲
- 章节纲格式：
  ```
  第X章：[章节名]
  场景：[发生地点]
  人物：[出场人物]
  情节：[本章主要情节，100-200字]
  冲突：[本章的冲突/矛盾]
  结局：[本章如何收尾/悬念]
  预计字数：[字数]
  ```
- 用户可修改章节纲

### 4. 正文写作

- 流式生成（SSE）
- 实时显示生成内容
- 支持暂停/继续
- 富文本编辑（TipTap）：
  - 粗体 / 斜体
  - 段落分隔
  - 撤销 / 重做
  - 字数统计
- 用户可手动编辑
- 用户可要求 Agent 重写

### 5. 审核（可选）

- 全程可开关
- 三种严格度：宽松 / 标准 / 严格
- 审核维度：
  - 一致性：人物名、地名、前后情节
  - 质量：文笔、节奏、逻辑
  - AI味：过于书面化、重复表达、缺乏细节
  - 规则：是否符合用户设定的风格
- 不通过则重写

### 6. 模型配置

- 界面选择模型：DeepSeek / OpenAI / 其他
- 界面配置 API Key
- 设置页面管理

---

## 页面结构

### 页面导航

```
/ → 首页（项目列表）
/project/:id → 项目详情
/project/:id/write → 写作页面
/project/:id/read/:chapterId → 阅读/审核
/settings → 设置（模型配置）
```

### 页面详情

#### 首页 - 项目列表

- 顶部导航栏：Logo + 用户下拉菜单
- 新建项目按钮
- 项目卡片网格（响应式）：
  - 项目名称 + 状态标签
  - 基本信息（阶段、章节、字数、时间）
  - 进度条
  - 操作按钮

#### 项目详情页

- 顶部：项目状态信息
- 左侧：章节列表
- 右侧：当前章节纲内容
- 操作：开始写作、编辑大纲

#### 写作页面

- 顶部：章节信息
- 主体：流式生成区域 / 富文本编辑器
- 底部：控制按钮（暂停、审核设置）

#### 阅读/审核页面

- 主体：章节正文显示
- 底部：章节导航（上一章/下一章）
- 审核按钮、编辑按钮

---

## 数据库设计

### ER 图

```
users ──┬──< projects ──┬──< outlines
        │               │
        │               └──< chapter_outlines ──< chapters
        │
        └──< settings
```

### 表结构

#### users（用户表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| username | VARCHAR(50) | 用户名，唯一 |
| password_hash | VARCHAR(255) | 密码哈希 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### projects（项目表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| user_id | INTEGER | 外键，关联 users |
| name | VARCHAR(100) | 项目名称 |
| stage | VARCHAR(50) | 当前阶段 |
| target_words | INTEGER | 目标字数 |
| total_words | INTEGER | 已完成字数 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### outlines（大纲表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| project_id | INTEGER | 外键，关联 projects |
| title | VARCHAR(200) | 小说标题 |
| summary | TEXT | 故事概述 |
| plot_points | JSONB | 情节节点列表 |
| collected_info | JSONB | 收集的信息 |
| confirmed | BOOLEAN | 是否已确认 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### chapter_outlines（章节纲表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| project_id | INTEGER | 外键，关联 projects |
| chapter_number | INTEGER | 章节序号 |
| title | VARCHAR(200) | 章节名 |
| scene | VARCHAR(500) | 场景 |
| characters | TEXT | 出场人物 |
| plot | TEXT | 情节 |
| conflict | TEXT | 冲突 |
| ending | TEXT | 结局 |
| target_words | INTEGER | 预计字数 |
| confirmed | BOOLEAN | 是否已确认 |
| created_at | TIMESTAMP | 创建时间 |

#### chapters（章节正文表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| chapter_outline_id | INTEGER | 外键，关联 chapter_outlines |
| content | TEXT | 章节正文 |
| word_count | INTEGER | 实际字数 |
| review_passed | BOOLEAN | 审核是否通过 |
| review_feedback | TEXT | 审核反馈 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### settings（用户设置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| user_id | INTEGER | 外键，关联 users |
| model_provider | VARCHAR(50) | 模型提供商 |
| model_name | VARCHAR(100) | 模型名称 |
| api_key_encrypted | TEXT | 加密的 API Key |
| review_enabled | BOOLEAN | 是否启用审核 |
| review_strictness | VARCHAR(20) | 审核严格度 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## API 设计

### 认证 API

```
POST /api/auth/login     # 登录
POST /api/auth/logout    # 登出
GET  /api/auth/me        # 获取当前用户
```

### 项目 API

```
GET    /api/projects           # 获取项目列表
POST   /api/projects           # 创建项目
GET    /api/projects/:id       # 获取项目详情
PUT    /api/projects/:id       # 更新项目
DELETE /api/projects/:id       # 删除项目
```

### 大纲 API

```
GET    /api/projects/:id/outline         # 获取大纲
POST   /api/projects/:id/outline         # 生成大纲
PUT    /api/projects/:id/outline         # 修改大纲
POST   /api/projects/:id/outline/confirm # 确认大纲
```

### 章节纲 API

```
GET    /api/projects/:id/chapter-outlines           # 获取所有章节纲
POST   /api/projects/:id/chapter-outlines           # 生成章节纲
PUT    /api/projects/:id/chapter-outlines/:num      # 修改章节纲
POST   /api/projects/:id/chapter-outlines/confirm   # 确认章节纲
```

### 章节 API

```
GET    /api/projects/:id/chapters/:num       # 获取章节
POST   /api/projects/:id/chapters/:num       # 生成章节（SSE）
PUT    /api/projects/:id/chapters/:num       # 更新章节
POST   /api/projects/:id/chapters/:num/review # 审核章节
```

### 设置 API

```
GET  /api/settings     # 获取设置
PUT  /api/settings     # 更新设置
```

---

## LangGraph Agent 设计

### 状态图

```
                    ┌─────────────────┐
                    │                 │
                    ▼                 │
┌──────────┐    ┌──────────┐    ┌──────────┐
│ 信息收集 │───▶│ 大纲生成 │───▶│ 大纲确认 │
└──────────┘    └──────────┘    └──────────┘
                                     │
                                     ▼
                               ┌──────────┐
                               │ 章节数建议│
                               └──────────┘
                                     │
                                     ▼
                               ┌──────────┐
                               │ 章节纲生成│
                               └──────────┘
                                     │
                                     ▼
                               ┌──────────┐
                               │ 章节纲确认│
                               └──────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                ▼                │
                    │          ┌──────────┐          │
                    │          │ 章节写作 │          │
                    │          └──────────┘          │
                    │                │                │
                    │                ▼                │
                    │          ┌──────────┐          │
                    │          │   审核   │──通过───▶│───▶ 下一章
                    │          └──────────┘          │
                    │                │ 不通过         │
                    └────────────────┴────────────────┘
```

### 节点定义

| 节点 | 功能 | 输入 | 输出 |
|------|------|------|------|
| 信息收集 | 对话收集用户想法 | 用户消息 | 更新 collected_info |
| 大纲生成 | 根据信息生成大纲 | collected_info | outline |
| 大纲确认 | 等待用户确认 | outline | confirmed |
| 章节数建议 | 建议章节数量 | outline | chapter_count |
| 章节纲生成 | 生成所有章节纲 | outline, chapter_count | chapter_outlines[] |
| 章节纲确认 | 等待用户确认 | chapter_outlines[] | confirmed |
| 章节写作 | 生成章节正文 | chapter_outline, context | chapter_content |
| 审核 | 检查章节质量 | chapter_content | passed, feedback |

### 状态结构

```python
class NovelState(TypedDict):
    # 项目信息
    project_id: str
    stage: str

    # 收集的信息
    collected_info: dict

    # 大纲
    outline: dict
    outline_confirmed: bool

    # 章节纲
    chapter_count: int
    chapter_outlines: list
    chapter_outlines_confirmed: bool

    # 当前章节
    current_chapter: int
    chapter_content: str

    # 审核
    review_enabled: bool
    review_passed: bool
    review_feedback: str

    # 对话历史
    messages: list
```

---

## 部署方案

### Docker Compose 结构

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
    depends_on:
      - db

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=novelagent
      - POSTGRES_USER=...
      - POSTGRES_PASSWORD=...

volumes:
  postgres_data:
```

### 环境变量

```bash
# 数据库
DATABASE_URL=postgresql://user:password@db:5432/novelagent

# 认证
SECRET_KEY=your-secret-key
DEFAULT_USERNAME=admin
DEFAULT_PASSWORD=your-password

# 模型（可选默认值）
DEFAULT_MODEL_PROVIDER=deepseek
DEFAULT_API_KEY=your-api-key
```

---

## 验收标准

### 功能验收

1. ✅ 用户可登录系统
2. ✅ 用户可创建/删除项目
3. ✅ 用户可与 Agent 对话收集信息
4. ✅ Agent 可生成大纲
5. ✅ Agent 可建议章节数，用户可调整
6. ✅ Agent 可一次性生成所有章节纲
7. ✅ 用户可编辑大纲和章节纲
8. ✅ Agent 可流式生成章节正文
9. ✅ 用户可编辑章节正文
10. ✅ 用户可开启/关闭审核
11. ✅ 审核不通过时可重写
12. ✅ 用户可配置模型和 API Key
13. ✅ 支持多模型切换

### 技术验收

1. ✅ Docker Compose 一键启动
2. ✅ 数据库迁移正常
3. ✅ 前后端分离部署
4. ✅ 流式响应正常
5. ✅ Session 认证正常

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 回复不稳定 | Prompt 明确格式，重试机制 |
| 流式响应中断 | 断点续传，保存已生成内容 |
| API Key 安全 | 前端不暴露，后端加密存储 |
| 数据库性能 | 合理索引，分页查询 |
| 并发写入 | 乐观锁，冲突检测 |

---

## 版本规划

| 版本 | 目标 | 预计 |
|------|------|------|
| v0.2.0 | Web 应用基础版 | 当前 |
| v0.3.0 | 导出功能、阅读体验优化 | 后续 |
| v0.4.0 | 向量数据库、一致性检查 | 后续 |
| v1.0.0 | 多用户、云端部署 | 后续 |