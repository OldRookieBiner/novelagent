# Prompt 质量与上下文传递优化 — Phase 2 实现计划

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 完成 Phase 2 两个优化项：rewrite 节点 Prompt 加载统一 + 禁用词表抽取

**Architecture:** 
- Prompt 加载统一为 `state["_prompts"]` + `DEFAULT_PROMPTS` 回退模式
- 禁用词表抽取为 `app/agents/constants.py` 共享常量

---

## Task 1: Fix rewrite 节点 Prompt 加载 — 改为 state["_prompts"]

**Files:**
- Modify: `backend/app/agents/nodes/rewrite.py:49`
- Modify: `backend/app/api/workflow.py:380` 和 `738` — 补全 _prompts 预加载

- [ ] **Step 1: 修改 rewrite.py**

将：
```python
from app.services.prompt_loader import get_system_prompt
...
prompt = get_system_prompt(db, "rewrite").format(...)
```

改为：
```python
# 优先从 state["_prompts"] 获取，回退到 DEFAULT_PROMPTS
prompts = state.get("_prompts", {})
if prompts and "rewrite" in prompts:
    prompt_template = prompts["rewrite"]
else:
    from app.agents.prompts import DEFAULT_PROMPTS
    prompt_template = DEFAULT_PROMPTS.get("rewrite", "")

prompt = prompt_template.format(...)
```

注意：`rewrite_chapter_node` 的签名需要调整，因为要支持从 state 获取 prompts。

- [ ] **Step 2: 补全 workflow.py 中的 _prompts 预加载**

在 `workflow.py` 第 380 行和第 738 行，将 `_prompts` 字典补全为 7 个 key：
```python
initial_state["_prompts"] = {
    "outline_generation": get_system_prompt(db, "outline_generation"),
    "character_generation": get_system_prompt(db, "character_generation"),
    "relation_generation": get_system_prompt(db, "relation_generation"),
    "chapter_outline_generation": get_system_prompt(db, "chapter_outline_generation"),
    "chapter_content_generation": get_system_prompt(db, "chapter_content_generation"),
    "review": get_system_prompt(db, "review"),
    "rewrite": get_system_prompt(db, "rewrite"),
}
```

- [ ] **Step 3: 运行测试验证**

```bash
docker exec novelagent-backend-1 pytest tests/ -v -k "rewrite" 2>&1 | tail -20
```

---

## Task 2: 禁用词表抽取为共享常量

**Files:**
- Create: `backend/app/agents/constants.py`
- Modify: `backend/app/agents/prompts.py` — 引用常量
- Test: `backend/tests/test_constants.py` (新增)

- [ ] **Step 1: 创建 constants.py**

```python
# 禁用词汇列表（AI 味检测用）
FORBIDDEN_WORDS = [
    "不禁", "竟然", "居然", "蓦然", "恍然", "心中涌起", "一股暖流",
    "下意识", "不由自主地", "心头一震", "悄然", "缓缓", "注视",
    "似乎", "仿佛", "嘴角上扬", "眼神复杂", "欲言又止", "眸光微动",
    "眼中闪过一丝", "深吸一口气", "定了定神", "迟疑了片刻",
    "心里五味杂陈", "莫名的", "本能地", "条件反射", "脑海里浮现",
    "心中一动", "暗暗", "不动声色", "目光一凝", "瞳孔微缩", "浑身一震",
    "作为 AI",
]

# 禁用句式列表
FORBIDDEN_PATTERNS = [
    "他的眼神里有复杂的情绪",
    "她的嘴角微微上扬，露出一个意味深长的笑容",
    "两人对视了一眼，仿佛有千言万语",
]

# 禁用规则
FORBIDDEN_RULES = [
    "每段结尾的总结性句子（如"这一夜，注定不平静"）",
    "超过 3 行的纯心理活动描写",
    "用 "……" 省略号表达沉默或情绪（最多每章出现 1 次，且不超过 3 个连续点）",
    "以风光描写开头的环境铺陈（除非这个环境本身就是角色心理的投射）",
]
```
    "每段结尾的总结性句子（如"这一夜，注定不平静"）",
    "超过 3 行的纯心理活动描写",
    "用 "……" 省略号表达沉默或情绪（最多每章出现 1 次，且不超过 3 个连续点）",
    "以风光描写开头的环境铺陈（除非这个环境本身就是角色心理的投射）",
]
```

- [ ] **Step 2: 修改 prompts.py 引用常量**

在 GENERATE_CHAPTER_CONTENT_PROMPT 和 REVIEW_CHAPTER_PROMPT 中，用 `{forbidden_words}` 替换硬编码的词表。

- [ ] **Step 3: 编写测试**

```python
def test_forbidden_words_not_empty():
    from app.agents.constants import FORBIDDEN_WORDS
    assert len(FORBIDDEN_WORDS) > 0

def test_forbidden_words_no_duplicates():
    from app.agents.constants import FORBIDDEN_WORDS
    assert len(FORBIDDEN_WORDS) == len(set(FORBIDDEN_WORDS))
```

- [ ] **Step 4: 运行测试验证**

```bash
docker exec novelagent-backend-1 pytest tests/test_constants.py -v
```

---

## 验证方案

1. 运行完整后端测试：`docker exec novelagent-backend-1 pytest -v`
2. 运行前端测试：`cd frontend && npm run test:run`
3. 确认 rewrite 功能正常工作