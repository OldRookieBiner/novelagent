import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/utils'
import Settings from '@/pages/Settings'

// mock useSettings hook
const mockUseSettings = vi.fn(() => ({
  loading: false,
  modelConfigs: [],
  configsLoading: false,
  showConfigDialog: false,
  savingConfig: false,
  editingConfig: null,
  loadModelConfigs: vi.fn(),
  handleSaveModel: vi.fn(),
  handleEditModel: vi.fn(),
  handleAddModel: vi.fn(),
  handleSetDefault: vi.fn(),
  handleDeleteModel: vi.fn(),
  handleCheckHealth: vi.fn(),
  handleCloseConfigDialog: vi.fn(),
}))

vi.mock('@/components/settings/hooks/useSettings', () => ({
  useSettings: () => mockUseSettings(),
}))

vi.mock('@/lib/api', () => ({
  settingsApi: { get: vi.fn(), update: vi.fn() },
  modelConfigsApi: { list: vi.fn() },
  projectsApi: {},
  authApi: {},
  outlineApi: {},
  chapterOutlinesApi: {},
  chaptersApi: {},
}))

describe('Settings', () => {
  it('renders settings page with navigation', () => {
    render(<Settings />)

    expect(screen.getByText('系统设置')).toBeInTheDocument()
    // 侧边栏导航项和面板标题可能重名，使用 getAllByText 确认存在
    expect(screen.getAllByText('模型配置').length).toBeGreaterThan(0)
  })

  it('renders back button', () => {
    render(<Settings />)

    expect(screen.getByText('返回')).toBeInTheDocument()
  })
})
