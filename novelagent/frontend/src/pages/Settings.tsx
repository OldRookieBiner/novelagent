// frontend/src/pages/Settings.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { settingsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import type { UserSettings, SettingsUpdate } from '@/types'

const MODEL_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek (火山方舟)' },
  { value: 'deepseek-official', label: 'DeepSeek (官方)' },
  { value: 'openai', label: 'OpenAI' },
]

const REVIEW_STRICTNESS = [
  { value: 'loose', label: '宽松' },
  { value: 'standard', label: '标准' },
  { value: 'strict', label: '严格' },
]

const SETTINGS_TABS = [
  { id: 'model', label: '模型配置' },
  { id: 'review', label: '审核设置' },
] as const

type SettingsTab = typeof SETTINGS_TABS[number]['id']

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const [settings, setSettings] = useState<UserSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [clearingKey, setClearingKey] = useState(false)

  // Form state
  const [modelProvider, setModelProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [reviewEnabled, setReviewEnabled] = useState(true)
  const [reviewStrictness, setReviewStrictness] = useState('standard')

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const data = await settingsApi.get()
      setSettings(data)
      setModelProvider(data.model_provider)
      setReviewEnabled(data.review_enabled)
      setReviewStrictness(data.review_strictness)
      useSettingsStore.getState().setSettings(data)
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)

    try {
      const update: SettingsUpdate = {
        model_provider: modelProvider,
        review_enabled: reviewEnabled,
        review_strictness: reviewStrictness,
      }

      if (apiKey) {
        update.api_key = apiKey
      }

      const updated = await settingsApi.update(update)
      setSettings(updated)
      useSettingsStore.getState().setSettings(updated)
      setApiKey('')
      setSaved(true)
    } catch (err) {
      console.error('Failed to save settings:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleClearApiKey = async () => {
    if (!confirm('确定要删除已配置的 API Key 吗？删除后将无法使用 AI 功能。')) {
      return
    }

    setClearingKey(true)
    try {
      const updated = await settingsApi.update({ clear_api_key: true })
      setSettings(updated)
      useSettingsStore.getState().setSettings(updated)
    } catch (err) {
      console.error('Failed to clear API key:', err)
    } finally {
      setClearingKey(false)
    }
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="flex min-h-[calc(100vh-80px)]">
      {/* 左侧导航栏 */}
      <nav className="w-[220px] border-r bg-background">
        <div className="p-4 border-b">
          <h2 className="font-semibold">设置</h2>
        </div>
        <div className="p-3 space-y-1">
          {SETTINGS_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full px-3 py-2 text-sm rounded-md transition-colors ${
                activeTab === tab.id
                  ? 'bg-secondary text-foreground font-medium'
                  : 'bg-transparent text-muted-foreground hover:bg-secondary/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* 右侧内容区 */}
      <div className="flex-1 p-6">
        {activeTab === 'model' && (
          <div className="max-w-xl">
            <h3 className="text-lg font-semibold mb-1">模型配置</h3>
            <p className="text-muted-foreground text-sm mb-6">配置 AI 模型和 API Key</p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">模型提供商</label>
                <select
                  className="w-full h-10 px-3 rounded-md border border-input bg-background"
                  value={modelProvider}
                  onChange={(e) => setModelProvider(e.target.value)}
                >
                  {MODEL_PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  API Key {settings?.has_api_key && <span className="text-green-600">(已设置)</span>}
                </label>
                <Input
                  type="password"
                  placeholder={settings?.has_api_key ? '输入新的 API Key 以更新' : '输入 API Key'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  API Key 会被加密存储
                </p>
              </div>

              {settings?.has_api_key && (
                <Button
                  variant="outline"
                  onClick={handleClearApiKey}
                  disabled={clearingKey}
                  className="text-red-600 hover:text-red-700"
                >
                  {clearingKey ? '删除中...' : '删除 API Key'}
                </Button>
              )}
            </div>

            <div className="mt-6 pt-4 border-t">
              <div className="flex items-center gap-4">
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? '保存中...' : '保存设置'}
                </Button>
                {saved && (
                  <span className="text-sm text-green-600">已保存</span>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'review' && (
          <div className="max-w-xl">
            <h3 className="text-lg font-semibold mb-1">审核设置</h3>
            <p className="text-muted-foreground text-sm mb-6">配置章节审核行为</p>

            <div className="space-y-4">
              <div className="flex items-center justify-between py-2">
                <label className="text-sm font-medium">启用审核</label>
                <input
                  type="checkbox"
                  checked={reviewEnabled}
                  onChange={(e) => setReviewEnabled(e.target.checked)}
                  className="h-4 w-4"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">审核严格度</label>
                <select
                  className="w-full h-10 px-3 rounded-md border border-input bg-background"
                  value={reviewStrictness}
                  onChange={(e) => setReviewStrictness(e.target.value)}
                  disabled={!reviewEnabled}
                >
                  {REVIEW_STRICTNESS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t">
              <div className="flex items-center gap-4">
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? '保存中...' : '保存设置'}
                </Button>
                {saved && (
                  <span className="text-sm text-green-600">已保存</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}