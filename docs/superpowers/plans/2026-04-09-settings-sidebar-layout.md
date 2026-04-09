# 设置页面左侧导航栏实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Settings 页面重构为左侧导航栏 + 右侧内容区布局，使用状态切换而非 URL 路由。

**Architecture:** 单文件重构 Settings.tsx，添加 activeTab 状态管理左侧导航项切换，右侧内容区根据 activeTab 条件渲染对应设置内容。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, shadcn/ui

---

## Task 1: 重构 Settings.tsx 布局

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 添加 activeTab 状态和导航配置**

在 Settings.tsx 中添加 tab 状态管理。修改组件顶部：

```tsx
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
```

- [ ] **Step 2: 添加左侧导航栏渲染**

修改 return 部分，添加左侧导航栏布局：

```tsx
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
```

- [ ] **Step 3: 移除未使用的 Card 导入**

移除顶部不再使用的 Card 相关导入：

```tsx
// 删除这行：
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
```

- [ ] **Step 4: 重启 Docker 容器验证**

Run: `cd /opt/project/novelagent/novelagent && docker compose restart frontend`

Expected: frontend 容器重启成功，无报错

- [ ] **Step 5: 手动验证 UI**

打开浏览器访问 http://localhost:3001/settings，验证：
- 左侧导航栏显示"设置"标题和两个导航项
- 点击导航项切换右侧内容区
- 模型配置和审核设置的表单功能正常
- 保存按钮在每个内容区底部独立显示

- [ ] **Step 6: 提交更改**

```bash
cd /opt/project/novelagent/novelagent
git add frontend/src/pages/Settings.tsx
git commit -m "$(cat <<'EOF'
feat: refactor Settings page with left navigation sidebar

- Add tab state for switching between Model Config and Review Settings
- Left sidebar (220px) with navigation items
- Right content area renders based on active tab
- Use shadcn/ui theme colors (bg-secondary for selected item)
- Remove Card wrapper, direct content display

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

- [x] Spec coverage: Task 1 实现所有设计要求（左侧导航栏、状态切换、主题样式）
- [x] Placeholder scan: 无 TBD/TODO，所有代码完整
- [x] Type consistency: SettingsTab 类型定义与使用一致