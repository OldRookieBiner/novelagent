// frontend/src/pages/Settings.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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

export default function Settings() {
  const [settings, setSettings] = useState<UserSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

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

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">设置</h1>

      {/* Model Settings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>模型配置</CardTitle>
          <CardDescription>配置 AI 模型和 API Key</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
              API Key {settings?.has_api_key && '(已设置)'}
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
        </CardContent>
      </Card>

      {/* Review Settings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>审核设置</CardTitle>
          <CardDescription>配置章节审核行为</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
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
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex items-center gap-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存设置'}
        </Button>
        {saved && (
          <span className="text-sm text-green-600">已保存</span>
        )}
      </div>
    </div>
  )
}