// 灵感选项配置和工具函数

export interface SelectOption {
  value: string
  label: string
  desc?: string      // 仅用于每章字数选项
}

export interface InspirationData {
  novelType: string
  targetWords: number           // 改为 number 类型
  coreTheme: string
  worldSetting?: string
  customWorldSetting?: string
  protagonist?: string
  customProtagonist?: string
  stylePreference?: string
  // 新增字段
  targetReader: string
  wordsPerChapter: string
  customWordsPerChapter?: number
  narrative?: string
  goldFinger?: string
  customGoldFinger?: string
  // 分层选项新增字段
  era?: string                   // 年代
  genre?: string                 // 流派
  maleLead?: string              // 男主人设
  customMaleLead?: string
  femaleLead?: string            // 女主人设
  customFemaleLead?: string
}

// ============================================
// 通用选项配置（男女频共用）
// ============================================
export const COMMON_OPTIONS = {
  novelTypes: [
    { value: 'xuanhuan', label: '玄幻' },
    { value: 'dushi', label: '都市' },
    { value: 'xianxia', label: '仙侠' },
    { value: 'yanqing', label: '言情' },
    { value: 'lishi', label: '历史' },
    { value: 'xuanyi', label: '悬疑' },
    { value: 'kehuan', label: '科幻' },
    { value: 'youxi', label: '游戏' },
    { value: 'qihuan', label: '奇幻' },
    { value: 'junshi', label: '军事' },
    { value: 'lingyi', label: '灵异' },
    { value: 'jingji', label: '竞技' },
    { value: 'tongren', label: '同人' },
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
    { value: 'urban_fantasy', label: '都市异能' },
    { value: 'palace_intrigue', label: '宫廷宅斗' },
    { value: 'wuxia', label: '武侠江湖' },
    { value: 'interstellar', label: '星际帝国' },
    { value: 'game_world', label: '游戏世界' },
    { value: 'supernatural', label: '灵异悬疑' },
    { value: 'custom', label: '自定义' },
  ],

  stylePreferences: [
    { value: 'humorous', label: '轻松幽默' },
    { value: 'passionate', label: '热血激昂' },
    { value: 'aesthetic', label: '细腻唯美' },
    { value: 'dark', label: '暗黑深沉' },
    { value: 'tense', label: '紧张刺激' },
  ],

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

  // 年代选项（男女频共用）
  era: [
    { value: 'ancient', label: '古代' },
    { value: 'modern', label: '现代' },
    { value: 'future', label: '未来' },
    { value: 'fantasy', label: '架空' },
  ],
}

// ============================================
// 男频专属选项
// ============================================
export const MALE_OPTIONS = {
  // 流派选项（男频专属）
  genre: [
    { value: 'brain_hole', label: '脑洞文' },
    { value: 'waste', label: '废柴流' },
    { value: 'mortal', label: '凡人流' },
    { value: 'prehistoric', label: '洪荒流' },
    { value: 'infinite', label: '无限流' },
    { value: 'farm', label: '种田文' },
    { value: 'domination', label: '争霸文' },
    { value: 'invincible', label: '无敌流' },
    { value: 'low_key', label: '苟道流' },
    { value: 'heaven', label: '诸天流' },
    { value: 'system', label: '系统流' },
    { value: 'livestream', label: '直播流' },
  ],

  // 男主人设（男频专属）
  maleLead: [
    { value: 'genius', label: '少年天才' },
    { value: 'transmigrator', label: '穿越者' },
    { value: 'reborn', label: '重生者' },
    { value: 'underdog', label: '草根逆袭' },
    { value: 'ordinary', label: '普通人' },
    { value: 'custom', label: '自定义' },
  ],

  // 金手指（男频专属）
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

// ============================================
// 女频专属选项
// ============================================
export const FEMALE_OPTIONS = {
  // 女主人设（女频专属）
  femaleLead: [
    { value: 'rich_beauty', label: '白富美' },
    { value: 'strong_woman', label: '女强人' },
    { value: 'sweet', label: '傻白甜' },
    { value: 'cinderella', label: '灰姑娘' },
    { value: 'transmigrator', label: '穿越女' },
    { value: 'reborn', label: '重生女' },
    { value: 'custom', label: '自定义' },
  ],
}

// ============================================
// 动态获取选项（根据目标读者）
// ============================================
export function getInspirationOptions(targetReader?: 'male' | 'female') {
  const base = { ...COMMON_OPTIONS }

  if (targetReader === 'male') {
    return {
      ...base,
      genre: MALE_OPTIONS.genre,
      maleLead: MALE_OPTIONS.maleLead,
      goldFinger: MALE_OPTIONS.goldFinger,
    }
  }

  if (targetReader === 'female') {
    return {
      ...base,
      femaleLead: FEMALE_OPTIONS.femaleLead,
    }
  }

  // 未指定目标读者时，返回通用选项
  return base
}

// ============================================
// 向后兼容：保持原有的 INSPIRATION_OPTIONS 导出
// ============================================
export const INSPIRATION_OPTIONS = {
  novelTypes: COMMON_OPTIONS.novelTypes,
  coreThemes: COMMON_OPTIONS.coreThemes,
  worldSettings: COMMON_OPTIONS.worldSettings,
  protagonistTypes: MALE_OPTIONS.maleLead,  // 保持向后兼容，使用男主人设作为主角类型
  stylePreferences: COMMON_OPTIONS.stylePreferences,
  targetReader: COMMON_OPTIONS.targetReader,
  wordsPerChapter: COMMON_OPTIONS.wordsPerChapter,
  narrative: COMMON_OPTIONS.narrative,
  goldFinger: MALE_OPTIONS.goldFinger,
}

// 获取选项标签
export function getOptionLabel(options: SelectOption[], value: string | undefined): string {
  if (!value) return ''
  return options.find(o => o.value === value)?.label || value
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

// 生成 Markdown 模板
export function generateInspirationTemplate(data: InspirationData): string {
  const options = getInspirationOptions(data.targetReader as 'male' | 'female')

  const novelType = getOptionLabel(options.novelTypes, data.novelType)
  const targetWords = data.targetWords ? `${data.targetWords.toLocaleString()}字` : '未设置'
  const wordsPerChapter = getWordsPerChapterDisplay(data)
  const coreTheme = getOptionLabel(options.coreThemes, data.coreTheme)
  const worldSetting = data.customWorldSetting || getOptionLabel(options.worldSettings, data.worldSetting)
  const style = getOptionLabel(options.stylePreferences, data.stylePreference)
  const narrative = getOptionLabel(options.narrative, data.narrative)
  const era = getOptionLabel(options.era, data.era)

  // 根据目标读者生成不同的主角设定
  let protagonistSection = ''
  if (data.targetReader === 'male') {
    const maleLead = data.customMaleLead || getOptionLabel(MALE_OPTIONS.maleLead, data.maleLead)
    const goldFinger = data.customGoldFinger || getOptionLabel(MALE_OPTIONS.goldFinger, data.goldFinger)
    const genre = getOptionLabel(MALE_OPTIONS.genre, data.genre)
    protagonistSection = `- **流派**：${genre || '未设置'}
- **男主人设**：${maleLead || '未设置'}
- **金手指**：${goldFinger || '未设置'}`
  } else if (data.targetReader === 'female') {
    const femaleLead = data.customFemaleLead || getOptionLabel(FEMALE_OPTIONS.femaleLead, data.femaleLead)
    protagonistSection = `- **女主人设**：${femaleLead || '未设置'}`
  } else {
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
export function parseTemplateToData(template: string): Partial<InspirationData> {
  const lines = template.split('\n')
  const data: Partial<InspirationData> = {}

  for (const line of lines) {
    if (line.includes('**目标读者**')) {
      const value = line.split('：')[1]?.trim()
      if (value === '男频') data.targetReader = 'male'
      else if (value === '女频') data.targetReader = 'female'
    }
    if (line.includes('**小说类型**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.novelTypes.find(o => o.label === value)
      if (option) data.novelType = option.value
    }
    if (line.includes('**目标字数**')) {
      const value = line.split('：')[1]?.trim()
      // Parse number, remove "字" and commas
      const numStr = value?.replace(/[字,，]/g, '').replace(/万/g, '0000')
      if (numStr && !isNaN(parseInt(numStr))) {
        data.targetWords = parseInt(numStr)
      }
    }
    if (line.includes('**每章字数**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.label === value)
      if (option) data.wordsPerChapter = option.value
      else if (value && value !== '未设置') {
        const numMatch = value.match(/(\d+)/)
        if (numMatch) {
          data.wordsPerChapter = 'custom'
          data.customWordsPerChapter = parseInt(numMatch[1])
        }
      }
    }
    // 解析年代（新增字段）
    if (line.includes('**年代**')) {
      const value = line.split('：')[1]?.trim()
      const option = COMMON_OPTIONS.era.find(o => o.label === value)
      if (option) data.era = option.value
    }
    if (line.includes('**叙事视角**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.narrative.find(o => o.label === value)
      if (option) data.narrative = option.value
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
    // 解析流派（男频专属）
    if (line.includes('**流派**')) {
      const value = line.split('：')[1]?.trim()
      const option = MALE_OPTIONS.genre.find(o => o.label === value)
      if (option) data.genre = option.value
    }
    // 解析男主人设
    if (line.includes('**男主人设**')) {
      const value = line.split('：')[1]?.trim()
      const option = MALE_OPTIONS.maleLead.find(o => o.label === value)
      if (option) data.maleLead = option.value
      else if (value && value !== '未设置') data.customMaleLead = value
    }
    // 解析女主人设
    if (line.includes('**女主人设**')) {
      const value = line.split('：')[1]?.trim()
      const option = FEMALE_OPTIONS.femaleLead.find(o => o.label === value)
      if (option) data.femaleLead = option.value
      else if (value && value !== '未设置') data.customFemaleLead = value
    }
    // 兼容旧版本的主角设定
    if (line.includes('**主角**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.protagonistTypes.find(o => o.label === value)
      if (option) data.protagonist = option.value
      else if (value && value !== '未设置') data.customProtagonist = value
    }
    if (line.includes('**金手指**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.goldFinger.find(o => o.label === value)
      if (option) data.goldFinger = option.value
      else if (value && value !== '未设置') data.customGoldFinger = value
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
