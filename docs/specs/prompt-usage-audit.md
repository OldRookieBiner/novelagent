# Prompt 引用全景图

**审计时间**：2026-06-23
**目的**：盘点 `backend/app/agents/prompts.py` 中所有 prompt 模板的实际使用情况，识别"孤儿"与"重复"，为后续接通工作提供决策依据。

---

## 总览

- 模板总数：**28** 个（不含 `AGENT_SYSTEM_PROMPT`）
- 已接通：**6** 个（孵化阶段全部）
- 孤儿（零外部引用）：**22** 个
- 另有 **4 个内置 prompt** 散落在 `chapter_quality.py`，与 `prompts.py` 中的同名模板形成双轨制

---

## 分类清单

### ✅ 已接通（6 个）—— 全部用于项目初始化

| 模板 | 外部引用数 | 调用方 | 用途 |
|------|-----------|--------|------|
| STORY_SEED_PROMPT | 2 | `initialization.py:generate_story_seed` | 概念→故事种子 |
| OUTLINE_GENERATION_PROMPT | 2 | `initialization.py` | 故事种子→大纲 |
| WORLD_SETTING_PROMPT | 3 | `initialization.py:generate_world_setting` | 大纲→世界观 |
| CHARACTER_GENERATION_PROMPT | 3 | `initialization.py` | 大纲+世界观→角色 |
| RELATION_GENERATION_PROMPT | 2 | `initialization.py` | 角色→人物关系 |
| STYLE_SETUP_PROMPT | 2 | `initialization.py` | 大纲+世界观→风格约束 |

**结论**：孵化阶段（INCUBATION）的初始化链路是完整接通的。这也是当前 AI 生成质量最稳定的一段。

---

### ❌ 孤儿 prompt（22 个）—— 零外部引用

按"潜在影响"分组：

#### 🔴 P0 影响章节正文质量（4 个）

这组是**对生成质量影响最大**的孤儿，章节正文实际上靠 `AGENT_SYSTEM_PROMPT` 的宏观指引产出，没有走这些精细模板。

| 模板 | 设计用途 | 关键约束（未被强制） |
|------|---------|---------------------|
| **CHAPTER_WRITING_PROMPT** | 写章节正文 | 上章收束承接、POV 锁定、scene_directions 严格执行、字数 ±10%、信息层级 hiding/teasing/revealing、章末钩子 |
| **CHAPTER_PLANNING_PROMPT** | 生成章节点（场景规划） | 场景导演字段（POV/镜头/信息层级/情绪节拍/感官通道/切入切出） |
| CHARACTER_KNOWLEDGE_BOUNDARY_PROMPT | 角色知识边界审查 | 角色 OOC 防护核心模板 |
| POST_WRITE_CHECK_PROMPT | 写完后一致性自检 | 4 维度（角色/伏笔/问题链/风格）即时反馈 |

#### 🟡 P1 影响结构设计与审查（11 个）

这组主要影响结构设计阶段（STRUCTURE）和事后审查质量。当前结构阶段的产出依赖 Agent 自由发挥，审查则被规则脚本（rhythm_analysis / foreshadowing_check / consistency_scan）覆盖了一部分。

| 模板 | 设计用途 |
|------|---------|
| QUESTION_CHAIN_PROMPT | 问题链逆向规划 |
| PLOT_BLOCKS_PROMPT | 情节块展开 |
| SUBPLOT_NETWORK_PROMPT | 支线网络 |
| RHYTHM_CURVE_PROMPT | 预期节奏曲线 |
| FORESHADOWING_PLAN_PROMPT | 伏笔-回收地图规划 |
| DEEP_REVIEW_PROMPT | 最近 5 章深度审查（旧版） |
| DEEP_REVIEW_ENHANCED_PROMPT | 6 维度深度审查（新版） |
| STRUCTURAL_REVIEW_PROMPT | 全书结构完整性检查 |
| CHARACTER_ARC_REVIEW_PROMPT | 全书角色弧 + 风格审查 |
| FINAL_POLISH_PROMPT | 最终润色 |
| INSPIRATION_DIALOGUE_PROMPT | 创意启发对话（已被 inspiration_service 用其他实现取代？需确认） |

#### 🟢 P2 卷管理相关（7 个）

跨卷功能链路，孤儿率 100%。若项目当前以单卷为主，可暂缓接通。

| 模板 | 设计用途 |
|------|---------|
| VOLUME_TRANSITION_PROMPT | 卷过渡摘要 |
| VOLUME_REVIEW_PROMPT | 单卷结构检查 |
| PER_VOLUME_STRUCTURAL_REVIEW_PROMPT | 单卷结构检查（卷内范围） |
| FULL_BOOK_STRUCTURAL_REVIEW_PROMPT | 全书结构检查（跨卷） |
| PER_VOLUME_CHARACTER_ARC_REVIEW_PROMPT | 单卷角色弧检查 |
| FULL_BOOK_CHARACTER_ARC_REVIEW_PROMPT | 全书角色弧检查（跨卷） |
| FINAL_POLISH_FULL_PROMPT | 跨卷最终润色 |

---

### ⚠️ 双轨制：另一份独立的 prompt 实现

`backend/app/agents/services/chapter_quality.py` 内部定义了 **4 个 prompt**，与 `prompts.py` 中的相关模板**功能重叠**但**没有共用**：

| chapter_quality.py 内置 | prompts.py 对应模板（孤儿） | 差异 |
|-------------------------|------------------------|------|
| `_REVIEW_SYSTEM_PROMPT` + `_REVIEW_USER_PROMPT` | DEEP_REVIEW_PROMPT / DEEP_REVIEW_ENHANCED_PROMPT | 内置版是 6 维度 JSON 评分（plot/character/writing/emotion/ai_flavor/outline_deviation）；prompts.py 版多了支线、POV、风格漂移检测 |
| `_REWRITE_SYSTEM_PROMPT` + `_REWRITE_USER_PROMPT` | FINAL_POLISH_PROMPT | 内置版按章重写；prompts.py 版是全书最终润色 |

**问题**：
1. 模板分裂在两个地方，修改时容易遗漏
2. `DEEP_REVIEW_ENHANCED_PROMPT` 设计更完整（含支线、POV、风格漂移），但实际审查走的是内置简版
3. 维护成本翻倍

---

## 接通方式参考

### 路径 A：把孤儿 prompt 改造为"真工具"

适合 `CHAPTER_WRITING_PROMPT` / `CHAPTER_PLANNING_PROMPT` 这种产出大块内容的模板。

```python
@tool
async def generate_chapter_content(chapter_number: int) -> dict:
    # 内部：读上下文 → 用 CHAPTER_WRITING_PROMPT 调 LLM → 落库
    ...
```

Agent 只决定"写第几章"，由工具内部强制所有铁规则。

### 路径 B：注入到 AGENT_SYSTEM_PROMPT 按阶段拼接

适合规则性约束（POV 锁定、字数控制、taboo_words）。

```python
# agent.py 拼接 system prompt 时
if phase == "writing":
    system_prompt += "\n\n## 写作铁规则\n" + extract_rules(CHAPTER_WRITING_PROMPT)
```

让主 LLM 在自由写作时也带着这些约束。

### 路径 C：合并双轨

把 `chapter_quality.py` 的内置 prompt 删掉，统一引用 `prompts.py`，避免维护分裂。

---

## 推荐优先级

| 优先级 | 动作 | 预期收益 |
|--------|------|---------|
| **P0** | 接通 CHAPTER_WRITING_PROMPT（路径 A 或 B） | 章节正文质量稳定性显著提升 |
| **P0** | 接通 CHAPTER_PLANNING_PROMPT 并把 scene_directions 入库 | 让"场景导演"设计真正生效 |
| **P1** | 合并双轨：chapter_quality.py 改用 prompts.py | 降低维护成本，统一升级路径 |
| **P1** | 接通 DEEP_REVIEW_ENHANCED_PROMPT（替换 chapter_quality 内置版） | 审查覆盖支线/POV/风格漂移 |
| **P1** | 接通 CHARACTER_KNOWLEDGE_BOUNDARY_PROMPT 到 POST_WRITE_CHECK 链 | 强化 OOC 防护 |
| **P2** | 结构设计阶段 prompt（QUESTION_CHAIN / PLOT_BLOCKS / RHYTHM_CURVE）接通 | 让结构设计有可复现质量基线 |
| **P3** | 卷管理 prompt 接通 | 视产品规划决定（是否主推跨卷长篇） |
| **🗑️** | 移除明确废弃的 prompt（如 DEEP_REVIEW_PROMPT 旧版，若 ENHANCED 已替代） | 减少噪音 |

---

## 备注

- `INSPIRATION_DIALOGUE_PROMPT` 是否真的废弃需要确认：`backend/app/api/inspiration.py` 和 `backend/app/services/inspiration_service.py` 是否走了另一份 prompt
- 若决定走"路径 A 接通 CHAPTER_WRITING_PROMPT"，需同步删除/标记 `generate_chapter_content` 的旧契约（让 Agent 不再传 content 字段，而是只传 chapter_number）
- 接通过程建议每个 prompt 配 1 个集成测试，断言关键约束生效（如 taboo_words 命中率、字数偏差、POV 一致性）
