import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import {
  INSPIRATION_OPTIONS,
  generateInspirationTemplate,
  type InspirationData,
} from '@/lib/inspiration'

interface InspirationEditorProps {
  data: InspirationData
  template: string
  onDataChange: (data: InspirationData) => void
  onTemplateChange: (template: string) => void
  onConfirm: () => void
  onBack: () => void
}

export default function InspirationEditor({
  data,
  template,
  onDataChange,
  onTemplateChange,
  onConfirm,
  onBack,
}: InspirationEditorProps) {
  // 更新数据并同步模板
  const updateData = (newData: InspirationData) => {
    onDataChange(newData)
    onTemplateChange(generateInspirationTemplate(newData))
  }

  const showCustomWordsPerChapter = data.wordsPerChapter === 'custom'
  const showCustomWorld = data.worldSetting === 'custom'
  const showCustomProtagonist = data.protagonist === 'custom'
  const showCustomGoldFinger = data.goldFinger === 'custom'

  return (
    <div className="space-y-4">
      {/* 上半部分：表单区域 */}
      <div className="p-4 border rounded-lg bg-gray-50">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-gray-700">基本信息</h4>
          <div className="flex gap-4 text-sm text-gray-600">
            <span>目标字数: <strong>{data.targetWords ? data.targetWords.toLocaleString() : 0}字</strong></span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 目标读者 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">目标读者</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.targetReader}
              onChange={(e) => updateData({ ...data, targetReader: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.targetReader.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 小说类型 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">小说类型</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.novelType}
              onChange={(e) => updateData({ ...data, novelType: e.target.value })}
            >
              {INSPIRATION_OPTIONS.novelTypes.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 目标字数 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1">
              目标字数
              <div className="relative group ml-1">
                <svg
                  className="w-3 h-3 text-gray-400 cursor-help hover:text-blue-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
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
            </label>
            <Input
              type="number"
              className="h-9 text-sm"
              value={data.targetWords || ''}
              onChange={(e) => updateData({ ...data, targetWords: parseInt(e.target.value) || 0 })}
              placeholder="输入目标字数"
            />
          </div>

          {/* 每章字数 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">每章字数</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.wordsPerChapter}
              onChange={(e) => updateData({ ...data, wordsPerChapter: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.wordsPerChapter.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 自定义每章字数 */}
          {showCustomWordsPerChapter && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">自定义每章字数</label>
              <Input
                type="number"
                className="h-9 text-sm"
                value={data.customWordsPerChapter || ''}
                onChange={(e) => updateData({ ...data, customWordsPerChapter: parseInt(e.target.value) || undefined })}
                placeholder="输入字数"
              />
            </div>
          )}

          {/* 核心主题 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">核心主题</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.coreTheme}
              onChange={(e) => updateData({ ...data, coreTheme: e.target.value })}
            >
              {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          {/* 叙事视角 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">叙事视角</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.narrative}
              onChange={(e) => updateData({ ...data, narrative: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.narrative.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 世界观 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">世界观设定</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.worldSetting}
              onChange={(e) => updateData({ ...data, worldSetting: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.worldSettings.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 自定义世界观 */}
          {showCustomWorld && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">自定义世界观</label>
              <Input
                type="text"
                className="h-9 text-sm"
                value={data.customWorldSetting || ''}
                onChange={(e) => updateData({ ...data, customWorldSetting: e.target.value })}
                placeholder="输入世界观设定"
              />
            </div>
          )}

          {/* 主角设定 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">主角设定</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.protagonist}
              onChange={(e) => updateData({ ...data, protagonist: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.protagonistTypes.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 自定义主角 */}
          {showCustomProtagonist && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">自定义主角</label>
              <Input
                type="text"
                className="h-9 text-sm"
                value={data.customProtagonist || ''}
                onChange={(e) => updateData({ ...data, customProtagonist: e.target.value })}
                placeholder="输入主角设定"
              />
            </div>
          )}

          {/* 金手指设定 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">金手指设定</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.goldFinger}
              onChange={(e) => updateData({ ...data, goldFinger: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.goldFinger.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 自定义金手指 */}
          {showCustomGoldFinger && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">自定义金手指</label>
              <Input
                type="text"
                className="h-9 text-sm"
                value={data.customGoldFinger || ''}
                onChange={(e) => updateData({ ...data, customGoldFinger: e.target.value })}
                placeholder="输入金手指设定"
              />
            </div>
          )}

          {/* 风格偏好 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">风格偏好</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.stylePreference}
              onChange={(e) => updateData({ ...data, stylePreference: e.target.value })}
            >
              <option value="">未设置</option>
              {INSPIRATION_OPTIONS.stylePreferences.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 下半部分：Markdown 编辑区 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium text-gray-700">补充灵感</h4>
          <span className="text-xs text-gray-400">支持 Markdown 格式，可自由编辑</span>
        </div>
        <Textarea
          className="min-h-[300px] font-mono text-sm leading-relaxed"
          value={template}
          onChange={(e) => onTemplateChange(e.target.value)}
          placeholder="灵感模板内容..."
        />
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="outline" onClick={onBack}>
          上一步
        </Button>
        <Button onClick={onConfirm}>确认，生成大纲</Button>
      </div>
    </div>
  )
}
