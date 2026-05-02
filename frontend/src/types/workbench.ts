// frontend/src/types/workbench.ts

/** 工作台 Tab 类型 */
export type WorkbenchTab = 'planning' | 'chapter_outlines' | 'writing'

/** 规划功能菜单项 */
export type PlanningMenuItem = 'inspiration' | 'outline' | 'characters' | 'relations'

/** 所有菜单项 */
export type MenuItem = PlanningMenuItem

/** 菜单配置 */
export interface MenuConfig {
  key: MenuItem
  label: string
  icon: string
}

/** 规划菜单配置 */
export const PLANNING_MENUS: MenuConfig[] = [
  { key: 'inspiration', label: '灵感', icon: 'Lightbulb' },
  { key: 'outline', label: '大纲', icon: 'FileText' },
  { key: 'characters', label: '人物', icon: 'Users' },
  { key: 'relations', label: '关系', icon: 'Link' },
]
