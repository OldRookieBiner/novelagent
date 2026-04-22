# 灵感采集表单优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化灵感采集表单，新增 4 个配置项（目标读者、每章字数、叙事视角、金手指），并改进 UI 交互（卡片选择、标签选择）。

**Architecture:** 前端表单重构，保持现有数据流，扩展类型定义和选项配置。使用卡片 UI 呈现必填项，标签 UI 呈现选填项。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, shadcn/ui

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/types/index.ts` | 修改 | 扩展 CollectedInfo 类型，新增字段 |
| `frontend/src/lib/inspiration.ts` | 修改 | 扩展 InspirationData 类型，新增选项配置 |
| `frontend/src/components/project/InspirationForm.tsx` | 重写 | 完整重构 UI：卡片选择 + 标签选择 + 下拉框 |
| `frontend/src/components/project/InspirationEditor.tsx` | 修改 | 支持新增字段显示和编辑 |

---

### Task 1: 扩展类型定义

**Files:**
- Modify: `frontend/src/types/index.ts:61-73`

- [ ] **Step 1: 更新 CollectedInfo 类型**

在 `frontend/src/types/index.ts` 中，找到 `CollectedInfo` 接口（第 61-73 行），添加新字段：

```typescript
export interface CollectedInfo {
  novelType?: string;
  novelLength?: string;
  customChapterCount?: number;
  targetWords?: string;
  customTargetWords?: number;
  coreTheme?: string;
  worldSetting?: string;
  customWorldSetting?: string;
  protagonist?: string;
  customProtagonist?: string;
  stylePreference?: string;
  // 新增字段
  targetReader?: string;        // 'male' | 'female'
  wordsPerChapter?: string;     // 每章字数
  customWordsPerChapter?: number;
  narrative?: string;           // 'first' | 'third'
  goldFinger?: string;          // 金手指类型
  customGoldFinger?: string;
}
```

- [ ] **Step 2: 验证类型修改**

运行 TypeScript 编译检查：
```bash
cd /opt/project/novelagent/frontend && npm run build 2>&1 | head -20
```
预期：可能有类型错误（因为其他文件尚未更新），但类型定义本身应正确。

- [ ] **Step 3: 提交类型修改**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add new inspiration fields to CollectedInfo

- Add targetReader (male/female)
- Add wordsPerChapter and customWordsPerChapter
- Add narrative perspective (first/third person)
- Add goldFinger and customGoldFinger"
```

---

### Task 2: 扩展灵感配置

**Files:**
- Modify: `frontend/src/lib/inspiration.ts`

- [ ] **Step 1: 更新 InspirationData 类型**

在 `frontend/src/lib/inspiration.ts` 中，更新 `InspirationData` 接口（第 10-22 行）：

```typescript
export interface InspirationData {
  novelType: string
  novelLength: string
  customChapterCount?: number
  targetWords: string
  customTargetWords?: number
  coreTheme: string
  worldSetting?: string
  customWorldSetting?: string
  protagonist?: string
  customProtagonist?: string
  stylePreference?: string
  // 新增字段
  targetReader: string        // 'male' | 'female'
  wordsPerChapter: string     // 每章字数
  customWordsPerChapter?: number
  narrative?: string          // 'first' | 'third'
  goldFinger?: string         // 金手指类型
  customGoldFinger?: string
}
```

- [ ] **Step 2: 添加新选项配置**

在 `INSPIRATION_OPTIONS` 对象中添加新选项（在 `stylePreferences` 之后）：

```typescript
  // 新增选项

  targetReader: [
    { value: 'male', label: '男频' },
    { value: 'female', label: '女频' },
  ],

  wordsPerChapter: [
    { value: '1500-2000', label: '1500-2000字', desc: '短章' },
    { value: '2000-2500', label: '2000-2500字', desc: '标准·番茄推荐' },
    { value: '2500-3000', label: '2500-3000字', desc: '中章·七猫推荐' },
    { value: '3000-5000', label: '3000-5000字', desc: '长章' },
    { value: 'custom', label: '自定义' },
  ],

  narrative: [
    { value: 'first', label: '第一人称' },
    { value: 'third', label: '第三人称' },
  ],

  goldFinger: [
    { value: 'system', label: '系统流' },
    { value: 'space', label: '空间流' },
    { value: 'reborn', label: '重生流' },
    { value: 'transmigrate', label: '穿越流' },
    { value: 'checkin', label: '签到流' },
    { value: 'none', label: '无金手指' },
    { value: 'custom', label: '自定义' },
  ],
```

同时需要扩展 `SelectOption` 类型以支持 `desc` 字段：

```typescript
export interface SelectOption {
  value: string
  label: string
  chapters?: string  // 仅用于篇幅选项
  words?: string     // 仅用于字数选项
  desc?: string      // 仅用于每章字数选项
}
```

- [ ] **Step 3: 更新 generateInspirationTemplate 函数**

修改 `generateInspirationTemplate` 函数以包含新字段：

```typescript
// 获取每章字数显示文本
export function getWordsPerChapterDisplay(data: InspirationData): string {
  if (data.wordsPerChapter === 'custom' && data.customWordsPerChapter) {
    return `${data.customWordsPerChapter}字`
  }
  const option = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.value === data.wordsPerChapter)
  if (option) {
    return option.label
  }
  return data.wordsPerChapter || ''
}

// 生成 Markdown 模板
export function generateInspirationTemplate(data: InspirationData): string {
  const novelType = getOptionLabel(INSPIRATION_OPTIONS.novelTypes, data.novelType)
  const novelLength = getLengthDisplay(data)
  const targetWords = getTargetWordsDisplay(data)
  const wordsPerChapter = getWordsPerChapterDisplay(data)
  const coreTheme = getOptionLabel(INSPIRATION_OPTIONS.coreThemes, data.coreTheme)
  const worldSetting = data.customWorldSetting || getOptionLabel(INSPIRATION_OPTIONS.worldSettings, data.worldSetting)
  const protagonist = data.customProtagonist || getOptionLabel(INSPIRATION_OPTIONS.protagonistTypes, data.protagonist)
  const style = getOptionLabel(INSPIRATION_OPTIONS.stylePreferences, data.stylePreference)
  const narrative = getOptionLabel(INSPIRATION_OPTIONS.narrative, data.narrative)
  const goldFinger = data.customGoldFinger || getOptionLabel(INSPIRATION_OPTIONS.goldFinger, data.goldFinger)

  return `# 小说创作灵感

## 基本信息

- **目标读者**：${data.targetReader === 'male' ? '男频' : data.targetReader === 'female' ? '女频' : '未设置'}
- **小说类型**：${novelType || '未设置'}
- **小说篇幅**：${novelLength || '未设置'}
- **目标字数**：${targetWords || '未设置'}
- **每章字数**：${wordsPerChapter || '未设置'}

## 叙事设定

- **叙事视角**：${narrative || '未设置'}

## 核心设定

- **核心主题**：${coreTheme || '未设置'}
- **世界观**：${worldSetting || '未设置'}
- **主角**：${protagonist || '未设置'}
- **金手指**：${goldFinger || '未设置'}

## 风格

- **风格偏好**：${style || '未设置'}

## 补充灵感

> 在下方添加更多灵感细节...

-

-

`
}
```

- [ ] **Step 4: 验证编译**

```bash
cd /opt/project/novelagent/frontend && npm run build 2>&1 | head -30
```

- [ ] **Step 5: 提交配置修改**

```bash
git add frontend/src/lib/inspiration.ts
git commit -m "feat(inspiration): add new options and update template generator

- Add targetReader, wordsPerChapter, narrative, goldFinger options
- Update InspirationData interface with new fields
- Update generateInspirationTemplate to include new fields
- Add getWordsPerChapterDisplay helper function"
```

---

### Task 3: 重构 InspirationForm 组件

**Files:**
- Rewrite: `frontend/src/components/project/InspirationForm.tsx`

- [ ] **Step 1: 编写新的 InspirationForm 组件**

完整重写组件，实现混合模式 UI：

```typescript
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  INSPIRATION_OPTIONS,
  saveInspirationDraft,
  loadInspirationDraft,
  clearInspirationDraft,
  type InspirationData,
  type SelectOption,
} from '@/lib/inspiration'

interface InspirationFormProps {
  initialData?: Partial<InspirationData>
  onSubmit: (data: InspirationData) => void
}

// 卡片选择组件
function CardSelect({
  options,
  value,
  onChange,
  icons,
  descriptions,
  columns = 6,
}: {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  icons?: Record<string, string>
  descriptions?: Record<string, string>
  columns?: number
}) {
  return (
    <div className={`grid grid-cols-${columns} gap-2`}>
      {options.map((opt) => (
        <div
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${
            value === opt.value
              ? 'border-blue-500 bg-blue-50 shadow-sm'
              : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
          }`}
        >
          {icons?.[opt.value] && <div className="text-lg mb-1">{icons[opt.value]}</div>}
          <div className="text-sm font-medium">{opt.label}</div>
          {descriptions?.[opt.value] && (
            <div className="text-xs text-gray-500 mt-1">{descriptions[opt.value]}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// 标签选择组件
function TagSelect({
  options,
  value,
  onChange,
}: {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <span
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
            value === opt.value
              ? 'bg-blue-500 text-white border-blue-500'
              : 'border-gray-200 hover:border-blue-300'
          }`}
        >
          {opt.label}
        </span>
      ))}
    </div>
  )
}

// 小说类型图标
const NOVEL_TYPE_ICONS: Record<string, string> = {
  xuanhuan: '⚔️',
  kehuan: '🚀',
  dushi: '🏙️',
  yanqing: '💕',
  xuanyi: '🔍',
  lishi: '📜',
}

// 目标读者图标和描述
const TARGET_READER_ICONS: Record<string, string> = {
  male: '👨',
  female: '👩',
}

const TARGET_READER_DESC: Record<string, string> = {
  male: '热血、爽文、升级',
  female: '言情、甜宠、逆袭',
}

export default function InspirationForm({ initialData, onSubmit }: InspirationFormProps) {
  // 必填项状态
  const [targetReader, setTargetReader] = useState(initialData?.targetReader || '')
  const [novelType, setNovelType] = useState(initialData?.novelType || '')
  const [novelLength, setNovelLength] = useState(initialData?.novelLength || '')
  const [customChapterCount, setCustomChapterCount] = useState<number | undefined>(initialData?.customChapterCount)
  const [targetWords, setTargetWords] = useState(initialData?.targetWords || '')
  const [customTargetWords, setCustomTargetWords] = useState<number | undefined>(initialData?.customTargetWords)
  const [wordsPerChapter, setWordsPerChapter] = useState(initialData?.wordsPerChapter || '')
  const [customWordsPerChapter, setCustomWordsPerChapter] = useState<number | undefined>(initialData?.customWordsPerChapter)

  // 选填项状态
  const [narrative, setNarrative] = useState(initialData?.narrative || '')
  const [coreTheme, setCoreTheme] = useState(initialData?.coreTheme || '')
  const [worldSetting, setWorldSetting] = useState(initialData?.worldSetting || '')
  const [customWorldSetting, setCustomWorldSetting] = useState(initialData?.customWorldSetting || '')
  const [protagonist, setProtagonist] = useState(initialData?.protagonist || '')
  const [customProtagonist, setCustomProtagonist] = useState(initialData?.customProtagonist || '')
  const [goldFinger, setGoldFinger] = useState(initialData?.goldFinger || '')
  const [customGoldFinger, setCustomGoldFinger] = useState(initialData?.customGoldFinger || '')
  const [stylePreference, setStylePreference] = useState(initialData?.stylePreference || '')

  const [errors, setErrors] = useState<Record<string, string>>({})

  // 加载草稿
  useEffect(() => {
    if (!initialData || Object.keys(initialData).length === 0) {
      const draft = loadInspirationDraft()
      if (draft) {
        if (draft.targetReader) setTargetReader(draft.targetReader)
        if (draft.novelType) setNovelType(draft.novelType)
        if (draft.novelLength) setNovelLength(draft.novelLength)
        if (draft.customChapterCount) setCustomChapterCount(draft.customChapterCount)
        if (draft.targetWords) setTargetWords(draft.targetWords)
        if (draft.customTargetWords) setCustomTargetWords(draft.customTargetWords)
        if (draft.wordsPerChapter) setWordsPerChapter(draft.wordsPerChapter)
        if (draft.customWordsPerChapter) setCustomWordsPerChapter(draft.customWordsPerChapter)
        if (draft.narrative) setNarrative(draft.narrative)
        if (draft.coreTheme) setCoreTheme(draft.coreTheme)
        if (draft.worldSetting) setWorldSetting(draft.worldSetting)
        if (draft.customWorldSetting) setCustomWorldSetting(draft.customWorldSetting)
        if (draft.protagonist) setProtagonist(draft.protagonist)
        if (draft.customProtagonist) setCustomProtagonist(draft.customProtagonist)
        if (draft.goldFinger) setGoldFinger(draft.goldFinger)
        if (draft.customGoldFinger) setCustomGoldFinger(draft.customGoldFinger)
        if (draft.stylePreference) setStylePreference(draft.stylePreference)
      }
    }
  }, [initialData])

  // 自动保存草稿
  useEffect(() => {
    const data: InspirationData = {
      novelType,
      novelLength,
      customChapterCount,
      targetWords,
      customTargetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      protagonist,
      customProtagonist,
      stylePreference,
      targetReader,
      wordsPerChapter,
      customWordsPerChapter,
      narrative,
      goldFinger,
      customGoldFinger,
    }
    if (novelType || novelLength || targetWords || coreTheme || targetReader) {
      saveInspirationDraft(data)
    }
  }, [novelType, novelLength, customChapterCount, targetWords, customTargetWords, coreTheme, worldSetting, customWorldSetting, protagonist, customProtagonist, stylePreference, targetReader, wordsPerChapter, customWordsPerChapter, narrative, goldFinger, customGoldFinger])

  const handleSubmit = () => {
    const newErrors: Record<string, string> = {}
    if (!targetReader) newErrors.targetReader = '请选择目标读者'
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!novelLength) newErrors.novelLength = '请选择小说篇幅'
    if (!targetWords) newErrors.targetWords = '请选择目标字数'
    if (!wordsPerChapter) newErrors.wordsPerChapter = '请选择每章字数'
    if (!coreTheme) newErrors.coreTheme = '请选择核心主题'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    const data: InspirationData = {
      novelType,
      novelLength,
      customChapterCount,
      targetWords,
      customTargetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      protagonist,
      customProtagonist,
      stylePreference,
      targetReader,
      wordsPerChapter,
      customWordsPerChapter,
      narrative,
      goldFinger,
      customGoldFinger,
    }

    clearInspirationDraft()
    onSubmit(data)
  }

  const handleClear = () => {
    clearInspirationDraft()
    setTargetReader('')
    setNovelType('')
    setNovelLength('')
    setCustomChapterCount(undefined)
    setTargetWords('')
    setCustomTargetWords(undefined)
    setWordsPerChapter('')
    setCustomWordsPerChapter(undefined)
    setNarrative('')
    setCoreTheme('')
    setWorldSetting('')
    setCustomWorldSetting('')
    setProtagonist('')
    setCustomProtagonist('')
    setGoldFinger('')
    setCustomGoldFinger('')
    setStylePreference('')
    setErrors({})
  }

  return (
    <div className="space-y-8">
      {/* 目标读者：独占一行，卡片选择 */}
      <div>
        <div className="text-sm font-medium text-gray-700 mb-3">
          目标读者 <span className="text-red-500">*</span>
        </div>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {INSPIRATION_OPTIONS.targetReader.map((opt) => (
            <div
              key={opt.value}
              onClick={() => {
                setTargetReader(opt.value)
                if (errors.targetReader) setErrors({ ...errors, targetReader: '' })
              }}
              className={`border-2 rounded-lg p-5 text-center cursor-pointer transition-all ${
                targetReader === opt.value
                  ? 'border-blue-500 bg-blue-50 shadow-sm'
                  : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
              }`}
            >
              <div className="text-3xl mb-2">{TARGET_READER_ICONS[opt.value]}</div>
              <div className="font-medium text-base">{opt.label}</div>
              <div className="text-xs text-gray-500 mt-1">{TARGET_READER_DESC[opt.value]}</div>
            </div>
          ))}
        </div>
        {errors.targetReader && <p className="text-red-500 text-xs mt-2">{errors.targetReader}</p>}
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 基本设定 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-semibold text-gray-700">基本设定</span>
          <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">必填</span>
        </div>

        {/* 小说类型：卡片选择 */}
        <div className="mb-6">
          <div className="text-sm font-medium text-gray-700 mb-3">
            小说类型 <span className="text-red-500">*</span>
          </div>
          <div className="grid grid-cols-6 gap-2">
            {INSPIRATION_OPTIONS.novelTypes.map((opt) => (
              <div
                key={opt.value}
                onClick={() => {
                  setNovelType(opt.value)
                  if (errors.novelType) setErrors({ ...errors, novelType: '' })
                }}
                className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${
                  novelType === opt.value
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
                }`}
              >
                <div className="text-lg mb-1">{NOVEL_TYPE_ICONS[opt.value]}</div>
                <div className="text-sm font-medium">{opt.label}</div>
              </div>
            ))}
          </div>
          {errors.novelType && <p className="text-red-500 text-xs mt-2">{errors.novelType}</p>}
        </div>

        {/* 下拉框选项：篇幅、目标字数、每章字数 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">
              小说篇幅 <span className="text-red-500">*</span>
            </div>
            <select
              className={`w-full h-11 px-3 rounded-lg border-2 bg-white text-sm ${
                errors.novelLength ? 'border-red-500' : 'border-gray-200'
              }`}
              value={novelLength}
              onChange={(e) => {
                setNovelLength(e.target.value)
                if (errors.novelLength) setErrors({ ...errors, novelLength: '' })
              }}
            >
              <option value="">请选择</option>
              {INSPIRATION_OPTIONS.novelLength.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                  {opt.chapters ? ` (${opt.chapters}章)` : ''}
                </option>
              ))}
            </select>
            {errors.novelLength && <p className="text-red-500 text-xs mt-1">{errors.novelLength}</p>}
          </div>

          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">
              目标字数 <span className="text-red-500">*</span>
            </div>
            <select
              className={`w-full h-11 px-3 rounded-lg border-2 bg-white text-sm ${
                errors.targetWords ? 'border-red-500' : 'border-gray-200'
              }`}
              value={targetWords}
              onChange={(e) => {
                setTargetWords(e.target.value)
                if (errors.targetWords) setErrors({ ...errors, targetWords: '' })
              }}
            >
              <option value="">请选择</option>
              {INSPIRATION_OPTIONS.targetWords.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.targetWords && <p className="text-red-500 text-xs mt-1">{errors.targetWords}</p>}
          </div>

          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">
              每章字数 <span className="text-red-500">*</span>
            </div>
            <select
              className={`w-full h-11 px-3 rounded-lg border-2 bg-white text-sm ${
                errors.wordsPerChapter ? 'border-red-500' : 'border-gray-200'
              }`}
              value={wordsPerChapter}
              onChange={(e) => {
                setWordsPerChapter(e.target.value)
                if (errors.wordsPerChapter) setErrors({ ...errors, wordsPerChapter: '' })
              }}
            >
              <option value="">请选择</option>
              {INSPIRATION_OPTIONS.wordsPerChapter.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                  {opt.desc ? `（${opt.desc}）` : ''}
                </option>
              ))}
            </select>
            {errors.wordsPerChapter && <p className="text-red-500 text-xs mt-1">{errors.wordsPerChapter}</p>}
          </div>
        </div>

        {/* 自定义输入 */}
        {(novelLength === 'custom' || targetWords === 'custom' || wordsPerChapter === 'custom') && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
            {novelLength === 'custom' && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">自定义章节数</div>
                <Input
                  type="number"
                  value={customChapterCount || ''}
                  onChange={(e) => setCustomChapterCount(parseInt(e.target.value) || undefined)}
                  placeholder="输入章节数"
                  className="h-11"
                />
              </div>
            )}
            {targetWords === 'custom' && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">自定义字数（万字）</div>
                <Input
                  type="number"
                  value={customTargetWords || ''}
                  onChange={(e) => setCustomTargetWords(parseInt(e.target.value) || undefined)}
                  placeholder="输入目标字数"
                  className="h-11"
                />
              </div>
            )}
            {wordsPerChapter === 'custom' && (
              <div>
                <div className="text-sm font-medium text-gray-700 mb-2">自定义每章字数</div>
                <Input
                  type="number"
                  value={customWordsPerChapter || ''}
                  onChange={(e) => setCustomWordsPerChapter(parseInt(e.target.value) || undefined)}
                  placeholder="输入字数"
                  className="h-11"
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 进阶设定 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-semibold text-gray-700">进阶设定</span>
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">选填</span>
        </div>

        <div className="space-y-6">
          {/* 叙事视角 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">叙事视角</div>
            <div className="flex gap-2">
              {INSPIRATION_OPTIONS.narrative.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setNarrative(opt.value)}
                  className={`px-5 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    narrative === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>

          {/* 核心主题 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">
              核心主题 <span className="text-red-500">*</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => {
                    setCoreTheme(opt.value)
                    if (errors.coreTheme) setErrors({ ...errors, coreTheme: '' })
                  }}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    coreTheme === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {errors.coreTheme && <p className="text-red-500 text-xs mt-2">{errors.coreTheme}</p>}
          </div>

          {/* 世界观设定 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">世界观设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.worldSettings.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setWorldSetting(opt.value)}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    worldSetting === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {worldSetting === 'custom' && (
              <Input
                type="text"
                value={customWorldSetting || ''}
                onChange={(e) => setCustomWorldSetting(e.target.value)}
                placeholder="输入自定义世界观设定"
                className="mt-2 max-w-md"
              />
            )}
          </div>

          {/* 主角设定 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">主角设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.protagonistTypes.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setProtagonist(opt.value)}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    protagonist === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {protagonist === 'custom' && (
              <Input
                type="text"
                value={customProtagonist || ''}
                onChange={(e) => setCustomProtagonist(e.target.value)}
                placeholder="输入自定义主角设定"
                className="mt-2 max-w-md"
              />
            )}
          </div>

          {/* 金手指设定 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">金手指设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.goldFinger.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setGoldFinger(opt.value)}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    goldFinger === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {goldFinger === 'custom' && (
              <Input
                type="text"
                value={customGoldFinger || ''}
                onChange={(e) => setCustomGoldFinger(e.target.value)}
                placeholder="输入自定义金手指设定"
                className="mt-2 max-w-md"
              />
            )}
          </div>

          {/* 风格偏好 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">风格偏好</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.stylePreferences.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setStylePreference(opt.value)}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    stylePreference === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button variant="outline" onClick={handleClear}>
          清空表单
        </Button>
        <Button onClick={handleSubmit}>生成灵感模板</Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 验证编译**

```bash
cd /opt/project/novelagent/frontend && npm run build 2>&1 | head -30
```

- [ ] **Step 3: 提交表单重构**

```bash
git add frontend/src/components/project/InspirationForm.tsx
git commit -m "refactor(InspirationForm): redesign UI with cards and tags

- Add target reader card selection at top
- Use card selection for novel type with icons
- Use tag selection for advanced settings
- Add words per chapter dropdown
- Add narrative perspective and gold finger options
- Improve form validation and error display"
```

---

### Task 4: 更新 InspirationEditor 组件

**Files:**
- Modify: `frontend/src/components/project/InspirationEditor.tsx`

- [ ] **Step 1: 添加新字段的显示和编辑**

更新 InspirationEditor 组件，添加新字段：

在状态定义部分添加新字段，并在表单中添加对应的 UI。

需要修改的关键部分：

1. 添加新字段的状态处理
2. 在表单中添加新字段的下拉框/标签选择
3. 更新章节数和字数计算逻辑

详细代码变更（由于文件较大，仅展示关键变更）：

在第一行表单区域（小说类型、篇幅、目标字数）后添加：
- 每章字数下拉框
- 目标读者显示

在第二行表单区域添加：
- 叙事视角下拉框
- 金手指设定下拉框

- [ ] **Step 2: 验证编译**

```bash
cd /opt/project/novelagent/frontend && npm run build 2>&1 | head -30
```

- [ ] **Step 3: 提交编辑器更新**

```bash
git add frontend/src/components/project/InspirationEditor.tsx
git commit -m "feat(InspirationEditor): add new field editing support

- Add target reader display
- Add words per chapter dropdown
- Add narrative perspective dropdown
- Add gold finger setting dropdown
- Update display logic for new fields"
```

---

### Task 5: 构建并测试

**Files:**
- None (验证步骤)

- [ ] **Step 1: 构建前端**

```bash
cd /opt/project/novelagent && docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 2: 重启后端**

```bash
cd /opt/project/novelagent && docker compose restart backend
```

- [ ] **Step 3: 验证功能**

在浏览器中访问：
1. 创建新项目
2. 进入灵感采集步骤
3. 验证新 UI：
   - 目标读者卡片显示正常
   - 小说类型卡片带图标
   - 下拉框样式正确
   - 标签选择交互正常
   - 表单验证正常
   - 生成模板包含新字段

- [ ] **Step 4: 最终提交**

```bash
git add -A
git status
git commit -m "feat: complete inspiration form enhancement

- Add 4 new config items: target reader, words per chapter, narrative, gold finger
- Redesign UI with card selection for required items
- Use tag selection for advanced settings
- Update type definitions and template generator"
```

---

## Success Criteria

1. ✅ 目标读者卡片独占一行，样式突出
2. ✅ 小说类型使用卡片选择，带图标
3. ✅ 必填项（篇幅、字数、每章字数）使用下拉框
4. ✅ 进阶设定全部使用标签选择，每种独占一行
5. ✅ 所有新增字段正确保存到后端
6. ✅ 灵感模板正确包含新增字段
7. ✅ 表单验证正常工作
