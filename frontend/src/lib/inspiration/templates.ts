// 灵感模板生成与解析

import type { InspirationData } from './types'
import { CONTEXT_STRATEGY_OPTIONS, INSPIRATION_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS, COMMON_OPTIONS, getInspirationOptions } from './config'
import type { SelectOption } from './types'

// 获取选项标签
export function getOptionLabel(options: SelectOption[], value: string | undefined): string
{
  if (!value) return ''
  return options.find(o => o.value === value)?.label || value
}

// 获取每章字数显示文本
export function getWordsPerChapterDisplay(data: InspirationData): string
{
  if (data.wordsPerChapter === 'custom' && data.customWordsPerChapter)
  {
    return `${data.customWordsPerChapter}字`
  }
  const option = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.value === data.wordsPerChapter)
  if (option)
  {
    return option.label
  }
  return data.wordsPerChapter || ''
}

// 生成 Markdown 模板
export function generateInspirationTemplate(data: InspirationData): string
{
  const options = getInspirationOptions(data.targetReader as 'male' | 'female')

  const novelType = getOptionLabel(options.novelTypes, data.novelType)
  const targetWords = data.targetWords ? `${data.targetWords.toLocaleString()}字` : '未设置'
  const wordsPerChapter = getWordsPerChapterDisplay(data)
  const coreTheme = getOptionLabel(options.coreThemes, data.coreTheme)
  const worldSetting = data.customWorldSetting || getOptionLabel(options.worldSettings, data.worldSetting)
  const style = getOptionLabel(options.stylePreferences, data.stylePreference)
  const narrative = getOptionLabel(options.narrative, data.narrative)
  const era = getOptionLabel(options.era, data.era)
  const contextStrategy = getOptionLabel(CONTEXT_STRATEGY_OPTIONS.map(o => ({ value: o.value, label: o.label })), data.contextStrategy)

  // 根据目标读者生成不同的主角设定
  let protagonistSection = ''
  if (data.targetReader === 'male')
  {
    const maleLead = data.customMaleLead || getOptionLabel(MALE_OPTIONS.maleLead, data.maleLead)
    const goldFinger = data.customGoldFinger || getOptionLabel(MALE_OPTIONS.goldFinger, data.goldFinger)
    const genre = data.customGenre || getOptionLabel(MALE_OPTIONS.genre, data.genre)
    protagonistSection = `- **流派**：${genre || '未设置'}
- **男主人设**：${maleLead || '未设置'}
- **金手指**：${goldFinger || '未设置'}`
  }
  else if (data.targetReader === 'female')
  {
    const femaleLead = data.customFemaleLead || getOptionLabel(FEMALE_OPTIONS.femaleLead, data.femaleLead)
    protagonistSection = `- **女主人设**：${femaleLead || '未设置'}`
  }
  else
  {
    // 兼容旧版本的主角设定
    const protagonist = data.customProtagonist || getOptionLabel(INSPIRATION_OPTIONS.protagonistTypes, data.protagonist)
    const goldFinger = data.customGoldFinger || getOptionLabel(INSPIRATION_OPTIONS.goldFinger, data.goldFinger)
    protagonistSection = `- **主角**：${protagonist || '未设置'}
- **金手指**：${goldFinger || '未设置'}`
  }

  return `# 小说创作灵感

## 基本信息

- **目标读者**：${data.targetReader === 'male' ? '男频' : data.targetReader === 'female' ? '女频' : '未设置'}
- **小说类型**：${novelType || '未设置'}
- **目标字数**：${targetWords}
- **上下文策略**：${contextStrategy || '全文上下文'}
- **每章字数**：${wordsPerChapter || '未设置'}
- **年代**：${era || '未设置'}

## 叙事设定

- **叙事视角**：${narrative || '未设置'}

## 核心设定

- **核心主题**：${coreTheme || '未设置'}
- **世界观**：${worldSetting || '未设置'}
${protagonistSection}

## 风格

- **风格偏好**：${style || '未设置'}

## 补充灵感

> 在下方添加更多灵感细节...

-

-

`
}

// 从模板解析灵感数据（用于回显）
export function parseTemplateToData(template: string): Partial<InspirationData>
{
  const lines = template.split('\n')
  const data: Partial<InspirationData> = {}

  for (const line of lines)
  {
    if (line.includes('**目标读者**'))
    {
      const value = line.split('：')[1]?.trim()
      if (value === '男频') data.targetReader = 'male'
      else if (value === '女频') data.targetReader = 'female'
    }
    if (line.includes('**小说类型**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.novelTypes.find(o => o.label === value)
      if (option) data.novelType = option.value
    }
    if (line.includes('**目标字数**'))
    {
      const value = line.split('：')[1]?.trim()
      const numStr = value?.replace(/[字,，]/g, '').replace(/([\d.]+)万/g, (_, num) => String(Math.round(parseFloat(num) * 10000)))
      if (numStr && !isNaN(parseInt(numStr)))
      {
        data.targetWords = parseInt(numStr)
      }
    }
    if (line.includes('**上下文策略**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = CONTEXT_STRATEGY_OPTIONS.find(o => o.label === value)
      if (option) data.contextStrategy = option.value
    }
    if (line.includes('**每章字数**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.label === value)
      if (option) data.wordsPerChapter = option.value
      else if (value && value !== '未设置')
      {
        const numMatch = value.match(/(\d+)/)
        if (numMatch)
        {
          const numVal = parseInt(numMatch[1])
          const presetOption = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.value === String(numVal))
          if (presetOption)
          {
            data.wordsPerChapter = presetOption.value
          }
          else
          {
            data.wordsPerChapter = 'custom'
            data.customWordsPerChapter = numVal
          }
        }
      }
    }
    if (line.includes('**年代**'))
    {
      const value = line.split('：')[1]?.trim()
      const eraFound = COMMON_OPTIONS.era.find(o => o.label === value)
      if (eraFound) data.era = eraFound.value
    }
    if (line.includes('**叙事视角**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.narrative.find(o => o.label === value)
      if (option) data.narrative = option.value
    }
    if (line.includes('**核心主题**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.coreThemes.find(o => o.label === value)
      if (option) data.coreTheme = option.value
    }
    if (line.includes('**世界观**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.worldSettings.find(o => o.label === value)
      if (option) data.worldSetting = option.value
      else if (value && value !== '未设置') data.customWorldSetting = value
    }
    if (line.includes('**流派**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = MALE_OPTIONS.genre.find(o => o.label === value)
      if (option) data.genre = option.value
      else if (value && value !== '未设置') data.customGenre = value
    }
    if (line.includes('**男主人设**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = MALE_OPTIONS.maleLead.find(o => o.label === value)
      if (option) data.maleLead = option.value
      else if (value && value !== '未设置') data.customMaleLead = value
    }
    if (line.includes('**女主人设**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = FEMALE_OPTIONS.femaleLead.find(o => o.label === value)
      if (option) data.femaleLead = option.value
      else if (value && value !== '未设置') data.customFemaleLead = value
    }
    if (line.includes('**主角**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.protagonistTypes.find(o => o.label === value)
      if (option) data.protagonist = option.value
      else if (value && value !== '未设置') data.customProtagonist = value
    }
    if (line.includes('**金手指**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.goldFinger.find(o => o.label === value)
      if (option) data.goldFinger = option.value
      else if (value && value !== '未设置') data.customGoldFinger = value
    }
    if (line.includes('**风格偏好**'))
    {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.stylePreferences.find(o => o.label === value)
      if (option) data.stylePreference = option.value
    }
  }

  return data
}

/** 快捷填充模板 */
export const QUICK_TEMPLATES = [
  {
    id: 'wuxia',
    label: '废柴逆袭（男频玄幻）',
    icon: '🗡️',
    data: {
      novelType: 'xuanhuan',
      targetWords: 500000,
      contextStrategy: 'summary',
      coreTheme: 'counterattack',
      worldSetting: 'xianxia',
      era: 'ancient',
      targetReader: 'male',
      wordsPerChapter: '3000',
      narrative: 'third',
      genre: 'waste',
      maleLead: 'underdog',
      goldFinger: 'system',
      stylePreference: 'passionate',
    },
  },
  {
    id: 'romance',
    label: '甜宠逆袭（女频言情）',
    icon: '💕',
    data: {
      novelType: 'yanqing',
      targetWords: 300000,
      contextStrategy: 'hybrid',
      coreTheme: 'love',
      era: 'modern',
      targetReader: 'female',
      wordsPerChapter: '3000',
      narrative: 'first',
      femaleLead: 'cinderella',
      stylePreference: 'aesthetic',
    },
  },
  {
    id: 'scifi',
    label: '星际科幻',
    icon: '🚀',
    data: {
      novelType: 'kehuan',
      targetWords: 400000,
      contextStrategy: 'hybrid',
      coreTheme: 'adventure',
      worldSetting: 'interstellar',
      era: 'future',
      targetReader: 'male',
      wordsPerChapter: '3000',
      narrative: 'third',
      genre: 'infinite',
      maleLead: 'ordinary',
      goldFinger: 'system',
      stylePreference: 'tense',
    },
  },
]
