"""章节品控服务 — 审核、重写、审核后重写

深模块：调用方传入 chapter_number、LLM 实例和 context_window，
内部完成 KB 读取、上下文组装、LLM 调用、结果解析、DB 写入。

替代旧版 review_utils / rewrite_utils / _build_state_for_review 的隐式 dict 链路。
"""

import json
import re
import logging
from typing import Optional

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.context_strategy import get_context_strategy
from app.agents.token_budget import (
    estimate_tokens,
    calculate_context_budget,
    DEFAULT_CONTEXT_WINDOW,
)
from app.agents.constants import NODE_TEMPERATURES
from app.agents.nodes_utils import safe_format

logger = logging.getLogger(__name__)


# ========== 内置 Prompt 模板 ==========

_REVIEW_SYSTEM_PROMPT = """你是独立审查员，对小说章节进行 6 维度质量审核。

## 章节大纲
{chapter_outline}

## 主要角色
{main_characters}

## 世界观
{world_setting}

{previous_context}"""

_REVIEW_USER_PROMPT = """请审核以下章节内容。

审核严格度：{strictness}
类型：{genre}
风格偏好：{style_preference}

## 章节正文
{chapter_content}

## 输出格式

请输出 JSON：
```json
{{
  "passed": true/false,
  "scores": {{
    "plot_consistency": 1-10,
    "character_consistency": 1-10,
    "writing_quality": 1-10,
    "emotional_tension": 1-10,
    "ai_flavor": 1-10,
    "outline_deviation": 1-10
  }},
  "issues": [
    {{"type": "问题类型", "description": "具体描述", "suggestion": "修改建议"}}
  ],
  "suggestions": "整体改进建议"
}}
```

评分说明：
- plot_consistency: 情节是否与大纲一致，有无逻辑矛盾
- character_consistency: 角色行为是否符合设定，对话是否符合风格
- writing_quality: 文笔质量、语言流畅度
- emotional_tension: 情感张力是否到位
- ai_flavor: AI 味程度（越高越差，1=无AI味，10=严重AI味）
- outline_deviation: 大纲偏离度（越高越差，1=严格遵循，10=严重偏离）"""

_REWRITE_SYSTEM_PROMPT = """你是资深小说编辑，根据审核反馈重写章节。

## 章节大纲
{chapter_outline}

## 主要角色
{main_characters}

## 世界观
{world_setting}

{previous_context}"""

_REWRITE_USER_PROMPT = """请根据审核反馈重写以下章节。

类型：{genre}

## 审核反馈
{review_feedback}

## 原文
{original_content}

要求：
- 针对审核反馈中的问题逐一改进
- 保持情节方向不变，只改进表达和一致性
- 直接输出重写后的完整章节，不要输出其他说明"""


# ========== 结果解析 ==========

def _parse_review_result(response: str) -> dict:
    """解析审核 LLM 输出（优先 JSON，回退旧格式正则）"""
    # 策略 1：markdown 代码块中提取 JSON
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1))
            if "passed" in data:
                return _extract_review_fields(data)
        except json.JSONDecodeError:
            pass

    # 策略 2：直接匹配花括号
    brace_start = response.find('{')
    while brace_start != -1:
        depth = 0
        for i in range(brace_start, len(response)):
            if response[i] == '{':
                depth += 1
            elif response[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = response[brace_start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if "passed" in data:
                            return _extract_review_fields(data)
                    except json.JSONDecodeError:
                        pass
                    break
        brace_start = response.find('{', brace_start + 1)

    # 策略 3：旧格式正则
    return _parse_review_result_legacy(response)


def _extract_review_fields(data: dict) -> dict:
    """从 JSON 解析结果中提取审核字段"""
    suggestions = (
        data.get("suggestions")
        or data.get("feedback")
        or data.get("改进建议")
        or ""
    )

    raw_issues = data.get("issues") or data.get("problems") or []
    normalized_issues = []
    for issue in raw_issues:
        if isinstance(issue, str):
            normalized_issues.append({"type": "", "suggestion": "", "description": issue})
            continue
        normalized = {
            "type": issue.get("type", ""),
            "suggestion": issue.get("suggestion", ""),
        }
        if "paragraph_start" in issue:
            normalized["paragraph_start"] = issue["paragraph_start"]
        if "location" in issue:
            normalized["location"] = issue["location"]
        if "description" in issue:
            normalized["description"] = issue["description"]
        normalized_issues.append(normalized)

    return {
        "passed": bool(data.get("passed", False)),
        "scores": data.get("scores", {}),
        "issues": normalized_issues,
        "suggestions": suggestions,
    }


def _parse_review_result_legacy(response: str) -> dict:
    """旧格式回退解析"""
    result = {"passed": False, "scores": {}, "issues": [], "suggestions": ""}

    result["passed"] = "【审核结果】通过" in response

    score_patterns = {
        "plot_consistency": r"情节一致性[：:]\s*(\d+)/10",
        "character_consistency": r"人物一致性[：:]\s*(\d+)/10",
        "writing_quality": r"文笔质量[：:]\s*(\d+)/10",
        "emotional_tension": r"情感张力[：:]\s*(\d+)/10",
        "ai_flavor": r"AI味程度[：:]\s*(\d+)/10",
        "outline_deviation": r"大纲偏离度[：:]\s*(\d+)/10",
    }

    for key, pattern in score_patterns.items():
        match = re.search(pattern, response)
        if match:
            result["scores"][key] = int(match.group(1))

    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [
            i.strip()
            for i in re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|无|$)", issues_text, re.DOTALL)
            if i.strip()
        ]
        if issues_text.strip() != "无":
            result["issues"] = issues

    suggestions_match = re.search(r"【修改建议】(.+?)(?=---|$)", response, re.DOTALL)
    if suggestions_match:
        suggestions = suggestions_match.group(1).strip()
        if suggestions != "无":
            result["suggestions"] = suggestions

    return result


def _check_review_passed(review_result: dict) -> bool:
    """检查审核是否通过"""
    scores = review_result.get("scores", {})

    for key in [
        "plot_consistency",
        "character_consistency",
        "writing_quality",
        "emotional_tension",
    ]:
        if scores.get(key, 0) < 6:
            return False

    if scores.get("ai_flavor", 10) > 3:
        return False

    if scores.get("outline_deviation", 0) > 4:
        return False

    return True


def _clean_chapter_content(content: str) -> str:
    """清理章节内容，移除 LLM 可能添加的尾部数字"""
    if not content:
        return content

    result = content.strip()
    pattern = re.compile(r'\n+\s*\d+\s*$')
    while pattern.search(result):
        result = pattern.sub('', result)
    return result


# ========== 上下文格式化 ==========

def _format_characters(characters: list[dict]) -> str:
    """格式化角色信息为 prompt 文本"""
    if not characters:
        return "未指定"

    parts = []
    for c in characters:
        name = c.get("name", "")
        role = c.get("role", "")
        motivation = c.get("core_motivation", "")
        personality = c.get("personality", "")
        speech = c.get("speech_style", "")
        line = f"- {name}（{role}）"
        if motivation:
            line += f"：核心动机 {motivation}"
        if personality:
            line += f"，{personality[:100]}"
        if speech:
            line += f"，说话风格：{speech[:60]}"
        parts.append(line)
    return "\n".join(parts)


def _format_world_setting(ws: dict) -> str:
    """格式化世界观为 prompt 文本"""
    if not ws:
        return "未指定"

    parts = []
    if ws.get("core_concept"):
        parts.append(f"核心理念：{ws['core_concept']}")
    red = (ws.get("tiered_settings") or {}).get("red", [])
    if red:
        parts.append(f"不可违反设定：{'；'.join(red[:5])}")
    locs = ws.get("key_locations", [])
    if locs:
        parts.append(f"关键地点：{'；'.join(locs[:5])}")
    return "\n".join(parts) if parts else "未指定"


def _format_chapter_outline(co: dict) -> str:
    """格式化章节大纲为 prompt 文本"""
    parts = [f"第{co.get('chapter_number', '')}章：{co.get('title', '')}"]
    for field, label in [("scene", "场景"), ("characters", "出场人物"), ("plot", "情节要点"),
                         ("conflict", "冲突"), ("turning_point", "转折"), ("hook", "悬念钩子"),
                         ("ending", "结尾"), ("transition", "过渡"),
                         ("opening_state", "开场状态"), ("emotional_arc", "情绪弧线"),
                         ("pacing_note", "节奏标注")]:
        val = co.get(field)
        if val:
            parts.append(f"  {label}：{val}")
    scenes = co.get("key_scenes")
    if scenes and isinstance(scenes, list):
        for s in scenes:
            seq = s.get("seq", "")
            desc = s.get("desc", "")
            mood = s.get("mood", "")
            parts.append(f"  场景{seq}：{desc}（{mood}）")
    return "\n".join(parts)


# ========== 主服务类 ==========

class ChapterQuality:
    """章节品控 — 审核、重写、审核后重写

    深模块：调用方只需知道 chapter_number，
    内部完成 KB 读取、上下文组装、LLM 调用、结果解析、DB 写入。
    """

    def __init__(self, project_id: int, llm, context_window: int = DEFAULT_CONTEXT_WINDOW):
        self.project_id = project_id
        self.kb = KnowledgeBaseService(project_id)
        self.llm = llm
        self.context_window = context_window

    async def review(self, chapter_number: int, strictness: str = "standard") -> dict:
        """审核章节质量

        Returns:
            {
                "chapter_number": int,
                "passed": bool,
                "scores": dict,
                "issues": list,
                "suggestions": str,
                "message": str,
            }
        """
        # 1. 读 KB
        chapter = self.kb.chapters.get_by_number(chapter_number)
        if not chapter or not chapter.get("content"):
            return {"error": f"第{chapter_number}章内容不存在，请先生成"}

        co = self.kb.outlines.get_chapter_outline(chapter_number)
        if not co:
            return {"error": f"第{chapter_number}章大纲不存在"}

        # 2. 构建消息
        messages = self._build_review_messages(chapter["content"], co, strictness)

        # 3. 调 LLM
        try:
            response = await self.llm.chat(
                messages, temperature=NODE_TEMPERATURES["review"], max_tokens=8192
            )
            review_result = _parse_review_result(response)
            review_result["raw_response"] = response
            passed = _check_review_passed(review_result)
        except Exception as e:
            return {"error": f"审核 LLM 调用失败: {e}"}

        # 4. 存 DB
        try:
            self.kb.chapters.save_review_result(
                chapter_number, passed, response, review_result
            )
        except Exception as e:
            return {"error": f"保存审核结果失败: {e}"}

        return {
            "chapter_number": chapter_number,
            "passed": passed,
            "scores": review_result.get("scores", {}),
            "issues": review_result.get("issues", []),
            "suggestions": review_result.get("suggestions", ""),
            "message": f"审核{'通过' if passed else '未通过'} — "
                       f"发现 {len(review_result.get('issues', []))} 个问题",
        }

    async def rewrite(self, chapter_number: int) -> dict:
        """根据上次审核反馈重写章节

        Returns:
            {
                "action": "rewritten",
                "chapter_number": int,
                "word_count": int,
                "message": str,
            }
        """
        # 1. 读 KB
        chapter = self.kb.chapters.get_by_number(chapter_number)
        if not chapter or not chapter.get("content"):
            return {"error": f"第{chapter_number}章内容不存在，请先生成"}

        # 2. 提取审核反馈
        review_feedback = ""
        review_result = chapter.get("review_result")
        if review_result and isinstance(review_result, dict):
            review_feedback = (
                review_result.get("raw_response", "")
                or review_result.get("suggestions", "")
            )
        if not review_feedback and chapter.get("review_feedback"):
            review_feedback = chapter["review_feedback"]
        if not review_feedback:
            return {"error": f"第{chapter_number}章尚未审核，请先使用 review_chapter"}

        co = self.kb.outlines.get_chapter_outline(chapter_number)
        if not co:
            return {"error": f"第{chapter_number}章大纲不存在"}

        original_content = chapter["content"]

        # 3. 构建消息
        messages = self._build_rewrite_messages(co, original_content, review_feedback)

        # 4. 调 LLM
        try:
            response = await self.llm.chat(
                messages,
                temperature=NODE_TEMPERATURES["rewrite"],
                max_tokens=16384,
            )
            new_content = _clean_chapter_content(response)
        except Exception as e:
            return {"error": f"重写 LLM 调用失败: {e}"}

        # 5. 存 DB
        try:
            self.kb.chapters.save_rewrite_result(chapter_number, new_content)
        except Exception as e:
            return {"error": f"保存重写结果失败: {e}"}

        word_count = len(new_content)
        return {
            "action": "rewritten",
            "chapter_number": chapter_number,
            "word_count": word_count,
            "message": f"第{chapter_number}章已重写（{word_count}字），请再次审核",
        }

    async def review_and_rewrite(self, chapter_number: int, strictness: str = "standard") -> dict:
        """审核不通过时自动重写再审核（内部方法，不暴露为 @tool）

        Returns:
            同 review，但额外包含 rewrite_count 字段
        """
        review_result = await self.review(chapter_number, strictness)

        if review_result.get("error"):
            return review_result

        if not review_result.get("passed"):
            rewrite_result = await self.rewrite(chapter_number)
            if rewrite_result.get("error"):
                return rewrite_result

            # 重写后再审核
            review_result = await self.review(chapter_number, strictness)
            if review_result.get("error"):
                return review_result
            review_result["rewritten"] = True

        return review_result

    # ========== 内部方法：上下文组装 ==========

    def _gather_context(self, chapter_number: int) -> dict:
        """从 KB 读取上下文数据，返回领域 dict（非旧版 NovelState）"""
        characters = self.kb.characters.list_characters()
        ws = self.kb.world_setting.get()
        outline = self.kb.outlines.get()
        style = self.kb.styles.get_constraints()
        timeline = self.kb.timelines.list_timeline()

        # 已写章节摘要（供上下文策略使用）
        written_chapters = []
        for t in timeline:
            written_chapters.append({
                "chapter_number": t.get("chapter_number"),
                "summary": t.get("summary") or "",
            })

        # 目标字数
        target_words = 100000
        if outline:
            target_words = (
                (outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 100)
                * 3000
            )

        # 类型 / 风格偏好
        genre = ""
        style_preference = ""
        if outline:
            genre = outline.get("novel_type") or ""
        if style:
            style_preference = style.get("style_preference") or ""

        # 章节大纲列表（供上下文策略使用）
        chapter_outlines = self.kb.outlines.list_chapter_outlines()

        return {
            "characters": characters,
            "world_setting": ws or {},
            "outline": outline,
            "style": style,
            "written_chapters": written_chapters,
            "chapter_outlines": chapter_outlines,
            "target_words": target_words,
            "genre": genre,
            "style_preference": style_preference,
        }

    def _build_previous_context(
        self,
        ctx: dict,
        chapter_number: int,
        output_tokens: int,
    ) -> str:
        """构建前文上下文（使用上下文策略）"""
        strategy = get_context_strategy(ctx["target_words"])

        # 估算 system prompt 占用
        system_tokens = estimate_tokens(_REVIEW_SYSTEM_PROMPT[:200])
        budget = calculate_context_budget(
            self.context_window, output_tokens, system_tokens
        )

        return strategy.build_previous_context(
            written_chapters=ctx["written_chapters"],
            current_chapter=chapter_number,
            chapter_outlines=ctx["chapter_outlines"],
            token_budget=budget,
        )

    def _build_review_messages(
        self,
        chapter_content: str,
        chapter_outline: dict,
        strictness: str,
    ) -> list[dict]:
        """构建审核的 system/user 消息"""
        ctx = self._gather_context(chapter_outline.get("chapter_number", 1))

        previous_context = self._build_previous_context(ctx, chapter_outline.get("chapter_number", 1), 2048)
        if previous_context and previous_context != "（这是第一章，没有前文）":
            previous_context = f"## 前文上下文\n{previous_context}"
        else:
            previous_context = ""

        chars_str = _format_characters(ctx["characters"])
        ws_str = _format_world_setting(ctx["world_setting"])
        co_str = _format_chapter_outline(chapter_outline)

        system_content = safe_format(
            _REVIEW_SYSTEM_PROMPT,
            chapter_outline=co_str,
            main_characters=chars_str,
            world_setting=ws_str,
            previous_context=previous_context,
        )

        user_content = safe_format(
            _REVIEW_USER_PROMPT,
            strictness=strictness,
            genre=ctx["genre"] or "未指定",
            style_preference=ctx["style_preference"] or "未指定",
            chapter_content=chapter_content,
        )

        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_rewrite_messages(
        self,
        chapter_outline: dict,
        original_content: str,
        review_feedback: str,
    ) -> list[dict]:
        """构建重写的 system/user 消息"""
        ctx = self._gather_context(chapter_outline.get("chapter_number", 1))

        previous_context = self._build_previous_context(ctx, chapter_outline.get("chapter_number", 1), 8192)
        if previous_context and previous_context != "（这是第一章，没有前文）":
            previous_context = f"## 前文上下文\n{previous_context}"
        else:
            previous_context = ""

        chars_str = _format_characters(ctx["characters"])
        ws_str = _format_world_setting(ctx["world_setting"])
        co_str = _format_chapter_outline(chapter_outline)

        system_content = safe_format(
            _REWRITE_SYSTEM_PROMPT,
            chapter_outline=co_str,
            main_characters=chars_str,
            world_setting=ws_str,
            previous_context=previous_context,
        )

        user_content = safe_format(
            _REWRITE_USER_PROMPT,
            genre=ctx["genre"] or "未指定",
            review_feedback=review_feedback,
            original_content=original_content,
        )

        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": user_content})
        return messages
