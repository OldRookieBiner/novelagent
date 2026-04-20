# 目标字数输入框优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将目标字数从下拉框改为数字输入框，删除小说篇幅选项，添加字数与篇幅对应关系的提示。

**Architecture:** 修改前端类型定义和多个组件，targetWords 从 string 改为 number，删除 novelLength 相关代码。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, shadcn/ui

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/types/index.ts` | 修改 | 删除 novelLength/customChapterCount，targetWords 改为 number |
| `frontend/src/lib/inspiration.ts` | 修改 | 删除 novelLength 选项，更新类型和模板生成 |
| `frontend/src/components/project/InspirationForm.tsx` | 修改 | 删除篇幅下拉框，目标字数改为输入框+tips |
| `frontend/src/components/project/InspirationDisplay.tsx` | 修改 | 删除篇幅显示，更新目标字数显示 |
| `frontend/src/components/project/InspirationEditor.tsx` | 修改 | 同上 |
| `frontend/src/pages/ProjectDetail.tsx` | 修改 | 删除 valueLabels 中的 novelLength |

---

### Task 1: 更新类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 更新 CollectedInfo 接口**

将 `CollectedInfo` 接口中的 `targetWords` 改为 `number` 类型，删除 `novelLength` 和 `customChapterCount` 字段：

```typescript
export interface CollectedInfo {
  novelType?: string;
  targetWords?: number;           // 改为 number 类型
  coreTheme?: string;
  worldSetting?: string;
  customWorldSetting?: string;
  protagonist?: string;
  customProtagonist?: string;
  stylePreference?: string;
  // 新增字段
  targetReader?: string;          // 'male' | 'female'
  wordsPerChapter?: string;       // 每章字数
  customWordsPerChapter?: number;
  narrative?: string;             // 'first' | 'third'
  goldFinger?: string;            // 金手指类型
  customGoldFinger?: string;
}
```

- [ ] **Step 2: 提交类型修改**

```bash
git add frontend/src/types/index.ts
git commit -m "refactor(types): change targetWords to number, remove novelLength"
```

---

### Task 2: 更新灵感配置和工具函数

**Files:**
- Modify: `frontend/src/lib/inspiration.ts`

- [ ] **Step 1: 更新 InspirationData 接口**

删除 `novelLength`、`customChapterCount`、`customTargetWords` 字段，`targetWords` 改为 number：

```typescript
export interface InspirationData {
  novelType: string
  targetWords: number           // 改为 number 类型
  coreTheme: string
  worldSetting?: string
  customWorldSetting?: string
  protagonist?: string
  customProtagonist?: string
  stylePreference?: string
  // 新增字段
  targetReader: string
  wordsPerChapter: string
  customWordsPerChapter?: number
  narrative?: string
  goldFinger?: string
  customGoldFinger?: string
}
```

- [ ] **Step 2: 删除 novelLength 和 targetWords 选项配置**

删除 `INSPIRATION_OPTIONS` 中的 `novelLength` 和 `targetWords` 配置。

- [ ] **Step 3: 删除 getLengthDisplay 和 getTargetWordsDisplay 函数**

删除以下函数：
- `getLengthDisplay`
- `getTargetWordsDisplay`
- `getChapterCount`（依赖于 novelLength）
- `getTotalWords`（依赖于 targetWords）

- [ ] **Step 4: 更新 generateInspirationTemplate 函数**

修改模板生成，使用 `targetWords` 数字直接显示：

```typescript
export function generateInspirationTemplate(data: InspirationData): string {
  const novelType = getOptionLabel(INSPIRATION_OPTIONS.novelTypes, data.novelType)
  const targetWords = data.targetWords ? `${data.targetWords.toLocaleString()}字` : '未设置'
  const wordsPerChapter = getWordsPerChapterDisplay(data)
  const coreTheme = getOptionLabel(INSPIRATION_OPTIONS.coreThemes, data.coreTheme)
  // ... 其他字段

  return `# 小说创作灵感

## 基本信息

- **目标读者**：${data.targetReader === 'male' ? '男频' : data.targetReader === 'female' ? '女频' : '未设置'}
- **小说类型**：${novelType || '未设置'}
- **目标字数**：${targetWords}
- **每章字数**：${wordsPerChapter || '未设置'}

## 叙事设定

- **叙事视角**：${narrative || '未设置'}

## 核心设定

- **核心主题**：${coreTheme || '未设置'}
- **世界观**：${worldSetting || '未设置'}
- **主角**：${protagonist || '未设置'}
- **金手指**：${goldFinger || '未设置'}

## 风格

- **风格偏好**：${style || '未设置'}

## 补充灵感

> 在下方添加更多灵感细节...

-

-

`
}
```

- [ ] **Step 5: 更新 parseTemplateToData 函数**

删除 novelLength 相关解析，更新 targetWords 解析逻辑：

```typescript
export function parseTemplateToData(template: string): Partial<InspirationData> {
  const lines = template.split('\n')
  const data: Partial<InspirationData> = {}

  for (const line of lines) {
    // ... 其他字段解析 ...
    
    if (line.includes('**目标字数**')) {
      const value = line.split('：')[1]?.trim()
      // 移除"字"和逗号，解析数字
      const numStr = value?.replace(/[字,，]/g, '').replace(/万/g, '0000')
      if (numStr && !isNaN(parseInt(numStr))) {
        data.targetWords = parseInt(numStr)
      }
    }
    
    // 删除 novelLength 相关解析
  }

  return data
}
```

- [ ] **Step 6: 验证编译**

```bash
cd /opt/project/novelagent/frontend && npm run build 2>&1 | head -30
```

- [ ] **Step 7: 提交配置修改**

```bash
git add frontend/src/lib/inspiration.ts
git commit -m "refactor(inspiration): change targetWords to number, remove novelLength"
```

---

### Task 3: 更新 InspirationForm 组件

**Files:**
- Modify: `frontend/src/components/project/InspirationForm.tsx`

- [ ] **Step 1: 删除 novelLength 相关状态和 UI**

删除：
- `novelLength` state
- `customChapterCount` state
- 小说篇幅下拉框 UI
- 自定义章节数输入框

- [ ] **Step 2: 修改 targetWords 状态为 number**

```typescript
const [targetWords, setTargetWords] = useState<number>(
  initialData?.targetWords || 0
)
```

- [ ] **Step 3: 添加目标字数输入框和 Tips**

替换目标字数下拉框为输入框：

```tsx
<div>
  <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
    目标字数
    <span className="text-red-500">*</span>
    {/* Tips 图标 */}
    <div className="relative group ml-1">
      <svg
        className="w-4 h-4 text-gray-400 cursor-help hover:text-blue-500"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {/* Tooltip */}
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
  </div>
  <div className="flex items-center gap-2">
    <Input
      type="number"
      className="flex-1 h-11"
      value={targetWords || ''}
      onChange={(e) => {
        setTargetWords(parseInt(e.target.value) || 0)
        if (errors.targetWords) setErrors({ ...errors, targetWords: '' })
      }}
      placeholder="输入目标字数"
    />
    <span className="text-sm text-gray-500">字</span>
  </div>
  {errors.targetWords && <p className="text-red-500 text-xs mt-1">{errors.targetWords}</p>}
</div>
```

- [ ] **Step 4: 更新验证逻辑**

```typescript
if (!targetWords || targetWords < 10000) {
  newErrors.targetWords = '请输入目标字数（至少1万字）'
}
```

- [ ] **Step 5: 更新自动保存草稿逻辑**

删除 novelLength 相关字段，更新 targetWords：

```typescript
const data: InspirationData = {
  novelType,
  targetWords,
  coreTheme,
  // ... 其他字段，删除 novelLength, customChapterCount, customTargetWords
}
```

- [ ] **Step 6: 更新 handleSubmit 函数**

```typescript
const data: InspirationData = {
  novelType,
  targetWords,
  coreTheme,
  // ... 删除 novelLength, customChapterCount, customTargetWords
}
```

- [ ] **Step 7: 更新 handleClear 函数**

删除 novelLength 和 customChapterCount 的清除逻辑。

- [ ] **Step 8: 删除下拉框从 3 列改为 2 列**

将 grid 从 `grid-cols-3` 改为 `grid-cols-2`（只保留目标字数和每章字数）。

- [ ] **Step 9: 验证编译**

```bash
cd /opt/project/novelagent/frontend && npm run build 2>&1 | head -30
```

- [ ] **Step 10: 提交表单修改**

```bash
git add frontend/src/components/project/InspirationForm.tsx
git commit -m "refactor(InspirationForm): change targetWords to input, remove novelLength, add tips"
```

---

### Task 4: 更新 InspirationDisplay 组件

**Files:**
- Modify: `frontend/src/components/project/InspirationDisplay.tsx`

- [ ] **Step 1: 删除篇幅显示**

删除 `getLengthDisplay` 函数和篇幅显示 UI。

- [ ] **Step 2: 更新目标字数显示**

```tsx
<div>
  <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
    目标字数
    {/* Tips 图标 */}
    <div className="relative group ml-1">
      <svg className="w-4 h-4 text-gray-400 cursor-help hover:text-blue-500" ...>
        ...
      </svg>
      <div className="tooltip ...">
        ...
      </div>
    </div>
  </div>
  <div className="h-11 px-3 rounded-lg border-2 border-gray-200 bg-gray-50 flex items-center text-sm">
    {data.targetWords ? `${data.targetWords.toLocaleString()}字` : '-'}
  </div>
</div>
```

- [ ] **Step 3: 更新 grid 布局**

将基本设定区域从 3 列改为 2 列。

- [ ] **Step 4: 提交修改**

```bash
git add frontend/src/components/project/InspirationDisplay.tsx
git commit -m "refactor(InspirationDisplay): update targetWords display, remove novelLength"
```

---

### Task 5: 更新 InspirationEditor 组件

**Files:**
- Modify: `frontend/src/components/project/InspirationEditor.tsx`

- [ ] **Step 1: 删除篇幅和自定义章节数相关 UI**

删除小说篇幅下拉框和自定义章节数输入框。

- [ ] **Step 2: 更新目标字数为输入框**

将目标字数下拉框改为数字输入框。

- [ ] **Step 3: 更新 grid 布局**

调整布局适应新的字段数量。

- [ ] **Step 4: 提交修改**

```bash
git add frontend/src/components/project/InspirationEditor.tsx
git commit -m "refactor(InspirationEditor): update targetWords to input, remove novelLength"
```

---

### Task 6: 更新 ProjectDetail 页面

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 删除 valueLabels 中的 novelLength**

删除 `valueLabels` 对象中的 `novelLength` 映射。

- [ ] **Step 2: 提交修改**

```bash
git add frontend/src/pages/ProjectDetail.tsx
git commit -m "refactor(ProjectDetail): remove novelLength from valueLabels"
```

---

### Task 7: 构建并测试

**Files:**
- None (验证步骤)

- [ ] **Step 1: 构建前端**

```bash
cd /opt/project/novelagent && docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 2: 重启后端**

```bash
cd /opt/project/novelagent && docker compose restart backend
```

- [ ] **Step 3: 验证功能**

1. 创建新项目
2. 进入灵感采集步骤
3. 验证：
   - 小说篇幅选项已删除
   - 目标字数为数字输入框
   - 鼠标悬浮 ? 图标显示 tips
   - 输入字数正常保存

- [ ] **Step 4: 最终提交**

```bash
git add -A
git status
git commit -m "feat: change targetWords to number input, remove novelLength, add tips"
```

---

## Success Criteria

1. ✅ 目标字数使用数字输入框，单位为"字"
2. ✅ 删除小说篇幅选项
3. ✅ ? 图标悬浮显示字数与篇幅对应关系
4. ✅ 所有相关文件正确更新
5. ✅ 灵感模板正确显示目标字数
6. ✅ 历史视图正确显示目标字数
