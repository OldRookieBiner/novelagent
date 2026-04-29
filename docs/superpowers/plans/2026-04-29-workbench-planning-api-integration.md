# 工作台规划模块 API 对接实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工作台规划模块对接后端 API，实现灵感采集保存、人物和关系的完整 CRUD 功能

**Architecture:** 使用现有的 API 客户端（collectedInfoApi、characterApi、relationApi），通过 Dialog 弹窗实现新增/编辑功能，不修改现有 UI 布局

**Tech Stack:** React 18 + TypeScript + shadcn/ui Dialog + toast

---

## 文件变更规划

### 修改文件

| 文件 | 职责 | 变更内容 |
|------|------|----------|
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 灵感采集 | 添加保存按钮，对接 collectedInfoApi |
| `frontend/src/components/workbench/planning/CharacterPanel.tsx` | 人物管理 | 添加新增/编辑 Dialog，对接 characterApi |
| `frontend/src/components/workbench/planning/RelationPanel.tsx` | 关系管理 | 添加新增/编辑 Dialog，对接 relationApi |

---

## Task 1: InspirationPanel 灵感采集保存功能

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

### 当前状态分析

- 组件有完整的表单状态（targetReader, novelType, targetWords, era, coreTheme 等）
- 使用 localStorage 草稿（saveInspirationDraft/loadInspirationDraft）
- 无后端 API 调用
- 页面顶部无保存按钮

### 实现步骤

- [ ] **Step 1: 导入 collectedInfoApi 和 toast**

```typescript
import { collectedInfoApi } from '@/lib/api'
import { toast } from 'sonner'
```

- [ ] **Step 2: 添加保存状态**

```typescript
const [saving, setSaving] = useState(false)
```

- [ ] **Step 3: 实现保存到后端函数**

```typescript
const handleSaveToServer = async () =>
{
  setSaving(true)
  try
  {
    // 构建 collected_info 数据
    const collectedInfoData: Record<string, unknown> = {}
    
    if (novelType) collectedInfoData.novelType = novelType
    if (targetWords) collectedInfoData.targetWords = targetWords
    if (coreTheme) collectedInfoData.coreTheme = coreTheme
    if (worldSetting)
    {
      collectedInfoData.worldSetting = worldSetting
      if (customWorldSetting) collectedInfoData.customWorldSetting = customWorldSetting
    }
    if (targetReader) collectedInfoData.targetReader = targetReader
    if (wordsPerChapter)
    {
      collectedInfoData.wordsPerChapter = wordsPerChapter
      if (customWordsPerChapter) collectedInfoData.customWordsPerChapter = customWordsPerChapter
    }
    if (narrative) collectedInfoData.narrative = narrative
    if (stylePreference) collectedInfoData.stylePreference = stylePreference
    if (era) collectedInfoData.era = era
    
    // 主角设定
    if (targetReader === 'male')
    {
      const lead = maleLead === 'custom' ? customMaleLead : maleLead
      if (lead) collectedInfoData.protagonist = lead
      if (genre === 'custom' ? customGenre : genre) collectedInfoData.genre = genre === 'custom' ? customGenre : genre
      const gf = goldFinger === 'custom' ? customGoldFinger : goldFinger
      if (gf) collectedInfoData.goldFinger = gf
    }
    else if (targetReader === 'female')
    {
      const lead = femaleLead === 'custom' ? customFemaleLead : femaleLead
      if (lead) collectedInfoData.protagonist = lead
    }
    
    await collectedInfoApi.update(projectId, collectedInfoData)
    toast.success('灵感已保存')
  }
  catch (err)
  {
    console.error('Failed to save inspiration:', err)
    toast.error('保存失败')
  }
  finally
  {
    setSaving(false)
  }
}
```

- [ ] **Step 4: 在页面顶部添加保存按钮**

```tsx
<div className="flex items-center justify-between mb-6">
  <h2 className="text-xl font-semibold flex items-center gap-2">
    <Lightbulb className="h-5 w-5" />
    灵感采集
  </h2>
  <Button size="sm" onClick={handleSaveToServer} disabled={saving}>
    {saving ? '保存中...' : '保存到服务器'}
  </Button>
</div>
```

- [ ] **Step 5: 提交变更**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "feat(workbench): add inspiration save to server API"
```

---

## Task 2: CharacterPanel 人物新增/编辑功能

**Files:**
- Modify: `frontend/src/components/workbench/planning/CharacterPanel.tsx`

### 当前状态分析

- 组件已导入 `characterApi` 和 `Character` 类型
- 列表和删除功能已实现
- 新增按钮调用 `toast.info('新增人物功能开发中')`
- 编辑按钮调用 `toast.info('编辑功能开发中')`

### 实现步骤

- [ ] **Step 1: 添加 Dialog 导入和编辑状态**

```typescript
import { useState, useEffect } from 'react'
import { Users, Plus, Edit, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { characterApi } from '@/lib/characterApi'
import type { Character, CharacterCreate, CharacterUpdate } from '@/types/character'

// ... existing code ...

// 在组件内添加状态
const [dialogOpen, setDialogOpen] = useState(false)
const [editingCharacter, setEditingCharacter] = useState<Character | null>(null)
// 表单状态
const [formName, setFormName] = useState('')
const [formRole, setFormRole] = useState('配角')
const [formPersonality, setFormPersonality] = useState('')
const [formMotivation, setFormMotivation] = useState('')
const [formCatchphrase, setFormCatchphrase] = useState('')
const [formBackstory, setFormBackstory] = useState('')
const [formAppearance, setFormAppearance] = useState('')
const [formHabitAction, setFormHabitAction] = useState('')
const [formDeepFear, setFormDeepFear] = useState('')
const [formGrowthArc, setFormGrowthArc] = useState('')
const [submitting, setSubmitting] = useState(false)
```

- [ ] **Step 2: 实现打开弹窗逻辑**

```typescript
const openCreateDialog = () =>
{
  setEditingCharacter(null)
  resetForm()
  setDialogOpen(true)
}

const openEditDialog = (character: Character) =>
{
  setEditingCharacter(character)
  setFormName(character.name)
  setFormRole(character.role)
  setFormPersonality(character.personality || '')
  setFormMotivation(character.core_motivation || '')
  setFormCatchphrase(character.catchphrase || '')
  setFormBackstory(character.backstory || '')
  setFormAppearance(character.appearance || '')
  setFormHabitAction(character.habit_action || '')
  setFormDeepFear(character.deep_fear || '')
  setFormGrowthArc(character.growth_arc || '')
  setDialogOpen(true)
}

const resetForm = () =>
{
  setFormName('')
  setFormRole('配角')
  setFormPersonality('')
  setFormMotivation('')
  setFormCatchphrase('')
  setFormBackstory('')
  setFormAppearance('')
  setFormHabitAction('')
  setFormDeepFear('')
  setFormGrowthArc('')
}
```

- [ ] **Step 3: 实现提交逻辑**

```typescript
const handleSubmit = async () =>
{
  if (!formName.trim())
  {
    toast.error('请输入人物姓名')
    return
  }
  
  setSubmitting(true)
  try
  {
    if (editingCharacter)
    {
      // 更新人物
      const data: CharacterUpdate = {}
      if (formName !== editingCharacter.name) data.name = formName
      if (formRole !== editingCharacter.role) data.role = formRole
      data.personality = formPersonality
      data.core_motivation = formMotivation
      data.catchphrase = formCatchphrase
      data.backstory = formBackstory
      data.appearance = formAppearance
      data.habit_action = formHabitAction
      data.deep_fear = formDeepFear
      data.growth_arc = formGrowthArc
      
      const updated = await characterApi.update(projectId, editingCharacter.id, data)
      setCharacters(characters.map(c => c.id === updated.id ? updated : c))
      toast.success('人物已更新')
    }
    else
    {
      // 创建人物
      const data: CharacterCreate = {
        name: formName,
        role: formRole,
        personality: formPersonality,
        core_motivation: formMotivation,
        catchphrase: formCatchphrase,
        backstory: formBackstory,
        appearance: formAppearance,
        habit_action: formHabitAction,
        deep_fear: formDeepFear,
        growth_arc: formGrowthArc,
      }
      
      const created = await characterApi.create(projectId, data)
      setCharacters([...characters, created])
      toast.success('人物已创建')
    }
    
    setDialogOpen(false)
  }
  catch (err)
  {
    console.error('Failed to save character:', err)
    toast.error('保存失败')
  }
  finally
  {
    setSubmitting(false)
  }
}
```

- [ ] **Step 4: 添加 Dialog 组件**

```tsx
<Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
  <DialogContent className="max-w-lg max-h-[80vh] overflow-auto">
    <DialogHeader>
      <DialogTitle>{editingCharacter ? '编辑人物' : '新增人物'}</DialogTitle>
    </DialogHeader>
    
    <div className="space-y-4 py-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="char-name">姓名 <span className="text-red-500">*</span></Label>
          <Input
            id="char-name"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            placeholder="人物姓名"
          />
        </div>
        <div>
          <Label htmlFor="char-role">角色定位</Label>
          <Select value={formRole} onValueChange={setFormRole}>
            <SelectTrigger id="char-role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="主角">主角</SelectItem>
              <SelectItem value="核心反派">核心反派</SelectItem>
              <SelectItem value="重要配角">重要配角</SelectItem>
              <SelectItem value="配角">配角</SelectItem>
              <SelectItem value="次要">次要</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      
      <div>
        <Label>性格特点</Label>
        <Textarea
          value={formPersonality}
          onChange={(e) => setFormPersonality(e.target.value)}
          placeholder="描述人物性格特点"
          rows={2}
        />
      </div>
      
      <div>
        <Label>核心动机</Label>
        <Input
          value={formMotivation}
          onChange={(e) => setFormMotivation(e.target.value)}
          placeholder="人物的核心驱动力"
        />
      </div>
      
      <div>
        <Label>口头禅</Label>
        <Input
          value={formCatchphrase}
          onChange={(e) => setFormCatchphrase(e.target.value)}
          placeholder="人物的口头禅或标志性语言"
        />
      </div>
      
      <div>
        <Label>习惯动作</Label>
        <Input
          value={formHabitAction}
          onChange={(e) => setFormHabitAction(e.target.value)}
          placeholder="人物的习惯动作"
        />
      </div>
      
      <div>
        <Label>外貌描写</Label>
        <Textarea
          value={formAppearance}
          onChange={(e) => setFormAppearance(e.target.value)}
          placeholder="描述人物外貌特征"
          rows={2}
        />
      </div>
      
      <div>
        <Label>背景故事</Label>
        <Textarea
          value={formBackstory}
          onChange={(e) => setFormBackstory(e.target.value)}
          placeholder="人物的身世和经历"
          rows={3}
        />
      </div>
      
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>深层恐惧</Label>
          <Input
            value={formDeepFear}
            onChange={(e) => setFormDeepFear(e.target.value)}
            placeholder="人物内心深处的恐惧"
          />
        </div>
        <div>
          <Label>成长弧线</Label>
          <Input
            value={formGrowthArc}
            onChange={(e) => setFormGrowthArc(e.target.value)}
            placeholder="人物的成长轨迹"
          />
        </div>
      </div>
    </div>
    
    <DialogFooter>
      <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
      <Button onClick={handleSubmit} disabled={submitting}>
        {submitting ? '保存中...' : '保存'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

- [ ] **Step 5: 更新新增和编辑按钮的 onClick**

```typescript
// 新增按钮
<Button size="sm" onClick={openCreateDialog}>
  <Plus className="h-4 w-4 mr-2" />
  新增人物
</Button>

// 卡片中的新增按钮（虚线卡片）
onClick={openCreateDialog}

// 编辑按钮
<Button variant="ghost" size="sm" onClick={() => openEditDialog(character)}>
  <Edit className="h-4 w-4" />
</Button>
```

- [ ] **Step 6: 提交变更**

```bash
git add frontend/src/components/workbench/planning/CharacterPanel.tsx
git commit -m "feat(workbench): add character create and edit dialog with API"
```

---

## Task 3: RelationPanel 关系新增/编辑功能

**Files:**
- Modify: `frontend/src/components/workbench/planning/RelationPanel.tsx`

### 当前状态分析

- 组件已导入 `relationApi` 和 `RelationWithCharacters` 类型
- 列表和删除功能已实现
- 新增按钮调用 `toast.info('新增关系功能开发中')`
- 编辑按钮调用 `toast.info('编辑功能开发中')`

### 实现步骤

- [ ] **Step 1: 导入 Dialog 组件和 Character API**

```typescript
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { relationApi, characterApi } from '@/lib/characterApi'
import type { RelationWithCharacters, Character } from '@/types/character'
```

- [ ] **Step 2: 添加 Dialog 状态和表单状态**

```typescript
const [dialogOpen, setDialogOpen] = useState(false)
const [editingRelation, setEditingRelation] = useState<RelationWithCharacters | null>(null)
const [characters, setCharacterList] = useState<Character[]>([])
// 表单状态
const [formCharAId, setFormCharAId] = useState<number | string>('')
const [formCharBId, setFormCharBId] = useState<number | string>('')
const [formRelationType, setFormRelationType] = useState('陌生')
const [formStatus, setFormStatus] = useState('')
const [formTrustLevel, setFormTrustLevel] = useState(50)
const [submitting, setSubmitting] = useState(false)
```

- [ ] **Step 3: 加载人物列表（打开弹窗时）**

```typescript
const openCreateDialog = async () =>
{
  setEditingRelation(null)
  resetForm()
  // 加载人物列表
  try
  {
    const data = await characterApi.list(projectId)
    setCharacterList(data.characters)
  }
  catch (err)
  {
    console.error('Failed to load characters:', err)
    toast.error('加载人物列表失败')
  }
  setDialogOpen(true)
}

const openEditDialog = (relation: RelationWithCharacters) =>
{
  setEditingRelation(relation)
  setFormCharAId(relation.character_a_id)
  setFormCharBId(relation.character_b_id)
  setFormRelationType(relation.relation_type)
  setFormStatus(relation.current_status || '')
  setFormTrustLevel(relation.trust_level)
  // 加载人物列表
  characterApi.list(projectId).then(data => setCharacterList(data.characters))
  setDialogOpen(true)
}

const resetForm = () =>
{
  setFormCharAId('')
  setFormCharBId('')
  setFormRelationType('陌生')
  setFormStatus('')
  setFormTrustLevel(50)
}
```

- [ ] **Step 4: 实现提交逻辑**

```typescript
const handleSubmit = async () =>
{
  if (!formCharAId || !formCharBId)
  {
    toast.error('请选择两个人物')
    return
  }
  if (typeof formCharAId === 'string' || typeof formCharBId === 'string')
  {
    toast.error('请选择有效的人物')
    return
  }
  if (formCharAId === formCharBId)
  {
    toast.error('不能选择同一个人物')
    return
  }
  
  setSubmitting(true)
  try
  {
    if (editingRelation)
    {
      // 更新关系
      const updated = await relationApi.update(
        projectId,
        editingRelation.id,
        {
          character_a_id: formCharAId,
          character_b_id: formCharBId,
          relation_type: formRelationType,
          current_status: formStatus,
          trust_level: formTrustLevel,
        }
      )
      // 重新加载列表以获取完整数据
      const data = await relationApi.list(projectId)
      setRelations(data.relations)
      toast.success('关系已更新')
    }
    else
    {
      // 创建关系
      await relationApi.create(projectId, {
        character_a_id: formCharAId,
        character_b_id: formCharBId,
        relation_type: formRelationType,
        current_status: formStatus,
        trust_level: formTrustLevel,
      })
      // 重新加载列表
      const data = await relationApi.list(projectId)
      setRelations(data.relations)
      toast.success('关系已创建')
    }
    
    setDialogOpen(false)
  }
  catch (err)
  {
    console.error('Failed to save relation:', err)
    toast.error('保存失败')
  }
  finally
  {
    setSubmitting(false)
  }
}
```

- [ ] **Step 5: 添加 Dialog 组件**

```tsx
<Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
  <DialogContent className="max-w-md">
    <DialogHeader>
      <DialogTitle>{editingRelation ? '编辑关系' : '新增关系'}</DialogTitle>
    </DialogHeader>
    
    <div className="space-y-4 py-4">
      <div>
        <Label htmlFor="char-a">人物A <span className="text-red-500">*</span></Label>
        <Select
          value={String(formCharAId)}
          onValueChange={(v) => setFormCharAId(parseInt(v))}
        >
          <SelectTrigger id="char-a">
            <SelectValue placeholder="选择人物" />
          </SelectTrigger>
          <SelectContent>
            {characters.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div>
        <Label htmlFor="relation-type">关系类型</Label>
        <Select value={formRelationType} onValueChange={setFormRelationType}>
          <SelectTrigger id="relation-type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="信任">信任</SelectItem>
            <SelectItem value="敌对">敌对</SelectItem>
            <SelectItem value="感情">感情</SelectItem>
            <SelectItem value="合作">合作</SelectItem>
            <SelectItem value="利用">利用</SelectItem>
            <SelectItem value="陌生">陌生</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div>
        <Label htmlFor="char-b">人物B <span className="text-red-500">*</span></Label>
        <Select
          value={String(formCharBId)}
          onValueChange={(v) => setFormCharBId(parseInt(v))}
        >
          <SelectTrigger id="char-b">
            <SelectValue placeholder="选择人物" />
          </SelectTrigger>
          <SelectContent>
            {characters.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div>
        <Label>当前状态</Label>
        <Input
          value={formStatus}
          onChange={(e) => setFormStatus(e.target.value)}
          placeholder="描述当前关系状态"
        />
      </div>
      
      <div>
        <Label>信任度 ({formTrustLevel})</Label>
        <input
          type="range"
          min="0"
          max="100"
          value={formTrustLevel}
          onChange={(e) => setFormTrustLevel(parseInt(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>0</span>
          <span>100</span>
        </div>
      </div>
    </div>
    
    <DialogFooter>
      <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
      <Button onClick={handleSubmit} disabled={submitting}>
        {submitting ? '保存中...' : '保存'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

- [ ] **Step 6: 更新新增和编辑按钮的 onClick**

```typescript
// 新增按钮
<Button size="sm" onClick={openCreateDialog}>
  <Plus className="h-4 w-4 mr-2" />
  新增关系
</Button>

// 编辑按钮
<Button variant="ghost" size="sm" onClick={() => openEditDialog(relation)}>
  <Edit className="h-4 w-4" />
</Button>
```

- [ ] **Step 7: 提交变更**

```bash
git add frontend/src/components/workbench/planning/RelationPanel.tsx
git commit -m "feat(workbench): add relation create and edit dialog with API"
```

---

## 测试验证

### 手动测试清单

- [ ] 灵感页面 - 保存灵感数据到服务器
- [ ] 人物管理 - 新增人物（填写表单 → 保存 → 卡片出现）
- [ ] 人物管理 - 编辑人物（点击编辑 → 修改 → 保存）
- [ ] 人物管理 - 删除人物（确认删除）
- [ ] 关系管理 - 新增关系（选择人物A/B → 保存）
- [ ] 关系管理 - 编辑关系（点击编辑 → 修改 → 保存）
- [ ] 关系管理 - 删除关系（确认删除）

---

## 注意事项

1. **不修改 UI 布局** - 仅添加事件绑定、Dialog 和 API 调用
2. **Dialog 复用 shadcn/ui** - 项目已有 shadcn/ui 组件
3. **API 客户端已存在** - characterApi/relationApi 在 characterApi.ts 中定义
4. **遵循项目代码风格** - 中文注释、camelCase 命名、Allman 风格大括号