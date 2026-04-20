import {
  INSPIRATION_OPTIONS,
  type InspirationData,
} from '@/lib/inspiration'

interface InspirationDisplayProps {
  data: Partial<InspirationData>
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

// 值到标签映射
const VALUE_LABELS: Record<string, Record<string, string>> = {
  targetReader: { male: '男频', female: '女频' },
  novelType: { xuanhuan: '玄幻', kehuan: '科幻', dushi: '都市', yanqing: '言情', xuanyi: '悬疑', lishi: '历史' },
  wordsPerChapter: { '1500-2000': '1500-2000字', '2000-2500': '2000-2500字', '2500-3000': '2500-3000字', '3000-5000': '3000-5000字', custom: '自定义' },
  narrative: { first: '第一人称', third: '第三人称' },
  coreTheme: { revenge: '复仇', growth: '成长', counterattack: '逆袭', love: '爱情', adventure: '探险', power_struggle: '权谋' },
  worldSetting: { cultivation: '修仙体系', magic: '魔法世界', cyberpunk: '赛博朋克', modern: '现代社会', ancient: '古代王朝', custom: '自定义' },
  protagonist: { genius: '少年天才', transmigrator: '穿越者', reborn: '重生者', underdog: '草根逆袭', ordinary: '普通人', custom: '自定义' },
  goldFinger: { system: '系统流', space: '空间流', reborn: '重生流', transmigrate: '穿越流', checkin: '签到流', none: '无金手指', custom: '自定义' },
  stylePreference: { humorous: '轻松幽默', passionate: '热血激昂', aesthetic: '细腻唯美', dark: '暗黑深沉', tense: '紧张刺激' },
}

// 获取显示标签
const getLabel = (key: string, value: string | undefined): string => {
  if (!value) return ''
  return VALUE_LABELS[key]?.[value] || value
}

export default function InspirationDisplay({ data }: InspirationDisplayProps) {
  // 获取目标字数显示文本
  const getTargetWordsDisplay = (): string => {
    if (data.targetWords) {
      return `${data.targetWords.toLocaleString()}字`
    }
    return '-'
  }

  // 获取每章字数显示文本
  const getWordsPerChapterDisplay = (): string => {
    if (data.wordsPerChapter === 'custom' && data.customWordsPerChapter) {
      return `${data.customWordsPerChapter}字`
    }
    return getLabel('wordsPerChapter', data.wordsPerChapter) || '-'
  }

  // 获取自定义值显示
  const getCustomValue = (field: string, customField: string | undefined): string | null => {
    const fieldValue = data[field as keyof InspirationData]
    if (fieldValue === 'custom' && customField) {
      return customField
    }
    return null
  }

  return (
    <div className="space-y-8">
      {/* 目标读者：独占一行，卡片选择 */}
      <div>
        <div className="text-sm font-medium text-gray-700 mb-3">目标读者</div>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {INSPIRATION_OPTIONS.targetReader.map((opt) => (
            <div
              key={opt.value}
              className={`border-2 rounded-lg p-5 text-center ${
                data.targetReader === opt.value
                  ? 'border-blue-500 bg-blue-50 shadow-sm'
                  : 'border-gray-200 opacity-50'
              }`}
            >
              <div className="text-3xl mb-2">{TARGET_READER_ICONS[opt.value]}</div>
              <div className="font-medium text-base">{opt.label}</div>
              <div className="text-xs text-gray-500 mt-1">{TARGET_READER_DESC[opt.value]}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 基本设定 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-semibold text-gray-700">基本设定</span>
        </div>

        {/* 小说类型：卡片选择 */}
        <div className="mb-6">
          <div className="text-sm font-medium text-gray-700 mb-3">小说类型</div>
          <div className="grid grid-cols-6 gap-2">
            {INSPIRATION_OPTIONS.novelTypes.map((opt) => (
              <div
                key={opt.value}
                className={`border-2 rounded-lg p-3 text-center ${
                  data.novelType === opt.value
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 opacity-50'
                }`}
              >
                <div className="text-lg mb-1">{NOVEL_TYPE_ICONS[opt.value]}</div>
                <div className="text-sm font-medium">{opt.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 下拉框值展示 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
              目标字数
              {/* Tips 图标 */}
              <div className="relative group ml-1">
                <svg
                  className="w-4 h-4 text-gray-400 cursor-help hover:text-blue-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {/* Tooltip */}
                <div className="absolute bottom-full left-0 mb-2 w-56 p-3 bg-gray-800 text-white text-xs rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  <div className="font-medium mb-2">📖 字数与篇幅对应关系：</div>
                  <ul className="space-y-1">
                    <li>• 超短篇：1万-5万字</li>
                    <li>• 短篇：5万-20万字</li>
                    <li>• 中篇：20万-50万字</li>
                    <li>• 长篇：50万-100万字</li>
                    <li>• 超长篇：100万字以上</li>
                  </ul>
                  <div className="absolute bottom-0 left-4 transform translate-y-full">
                    <div className="border-8 border-transparent border-t-gray-800"></div>
                  </div>
                </div>
              </div>
            </div>
            <div className="h-11 px-3 rounded-lg border-2 border-gray-200 bg-gray-50 flex items-center text-sm">
              {getTargetWordsDisplay()}
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">每章字数</div>
            <div className="h-11 px-3 rounded-lg border-2 border-gray-200 bg-gray-50 flex items-center text-sm">
              {getWordsPerChapterDisplay()}
            </div>
          </div>
        </div>
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 进阶设定 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-semibold text-gray-700">进阶设定</span>
        </div>

        <div className="space-y-6">
          {/* 叙事视角 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">叙事视角</div>
            <div className="flex gap-2">
              {INSPIRATION_OPTIONS.narrative.map((opt) => (
                <span
                  key={opt.value}
                  className={`px-5 py-2 rounded-full border-2 text-sm ${
                    data.narrative === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 opacity-50'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>

          {/* 核心主题 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">核心主题</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
                <span
                  key={opt.value}
                  className={`px-4 py-2 rounded-full border-2 text-sm ${
                    data.coreTheme === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 opacity-50'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>

          {/* 世界观设定 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">世界观设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.worldSettings.map((opt) => (
                <span
                  key={opt.value}
                  className={`px-4 py-2 rounded-full border-2 text-sm ${
                    data.worldSetting === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 opacity-50'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {getCustomValue('worldSetting', data.customWorldSetting) && (
              <div className="mt-2 text-sm text-gray-600">
                自定义：{data.customWorldSetting}
              </div>
            )}
          </div>

          {/* 主角设定 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">主角设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.protagonistTypes.map((opt) => (
                <span
                  key={opt.value}
                  className={`px-4 py-2 rounded-full border-2 text-sm ${
                    data.protagonist === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 opacity-50'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {getCustomValue('protagonist', data.customProtagonist) && (
              <div className="mt-2 text-sm text-gray-600">
                自定义：{data.customProtagonist}
              </div>
            )}
          </div>

          {/* 金手指设定 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">金手指设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.goldFinger.map((opt) => (
                <span
                  key={opt.value}
                  className={`px-4 py-2 rounded-full border-2 text-sm ${
                    data.goldFinger === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 opacity-50'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
            {getCustomValue('goldFinger', data.customGoldFinger) && (
              <div className="mt-2 text-sm text-gray-600">
                自定义：{data.customGoldFinger}
              </div>
            )}
          </div>

          {/* 风格偏好 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">风格偏好</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.stylePreferences.map((opt) => (
                <span
                  key={opt.value}
                  className={`px-4 py-2 rounded-full border-2 text-sm ${
                    data.stylePreference === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 opacity-50'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
