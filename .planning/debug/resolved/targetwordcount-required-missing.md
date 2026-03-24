---
status: resolved
trigger: "用户端创建新项目失败，提示'body must have required property 'targetWordCount''"
created: 2026-03-24T10:00:00Z
updated: 2026-03-24T10:15:00Z
---

## Current Focus
hypothesis: targetWordCount 字段没有对应的 Form.Item，导致表单提交时该字段未被包含
test: 添加隐藏的 Form.Item 或在提交时手动设置该字段
expecting: 修复后创建项目成功
next_action: 应用修复方案

## Symptoms
expected: 填写表单后成功创建项目
actual: 创建失败，报错 "body must have required property 'targetWordCount'"
errors: body must have required property 'targetWordCount'
reproduction: 用户端创建新项目时触发
started: 未知，可能是最近出现的问题

## Eliminated
<!-- APPEND only -->

## Evidence
- timestamp: 2026-03-24T10:05:00Z
  checked: 后端路由文件 backend/src/routes/projects.ts
  found: 第 65 行定义了 required: ['name', 'type', 'targetWordCount']，targetWordCount 为必填字段
  implication: 后端要求 targetWordCount 必须存在

- timestamp: 2026-03-24T10:06:00Z
  checked: 前端表单组件 ProjectCreateModal.tsx
  found: targetWordCount 在接口中定义(第30行)、在默认值中设置(第83行)、通过 setFieldValue 更新(第391行)，但没有对应的 Form.Item
  implication: 缺少 Form.Item 导致字段值可能不被 validateFields() 获取

- timestamp: 2026-03-24T10:07:00Z
  checked: 搜索 name="targetWordCount" 的 Form.Item
  found: 无匹配结果
  implication: 确认 targetWordCount 字段没有绑定的表单项

## Resolution
root_cause: 前端表单中 targetWordCount 字段没有对应的 Form.Item 组件，导致 validateFields() 返回的对象中不包含该字段，后端因缺少必填字段而报错
fix: 在步骤1表单中添加一个隐藏的 Form.Item 来绑定 targetWordCount 字段，确保其值被正确提交到后端
verification: 前端构建成功，无编译错误
files_changed: [/opt/1panel/www/sites/inkflowx/frontend/src/pages/home/components/ProjectCreateModal.tsx]