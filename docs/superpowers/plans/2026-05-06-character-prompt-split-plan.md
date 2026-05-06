# 大纲与人物 Prompt 拆分实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将人物生成从大纲 prompt 完全拆分出来，使大纲 prompt 只专注大纲生成，人物由独立的 LLM 调用负责。

**Architecture:** 修改 4 个后端文件：`prompts.py`（新增/修改 prompt 模板）、`character_generation.py`（增加 LLM 调用和解析器）、`system_prompt.py`（注册 agent type）、`system_prompts.py`（注册 prompt key）。不修改 graph、state、workflow API、persistence、frontend 和 tests。

**Tech Stack:** Python, LangGraph, SQLAlchemy, FastAPI

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/agents/prompts.py` | 修改 | 新增 CHARACTER_GENERATION_PROMPT，移除大纲 prompt 人物板块，更新 DEFAULT_PROMPTS |
| `backend/app/agents/nodes/character_generation.py` | 修改 | 增加 LLM 调用 + `parse_character_generation_response()` |
| `backend/app/schemas/system_prompt.py` | 修改 | 注册 `character_generation` agent type |
| `backend/app/api/system_prompts.py` | 修改 | 添加 `character_generation` 到 PROMPT_KEY_MAP |

---

### Task 1: 新增人物生成 Prompt 模板 & 简化大纲 Prompt

**Files:**
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: 新增 `CHARACTER_GENERATION_PROMPT`**

在 `RELATION_GENERATION_PROMPT` 之前（第 415 行前）插入：

```python
# ==================== 人物生成 Prompt ====================

CHARACTER_GENERATION_PROMPT = """你是一个资深小说角色设计师，擅长根据故事大纲创建性格鲜明、有深度、让人过目不忘的角色。

## 输入信息

### 大纲概述
{outline_summary}

### 世界观时代背景
{world_era}

## 输出要求

请根据大纲创建 4-6 个核心角色，严格按以下格式输出每条：

- 角色定位 | 姓名 | 性格描述 | 核心动机 | 成长弧线

### 角色定位
必须是以下之一：主角、核心反派、重要配角、配角

### 字段说明
- 姓名：2-4个字的中文名，符合世界观背景，不要用英文名
- 性格描述：用具体行为特征而非抽象形容词，如"面对威胁时表面冷静但会咬指甲"而不是"勇敢"（50字以内）
- 核心动机：角色最想要的东西和为什么（50字以内）
- 成长弧线：初期状态 → 经历的核心事件 → 最终状态（80字以内）

### 规则
1. 必须包含至少 1 个主角和 1 个核心反派
2. 所有角色姓名必须不同
3. 角色之间要有内在矛盾或张力关系
4. 性格描述必须有辨识度，不同角色之间要有鲜明对比
5. 严格按管道符分隔格式输出，每行一条

示例输出：
- 主角 | 林昭 | 话少但观察力极强，习惯用手指敲桌面表达不耐烦 | 寻找十年前灭门惨案的真相 | 隐忍复仇者 → 发现真凶是恩师 → 在复仇与救赎间抉择
- 核心反派 | 沈鹤鸣 | 温文尔雅的外表下控制欲极强，对秩序有偏执追求 | 建立一个"完美秩序"的世界，不惜任何代价 | 理想主义改革家 → 手段日益极端 → 成为自己曾反抗的暴君

请直接输出角色列表，不要添加任何解释说明。
"""
```

- [ ] **Step 2: 修改 `OUTLINE_GENERATION_PROMPT`，移除人物设定板块**

替换 `OUTLINE_GENERATION_PROMPT` 中的以下内容：

**替换前（第 15 行 "六大板块"）：**
```python
请按以下 **六大板块** 输出完整大纲：
```

**替换后：**
```python
请按以下 **五大板块** 输出完整大纲：
```

**删除（第 28-37 行，整个 "### 三、人物设定" 板块）：**
删除以下全部内容：
```python
### 三、人物设定（要求立体化）
- 主角：[姓名] | [一句话核心性格，用具体行为而非形容词，如"面对威胁时表面冷静但会咬指甲"而不是"勇敢"]
  - 口头禅：[常说的一句话或语气词]
  - 习惯动作：[紧张/思考/愤怒时的具象化动作]
  - 深层恐惧/弱点：[不为人知的软肋，驱动其决策的核心]
  - 核心动机：[最想要的东西，为什么]
  - 成长弧线：[初期的状态 → 经历的核心事件 → 最终的状态转变]
- 核心反派：[姓名] | [与主角的关系] | [其行为的合理性/令人共情之处，拒绝脸谱化]
- 重要配角1：[姓名] | [与主角的关系及演变] | [在本故事中的不可替代作用]
（可根据需要增加，但核心人物不超过 6 个）
```

**修改板块编号（第 39 行起）：**
```python
### 四、世界观与势力    →    ### 三、世界观与势力
### 五、情节节点        →    ### 四、情节节点
### 六、情感曲线与节奏  →    ### 五、情感曲线与节奏
### 七、伏笔-回收地图    →    ### 六、伏笔-回收地图
```

**修改注意事项第 2 条（第 73 行）：**

删除这一行：
```python
2. **人物设定要用具体事件/行为体现**，禁止出现"勇敢善良""冷酷无情"等抽象标签。
```

将后续条目重新编号：
```python
2. **每个情节节点必须有明确的冲突和钩子**，不能是状态描述。
3. **情感曲线必须有至少 3 次起伏**，避免单调上升/下降。
4. **伏笔密度要求**：前 1/3 章节至少埋设 5 个有效伏笔，且全部在后文有回收。
5. **世界观规则必须自洽**，任何超自然设定都要有约束和代价。
6. **情节节点数量应与目标章节数严格匹配**，每个节点对应 2-4 个章节。
```

**简化描述文本（第 1 行）：**
```python
OUTLINE_GENERATION_PROMPT = """你是一个拥有 20 年经验的资深小说策划师，擅长设计结构严谨、伏笔密布的长篇小说。
```

- [ ] **Step 3: 更新 `DEFAULT_PROMPTS` 字典**

在 `DEFAULT_PROMPTS` 中添加新条目：

在 `"relation_generation": RELATION_GENERATION_PROMPT,` 之前插入：
```python
    "character_generation": CHARACTER_GENERATION_PROMPT,
```

- [ ] **Step 4: 验证语法正确性**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.prompts import DEFAULT_PROMPTS, CHARACTER_GENERATION_PROMPT, OUTLINE_GENERATION_PROMPT; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/prompts.py
git commit -m "feat(backend): add character generation prompt, simplify outline prompt
- New CHARACTER_GENERATION_PROMPT for dedicated character creation
- Remove character settings section from OUTLINE_GENERATION_PROMPT (5 sections now)
- Register character_generation in DEFAULT_PROMPTS

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 重构角色生成节点，增加 LLM 调用

**Files:**
- Modify: `backend/app/agents/nodes/character_generation.py`

- [ ] **Step 1: 新增 `parse_character_generation_response()` 解析器**

在 `_map_role()` 函数之后插入：

```python
import re


# 预编译正则：匹配 - 角色定位 | 姓名 | 性格 | 核心动机 | 成长弧线
_RE_CHARACTER_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
)


def parse_character_generation_response(response: str) -> list[dict]:
    """从 AI 响应中解析角色列表

    格式：- 角色定位 | 姓名 | 性格描述 | 核心动机 | 成长弧线

    Args:
        response: AI 原始响应文本

    Returns:
        解析后的角色列表 [{name, role, personality, core_motivation, growth_arc}]
    """
    characters = []

    for line in response.strip().split("\n"):
        match = _RE_CHARACTER_LINE.search(line)
        if not match:
            continue

        role_label = match.group(1).strip()
        name = match.group(2).strip()
        personality = match.group(3).strip()
        core_motivation = match.group(4).strip()
        growth_arc = match.group(5).strip()

        # 姓名不能为空或纯标点
        if not name or len(name) < 1:
            continue

        characters.append(
            {
                "name": name,
                "role": _map_role(role_label),
                "personality": personality[:500],
                "core_motivation": core_motivation[:500],
                "growth_arc": growth_arc[:500],
            }
        )

    return characters
```

- [ ] **Step 2: 重构 `create_characters_from_outline_node`，增加 LLM 调用**

用以下内容替换现有的函数体（第 72-109 行）：

```python
async def create_characters_from_outline_node(state: NovelState) -> NovelState:
    """LangGraph 节点：根据大纲通过独立 LLM 调用生成角色

    签名： (state: NovelState) -> NovelState

    读取大纲摘要和世界观背景，使用 character_generation prompt
    调用 LLM 生成角色列表。不再依赖 state["outline_characters"]。

    注意：数据库 session 由 workflow API 中 astream_events 的 persist 逻辑管理，
    此节点仅负责生成数据，不自行创建/提交 session。
    """
    import logging
    from app.database import SessionLocal
    from app.services.prompt_loader import get_system_prompt
    from app.utils.llm import get_llm_from_state_async

    logger = logging.getLogger(__name__)

    outline_summary = state.get("outline_summary", "")
    world_era = (state.get("outline_world_setting") or {}).get("era", "未指定")

    characters = []

    try:
        # 获取 LLM 服务
        llm = await get_llm_from_state_async(state)

        # 获取人物生成 prompt
        db = SessionLocal()
        try:
            prompt = get_system_prompt(db, "character_generation").format(
                outline_summary=outline_summary,
                world_era=world_era,
            )
        finally:
            db.close()

        # 调用 LLM 生成人物
        response = await llm.chat([{"role": "user", "content": prompt}])

        # 解析响应
        characters = parse_character_generation_response(response)

        logger.info(
            f"character_gen_node: LLM generated {len(characters)} characters"
        )

    except Exception as e:
        logger.warning(
            f"character_gen_node: LLM call failed ({e}), "
            f"character list will be empty"
        )

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }

    return new_state
```

- [ ] **Step 3: 移除不再需要的导入**

删除文件顶部不再使用的 `import asyncio` 和 `from sqlalchemy.orm import Session`（如果 `extract_characters_from_outline` 仍需要 `Session`，则保留后者）。

- [ ] **Step 4: 验证语法正确性**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.nodes.character_generation import create_characters_from_outline_node, parse_character_generation_response, extract_characters_from_outline; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/nodes/character_generation.py
git commit -m "feat(backend): add LLM call to character generation node
- New parse_character_generation_response() parses pipe-delimited format
- create_characters_from_outline_node now calls LLM with dedicated prompt
- Falls back to empty list if LLM call fails

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 注册 character_generation Agent Type

**Files:**
- Modify: `backend/app/schemas/system_prompt.py`

- [ ] **Step 1: 扩展 `AgentTypeKey` 类型**

在第 17 行末尾添加 `"character_generation"`：

```python
AgentTypeKey = Literal[
    "outline_generation",
    "chapter_outline_generation",
    "chapter_content_generation",
    "review",
    "rewrite",
    "character_generation",
]
```

- [ ] **Step 2: 添加 agent type 元数据**

在 `AGENT_TYPES` 字典末尾（"rewrite" 条目的 `},` 之后，`}` 之前）添加：

```python
    "character_generation": {
        "name": "人物生成",
        "description": "根据小说大纲概述和世界观设定，生成性格鲜明的人物角色列表",
        "variables": ["outline_summary", "world_era"],
        "variable_descriptions": {
            "outline_summary": "小说大纲的概述内容，包含核心冲突和故事主线",
            "world_era": "故事世界观的年代设定，如古代、现代、未来、架空",
        },
    },
```

- [ ] **Step 3: 更新 `outline_generation` 描述（移除"包含人物设定"）**

将第 30 行的描述从：
```python
"description": "根据灵感信息生成结构化大纲，包含人物设定、世界观、情节节点",
```

改为：
```python
"description": "根据灵感信息生成结构化大纲，包含世界观、情节节点、情感曲线、伏笔地图",
```

- [ ] **Step 4: 验证语法正确性**

```bash
docker exec novelagent-backend-1 python -c "from app.schemas.system_prompt import AGENT_TYPES; assert 'character_generation' in AGENT_TYPES; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/system_prompt.py
git commit -m "feat(backend): register character_generation agent type
- Add character_generation to AgentTypeKey type and AGENT_TYPES metadata
- Update outline_generation description (no longer mentions character settings)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 注册 character_generation Prompt Key

**Files:**
- Modify: `backend/app/api/system_prompts.py`

- [ ] **Step 1: 添加 prompt key 映射**

在 `PROMPT_KEY_MAP` 字典中添加新条目（第 26 行 `}` 前）：

```python
PROMPT_KEY_MAP = {
    "outline_generation": "prompt_outline_generation",
    "chapter_outline_generation": "prompt_chapter_outline_generation",
    "chapter_content_generation": "prompt_chapter_content_generation",
    "review": "prompt_review",
    "rewrite": "prompt_rewrite",
    "character_generation": "prompt_character_generation",
}
```

- [ ] **Step 2: 验证语法正确性**

```bash
docker exec novelagent-backend-1 python -c "from app.api.system_prompts import PROMPT_KEY_MAP; assert 'character_generation' in PROMPT_KEY_MAP; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/system_prompts.py
git commit -m "feat(backend): add character_generation to prompt key map

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 集成验证

**Files:** 无新文件

- [ ] **Step 1: 重启后端并验证所有模块可导入**

```bash
docker compose restart backend
sleep 3
docker exec novelagent-backend-1 python -c "
from app.agents.prompts import DEFAULT_PROMPTS, CHARACTER_GENERATION_PROMPT, OUTLINE_GENERATION_PROMPT
from app.agents.nodes.character_generation import create_characters_from_outline_node, parse_character_generation_response, extract_characters_from_outline
from app.schemas.system_prompt import AGENT_TYPES, AgentTypeKey
from app.api.system_prompts import PROMPT_KEY_MAP
print('All imports OK')
print('DEFAULT_PROMPTS keys:', list(DEFAULT_PROMPTS.keys()))
print('AGENT_TYPES keys:', list(AGENT_TYPES.keys()))
print('PROMPT_KEY_MAP keys:', list(PROMPT_KEY_MAP.keys()))
"
```

Expected: 全部导入成功，三个字典都包含 `character_generation`。

- [ ] **Step 2: 运行现有测试确认无回归**

```bash
docker exec novelagent-backend-1 pytest -v
```

Expected: 所有测试通过。

- [ ] **Step 3: 验证 API 端点正常**

```bash
# 验证 settings 页 prompt 列表包含新 agent type
curl -s http://localhost:8000/api/system_prompts/ 2>&1 | python -c "import sys,json; data=json.load(sys.stdin); types=[p['agent_type'] for p in data['prompts']]; print('Agent types from API:', types); assert 'character_generation' in types"
```

Expected: `Agent types from API: [..., 'character_generation']`

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "chore(backend): add integration verification notes for character prompt split

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## 完成条件

1. 所有 4 个文件的修改已提交
2. `docker exec novelagent-backend-1 pytest -v` 全部通过
3. API `/api/system_prompts/` 返回包含 `character_generation`
4. 灵感页面"开始规划"功能正常工作，人物生成独立于大纲生成