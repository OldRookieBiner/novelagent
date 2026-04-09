# NovelAgent 阶段2 实现计划（完整流程）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的小说创作流程：大纲 → 卷纲 → 单元纲 → 章节纲 → 正文 → 审核

**Architecture:** 扩展现有大纲Agent，新增写作Agent和审核Agent，更新状态结构支持多层级纲领

**Tech Stack:** Python 3, requests, argparse, JSON

---

## Task 1: 更新状态结构

**Files:**
- Modify: `core/state.py`

- [ ] **Step 1: 更新 ProjectState 类**

新增方法支持卷、单元、章节的状态管理：

```python
# 在 ProjectState 类中添加以下方法

# === 卷纲管理 ===
def get_volumes(self) -> List[Dict[str, Any]]:
    """获取所有卷纲"""
    return self.data.get("volumes", [])

def set_volumes(self, volumes: List[Dict[str, Any]]) -> None:
    """设置所有卷纲"""
    self.data["volumes"] = volumes
    self._save()

def get_current_volume_index(self) -> int:
    """获取当前卷索引（0-based）"""
    return self.data.get("current_progress", {}).get("current_volume", 0)

def set_current_volume(self, index: int) -> None:
    """设置当前卷"""
    if "current_progress" not in self.data:
        self.data["current_progress"] = {}
    self.data["current_progress"]["current_volume"] = index
    self._save()

# === 单元纲管理 ===
def get_current_unit_index(self) -> int:
    """获取当前单元索引（0-based）"""
    return self.data.get("current_progress", {}).get("current_unit", 0)

def set_current_unit(self, index: int) -> None:
    """设置当前单元"""
    if "current_progress" not in self.data:
        self.data["current_progress"] = {}
    self.data["current_progress"]["current_unit"] = index
    self._save()

def update_volume(self, volume_index: int, volume_data: Dict[str, Any]) -> None:
    """更新指定卷的数据"""
    if "volumes" not in self.data:
        self.data["volumes"] = []
    while len(self.data["volumes"]) <= volume_index:
        self.data["volumes"].append({})
    self.data["volumes"][volume_index] = volume_data
    self._save()

# === 章节管理 ===
def get_current_chapter_index(self) -> int:
    """获取当前章节索引（0-based）"""
    return self.data.get("current_progress", {}).get("current_chapter", 0)

def set_current_chapter(self, index: int) -> None:
    """设置当前章节"""
    if "current_progress" not in self.data:
        self.data["current_progress"] = {}
    self.data["current_progress"]["current_chapter"] = index
    self._save()

def get_chapter(self, volume_index: int, unit_index: int, chapter_index: int) -> Optional[Dict[str, Any]]:
    """获取指定章节"""
    try:
        return self.data["volumes"][volume_index]["units"][unit_index]["chapters"][chapter_index]
    except (KeyError, IndexError):
        return None

def update_chapter(self, volume_index: int, unit_index: int, chapter_index: int, chapter_data: Dict[str, Any]) -> None:
    """更新指定章节"""
    if "volumes" not in self.data:
        self.data["volumes"] = []
    while len(self.data["volumes"]) <= volume_index:
        self.data["volumes"].append({"units": []})
    if "units" not in self.data["volumes"][volume_index]:
        self.data["volumes"][volume_index]["units"] = []
    while len(self.data["volumes"][volume_index]["units"]) <= unit_index:
        self.data["volumes"][volume_index]["units"].append({"chapters": []})
    if "chapters" not in self.data["volumes"][volume_index]["units"][unit_index]:
        self.data["volumes"][volume_index]["units"][unit_index]["chapters"] = []
    while len(self.data["volumes"][volume_index]["units"][unit_index]["chapters"]) <= chapter_index:
        self.data["volumes"][volume_index]["units"][unit_index]["chapters"].append({})
    self.data["volumes"][volume_index]["units"][unit_index]["chapters"][chapter_index] = chapter_data
    self._save()

# === 进度统计 ===
def get_total_words(self) -> int:
    """获取总字数"""
    return self.data.get("current_progress", {}).get("total_words", 0)

def add_words(self, count: int) -> None:
    """增加字数"""
    if "current_progress" not in self.data:
        self.data["current_progress"] = {}
    self.data["current_progress"]["total_words"] = self.get_total_words() + count
    self._save()

def get_progress_summary(self) -> Dict[str, Any]:
    """获取进度摘要"""
    return {
        "stage": self.get_stage(),
        "current_volume": self.get_current_volume_index() + 1,
        "current_unit": self.get_current_unit_index() + 1,
        "current_chapter": self.get_current_chapter_index() + 1,
        "total_words": self.get_total_words()
    }
```

- [ ] **Step 2: 提交**

```bash
git add core/state.py
git commit -m "feat: extend state with volume/unit/chapter support"
```

---

## Task 2: 添加卷纲/单元纲/章节纲 Prompt

**Files:**
- Modify: `prompts/outline.py`

- [ ] **Step 1: 添加卷纲生成 Prompt**

```python
# 卷纲生成 Prompt
GENERATE_VOLUMES_PROMPT = """你是一个专业的小说大纲策划师。根据已有的小说大纲，将其拆分为若干卷。

要求：
1. 根据故事的起承转合自然分卷
2. 每卷有明确的主题和冲突
3. 卷之间有过渡和悬念

小说大纲：
{outline}

请生成所有卷纲，每卷格式如下：
---
第X卷：[卷名]
概述：[本卷主要内容，100-200字]
核心冲突：[本卷的主要矛盾]
关键事件：[本卷的关键情节点，3-5个]
结局：[本卷如何收尾]
单元数：[数量]
---

请直接输出所有卷纲，不要其他说明。
"""

# 卷纲修改 Prompt
MODIFY_VOLUMES_PROMPT = """用户对当前卷纲提出了修改意见，请根据意见调整。

当前卷纲：
{current_volumes}

用户意见：{user_feedback}

请输出修改后的完整卷纲。
"""
```

- [ ] **Step 2: 添加单元纲生成 Prompt**

```python
# 单元纲生成 Prompt
GENERATE_UNITS_PROMPT = """你是一个小说大纲策划师。根据卷纲，将其拆分为若干单元。

要求：
1. 每单元是一个相对独立的故事单元
2. 单元之间有连贯性
3. 每单元包含若干章节

当前卷纲：
{volume_outline}

小说大纲参考：
{novel_outline}

请生成该卷的所有单元纲，每单元格式如下：
---
第X单元：[单元名]
概述：[本单元主要内容]
章节数：[数量]
---

请直接输出所有单元纲，不要其他说明。
"""

# 单元纲修改 Prompt
MODIFY_UNITS_PROMPT = """用户对当前单元纲提出了修改意见，请根据意见调整。

当前单元纲：
{current_units}

卷纲参考：
{volume_outline}

用户意见：{user_feedback}

请输出修改后的完整单元纲。
"""
```

- [ ] **Step 3: 添加章节纲生成 Prompt**

```python
# 章节纲生成 Prompt
GENERATE_CHAPTERS_PROMPT = """你是一个小说章节策划师。根据单元纲，生成每个章节的详细大纲。

要求：
1. 每章有明确的场景、人物、情节
2. 章节之间有连贯性
3. 每章有冲突和结局（或悬念）

当前单元纲：
{unit_outline}

卷纲参考：
{volume_outline}

请生成该单元的所有章节纲，每章格式如下：
---
第X章：[章节名]
场景：[发生地点]
人物：[出场人物]
情节：[本章主要情节，100-200字]
冲突：[本章的冲突/矛盾]
结局：[本章如何收尾/悬念]
预计字数：[字数]
---

请直接输出所有章节纲，不要其他说明。
"""

# 章节纲修改 Prompt
MODIFY_CHAPTERS_PROMPT = """用户对当前章节纲提出了修改意见，请根据意见调整。

当前章节纲：
{current_chapters}

单元纲参考：
{unit_outline}

用户意见：{user_feedback}

请输出修改后的完整章节纲。
"""
```

- [ ] **Step 4: 提交**

```bash
git add prompts/outline.py
git commit -m "feat: add prompts for volume/unit/chapter outline generation"
```

---

## Task 3: 创建写作 Agent Prompt

**Files:**
- Create: `prompts/writing.py`

- [ ] **Step 1: 创建写作 Prompt 文件**

```python
# prompts/writing.py
"""写作 Agent 相关的 prompt 模板"""

# 章节正文生成 Prompt
GENERATE_CHAPTER_CONTENT_PROMPT = """你是一个小说作家。根据章节大纲，写出完整的章节正文。

要求：
1. 严格遵循章节纲的情节发展
2. 保持人物性格一致
3. 文笔流畅，有代入感
4. 避免AI生成的常见问题：
   - 不要过于书面化
   - 不要过度解释
   - 要有细节描写
   - 要有情感张力

章节大纲：
{chapter_outline}

前文参考（上一章结尾，如有）：
{previous_chapter_ending}

小说设定：
题材：{genre}
主角：{main_characters}
世界观：{world_setting}
风格：{style_preference}

请直接输出章节正文，不要其他说明。
"""

# 章节重写 Prompt
REWRITE_CHAPTER_CONTENT_PROMPT = """你是一个小说作家。根据审核反馈，重写章节正文。

原章节大纲：
{chapter_outline}

审核反馈：
{review_feedback}

问题章节：
{original_content}

请根据审核反馈重写，注意：
1. 解决审核指出的问题
2. 保持情节连贯
3. 不要引入新问题

请直接输出重写后的章节正文。
"""
```

- [ ] **Step 2: 提交**

```bash
git add prompts/writing.py
git commit -m "feat: add writing agent prompts"
```

---

## Task 4: 创建审核 Agent Prompt

**Files:**
- Create: `prompts/review.py`

- [ ] **Step 1: 创建审核 Prompt 文件**

```python
# prompts/review.py
"""审核 Agent 相关的 prompt 模板"""

# 章节审核 Prompt
REVIEW_CHAPTER_PROMPT = """你是一个专业的小说编辑。审核章节正文的质量。

审核维度：
1. 一致性：人物名、地名、前后情节是否一致
2. 质量：文笔、节奏、逻辑是否合理
3. AI味：是否有明显AI生成痕迹（过于书面化、重复表达、缺乏细节）
4. 规则：是否符合用户设定的风格

章节大纲：
{chapter_outline}

章节正文：
{chapter_content}

小说设定：
题材：{genre}
主角：{main_characters}
风格：{style_preference}

请严格审核，回复格式如下：
---
【审核结果】通过/不通过
【问题列表】（如果没有问题则写"无"）
1. [问题描述]
2. ...
【修改建议】（如果没有则写"无"）
[具体建议]
---

注意：只要有一个维度不达标，就应判定为不通过。
"""
```

- [ ] **Step 2: 提交**

```bash
git add prompts/review.py
git commit -m "feat: add review agent prompts"
```

---

## Task 5: 创建写作 Agent

**Files:**
- Create: `agents/writing_agent.py`

- [ ] **Step 1: 创建写作 Agent**

```python
# agents/writing_agent.py
"""写作 Agent 实现"""

from typing import Dict, Any, Optional
from agents.base import BaseAgent
from core.state import ProjectState
from prompts.writing import GENERATE_CHAPTER_CONTENT_PROMPT, REWRITE_CHAPTER_CONTENT_PROMPT


class WritingAgent(BaseAgent):
    """写作 Agent：生成章节正文"""

    def __init__(self, project_state: ProjectState):
        self.project_state = project_state
        super().__init__(
            name="写作Agent",
            system_prompt="你是一个专业的小说作家，擅长写出引人入胜的故事。"
        )

    def generate_chapter_content(
        self,
        chapter_outline: Dict[str, Any],
        previous_chapter_ending: str = ""
    ) -> str:
        """
        生成章节正文

        Args:
            chapter_outline: 章节大纲
            previous_chapter_ending: 上一章结尾内容

        Returns:
            章节正文
        """
        collected_info = self.project_state.get_collected_info()

        prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
            chapter_outline=self._format_chapter_outline(chapter_outline),
            previous_chapter_ending=previous_chapter_ending or "（这是第一章，无前文）",
            genre=collected_info.get("genre", "未指定"),
            main_characters=collected_info.get("main_characters", "未指定"),
            world_setting=collected_info.get("world_setting", "未指定"),
            style_preference=collected_info.get("style_preference", "未指定")
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说作家。",
            [{"role": "user", "content": prompt}]
        )

        return response

    def rewrite_chapter_content(
        self,
        chapter_outline: Dict[str, Any],
        original_content: str,
        review_feedback: str
    ) -> str:
        """
        根据审核反馈重写章节

        Args:
            chapter_outline: 章节大纲
            original_content: 原始内容
            review_feedback: 审核反馈

        Returns:
            重写后的章节正文
        """
        prompt = REWRITE_CHAPTER_CONTENT_PROMPT.format(
            chapter_outline=self._format_chapter_outline(chapter_outline),
            original_content=original_content,
            review_feedback=review_feedback
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说作家。",
            [{"role": "user", "content": prompt}]
        )

        return response

    def _format_chapter_outline(self, chapter: Dict[str, Any]) -> str:
        """格式化章节大纲"""
        lines = []
        lines.append(f"章节：{chapter.get('title', '未命名')}")
        lines.append(f"场景：{chapter.get('scene', '未指定')}")
        lines.append(f"人物：{chapter.get('characters', '未指定')}")
        lines.append(f"情节：{chapter.get('plot', '未指定')}")
        lines.append(f"冲突：{chapter.get('conflict', '未指定')}")
        lines.append(f"结局：{chapter.get('ending', '未指定')}")
        return "\n".join(lines)
```

- [ ] **Step 2: 提交**

```bash
git add agents/writing_agent.py
git commit -m "feat: add writing agent implementation"
```

---

## Task 6: 创建审核 Agent

**Files:**
- Create: `agents/review_agent.py`

- [ ] **Step 1: 创建审核 Agent**

```python
# agents/review_agent.py
"""审核 Agent 实现"""

from typing import Dict, Any, Tuple
from agents.base import BaseAgent
from core.state import ProjectState
from prompts.review import REVIEW_CHAPTER_PROMPT


class ReviewAgent(BaseAgent):
    """审核 Agent：检查章节质量"""

    def __init__(self, project_state: ProjectState):
        self.project_state = project_state
        super().__init__(
            name="审核Agent",
            system_prompt="你是一个专业的小说编辑，擅长发现文稿中的问题。"
        )

    def review_chapter(
        self,
        chapter_outline: Dict[str, Any],
        chapter_content: str
    ) -> Tuple[bool, str]:
        """
        审核章节

        Args:
            chapter_outline: 章节大纲
            chapter_content: 章节正文

        Returns:
            (是否通过, 审核结果详情)
        """
        collected_info = self.project_state.get_collected_info()

        prompt = REVIEW_CHAPTER_PROMPT.format(
            chapter_outline=self._format_chapter_outline(chapter_outline),
            chapter_content=chapter_content,
            genre=collected_info.get("genre", "未指定"),
            main_characters=collected_info.get("main_characters", "未指定"),
            style_preference=collected_info.get("style_preference", "未指定")
        )

        response = self.llm_client.chat_with_system(
            "你是一个专业的小说编辑。",
            [{"role": "user", "content": prompt}]
        )

        # 解析审核结果
        passed = "【审核结果】通过" in response

        return passed, response

    def _format_chapter_outline(self, chapter: Dict[str, Any]) -> str:
        """格式化章节大纲"""
        lines = []
        lines.append(f"章节：{chapter.get('title', '未命名')}")
        lines.append(f"情节：{chapter.get('plot', '未指定')}")
        return "\n".join(lines)
```

- [ ] **Step 2: 提交**

```bash
git add agents/review_agent.py
git commit -m "feat: add review agent implementation"
```

---

## Task 7: 扩展大纲 Agent（核心任务）

**Files:**
- Modify: `agents/outline_agent.py`

- [ ] **Step 1: 添加卷纲生成方法**

在 OutlineAgent 类中添加：

```python
def _generate_volumes(self) -> str:
    """生成所有卷纲"""
    outline = self.project_state.get_outline()
    if not outline:
        return "请先生成大纲。"

    prompt = GENERATE_VOLUMES_PROMPT.format(
        outline=outline.get("raw", "")
    )

    response = self.llm_client.chat_with_system(
        "你是一个专业的小说大纲策划师。",
        [{"role": "user", "content": prompt}]
    )

    # 解析卷纲
    volumes = self._parse_volumes(response)
    self.project_state.set_volumes(volumes)
    self.project_state.set_stage("volumes_confirming")

    return f"已生成 {len(volumes)} 卷纲，请查看并提出修改意见，或回复'确认卷纲'继续：\n\n{response}"

def _parse_volumes(self, text: str) -> List[Dict[str, Any]]:
    """解析卷纲文本为结构化数据"""
    volumes = []
    # 简单解析：按 "---" 或 "第X卷" 分割
    import re
    pattern = r'第(\d+)卷[：:]\s*(.+?)(?=第\d+卷|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for i, (num, content) in enumerate(matches):
        volumes.append({
            "volume_id": int(num),
            "raw": f"第{num}卷：{content.strip()}",
            "confirmed": False,
            "units": []
        })
    
    if not volumes:
        # 备用解析：按段落分割
        volumes.append({"volume_id": 1, "raw": text, "confirmed": False, "units": []})
    
    return volumes
```

- [ ] **Step 2: 添加单元纲生成方法**

```python
def _generate_units_for_volume(self, volume_index: int) -> str:
    """为指定卷生成单元纲"""
    volumes = self.project_state.get_volumes()
    if volume_index >= len(volumes):
        return "卷索引超出范围"

    volume = volumes[volume_index]
    outline = self.project_state.get_outline()

    prompt = GENERATE_UNITS_PROMPT.format(
        volume_outline=volume.get("raw", ""),
        novel_outline=outline.get("raw", "") if outline else ""
    )

    response = self.llm_client.chat_with_system(
        "你是一个小说大纲策划师。",
        [{"role": "user", "content": prompt}]
    )

    # 解析单元纲
    units = self._parse_units(response)
    volume["units"] = units
    volume["units_confirmed"] = False
    self.project_state.update_volume(volume_index, volume)
    self.project_state.set_stage("units_confirming")

    return f"已生成第{volume_index + 1}卷的 {len(units)} 个单元纲，请查看并提出修改意见，或回复'确认单元纲'继续：\n\n{response}"

def _parse_units(self, text: str) -> List[Dict[str, Any]]:
    """解析单元纲文本为结构化数据"""
    units = []
    import re
    pattern = r'第(\d+)单元[：:]\s*(.+?)(?=第\d+单元|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for num, content in matches:
        units.append({
            "unit_id": int(num),
            "raw": f"第{num}单元：{content.strip()}",
            "confirmed": False,
            "chapters": []
        })
    
    if not units:
        units.append({"unit_id": 1, "raw": text, "confirmed": False, "chapters": []})
    
    return units
```

- [ ] **Step 3: 添加章节纲生成方法**

```python
def _generate_chapters_for_unit(self, volume_index: int, unit_index: int) -> str:
    """为指定单元生成章节纲"""
    volumes = self.project_state.get_volumes()
    if volume_index >= len(volumes):
        return "卷索引超出范围"
    
    volume = volumes[volume_index]
    if unit_index >= len(volume.get("units", [])):
        return "单元索引超出范围"
    
    unit = volume["units"][unit_index]

    prompt = GENERATE_CHAPTERS_PROMPT.format(
        unit_outline=unit.get("raw", ""),
        volume_outline=volume.get("raw", "")
    )

    response = self.llm_client.chat_with_system(
        "你是一个小说章节策划师。",
        [{"role": "user", "content": prompt}]
    )

    # 解析章节纲
    chapters = self._parse_chapters(response)
    unit["chapters"] = chapters
    unit["chapters_confirmed"] = False
    volume["units"][unit_index] = unit
    self.project_state.update_volume(volume_index, volume)
    self.project_state.set_stage("chapters_outline_confirming")

    return f"已生成第{unit_index + 1}单元的 {len(chapters)} 个章节纲，请查看并提出修改意见，或回复'确认章节纲'开始写作：\n\n{response}"

def _parse_chapters(self, text: str) -> List[Dict[str, Any]]:
    """解析章节纲文本为结构化数据"""
    chapters = []
    import re
    pattern = r'第(\d+)章[：:]\s*(.+?)(?=第\d+章|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for num, content in matches:
        chapters.append({
            "chapter_id": int(num),
            "raw": f"第{num}章：{content.strip()}",
            "title": self._extract_title(content),
            "confirmed": False,
            "content": None,
            "review_passed": False
        })
    
    if not chapters:
        chapters.append({"chapter_id": 1, "raw": text, "title": "第一章", "confirmed": False, "content": None, "review_passed": False})
    
    return chapters

def _extract_title(self, content: str) -> str:
    """从章节内容中提取标题"""
    import re
    match = re.search(r'章节名[：:]\s*(.+)', content)
    if match:
        return match.group(1).strip()
    return "未命名章节"
```

- [ ] **Step 4: 更新 process_user_input 方法**

添加新的阶段处理：

```python
def process_user_input(self, user_input: str) -> str:
    """处理用户输入"""
    stage = self.project_state.get_stage()

    if stage == "collecting_info":
        return self._handle_collecting_info(user_input)
    elif stage == "generating_outline":
        return self._handle_generating_outline(user_input)
    elif stage == "outline_confirming":
        return self._handle_outline_confirming(user_input)
    elif stage == "volumes_generating":
        return self._generate_volumes()
    elif stage == "volumes_confirming":
        return self._handle_volumes_confirming(user_input)
    elif stage == "units_generating":
        vol_idx = self.project_state.get_current_volume_index()
        return self._generate_units_for_volume(vol_idx)
    elif stage == "units_confirming":
        return self._handle_units_confirming(user_input)
    elif stage == "chapters_outline_generating":
        vol_idx = self.project_state.get_current_volume_index()
        unit_idx = self.project_state.get_current_unit_index()
        return self._generate_chapters_for_unit(vol_idx, unit_idx)
    elif stage == "chapters_outline_confirming":
        return self._handle_chapters_outline_confirming(user_input)
    else:
        return "当前阶段无法处理输入。"
```

- [ ] **Step 5: 添加确认处理方法**

```python
def _handle_volumes_confirming(self, user_input: str) -> str:
    """处理卷纲确认"""
    if "确认卷纲" in user_input or "确认" in user_input:
        # 标记所有卷为已确认
        volumes = self.project_state.get_volumes()
        for v in volumes:
            v["confirmed"] = True
        self.project_state.set_volumes(volumes)
        
        # 开始第一卷的单元纲生成
        self.project_state.set_current_volume(0)
        self.project_state.set_stage("units_generating")
        return "卷纲已确认！开始生成第一卷的单元纲...\n\n" + self._generate_units_for_volume(0)
    
    # 修改卷纲
    volumes = self.project_state.get_volumes()
    if volumes:
        response = self.llm_client.chat_with_system(
            MODIFY_VOLUMES_PROMPT.format(
                current_volumes="\n".join([v.get("raw", "") for v in volumes]),
                user_feedback=user_input
            ),
            [{"role": "user", "content": "请根据我的意见修改卷纲。"}]
        )
        
        new_volumes = self._parse_volumes(response)
        self.project_state.set_volumes(new_volumes)
        
        return f"已修改卷纲，请继续提出意见或回复'确认卷纲'继续：\n\n{response}"
    
    return "当前没有卷纲，请重新生成。"

def _handle_units_confirming(self, user_input: str) -> str:
    """处理单元纲确认"""
    if "确认单元纲" in user_input or "确认" in user_input:
        vol_idx = self.project_state.get_current_volume_index()
        volumes = self.project_state.get_volumes()
        if vol_idx < len(volumes):
            for u in volumes[vol_idx].get("units", []):
                u["confirmed"] = True
            self.project_state.update_volume(vol_idx, volumes[vol_idx])
        
        # 开始章节纲生成
        self.project_state.set_current_unit(0)
        self.project_state.set_stage("chapters_outline_generating")
        return "单元纲已确认！开始生成第一个单元的章节纲...\n\n" + self._generate_chapters_for_unit(vol_idx, 0)
    
    # 修改单元纲
    vol_idx = self.project_state.get_current_volume_index()
    volumes = self.project_state.get_volumes()
    if vol_idx < len(volumes) and volumes[vol_idx].get("units"):
        units = volumes[vol_idx]["units"]
        response = self.llm_client.chat_with_system(
            MODIFY_UNITS_PROMPT.format(
                current_units="\n".join([u.get("raw", "") for u in units]),
                volume_outline=volumes[vol_idx].get("raw", ""),
                user_feedback=user_input
            ),
            [{"role": "user", "content": "请根据我的意见修改单元纲。"}]
        )
        
        new_units = self._parse_units(response)
        volumes[vol_idx]["units"] = new_units
        self.project_state.update_volume(vol_idx, volumes[vol_idx])
        
        return f"已修改单元纲，请继续提出意见或回复'确认单元纲'继续：\n\n{response}"
    
    return "当前没有单元纲，请重新生成。"

def _handle_chapters_outline_confirming(self, user_input: str) -> str:
    """处理章节纲确认"""
    if "确认章节纲" in user_input or "确认" in user_input:
        vol_idx = self.project_state.get_current_volume_index()
        unit_idx = self.project_state.get_current_unit_index()
        volumes = self.project_state.get_volumes()
        
        if vol_idx < len(volumes) and unit_idx < len(volumes[vol_idx].get("units", [])):
            for c in volumes[vol_idx]["units"][unit_idx].get("chapters", []):
                c["confirmed"] = True
            self.project_state.update_volume(vol_idx, volumes[vol_idx])
        
        self.project_state.set_current_chapter(0)
        self.project_state.set_stage("chapter_writing")
        return "章节纲已确认！准备开始写作，请回复'开始写作'生成第一章正文。"
    
    # 修改章节纲
    vol_idx = self.project_state.get_current_volume_index()
    unit_idx = self.project_state.get_current_unit_index()
    volumes = self.project_state.get_volumes()
    
    if vol_idx < len(volumes) and unit_idx < len(volumes[vol_idx].get("units", [])):
        chapters = volumes[vol_idx]["units"][unit_idx].get("chapters", [])
        response = self.llm_client.chat_with_system(
            MODIFY_CHAPTERS_PROMPT.format(
                current_chapters="\n".join([c.get("raw", "") for c in chapters]),
                unit_outline=volumes[vol_idx]["units"][unit_idx].get("raw", ""),
                user_feedback=user_input
            ),
            [{"role": "user", "content": "请根据我的意见修改章节纲。"}]
        )
        
        new_chapters = self._parse_chapters(response)
        volumes[vol_idx]["units"][unit_idx]["chapters"] = new_chapters
        self.project_state.update_volume(vol_idx, volumes[vol_idx])
        
        return f"已修改章节纲，请继续提出意见或回复'确认章节纲'开始写作：\n\n{response}"
    
    return "当前没有章节纲，请重新生成。"
```

- [ ] **Step 6: 更新大纲确认后的流程**

修改 `_handle_outline_confirming` 方法：

```python
def _handle_outline_confirming(self, user_input: str) -> str:
    """处理大纲确认阶段的用户输入"""
    if "确认大纲" in user_input or "确认" in user_input or "满意" in user_input:
        self.project_state.confirm_outline()
        self.project_state.set_stage("volumes_generating")
        return "大纲已确认！开始生成卷纲...\n\n" + self._generate_volumes()

    # 用户提出修改意见
    current_outline = self.project_state.get_outline()
    if current_outline:
        response = self.llm_client.chat_with_system(
            MODIFY_OUTLINE_SYSTEM_PROMPT.format(
                current_outline=current_outline.get("raw", ""),
                user_feedback=user_input
            ),
            [{"role": "user", "content": "请根据我的意见修改大纲。"}]
        )

        self.project_state.set_outline({"raw": response})
        self.project_state.add_conversation_message("user", user_input)
        self.project_state.add_conversation_message("assistant", response)

        return f"已修改大纲，请继续提出意见或回复'确认大纲'继续：\n\n{response}"

    return "当前没有大纲，请重新生成。"
```

- [ ] **Step 7: 添加必要的导入**

在文件顶部添加：

```python
from prompts.outline import (
    COLLECT_INFO_SYSTEM_PROMPT,
    CHECK_INFO_PROMPT,
    GENERATE_OUTLINE_SYSTEM_PROMPT,
    GENERATE_OUTLINE_USER_PROMPT,
    MODIFY_OUTLINE_SYSTEM_PROMPT,
    GENERATE_VOLUMES_PROMPT,
    MODIFY_VOLUMES_PROMPT,
    GENERATE_UNITS_PROMPT,
    MODIFY_UNITS_PROMPT,
    GENERATE_CHAPTERS_PROMPT,
    MODIFY_CHAPTERS_PROMPT
)
from typing import List
```

- [ ] **Step 8: 提交**

```bash
git add agents/outline_agent.py
git commit -m "feat: extend outline agent with volume/unit/chapter outline generation"
```

---

## Task 8: 更新 CLI 支持完整流程

**Files:**
- Modify: `cli.py`

- [ ] **Step 1: 导入新 Agent**

```python
from agents.outline_agent import OutlineAgent
from agents.writing_agent import WritingAgent
from agents.review_agent import ReviewAgent
```

- [ ] **Step 2: 更新 conversation_loop**

```python
def conversation_loop(agent: OutlineAgent, state: ProjectState):
    """对话循环"""
    print("(输入 'quit' 退出，'status' 查看状态，'progress' 查看进度)\n")

    writing_agent = None
    review_agent = None

    while True:
        try:
            stage = state.get_stage()
            
            # 章节写作阶段需要特殊处理
            if stage == "chapter_writing":
                if writing_agent is None:
                    writing_agent = WritingAgent(state)
                    review_agent = ReviewAgent(state)
                
                result = handle_chapter_writing(state, writing_agent, review_agent)
                if result == "next_chapter":
                    continue
                elif result == "done":
                    break
                else:
                    user_input = input("你: ").strip()
                    if user_input == "quit":
                        print("已保存进度，下次使用 continue 命令继续")
                        break
                    continue
            
            # 其他阶段正常对话
            user_input = input("你: ").strip()

            if not user_input:
                continue

            if user_input == "quit":
                print("已保存进度，下次使用 continue 命令继续")
                break

            if user_input == "status":
                cmd_status(type('Args', (), {'name': state.project_name})())
                continue
            
            if user_input == "progress":
                progress = state.get_progress_summary()
                print(f"\n当前进度：")
                print(f"  阶段：{progress['stage']}")
                print(f"  当前卷：第{progress['current_volume']}卷")
                print(f"  当前单元：第{progress['current_unit']}单元")
                print(f"  当前章节：第{progress['current_chapter']}章")
                print(f"  总字数：{progress['total_words']}\n")
                continue

            response = agent.process_user_input(user_input)
            print(f"\n[{agent.name}] {response}\n")

            # 检查是否进入写作阶段
            if state.get_stage() == "chapter_writing":
                writing_agent = WritingAgent(state)
                review_agent = ReviewAgent(state)

        except KeyboardInterrupt:
            print("\n已保存进度，下次使用 continue 命令继续")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            print("已保存进度，请检查后继续")


def handle_chapter_writing(state: ProjectState, writing_agent: WritingAgent, review_agent: ReviewAgent) -> str:
    """处理章节写作流程"""
    vol_idx = state.get_current_volume_index()
    unit_idx = state.get_current_unit_index()
    chapter_idx = state.get_current_chapter_index()
    
    # 获取当前章节
    chapter = state.get_chapter(vol_idx, unit_idx, chapter_idx)
    if not chapter:
        return "error"
    
    # 如果章节已完成，检查是否需要进入下一章
    if chapter.get("review_passed"):
        return move_to_next_chapter(state, vol_idx, unit_idx, chapter_idx)
    
    # 如果章节内容已生成但未审核
    if chapter.get("content") and not chapter.get("review_passed"):
        print(f"\n[系统] 第{chapter_idx + 1}章《{chapter.get('title', '')}》已有内容，正在审核...")
        passed, review_result = review_agent.review_chapter(chapter, chapter["content"])
        print(f"\n[审核Agent]\n{review_result}\n")
        
        if passed:
            chapter["review_passed"] = True
            state.update_chapter(vol_idx, unit_idx, chapter_idx, chapter)
            word_count = len(chapter["content"])
            state.add_words(word_count)
            print(f"[系统] 审核通过！本章 {word_count} 字。")
            return move_to_next_chapter(state, vol_idx, unit_idx, chapter_idx)
        else:
            print("[系统] 审核未通过，正在重写...")
            new_content = writing_agent.rewrite_chapter_content(
                chapter, chapter["content"], review_result
            )
            chapter["content"] = new_content
            state.update_chapter(vol_idx, unit_idx, chapter_idx, chapter)
            print(f"\n[写作Agent] 已重写第{chapter_idx + 1}章：\n\n{new_content[:500]}...\n")
            print("(输入 '继续' 进行审核，或 'quit' 退出)")
            return "rewrite"
    
    # 生成新章节
    print(f"\n[系统] 开始生成第{chapter_idx + 1}章《{chapter.get('title', '')}》...")
    
    # 获取上一章结尾
    prev_ending = ""
    if chapter_idx > 0:
        prev_chapter = state.get_chapter(vol_idx, unit_idx, chapter_idx - 1)
        if prev_chapter and prev_chapter.get("content"):
            prev_ending = prev_chapter["content"][-500:]  # 最后500字
    
    content = writing_agent.generate_chapter_content(chapter, prev_ending)
    chapter["content"] = content
    state.update_chapter(vol_idx, unit_idx, chapter_idx, chapter)
    
    print(f"\n[写作Agent] 第{chapter_idx + 1}章《{chapter.get('title', '')}》已生成：\n\n{content[:800]}...\n")
    print("(输入 '审核' 进行审核，或提出修改意见，或 'quit' 退出)")
    
    return "waiting"


def move_to_next_chapter(state: ProjectState, vol_idx: int, unit_idx: int, chapter_idx: int) -> str:
    """移动到下一章"""
    volumes = state.get_volumes()
    current_unit = volumes[vol_idx]["units"][unit_idx]
    chapters = current_unit.get("chapters", [])
    
    # 还有下一章
    if chapter_idx + 1 < len(chapters):
        state.set_current_chapter(chapter_idx + 1)
        print(f"\n[系统] 进入第{chapter_idx + 2}章...")
        return "next_chapter"
    
    # 当前单元完成
    print(f"\n[系统] 第{unit_idx + 1}单元全部完成！")
    
    # 检查是否还有下一单元
    if unit_idx + 1 < len(volumes[vol_idx]["units"]):
        state.set_current_unit(unit_idx + 1)
        state.set_current_chapter(0)
        print(f"[系统] 进入第{unit_idx + 2}单元...")
        return "next_chapter"
    
    # 当前卷完成
    print(f"\n[系统] 第{vol_idx + 1}卷全部完成！")
    
    # 检查是否还有下一卷
    if vol_idx + 1 < len(volumes):
        state.set_current_volume(vol_idx + 1)
        state.set_current_unit(0)
        state.set_current_chapter(0)
        # 需要生成下一卷的单元纲
        state.set_stage("units_generating")
        print(f"[系统] 进入第{vol_idx + 2}卷，请回复'继续'生成单元纲...")
        return "next_volume"
    
    # 全部完成
    state.set_stage("completed")
    total_words = state.get_total_words()
    print(f"\n[系统] 🎉 恭喜！小说全部完成！共 {total_words} 字。")
    return "done"
```

- [ ] **Step 3: 提交**

```bash
git add cli.py
git commit -m "feat: update CLI with full writing workflow"
```

---

## Task 9: 验证运行

- [ ] **Step 1: 测试基本导入**

```bash
cd /root/novelagent
python -c "from agents.writing_agent import WritingAgent; from agents.review_agent import ReviewAgent; print('All imports OK')"
```

- [ ] **Step 2: 测试状态扩展**

```bash
python -c "
from core.state import ProjectState
s = ProjectState('test_project')
s.set_volumes([{'volume_id': 1, 'title': 'Test'}])
print('Volumes:', s.get_volumes())
print('State extended OK')
"
```

- [ ] **Step 3: 清理测试数据**

```bash
rm -f data/projects/test_project.json
```

---

## Task 10: 最终提交

- [ ] **Step 1: 最终提交**

```bash
git add .
git commit -m "feat: complete phase 2 - full novel creation workflow"
```

- [ ] **Step 2: 创建版本标签**

```bash
git tag v0.2.0-phase2 -m "Phase 2: Complete workflow with volumes/units/chapters"
```

---

## 验收标准

1. 大纲确认后能生成所有卷纲
2. 用户可修改卷纲并确认
3. 每卷能生成单元纲
4. 每单元能生成章节纲
5. 写作Agent能生成章节正文
6. 审核Agent能检查章节质量
7. 能根据审核反馈重写
8. 完整流程能跑通