# 灵感采集选项优化设计

> 创建日期: 2026-04-27
> 版本: v0.7.x
> 功能: 新增灵感选项，优化男女频分类结构

---

## 概述

扩展现有灵感采集选项，新增年代、流派等字段，并将主角设定拆分为男主人设和女主人设。同时重构选项配置结构，为男频和女频建立独立的选项配置，便于后续差异化扩展。

---

## 变更摘要

### 新增字段

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `era` | 必填 | ✅ | 年代设定 |
| `genre` | 选填 | ❌ | 流派类型 |
| `maleLead` | 条件必填 | 男频必填 | 男主人设 |
| `femaleLead` | 条件必填 | 女频必填 | 女主人设 |

### 修改字段

| 字段 | 变更 |
|-----|------|
| `worldSetting` | 扩展选项列表 |
| `stylePreference` | 保持不变（风格） |
| `protagonist` | 重命名为 `maleLead`/`femaleLead` |

---

## 详细选项定义

### 年代设定 (era) - 新增必填

```typescript
era: [
  { value: 'ancient', label: '古代' },
  { value: 'modern', label: '现代' },
  { value: 'future', label: '未来' },
  { value: 'fictional', label: '架空' },
]
```

### 流派设定 (genre) - 新增选填

```typescript
genre: [
  { value: 'brain_hole', label: '脑洞文' },
  { value: 'trash_flow', label: '废柴流' },
  { value: 'mortal_flow', label: '凡人流' },
  { value: 'prehistoric', label: '洪荒流' },
  { value: 'infinite', label: '无限流' },
]
```

### 世界观设定 (worldSetting) - 扩展选项

```typescript
worldSettings: [
  // 原有选项
  { value: 'cultivation', label: '修仙体系' },
  { value: 'magic', label: '魔法世界' },
  { value: 'cyberpunk', label: '赛博朋克' },
  { value: 'modern', label: '现代社会' },
  { value: 'ancient', label: '古代王朝' },
  // 新增选项
  { value: 'xianxia', label: '仙侠世界' },
  { value: 'western_fantasy', label: '西幻大陆' },
  { value: 'apocalypse', label: '末世废土' },
  { value: 'urban_ability', label: '都市异能' },
  { value: 'palace', label: '宫廷宅斗' },
  { value: 'wuxia', label: '武侠江湖' },
  { value: 'interstellar', label: '星际帝国' },
  { value: 'game_world', label: '游戏世界' },
  { value: 'supernatural', label: '灵异悬疑' },
  // 自定义
  { value: 'custom', label: '自定义' },
]
```

### 男主人设 (maleLead) - 男频必填

```typescript
maleLead: [
  { value: 'genius', label: '少年天才' },
  { value: 'transmigrator', label: '穿越者' },
  { value: 'reborn', label: '重生者' },
  { value: 'underdog', label: '草根逆袭' },
  { value: 'ordinary', label: '普通人' },
  { value: 'custom', label: '自定义' },
]
```

### 女主人设 (femaleLead) - 女频必填

```typescript
femaleLead: [
  { value: 'rich_beauty', label: '白富美' },
  { value: 'strong_woman', label: '女强人' },
  { value: 'sweet_naive', label: '傻白甜' },
  { value: 'cinderella', label: '灰姑娘' },
  { value: 'transmigrator', label: '穿越女' },
  { value: 'reborn', label: '重生女' },
  { value: 'custom', label: '自定义' },
]
```

---

## 代码结构设计

### 选项配置重构

将原有的扁平配置重构为分层结构，区分男频和女频：

```typescript
// frontend/src/lib/inspiration.ts

// 通用选项（男女频共用）
const COMMON_OPTIONS = {
  novelTypes: [...],
  coreThemes: [...],
  era: [...],
  genre: [...],
  worldSettings: [...],
  narrative: [...],
  wordsPerChapter: [...],
  goldFinger: [...],
  stylePreferences: [...],
}

// 男频专属选项
const MALE_OPTIONS = {
  maleLead: [...],
  genre: [...],  // 男频流派
}

// 女频专属选项
const FEMALE_OPTIONS = {
  femaleLead: [...],
  genre: [...],  // 女频流派（暂时与男频相同，预留扩展）
}

// 统一导出，根据 targetReader 动态获取
export function getInspirationOptions(targetReader: 'male' | 'female') {
  return {
    ...COMMON_OPTIONS,
    ...(targetReader === 'male' ? MALE_OPTIONS : FEMALE_OPTIONS),
  }
}
```

### 数据结构更新

```typescript
// InspirationData 接口更新
export interface InspirationData {
  // 必填项
  targetReader: string           // 男频/女频
  novelType: string              // 小说类型
  era: string                    // 年代（新增）
  targetWords: number
  wordsPerChapter: string
  coreTheme: string
  maleLead?: string              // 男主人设（新增）
  customMaleLead?: string
  femaleLead?: string            // 女主人设（新增）
  customFemaleLead?: string

  // 选填项
  narrative?: string
  worldSetting?: string
  customWorldSetting?: string
  genre?: string                 // 流派（新增）
  goldFinger?: string
  customGoldFinger?: string
  stylePreference?: string
}
```

---

## UI 布局调整

### 表单结构

```
┌─────────────────────────────────────────────────────┐
│  目标读者 *  [男频] [女频]                           │
├─────────────────────────────────────────────────────┤
│  基本设定（必填）                                    │
│  ├─ 小说类型 *                                      │
│  ├─ 年代 *  [古代] [现代] [未来] [架空]             │
│  ├─ 目标字数 *                                      │
│  └─ 每章字数 *                                      │
├─────────────────────────────────────────────────────┤
│  主角设定（必填）                                    │
│  ├─ 男频：男主人设 *                                │
│  └─ 女频：女主人设 *                                │
├─────────────────────────────────────────────────────┤
│  进阶设定（选填）                                    │
│  ├─ 核心主题 *                                      │
│  ├─ 世界观设定                                      │
│  ├─ 流派                                           │
│  ├─ 金手指设定                                      │
│  └─ 风格偏好                                        │
└─────────────────────────────────────────────────────┘
```

### 交互逻辑

1. 选择「男频」后显示「男主人设」选项
2. 选择「女频」后显示「女主人设」选项
3. 流派选项根据目标读者动态加载（预留扩展）
4. 年代为必填项，放置在基本设定区域

---

## Markdown 模板更新

```markdown
# 小说创作灵感

## 基本信息

- **目标读者**：男频/女频
- **小说类型**：{novelType}
- **年代设定**：{era}
- **目标字数**：{targetWords}字
- **每章字数**：{wordsPerChapter}

## 主角设定

- **男主**：{maleLead}（男频显示）
- **女主**：{femaleLead}（女频显示）

## 核心设定

- **核心主题**：{coreTheme}
- **世界观**：{worldSetting}
- **流派**：{genre}
- **金手指**：{goldFinger}

## 风格

- **风格偏好**：{stylePreference}

## 补充灵感

> 在下方添加更多灵感细节...

-
```

---

## 后端适配

### Schema 更新

```python
# backend/app/schemas/outline.py

class InspirationData(BaseModel):
    # 必填项
    target_reader: str
    novel_type: str
    era: str                    # 新增
    target_words: int
    words_per_chapter: str
    core_theme: str
    male_lead: Optional[str]    # 新增
    custom_male_lead: Optional[str]
    female_lead: Optional[str]  # 新增
    custom_female_lead: Optional[str]

    # 选填项
    narrative: Optional[str]
    world_setting: Optional[str]
    custom_world_setting: Optional[str]
    genre: Optional[str]        # 新增
    gold_finger: Optional[str]
    custom_gold_finger: Optional[str]
    style_preference: Optional[str]
```

### 大纲生成节点适配

在 `backend/app/agents/nodes/outline_generation.py` 中更新提示词模板，包含新增字段。

---

## 实现范围

### 本次实现

- [ ] 前端选项配置重构（男频/女频分离）
- [ ] 新增「年代」字段及 UI
- [ ] 新增「流派」字段及 UI
- [ ] 主角设定拆分为男主人设/女主人设
- [ ] 世界观选项扩展
- [ ] InspirationData 类型更新
- [ ] Markdown 模板更新
- [ ] 后端 Schema 更新
- [ ] 大纲生成节点适配

### 暂不实现

- 男频/女频流派选项差异化
- 灵感模板保存/加载
- 灵感选项动态扩展

---

## 验收标准

- [ ] 年代字段正确显示 4 个选项
- [ ] 流派字段正确显示 5 个选项
- [ ] 选择男频后显示男主人设，选择女频后显示女主人设
- [ ] 世界观选项扩展到 15 个
- [ ] 表单验证正确处理新增必填项
- [ ] Markdown 模板包含新增字段
- [ ] 大纲生成正确使用新增灵感选项
- [ ] 现有功能不受影响
