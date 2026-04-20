// 灵感选项配置和工具函数

export interface SelectOption {
  value: string
  label: string
  chapters?: string  // 仅用于篇幅选项
  words?: string     // 仅用于字数选项
  desc?: string      // 仅用于每章字数选项
}

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

  targetWords: [
    { value: '50w', label: '50万字', words: '50万' },
    { value: '100w', label: '100万字', words: '100万' },
    { value: '200w', label: '200万字', words: '200万' },
    { value: '300w', label: '300万字', words: '300万' },
    { value: '500w', label: '500万字', words: '500万' },
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
}

// 获取选项标签
export function getOptionLabel(options: SelectOption[], value: string | undefined): string {
  if (!value) return ''
  return options.find(o => o.value === value)?.label || value
}

// 获取篇幅显示文本
export function getLengthDisplay(data: InspirationData): string {
  if (data.novelLength === 'custom' && data.customChapterCount) {
    return `${data.customChapterCount}章`
  }
  const option = INSPIRATION_OPTIONS.novelLength.find(o => o.value === data.novelLength)
  if (option) {
    return option.chapters ? `${option.label}(${option.chapters}章)` : option.label
  }
  return data.novelLength
}

// 获取字数显示文本
export function getTargetWordsDisplay(data: InspirationData): string {
  if (data.targetWords === 'custom' && data.customTargetWords) {
    return `${data.customTargetWords}万字`
  }
  const option = INSPIRATION_OPTIONS.targetWords.find(o => o.value === data.targetWords)
  if (option) {
    return option.words || option.label
  }
  return data.targetWords
}

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

// 获取章节数（根据篇幅或自定义）
export function getChapterCount(data: InspirationData): number {
  if (data.novelLength === 'custom' && data.customChapterCount) {
    return data.customChapterCount
  }
  const lengthToChapters: Record<string, number> = {
    short: 15,
    medium: 40,
    long: 75,
    extra_long: 100,
  }
  return lengthToChapters[data.novelLength] || 40
}

// 获取总字数（万字为单位）
export function getTotalWords(data: InspirationData): number {
  if (data.targetWords === 'custom' && data.customTargetWords) {
    return data.customTargetWords
  }
  const wordsToNumber: Record<string, number> = {
    '50w': 50,
    '100w': 100,
    '200w': 200,
    '300w': 300,
    '500w': 500,
  }
  return wordsToNumber[data.targetWords] || 100
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

// 从模板解析灵感数据（用于回显）
export function parseTemplateToData(template: string): Partial<InspirationData> {
  const lines = template.split('\n')
  const data: Partial<InspirationData> = {}

  for (const line of lines) {
    if (line.includes('**小说类型**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.novelTypes.find(o => o.label === value)
      if (option) data.novelType = option.value
    }
    if (line.includes('**核心主题**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.coreThemes.find(o => o.label === value)
      if (option) data.coreTheme = option.value
    }
    if (line.includes('**世界观**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.worldSettings.find(o => o.label === value)
      if (option) data.worldSetting = option.value
      else if (value && value !== '未设置') data.customWorldSetting = value
    }
    if (line.includes('**主角**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.protagonistTypes.find(o => o.label === value)
      if (option) data.protagonist = option.value
      else if (value && value !== '未设置') data.customProtagonist = value
    }
    if (line.includes('**风格偏好**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.stylePreferences.find(o => o.label === value)
      if (option) data.stylePreference = option.value
    }
  }

  return data
}

// localStorage 持久化
const STORAGE_KEY = 'novelagent_inspiration_draft'

export function saveInspirationDraft(data: InspirationData): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch (e) {
    console.error('Failed to save draft:', e)
  }
}

export function loadInspirationDraft(): Partial<InspirationData> | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch (e) {
    console.error('Failed to load draft:', e)
  }
  return null
}

export function clearInspirationDraft(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    console.error('Failed to clear draft:', e)
  }
}
