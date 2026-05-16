# 上下文传递数据完整性与策略优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复上下文传递的根源数据完整性问题，补全 DB schema，实现混合上下文策略，统一 `_prompts` 注入。

**Architecture:** 从 DB schema 根源补起——给 `chapter_outlines` 表加列，全链路贯通（ORM → Schema → API 创建/更新/响应 → 前端类型），修正 `build_initial_state` 的 characters 字段映射和 evolution 数据加载，修正 `format_characters_info` 与 DB 字段对齐，补全 `_format_chapter_outline_str` 缺失字段；`ContextStrategy` 接口新增 `chapter_outlines` 参数供混合策略使用，review/rewrite 改用 `get_context_strategy`；`_prompts` 注入统一到 `build_initial_state` 并做降级保护。

**Tech Stack:** Python, SQLAlchemy, Alembic, LangGraph

---

### Task 1: DB Schema 补全 — `chapter_outlines` 表加列 + 全链路贯通

**Files:**
- Create: `backend/alembic/versions/<auto>_add_chapter_outline_fields.py`
- Modify: `backend/app/models/outline.py`
- Modify: `backend/app/schemas/chapter.py`
- Modify: `backend/app/api/chapters.py` (3 处 `ChapterOutlineResponse` + 1 处创建 + 1 处 progress + 1 处更新)
- Modify: `backend/app/utils/workflow_persistence.py`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 创建 Alembic 迁移**

Run: `docker exec novelagent-backend-1 alembic revision -m "add_chapter_outline_fields"`

- [ ] **Step 2: 编写迁移代码**

在新生成的迁移文件中写入：

```python
"""add chapter_outline fields: turning_point, hook, transition

Revision ID: <auto>
Revises: <auto>
Create Date: <auto>
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('chapter_outlines', sa.Column('turning_point', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('hook', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('transition', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('chapter_outlines', 'transition')
    op.drop_column('chapter_outlines', 'hook')
    op.drop_column('chapter_outlines', 'turning_point')
```

- [ ] **Step 3: 补全 ChapterOutline ORM 模型**

在 `backend/app/models/outline.py` 的 `ChapterOutline` 类中，`confirmed` 列之前添加：

```python
    turning_point = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    transition = Column(Text, nullable=True)
```

- [ ] **Step 4: 补全 Pydantic Schema**

修改 `backend/app/schemas/chapter.py`，在 `ChapterOutlineBase`、`ChapterOutlineUpdate`、`ChapterOutlineResponse` 中加入新字段：

```python
class ChapterOutlineBase(BaseModel):
    title: Optional[str] = None
    scene: Optional[str] = None
    characters: Optional[str] = None
    plot: Optional[str] = None
    conflict: Optional[str] = None
    turning_point: Optional[str] = None
    hook: Optional[str] = None
    transition: Optional[str] = None
    ending: Optional[str] = None
    target_words: Optional[int] = 3000


class ChapterOutlineUpdate(BaseModel):
    title: Optional[str] = None
    scene: Optional[str] = None
    characters: Optional[str] = None
    plot: Optional[str] = None
    conflict: Optional[str] = None
    turning_point: Optional[str] = None
    hook: Optional[str] = None
    transition: Optional[str] = None
    ending: Optional[str] = None
    target_words: Optional[int] = None


class ChapterOutlineResponse(ChapterOutlineBase):
    id: int
    project_id: int
    chapter_number: int
    confirmed: bool
    created_at: datetime
    has_content: bool = False

    class Config:
        from_attributes = True
```

- [ ] **Step 5: 补全前端类型定义**

修改 `frontend/src/types/index.ts` 的 `ChapterOutline` 和 `ChapterOutlineUpdate` 接口：

```typescript
export interface ChapterOutline {
  id: number;
  project_id: number;
  chapter_number: number;
  title?: string;
  scene?: string;
  characters?: string;
  plot?: string;
  conflict?: string;
  turning_point?: string;
  hook?: string;
  transition?: string;
  ending?: string;
  target_words: number;
  confirmed: boolean;
  created_at: string;
  has_content: boolean;
}

export interface ChapterOutlineUpdate {
  title?: string;
  scene?: string;
  characters?: string;
  plot?: string;
  conflict?: string;
  turning_point?: string;
  hook?: string;
  transition?: string;
  ending?: string;
  target_words?: number;
}
```

- [ ] **Step 6: 修改章节大纲创建 — `workflow_persistence.py`**

将 `persist_chapter_outlines` 中的 `ChapterOutline(...)` 构造加入新字段：

```python
        chapter_outline = ChapterOutline(
            project_id=project_id,
            chapter_number=co_data.get("chapter_number", 1),
            title=co_data.get("title"),
            scene=co_data.get("scene"),
            characters=co_data.get("characters"),
            plot=co_data.get("plot"),
            conflict=co_data.get("conflict"),
            turning_point=co_data.get("turning_point"),
            hook=co_data.get("hook"),
            transition=co_data.get("transition"),
            ending=co_data.get("ending"),
            target_words=co_data.get("target_words", 3000),
            confirmed=False,
        )
```

- [ ] **Step 7: 修改章节大纲创建 — `chapters.py` SSE 流内**

搜索 `chapters.py` 中所有 `ChapterOutline(` 构造，加入新字段。SSE 流内的章节大纲创建（约 L153-166）：

```python
                        chapter_outline = ChapterOutline(
                            project_id=project_id,
                            chapter_number=co_data.get("chapter_number", 1),
                            title=co_data.get("title"),
                            scene=co_data.get("scene"),
                            characters=co_data.get("characters"),
                            plot=co_data.get("plot"),
                            conflict=co_data.get("conflict"),
                            turning_point=co_data.get("turning_point"),
                            hook=co_data.get("hook"),
                            transition=co_data.get("transition"),
                            ending=co_data.get("ending"),
                            target_words=co_data.get("target_words", 3000),
                            confirmed=False
                        )
```

progress 事件（约 L130-143），补全缺失字段：

```python
                progress_payload = {
                    "chapter_number": event.get("chapter_number"),
                    "total": event.get("total"),
                    "chapter": {
                        "chapter_number": chapter_data.get("chapter_number"),
                        "title": chapter_data.get("title", ""),
                        "scene": chapter_data.get("scene", ""),
                        "characters": chapter_data.get("characters", ""),
                        "plot": chapter_data.get("plot", ""),
                        "conflict": chapter_data.get("conflict", ""),
                        "turning_point": chapter_data.get("turning_point", ""),
                        "hook": chapter_data.get("hook", ""),
                        "transition": chapter_data.get("transition", ""),
                        "ending": chapter_data.get("ending", ""),
                        "target_words": chapter_data.get("target_words", 3000),
                    }
                }
```

- [ ] **Step 8: 修改章节大纲更新 — `chapters.py:update_chapter_outline`**

在 `update_chapter_outline` 函数中（约 L284-298），加入新字段的更新逻辑：

```python
    # Update fields if provided
    if request.title is not None:
        chapter_outline.title = request.title
    if request.scene is not None:
        chapter_outline.scene = request.scene
    if request.characters is not None:
        chapter_outline.characters = request.characters
    if request.plot is not None:
        chapter_outline.plot = request.plot
    if request.conflict is not None:
        chapter_outline.conflict = request.conflict
    if request.turning_point is not None:
        chapter_outline.turning_point = request.turning_point
    if request.hook is not None:
        chapter_outline.hook = request.hook
    if request.transition is not None:
        chapter_outline.transition = request.transition
    if request.ending is not None:
        chapter_outline.ending = request.ending
    if request.target_words is not None:
        chapter_outline.target_words = request.target_words
```

- [ ] **Step 9: 补全所有 `ChapterOutlineResponse` 返回处 — 3 处**

`chapters.py` 中有 3 处手动构造 `ChapterOutlineResponse`，全部需加入新字段：

a) `get_chapter_outlines` 列表端点（约 L90-104），`outline_dict` 加入：

```python
        outline_dict = {
            "id": co.id,
            "project_id": co.project_id,
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
            "confirmed": co.confirmed,
            "created_at": co.created_at,
            "has_content": has_content
        }
```

b) `update_chapter_outline`（约 L308-322）：

```python
    return ChapterOutlineResponse(
        id=chapter_outline.id,
        project_id=chapter_outline.project_id,
        chapter_number=chapter_outline.chapter_number,
        title=chapter_outline.title,
        scene=chapter_outline.scene,
        characters=chapter_outline.characters,
        plot=chapter_outline.plot,
        conflict=chapter_outline.conflict,
        turning_point=chapter_outline.turning_point,
        hook=chapter_outline.hook,
        transition=chapter_outline.transition,
        ending=chapter_outline.ending,
        target_words=chapter_outline.target_words,
        confirmed=chapter_outline.confirmed,
        created_at=chapter_outline.created_at,
        has_content=has_content
    )
```

c) `confirm_chapter_outline`（约 L392-406）：

```python
    return ChapterOutlineResponse(
        id=chapter_outline.id,
        project_id=chapter_outline.project_id,
        chapter_number=chapter_outline.chapter_number,
        title=chapter_outline.title,
        scene=chapter_outline.scene,
        characters=chapter_outline.characters,
        plot=chapter_outline.plot,
        conflict=chapter_outline.conflict,
        turning_point=chapter_outline.turning_point,
        hook=chapter_outline.hook,
        transition=chapter_outline.transition,
        ending=chapter_outline.ending,
        target_words=chapter_outline.target_words,
        confirmed=chapter_outline.confirmed,
        created_at=chapter_outline.created_at,
        has_content=has_content
    )
```

- [ ] **Step 10: 执行迁移验证**

Run: `docker exec novelagent-backend-1 alembic upgrade head`

Expected: 无报错

- [ ] **Step 11: 验证全链路**

Run: `docker exec novelagent-backend-1 python -c "from app.models.outline import ChapterOutline; from app.schemas.chapter import ChapterOutlineBase, ChapterOutlineUpdate, ChapterOutlineResponse; print('orm:', [c.name for c in ChapterOutline.__table__.columns if c.name in ('turning_point','hook','transition')]); print('schema:', [f for f in ChapterOutlineBase.model_fields if f in ('turning_point','hook','transition')]); print('ok')"`

Expected: 三列名都出现在 orm 和 schema 输出中

- [ ] **Step 12: 提交**

```bash
git add backend/alembic/versions/ backend/app/models/outline.py backend/app/schemas/chapter.py backend/app/api/chapters.py backend/app/utils/workflow_persistence.py frontend/src/types/index.ts
git commit -m "feat(chapter-outline): add turning_point/hook/transition columns, full-stack贯通"
```

---

### Task 2: `build_initial_state` 数据完整性修复

**Files:**
- Modify: `backend/app/api/workflow.py:141-284`

- [ ] **Step 1: 修正 chapter_outlines 字段（加入新列）**

将 `build_initial_state` L167-179 的 chapter_outlines 构建改为：

```python
    chapter_outlines = [
        {
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
    ]
```

- [ ] **Step 2: 修正 characters 字段映射（对齐 DB 模型）**

将 L253-263 的 characters 加载改为：

```python
            state["characters"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "appearance": c.appearance or "",
                    "personality": c.personality or "",
                    "backstory": c.backstory or "",
                    "catchphrase": c.catchphrase or "",
                    "habit_action": c.habit_action or "",
                    "deep_fear": c.deep_fear or "",
                    "core_motivation": c.core_motivation or "",
                    "growth_arc": c.growth_arc or "",
                    "signature_item": c.signature_item or "",
                }
                for c in db_characters
            ]
```

- [ ] **Step 3: 加载 evolution_plans 和 evolution_records**

在 `if db is not None:` 块内，`db_relations` 加载之后、`return state` 之前（约 L282 之后）添加。使用 dict 做 O(1) 查找：

```python
        # 预加载演变计划和记录（通过 Relation join 查询，EvolutionPlan/Record 无 project_id）
        relation_ids = [r.id for r in db_relations]
        if relation_ids:
            from app.models.character import EvolutionPlan, EvolutionRecord

            db_plans = db.query(EvolutionPlan).filter(
                EvolutionPlan.relation_id.in_(relation_ids)
            ).order_by(EvolutionPlan.trigger_chapter).all()

            db_records = db.query(EvolutionRecord).filter(
                EvolutionRecord.relation_id.in_(relation_ids)
            ).order_by(EvolutionRecord.chapter_number).all()

            # 批量构建：id → Character 映射（O(1) 查找）
            char_map = {c.id: c for c in db_characters}

            # 批量构建：relation_id → (character_a_name, character_b_name)
            relation_name_map = {}
            for r in db_relations:
                a = char_map.get(r.character_a_id)
                b = char_map.get(r.character_b_id)
                relation_name_map[r.id] = (a.name if a else "未知", b.name if b else "未知")

            if db_plans:
                state["evolution_plans"] = [
                    {
                        "chapter_number": p.trigger_chapter,
                        "character_name": "、".join(relation_name_map.get(p.relation_id, ("未知", "未知"))),
                        "changes": f"{p.status_before or ''} → {p.status_after}",
                    }
                    for p in db_plans
                ]

            if db_records:
                state["evolution_records"] = [
                    {
                        "chapter_number": r.chapter_number,
                        "character_name": "、".join(relation_name_map.get(r.relation_id, ("未知", "未知"))),
                        "actual_changes": r.content,
                    }
                    for r in db_records
                ]
```

- [ ] **Step 4: 注入 `_prompts` 到 build_initial_state（带降级保护+日志+TODO）**

在 `return state` 之前添加。`_prompts` 是配置性数据，注入失败不应阻断业务流程，降级到 DEFAULT_PROMPTS 并记录日志：

```python
    # 预加载 prompts（过渡方案：统一 SSE 端点和 LangGraph 节点的 prompt 获取）
    # TODO: _prompts 应通过 LangGraph config 传递而非 state 字段，
    # 重构时移入 config["configurable"]["prompts"]，节点通过 config 获取
    if db is not None:
        try:
            state["_prompts"] = _build_prompts_dict(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load custom prompts, using defaults: {e}")
            from app.agents.prompts import DEFAULT_PROMPTS
            state["_prompts"] = DEFAULT_PROMPTS

    return state
```

- [ ] **Step 5: 删除 3 处重复的 `_prompts` 注入**

搜索 `workflow.py` 中所有 `initial_state["_prompts"] = _build_prompts_dict(db)` 的位置（约 L436、L831、L932），全部删除。

- [ ] **Step 6: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.api.workflow import build_initial_state, _build_prompts_dict; print('ok')"`

Expected: `ok`

- [ ] **Step 7: 提交**

```bash
git add backend/app/api/workflow.py
git commit -m "fix(workflow): build_initial_state loads complete data, injects _prompts with fallback"
```

---

### Task 3: 修正 `format_characters_info` 字段映射 + 补全 `_format_chapter_outline_str`

**Files:**
- Modify: `backend/app/agents/nodes/utils.py:4-50`
- Modify: `backend/tests/test_nodes_utils.py`

- [ ] **Step 1: 编写 `format_characters_info` 失败测试**

在 `backend/tests/test_nodes_utils.py` 的 `TestFormatCharactersInfo` 类之后追加测试类：

```python
class TestFormatCharactersInfoFieldMapping:
    """测试 format_characters_info 使用 DB 实际字段名"""

    def test_uses_backstory_not_background(self):
        """backstory 字段应显示为'背景'"""
        state = {"characters": [
            {"name": "张三", "role": "主角", "backstory": "曾是军人"},
        ]}
        result = format_characters_info(state)
        assert "曾是军人" in result
        assert "背景" in result

    def test_uses_db_model_fields(self):
        """DB Character 模型所有字段都应被格式化"""
        state = {"characters": [
            {
                "name": "张三", "role": "主角",
                "appearance": "高大", "personality": "沉稳",
                "backstory": "军人出身", "catchphrase": "走",
                "habit_action": "敲桌面", "deep_fear": "背叛",
                "core_motivation": "复仇", "growth_arc": "隐忍→觉醒",
                "signature_item": "旧怀表",
            },
        ]}
        result = format_characters_info(state)
        assert "高大" in result
        assert "沉稳" in result
        assert "军人出身" in result
        assert "走" in result
        assert "敲桌面" in result
        assert "背叛" in result
        assert "复仇" in result
        assert "隐忍→觉醒" in result
        assert "旧怀表" in result

    def test_old_fields_not_recognized(self):
        """旧字段名 background/skills/goals 不应被读取"""
        state = {"characters": [
            {"name": "张三", "role": "主角", "background": "旧背景", "skills": "旧能力", "goals": "旧目标"},
        ]}
        result = format_characters_info(state)
        assert "旧背景" not in result
        assert "旧能力" not in result
        assert "旧目标" not in result
```

- [ ] **Step 2: 编写 `_format_chapter_outline_str` 补全测试**

在 `TestFormatChapterOutlineStr` 类中追加测试：

```python
    def test_includes_transition_and_ending(self):
        """transition 和 ending 字段应被格式化"""
        chapter_outline = {
            "title": "初入江湖",
            "scene": "古城",
            "characters": "林风",
            "plot": "遭遇劫匪",
            "conflict": "对抗",
            "turning_point": "获得秘籍",
            "hook": "神秘符号",
            "transition": "黎明时分离开",
            "ending": "踏上征途",
        }
        result = _format_chapter_outline_str(chapter_outline)

        assert "衔接：黎明时分离开" in result
        assert "结局：踏上征途" in result
```

- [ ] **Step 3: 运行测试验证失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestFormatCharactersInfoFieldMapping tests/test_nodes_utils.py::TestFormatChapterOutlineStr::test_includes_transition_and_ending -v`

Expected: FAIL — `backstory`/`catchphrase` 等字段当前不被读取，`transition`/`ending` 不被输出

- [ ] **Step 4: 修正 `format_characters_info`**

将 `utils.py` L27-41 的 detailed_characters 分支替换为：

```python
    if detailed_characters:
        chars_str = "【详细人物设定】\n"
        for c in detailed_characters:
            chars_str += f"- {c.get('name', '')}（{c.get('role', '配角')}）：\n"
            if c.get("appearance"):
                chars_str += f"  外貌：{c.get('appearance')}\n"
            if c.get("personality"):
                chars_str += f"  性格：{c.get('personality')}\n"
            if c.get("backstory"):
                chars_str += f"  背景：{c.get('backstory')}\n"
            if c.get("catchphrase"):
                chars_str += f"  口头禅：{c.get('catchphrase')}\n"
            if c.get("habit_action"):
                chars_str += f"  习惯动作：{c.get('habit_action')}\n"
            if c.get("deep_fear"):
                chars_str += f"  深层恐惧：{c.get('deep_fear')}\n"
            if c.get("core_motivation"):
                chars_str += f"  核心动机：{c.get('core_motivation')}\n"
            if c.get("growth_arc"):
                chars_str += f"  成长弧线：{c.get('growth_arc')}\n"
            if c.get("signature_item"):
                chars_str += f"  标志性物品：{c.get('signature_item')}\n"
        return chars_str
```

- [ ] **Step 5: 补全 `_format_chapter_outline_str` 缺失字段**

将 `utils.py` L4-14 的 `_format_chapter_outline_str` 替换为：

```python
def _format_chapter_outline_str(chapter_outline: dict) -> str:
    """格式化章节大纲为提示词用字符串"""
    return f"""
章节名：{chapter_outline.get("title", "")}
场景：{chapter_outline.get("scene", "")}
人物：{chapter_outline.get("characters", "")}
情节：{chapter_outline.get("plot", "")}
冲突：{chapter_outline.get("conflict", "")}
转折：{chapter_outline.get("turning_point", "无")}
钩子：{chapter_outline.get("hook", "")}
衔接：{chapter_outline.get("transition", "")}
结局：{chapter_outline.get("ending", "")}
"""
```

- [ ] **Step 6: 更新旧测试数据 — `TestFormatCharactersInfo`**

将 `test_nodes_utils.py` L60-83 的 `test_detailed_characters` 中的旧字段名替换为 DB 实际字段：

```python
    def test_detailed_characters(self):
        """有详细人物设定时，应格式化所有字段"""
        state = {
            "characters": [
                {
                    "name": "林风",
                    "role": "主角",
                    "appearance": "剑眉星目",
                    "personality": "坚毅果敢",
                    "backstory": "山村少年",
                    "catchphrase": "剑来",
                    "habit_action": "摩挲剑柄",
                    "deep_fear": "失去至亲",
                    "core_motivation": "守护苍生",
                    "growth_arc": "少年→仙帝",
                    "signature_item": "玄铁剑",
                }
            ]
        }
        result = format_characters_info(state)

        assert "【详细人物设定】" in result
        assert "林风（主角）" in result
        assert "外貌：剑眉星目" in result
        assert "性格：坚毅果敢" in result
        assert "背景：山村少年" in result
        assert "口头禅：剑来" in result
        assert "习惯动作：摩挲剑柄" in result
        assert "深层恐惧：失去至亲" in result
        assert "核心动机：守护苍生" in result
        assert "成长弧线：少年→仙帝" in result
        assert "标志性物品：玄铁剑" in result
```

同时更新 L100-101 的 `test_detailed_characters_partial_fields` 断言——`background` 改为 `backstory`：

```python
    def test_detailed_characters_partial_fields(self):
        """详细人物设定缺少部分字段时，只输出已有字段"""
        state = {
            "characters": [
                {
                    "name": "苏瑶",
                    "role": "女主",
                    "personality": "温柔聪慧",
                }
            ]
        }
        result = format_characters_info(state)

        assert "苏瑶（女主）" in result
        assert "性格：温柔聪慧" in result
        assert "外貌" not in result
        assert "背景" not in result
```

此测试无需改动——它检查"背景"不在结果中，而修改后苏瑶没有 `backstory` 字段，所以"背景"确实不会出现，断言仍然正确。

- [ ] **Step 7: 运行全部 nodes_utils 测试验证通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py -v`

Expected: 全部 PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/agents/nodes/utils.py backend/tests/test_nodes_utils.py
git commit -m "fix(utils): format_characters_info uses DB field names, _format_chapter_outline_str adds transition/ending"
```

---

### Task 4: 章节大纲生成补充人物关系和演变上下文

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py:210-237`

- [ ] **Step 1: 在 `generate_single_chapter_outline` 中补充关系和演变上下文**

在 `chars_str = format_characters_info(state)` 之后（约 L211），将后续代码改为：

```python
    # 格式化人物设定
    chars_str = format_characters_info(state)

    # 格式化人物关系和演变计划
    relations_str = format_relations_info(state, chapter_number)
    evolution_str, _ = format_evolution_info(state, chapter_number)
    combined_chars = chars_str + relations_str + evolution_str

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)
```

然后在 prompt 构建中，将 `characters=chars_str` 改为 `characters=combined_chars`：

```python
    prompt = prompt_template.format(
        outline=outline,
        plot_points=plot_points_str,
        characters=combined_chars,
        world_setting=world_str,
        emotional_curve=emotional_curve,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info,
        min_words=min_words,
    )
```

确认 `format_relations_info` 和 `format_evolution_info` 已在 import 中（当前文件已有 import）。如果缺少则添加。

- [ ] **Step 2: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.chapter_generation import generate_single_chapter_outline; print('ok')"`

Expected: `ok`

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/nodes/chapter_generation.py
git commit -m "feat(chapter-outline): pass relations and evolution context to chapter outline generation"
```

---

### Task 5: ContextStrategy 接口扩展 + HybridContentStrategy 实现

**Files:**
- Modify: `backend/app/agents/context_strategy.py`
- Modify: `backend/tests/test_context_strategy.py`

- [ ] **Step 1: 编写 HybridContentStrategy 失败测试**

在 `test_context_strategy.py` 中追加：

```python
from app.agents.context_strategy import HybridContentStrategy


class TestHybridContentStrategy:
    def test_no_previous_chapters(self):
        """第一章没有前文"""
        strategy = HybridContentStrategy(recent_count=3)
        result = strategy.build_previous_context([], 1)
        assert "没有前文" in result

    def test_all_recent_fulltext(self):
        """所有前章都在近章范围内，全部全文"""
        strategy = HybridContentStrategy(recent_count=3)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        outlines = [
            {"chapter_number": 1, "title": "起风了", "plot": "风吹过"},
            {"chapter_number": 2, "title": "雨来了", "plot": "雨倾盆"},
        ]
        result = strategy.build_previous_context(chapters, 3, outlines)
        assert "风起" in result
        assert "雨落" in result

    def test_distant_uses_outlines(self):
        """远章从 chapter_outlines 取概要，不取全文"""
        strategy = HybridContentStrategy(recent_count=1)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "很长的正文内容。"},
            {"chapter_number": 2, "title": "雨来了", "content": "也很长的正文。"},
            {"chapter_number": 3, "title": "雷鸣", "content": "雷声轰鸣。"},
        ]
        outlines = [
            {"chapter_number": 1, "title": "起风了", "plot": "大风席卷", "conflict": "人与自然", "hook": "风暴将至"},
            {"chapter_number": 2, "title": "雨来了", "plot": "暴雨如注", "conflict": "求生存"},
            {"chapter_number": 3, "title": "雷鸣", "plot": "雷电交加"},
        ]
        result = strategy.build_previous_context(chapters, 4, outlines)
        # 远章（1、2）只有概要，不出现全文
        assert "大风席卷" in result
        assert "很长的正文内容" not in result
        # 近章（3）有全文
        assert "雷声轰鸣" in result

    def test_distant_without_outlines_falls_back(self):
        """远章没有 chapter_outlines 时不输出概要"""
        strategy = HybridContentStrategy(recent_count=1)
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 3, chapter_outlines=None)
        # 近章有全文
        assert "雨落" in result
        # 远章无 outlines 不输出概要段
        assert "前文概要" not in result

    def test_get_context_strategy_hybrid(self):
        """用户选择 hybrid 策略时返回 HybridContentStrategy"""
        strategy = get_context_strategy(100000, "hybrid")
        assert isinstance(strategy, HybridContentStrategy)

    def test_fulltext_ignores_chapter_outlines(self):
        """全文策略忽略 chapter_outlines 参数"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
        ]
        outlines = [{"chapter_number": 1, "plot": "不应该出现"}]
        result = strategy.build_previous_context(chapters, 2, outlines)
        assert "风起" in result
        assert "不应该出现" not in result
```

- [ ] **Step 2: 运行测试验证失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py::TestHybridContentStrategy -v`

Expected: FAIL — `HybridContentStrategy` 未导入/未实现

- [ ] **Step 3: 修改 ContextStrategy 接口和实现**

将 `context_strategy.py` 全文替换为：

```python
"""上下文策略 — 管理章节生成时的前文上下文构建方式"""

from abc import ABC, abstractmethod


class ContextStrategy(ABC):
    """上下文策略基类"""

    @abstractmethod
    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
    ) -> str:
        """构建前文上下文文本

        Args:
            written_chapters: 已写章节列表（含 content）
            current_chapter: 当前章节号
            chapter_outlines: 章节大纲列表（远章概要的数据源，可选）
        """
        pass


class FulltextContentStrategy(ContextStrategy):
    """全文策略：所有已写章节全文放入上下文"""

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
    ) -> str:
        parts = []
        for ch in written_chapters:
            ch_num = ch.get("chapter_number", 0)
            if ch_num < current_chapter:
                title = ch.get("title", "")
                content = ch.get("content", "")
                if content:
                    parts.append(f"第{ch_num}章《{title}》\n{content}")
        if not parts:
            return "（这是第一章，没有前文）"
        return "\n\n---\n\n".join(parts)


class HybridContentStrategy(ContextStrategy):
    """混合策略：近 N 章全文 + 远章大纲概要

    近章提供完整的语言风格和衔接参考，
    远章提供情节线索和伏笔追踪（从 chapter_outlines 提取，无需 LLM 调用）。
    """

    def __init__(self, recent_count: int = 3):
        self.recent_count = recent_count

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
    ) -> str:
        if not written_chapters:
            return "（这是第一章，没有前文）"

        # 分离近章和远章
        recent = []
        distant_nums = []
        for ch in written_chapters:
            ch_num = ch.get("chapter_number", 0)
            if ch_num < current_chapter:
                if current_chapter - ch_num <= self.recent_count:
                    recent.append(ch)
                else:
                    distant_nums.append(ch_num)

        parts = []

        # 远章：从 chapter_outlines 提取概要
        if distant_nums and chapter_outlines:
            outline_map = {co.get("chapter_number"): co for co in chapter_outlines}
            distant_parts = []
            for ch_num in sorted(distant_nums):
                co = outline_map.get(ch_num, {})
                title = co.get("title", "")
                plot = co.get("plot", "")
                conflict = co.get("conflict", "")
                hook = co.get("hook", "")
                summary = f"第{ch_num}章《{title}》"
                if plot:
                    summary += f"\n情节：{plot[:200]}"
                if conflict:
                    summary += f"\n冲突：{conflict}"
                if hook:
                    summary += f"\n钩子：{hook}"
                distant_parts.append(summary)
            if distant_parts:
                parts.append("【前文概要】\n" + "\n\n".join(distant_parts))

        # 近章：全文
        if recent:
            recent_parts = []
            for ch in sorted(recent, key=lambda x: x.get("chapter_number", 0)):
                title = ch.get("title", "")
                content = ch.get("content", "")
                recent_parts.append(f"第{ch.get('chapter_number', 0)}章《{title}》\n{content}")
            parts.append("【近期全文】\n" + "\n\n---\n\n".join(recent_parts))

        return "\n\n---\n\n".join(parts) if parts else "（这是第一章，没有前文）"


class SummaryContentStrategy(ContextStrategy):
    """摘要策略（Phase 4 实现）"""

    def build_previous_context(self, written_chapters, current_chapter, chapter_outlines=None):
        raise NotImplementedError("SummaryContentStrategy 尚未实现")


# 策略名到类的映射
_STRATEGY_MAP = {
    "fulltext": FulltextContentStrategy,
    "hybrid": HybridContentStrategy,
    "summary": SummaryContentStrategy,
}


def get_context_strategy(target_words: int, strategy_name: str | None = None) -> ContextStrategy:
    """根据策略名或目标字数选择上下文策略

    Args:
        target_words: 目标字数（仅当 strategy_name 为 None 时用作回退）
        strategy_name: 用户选择的策略名（fulltext/hybrid/summary），优先级高于 target_words
    """
    if strategy_name and strategy_name in _STRATEGY_MAP:
        return _STRATEGY_MAP[strategy_name]()
    # 回退：当前默认全文策略
    return FulltextContentStrategy()
```

- [ ] **Step 4: 运行全部 context_strategy 测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py -v`

Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/context_strategy.py backend/tests/test_context_strategy.py
git commit -m "feat(context-strategy): add chapter_outlines param, implement HybridContentStrategy"
```

---

### Task 6: 适配节点调用 — 传入 chapter_outlines + 使用 get_context_strategy

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py:359-366`
- Modify: `backend/app/agents/nodes/review.py:11, 51`
- Modify: `backend/app/agents/nodes/rewrite.py:11, 51`

- [ ] **Step 1: 修改 chapter_generation.py 传入 chapter_outlines**

将 L359-366 的上下文策略调用改为：

```python
    # 上下文策略：构建前文上下文
    target_words = info.get("targetWords", 100000)
    if isinstance(target_words, str):
        target_words = int(target_words)
    strategy_name = info.get("contextStrategy")
    strategy = get_context_strategy(target_words, strategy_name)
    chapter_outlines_list = state.get("chapter_outlines", [])
    previous_context = strategy.build_previous_context(written_chapters, chapter_number, chapter_outlines_list)
```

- [ ] **Step 2: 修改 review.py — 改用 get_context_strategy + 传入 chapter_outlines**

修改 import，将：

```python
from app.agents.context_strategy import FulltextContentStrategy
```

改为：

```python
from app.agents.context_strategy import get_context_strategy
```

将 `_build_review_messages` 中 L51 的策略调用改为：

```python
    # 上下文策略：构建前文上下文
    target_words = info.get("targetWords", 100000)
    if isinstance(target_words, str):
        target_words = int(target_words)
    strategy_name = info.get("contextStrategy")
    strategy = get_context_strategy(target_words, strategy_name)
    chapter_outlines_list = state.get("chapter_outlines", [])
    previous_context = strategy.build_previous_context(written_chapters, chapter_number, chapter_outlines_list)
```

- [ ] **Step 3: 修改 rewrite.py — 改用 get_context_strategy + 传入 chapter_outlines**

修改 import，将：

```python
from app.agents.context_strategy import FulltextContentStrategy
```

改为：

```python
from app.agents.context_strategy import get_context_strategy
```

将 `_build_rewrite_messages` 中 L51 的策略调用改为：

```python
    # 上下文策略：构建前文上下文
    target_words = info.get("targetWords", 100000)
    if isinstance(target_words, str):
        target_words = int(target_words)
    strategy_name = info.get("contextStrategy")
    strategy = get_context_strategy(target_words, strategy_name)
    chapter_outlines_list = state.get("chapter_outlines", [])
    previous_context = strategy.build_previous_context(written_chapters, chapter_number, chapter_outlines_list)
```

- [ ] **Step 4: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.chapter_generation import generate_chapter_content_node; from app.agents.nodes.review import review_node; from app.agents.nodes.rewrite import rewrite_node; print('ok')"`

Expected: `ok`

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/nodes/chapter_generation.py backend/app/agents/nodes/review.py backend/app/agents/nodes/rewrite.py
git commit -m "feat(nodes): use get_context_strategy + pass chapter_outlines for hybrid strategy support"
```

---

### Task 7: 运行全部后端测试验证

**Files:** 无修改

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`

Expected: 全部 PASS。重点关注：
- `test_context_strategy.py`
- `test_nodes_utils.py`
- `test_review.py`
- `test_rewrite.py`
- `test_agents.py`
- `test_workflow.py`

- [ ] **Step 2: 如有测试失败，修复并重新运行**

常见可能失败原因：
- 旧测试 mock 了 `FulltextContentStrategy()` 直接调用，需改为 mock `get_context_strategy` 返回值
- `build_initial_state` 相关测试依赖旧字段名
- `test_review.py` / `test_rewrite.py` 中 mock 了 `FulltextContentStrategy` import

- [ ] **Step 3: 提交修复（如有）**

```bash
git add -u
git commit -m "fix: update tests for context strategy and field mapping changes"
```
