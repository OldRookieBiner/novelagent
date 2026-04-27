# 灵感采集选项优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展灵感采集选项，新增年代、流派字段，拆分主角设定为男主人设/女主人设，重构选项配置支持男女频差异化。

**Architecture:** 前端重构选项配置为分层结构（通用选项 + 男频/女频专属选项），表单根据目标读者动态显示对应选项；后端更新 Schema 和提示词模板。

**Tech Stack:** React + TypeScript (前端), FastAPI + Pydantic (后端)

---

## 文件结构

| 文件 | 职责 |
|-----|------|
| `frontend/src/lib/inspiration.ts` | 选项配置和数据类型定义 |
| `frontend/src/components/project/InspirationForm.tsx` | 灵感采集表单组件 |
| `backend/app/schemas/outline.py` | 后端 Schema 定义 |
| `backend/app/agents/prompts.py` | Agent 提示词模板 |

---

## Task 1: 前端选项配置重构

**Files:**
- Modify: `frontend/src/lib/inspiration.ts`

- [ ] **Step 1: 重构选项配置为分层结构**

将原有的 `INSPIRATION_OPTIONS` 重构为分层结构，区分通用选项和男频/女频专属选项。

```typescript
// frontend/src/lib/inspiration.ts

export interface SelectOption {
  value: string
  label: string
  desc?: string      // 仅用于每章字数选项
}

export interface InspirationData {
  // 必填项
  novelType: string
  targetWords: number
  coreTheme: string
  targetReader: string
  era: string                    // 新增：年代
  wordsPerChapter: string
  maleLead?: string              // 新增：男主人设
  customMaleLead?: string
  femaleLead?: string            // 新增：女主人设
  customFemaleLead?: string
  // 选填项
  worldSetting?: string
  customWorldSetting?: string
  narrative?: string
  genre?: string                 // 新增：流派
  goldFinger?: string
  customGoldFinger?: string
  stylePreference?: string
}

// 通用选项（男女频共用）
const COMMON_OPTIONS = {
  novelTypes: [
    { value: 'xuanhuan', label: '玄幻' },
    { value: 'kehuan', label: '科幻' },
    { value: 'dushi', label: '都市' },
    { value: 'yanqing', label: '言情' },
    { value: 'xuanyi', label: '悬疑' },
    { value: 'lishi', label: '历史' },
  ],

  era: [
    { value: 'ancient', label: '古代' },
    { value: 'modern', label: '现代' },
    { value: 'future', label: '未来' },
    { value: 'fictional', label: '架空' },
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
    { value: 'xianxia', label: '仙侠世界' },
    { value: 'western_fantasy', label: '西幻大陆' },
    { value: 'apocalypse', label: '末世废土' },
    { value: 'urban_ability', label: '都市异能' },
    { value: 'palace', label: '宫廷宅斗' },
    { value: 'wuxia', label: '武侠江湖' },
    { value: 'interstellar', label: '星际帝国' },
    { value: 'game_world', label: '游戏世界' },
    { value: 'supernatural', label: '灵异悬疑' },
    { value: 'custom', label: '自定义' },
  ],

  narrative: [
    { value: 'first', label: '第一人称' },
    { value: 'third', label: '第三人称' },
  ],

  wordsPerChapter: [
    { value: '1500-2000', label: '1500-2000字', desc: '短章' },
    { value: '2000-2500', label: '2000-2500字', desc: '标准·番茄推荐' },
    { value: '2500-3000', label: '2500-3000字', desc: '中章·七猫推荐' },
    { value: '3000-5000', label: '3000-5000字', desc: '长章' },
    { value: 'custom', label: '自定义' },
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

  stylePreferences: [
    { value: 'humorous', label: '轻松幽默' },
    { value: 'passionate', label: '热血激昂' },
    { value: 'aesthetic', label: '细腻唯美' },
    { value: 'dark', label: '暗黑深沉' },
    { value: 'tense', label: '紧张刺激' },
  ],

  genre: [
    { value: 'brain_hole', label: '脑洞文' },
    { value: 'trash_flow', label: '废柴流' },
    { value: 'mortal_flow', label: '凡人流' },
    { value: 'prehistoric', label: '洪荒流' },
    { value: 'infinite', label: '无限流' },
  ],

  targetReader: [
    { value: 'male', label: '男频' },
    { value: 'female', label: '女频' },
  ],
}

// 男频专属选项
const MALE_OPTIONS = {
  maleLead: [
    { value: 'genius', label: '少年天才' },
    { value: 'transmigrator', label: '穿越者' },
    { value: 'reborn', label: '重生者' },
    { value: 'underdog', label: '草根逆袭' },
    { value: 'ordinary', label: '普通人' },
    { value: 'custom', label: '自定义' },
  ],
  genre: COMMON_OPTIONS.genre,  // 暂时与通用相同，预留扩展
}

// 女频专属选项
const FEMALE_OPTIONS = {
  femaleLead: [
    { value: 'rich_beauty', label: '白富美' },
    { value: 'strong_woman', label: '女强人' },
    { value: 'sweet_naive', label: '傻白甜' },
    { value: 'cinderella', label: '灰姑娘' },
    { value: 'transmigrator', label: '穿越女' },
    { value: 'reborn', label: '重生女' },
    { value: 'custom', label: '自定义' },
  ],
  genre: COMMON_OPTIONS.genre,  // 暂时与通用相同，预留扩展
}

// 根据目标读者获取完整选项
export function getInspirationOptions(targetReader?: 'male' | 'female') {
  if (!targetReader) {
    return COMMON_OPTIONS
  }
  return {
    ...COMMON_OPTIONS,
    ...(targetReader === 'male' ? MALE_OPTIONS : FEMALE_OPTIONS),
  }
}

// 保持向后兼容的导出
export const INSPIRATION_OPTIONS = {
  ...COMMON_OPTIONS,
  protagonistTypes: MALE_OPTIONS.maleLead,  // 向后兼容
}
```

- [ ] **Step 2: 更新 getOptionLabel 函数**

保持不变，已支持通用选项数组。

- [ ] **Step 3: 更新 getWordsPerChapterDisplay 函数**

保持不变，已支持 InspirationData。

- [ ] **Step 4: 更新 generateInspirationTemplate 函数**

更新 Markdown 模板生成函数，包含新增字段。

```typescript
// 生成 Markdown 模板
export function generateInspirationTemplate(data: InspirationData): string {
  const options = getInspirationOptions(data.targetReader as 'male' | 'female')
  const novelType = getOptionLabel(options.novelTypes, data.novelType)
  const era = getOptionLabel(options.era, data.era)
  const targetWords = data.targetWords ? `${data.targetWords.toLocaleString()}字` : '未设置'
  const wordsPerChapter = getWordsPerChapterDisplay(data)
  const coreTheme = getOptionLabel(options.coreThemes, data.coreTheme)
  const worldSetting = data.customWorldSetting || getOptionLabel(options.worldSettings, data.worldSetting)
  const genre = getOptionLabel(options.genre, data.genre)
  const narrative = getOptionLabel(options.narrative, data.narrative)
  const goldFinger = data.customGoldFinger || getOptionLabel(options.goldFinger, data.goldFinger)
  const style = getOptionLabel(options.stylePreferences, data.stylePreference)

  // 根据目标读者显示对应主角设定
  let protagonistLine = ''
  if (data.targetReader === 'male') {
    const maleLead = data.customMaleLead || getOptionLabel(MALE_OPTIONS.maleLead, data.maleLead)
    protagonistLine = `- **男主**：${maleLead || '未设置'}`
  } else if (data.targetReader === 'female') {
    const femaleLead = data.customFemaleLead || getOptionLabel(FEMALE_OPTIONS.femaleLead, data.femaleLead)
    protagonistLine = `- **女主**：${femaleLead || '未设置'}`
  }

  return `# 小说创作灵感

## 基本信息

- **目标读者**：${data.targetReader === 'male' ? '男频' : data.targetReader === 'female' ? '女频' : '未设置'}
- **小说类型**：${novelType || '未设置'}
- **年代设定**：${era || '未设置'}
- **目标字数**：${targetWords}
- **每章字数**：${wordsPerChapter || '未设置'}

## 主角设定

${protagonistLine}

## 核心设定

- **核心主题**：${coreTheme || '未设置'}
- **世界观**：${worldSetting || '未设置'}
- **流派**：${genre || '未设置'}
- **金手指**：${goldFinger || '未设置'}

## 风格

- **风格偏好**：${style || '未设置'}

## 叙事

- **叙事视角**：${narrative || '未设置'}

## 补充灵感

> 在下方添加更多灵感细节...

-

-

`
}
```

- [ ] **Step 5: 更新 parseTemplateToData 函数**

更新模板解析函数，支持新增字段。

```typescript
// 从模板解析灵感数据（用于回显）
export function parseTemplateToData(template: string): Partial<InspirationData> {
  const lines = template.split('\n')
  const data: Partial<InspirationData> = {}

  for (const line of lines) {
    // 原有字段解析
    if (line.includes('**目标读者**')) {
      const value = line.split('：')[1]?.trim()
      if (value === '男频') data.targetReader = 'male'
      else if (value === '女频') data.targetReader = 'female'
    }
    if (line.includes('**小说类型**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.novelTypes.find(o => o.label === value)
      if (option) data.novelType = option.value
    }
    if (line.includes('**年代设定**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.era.find(o => o.label === value)
      if (option) data.era = option.value
    }
    if (line.includes('**目标字数**')) {
      const value = line.split('：')[1]?.trim()
      const numStr = value?.replace(/[字,，]/g, '').replace(/万/g, '0000')
      if (numStr && !isNaN(parseInt(numStr))) {
        data.targetWords = parseInt(numStr)
      }
    }
    if (line.includes('**每章字数**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.wordsPerChapter.find(o => o.label === value)
      if (option) data.wordsPerChapter = option.value
      else if (value && value !== '未设置') {
        const numMatch = value.match(/(\d+)/)
        if (numMatch) {
          data.wordsPerChapter = 'custom'
          data.customWordsPerChapter = parseInt(numMatch[1])
        }
      }
    }
    if (line.includes('**叙事视角**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.narrative.find(o => o.label === value)
      if (option) data.narrative = option.value
    }
    if (line.includes('**核心主题**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.coreThemes.find(o => o.label === value)
      if (option) data.coreTheme = option.value
    }
    if (line.includes('**世界观**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.worldSettings.find(o => o.label === value)
      if (option) data.worldSetting = option.value
      else if (value && value !== '未设置') data.customWorldSetting = value
    }
    if (line.includes('**流派**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.genre.find(o => o.label === value)
      if (option) data.genre = option.value
    }
    if (line.includes('**金手指**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.goldFinger.find(o => o.label === value)
      if (option) data.goldFinger = option.value
      else if (value && value !== '未设置') data.customGoldFinger = value
    }
    if (line.includes('**风格偏好**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.stylePreferences.find(o => o.label === value)
      if (option) data.stylePreference = option.value
    }
    // 新增：男主设定
    if (line.includes('**男主**')) {
      const value = line.split('：')[1]?.trim()
      const option = MALE_OPTIONS.maleLead.find(o => o.label === value)
      if (option) data.maleLead = option.value
      else if (value && value !== '未设置') data.customMaleLead = value
    }
    // 新增：女主设定
    if (line.includes('**女主**')) {
      const value = line.split('：')[1]?.trim()
      const option = FEMALE_OPTIONS.femaleLead.find(o => o.label === value)
      if (option) data.femaleLead = option.value
      else if (value && value !== '未设置') data.customFemaleLead = value
    }
  }

  return data
}
```

- [ ] **Step 6: 运行前端类型检查**

Run: `cd frontend && npm run build`
Expected: 无 TypeScript 错误

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/inspiration.ts
git commit -m "refactor(frontend): restructure inspiration options with male/female separation

- Add era, genre, maleLead, femaleLead fields
- Split options into COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS
- Add getInspirationOptions() for dynamic option loading
- Update generateInspirationTemplate() with new fields
- Update parseTemplateToData() for new fields

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: 前端表单 UI 更新

**Files:**
- Modify: `frontend/src/components/project/InspirationForm.tsx`

- [ ] **Step 1: 新增年代字段状态和 UI**

在基本设定区域新增年代选择 UI。

```tsx
// 在 InspirationForm 组件中添加状态
const [era, setEra] = useState(initialData?.era || '')

// 年代图标
const ERA_ICONS: Record<string, string> = {
  ancient: '🏛️',
  modern: '🏙️',
  future: '🚀',
  fictional: '🌐',
}

// 在基本设定区域，小说类型后面添加年代选择
{/* 年代设定：卡片选择 */}
<div className="mb-6">
  <div className="text-sm font-medium text-gray-700 mb-3">
    年代设定 <span className="text-red-500">*</span>
  </div>
  <div className="grid grid-cols-4 gap-2">
    {INSPIRATION_OPTIONS.era.map((opt) => (
      <div
        key={opt.value}
        onClick={() => {
          setEra(opt.value)
          if (errors.era) setErrors({ ...errors, era: '' })
        }}
        className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${
          era === opt.value
            ? 'border-blue-500 bg-blue-50 shadow-sm'
            : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
        }`}
      >
        <div className="text-lg mb-1">{ERA_ICONS[opt.value]}</div>
        <div className="text-sm font-medium">{opt.label}</div>
      </div>
    ))}
  </div>
  {errors.era && <p className="text-red-500 text-xs mt-2">{errors.era}</p>}
</div>
```

- [ ] **Step 2: 新增流派字段状态和 UI**

在进阶设定区域新增流派选择 UI。

```tsx
// 在 InspirationForm 组件中添加状态
const [genre, setGenre] = useState(initialData?.genre || '')

// 在进阶设定区域添加流派选择
{/* 流派设定 */}
<div>
  <div className="text-sm font-medium text-gray-700 mb-2">流派</div>
  <div className="flex flex-wrap gap-2">
    {INSPIRATION_OPTIONS.genre.map((opt) => (
      <span
        key={opt.value}
        onClick={() => setGenre(opt.value)}
        className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
          genre === opt.value
            ? 'bg-blue-500 text-white border-blue-500'
            : 'border-gray-200 hover:border-blue-300'
        }`}
      >
        {opt.label}
      </span>
    ))}
  </div>
</div>
```

- [ ] **Step 3: 替换主角设定为男主人设/女主人设**

根据目标读者动态显示对应的主角设定。

```tsx
// 添加男主人设和女主人设状态
const [maleLead, setMaleLead] = useState(initialData?.maleLead || '')
const [customMaleLead, setCustomMaleLead] = useState(initialData?.customMaleLead || '')
const [femaleLead, setFemaleLead] = useState(initialData?.femaleLead || '')
const [customFemaleLead, setCustomFemaleLead] = useState(initialData?.customFemaleLead || '')

// 删除原有的 protagonist 和 customProtagonist 状态

// 在主角设定区域，根据目标读者显示对应选项
{/* 主角设定：根据目标读者动态显示 */}
<div>
  <div className="text-sm font-medium text-gray-700 mb-2">
    {targetReader === 'male' ? '男主人设' : '女主人设'} <span className="text-red-500">*</span>
  </div>
  {targetReader === 'male' ? (
    <>
      <div className="flex flex-wrap gap-2">
        {INSPIRATION_OPTIONS.maleLead?.map((opt) => (
          <span
            key={opt.value}
            onClick={() => {
              setMaleLead(opt.value)
              if (errors.protagonist) setErrors({ ...errors, protagonist: '' })
            }}
            className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
              maleLead === opt.value
                ? 'bg-blue-500 text-white border-blue-500'
                : 'border-gray-200 hover:border-blue-300'
            }`}
          >
            {opt.label}
          </span>
        ))}
      </div>
      {maleLead === 'custom' && (
        <Input
          type="text"
          value={customMaleLead || ''}
          onChange={(e) => setCustomMaleLead(e.target.value)}
          placeholder="输入自定义男主人设"
          className="mt-2 max-w-md"
        />
      )}
    </>
  ) : targetReader === 'female' ? (
    <>
      <div className="flex flex-wrap gap-2">
        {INSPIRATION_OPTIONS.femaleLead?.map((opt) => (
          <span
            key={opt.value}
            onClick={() => {
              setFemaleLead(opt.value)
              if (errors.protagonist) setErrors({ ...errors, protagonist: '' })
            }}
            className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
              femaleLead === opt.value
                ? 'bg-blue-500 text-white border-blue-500'
                : 'border-gray-200 hover:border-blue-300'
            }`}
          >
            {opt.label}
          </span>
        ))}
      </div>
      {femaleLead === 'custom' && (
        <Input
          type="text"
          value={customFemaleLead || ''}
          onChange={(e) => setCustomFemaleLead(e.target.value)}
          placeholder="输入自定义女主人设"
          className="mt-2 max-w-md"
        />
      )}
    </>
  ) : (
    <p className="text-gray-400 text-sm">请先选择目标读者</p>
  )}
  {errors.protagonist && <p className="text-red-500 text-xs mt-2">{errors.protagonist}</p>}
</div>
```

- [ ] **Step 4: 更新表单验证逻辑**

更新 handleSubmit 中的验证逻辑，添加年代验证，更新主角验证。

```tsx
const handleSubmit = () => {
  const newErrors: Record<string, string> = {}
  if (!targetReader) newErrors.targetReader = '请选择目标读者'
  if (!novelType) newErrors.novelType = '请选择小说类型'
  if (!era) newErrors.era = '请选择年代设定'  // 新增
  if (!targetWords) newErrors.targetWords = '请输入目标字数'
  else if (targetWords < 10000) newErrors.targetWords = '目标字数不能少于1万字'
  if (!wordsPerChapter) newErrors.wordsPerChapter = '请选择每章字数'
  if (!coreTheme) newErrors.coreTheme = '请选择核心主题'

  // 根据目标读者验证主角设定
  if (targetReader === 'male' && !maleLead) {
    newErrors.protagonist = '请选择男主人设'
  }
  if (targetReader === 'female' && !femaleLead) {
    newErrors.protagonist = '请选择女主人设'
  }

  if (Object.keys(newErrors).length > 0) {
    setErrors(newErrors)
    return
  }

  const data: InspirationData = {
    novelType,
    targetWords,
    coreTheme,
    worldSetting,
    customWorldSetting,
    stylePreference,
    targetReader,
    era,                    // 新增
    wordsPerChapter,
    customWordsPerChapter,
    narrative,
    genre,                  // 新增
    maleLead,               // 新增
    customMaleLead,         // 新增
    femaleLead,             // 新增
    customFemaleLead,       // 新增
    goldFinger,
    customGoldFinger,
  }

  clearInspirationDraft()
  onSubmit(data, selectedModelId || undefined)
}
```

- [ ] **Step 5: 更新自动保存草稿逻辑**

更新 useEffect 中的自动保存逻辑，包含新增字段。

```tsx
// 自动保存草稿
useEffect(() => {
  const data: InspirationData = {
    novelType,
    targetWords,
    coreTheme,
    worldSetting,
    customWorldSetting,
    stylePreference,
    targetReader,
    era,                    // 新增
    wordsPerChapter,
    customWordsPerChapter,
    narrative,
    genre,                  // 新增
    maleLead,               // 新增
    customMaleLead,         // 新增
    femaleLead,             // 新增
    customFemaleLead,       // 新增
    goldFinger,
    customGoldFinger,
  }
  if (novelType || targetWords || coreTheme || targetReader || era) {
    saveInspirationDraft(data)
  }
}, [novelType, targetWords, coreTheme, worldSetting, customWorldSetting, stylePreference, targetReader, era, wordsPerChapter, customWordsPerChapter, narrative, genre, maleLead, customMaleLead, femaleLead, customFemaleLead, goldFinger, customGoldFinger])
```

- [ ] **Step 6: 更新加载草稿逻辑**

更新 useEffect 中的加载草稿逻辑。

```tsx
// 加载草稿
useEffect(() => {
  if (!initialData || Object.keys(initialData).length === 0) {
    const draft = loadInspirationDraft()
    if (draft) {
      if (draft.targetReader) setTargetReader(draft.targetReader)
      if (draft.novelType) setNovelType(draft.novelType)
      if (draft.era) setEra(draft.era)                  // 新增
      if (draft.targetWords) setTargetWords(draft.targetWords)
      if (draft.wordsPerChapter) setWordsPerChapter(draft.wordsPerChapter)
      if (draft.customWordsPerChapter) setCustomWordsPerChapter(draft.customWordsPerChapter)
      if (draft.narrative) setNarrative(draft.narrative)
      if (draft.coreTheme) setCoreTheme(draft.coreTheme)
      if (draft.worldSetting) setWorldSetting(draft.worldSetting)
      if (draft.customWorldSetting) setCustomWorldSetting(draft.customWorldSetting)
      if (draft.genre) setGenre(draft.genre)           // 新增
      if (draft.maleLead) setMaleLead(draft.maleLead)   // 新增
      if (draft.customMaleLead) setCustomMaleLead(draft.customMaleLead)  // 新增
      if (draft.femaleLead) setFemaleLead(draft.femaleLead)  // 新增
      if (draft.customFemaleLead) setCustomFemaleLead(draft.customFemaleLead)  // 新增
      if (draft.goldFinger) setGoldFinger(draft.goldFinger)
      if (draft.customGoldFinger) setCustomGoldFinger(draft.customGoldFinger)
      if (draft.stylePreference) setStylePreference(draft.stylePreference)
    }
  }
}, [initialData])
```

- [ ] **Step 7: 更新清空表单逻辑**

更新 handleClear 函数，包含新增字段。

```tsx
const handleClear = () => {
  clearInspirationDraft()
  setTargetReader('')
  setNovelType('')
  setEra('')                    // 新增
  setTargetWords(0)
  setWordsPerChapter('')
  setCustomWordsPerChapter(undefined)
  setNarrative('')
  setCoreTheme('')
  setWorldSetting('')
  setCustomWorldSetting('')
  setGenre('')                  // 新增
  setMaleLead('')               // 新增
  setCustomMaleLead('')         // 新增
  setFemaleLead('')             // 新增
  setCustomFemaleLead('')       // 新增
  setGoldFinger('')
  setCustomGoldFinger('')
  setStylePreference('')
  setErrors({})
}
```

- [ ] **Step 8: 运行前端构建验证**

Run: `cd frontend && npm run build`
Expected: 无 TypeScript 错误，构建成功

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/project/InspirationForm.tsx
git commit -m "feat(frontend): add era, genre, maleLead, femaleLead to inspiration form

- Add era field with card selection UI
- Add genre field with tag selection UI
- Replace protagonist with maleLead/femaleLead based on targetReader
- Update form validation for new required fields
- Update draft save/load/clear logic

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: 后端 Schema 更新

**Files:**
- Modify: `backend/app/schemas/outline.py`

- [ ] **Step 1: 更新 InspirationData Schema**

添加新增字段到 Schema 定义。

```python
# backend/app/schemas/outline.py

from pydantic import BaseModel
from typing import Optional

class InspirationData(BaseModel):
    """灵感数据"""
    # 必填项
    target_reader: str
    novel_type: str
    era: str                        # 新增
    target_words: int
    words_per_chapter: str
    core_theme: str
    male_lead: Optional[str] = None     # 新增
    custom_male_lead: Optional[str] = None
    female_lead: Optional[str] = None   # 新增
    custom_female_lead: Optional[str] = None

    # 选填项
    narrative: Optional[str] = None
    world_setting: Optional[str] = None
    custom_world_setting: Optional[str] = None
    genre: Optional[str] = None         # 新增
    gold_finger: Optional[str] = None
    custom_gold_finger: = None
    style_preference: Optional[str] = None
```

- [ ] **Step 2: 运行后端测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/ -v -k "outline or inspiration"`
Expected: 测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/outline.py
git commit -m "feat(backend): add era, genre, maleLead, femaleLead to InspirationData schema

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: 大纲生成提示词适配

**Files:**
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: 更新大纲生成提示词模板**

在大纲生成提示词中包含新增字段。

```python
# backend/app/agents/prompts.py

# 在 OUTLINE_GENERATION_PROMPT 或相关提示词中添加新字段引用
# 示例：更新模板中的灵感信息部分

OUTLINE_SYSTEM_PROMPT = """你是一位专业的小说大纲策划师。

根据用户提供的灵感信息，生成一份完整、吸引人的小说大纲。

## 灵感信息

- 目标读者：{target_reader}
- 小说类型：{novel_type}
- 年代设定：{era}
- 目标字数：{target_words}字
- 每章字数：{words_per_chapter}
- 核心主题：{core_theme}
- 世界观：{world_setting}
- 主角设定：{protagonist}
- 流派：{genre}
- 金手指：{gold_finger}
- 风格偏好：{style_preference}

## 输出要求

1. 生成小说标题
2. 生成故事简介（200-300字）
3. 生成详细大纲结构
...
"""
```

- [ ] **Step 2: 更新 outline_generation.py 节点**

确保节点正确处理新增字段并传递给提示词。

```python
# backend/app/agents/nodes/outline_generation.py

# 在构建提示词时包含新增字段
def format_inspiration_for_prompt(inspiration: InspirationData) -> str:
    """格式化灵感数据为提示词"""
    protagonist = ""
    if inspiration.target_reader == "male":
        protagonist = inspiration.custom_male_lead or inspiration.male_lead or ""
    else:
        protagonist = inspiration.custom_female_lead or inspiration.female_lead or ""

    return f"""
目标读者：{inspiration.target_reader}
小说类型：{inspiration.novel_type}
年代设定：{inspiration.era}
目标字数：{inspiration.target_words}字
每章字数：{inspiration.words_per_chapter}
核心主题：{inspiration.core_theme}
世界观：{inspiration.custom_world_setting or inspiration.world_setting or '未设置'}
主角设定：{protagonist}
流派：{inspiration.genre or '未设置'}
金手指：{inspiration.custom_gold_finger or inspiration.gold_finger or '未设置'}
风格偏好：{inspiration.style_preference or '未设置'}
"""
```

- [ ] **Step 3: 运行后端测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_agents.py -v`
Expected: 测试通过

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/outline_generation.py
git commit -m "feat(backend): update outline generation prompts with new inspiration fields

- Add era, genre to outline system prompt
- Add maleLead/femaleLead support based on targetReader
- Update format_inspiration_for_prompt function

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: 集成测试与验证

**Files:**
- Test: 手动测试

- [ ] **Step 1: 启动服务进行手动测试**

Run: `docker compose up -d`
Expected: 服务正常启动

- [ ] **Step 2: 验证前端表单功能**

访问 http://localhost:3001，创建新项目：
1. 验证年代字段显示 4 个选项
2. 验证流派字段显示 5 个选项
3. 验证选择男频后显示男主人设
4. 验证选择女频后显示女主人设
5. 验证世界观选项扩展到 15 个
6. 验证表单验证正常工作
7. 验证草稿保存/加载正常

- [ ] **Step 3: 验证大纲生成功能**

创建完整灵感并生成大纲：
1. 验证大纲生成成功
2. 验证生成的 Markdown 模板包含新增字段

- [ ] **Step 4: 最终 Commit**

```bash
git add docs/superpowers/specs/2026-04-27-inspiration-options-enhancement-design.md docs/superpowers/plans/2026-04-27-inspiration-options-enhancement.md
git commit -m "docs: add inspiration options enhancement design and plan

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## 验收清单

- [ ] 年代字段正确显示 4 个选项（古代、现代、未来、架空）
- [ ] 流派字段正确显示 5 个选项（脑洞文、废柴流、凡人流、洪荒流、无限流）
- [ ] 选择男频后显示男主人设，选择女频后显示女主人设
- [ ] 世界观选项扩展到 15 个
- [ ] 表单验证正确处理新增必填项（年代、主角设定）
- [ ] Markdown 模板包含新增字段
- [ ] 大纲生成正确使用新增灵感选项
- [ ] 现有功能不受影响
