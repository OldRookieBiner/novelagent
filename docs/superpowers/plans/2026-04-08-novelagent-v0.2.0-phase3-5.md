# NovelAgent v0.2.0 Implementation Plan - Phase 3-5

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成前端实现、功能集成和部署验证

**Architecture:** React 18 + Vite + shadcn/ui + Zustand, TipTap 编辑器, SSE 流式请求

**前置条件:** Phase 1-2 已完成

---

## Phase 3: 前端基础设施

### Task 18: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "novelagent-frontend",
  "version": "0.2.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "zustand": "^4.5.0",
    "@tiptap/react": "^2.2.0",
    "@tiptap/starter-kit": "^2.2.0",
    "@tiptap/extension-placeholder": "^2.2.0",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-select": "^2.0.0",
    "@radix-ui/react-slot": "^1.0.2",
    "@radix-ui/react-progress": "^1.0.3",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "lucide-react": "^0.344.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.56",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.2.2",
    "vite": "^5.1.4"
  }
}
```

- [ ] **Step 2: 创建 vite.config.ts**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: 创建 tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: 创建 tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 6: 创建 postcss.config.js**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 7: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NovelAgent - AI 小说创作助手</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: 创建 main.tsx**

```tsx
// frontend/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 9: 创建 index.css**

```css
/* frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

- [ ] **Step 10: 提交**

```bash
git add frontend/
git commit -m "feat: initialize React frontend with Vite and Tailwind"
```

---

### Task 19: shadcn/ui 组件配置

**Files:**
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/card.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/dialog.tsx`
- Create: `frontend/src/components/ui/select.tsx`
- Create: `frontend/src/components/ui/progress.tsx`

- [ ] **Step 1: 创建 utils.ts**

```typescript
// frontend/src/lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 2: 创建 Button 组件**

```tsx
// frontend/src/components/ui/button.tsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

- [ ] **Step 3: 创建 Card 组件**

```tsx
// frontend/src/components/ui/card.tsx
import * as React from "react"

import { cn } from "@/lib/utils"

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
```

- [ ] **Step 4: 创建 Input 组件**

```tsx
// frontend/src/components/ui/input.tsx
import * as React from "react"

import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
```

- [ ] **Step 5: 创建 Progress 组件**

```tsx
// frontend/src/components/ui/progress.tsx
import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"

import { cn } from "@/lib/utils"

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root>
>(({ className, value, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn(
      "relative h-4 w-full overflow-hidden rounded-full bg-secondary",
      className
    )}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full w-full flex-1 bg-primary transition-all"
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/lib/utils.ts frontend/src/components/ui/
git commit -m "feat: add shadcn/ui components"
```

---

### Task 20: 类型定义和 API 客户端

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: 创建类型定义**

```typescript
// frontend/src/types/index.ts
export interface User {
  id: number
  username: string
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  success: boolean
  user: User
  session_token: string
}

export interface Project {
  id: number
  user_id: number
  name: string
  stage: string
  target_words: number
  total_words: number
  created_at: string
  updated_at: string
}

export interface ProjectDetail extends Project {
  chapter_count: number
  completed_chapters: number
  progress_percentage: number
}

export interface ProjectListResponse {
  projects: Project[]
  total: number
}

export interface ProjectCreate {
  name: string
  target_words?: number
}

export interface CollectedInfo {
  genre?: string
  theme?: string
  main_characters?: string
  world_setting?: string
  style_preference?: string
}

export interface Outline {
  id: number
  project_id: number
  title: string | null
  summary: string | null
  plot_points: string[] | null
  collected_info: CollectedInfo | null
  chapter_count_suggested: number
  chapter_count_confirmed: boolean
  confirmed: boolean
  created_at: string
  updated_at: string
}

export interface ChapterOutline {
  id: number
  project_id: number
  chapter_number: number
  title: string | null
  scene: string | null
  characters: string | null
  plot: string | null
  conflict: string | null
  ending: string | null
  target_words: number
  confirmed: boolean
  created_at: string
  has_content: boolean
}

export interface Chapter {
  id: number
  chapter_outline_id: number
  content: string | null
  word_count: number
  review_passed: boolean
  review_feedback: string | null
  created_at: string
  updated_at: string
}

export interface UserSettings {
  model_provider: string
  model_name: string
  has_api_key: boolean
  review_enabled: boolean
  review_strictness: string
}

export interface SettingsUpdate {
  model_provider?: string
  model_name?: string
  api_key?: string
  review_enabled?: boolean
  review_strictness?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
```

- [ ] **Step 2: 创建 API 客户端**

```typescript
// frontend/src/lib/api.ts
const API_BASE = '/api'

// Session token stored in memory
let sessionToken: string | null = null

export function setSessionToken(token: string | null) {
  sessionToken = token
}

export function getSessionToken(): string | null {
  return sessionToken
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  // Add session token as Basic auth
  if (sessionToken) {
    headers['Authorization'] = `Basic ${btoa(sessionToken + ':')}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// Auth API
export const authApi = {
  login: (data: import('@/types').LoginRequest) =>
    request<import('@/types').LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  logout: () => request('/auth/logout', { method: 'POST' }),

  me: () => request<import('@/types').User>('/auth/me'),
}

// Projects API
export const projectsApi = {
  list: () => request<import('@/types').ProjectListResponse>('/projects'),

  get: (id: number) => request<import('@/types').ProjectDetail>(`/projects/${id}`),

  create: (data: import('@/types').ProjectCreate) =>
    request<import('@/types').Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: number, data: Partial<import('@/types').Project>) =>
    request<import('@/types').Project>(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    request(`/projects/${id}`, { method: 'DELETE' }),
}

// Outline API
export const outlineApi = {
  get: (projectId: number) =>
    request<import('@/types').Outline>(`/projects/${projectId}/outline`),

  create: (projectId: number) =>
    request<import('@/types').Outline>(`/projects/${projectId}/outline`, {
      method: 'POST',
    }),

  update: (projectId: number, data: Partial<import('@/types').Outline>) =>
    request<import('@/types').Outline>(`/projects/${projectId}/outline`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  confirm: (projectId: number) =>
    request(`/projects/${projectId}/outline/confirm`, { method: 'POST' }),
}

// Chapter Outlines API
export const chapterOutlinesApi = {
  list: (projectId: number) =>
    request<import('@/types').ChapterOutline[]>(`/projects/${projectId}/chapter-outlines`),

  create: (projectId: number, chapterCount: number) =>
    request<import('@/types').ChapterOutline[]>(`/projects/${projectId}/chapter-outlines`, {
      method: 'POST',
      body: JSON.stringify({ chapter_count: chapterCount }),
    }),

  update: (projectId: number, chapterNum: number, data: Partial<import('@/types').ChapterOutline>) =>
    request<import('@/types').ChapterOutline>(`/projects/${projectId}/chapter-outlines/${chapterNum}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  confirm: (projectId: number) =>
    request(`/projects/${projectId}/chapter-outlines/confirm`, { method: 'POST' }),
}

// Chapters API
export const chaptersApi = {
  get: (projectId: number, chapterNum: number) =>
    request<import('@/types').Chapter>(`/projects/${projectId}/chapters/${chapterNum}`),

  update: (projectId: number, chapterNum: number, content: string) =>
    request<import('@/types').Chapter>(`/projects/${projectId}/chapters/${chapterNum}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),

  review: (projectId: number, chapterNum: number, strictness?: string) =>
    request<{ passed: boolean; feedback: string }>(`/projects/${projectId}/chapters/${chapterNum}/review`, {
      method: 'POST',
      body: JSON.stringify({ strictness }),
    }),
}

// Settings API
export const settingsApi = {
  get: () => request<import('@/types').UserSettings>('/settings'),

  update: (data: import('@/types').SettingsUpdate) =>
    request<import('@/types').UserSettings>('/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat: add TypeScript types and API client"
```

---

### Task 21: Zustand Stores

**Files:**
- Create: `frontend/src/stores/authStore.ts`
- Create: `frontend/src/stores/projectStore.ts`
- Create: `frontend/src/stores/settingsStore.ts`

- [ ] **Step 1: 创建认证 Store**

```typescript
// frontend/src/stores/authStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { setSessionToken } from '@/lib/api'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => {
        setSessionToken(token)
        set({ token, isAuthenticated: !!token })
      },
      logout: () => {
        setSessionToken(null)
        set({ user: null, token: null, isAuthenticated: false })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          setSessionToken(state.token)
        }
      },
    }
  )
)
```

- [ ] **Step 2: 创建项目 Store**

```typescript
// frontend/src/stores/projectStore.ts
import { create } from 'zustand'
import type { ProjectDetail, Outline, ChapterOutline } from '@/types'

interface ProjectState {
  currentProject: ProjectDetail | null
  outline: Outline | null
  chapterOutlines: ChapterOutline[]
  currentChapterNum: number
  setCurrentProject: (project: ProjectDetail | null) => void
  setOutline: (outline: Outline | null) => void
  setChapterOutlines: (outlines: ChapterOutline[]) => void
  setCurrentChapterNum: (num: number) => void
  clear: () => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  outline: null,
  chapterOutlines: [],
  currentChapterNum: 1,
  setCurrentProject: (project) => set({ currentProject: project }),
  setOutline: (outline) => set({ outline }),
  setChapterOutlines: (outlines) => set({ chapterOutlines: outlines }),
  setCurrentChapterNum: (num) => set({ currentChapterNum: num }),
  clear: () => set({
    currentProject: null,
    outline: null,
    chapterOutlines: [],
    currentChapterNum: 1,
  }),
}))
```

- [ ] **Step 3: 创建设置 Store**

```typescript
// frontend/src/stores/settingsStore.ts
import { create } from 'zustand'
import type { UserSettings } from '@/types'

interface SettingsState {
  settings: UserSettings | null
  setSettings: (settings: UserSettings) => void
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  setSettings: (settings) => set({ settings }),
}))
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/stores/
git commit -m "feat: add Zustand stores for auth, project, and settings"
```

---

### Task 22: App 和路由配置

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/layout/Layout.tsx`
- Create: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: 创建 App.tsx**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import Layout from '@/components/layout/Layout'
import Login from '@/pages/Login'
import Home from '@/pages/Home'
import ProjectDetail from '@/pages/ProjectDetail'
import Writing from '@/pages/Writing'
import Reading from '@/pages/Reading'
import Settings from '@/pages/Settings'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Home />} />
          <Route path="project/:id" element={<ProjectDetail />} />
          <Route path="project/:id/write" element={<Writing />} />
          <Route path="project/:id/read/:chapterNum" element={<Reading />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
```

- [ ] **Step 2: 创建 Layout**

```tsx
// frontend/src/components/layout/Layout.tsx
import { Outlet } from 'react-router-dom'
import Header from './Header'

export default function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 3: 创建 Header**

```tsx
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
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/App.tsx frontend/src/components/layout/
git commit -m "feat: add app routing and layout components"
```

---

## Phase 3 自检

**Spec 覆盖检查：**

| 设计文档要求 | 对应任务 |
|-------------|---------|
| React 18 + Vite | Task 18 |
| shadcn/ui | Task 19 |
| Tailwind CSS | Task 18 |
| Zustand 状态管理 | Task 21 |
| React Router | Task 22 |

**占位符检查：** ✅ 无 TBD、TODO

---

## Phase 4: 页面实现

### Task 23: 登录页面

**Files:**
- Create: `frontend/src/pages/Login.tsx`

- [ ] **Step 1: 创建登录页面**

```tsx
// frontend/src/pages/Login.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/lib/api'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const setUser = useAuthStore((state) => state.setUser)
  const setToken = useAuthStore((state) => state.setToken)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await authApi.login({ username, password })
      setUser(response.user)
      setToken(response.session_token)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">NovelAgent</CardTitle>
          <CardDescription>AI 小说创作助手</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-sm text-destructive text-center">{error}</div>
            )}
            <div className="space-y-2">
              <Input
                type="text"
                placeholder="用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Input
                type="password"
                placeholder="密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? '登录中...' : '登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/Login.tsx
git commit -m "feat: add login page"
```

---

### Task 24: 首页 - 项目列表

**Files:**
- Create: `frontend/src/pages/Home.tsx`
- Create: `frontend/src/components/common/ProjectCard.tsx`

- [ ] **Step 1: 创建项目卡片组件**

```tsx
// frontend/src/components/common/ProjectCard.tsx
import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import type { ProjectDetail } from '@/types'

interface ProjectCardProps {
  project: ProjectDetail
  onDelete: (id: number) => void
}

const STAGE_LABELS: Record<string, { label: string; color: string }> = {
  collecting_info: { label: '信息收集', color: 'bg-yellow-500' },
  outline_generating: { label: '生成大纲', color: 'bg-blue-500' },
  outline_confirming: { label: '确认大纲', color: 'bg-blue-500' },
  chapter_outlines_generating: { label: '生成章节纲', color: 'bg-purple-500' },
  chapter_writing: { label: '写作中', color: 'bg-green-500' },
  completed: { label: '已完成', color: 'bg-emerald-500' },
  paused: { label: '暂停', color: 'bg-gray-500' },
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const stageInfo = STAGE_LABELS[project.stage] || { label: project.stage, color: 'bg-gray-500' }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <h3 className="font-semibold text-lg truncate">{project.name}</h3>
          <span className={`px-2 py-0.5 rounded text-xs text-white ${stageInfo.color}`}>
            {stageInfo.label}
          </span>
        </div>

        <div className="space-y-1 text-sm text-muted-foreground mb-3">
          <div>📝 第 {project.completed_chapters} 章 / 共 {project.chapter_count} 章</div>
          <div>📏 {project.total_words.toLocaleString()} 字</div>
          <div>🕐 {new Date(project.updated_at).toLocaleDateString()}</div>
        </div>

        <div className="mb-3">
          <Progress value={project.progress_percentage} className="h-2" />
          <div className="text-xs text-muted-foreground mt-1">
            进度 {project.progress_percentage}%
          </div>
        </div>

        <div className="flex gap-2">
          <Link to={`/project/${project.id}`} className="flex-1">
            <Button className="w-full" size="sm">
              {project.stage === 'completed' ? '查看' : '继续'}
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDelete(project.id)}
          >
            删除
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 2: 创建首页**

```tsx
// frontend/src/pages/Home.tsx
import { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import ProjectCard from '@/components/common/ProjectCard'
import { projectsApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { ProjectDetail } from '@/types'

export default function Home() {
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creating, setCreating] = useState(false)

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const fetchProjects = async () => {
    try {
      const response = await projectsApi.list()
      // Fetch details for each project
      const details = await Promise.all(
        response.projects.map(p => projectsApi.get(p.id))
      )
      setProjects(details)
    } catch (err) {
      console.error('Failed to fetch projects:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects()
    }
  }, [isAuthenticated])

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return

    setCreating(true)
    try {
      await projectsApi.create({ name: newProjectName })
      setShowNewProject(false)
      setNewProjectName('')
      fetchProjects()
    } catch (err) {
      console.error('Failed to create project:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteProject = async (id: number) => {
    if (!confirm('确定要删除这个项目吗？')) return

    try {
      await projectsApi.delete(id)
      setProjects(projects.filter(p => p.id !== id))
    } catch (err) {
      console.error('Failed to delete project:', err)
    }
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">我的项目</h1>
        <Button onClick={() => setShowNewProject(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建项目
        </Button>
      </div>

      {showNewProject && (
        <Card className="mb-6">
          <CardContent className="p-4">
            <div className="flex gap-2">
              <Input
                placeholder="项目名称"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
              />
              <Button onClick={handleCreateProject} disabled={creating}>
                {creating ? '创建中...' : '创建'}
              </Button>
              <Button variant="outline" onClick={() => setShowNewProject(false)}>
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {projects.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <p>还没有项目，点击上方按钮创建第一个项目</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={handleDeleteProject}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Home.tsx frontend/src/components/common/ProjectCard.tsx
git commit -m "feat: add home page with project cards"
```

---

由于计划内容很长，我将在后续文件中继续编写剩余任务。是否继续编写 Phase 4-5 的完整计划？