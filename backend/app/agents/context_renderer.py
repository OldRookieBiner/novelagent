"""上下文中文化渲染层

替代 json.dumps(project_data) 直接喂给 LLM 的旧方式。
把 ProjectContextAssembler 输出的 dict 渲染成带中文标签的 Markdown 文本，
避免 LLM 在回答中复述 core_motivation / habit_action / backstory 等
内部英文字段名。

规则总览：
  - 顶层 key   → ## <中文标签>
  - dict 内 key → - <中文标签>：<value>
  - list[dict] → 每项以 - 起首，子字段缩进两空格
  - list[基本类型] → 用「、」连接成单行
  - 跳过条件：value is None / "" / [] / {}
    （不能用 if not value：trust_level=0、confirmed=False 是合法值）
  - prerequisites 顶层 key 直接跳过（由 {context_prerequisites_warning} 通道单独展示）
  - 未在 FIELD_LABELS 中的 key：保留原 key 作为标签，logger.warning 上报，
    不在文本中加 [未映射] 等标记
  - 单值最长 800 字，超出截断加「……」
  - 布尔值 True/False 渲染为「是/否」
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# 单值长度上限（字符），超出截断
_MAX_VALUE_CHARS = 800
# 截断后缀
_TRUNCATE_SUFFIX = "……"

# compact 模式白名单（与 agent.py slim_data 白名单一致）
_COMPACT_WHITELIST = frozenset({
    "outline",
    "style_constraints",
    "current_plot_block",
    "pending_foreshadowings",
    "overdue_foreshadowings",
})

# prerequisites 已通过独立的 {context_prerequisites_warning} 通道展示，
# 渲染器跳过避免双重展示。
_SKIP_TOP_LEVEL_KEYS = frozenset({"prerequisites"})


# ==========================================================================
# 字段名 → 中文标签映射
# 必须穷尽 project_data 所有可能出现的顶层与嵌套 key。
# 新增字段时同步更新此表，未映射 key 会触发 logger.warning。
# ==========================================================================
FIELD_LABELS: dict[str, str] = {
    # ---- 顶层 key ----
    "outline_index": "大纲索引",
    "world_setting": "世界观",
    "outline": "大纲",
    "characters": "角色",
    "plot_blocks": "情节块",
    "foreshadowings": "伏笔",
    "pending_foreshadowings": "待回收伏笔",
    "overdue_foreshadowings": "逾期伏笔",
    "style_constraints": "风格约束",
    "style_deviation": "风格偏差摘要",
    "current_chapter_outline": "当前章节大纲",
    "previous_chapter_closing": "上一章结尾画面",
    "current_plot_block": "当前情节块",
    "active_subplot_events": "当前支线事件",
    "recent_decisions": "最近的变更决策",
    "questions_for_chapter": "本章情节问题",
    "recent_timeline": "最近时间线",
    "relation_evolution_cues": "关系演变线索",
    "timeline": "时间线",
    "plot_questions": "情节问题",
    "subplots": "支线",
    "style_snapshots": "风格快照",
    "character_index": "角色索引",
    "phase": "创作阶段",
    "current_chapter_number": "当前章节号",
    "critical_rules": "核心红线规则",
    # prerequisites 在 _SKIP_TOP_LEVEL_KEYS 中跳过，仍保留标签以备未来调整

    # ---- 角色字段 ----
    "id": "ID",
    "name": "名称",
    "role": "角色定位",
    "personality": "性格",
    "catchphrase": "口头禅",
    "habit_action": "习惯动作",
    "deep_fear": "深层恐惧",
    "core_motivation": "核心动机",
    "growth_arc": "成长弧线",
    "appearance": "外貌",
    "backstory": "背景故事",
    "signature_item": "标志性物品",
    "knowledge_boundary": "知识边界",
    "speech_style": "语言风格",
    "speech_samples": "对话样本",

    # ---- 大纲与章节大纲 ----
    "title": "标题",
    "summary": "概述",
    "chapter_count_suggested": "建议章节数",
    "chapter_count_confirmed": "确认章节数",
    "plot_points": "情节节点",
    "order": "序号",
    "event": "事件",
    "conflict": "冲突",
    "hook": "钩子",
    "foreshadowing_label": "伏笔编号",
    "foreshadowing_content": "伏笔内容",
    "emotional_curve": "情感曲线",
    "theme": "主题",
    "chapter_number": "章节号",
    "scene": "场景",
    "emotional_arc": "情感弧线",
    "key_scenes": "关键场景",
    "target_words": "目标字数",
    "pacing_note": "节奏说明",
    "opening_state": "开篇状态",
    "turning_point": "转折点",
    "transition": "过渡",
    "ending": "结尾",
    "confirmed": "已确认",

    # ---- 世界观 ----
    "core_concept": "核心设定",
    "tiered_settings": "分级设定",
    "red": "红线规则（不可违反）",
    "yellow": "黄线规则（可突破有代价）",
    "green": "绿色装饰设定",
    "key_locations": "关键地点",

    # ---- 伏笔 / 情节块 / 支线 / 问题 / 演变 ----
    "content": "内容",
    "planted_chapter": "埋设章节",
    "expected_resolve_chapter": "预期回收章节",
    "status": "状态",
    "chapter_start": "起始章节",
    "chapter_end": "终止章节",
    "expected_mood": "预期情绪",
    "must_happen": "必须发生事件",
    "questions_to_answer": "要回答的问题",
    "questions_to_raise": "要提出的问题",
    "raised_in_chapter": "提出章节",
    "planned_intersection_chapter": "计划交汇章节",
    "expected_resolution_chapter": "预期解决章节",
    "current_status": "当前状态",
    "question_text": "问题内容",
    "trigger_chapter": "触发章节",
    "status_before": "演变前状态",
    "status_after": "演变后状态",
    "trust_before": "演变前信任度",
    "trust_after": "演变后信任度",
    "event_description": "事件描述",

    # ---- 时间线 / 风格 / 决策 ----
    "emotion_tag": "情绪标签",
    "dialogue_ratio": "对话占比",
    "avg_sentence_length": "平均句长",
    "avg_paragraph_length": "平均段长",
    "snapshots_available": "可用快照数",
    "dialogue_trend": "对话比趋势",
    "anomalies": "异常章节",
    "metric": "指标",
    "value": "数值",
    "baseline": "基线",
    "direction": "偏离方向",
    "chapter": "章节",
    "taboo_words": "禁忌词",
    "forbidden_patterns": "禁用句式",
    "abstract_rules": "抽象规则",
    "style_anchor": "风格锚点",
    "target_type": "目标类型",
    "decision": "决策",
    "description": "描述",

    # ---- prerequisites 子字段（虽然顶层跳过，但若未来挪到别处展示也能识别）----
    "prerequisites": "前置条件",
    "blocked": "阻断项",
    "warnings": "警告",
    "validated": "已校验",
    "severity": "严重程度",
    "type": "类型",
    "message": "说明",
}


# ==========================================================================
# 渲染主入口
# ==========================================================================

def render_context_block(data: dict) -> str:
    """把项目上下文 dict 渲染成中文 Markdown 文本喂给 LLM。

    顶层 key 渲染为 ## 标题；嵌套结构按规则展开。
    跳过 prerequisites（由独立通道展示）以及空值。
    """
    if not isinstance(data, dict) or not data:
        return ""

    lines: list[str] = []
    for key, value in data.items():
        # 隐藏内部辅助字段（以 _ 开头，如 _budget_used / _budget_max / _mode）
        if isinstance(key, str) and key.startswith("_"):
            continue
        if key in _SKIP_TOP_LEVEL_KEYS:
            continue
        if _is_empty(value):
            continue

        label = _label_for(key)
        rendered = _render_value(value, indent=0)
        if rendered is None:
            # 渲染出来为空（例如 dict 全部 key 被跳过）
            continue

        lines.append(f"## {label}")
        # 顶层值若是简单标量，直接展示在标题下一行；
        # 若是 dict / list，rendered 已经是多行内容。
        if "\n" in rendered or rendered.startswith("- "):
            lines.append(rendered)
        else:
            lines.append(rendered)
        lines.append("")  # 段间空行

    # 移除尾部空行
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def render_context_block_compact(data: dict) -> str:
    """精简版渲染 — 只渲染白名单 key。

    用于 history_budget <= 0 的回退路径，与 agent.py slim_data 白名单一致。
    """
    if not isinstance(data, dict) or not data:
        return ""
    filtered = {k: v for k, v in data.items() if k in _COMPACT_WHITELIST}
    return render_context_block(filtered)


# ==========================================================================
# 内部工具
# ==========================================================================

def _is_empty(value) -> bool:
    """空值判定 — 必须区分 0 / False / 空字符串。

    0 和 False 是合法值（如 trust_level=0、confirmed=False），不能跳过；
    None / "" / [] / {} 视为空。
    """
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


def _label_for(key) -> str:
    """查表得到中文标签。未映射 key 静默回退到原 key 并 logger.warning。"""
    if not isinstance(key, str):
        return str(key)
    label = FIELD_LABELS.get(key)
    if label is None:
        logger.warning("context_renderer: unmapped key=%s", key)
        return key
    return label


def _format_scalar(value) -> str:
    """格式化标量值。布尔转「是/否」，超长截断。"""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip("\n")
        if len(text) > _MAX_VALUE_CHARS:
            text = text[:_MAX_VALUE_CHARS] + _TRUNCATE_SUFFIX
        return text
    # 其他类型兜底
    text = str(value)
    if len(text) > _MAX_VALUE_CHARS:
        text = text[:_MAX_VALUE_CHARS] + _TRUNCATE_SUFFIX
    return text


def _is_scalar(value) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _render_value(value, indent: int) -> str | None:
    """递归渲染任意值为 Markdown 片段。

    返回 None 表示该值整体应被跳过（例如 dict 所有子 key 都为空）。
    indent 表示当前缩进层级（每层两个空格）。
    """
    if _is_empty(value):
        return None

    if _is_scalar(value):
        return _format_scalar(value)

    if isinstance(value, list):
        return _render_list(value, indent)

    if isinstance(value, dict):
        return _render_dict(value, indent)

    # 其他类型兜底转字符串
    return _format_scalar(value)


def _render_list(items: list, indent: int) -> str | None:
    """渲染 list。

    - 元素全是标量 → 用「、」拼接成单行
    - 含 dict → 每项前缀「- 」，dict 子字段缩进展示
    """
    if not items:
        return None

    # 标量 list：单行拼接
    if all(_is_scalar(it) for it in items):
        parts = [_format_scalar(it) for it in items if not _is_empty(it)]
        if not parts:
            return None
        return "、".join(parts)

    # 复杂 list：逐项渲染
    prefix = "  " * indent
    lines: list[str] = []
    for item in items:
        if _is_empty(item):
            continue
        if _is_scalar(item):
            lines.append(f"{prefix}- {_format_scalar(item)}")
            continue
        if isinstance(item, dict):
            rendered = _render_dict_inline(item, indent + 1)
            if rendered is None:
                continue
            # _render_dict 输出每行格式为「  - key：value」，
            # 首行需要把内层「- 」替换为外层「- 」（同级列表标记），其余行原样保留缩进
            sub_lines = rendered.split("\n")
            if not sub_lines:
                continue
            # 首行去掉内层缩进与「- 」前缀，再拼上外层 prefix + 「- 」
            first_stripped = sub_lines[0].lstrip()
            if first_stripped.startswith("- "):
                first_stripped = first_stripped[2:]
            lines.append(f"{prefix}- {first_stripped}")
            for r in sub_lines[1:]:
                lines.append(r)
            continue
        if isinstance(item, list):
            sub = _render_list(item, indent + 1)
            if sub is not None:
                lines.append(f"{prefix}- {sub}")
            continue

    if not lines:
        return None
    return "\n".join(lines)


def _render_dict(d: dict, indent: int) -> str | None:
    """渲染 dict 为多行 key: value 列表。"""
    if not d:
        return None
    prefix = "  " * indent
    lines: list[str] = []
    for k, v in d.items():
        if isinstance(k, str) and k.startswith("_"):
            continue
        if _is_empty(v):
            continue
        label = _label_for(k)
        if _is_scalar(v):
            lines.append(f"{prefix}- {label}：{_format_scalar(v)}")
        elif isinstance(v, list):
            if all(_is_scalar(it) for it in v):
                parts = [_format_scalar(it) for it in v if not _is_empty(it)]
                if parts:
                    lines.append(f"{prefix}- {label}：{'、'.join(parts)}")
            else:
                sub = _render_list(v, indent + 1)
                if sub is not None:
                    lines.append(f"{prefix}- {label}：")
                    lines.append(sub)
        elif isinstance(v, dict):
            sub = _render_dict(v, indent + 1)
            if sub is not None:
                lines.append(f"{prefix}- {label}：")
                lines.append(sub)
        else:
            lines.append(f"{prefix}- {label}：{_format_scalar(v)}")

    if not lines:
        return None
    return "\n".join(lines)


def _render_dict_inline(d: dict, indent: int) -> str | None:
    """渲染 list[dict] 中单个 dict 项 — 与 _render_dict 相同，
    但首行去掉缩进前缀，由调用方拼接 - 前缀。
    """
    rendered = _render_dict(d, indent)
    if rendered is None:
        return None
    return rendered
