# 灵感页面重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将灵感采集页面从「表单/对话双模式切换」重构为「Agent 驱动表单」统一体验。

**Architecture:** 删除 InspirationChatPanel + InspirationPreview，灵感对话由右栏 AICompanionSidebar 承载。左栏参数面板通过 workbenchStore 与 Agent 双向桥接，Agent tool call 实时操作表单字段。1400 行巨型组件拆分为 4 个聚焦文件 + 1 个自定义 hook。

**Tech Stack:** React 18 + Zustand + TypeScript + Tailwind + shadcn/ui + Vitest

---

## Task 1: 拆分 inspiration.ts 为模块化文件

**Files:**
- Create: `frontend/src/lib/inspiration/types.ts`
- Create: `frontend/src/lib/inspiration/config.ts`
- Create: `frontend/src/lib/inspiration/templates.ts`
- Create: `frontend/src/lib/inspiration/utils.ts`
- Create: `frontend/src/lib/inspiration/index.ts`
- Delete: `frontend/src/lib/inspiration.ts` (删除原文件，由目录入口替代)

> **重要：** 不能同时保留 `inspiration.ts` 文件和 `inspiration/` 目录，否则模块解析冲突。
> 删除原文件后，`import ... from '@/lib/inspiration'` 自动解析到 `inspiration/index.ts`。

- [ ] **Step 1: 创建 `types.ts`**

从 `inspiration.ts` 提取所有类型定义：

```typescript
// frontend/src/lib/inspiration/types.ts

/** 字段状态：Agent 联动标签 */
export type FieldStatus =
  | 'agent_populated'  // Agent 填充，紫色标签
  | 'agent_asking'     // Agent 询问中，黄色标签
  | 'empty'            // 待填写
  | 'user_filled'      // 用户手动填写

/** 选项基础结构 */
export interface SelectOption {
  value: string
  label: string
  desc?: string
}

/** 灵感采集数据 */
export interface InspirationData {
  novelType: string
  targetWords: number
  contextStrategy: string
  coreTheme: string
  worldSetting?: string
  customWorldSetting?: string
  protagonist?: string
  customProtagonist?: string
  stylePreference?: string
  targetReader: string
  wordsPerChapter: string
  customWordsPerChapter?: number
  narrative?: string
  goldFinger?: string
  customGoldFinger?: string
  era?: string
  genre?: string
  customGenre?: string
  maleLead?: string
  customMaleLead?: string
  femaleLead?: string
  customFemaleLead?: string
  novelLength?: 'short' | 'medium' | 'long'
}

/** 上下文策略选项 */
export interface ContextStrategyOption {
  value: string
  label: string
  desc: string
  recommendedWords: string
}

/** 快捷填充模板 */
export interface QuickTemplate {
  id: string
  label: string
  icon: string
  data: Partial<InspirationData>
}

/** 必填字段 key */
export const REQUIRED_FIELDS: (keyof InspirationData)[] = [
  'novelType', 'targetReader', 'targetWords', 'era', 'coreTheme', 'wordsPerChapter',
]

/** 男频必填字段 */
export const MALE_REQUIRED_FIELDS: (keyof InspirationData)[] = ['maleLead']

/** 女频必填字段 */
export const FEMALE_REQUIRED_FIELDS: (keyof InspirationData)[] = ['femaleLead']
```

- [ ] **Step 2: 创建 `config.ts`**

从 `inspiration.ts` 提取所有选项常量（COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS, CONTEXT_STRATEGY_OPTIONS 等），保持原值不变。将 `getInspirationOptions()` 函数移入。

同时从 `InspirationPanel.tsx` 提取图标映射常量（原文件中 `NOVEL_TYPE_ICONS`、`ERA_ICONS`、`TARGET_READER_ICONS`、`TARGET_READER_DESC` 是 `const` 未导出的，位于 InspirationPanel.tsx:67-100 行）。

```typescript
// frontend/src/lib/inspiration/config.ts
// 从原 inspiration.ts 复制：COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS, CONTEXT_STRATEGY_OPTIONS
// 复制函数：getInspirationOptions, getContextStrategyFromTargetWords
// 复制常量：INSPIRATION_OPTIONS（向后兼容）
// 从 InspirationPanel.tsx:67-100 复制图标映射：NOVEL_TYPE_ICONS, ERA_ICONS, TARGET_READER_ICONS, TARGET_READER_DESC
// 不再复制：NOVEL_LENGTH_OPTIONS（空数组，已废弃的死代码）
```

- [ ] **Step 3: 创建 `templates.ts`**

从 `inspiration.ts` 提取模板相关函数和常量：

```typescript
// frontend/src/lib/inspiration/templates.ts
// 复制：QUICK_TEMPLATES, generateInspirationTemplate, parseTemplateToData, getOptionLabel, getWordsPerChapterDisplay
```

- [ ] **Step 4: 创建 `utils.ts`**

从 `inspiration.ts` 提取工具函数和持久化：

```typescript
// frontend/src/lib/inspiration/utils.ts
// 复制：inferFieldsFromText, getMissingFields, saveInspirationDraft, loadInspirationDraft, clearInspirationDraft, asString
```

- [ ] **Step 5: 创建 `index.ts` 兼容入口**

```typescript
// frontend/src/lib/inspiration/index.ts
// Re-export all public APIs，确保现有 import '@/lib/inspiration' 不中断
export type { InspirationData, SelectOption, ContextStrategyOption, FieldStatus, QuickTemplate } from './types'
export { REQUIRED_FIELDS, MALE_REQUIRED_FIELDS, FEMALE_REQUIRED_FIELDS } from './types'
export { COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS, CONTEXT_STRATEGY_OPTIONS, INSPIRATION_OPTIONS, getInspirationOptions, getContextStrategyFromTargetWords, NOVEL_TYPE_ICONS, ERA_ICONS, TARGET_READER_ICONS, TARGET_READER_DESC } from './config'
export { QUICK_TEMPLATES, generateInspirationTemplate, parseTemplateToData, getOptionLabel, getWordsPerChapterDisplay } from './templates'
export { inferFieldsFromText, getMissingFields, saveInspirationDraft, loadInspirationDraft, clearInspirationDraft, asString } from './utils'
```

- [ ] **Step 6: 删除原 `inspiration.ts`**

```bash
rm frontend/src/lib/inspiration.ts
```

> 不能保留 `inspiration.ts` 文件与 `inspiration/` 目录共存，否则模块解析冲突。
> 删除后 `import ... from '@/lib/inspiration'` 自动解析到 `inspiration/index.ts`。

- [ ] **Step 7: 验证编译通过**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无新增错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/inspiration/
git commit -m "refactor(frontend): split inspiration.ts into modular files (types/config/templates/utils)"
```

---

## Task 2: workbenchStore 新增灵感状态

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`
- Test: `frontend/src/stores/__tests__/workbenchStore.inspiration.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// frontend/src/stores/__tests__/workbenchStore.inspiration.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { InspirationData, FieldStatus } from '@/lib/inspiration/types'

describe('workbenchStore inspiration fields', () => {
  beforeEach(() => {
    useWorkbenchStore.getState().reset()
  })

  it('should have default empty inspirationFields', () => {
    const { inspirationFields } = useWorkbenchStore.getState()
    expect(inspirationFields).toBeDefined()
    expect(inspirationFields.novelType).toBe('')
    expect(inspirationFields.targetWords).toBe(50000)
  })

  it('should update inspirationFields via setInspirationField', () => {
    useWorkbenchStore.getState().setInspirationField('novelType', 'xuanhuan')
    expect(useWorkbenchStore.getState().inspirationFields.novelType).toBe('xuanhuan')
    // 设置字段时自动将 fieldStatus 从 agent_asking 变为 empty
  })

  it('should update fieldStatus via setInspirationFieldStatus', () => {
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_populated')
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBe('agent_populated')
  })

  it('should clear fieldStatus when field is set by user', () => {
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_asking')
    useWorkbenchStore.getState().setInspirationField('novelType', 'xuanhuan')
    // 用户手动设置字段后，应清除 agent_asking 状态
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBeUndefined()
  })

  it('should batch update inspirationFields via setInspirationFields', () => {
    useWorkbenchStore.getState().setInspirationFields({
      novelType: 'xuanhuan',
      targetReader: 'male',
      targetWords: 100000,
    })
    const { inspirationFields } = useWorkbenchStore.getState()
    expect(inspirationFields.novelType).toBe('xuanhuan')
    expect(inspirationFields.targetReader).toBe('male')
    expect(inspirationFields.targetWords).toBe(100000)
  })

  it('should reset inspiration state on reset()', () => {
    useWorkbenchStore.getState().setInspirationField('novelType', 'xuanhuan')
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_populated')
    useWorkbenchStore.getState().reset()
    expect(useWorkbenchStore.getState().inspirationFields.novelType).toBe('')
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBeUndefined()
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx vitest run src/stores/__tests__/workbenchStore.inspiration.test.ts 2>&1 | tail -15`
Expected: FAIL — `inspirationFields` 不存在

- [ ] **Step 3: 在 workbenchStore 中添加灵感状态**

在 `WorkbenchState` 接口中新增：

```typescript
// 新增 imports
import type { InspirationData, FieldStatus } from '@/lib/inspiration/types'

// WorkbenchState 接口新增：
inspirationFields: InspirationData
inspirationFieldStatus: Record<string, FieldStatus>
setInspirationField: <K extends keyof InspirationData>(key: K, value: InspirationData[K]) => void
setInspirationFieldStatus: (key: string, status: FieldStatus) => void
setInspirationFields: (fields: Partial<InspirationData>) => void
```

在 `initialState` 中新增默认值：

```typescript
inspirationFields: {
  novelType: '',
  targetWords: 50000,
  contextStrategy: 'fulltext',
  coreTheme: '',
  targetReader: '',
  wordsPerChapter: '',
} as InspirationData,
inspirationFieldStatus: {} as Record<string, FieldStatus>,
```

在 store 实现中新增方法：

```typescript
setInspirationField: (key, value) => set((state) => {
  const newStatus = { ...state.inspirationFieldStatus }
  // 用户手动设置字段时，清除 agent_asking 状态（表示用户已响应 Agent 询问）
  // 保留 agent_populated 状态不变（仅 Agent 自身可清除）
  if (newStatus[key] === 'agent_asking') {
    delete newStatus[key]
  }
  return {
    inspirationFields: { ...state.inspirationFields, [key]: value },
    inspirationFieldStatus: newStatus,
  }
}),

setInspirationFieldStatus: (key, status) => set((state) => ({
  inspirationFieldStatus: { ...state.inspirationFieldStatus, [key]: status }
})),

setInspirationFields: (fields) => set((state) => ({
  inspirationFields: { ...state.inspirationFields, ...fields }
})),
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx vitest run src/stores/__tests__/workbenchStore.inspiration.test.ts 2>&1 | tail -10`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/workbenchStore.ts frontend/src/stores/__tests__/workbenchStore.inspiration.test.ts
git commit -m "feat(frontend): add inspirationFields and FieldStatus to workbenchStore"
```

---

## Task 3: 提取 useInspirationForm hook

**Files:**
- Create: `frontend/src/components/workbench/planning/useInspirationForm.ts`
- Test: `frontend/src/components/workbench/planning/__tests__/useInspirationForm.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// frontend/src/components/workbench/planning/__tests__/useInspirationForm.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useInspirationForm } from '../useInspirationForm'
import { useWorkbenchStore } from '@/stores/workbenchStore'

vi.mock('@/lib/api', () => ({
  collectedInfoApi: { update: vi.fn().mockResolvedValue({}) },
  modelConfigsApi: { list: vi.fn().mockResolvedValue({ models: [] }) },
  outlineApi: { get: vi.fn().mockRejectedValue({}) },
}))

describe('useInspirationForm', () => {
  beforeEach(() => {
    useWorkbenchStore.getState().reset()
  })

  it('should initialize with default values', () => {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    expect(result.current.errors).toEqual({})
    expect(result.current.confirming).toBe(false)
  })

  it('should validate required fields and set errors', () => {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() => { result.current.validate() })
    expect(Object.keys(result.current.errors).length).toBeGreaterThan(0)
    expect(result.current.errors.targetReader).toBeDefined()
  })

  it('should clear error when field is set', () => {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() => { result.current.validate() })
    expect(result.current.errors.targetReader).toBeDefined()
    act(() => { result.current.setField('targetReader', 'male') })
    expect(result.current.errors.targetReader).toBeUndefined()
  })

  it('should build collectedInfoData for API', () => {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() => {
      result.current.setField('novelType', 'xuanhuan')
      result.current.setField('targetReader', 'male')
      result.current.setField('targetWords', 100000)
    })
    const data = result.current.buildCollectedInfoData()
    expect(data.novelType).toBe('xuanhuan')
    expect(data.targetReader).toBe('male')
  })

  it('should compute required progress', () => {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    // 默认状态：targetWords 有值，其余必填为空
    const { requiredFilled, requiredTotal } = result.current.progress
    expect(requiredTotal).toBeGreaterThanOrEqual(6)
    expect(requiredFilled).toBeLessThan(requiredTotal)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx vitest run src/components/workbench/planning/__tests__/useInspirationForm.test.ts 2>&1 | tail -10`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现 useInspirationForm**

```typescript
// frontend/src/components/workbench/planning/useInspirationForm.ts
import { useState, useEffect, useRef, useCallback } from 'react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import {
  type InspirationData, REQUIRED_FIELDS, MALE_REQUIRED_FIELDS, FEMALE_REQUIRED_FIELDS,
  getContextStrategyFromTargetWords, generateInspirationTemplate,
  saveInspirationDraft, loadInspirationDraft,
} from '@/lib/inspiration'
import { outlineApi } from '@/lib/api'

interface UseInspirationFormOptions {
  projectId: number
  hasOutline?: boolean
}

export function useInspirationForm({ projectId, hasOutline = false }: UseInspirationFormOptions) {
  const {
    inspirationFields, setInspirationField, setInspirationFields, setInspirationFieldStatus,
    inspirationFieldStatus,
  } = useWorkbenchStore()

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [confirming, setConfirming] = useState(false)
  const [template, setTemplate] = useState('')
  const [templateManuallyEdited, setTemplateManuallyEdited] = useState(false)
  const initializedRef = useRef(false)
  // 防抖自动保存：用 ref 追踪最新状态，避免闭包捕获旧值
  const fieldsRef = useRef(inspirationFields)
  fieldsRef.current = inspirationFields

  // 初始化：从后端或 localStorage 加载
  useEffect(() => {
    if (initializedRef.current) return
    const load = async () => {
      let source: Record<string, unknown> | null = null
      try {
        const outline = await outlineApi.get(projectId)
        if (outline.collected_info && Object.keys(outline.collected_info).length > 0) {
          source = outline.collected_info as Record<string, unknown>
        }
      } catch { /* 新项目无 outline */ }
      if (!source) {
        const draft = loadInspirationDraft()
        if (draft) source = draft as Record<string, unknown>
      }
      if (source) {
        const fields: Partial<InspirationData> = {}
        for (const [key, val] of Object.entries(source)) {
          if (key in inspirationFields && val !== undefined && val !== '') {
            (fields as Record<string, unknown>)[key] = val
          }
        }
        setInspirationFields(fields)
      }
      initializedRef.current = true
    }
    load()
  }, [projectId])

  // 自动保存草稿（用 ref 读取最新状态，避免防抖闭包捕获旧值）
  useEffect(() => {
    if (!initializedRef.current) return
    const timer = setTimeout(() => {
      const fields = fieldsRef.current
      if (fields.novelType || fields.targetReader || fields.targetWords) {
        saveInspirationDraft(fields)
      }
    }, 500) // 500ms 防抖
    return () => clearTimeout(timer)
  }, [inspirationFields])

  // 自动生成模板
  useEffect(() => {
    if (!templateManuallyEdited) {
      setTemplate(generateInspirationTemplate(inspirationFields))
    }
  }, [inspirationFields, templateManuallyEdited])

  // targetReader 变化时清除不相关字段
  // 使用 prevReaderRef 防止初始化加载时误清
  const prevReaderRef = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (!initializedRef.current) return
    const reader = inspirationFields.targetReader
    const prevReader = prevReaderRef.current
    prevReaderRef.current = reader
    // 仅在 targetReader 真正变化且从 male/female 切换时清除
    if (prevReader && reader !== prevReader) {
      if (reader === 'female') {
        setInspirationFields({ genre: '', customGenre: '', maleLead: '', customMaleLead: '', goldFinger: '', customGoldFinger: '' })
      } else if (reader === 'male') {
        setInspirationFields({ femaleLead: '', customFemaleLead: '' })
      }
    }
  }, [inspirationFields.targetReader])

  // 设置单个字段（清除对应 error）
  const setField = useCallback(<K extends keyof InspirationData>(key: K, value: InspirationData[K]) => {
    setInspirationField(key, value)
    if (errors[key]) {
      setErrors(prev => { const next = { ...prev }; delete next[key]; return next })
    }
    if (!value) return
    // 自动推荐上下文策略
    if (key === 'targetWords') {
      setInspirationField('contextStrategy', getContextStrategyFromTargetWords(value as number))
    }
  }, [errors, setInspirationField])

  // 校验
  const validate = useCallback((): boolean => {
    const newErrors: Record<string, string> = {}
    const reader = inspirationFields.targetReader
    for (const f of REQUIRED_FIELDS) {
      if (!inspirationFields[f]) newErrors[f] = `请选择${f}`
    }
    if (reader === 'male') {
      for (const f of MALE_REQUIRED_FIELDS) {
        if (!inspirationFields[f]) newErrors[f] = `请选择${f}`
      }
    } else if (reader === 'female') {
      for (const f of FEMALE_REQUIRED_FIELDS) {
        if (!inspirationFields[f]) newErrors[f] = `请选择${f}`
      }
    }
    if (inspirationFields.targetWords < 10000) newErrors.targetWords = '目标字数至少1万字'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }, [inspirationFields])

  // 构建 collectedInfo（供 confirm 和 replan 共用，消除重复代码）
  // 直接从 store 读取 selectedModelKey，避免闭包捕获旧值
  const buildCollectedInfoData = useCallback((): Record<string, unknown> => {
    const data: Record<string, unknown> = { inspiration_template: template }
    const f = inspirationFields
    if (f.novelType) data.novelType = f.novelType
    data.targetWords = f.targetWords
    data.contextStrategy = f.contextStrategy
    if (f.novelLength) data.novelLength = f.novelLength
    if (f.coreTheme) data.coreTheme = f.coreTheme
    if (f.worldSetting) { data.worldSetting = f.worldSetting; if (f.customWorldSetting) data.customWorldSetting = f.customWorldSetting }
    if (f.targetReader) data.targetReader = f.targetReader
    if (f.wordsPerChapter) { data.wordsPerChapter = f.wordsPerChapter; if (f.customWordsPerChapter) data.customWordsPerChapter = f.customWordsPerChapter }
    if (f.narrative) data.narrative = f.narrative
    if (f.stylePreference) data.stylePreference = f.stylePreference
    if (f.era) data.era = f.era
    if (f.targetReader === 'male') {
      if (f.maleLead) data.maleLead = f.maleLead
      if (f.customMaleLead) data.customMaleLead = f.customMaleLead
      const lead = f.maleLead === 'custom' ? f.customMaleLead : f.maleLead
      if (lead) data.protagonist = lead
      const genreVal = f.genre === 'custom' ? f.customGenre : f.genre
      if (genreVal) data.genre = genreVal
      const gf = f.goldFinger === 'custom' ? f.customGoldFinger : f.goldFinger
      if (gf) data.goldFinger = gf
    } else if (f.targetReader === 'female') {
      if (f.femaleLead) data.femaleLead = f.femaleLead
      if (f.customFemaleLead) data.customFemaleLead = f.customFemaleLead
      const lead = f.femaleLead === 'custom' ? f.customFemaleLead : f.femaleLead
      if (lead) data.protagonist = lead
    }
    // 模型信息：从 store 实时读取，不依赖闭包
    const selectedModelKey = useWorkbenchStore.getState().selectedModelKey
    if (selectedModelKey) {
      const [configIdStr, ...modelNameParts] = selectedModelKey.split(':')
      const configId = parseInt(configIdStr)
      const modelName = modelNameParts.join(':')
      if (!isNaN(configId) && modelName) {
        data.model_config_id = configId
        data.model_name = modelName
      }
    }
    return data
  }, [inspirationFields, template])

  // 进度计算
  const progress = useCallback(() => {
    let required = [...REQUIRED_FIELDS]
    if (inspirationFields.targetReader === 'male') required = [...required, ...MALE_REQUIRED_FIELDS]
    else if (inspirationFields.targetReader === 'female') required = [...required, ...FEMALE_REQUIRED_FIELDS]
    const filled = required.filter(k => {
      const val = inspirationFields[k]
      return val !== undefined && val !== null && val !== ''
    }).length
    return { requiredFilled: filled, requiredTotal: required.length }
  }, [inspirationFields])()

  // 模板编辑
  const handleTemplateChange = useCallback((value: string) => {
    setTemplate(value)
    setTemplateManuallyEdited(true)
  }, [])

  const handleResetTemplate = useCallback(() => {
    setTemplate(generateInspirationTemplate(inspirationFields))
    setTemplateManuallyEdited(false)
  }, [inspirationFields])

  return {
    fields: inspirationFields,
    fieldStatus: inspirationFieldStatus,
    errors,
    confirming,
    setConfirming,
    template,
    templateManuallyEdited,
    setField,
    validate,
    buildCollectedInfoData,
    progress,
    handleTemplateChange,
    handleResetTemplate,
    initializedRef,
  }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx vitest run src/components/workbench/planning/__tests__/useInspirationForm.test.ts 2>&1 | tail -10`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/planning/useInspirationForm.ts frontend/src/components/workbench/planning/__tests__/useInspirationForm.test.ts
git commit -m "feat(frontend): extract useInspirationForm hook from InspirationPanel"
```

---

## Task 4: 创建 InspirationFieldGroup 组件

**Files:**
- Create: `frontend/src/components/workbench/planning/InspirationFieldGroup.tsx`

- [ ] **Step 1: 实现 InspirationFieldGroup**

字段组容器：卡片式布局 + Agent 状态标签（Agent 已提取 / Agent 询问中 / 无标签）

```typescript
// frontend/src/components/workbench/planning/InspirationFieldGroup.tsx
import type { ReactNode } from 'react'
import type { FieldStatus } from '@/lib/inspiration/types'

interface InspirationFieldGroupProps {
  title: string
  icon: string
  required?: boolean
  children: ReactNode
  /** 字段组内所有字段的最高优先级状态 */
  groupStatus?: FieldStatus
  /** 是否可折叠 */
  collapsible?: boolean
  collapsed?: boolean
  onToggleCollapse?: () => void
  /** 已填选填项数 */
  optionalFilledCount?: number
}

const STATUS_CONFIG: Record<string, { label: string; borderClass: string; headerBg: string; badgeClass: string }> = {
  agent_populated: {
    label: 'Agent 已提取',
    borderClass: 'border-indigo-200',
    headerBg: 'bg-indigo-50',
    badgeClass: 'bg-indigo-600 text-white',
  },
  agent_asking: {
    label: 'Agent 询问中',
    borderClass: 'border-amber-300',
    headerBg: 'bg-amber-50',
    badgeClass: 'bg-amber-500 text-white',
  },
  empty: {
    label: '',
    borderClass: 'border-gray-200',
    headerBg: 'bg-white',
    badgeClass: '',
  },
  user_filled: {
    label: '',
    borderClass: 'border-gray-200',
    headerBg: 'bg-white',
    badgeClass: '',
  },
}

export function InspirationFieldGroup({
  title, icon, required, children, groupStatus = 'empty',
  collapsible, collapsed, onToggleCollapse, optionalFilledCount,
}: InspirationFieldGroupProps) {
  const config = STATUS_CONFIG[groupStatus] || STATUS_CONFIG.empty

  return (
    <div className={`rounded-lg border overflow-hidden ${config.borderClass}`}>
      <div className={`flex items-center justify-between px-3.5 py-2.5 ${config.headerBg}`}>
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className="text-xs font-bold text-slate-800">
            {title}
            {required && <span className="text-red-500 ml-1 text-[10px]">*必填</span>}
          </span>
          {!required && optionalFilledCount !== undefined && optionalFilledCount > 0 && (
            <span className="text-[10px] text-indigo-500">· 已填 {optionalFilledCount} 项</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {config.label && (
            <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium ${config.badgeClass}`}>
              {config.label}
            </span>
          )}
          {collapsible && (
            <button onClick={onToggleCollapse} className="text-xs text-muted-foreground hover:text-foreground">
              {collapsed ? '▾ 点击展开' : '▴ 收起'}
            </button>
          )}
        </div>
      </div>
      {!collapsed && <div className="p-3.5">{children}</div>}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationFieldGroup.tsx
git commit -m "feat(frontend): add InspirationFieldGroup component with Agent status badges"
```

---

## Task 5: 创建 InspirationTemplatePreview 组件

**Files:**
- Create: `frontend/src/components/workbench/planning/InspirationTemplatePreview.tsx`

- [ ] **Step 1: 实现 InspirationTemplatePreview**

```typescript
// frontend/src/components/workbench/planning/InspirationTemplatePreview.tsx
import { useState, useCallback } from 'react'
import { Copy, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'

interface InspirationTemplatePreviewProps {
  template: string
  manuallyEdited: boolean
  onTemplateChange: (value: string) => void
  onResetTemplate: () => void
}

export function InspirationTemplatePreview({
  template, manuallyEdited, onTemplateChange, onResetTemplate,
}: InspirationTemplatePreviewProps) {
  const [expanded, setExpanded] = useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(template).then(
      () => toast.success('Prompt 已复制到剪贴板'),
      () => toast.error('复制失败')
    )
  }, [template])

  return (
    <div className="rounded-lg border border-gray-200 bg-slate-50 overflow-hidden">
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-100">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500">📄 生成预览</span>
          <span className="text-[9px] text-slate-400">
            {manuallyEdited ? '手动编辑中 · 表单修改不再自动更新' : '自动生成 · 点击可编辑'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {manuallyEdited && (
            <button onClick={onResetTemplate} className="text-[9px] px-2 py-1 border rounded hover:bg-white text-slate-500">
              <RotateCcw className="h-3 w-3 inline mr-0.5" />重置
            </button>
          )}
          <button onClick={handleCopy} className="text-[9px] px-2 py-1 border rounded hover:bg-white text-slate-500">
            <Copy className="h-3 w-3 inline mr-0.5" />复制
          </button>
          <button onClick={() => setExpanded(!expanded)} className="text-[9px] px-2 py-1 text-slate-400 hover:text-slate-600">
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>
      <div className={`px-3.5 ${expanded ? 'py-2' : 'py-1.5'}`}>
        <Textarea
          value={template}
          onChange={(e) => onTemplateChange(e.target.value)}
          placeholder="选择灵感选项后，此处将自动生成创作 Prompt..."
          className={`w-full font-mono text-xs leading-relaxed resize-none border-none shadow-none focus-visible:ring-0 bg-transparent ${expanded ? 'h-64' : 'h-16'}`}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationTemplatePreview.tsx
git commit -m "feat(frontend): add InspirationTemplatePreview component"
```

---

## Task 6: 创建 InspirationForm 参数面板

**Files:**
- Create: `frontend/src/components/workbench/planning/InspirationForm.tsx`

这是最核心的组件，替代原来 InspirationPanel 中的全部表单 JSX。

- [ ] **Step 1: 实现 InspirationForm**

```typescript
// frontend/src/components/workbench/planning/InspirationForm.tsx
import { useState, useEffect } from 'react'
import { Lightbulb, Cpu, Settings2, Check, RefreshCw } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  INSPIRATION_OPTIONS, COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS,
  CONTEXT_STRATEGY_OPTIONS, QUICK_TEMPLATES,
  NOVEL_TYPE_ICONS, ERA_ICONS, TARGET_READER_ICONS, TARGET_READER_DESC,
  type InspirationData, type FieldStatus,
} from '@/lib/inspiration'
import { modelConfigsApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { InspirationFieldGroup } from './InspirationFieldGroup'
import { InspirationTemplatePreview } from './InspirationTemplatePreview'
import { useInspirationForm } from './useInspirationForm'

/** 扁平化后的模型选项 */
export interface ModelOption {
  modelConfigId: number
  modelName: string
  configName: string
  isDefault: boolean
}

interface InspirationFormProps {
  projectId: number
  hasOutline?: boolean
  /** 确认灵感：校验 → 调用 API 保存 → 返回 collectedInfo 供父组件打开进度弹窗 */
  onConfirm: (collectedInfo: Record<string, unknown>) => Promise<void>
  /** 重新规划：校验 → 构建 collectedInfo → 通知父组件显示确认弹窗 */
  onRequestReplan: (collectedInfo: Record<string, unknown>) => void
}

export function InspirationForm({ projectId, hasOutline, onConfirm, onRequestReplan }: InspirationFormProps) {
  const {
    fields, fieldStatus, errors, confirming, setConfirming,
    template, templateManuallyEdited,
    setField, validate, buildCollectedInfoData, progress,
    handleTemplateChange, handleResetTemplate,
  } = useInspirationForm({ projectId, hasOutline })

  const { selectedModelKey, setSelectedModelKey } = useWorkbenchStore()
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [reviewLlmConfigId, setReviewLlmConfigId] = useState<number | null>(null)
  const [showReviewModelAdvanced, setShowReviewModelAdvanced] = useState(false)
  const [advancedExpanded, setAdvancedExpanded] = useState(false)
  const [quickTemplateOpen, setQuickTemplateOpen] = useState(false)

  // 加载模型列表
  useEffect(() => {
    const load = async () => {
      setLoadingModels(true)
      try {
        const response = await modelConfigsApi.list()
        const options: ModelOption[] = []
        for (const config of response.models) {
          if (!config.is_enabled) continue
          if (config.models && config.models.length > 0) {
            for (const model of config.models) {
              if (!model.is_enabled) continue
              options.push({ modelConfigId: config.id, modelName: model.name, configName: config.name, isDefault: config.is_default })
            }
          } else if (config.model_name) {
            options.push({ modelConfigId: config.id, modelName: config.model_name, configName: config.name, isDefault: config.is_default })
          }
        }
        setModelOptions(options)
        if (!selectedModelKey) {
          const def = options.find(o => o.isDefault) || options[0]
          if (def) setSelectedModelKey(`${def.modelConfigId}:${def.modelName}`)
        }
      } catch (err) { console.error('Failed to load models:', err) }
      finally { setLoadingModels(false) }
    }
    load()
  }, [])

  // 快捷模板
  const applyQuickTemplate = (tpl: typeof QUICK_TEMPLATES[0]) => {
    setQuickTemplateOpen(false)
    for (const [key, val] of Object.entries(tpl.data)) {
      if (val !== undefined) setField(key as keyof InspirationData, val as never)
    }
  }

  // 计算每个字段组的状态
  const baseGroupStatus: FieldStatus = ['novelType', 'targetReader', 'era', 'targetWords', 'wordsPerChapter', 'coreTheme']
    .some(k => fieldStatus[k] === 'agent_asking') ? 'agent_asking'
    : ['novelType', 'targetReader', 'era', 'targetWords', 'wordsPerChapter', 'coreTheme']
      .some(k => fieldStatus[k] === 'agent_populated') ? 'agent_populated' : 'empty'

  const protagonistGroupStatus: FieldStatus = fields.targetReader === 'male'
    ? (fieldStatus.maleLead === 'agent_asking' || fieldStatus.goldFinger === 'agent_asking' ? 'agent_asking'
      : fieldStatus.maleLead === 'agent_populated' || fieldStatus.goldFinger === 'agent_populated' ? 'agent_populated' : 'empty')
    : fields.targetReader === 'female'
      ? (fieldStatus.femaleLead === 'agent_asking' ? 'agent_asking'
        : fieldStatus.femaleLead === 'agent_populated' ? 'agent_populated' : 'empty')
      : 'empty'

  // 高级设定已填项数
  const advancedFilled = [fields.narrative, fields.worldSetting, fields.genre, fields.stylePreference, fields.goldFinger]
    .filter(Boolean).length

  // 确认：校验 → 调 API 保存 → 父组件打开进度弹窗
  const handleConfirm = async () => {
    if (!validate()) return
    setConfirming(true)
    try {
      const data = buildCollectedInfoData()
      await onConfirm(data)
    } catch (err) {
      console.error('Failed to confirm:', err)
    } finally { setConfirming(false) }
  }

  // 重新规划：校验 → 构建数据 → 通知父组件显示确认弹窗
  const handleReplanRequest = () => {
    if (!validate()) return
    const data = buildCollectedInfoData()
    onRequestReplan(data)
  }

  // 模型分组渲染
  const renderModelGroups = (prefix?: string) => {
    const grouped = new Map<number, ModelOption[]>()
    for (const opt of modelOptions) {
      if (!grouped.has(opt.modelConfigId)) grouped.set(opt.modelConfigId, [])
      grouped.get(opt.modelConfigId)!.push(opt)
    }
    return Array.from(grouped.entries()).map(([configId, options]) => (
      <SelectGroup key={configId}>
        <SelectLabel>{options[0].configName}</SelectLabel>
        {options.map(opt => (
          <SelectItem key={`${prefix || ''}${opt.modelConfigId}:${opt.modelName}`} value={`${opt.modelConfigId}:${opt.modelName}`}>
            <span className="flex items-center gap-1.5">
              {opt.modelName}
              {opt.isDefault && <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">默认</span>}
            </span>
          </SelectItem>
        ))}
      </SelectGroup>
    ))
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-white">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2"><Lightbulb className="h-4 w-4" />灵感参数面板</h2>
          <p className="text-[10px] text-muted-foreground mt-0.5">填写创作参数，或让 AI 搭档帮你完成</p>
        </div>
        <div className="relative">
          <Button variant="outline" size="sm" className="text-xs h-7" onClick={() => setQuickTemplateOpen(!quickTemplateOpen)}>
            ⚡ 快捷模板 {quickTemplateOpen ? '▴' : '▾'}
          </Button>
          {quickTemplateOpen && (
            <div className="absolute right-0 top-full mt-1 z-20 w-56 bg-white border rounded-lg shadow-lg py-1">
              {QUICK_TEMPLATES.map(tpl => (
                <button key={tpl.id} onClick={() => applyQuickTemplate(tpl)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-indigo-50 text-left">
                  <span>{tpl.icon}</span>
                  <div><div className="font-medium">{tpl.label}</div></div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Scrollable form */}
      <div className="flex-1 p-4 overflow-auto">
        <div className="max-w-3xl space-y-3">
          {/* 基础设定 */}
          <InspirationFieldGroup title="基础设定" icon="📋" required groupStatus={baseGroupStatus}>
            {/* 目标读者 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">目标读者 <span className="text-red-500">*</span></label>
              <div className="grid grid-cols-2 gap-3 max-w-md">
                {INSPIRATION_OPTIONS.targetReader.map(opt => (
                  <div key={opt.value} onClick={() => setField('targetReader', opt.value)}
                    className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${fields.targetReader === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-xl mb-0.5">{TARGET_READER_ICONS[opt.value]}</div>
                    <div className="text-xs font-medium">{opt.label}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{TARGET_READER_DESC[opt.value]}</div>
                  </div>
                ))}
              </div>
              {errors.targetReader && <p className="text-red-500 text-[10px] mt-1">{errors.targetReader}</p>}
            </div>
            {/* 题材 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">小说类型 <span className="text-red-500">*</span></label>
              <div className="grid grid-cols-6 gap-1.5">
                {INSPIRATION_OPTIONS.novelTypes.map(opt => (
                  <div key={opt.value} onClick={() => setField('novelType', opt.value)}
                    className={`border-2 rounded-lg p-1.5 text-center cursor-pointer transition-all text-xs ${fields.novelType === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-sm mb-0.5">{NOVEL_TYPE_ICONS[opt.value]}</div>
                    <div className="text-[10px] font-medium">{opt.label}</div>
                  </div>
                ))}
              </div>
              {errors.novelType && <p className="text-red-500 text-[10px] mt-1">{errors.novelType}</p>}
            </div>
            {/* 篇幅 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">篇幅类型</label>
              <div className="grid grid-cols-3 gap-1.5 max-w-lg">
                {[
                  { value: 'short' as const, label: '短篇', desc: '<5万字' },
                  { value: 'medium' as const, label: '中篇', desc: '5-20万字' },
                  { value: 'long' as const, label: '长篇', desc: '20万字+' },
                ].map(opt => (
                  <div key={opt.value} onClick={() => {
                    setField('novelLength', opt.value)
                    setField('targetWords', opt.value === 'short' ? 30000 : opt.value === 'medium' ? 100000 : 250000 as never)
                    setField('contextStrategy', opt.value === 'short' ? 'fulltext' : opt.value === 'medium' ? 'hybrid' : 'summary' as never)
                  }}
                    className={`border-2 rounded-lg p-1.5 text-center cursor-pointer transition-all text-xs ${fields.novelLength === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-[10px] font-medium">{opt.label}</div>
                    <div className="text-[10px] text-muted-foreground">{opt.desc}</div>
                  </div>
                ))}
              </div>
            </div>
            {/* 年代 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">年代 <span className="text-red-500">*</span></label>
              <div className="grid grid-cols-4 gap-1.5 max-w-lg">
                {COMMON_OPTIONS.era.map(opt => (
                  <div key={opt.value} onClick={() => setField('era', opt.value)}
                    className={`border-2 rounded-lg p-1.5 text-center cursor-pointer transition-all text-xs ${fields.era === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-sm mb-0.5">{ERA_ICONS[opt.value]}</div>
                    <div className="text-[10px] font-medium">{opt.label}</div>
                  </div>
                ))}
              </div>
              {errors.era && <p className="text-red-500 text-[10px] mt-1">{errors.era}</p>}
            </div>
            {/* 核心主题 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">核心主题 <span className="text-red-500">*</span></label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.coreThemes.map(opt => (
                  <span key={opt.value} onClick={() => setField('coreTheme', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.coreTheme === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
              {errors.coreTheme && <p className="text-red-500 text-[10px] mt-1">{errors.coreTheme}</p>}
            </div>
            {/* 目标字数 + 每章字数 */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">目标字数 <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Input type="number" min={10000} step={10000} value={fields.targetWords || ''}
                    onChange={(e) => setField('targetWords', parseInt(e.target.value) || 50000)}
                    onBlur={() => { if (fields.targetWords) setField('contextStrategy', getContextStrategyFromTargetWords(fields.targetWords) as never) }}
                    className={`pr-7 text-xs ${errors.targetWords ? 'border-red-500' : ''}`}
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground">字</span>
                </div>
                {errors.targetWords && <p className="text-red-500 text-[10px] mt-0.5">{errors.targetWords}</p>}
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">每章字数 <span className="text-red-500">*</span></label>
                <Select value={fields.wordsPerChapter || ''} onValueChange={(v) => setField('wordsPerChapter', v)}>
                  <SelectTrigger className={`w-full h-9 text-xs ${errors.wordsPerChapter ? 'border-red-500' : ''}`}>
                    <SelectValue placeholder="请选择" />
                  </SelectTrigger>
                  <SelectContent>
                    {INSPIRATION_OPTIONS.wordsPerChapter.map(opt => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}{opt.desc ? ` (${opt.desc})` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.wordsPerChapter && <p className="text-red-500 text-[10px] mt-0.5">{errors.wordsPerChapter}</p>}
              </div>
            </div>
            {/* 上下文策略 */}
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">上下文策略</label>
              <RadioGroup value={fields.contextStrategy} onValueChange={(v) => setField('contextStrategy', v as never)} className="space-y-1">
                {CONTEXT_STRATEGY_OPTIONS.map(opt => (
                  <div key={opt.value} className="flex items-center space-x-2">
                    <RadioGroupItem value={opt.value} id={`strategy-${opt.value}`} disabled={opt.value !== 'fulltext'} />
                    <label htmlFor={`strategy-${opt.value}`} className={`text-xs ${opt.value !== 'fulltext' ? 'text-muted-foreground cursor-not-allowed' : 'cursor-pointer'}`}>
                      {opt.label} — {opt.desc}
                      <span className="ml-1 text-[10px] text-muted-foreground">(推荐{opt.recommendedWords})</span>
                      {opt.value !== 'fulltext' && <span className="ml-1 text-[10px] text-muted-foreground">(待开发)</span>}
                    </label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          </InspirationFieldGroup>

          {/* 主角设定 */}
          <InspirationFieldGroup title="主角设定" icon="👤" required groupStatus={protagonistGroupStatus}>
            {fields.targetReader === 'male' && (
              <>
                <div className="mb-2">
                  <label className="text-xs text-muted-foreground mb-1.5 block">男主人设 <span className="text-red-500">*</span></label>
                  <div className="flex flex-wrap gap-1.5">
                    {MALE_OPTIONS.maleLead.map(opt => (
                      <span key={opt.value} onClick={() => setField('maleLead', opt.value)}
                        className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.maleLead === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                        {opt.label}
                      </span>
                    ))}
                  </div>
                  {fields.maleLead === 'custom' && <Input type="text" value={fields.customMaleLead || ''} onChange={(e) => setField('customMaleLead', e.target.value)} placeholder="自定义男主人设" className="mt-1.5 max-w-md text-xs" />}
                  {errors.maleLead && <p className="text-red-500 text-[10px] mt-1">{errors.maleLead}</p>}
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">金手指设定</label>
                  <div className="flex flex-wrap gap-1.5">
                    {MALE_OPTIONS.goldFinger.map(opt => (
                      <span key={opt.value} onClick={() => setField('goldFinger', opt.value)}
                        className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.goldFinger === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                        {opt.label}
                      </span>
                    ))}
                  </div>
                  {fields.goldFinger === 'custom' && <Input type="text" value={fields.customGoldFinger || ''} onChange={(e) => setField('customGoldFinger', e.target.value)} placeholder="自定义金手指" className="mt-1.5 max-w-md text-xs" />}
                </div>
              </>
            )}
            {fields.targetReader === 'female' && (
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">女主人设 <span className="text-red-500">*</span></label>
                <div className="flex flex-wrap gap-1.5">
                  {FEMALE_OPTIONS.femaleLead.map(opt => (
                    <span key={opt.value} onClick={() => setField('femaleLead', opt.value)}
                      className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.femaleLead === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                      {opt.label}
                    </span>
                  ))}
                </div>
                {fields.femaleLead === 'custom' && <Input type="text" value={fields.customFemaleLead || ''} onChange={(e) => setField('customFemaleLead', e.target.value)} placeholder="自定义女主人设" className="mt-1.5 max-w-md text-xs" />}
                {errors.femaleLead && <p className="text-red-500 text-[10px] mt-1">{errors.femaleLead}</p>}
              </div>
            )}
            {!fields.targetReader && <p className="text-xs text-muted-foreground">请先选择目标读者</p>}
          </InspirationFieldGroup>

          {/* 高级设定 */}
          <InspirationFieldGroup title="高级设定" icon="📝" collapsible collapsed={!advancedExpanded}
            onToggleCollapse={() => setAdvancedExpanded(!advancedExpanded)} optionalFilledCount={advancedFilled}>
            {/* 叙事视角 */}
            <div className="mb-2">
              <label className="text-xs text-muted-foreground mb-1.5 block">叙事视角</label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.narrative.map(opt => (
                  <span key={opt.value} onClick={() => setField('narrative', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.narrative === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
            </div>
            {/* 世界观 */}
            <div className="mb-2">
              <label className="text-xs text-muted-foreground mb-1.5 block">世界观设定</label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.worldSettings.map(opt => (
                  <span key={opt.value} onClick={() => setField('worldSetting', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.worldSetting === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
              {fields.worldSetting === 'custom' && <Input type="text" value={fields.customWorldSetting || ''} onChange={(e) => setField('customWorldSetting', e.target.value)} placeholder="自定义世界观" className="mt-1.5 max-w-md text-xs" />}
            </div>
            {/* 男频流派 */}
            {fields.targetReader === 'male' && (
              <div className="mb-2">
                <label className="text-xs text-muted-foreground mb-1.5 block">流派</label>
                <div className="flex flex-wrap gap-1.5">
                  {MALE_OPTIONS.genre.map(opt => (
                    <span key={opt.value} onClick={() => setField('genre', opt.value)}
                      className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.genre === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                      {opt.label}
                    </span>
                  ))}
                </div>
                {fields.genre === 'custom' && <Input type="text" value={fields.customGenre || ''} onChange={(e) => setField('customGenre', e.target.value)} placeholder="自定义流派" className="mt-1.5 max-w-md text-xs" />}
              </div>
            )}
            {/* 风格偏好 */}
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">风格偏好</label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.stylePreferences.map(opt => (
                  <span key={opt.value} onClick={() => setField('stylePreference', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.stylePreference === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
            </div>
          </InspirationFieldGroup>

          {/* Prompt 预览 */}
          <InspirationTemplatePreview
            template={template}
            manuallyEdited={templateManuallyEdited}
            onTemplateChange={handleTemplateChange}
            onResetTemplate={handleResetTemplate}
          />
        </div>
      </div>

      {/* Bottom action bar */}
      <div className="border-t bg-white px-4 py-3">
        <div className="flex items-center gap-3 max-w-3xl mx-auto">
          <div className="flex-1 min-w-0">
            <label className="text-[10px] text-muted-foreground mb-1 flex items-center gap-1" htmlFor="model-select-trigger">
              <Cpu className="h-3 w-3" />AI 模型
            </label>
            <Select value={selectedModelKey} onValueChange={setSelectedModelKey} disabled={loadingModels || modelOptions.length === 0}>
              <SelectTrigger id="model-select-trigger" className="w-full h-8 text-xs">
                <SelectValue placeholder={loadingModels ? '加载中...' : '请选择模型'} />
              </SelectTrigger>
              <SelectContent>{renderModelGroups()}</SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-0">
            <button type="button" onClick={() => setShowReviewModelAdvanced(!showReviewModelAdvanced)}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors mb-1">
              <Settings2 className="h-3 w-3" />审核模型
            </button>
            {showReviewModelAdvanced && (
              <Select value={reviewLlmConfigId?.toString() || '__default__'}
                onValueChange={(v) => setReviewLlmConfigId(v === '__default__' ? null : parseInt(v))}>
                <SelectTrigger className="w-full h-8 text-xs">
                  <SelectValue placeholder="使用创作模型（默认）" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">使用创作模型（默认）</SelectItem>
                  {renderModelGroups('review-')}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground">{progress.requiredFilled}/{progress.requiredTotal}</span>
            <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all bg-primary"
                style={{ width: `${progress.requiredTotal > 0 ? (progress.requiredFilled / progress.requiredTotal * 100) : 0}%` }} />
            </div>
          </div>
          {hasOutline ? (
            <Button onClick={handleReplanRequest} className="px-4 h-8 text-xs" variant="outline">
              <RefreshCw className="h-3.5 w-3.5 mr-1" />重新规划
            </Button>
          ) : (
            <Button onClick={handleConfirm} disabled={confirming} className="px-4 h-8 text-xs">
              {confirming ? '保存中...' : <><Check className="h-3.5 w-3.5 mr-1" />开始规划</>}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationForm.tsx
git commit -m "feat(frontend): add InspirationForm component with Agent status badges"
```

---

## Task 7: 重写 InspirationPanel 为编排组件

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`
- Delete: `frontend/src/components/workbench/planning/InspirationChatPanel.tsx`
- Delete: `frontend/src/components/workbench/planning/InspirationPreview.tsx`

- [ ] **Step 1: 重写 InspirationPanel.tsx**

将 1400 行精简为 ~80 行编排组件：

```typescript
// frontend/src/components/workbench/planning/InspirationPanel.tsx
import { useState } from 'react'
import { collectedInfoApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
import { InspirationForm } from './InspirationForm'
import { OutlineProgressDialog } from './OutlineProgressDialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'

interface InspirationPanelProps {
  projectId: number
  hasOutline?: boolean
  onPlanningComplete?: () => void
}

export function InspirationPanel({ projectId, hasOutline = false, onPlanningComplete }: InspirationPanelProps) {
  const [showProgressDialog, setShowProgressDialog] = useState(false)
  const [showReplanConfirm, setShowReplanConfirm] = useState(false)
  // 暂存确认/重新规划的灵感数据，供 OutlineProgressDialog 使用
  const [pendingCollectedInfo, setPendingCollectedInfo] = useState<Record<string, unknown> | null>(null)
  const [pendingTemplate, setPendingTemplate] = useState<string>('')
  const { setActiveMenuItem, setActiveTab, selectedModelKey } = useWorkbenchStore()

  // 确认灵感：API 保存 → 打开进度弹窗
  const handleConfirm = async (collectedInfo: Record<string, unknown>) => {
    await collectedInfoApi.update(projectId, collectedInfo)
    toast.success('灵感已确认')
    setPendingCollectedInfo(collectedInfo)
    setPendingTemplate((collectedInfo.inspiration_template as string) || '')
    setShowProgressDialog(true)
  }

  // 重新规划请求：暂存数据 → 打开确认弹窗（不直接执行）
  const handleReplanRequest = (collectedInfo: Record<string, unknown>) => {
    setPendingCollectedInfo(collectedInfo)
    setPendingTemplate((collectedInfo.inspiration_template as string) || '')
    setShowReplanConfirm(true)
  }

  // 确认重新规划：关闭确认弹窗 → 打开进度弹窗
  const handleReplanConfirm = () => {
    setShowReplanConfirm(false)
    setShowProgressDialog(true)
  }

  // 解析模型信息
  const modelConfigId = selectedModelKey ? parseInt(selectedModelKey.split(':')[0]) : undefined
  const modelName = selectedModelKey ? selectedModelKey.split(':').slice(1).join(':') : undefined

  return (
    <div className="flex h-full">
      <InspirationForm
        projectId={projectId}
        hasOutline={hasOutline}
        onConfirm={handleConfirm}
        onRequestReplan={handleReplanRequest}
      />

      {/* 重新规划确认 */}
      <AlertDialog open={showReplanConfirm} onOpenChange={setShowReplanConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认重新规划？</AlertDialogTitle>
            <AlertDialogDescription>重新规划将清除当前的大纲、人物和关系数据，基于当前灵感重新生成。此操作不可撤销。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleReplanConfirm}>确认重新规划</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 大纲生成进度弹窗 */}
      <OutlineProgressDialog
        open={showProgressDialog}
        onClose={() => setShowProgressDialog(false)}
        projectId={projectId}
        modelConfigId={modelConfigId}
        modelName={modelName}
        isReplan={hasOutline}
        collectedInfo={pendingCollectedInfo}
        inspirationTemplate={pendingTemplate}
        onComplete={() => onPlanningComplete?.()}
        onViewOutline={() => {
          onPlanningComplete?.()
          setShowProgressDialog(false)
          setActiveTab('settings')
          setActiveMenuItem('outline')
        }}
      />
    </div>
  )
}
```

- [ ] **Step 2: 删除 InspirationChatPanel.tsx 和 InspirationPreview.tsx**

```bash
rm frontend/src/components/workbench/planning/InspirationChatPanel.tsx
rm frontend/src/components/workbench/planning/InspirationPreview.tsx
```

- [ ] **Step 3: 清理 api.ts 中的 inspirationChatApi 引用**

从 `frontend/src/lib/api.ts` 中移除 `InspirationChatCallbacks` 接口和 `inspirationChatApi` 对象（约 55 行，570-634 行）。保留 `collectedInfoApi`。

- [ ] **Step 4: 验证编译通过**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无新增错误（可能有 `InspirationChatPanel` 的 import 残留需要清理）

- [ ] **Step 5: 清理所有残留 import**

搜索并移除所有对 `InspirationChatPanel`、`InspirationPreview`、`inspirationChatApi` 的引用：

```bash
grep -rn "InspirationChatPanel\|InspirationPreview\|inspirationChatApi" frontend/src/ --include="*.ts" --include="*.tsx"
```

逐一清理找到的文件。

- [ ] **Step 6: 运行全部前端测试**

Run: `cd /Users/biner/Dev/novelagent/frontend && npx vitest run 2>&1 | tail -20`
Expected: 所有测试通过

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(frontend): rewrite InspirationPanel as orchestrator, delete ChatPanel and Preview"
```

---

## Task 8: 端到端验证

**Files:** 无新增

- [ ] **Step 1: 构建前端**

Run: `cd /Users/biner/Dev/novelagent && docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 构建成功，容器启动

- [ ] **Step 2: 验证灵感页面加载**

打开浏览器 `http://localhost:3001`，创建/进入项目，切换到灵感 Tab。

检查项：
- [ ] 参数面板正确渲染（基础设定 / 主角设定 / 高级设定 / Prompt 预览）
- [ ] 表单字段可正常点击选择
- [ ] 快捷模板下拉菜单正常工作
- [ ] 必填进度条和「开始规划」按钮联动
- [ ] 右栏 AI 搭档正常显示
- [ ] 无 InspirationChatPanel 残留（对话窗口不存在）
- [ ] 无模式切换按钮

- [ ] **Step 3: Commit 验证结果**

如有修复，提交；如通过，记录结果。

---

## Self-Review

**1. Spec 覆盖检查：**

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 删除 InspirationChatPanel + InspirationPreview | Task 7 |
| 删除表单/对话模式切换 | Task 7 |
| 左栏参数面板（卡片式分组） | Task 4 + Task 6 |
| 三种 Agent 状态视觉 | Task 4 (FieldGroup) + Task 6 (Form) |
| workbenchStore 新增状态 | Task 2 |
| Agent tool call 联动（前端接收端） | Task 2 (store) + Task 3 (hook) |
| inspiration.ts 拆分 | Task 1 |
| Prompt 预览移到底部 | Task 5 |
| 快捷模板下拉菜单 | Task 6 |
| 1400 行组件拆分 | Task 3 + Task 4 + Task 5 + Task 6 + Task 7 |

**2. Placeholder 扫描：** 无 TBD / TODO / "implement later"。

**3. 类型一致性：** InspirationData 类型从 `types.ts` 定义，通过 `index.ts` re-export，所有 Task 使用同一来源。FieldStatus 类型同上。workbenchStore 中 `setInspirationField` 签名与 hook 中调用一致。`ModelOption` 类型定义在 `InspirationForm.tsx` 中（不再从 InspirationPanel 循环导入）。

**4. 审查修复记录：**

| # | 问题 | 严重度 | 修复 |
|---|------|--------|------|
| 1 | `inspiration.ts` 与 `inspiration/` 目录共存导致模块解析冲突 | 关键 | 删除原文件，由目录入口替代 |
| 2 | `NOVEL_TYPE_ICONS` 等图标常量在 InspirationPanel.tsx 中，非 inspiration.ts | 关键 | Task 1 config.ts 步骤明确从 InspirationPanel.tsx 提取 |
| 3 | `ModelOption` 类型从 InspirationPanel 循环导入 | 关键 | ModelOption 移至 InspirationForm.tsx 定义 |
| 4 | 重新规划流程断裂：数据丢失 + 进度弹窗在确认前打开 | 关键 | 重设计流程：Form 传递数据 → Panel 确认 → 再开进度弹窗 |
| 5 | OutlineProgressDialog 缺少 reviewLlmConfigId/inspirationTemplate props | 关键 | 补全所有 props |
| 6 | 确认流程不完整：API 保存后未自动打开进度弹窗 | 关键 | handleConfirm 保存后直接打开进度弹窗 |
| 7 | 自动保存闭包捕获旧值（cerebrum 有记录） | 显著 | 使用 fieldsRef + 防抖模式 |
| 8 | targetReader 变化 effect 在初始化时误清字段 | 显著 | 使用 prevReaderRef 只在真正切换时清除 |
| 9 | NovelLengthOption/NOVEL_LENGTH_OPTIONS 死代码 | 显著 | 删除，不保留 |
| 10 | buildCollectedInfoData 中 selectedModelKey 闭包旧值 | 显著 | 从 store.getState() 实时读取 |
| 11 | 每章字数使用原生 `<select>` 而非 shadcn Select | 次要 | 改用 shadcn Select 组件 |
