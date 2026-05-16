# 导航栏创作平台快捷链接设计

## 需求

在顶部导航栏加入热门小说平台的作家网网址，方便用户一键跳转到创作平台。

## 方案

前端硬编码下拉菜单，无需后端改动。

## 平台列表

| 平台 | URL | 图标 |
|------|-----|------|
| 番茄小说网 | https://fanqienovel.com/ | 🍅 |
| 七猫中文网 | https://zuozhe.qimao.com/ | 🐱 |
| 起点中文网 | https://write.qq.com/ | 📕 |
| 晋江文学城 | https://www.jjwxc.net/ | 💜 |
| 飞卢小说 | https://www.faloo.com/ | 📘 |

## UI 设计

- 在 `Header.tsx` 的 Logo 和用户区域之间添加"创作平台"按钮
- 使用 shadcn/ui `DropdownMenu` 组件
- 触发按钮：`Button variant="ghost"` + `ExternalLink` 图标 + "创作平台"文字
- 下拉菜单项：emoji + 平台名 + `ExternalLink` 图标（表示外链）
- 点击菜单项 `window.open(url, '_blank')` 新标签页打开
- 菜单项之间用 `DropdownMenuSeparator` 分隔

## 改动文件

- `frontend/src/components/layout/Header.tsx` — 添加平台常量 + DropdownMenu 组件

## 不改动的文件

- 后端无改动
- 无新增文件
- 无数据库迁移
