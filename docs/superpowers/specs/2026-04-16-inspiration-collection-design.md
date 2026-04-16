# v0.5.0 灵感采集设计文档

> 创建日期: 2026-04-16
> 版本: v0.5.0
> 功能: 小说生成流程优化 - 从能用到好用

---

## 概述

将"信息收集"升级为"灵感采集"，简化流程（6步→5步），提供结构化的灵感选项表单和 Markdown 模板编辑功能，提升小说创作的自定义程度和用户体验。

---

## 目标

- **流程简化**: 将章节数合并到灵感采集，减少步骤
- **结构化输入**: 提供预设选项，降低用户思考成本
- **灵活扩展**: Markdown 模板支持自由编辑，满足深度定制需求

---

## 流程变化

### 原流程 (v0.4.0)

```
信息收集 → 大纲生成 → 章节数 → 章节纲 → 写作 → 审核
```

### 新流程 (v0.5.0)

```
灵感采集 → 大纲生成 → 章节纲 → 写作 → 审核
```

| 原步骤 | 新步骤 | 变化 |
|--------|--------|------|
| 信息收集 | 灵感采集 | 重命名 + 功能增强 |
| 大纲生成 | 大纲生成 | 无变化 |
| 章节数 | 合并到灵感采集 | 移除独立步骤 |
| 章节纲 | 章节纲 | 无变化 |
| 写作 | 写作 | 无变化 |
| 审核 | 审核 | 无变化 |

---

## 灵感选项设计

### 选项列表

| 字段 | 必填 | 输入方式 | 预设选项 |
|------|------|----------|----------|
| 小说类型 | ✅ | 下拉单选 | 玄幻、科幻、都市、言情、悬疑、历史 |
| 小说篇幅 | ✅ | 下拉预设 + 自定义输入 | 短篇(10-20章)、中篇(30-50章)、长篇(50-100章)、超长篇(100+) |
| 核心主题 | ✅ | 下拉单选 | 复仇、成长、逆袭、爱情、探险、权谋 |
| 世界观设定 | 可选 | 下拉 + 自定义输入 | 修仙体系、魔法世界、赛博朋克、现代社会、古代王朝 |
| 主角设定 | 可选 | 下拉 + 自定义输入 | 少年天才、穿越者、重生者、草根逆袭、普通人 |
| 风格偏好 | 可选 | 下拉单选 | 轻松幽默、热血激昂、细腻唯美、暗黑深沉、紧张刺激 |

### 预设选项详细定义

```typescript
// 灵感选项配置
export const INSPIRATION_OPTIONS = {
  novelTypes: [
    { value: 'xuanhuan', label: '玄幻' },
    { value: 'kehuan', label: '科幻' },
    { value: 'dushi', label: '都市' },
    { value: 'yanqing', label: '言情' },
    { value: 'xuanyi', label: '悬疑' },
    { value: 'lishi', label: '历史' },
  ],

  novelLength: [
    { value: 'short', label: '短篇', chapters: '10-20' },
    { value: 'medium', label: '中篇', chapters: '30-50' },
    { value: 'long', label: '长篇', chapters: '50-100' },
    { value: 'extra_long', label: '超长篇', chapters: '100+' },
    { value: 'custom', label: '自定义' },
  ],

  coreThemes: [
    { value: 'revenge', label: '复仇' },
    { value: 'growth', label: '成长' },
    { value: 'counterattack', label: '逆袭' },
    { value: 'love', label: '爱情' },
    { value: 'adventure', label: '探险' },
    { value: 'power_struggle', label: '权谋' },
  ],

  worldSettings: [
    { value: 'cultivation', label: '修仙体系' },
    { value: 'magic', label: '魔法世界' },
    { value: 'cyberpunk', label: '赛博朋克' },
    { value: 'modern', label: '现代社会' },
    { value: 'ancient', label: '古代王朝' },
    { value: 'custom', label: '自定义' },
  ],

  protagonistTypes: [
    { value: 'genius', label: '少年天才' },
    { value: 'transmigrator', label: '穿越者' },
    { value: 'reborn', label: '重生者' },
    { value: 'underdog', label: '草根逆袭' },
    { value: 'ordinary', label: '普通人' },
    { value: 'custom', label: '自定义' },
  ],

  stylePreferences: [
    { value: 'humorous', label: '轻松幽默' },
    { value: 'passionate', label: '热血激昂' },
    { value: 'aesthetic', label: '细腻唯美' },
    { value: 'dark', label: '暗黑深沉' },
    { value: 'tense', label: '紧张刺激' },
  ],
}
```

---

## Markdown 模板设计

### 模板生成逻辑

根据用户选择的灵感选项，生成结构化的 Markdown 模板：

```markdown
# 小说创作灵感

## 基本信息

- **小说类型**：{novelType}
- **小说篇幅**：{novelLength}
- **核心主题**：{coreTheme}

## 世界设定

- **世界观**：{worldSetting}

## 人物设定

- **主角**：{protagonist}

## 风格

- **风格偏好**：{stylePreference}

## 补充灵感

> 在下方添加更多灵感细节...

- 

- 

```

### 示例：用户选择玄幻题材

```markdown
# 小说创作灵感

## 基本信息

- **小说类型**：玄幻
- **小说篇幅**：中篇(30-50章)
- **核心主题**：成长逆袭

## 世界设定

- **世界观**：修仙体系

## 人物设定

- **主角**：少年天才

## 风格

- **风格偏好**：热血激昂

## 补充灵感

> 在下方添加更多灵感细节...

-

-

```

---

## UI 设计

### 页面一：灵感选项表单

```
┌─────────────────────────────────────────────────────┐
│  灵感采集                                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  小说类型 *    [请选择 ▼]                           │
│  小说篇幅 *    [请选择 ▼]  自定义: [  ] 章          │
│  核心主题 *    [请选择 ▼]                           │
│  世界观设定     [请选择 ▼]  自定义: [        ]      │
│  主角设定       [请选择 ▼]  自定义: [        ]      │
│  风格偏好       [请选择 ▼]                          │
│                                                     │
│                    [生成灵感模板]                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 页面二：灵感模板编辑

```
┌─────────────────────────────────────────────────────┐
│  灵感模板                                            │
├─────────────────────────────────────────────────────┤
│  基本信息                                            │
│  ┌───────────┬───────────┬───────────┐              │
│  │ 小说类型  │ 小说篇幅  │ 核心主题  │              │
│  │ [玄幻 ▼] │ [中篇 ▼] │ [成长 ▼] │              │
│  └───────────┴───────────┴───────────┘              │
│  ┌───────────┬───────────┬───────────┐              │
│  │ 世界观    │ 主角设定  │ 风格偏好  │              │
│  │ [修仙 ▼] │ [天才 ▼] │ [热血 ▼] │              │
│  └───────────┴───────────┴───────────┘              │
├─────────────────────────────────────────────────────┤
│  补充灵感（支持 Markdown 格式）                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ # 小说创作灵感                                │   │
│  │ ## 基本信息                                  │   │
│  │ - **小说类型**：玄幻                         │   │
│  │ ...                                         │   │
│  │ ## 补充灵感                                  │   │
│  │ - 金手指：神秘玉佩                           │   │
│  │ - 反派：宗门长老之子                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│         [上一步]          [确认，生成大纲]          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 数据结构

### 前端类型定义

```typescript
// 灵感数据结构
export interface InspirationData {
  novelType: string
  novelLength: string
  customChapterCount?: number  // 自定义章节数
  coreTheme: string
  worldSetting?: string
  customWorldSetting?: string
  protagonist?: string
  customProtagonist?: string
  stylePreference?: string
}

// 灵感模板
export interface InspirationTemplate {
  rawMarkdown: string  // 完整的 Markdown 内容
}

// 提交给大纲生成的完整数据
export interface OutlineGenerationInput {
  inspiration: InspirationData
  template: string  // Markdown 模板内容
}
```

### 后端 Schema

```python
# backend/app/schemas/inspiration.py

from pydantic import BaseModel
from typing import Optional

class InspirationData(BaseModel):
    novel_type: str
    novel_length: str
    custom_chapter_count: Optional[int] = None
    core_theme: str
    world_setting: Optional[str] = None
    custom_world_setting: Optional[str] = None
    protagonist: Optional[str] = None
    custom_protagonist: Optional[str] = None
    style_preference: Optional[str] = None

class InspirationTemplate(BaseModel):
    """灵感模板"""
    content: str  # Markdown 内容

class OutlineFromInspiration(BaseModel):
    """从灵感生成大纲的请求"""
    inspiration: InspirationData
    template: str
```

---

## 实现范围

### 本次实现

- [ ] 灵感选项表单组件
- [ ] Markdown 模板生成函数
- [ ] 灵感模板编辑组件
- [ ] 灵感采集页面整合
- [ ] 步骤导航栏更新（6步→5步）
- [ ] 后端 API 调整
- [ ] 大纲生成智能体适配

### 暂不实现

- 灵感模板保存/加载
- 灵感选项的动态扩展
- 灵感模板历史版本

---

## 验收标准

- [ ] 灵感采集表单正确显示 6 个选项
- [ ] 必填项验证正常
- [ ] 小说篇幅支持预设选择和自定义输入
- [ ] 世界观/主角设定支持选择和自定义
- [ ] 点击"生成灵感模板"正确生成 Markdown
- [ ] 上半部分表单与下半部分 Markdown 同步
- [ ] 用户可自由编辑 Markdown 内容
- [ ] 确认后正确传递给大纲生成智能体
- [ ] 步骤导航栏显示 5 个步骤
- [ ] 现有工作流功能不受影响