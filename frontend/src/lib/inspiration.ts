// 灵感选项配置和工具函数

export interface SelectOption {
  value: string
  label: string
  chapters?: string  // 仅用于篇幅选项
}

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

// 生成 Markdown 模板
export function generateInspirationTemplate(data: InspirationData): string {
  const novelType = getOptionLabel(INSPIRATION_OPTIONS.novelTypes, data.novelType)
  const novelLength = getLengthDisplay(data)
  const coreTheme = getOptionLabel(INSPIRATION_OPTIONS.coreThemes, data.coreTheme)
  const worldSetting = data.customWorldSetting || getOptionLabel(INSPIRATION_OPTIONS.worldSettings, data.worldSetting)
  const protagonist = data.customProtagonist || getOptionLabel(INSPIRATION_OPTIONS.protagonistTypes, data.protagonist)
  const style = getOptionLabel(INSPIRATION_OPTIONS.stylePreferences, data.stylePreference)

  return `# 小说创作灵感

## 基本信息

- **小说类型**：${novelType || '未设置'}
- **小说篇幅**：${novelLength || '未设置'}
- **核心主题**：${coreTheme || '未设置'}

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

// 从模板解析灵感数据（用于回显）
export function parseTemplateToData(template: string): Partial<InspirationData> {
  // 简单解析，后续可扩展
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
