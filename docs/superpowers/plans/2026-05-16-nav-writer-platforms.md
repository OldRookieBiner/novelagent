# 导航栏创作平台快捷链接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在顶部导航栏添加"创作平台"下拉菜单，一键跳转5个热门小说作家平台

**Architecture:** 在现有 Header.tsx 中硬编码平台列表常量，使用 shadcn/ui DropdownMenu 组件实现下拉菜单，点击新标签页打开外链

**Tech Stack:** React + shadcn/ui DropdownMenu + lucide-react ExternalLink 图标

---

### Task 1: 添加创作平台下拉菜单

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: 在 Header.tsx 中添加平台常量和 DropdownMenu**

在文件顶部添加导入：

```tsx
import { BookOpen, Settings, LogOut, User, ExternalLink } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
```

在组件外部添加平台常量：

```tsx
// 热门小说创作平台
const WRITER_PLATFORMS = [
  { name: '番茄小说网', url: 'https://fanqienovel.com/', icon: '🍅' },
  { name: '七猫中文网', url: 'https://zuozhe.qimao.com/', icon: '🐱' },
  { name: '起点中文网', url: 'https://write.qq.com/', icon: '📕' },
  { name: '晋江文学城', url: 'https://www.jjwxc.net/', icon: '💜' },
  { name: '飞卢小说', url: 'https://www.faloo.com/', icon: '📘' },
]
```

在 Header 组件 return 中，Logo `</Link>` 和右侧 `<div className="flex items-center gap-4">` 之间插入 DropdownMenu：

```tsx
      {/* 创作平台快捷链接 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-1.5 text-sm">
            <ExternalLink className="h-4 w-4" />
            创作平台
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {WRITER_PLATFORMS.map((platform) => (
            <DropdownMenuItem
              key={platform.name}
              onClick={() => window.open(platform.url, '_blank')}
            >
              <span>{platform.icon}</span>
              <span>{platform.name}</span>
              <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
```

完整修改后的 Header.tsx：

```tsx
// frontend/src/components/layout/Header.tsx
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, Settings, LogOut, User, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/stores/authStore'

// 热门小说创作平台
const WRITER_PLATFORMS = [
  { name: '番茄小说网', url: 'https://fanqienovel.com/', icon: '🍅' },
  { name: '七猫中文网', url: 'https://zuozhe.qimao.com/', icon: '🐱' },
  { name: '起点中文网', url: 'https://write.qq.com/', icon: '📕' },
  { name: '晋江文学城', url: 'https://www.jjwxc.net/', icon: '💜' },
  { name: '飞卢小说', url: 'https://www.faloo.com/', icon: '📘' },
]

export default function Header() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-14 border-b bg-white flex items-center justify-between px-6 shrink-0">
      <Link to="/" className="flex items-center gap-2 font-bold text-lg">
        <BookOpen className="h-5 w-5" />
        NovelAgent
      </Link>

      <div className="flex items-center gap-4">
        {/* 创作平台快捷链接 */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1.5 text-sm">
              <ExternalLink className="h-4 w-4" />
              创作平台
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {WRITER_PLATFORMS.map((platform) => (
              <DropdownMenuItem
                key={platform.name}
                onClick={() => window.open(platform.url, '_blank')}
              >
                <span>{platform.icon}</span>
                <span>{platform.name}</span>
                <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <span className="text-sm text-muted-foreground flex items-center gap-1">
          <User className="h-4 w-4" />
          {user?.username}
        </span>
        <Link to="/settings">
          <Button variant="ghost" size="icon">
            <Settings className="h-4 w-4" />
          </Button>
        </Link>
        <Button variant="ghost" size="icon" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  )
}
```

- [ ] **Step 2: 检查 shadcn/ui DropdownMenu 组件是否存在**

Run: `ls frontend/src/components/ui/dropdown-menu.tsx`

如果不存在，需要安装：

Run: `cd frontend && npx shadcn-ui@latest add dropdown-menu`

- [ ] **Step 3: 构建前端验证无报错**

Run: `cd frontend && npx tsc --noEmit`

Expected: 无类型错误

- [ ] **Step 4: 浏览器验证**

启动前端开发服务器，在浏览器中确认：
1. 导航栏出现"创作平台"按钮
2. 点击弹出下拉菜单，显示5个平台
3. 每项显示 emoji + 名称 + 外链图标
4. 点击任意平台在新标签页打开对应网址

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/layout/Header.tsx
git commit -m "feat(nav): add writer platforms dropdown menu in header"
```
