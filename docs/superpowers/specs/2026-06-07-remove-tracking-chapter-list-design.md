# 去掉追踪标签页最左栏（ChapterListPanel）

## Summary

追踪标签页当前为三栏布局：章节列表（ChapterListPanel, 180px）| 分区导航（40px）| 内容区。最左栏 ChapterListPanel 是功能孤岛——数据对不上，`selectedChapterNumber` 状态无其他组件消费，点击章节不会驱动追踪内容筛选或跳转。去掉后追踪标签页变为两栏，内容区更宽。

## Key Changes

1. **`ProjectWorkbench.tsx`** — 将 `showChapterList` 从 `activeTab === 'tracking'` 改为 `false`，使追踪标签页不再显示章节列表栏
2. **`WorkbenchLayout.tsx`** — 将 `showChapterList` 默认值从 `true` 改为 `false`，确保无调用方传参时也不显示该栏
3. **保留** `ChapterListPanel.tsx` 文件和 `showChapterList` prop 不删除，以备写作标签页等未来使用

## Test Plan

- 切换到追踪标签页，确认最左栏消失，分区导航和内容区正常显示
- 切换到其他标签页（写作/知识库/结构），确认布局不受影响
- 浏览器窗口缩放时确认追踪标签页内容区自适应正常

## Assumptions

- ChapterListPanel 当前无有效数据联动，去掉不影响任何功能
- 未来如果写作标签页需要章节列表，可通过重新设置 `showChapterList` 恢复
- `selectedChapterNumber` 状态保留在 store 中，不删除，避免破坏其他可能的消费者
