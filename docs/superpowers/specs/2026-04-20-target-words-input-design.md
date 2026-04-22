# 目标字数输入框优化设计

## Overview

将目标字数从下拉框选择改为数字输入框，删除小说篇幅选项，添加字数与篇幅对应关系的提示。

## Changes

### 1. 目标字数变更

| 项目 | 之前 | 之后 |
|------|------|------|
| 控件类型 | 下拉框选择 | 数字输入框 |
| 单位 | 万字 | 字 |
| 示例值 | "100万字" | "100000字" |
| 提示 | 无 | ? 图标 + 悬浮 tips |

### 2. 删除小说篇幅选项

- 删除 `novelLength` 字段
- 删除 `customChapterCount` 字段
- 删除相关 UI 组件

### 3. 新增 Tips 内容

鼠标悬浮 ? 图标显示：

```
📖 字数与篇幅对应关系：
• 超短篇：1万-5万字
• 短篇：5万-20万字
• 中篇：20万-50万字
• 长篇：50万-100万字
• 超长篇：100万字以上
```

---

## Data Schema

### InspirationData 变更

```typescript
// 之前
interface InspirationData {
  novelLength: string           // 'short' | 'medium' | 'long' | 'extra_long' | 'custom'
  customChapterCount?: number
  targetWords: string           // '50w' | '100w' | '200w' | '300w' | '500w' | 'custom'
  customTargetWords?: number    // 万字为单位
  // ...其他字段
}

// 之后
interface InspirationData {
  targetWords: number           // 直接存储字数（如 100000）
  // novelLength 和 customChapterCount 已删除
  // ...其他字段
}
```

### CollectedInfo 变更

同步更新 `frontend/src/types/index.ts` 中的 `CollectedInfo` 接口。

---

## Files Changed

| 文件 | 操作 |
|------|------|
| `frontend/src/types/index.ts` | 修改 - 删除 novelLength/customChapterCount，targetWords 改为 number |
| `frontend/src/lib/inspiration.ts` | 修改 - 删除 novelLength 选项，targetWords 类型变更，更新模板生成 |
| `frontend/src/components/project/InspirationForm.tsx` | 修改 - 删除篇幅下拉框，目标字数改为输入框+tips |
| `frontend/src/components/project/InspirationDisplay.tsx` | 修改 - 删除篇幅显示，更新目标字数显示 |
| `frontend/src/components/project/InspirationEditor.tsx` | 修改 - 同上 |
| `frontend/src/pages/ProjectDetail.tsx` | 修改 - 删除 valueLabels 中的 novelLength |

---

## UI Design

### 目标字数输入框

```
┌─────────────────────────────────────────┐
│ 目标字数 (?)  *                          │
│ ┌─────────────────────────────────────┐ │
│ │ [输入框: 100000] 字                 │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

- 输入框类型：`type="number"`
- 默认值：无（用户必须输入）
- 验证：必填，最小值 10000（1万字）

### Tips 组件

使用 shadcn/ui 的 Tooltip 组件，或自定义 CSS tooltip：

```tsx
<div className="tooltip-trigger relative">
  <svg>?</svg>
  <div className="tooltip">
    <div>📖 字数与篇幅对应关系：</div>
    <ul>
      <li>• 超短篇：1万-5万字</li>
      <li>• 短篇：5万-20万字</li>
      <li>• 中篇：20万-50万字</li>
      <li>• 长篇：50万-100万字</li>
      <li>• 超长篇：100万字以上</li>
    </ul>
  </div>
</div>
```

---

## Success Criteria

1. ✅ 目标字数使用数字输入框，单位为"字"
2. ✅ 删除小说篇幅选项
3. ✅ ? 图标悬浮显示字数与篇幅对应关系
4. ✅ 所有相关文件正确更新
5. ✅ 灵感模板正确显示目标字数
6. ✅ 历史视图正确显示目标字数
