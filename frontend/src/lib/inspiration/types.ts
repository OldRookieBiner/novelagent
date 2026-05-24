// 灵感采集类型定义

/** 字段状态：Agent 联动标签 */
export type FieldStatus =
  | 'agent_populated'  // Agent 填充，紫色标签
  | 'agent_asking'     // Agent 询问中，黄色标签
  | 'empty'            // 待填写
  | 'user_filled'      // 用户手动填写

/** 选项基础结构 */
export interface SelectOption
{
  value: string
  label: string
  desc?: string
}

/** 灵感采集数据 */
export interface InspirationData
{
  novelType: string
  targetWords: number
  contextStrategy: string          // 上下文策略：fulltext | hybrid | summary
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
export interface ContextStrategyOption
{
  value: string
  label: string
  desc: string
  recommendedWords: string
}

/** 快捷填充模板 */
export interface QuickTemplate
{
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
