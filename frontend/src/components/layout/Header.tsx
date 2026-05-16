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
