// frontend/src/types/workbench.ts

/** 工作台 Tab 类型 */
export type WorkbenchTab = 'inspiration' | 'settings' | 'chapter_outlines' | 'writing'

/** 设定功能菜单项 */
export type SettingsMenuItem = 'outline' | 'characters' | 'relations'

/** 所有菜单项 */
export type MenuItem = SettingsMenuItem

/** 菜单配置 */
export interface MenuConfig {
  key: MenuItem
  label: string
  icon: string
}

/** 设定菜单配置 */
export const SETTINGS_MENUS: MenuConfig[] = [
  { key: 'outline', label: '大纲', icon: 'FileText' },
  { key: 'characters', label: '人物', icon: 'Users' },
  { key: 'relations', label: '关系', icon: 'Link' },
]
