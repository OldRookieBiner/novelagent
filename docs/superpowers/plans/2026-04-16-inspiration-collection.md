# v0.5.0 灵感采集实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现灵感采集功能，简化流程（6步→5步），提供结构化选项表单和 Markdown 模板编辑。

**Architecture:** 前端新增灵感采集组件，修改步骤导航配置；后端调整 API 和大纲生成智能体。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, FastAPI, Pydantic

---

## 文件结构

**新增文件：**
```
frontend/src/components/project/InspirationForm.tsx      # 灵感选项表单
frontend/src/components/project/InspirationEditor.tsx   # 灵感模板编辑器
frontend/src/lib/inspiration.ts                          # 灵感选项配置和模板生成
```

**修改文件：**
```
frontend/src/components/project/StepNavigation.tsx      # 步骤数改为5步
frontend/src/pages/ProjectDetail.tsx                    # 集成灵感采集
frontend/src/types/index.ts                             # 新增类型定义
backend/app/schemas/outline.py                          # 新增灵感相关 schema
backend/app/api/outline.py                              # 调整大纲生成 API
backend/app/agents/nodes/outline_generation.py          # 适配新输入格式
```

---

## Task 1: 灵感选项配置和工具函数

**Files:**
- Create: `frontend/src/lib/inspiration.ts`

**Step 1: 创建灵感选项配置**

```typescript
// frontend/src/lib/inspiration.ts

export interface SelectOption {
  value: string
  label: string
  chapters?: string  // 仅用于篇幅选项
}

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

// 获取选项标签
export function getOptionLabel(options: SelectOption[], value: string): string {
  return options.find(o => o.value === value)?.label || value
}
```

**Step 2: 创建模板生成函数**

```typescript
// 生成 Markdown 模板
export function generateInspirationTemplate(data: InspirationData): string {
  const novelType = getOptionLabel(INSPIRATION_OPTIONS.novelTypes, data.novelType)
  const novelLength = data.customChapterCount 
    ? `${data.customChapterCount}章` 
    : getOptionLabel(INSPIRATION_OPTIONS.novelLength, data.novelLength)
  const coreTheme = getOptionLabel(INSPIRATION_OPTIONS.coreThemes, data.coreTheme)
  const worldSetting = data.customWorldSetting || getOptionLabel(INSPIRATION_OPTIONS.worldSettings, data.worldSetting || '')
  const protagonist = data.customProtagonist || getOptionLabel(INSPIRATION_OPTIONS.protagonistTypes, data.protagonist || '')
  const style = getOptionLabel(INSPIRATION_OPTIONS.stylePreferences, data.stylePreference || '')

  return `# 小说创作灵感

## 基本信息

- **小说类型**：${novelType}
- **小说篇幅**：${novelLength}
- **核心主题**：${coreTheme}

## 世界设定

- **世界观**：${worldSetting || '未设置'}

## 人物设定

- **主角**：${protagonist || '未设置'}

## 风格

- **风格偏好**：${style || '未设置'}

## 补充灵感

> 在下方添加更多灵感细节...

-

-

`
}
```

---

## Task 2: 类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: 添加灵感相关类型**

```typescript
// ==================== Inspiration Types ====================

export interface InspirationData {
  novelType: string
  novelLength: string
  customChapterCount?: number
  coreTheme: string
  worldSetting?: string
  customWorldSetting?: string
  protagonist?: string
  customProtagonist?: string
  stylePreference?: string
}

export interface InspirationTemplate {
  content: string
}
```

---

## Task 3: 灵感选项表单组件

**Files:**
- Create: `frontend/src/components/project/InspirationForm.tsx`

**Step 1: 创建表单组件**

```tsx
// frontend/src/components/project/InspirationForm.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { INSPIRATION_OPTIONS, type InspirationData } from '@/lib/inspiration'

interface InspirationFormProps {
  initialData?: Partial<InspirationData>
  onSubmit: (data: InspirationData) => void
}

export default function InspirationForm({ initialData, onSubmit }: InspirationFormProps) {
  const [novelType, setNovelType] = useState(initialData?.novelType || '')
  const [novelLength, setNovelLength] = useState(initialData?.novelLength || '')
  const [customChapterCount, setCustomChapterCount] = useState<number | undefined>(initialData?.customChapterCount)
  const [coreTheme, setCoreTheme] = useState(initialData?.coreTheme || '')
  const [worldSetting, setWorldSetting] = useState(initialData?.worldSetting || '')
  const [customWorldSetting, setCustomWorldSetting] = useState(initialData?.customWorldSetting || '')
  const [protagonist, setProtagonist] = useState(initialData?.protagonist || '')
  const [customProtagonist, setCustomProtagonist] = useState(initialData?.customProtagonist || '')
  const [stylePreference, setStylePreference] = useState(initialData?.stylePreference || '')

  const [errors, setErrors] = useState<Record<string, string>>({})

  const handleSubmit = () => {
    // 验证必填项
    const newErrors: Record<string, string> = {}
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!novelLength) newErrors.novelLength = '请选择小说篇幅'
    if (!coreTheme) newErrors.coreTheme = '请选择核心主题'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    onSubmit({
      novelType,
      novelLength,
      customChapterCount,
      coreTheme,
      worldSetting,
      customWorldSetting,
      protagonist,
      customProtagonist,
      stylePreference,
    })
  }

  const showCustomChapter = novelLength === 'custom'
  const showCustomWorld = worldSetting === 'custom'
  const showCustomProtagonist = protagonist === 'custom'

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        {/* 小说类型 */}
        <div>
          <label className="block text-sm font-medium mb-1">
            小说类型 <span className="text-red-500">*</span>
          </label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={novelType}
            onChange={(e) => setNovelType(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.novelTypes.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {errors.novelType && <p className="text-red-500 text-xs mt-1">{errors.novelType}</p>}
        </div>

        {/* 小说篇幅 */}
        <div>
          <label className="block text-sm font-medium mb-1">
            小说篇幅 <span className="text-red-500">*</span>
          </label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={novelLength}
            onChange={(e) => setNovelLength(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.novelLength.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}{opt.chapters ? `(${opt.chapters}章)` : ''}
              </option>
            ))}
          </select>
          {errors.novelLength && <p className="text-red-500 text-xs mt-1">{errors.novelLength}</p>}
        </div>

        {/* 自定义章节数 */}
        {showCustomChapter && (
          <div>
            <label className="block text-sm font-medium mb-1">自定义章节数</label>
            <input
              type="number"
              className="w-full h-10 px-3 rounded-md border border-input bg-background"
              value={customChapterCount || ''}
              onChange={(e) => setCustomChapterCount(parseInt(e.target.value) || undefined)}
              placeholder="输入章节数"
            />
          </div>
        )}

        {/* 核心主题 */}
        <div>
          <label className="block text-sm font-medium mb-1">
            核心主题 <span className="text-red-500">*</span>
          </label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={coreTheme}
            onChange={(e) => setCoreTheme(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.coreThemes.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {errors.coreTheme && <p className="text-red-500 text-xs mt-1">{errors.coreTheme}</p>}
        </div>

        {/* 世界观设定 */}
        <div>
          <label className="block text-sm font-medium mb-1">世界观设定</label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={worldSetting}
            onChange={(e) => setWorldSetting(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.worldSettings.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* 自定义世界观 */}
        {showCustomWorld && (
          <div>
            <label className="block text-sm font-medium mb-1">自定义世界观</label>
            <input
              type="text"
              className="w-full h-10 px-3 rounded-md border border-input bg-background"
              value={customWorldSetting || ''}
              onChange={(e) => setCustomWorldSetting(e.target.value)}
              placeholder="输入世界观设定"
            />
          </div>
        )}

        {/* 主角设定 */}
        <div>
          <label className="block text-sm font-medium mb-1">主角设定</label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={protagonist}
            onChange={(e) => setProtagonist(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.protagonistTypes.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* 自定义主角 */}
        {showCustomProtagonist && (
          <div>
            <label className="block text-sm font-medium mb-1">自定义主角</label>
            <input
              type="text"
              className="w-full h-10 px-3 rounded-md border border-input bg-background"
              value={customProtagonist || ''}
              onChange={(e) => setCustomProtagonist(e.target.value)}
              placeholder="输入主角设定"
            />
          </div>
        )}

        {/* 风格偏好 */}
        <div>
          <label className="block text-sm font-medium mb-1">风格偏好</label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={stylePreference}
            onChange={(e) => setStylePreference(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.stylePreferences.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSubmit}>生成灵感模板</Button>
      </div>
    </div>
  )
}
```

---

## Task 4: 灵感模板编辑器组件

**Files:**
- Create: `frontend/src/components/project/InspirationEditor.tsx`

**Step 1: 创建编辑器组件**

```tsx
// frontend/src/components/project/InspirationEditor.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { INSPIRATION_OPTIONS, getOptionLabel, generateInspirationTemplate, type InspirationData } from '@/lib/inspiration'

interface InspirationEditorProps {
  data: InspirationData
  template: string
  onDataChange: (data: InspirationData) => void
  onTemplateChange: (template: string) => void
  onConfirm: () => void
  onBack: () => void
}

export default function InspirationEditor({
  data,
  template,
  onDataChange,
  onTemplateChange,
  onConfirm,
  onBack,
}: InspirationEditorProps) {
  return (
    <div className="space-y-4">
      {/* 上半部分：表单区域 */}
      <div className="p-4 border rounded-lg bg-gray-50">
        <h4 className="text-sm font-medium text-gray-700 mb-3">基本信息</h4>
        <div className="grid grid-cols-3 gap-4">
          {/* 小说类型 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">小说类型</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.novelType}
              onChange={(e) => {
                const newData = { ...data, novelType: e.target.value }
                onDataChange(newData)
                onTemplateChange(generateInspirationTemplate(newData))
              }}
            >
              {INSPIRATION_OPTIONS.novelTypes.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* 小说篇幅 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">小说篇幅</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.novelLength}
              onChange={(e) => {
                const newData = { ...data, novelLength: e.target.value }
                onDataChange(newData)
                onTemplateChange(generateInspirationTemplate(newData))
              }}
            >
              {INSPIRATION_OPTIONS.novelLength.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}{opt.chapters ? `(${opt.chapters}章)` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* 核心主题 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">核心主题</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.coreTheme}
              onChange={(e) => {
                const newData = { ...data, coreTheme: e.target.value }
                onDataChange(newData)
                onTemplateChange(generateInspirationTemplate(newData))
              }}
            >
              {INSPIRATION_OPTIONS.coreThemes.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-4">
          {/* 世界观 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">世界观设定</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.worldSetting}
              onChange={(e) => {
                const newData = { ...data, worldSetting: e.target.value }
                onDataChange(newData)
                onTemplateChange(generateInspirationTemplate(newData))
              }}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.worldSettings.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* 主角设定 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">主角设定</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.protagonist}
              onChange={(e) => {
                const newData = { ...data, protagonist: e.target.value }
                onDataChange(newData)
                onTemplateChange(generateInspirationTemplate(newData))
              }}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.protagonistTypes.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* 风格偏好 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">风格偏好</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.stylePreference}
              onChange={(e) => {
                const newData = { ...data, stylePreference: e.target.value }
                onDataChange(newData)
                onTemplateChange(generateInspirationTemplate(newData))
              }}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.stylePreferences.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 下半部分：Markdown 编辑区 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium text-gray-700">补充灵感</h4>
          <span className="text-xs text-gray-400">支持 Markdown 格式，可自由编辑</span>
        </div>
        <Textarea
          className="min-h-[300px] font-mono text-sm"
          value={template}
          onChange={(e) => onTemplateChange(e.target.value)}
        />
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3">
        <Button variant="outline" onClick={onBack}>上一步</Button>
        <Button onClick={onConfirm}>确认，生成大纲</Button>
      </div>
    </div>
  )
}
```

---

## Task 5: 步骤导航栏更新

**Files:**
- Modify: `frontend/src/components/project/StepNavigation.tsx`

**Step 1: 更新 STEPS 配置**

```typescript
// 将 6 步改为 5 步，更新步骤名称
export const STEPS: StepConfig[] = [
  { index: 0, name: '灵感采集', stages: ['inspiration_collecting'] },
  { index: 1, name: '大纲生成', stages: ['outline_generating', 'outline_confirming'] },
  { index: 2, name: '章节纲', stages: ['chapter_outlines_generating', 'chapter_outlines_confirming'] },
  { index: 3, name: '写作', stages: ['chapter_writing'] },
  { index: 4, name: '审核', stages: ['chapter_reviewing', 'completed'] },
]
```

**Step 2: 更新 getStepStatus 和 getCurrentStepIndex**

调整 stageOrder 和步骤映射。

---

## Task 6: ProjectDetail 页面集成

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

**Step 1: 添加灵感采集状态**

```typescript
// 新增状态
const [inspirationData, setInspirationData] = useState<InspirationData | null>(null)
const [inspirationTemplate, setInspirationTemplate] = useState('')
const [showEditor, setShowEditor] = useState(false)

// 判断是否显示灵感采集
const showInspirationCollection = project.stage === 'collecting_info' || project.stage === 'inspiration_collecting'
```

**Step 2: 渲染灵感采集组件**

```tsx
{showInspirationCollection && !showEditor && (
  <InspirationForm
    initialData={outline?.collected_info as Partial<InspirationData>}
    onSubmit={(data) => {
      setInspirationData(data)
      setInspirationTemplate(generateInspirationTemplate(data))
      setShowEditor(true)
    }}
  />
)}

{showInspirationCollection && showEditor && inspirationData && (
  <InspirationEditor
    data={inspirationData}
    template={inspirationTemplate}
    onDataChange={setInspirationData}
    onTemplateChange={setInspirationTemplate}
    onConfirm={handleConfirmInspiration}
    onBack={() => setShowEditor(false)}
  />
)}
```

**Step 3: 实现确认灵感逻辑**

```typescript
const handleConfirmInspiration = async () => {
  if (!inspirationData || !id) return

  try {
    // 保存灵感数据并触发生成大纲
    await outlineApi.update(parseInt(id), {
      collected_info: inspirationData,
      inspiration_template: inspirationTemplate,
    })
    // 更新 stage
    await projectsApi.update(parseInt(id), { stage: 'outline_generating' })
    // 刷新数据
    // ...
  } catch (err) {
    console.error('Failed to confirm inspiration:', err)
  }
}
```

---

## Task 7: 后端 Schema 更新

**Files:**
- Modify: `backend/app/schemas/outline.py`

**Step 1: 添加灵感相关字段**

```python
# 在 OutlineUpdate 或相关 schema 中添加
class OutlineUpdate(BaseModel):
    # ... existing fields
    collected_info: Optional[dict] = None
    inspiration_template: Optional[str] = None
```

---

## Task 8: 后端 API 和智能体适配

**Files:**
- Modify: `backend/app/api/outline.py`
- Modify: `backend/app/agents/nodes/outline_generation.py`

**Step 1: 更新大纲生成逻辑**

将 `inspiration_template` 传递给大纲生成智能体作为 prompt 的一部分。

---

## Task 9: 测试验证

**Files:**
- 无新增文件

**Step 1: 功能测试**

1. 创建新项目
2. 填写灵感选项表单
3. 验证 Markdown 模板生成
4. 编辑模板内容
5. 确认后验证大纲生成
6. 检查步骤导航栏显示 5 步

**Step 2: 边缘情况测试**

- 自定义章节数
- 自定义世界观/主角
- 必填项验证
- 上一步/下一步导航

---

## 验收清单

- [ ] 灵感选项表单正确显示 6 个选项
- [ ] 必填项验证正常（类型、篇幅、主题）
- [ ] 小说篇幅支持预设和自定义
- [ ] 世界观/主角支持选择和自定义
- [ ] 生成 Markdown 模板正确
- [ ] 上半部分表单与下半部分 Markdown 同步
- [ ] 用户可自由编辑 Markdown
- [ ] 确认后正确传递给大纲生成
- [ ] 步骤导航栏显示 5 个步骤
- [ ] 前端构建无 TypeScript 错误
- [ ] 后端测试通过