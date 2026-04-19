import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import {
  INSPIRATION_OPTIONS,
  generateInspirationTemplate,
  getChapterCount,
  getTotalWords,
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

  const showCustomChapter = data.novelLength === 'custom'
  const showCustomWords = data.targetWords === 'custom'
  const showCustomWorld = data.worldSetting === 'custom'
  const showCustomProtagonist = data.protagonist === 'custom'

  // 计算章节数和字数
  const chapterCount = getChapterCount(data)
  const totalWords = getTotalWords(data)

  return (
    <div className="space-y-4">
      {/* 上半部分：表单区域 */}
      <div className="p-4 border rounded-lg bg-gray-50">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-gray-700">基本信息</h4>
          <div className="flex gap-4 text-sm text-gray-600">
            <span>章节数: <strong>{chapterCount}</strong></span>
            <span>总字数: <strong>{totalWords}万字</strong></span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

          {/* 小说篇幅 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">小说篇幅</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.novelLength}
              onChange={(e) => updateData({ ...data, novelLength: e.target.value })}
            >
              {INSPIRATION_OPTIONS.novelLength.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                  {opt.chapters ? ` (${opt.chapters}章)` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* 自定义章节数 */}
          {showCustomChapter && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">自定义章节数</label>
              <Input
                type="number"
                className="h-9 text-sm"
                value={data.customChapterCount || ''}
                onChange={(e) => updateData({ ...data, customChapterCount: parseInt(e.target.value) || undefined })}
                placeholder="输入章节数"
              />
            </div>
          )}

          {/* 目标字数 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">目标字数</label>
            <select
              className="w-full h-9 px-3 rounded-md border border-gray-300 bg-white text-sm"
              value={data.targetWords}
              onChange={(e) => updateData({ ...data, targetWords: e.target.value })}
            >
              {INSPIRATION_OPTIONS.targetWords.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* 自定义字数 */}
          {showCustomWords && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">自定义字数（万字）</label>
              <Input
                type="number"
                className="h-9 text-sm"
                value={data.customTargetWords || ''}
                onChange={(e) => updateData({ ...data, customTargetWords: parseInt(e.target.value) || undefined })}
                placeholder="输入目标字数"
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