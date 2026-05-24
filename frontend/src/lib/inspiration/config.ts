// 灵感选项配置和图标映射

// 上下文策略选项（本地定义，不再依赖已删除的 types.ts）
interface ContextStrategyOption
{
  value: string
  label: string
  desc: string
  recommendedWords: string
}

// ============================================
// 上下文策略选项
// ============================================
export const CONTEXT_STRATEGY_OPTIONS: ContextStrategyOption[] = [
  {
    value: 'fulltext',
    label: '全文上下文',
    desc: '保留全部历史章节，适合短篇',
    recommendedWords: '≤10万字',
  },
  {
    value: 'hybrid',
    label: '混合上下文',
    desc: '保留摘要+最新章节，适合中篇',
    recommendedWords: '10-30万字',
  },
  {
    value: 'summary',
    label: '摘要上下文',
    desc: '仅保留章节摘要，适合长篇',
    recommendedWords: '>30万字',
  },
]

/** 根据 targetWords 推荐上下文策略 */
export function getContextStrategyFromTargetWords(targetWords: number): string
{
  if (targetWords <= 100000) return 'fulltext'
  if (targetWords <= 300000) return 'hybrid'
  return 'summary'
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
    { value: '2000', label: '2000字起', desc: '短章' },
    { value: '3000', label: '3000字起', desc: '标准·番茄推荐' },
    { value: '4000', label: '4000字起', desc: '中章·七猫推荐' },
    { value: '5000', label: '5000字起', desc: '长章' },
    { value: 'custom', label: '自定义' },
  ],

  narrative: [
    { value: 'first', label: '第一人称' },
    { value: 'third', label: '第三人称' },
  ],

  // 年代选项
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
    { value: 'custom', label: '自定义' },
  ],

  maleLead: [
    { value: 'genius', label: '少年天才' },
    { value: 'transmigrator', label: '穿越者' },
    { value: 'reborn', label: '重生者' },
    { value: 'underdog', label: '草根逆袭' },
    { value: 'ordinary', label: '普通人' },
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
}

// ============================================
// 女频专属选项
// ============================================
export const FEMALE_OPTIONS = {
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
export function getInspirationOptions(targetReader?: 'male' | 'female')
{
  const base = { ...COMMON_OPTIONS }

  if (targetReader === 'male')
  {
    return {
      ...base,
      genre: MALE_OPTIONS.genre,
      maleLead: MALE_OPTIONS.maleLead,
      goldFinger: MALE_OPTIONS.goldFinger,
    }
  }

  if (targetReader === 'female')
  {
    return {
      ...base,
      femaleLead: FEMALE_OPTIONS.femaleLead,
    }
  }

  return base
}

// ============================================
// 向后兼容：保持原有的 INSPIRATION_OPTIONS 导出
// ============================================
export const INSPIRATION_OPTIONS = {
  novelTypes: COMMON_OPTIONS.novelTypes,
  coreThemes: COMMON_OPTIONS.coreThemes,
  worldSettings: COMMON_OPTIONS.worldSettings,
  protagonistTypes: MALE_OPTIONS.maleLead,
  stylePreferences: COMMON_OPTIONS.stylePreferences,
  targetReader: COMMON_OPTIONS.targetReader,
  wordsPerChapter: COMMON_OPTIONS.wordsPerChapter,
  narrative: COMMON_OPTIONS.narrative,
  goldFinger: MALE_OPTIONS.goldFinger,
}

// ============================================
// 图标映射（从 InspirationPanel.tsx 提取）
// ============================================
export const NOVEL_TYPE_ICONS: Record<string, string> = {
  xuanhuan: '⚔️',
  dushi: '🏙️',
  xianxia: '☁️',
  yanqing: '💕',
  lishi: '📜',
  xuanyi: '🔍',
  kehuan: '🚀',
  youxi: '🎮',
  qihuan: '🧙',
  junshi: '🎖️',
  lingyi: '👻',
  jingji: '🏆',
  tongren: '📖',
}

export const ERA_ICONS: Record<string, string> = {
  ancient: '🏛️',
  modern: '🏙️',
  future: '🚀',
  fantasy: '🌐',
}

export const TARGET_READER_ICONS: Record<string, string> = {
  male: '👨',
  female: '👩',
}

export const TARGET_READER_DESC: Record<string, string> = {
  male: '热血、爽文、升级',
  female: '言情、甜宠、逆袭',
}
