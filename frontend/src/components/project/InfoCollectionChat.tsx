// frontend/src/components/project/InfoCollectionChat.tsx
import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { chatApi, collectedInfoApi } from '@/lib/api'
import type { CollectedInfo } from '@/types'

interface InfoCollectionChatProps {
  projectId: number
  collectedInfo?: CollectedInfo
  onInfoCollected: (info: CollectedInfo) => void
  onStageChange: (stage: string) => void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function InfoCollectionChat({
  projectId,
  collectedInfo,
  onInfoCollected,
  onStageChange,
}: InfoCollectionChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '你好！我是小说创作助手。请告诉我你想写什么类型的小说？比如题材（武侠、科幻、都市等）、主角设定、世界观背景等信息。',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [manualMode, setManualMode] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Manual input fields
  const [manualInputs, setManualInputs] = useState({
    genre: collectedInfo?.genre || '',
    main_characters: collectedInfo?.main_characters || '',
    world_setting: collectedInfo?.world_setting || '',
    theme: collectedInfo?.theme || '',
    style_preference: collectedInfo?.style_preference || '',
  })

  useEffect(() => {
    // Scroll to bottom when messages change
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      const response = await chatApi.sendMessage(projectId, { message: userMessage })

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.response },
      ])

      if (response.collected_info) {
        onInfoCollected(response.collected_info)
      }

      if (response.is_info_sufficient) {
        onStageChange('outline_generating')
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '抱歉，处理您的消息时出现错误。请稍后再试。',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleManualSubmit = async () => {
    if (!manualInputs.genre || !manualInputs.main_characters || !manualInputs.world_setting) {
      alert('请至少填写题材、主角和世界观背景')
      return
    }

    setLoading(true)
    try {
      const response = await collectedInfoApi.update(projectId, manualInputs)
      onInfoCollected(manualInputs)

      // Check if stage changed
      if (response.collected_info) {
        onStageChange('outline_generating')
      }
    } catch (err) {
      alert('保存信息时出现错误')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="flex-1">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">信息收集</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setManualMode(!manualMode)}
          >
            {manualMode ? '切换到对话模式' : '切换到手动填写'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {manualMode ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">题材 *</label>
                <Input
                  value={manualInputs.genre}
                  onChange={(e) =>
                    setManualInputs((prev) => ({ ...prev, genre: e.target.value }))
                  }
                  placeholder="例如：武侠、科幻、都市"
                />
              </div>
              <div>
                <label className="text-sm font-medium">主题</label>
                <Input
                  value={manualInputs.theme}
                  onChange={(e) =>
                    setManualInputs((prev) => ({ ...prev, theme: e.target.value }))
                  }
                  placeholder="例如：成长、复仇、爱情"
                />
              </div>
              <div>
                <label className="text-sm font-medium">主角设定 *</label>
                <Input
                  value={manualInputs.main_characters}
                  onChange={(e) =>
                    setManualInputs((prev) => ({ ...prev, main_characters: e.target.value }))
                  }
                  placeholder="主角姓名、性格、背景"
                />
              </div>
              <div>
                <label className="text-sm font-medium">世界观背景 *</label>
                <Input
                  value={manualInputs.world_setting}
                  onChange={(e) =>
                    setManualInputs((prev) => ({ ...prev, world_setting: e.target.value }))
                  }
                  placeholder="时代、地点、世界观"
                />
              </div>
              <div className="col-span-2">
                <label className="text-sm font-medium">风格偏好</label>
                <Input
                  value={manualInputs.style_preference}
                  onChange={(e) =>
                    setManualInputs((prev) => ({ ...prev, style_preference: e.target.value }))
                  }
                  placeholder="例如：轻松幽默、严肃深沉、华丽唯美"
                />
              </div>
            </div>
            <Button onClick={handleManualSubmit} disabled={loading}>
              {loading ? '保存中...' : '开始生成大纲'}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col h-[400px]">
            <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
              <div className="space-y-4">
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2 ${
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-muted rounded-lg px-4 py-2">
                      正在思考...
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
            <div className="flex gap-2 pt-4 border-t">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="输入你的想法..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage()
                  }
                }}
                disabled={loading}
              />
              <Button onClick={handleSendMessage} disabled={loading || !input.trim()}>
                发送
              </Button>
            </div>
          </div>
        )}

        {collectedInfo && Object.keys(collectedInfo).length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <div className="text-sm font-medium mb-2">已收集的信息：</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {collectedInfo.genre && (
                <div>
                  <span className="text-muted-foreground">题材：</span>
                  {collectedInfo.genre}
                </div>
              )}
              {collectedInfo.theme && (
                <div>
                  <span className="text-muted-foreground">主题：</span>
                  {collectedInfo.theme}
                </div>
              )}
              {collectedInfo.main_characters && (
                <div>
                  <span className="text-muted-foreground">主角：</span>
                  {collectedInfo.main_characters}
                </div>
              )}
              {collectedInfo.world_setting && (
                <div>
                  <span className="text-muted-foreground">背景：</span>
                  {collectedInfo.world_setting}
                </div>
              )}
              {collectedInfo.style_preference && (
                <div>
                  <span className="text-muted-foreground">风格：</span>
                  {collectedInfo.style_preference}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}