// frontend/src/components/layout/Header.tsx
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, Settings, LogOut, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/authStore'

export default function Header() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="border-b">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <BookOpen className="h-5 w-5" />
          NovelAgent
        </Link>

        <div className="flex items-center gap-4">
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
      </div>
    </header>
  )
}