// frontend/src/types/workbench.ts

/** 工作台 Tab 类型 */
export type WorkbenchTab = 'planning' | 'creation'

/** 规划功能菜单项 */
export type PlanningMenuItem = 'inspiration' | 'characters' | 'relations'

/** 创作功能菜单项 */
export type CreationMenuItem = 'outline' | 'chapter_outlines' | 'writing'

/** 所有菜单项 */
export type MenuItem = PlanningMenuItem | CreationMenuItem

/** 菜单配置 */
export interface MenuConfig {
  key: MenuItem
  label: string
  icon: string
}

/** 规划菜单配置 */
export const PLANNING_MENUS: MenuConfig[] = [
  { key: 'inspiration', label: '灵感', icon: 'Lightbulb' },
  { key: 'characters', label: '人物', icon: 'Users' },
  { key: 'relations', label: '关系', icon: 'Link' },
]

/** 创作菜单配置 */
export const CREATION_MENUS: MenuConfig[] = [
  { key: 'outline', label: '小说大纲', icon: 'FileText' },
  { key: 'chapter_outlines', label: '章节大纲', icon: 'BookOpen' },
  { key: 'writing', label: '写作', icon: 'PenTool' },
]
