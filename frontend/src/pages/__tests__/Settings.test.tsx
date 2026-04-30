import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
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
  reviewMode: 'manual',
  setReviewMode: vi.fn(),
  maxRewriteCount: 3,
  setMaxRewriteCount: vi.fn(),
  workflowMode: 'hybrid',
  setWorkflowMode: vi.fn(),
  saving: false,
  saved: false,
  handleSaveReviewSettings: vi.fn(),
  prompts: [],
  promptsLoading: false,
  loadPrompts: vi.fn(),
  selectedAgent: 'outline_generation',
  setSelectedAgent: vi.fn(),
  editContent: '',
  setEditContent: vi.fn(),
  savingPrompt: false,
  resettingPrompt: false,
  handleSavePrompt: vi.fn(),
  handleResetPrompt: vi.fn(),
}))

vi.mock('@/components/settings/hooks/useSettings', () => ({
  useSettings: () => mockUseSettings(),
}))

vi.mock('@/lib/api', () => ({
  settingsApi: { get: vi.fn(), update: vi.fn() },
  modelConfigsApi: { list: vi.fn() },
  systemPromptsApi: { list: vi.fn() },
  projectsApi: {},
  authApi: {},
  workflowApi: {},
  outlineApi: {},
  chapterOutlinesApi: {},
  chaptersApi: {},
}))

describe('Settings', () => {
  it('renders settings page with tab navigation', () => {
    render(<Settings />)

    expect(screen.getByText('设置')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '模型配置' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '审核设置' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '智能体管理' })).toBeInTheDocument()
  })
})
