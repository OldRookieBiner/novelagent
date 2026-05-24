// 灵感模块统一入口
// 新代码请使用 '@/lib/inspiration/' 目录下的模块化导入

// 类型
export type { InspirationData, SelectOption, ContextStrategyOption, FieldStatus, QuickTemplate } from './types'
export { REQUIRED_FIELDS, MALE_REQUIRED_FIELDS, FEMALE_REQUIRED_FIELDS } from './types'

// 配置
export { COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS, CONTEXT_STRATEGY_OPTIONS, INSPIRATION_OPTIONS, getInspirationOptions, getContextStrategyFromTargetWords, NOVEL_TYPE_ICONS, ERA_ICONS, TARGET_READER_ICONS, TARGET_READER_DESC } from './config'

// 模板
export { QUICK_TEMPLATES, generateInspirationTemplate, parseTemplateToData, getOptionLabel, getWordsPerChapterDisplay } from './templates'

// 工具
export { inferFieldsFromText, getMissingFields, saveInspirationDraft, loadInspirationDraft, clearInspirationDraft, asString } from './utils'
