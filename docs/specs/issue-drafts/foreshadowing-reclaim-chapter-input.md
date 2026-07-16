# 伏笔回收对话框增加"回收章节"输入

**Labels**: `enhancement`, `frontend`, `ux`

## 背景

[TrackingTab.tsx:184-194](../../frontend/src/components/workbench/tracking/TrackingTab.tsx) 中，伏笔状态从 `pending_reclaim` 流转到 `reclaimed` 时，会把 `selectedChapterNumber`（用户在左侧章节列表选中的章节）直接作为 `resolved_chapter` 写入：

```typescript
if (newStatus === 'reclaimed') {
  if (selectedChapterNumber == null) {
    toast.error('请先在左侧章节列表中选中当前所在章节')
    return
  }
  payload.resolved_chapter = selectedChapterNumber
}
```

## 问题

`selectedChapterNumber` 的语义是"用户当前查看/编辑的章节"，而 `resolved_chapter` 的语义是"这个伏笔在哪一章被回收"。**两者通常一致但不必然**：

- 用户站在第 12 章想标记某伏笔在第 8 章已回收
- 用户在追踪 tab 浏览伏笔列表时，可能并未选中任何章节（`selectedChapterNumber == null`），目前会被 toast 阻止
- 批量回收多条伏笔时，只能逐条切换到对应章节再点

这是 commit 5a9356c 之前就存在的限制——但之前 `currentChapterNum` 永远是初始值 1（死代码），所以这条路径**事实上不可用**；commit 之后才"第一次真正可用"，问题随之显现。

## 方案

在伏笔回收按钮触发后弹一个轻量对话框：

```
回收这条伏笔
└─ 回收章节号  [ 8 ]    ← 默认填 selectedChapterNumber，可改
   备注（可选） [        ]
   [取消] [确认回收]
```

或更轻量：在伏笔卡片上直接 inline 一个数字 input + 确认按钮。

需要一并考虑：
- `resolved_chapter` 是否允许填写未来章节（语义上应该禁止：只能 ≤ 已写章节数）
- 校验范围：必须 ≥ `planted_chapter`
- 后端 `knowledgeApi.updateForeshadowing` 是否已支持 `resolved_chapter` 显式覆盖（应该支持，但要确认 schema）

## 验收

- 在追踪 tab 不选中任何章节也能完成伏笔回收
- 回收章节号可与 `selectedChapterNumber` 不一致并被正确持久化
- 校验：`resolved_chapter >= planted_chapter`、`<= 当前已写章节数`
- 现有的"已逾期"高亮判定仍正常工作

## 关联

- 上游 commit: 5a9356c (fix(workflow): pass current_chapter_number to agent...)
- 触发审查的位置: TrackingTab.tsx:184-194
