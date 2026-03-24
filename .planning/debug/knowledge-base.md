# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## targetwordcount-required-missing — Form.Item missing for form field causing validation failure
- **Date:** 2026-03-24T10:15:00Z
- **Error patterns:** targetWordCount, required property, body must have, Form.Item, validateFields, 表单提交
- **Root cause:** 前端表单中 targetWordCount 字段没有对应的 Form.Item 组件，导致 validateFields() 返回的对象中不包含该字段，后端因缺少必填字段而报错
- **Fix:** 在步骤1表单中添加一个隐藏的 Form.Item 来绑定 targetWordCount 字段，确保其值被正确提交到后端
- **Files changed:** /opt/1panel/www/sites/inkflowx/frontend/src/pages/home/components/ProjectCreateModal.tsx
---