// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { Toaster } from '@/components/ui/sonner'
import Layout from '@/components/layout/Layout'
import ErrorBoundary from '@/components/common/ErrorBoundary'
import Login from '@/pages/Login'
import Home from '@/pages/Home'
import Settings from '@/pages/Settings'
import ProjectWorkbench from '@/pages/ProjectWorkbench'

function RedirectToWorkbench() {
  const { id } = useParams()
  return <Navigate to={`/project/${id}/workbench`} replace />
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((state) => state.token)
  const hasHydrated = useAuthStore((state) => state._hasHydrated)

  // 从 token 推导认证状态，而不是依赖 isAuthenticated（可能未正确恢复）
  const isAuthenticated = !!token

  // 等待 rehydration 完成
  if (!hasHydrated) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          {/* 首页使用独立全屏布局 */}
          <Route
            path="/"
            element={
              <PrivateRoute>
                <Home />
              </PrivateRoute>
            }
            index
          />
          {/* 工作台页面使用独立布局（全屏） */}
          <Route
            path="/project/:id/workbench"
            element={
              <PrivateRoute>
                <ProjectWorkbench />
              </PrivateRoute>
            }
          />
          {/* 设置页面使用独立全屏布局 */}
          <Route
            path="/settings"
            element={
              <PrivateRoute>
                <Settings />
              </PrivateRoute>
            }
          />
          {/* 项目重定向使用 Layout */}
          <Route
            path="/"
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route path="project/:id" element={<RedirectToWorkbench />} />
          </Route>
        </Routes>
        <Toaster />
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App