// 灵感工具函数与持久化

import type { InspirationData } from './types'

// 从 Record<string, unknown> 安全提取字符串值
export function asString(val: unknown): string
{
  return typeof val === 'string' ? val : ''
}

/** 从自由文本推断灵感字段（客户端预推断，与后端同步） */
export function inferFieldsFromText(text: string): Partial<InspirationData>
{
  const inferred: Partial<InspirationData> = {}

  const rules: Array<[string[], Partial<InspirationData>]> = [
    [['都市', '现代', '城市'], { era: 'modern', novelType: 'dushi' }],
    [['修仙', '灵气', '飞升'], { era: 'fantasy', novelType: 'xianxia' }],
    [['古代', '朝代', '皇帝'], { era: 'ancient', novelType: 'lishi' }],
    [['未来', '星际', '机甲'], { era: 'future', novelType: 'kehuan' }],
    [['甜', '宠', '逆袭'], { targetReader: 'female' }],
    [['升级', '爽', '热血'], { targetReader: 'male' }],
  ]

  for (const [keywords, fields] of rules)
  {
    if (keywords.some((kw) => text.includes(kw)))
    {
      Object.assign(inferred, fields)
    }
  }

  return inferred
}

/** 获取仍缺失的必填字段 */
export function getMissingFields(data: Partial<InspirationData>): string[]
{
  const required: (keyof InspirationData)[] = ['novelType', 'targetReader', 'targetWords', 'era']
  return required.filter((f) => !data[f])
}

// localStorage 持久化
const STORAGE_KEY = 'novelagent_inspiration_draft'

export function saveInspirationDraft(data: InspirationData): void
{
  try
  {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }
  catch (e)
  {
    console.error('Failed to save draft:', e)
  }
}

export function loadInspirationDraft(): Partial<InspirationData> | null
{
  try
  {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved)
    {
      return JSON.parse(saved)
    }
  }
  catch (e)
  {
    console.error('Failed to load draft:', e)
  }
  return null
}

export function clearInspirationDraft(): void
{
  try
  {
    localStorage.removeItem(STORAGE_KEY)
  }
  catch (e)
  {
    console.error('Failed to clear draft:', e)
  }
}
