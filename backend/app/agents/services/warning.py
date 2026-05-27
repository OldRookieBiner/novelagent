"""主动预警服务

在写作流程中检测质量信号，主动推送预警到前端（通过 SSE）。

预警类型（对齐 spec section 6.4 和 novelskills 质量预警信号）：
- 🟡 伏笔超期：待回收伏笔超过预期回收位置 2 个情节块
- 🟡 风格漂移：最近 10 章统计偏离基准 >25%
- 🟡 节奏单调：连续 3+ 章相同情绪且无预期节奏变化
- 🔴 设定冲突：写作中产生的新内容与🔴设定矛盾
- 🟡 问题链停滞：连续 2 章没有推进问题链
- 🟡 支线停滞：支线在交汇点后 2 个情节块仍未交汇

设计原则：
- 预警是非阻塞的——不影响写作流程
- 预警推送到前端，作者可选择处理、忽略、或让 Agent 自动调整
- 同类预警去重，避免重复推送
"""

import logging
import time
from typing import Optional

from app.agents.services.knowledge_base import KnowledgeBaseService

logger = logging.getLogger(__name__)

# 项目级预警缓存（内存，避免重复推送）
_project_warnings: dict[int, dict[str, float]] = {}  # {project_id: {warning_key: last_emit_time}}


class WarningService:
    """主动预警服务

    供 LangGraph 节点在写后自检阶段调用，
    检测质量信号并返回预警列表。

    预警通过 SSE 推送到前端（由调用方负责）。
    """

    # 同类预警最小间隔（秒），避免短时间内重复推送
    DEDUP_INTERVAL = 300  # 5 分钟

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.kb = KnowledgeBaseService(project_id)
        if project_id not in _project_warnings:
            _project_warnings[project_id] = {}

    def check_foreshadowing_overdue(self, current_chapter: int) -> Optional[dict]:
        """检查伏笔是否超期

        novelskills 规则：伏笔在预期回收位置后 2 个情节块仍未回收 → 🟡
        """
        overdue = self.kb.get_overdue_foreshadowings(current_chapter)
        if not overdue:
            return None

        key = f"foreshadowing_overdue_{current_chapter}"
        if self._is_deduped(key):
            return None

        items = []
        for f in overdue[:5]:
            overdue_by = current_chapter - f.expected_resolve_chapter if f.expected_resolve_chapter else 0
            items.append(f"「{f.content[:30]}」超期{overdue_by}章")

        warning = {
            "type": "foreshadowing_overdue",
            "level": "warning",
            "emoji": "🟡",
            "title": f"伏笔超期（{len(overdue)}个）",
            "message": f"有 {len(overdue)} 个伏笔已超过预期回收章节：" + "；".join(items[:3]),
            "chapter_number": current_chapter,
        }
        self._mark_emitted(key)
        return warning

    def check_style_drift(self) -> Optional[dict]:
        """检查风格漂移

        novelskills 规则：最近 10 章统计偏离基准 >25% → 🟡
        """
        snapshots = self.kb.get_style_snapshots(last_n=10)
        if len(snapshots) < 5:
            return None

        # 计算基准（前 3 章平均）
        earliest = sorted(snapshots, key=lambda s: s.chapter_number)[:3]
        n = len(earliest)
        baseline_dialogue = sum(s.dialogue_ratio for s in earliest) / n
        baseline_sent_len = sum(s.avg_sentence_length for s in earliest) / n

        # 检查最近 3 章是否偏离
        recent = sorted(snapshots, key=lambda s: s.chapter_number)[-3:]
        recent_dialogue = sum(s.dialogue_ratio for s in recent) / len(recent)
        recent_sent_len = sum(s.avg_sentence_length for s in recent) / len(recent)

        drifts = []
        if baseline_dialogue > 0:
            dialogue_dev = abs(recent_dialogue - baseline_dialogue) / baseline_dialogue
            if dialogue_dev > 0.25:
                drifts.append(f"对话占比偏离{dialogue_dev:.0%}")

        if baseline_sent_len > 0:
            sent_dev = abs(recent_sent_len - baseline_sent_len) / baseline_sent_len
            if sent_dev > 0.25:
                drifts.append(f"句长偏离{sent_dev:.0%}")

        if not drifts:
            return None

        key = f"style_drift_{snapshots[0].chapter_number}"
        if self._is_deduped(key):
            return None

        warning = {
            "type": "style_drift",
            "level": "warning",
            "emoji": "🟡",
            "title": "风格漂移",
            "message": f"最近章节风格偏离基准：" + "；".join(drifts),
        }
        self._mark_emitted(key)
        return warning

    def check_rhythm_monotone(self, current_chapter: int) -> Optional[dict]:
        """检查节奏单调

        novelskills 规则：连续 3+ 章相同情绪且无预期节奏变化 → 🟡
        """
        timeline = self.kb.get_timeline(
            chapter_range=(max(1, current_chapter - 5), current_chapter - 1)
        )
        if len(timeline) < 3:
            return None

        # 检查最近 3+ 章是否相同情绪
        recent_emotions = [t.emotion_tag for t in timeline[-5:] if t.emotion_tag != "未标注"]
        if len(recent_emotions) < 3:
            return None

        # 连续相同情绪检测
        monotone_count = 1
        for i in range(len(recent_emotions) - 1, 0, -1):
            if recent_emotions[i] == recent_emotions[i-1]:
                monotone_count += 1
            else:
                break

        if monotone_count < 3:
            return None

        key = f"rhythm_monotone_{current_chapter}"
        if self._is_deduped(key):
            return None

        warning = {
            "type": "rhythm_monotone",
            "level": "warning",
            "emoji": "🟡",
            "title": "节奏单调",
            "message": f"连续 {monotone_count} 章相同情绪「{recent_emotions[-1]}」，建议引入节奏变化",
            "chapter_number": current_chapter,
        }
        self._mark_emitted(key)
        return warning

    def check_setting_conflict(self, current_chapter: int) -> Optional[dict]:
        """检查设定冲突

        novelskills 规则：写作中产生的新内容与🔴设定矛盾 → 🔴
        """
        ws = self.kb.get_world_setting()
        if not ws or not ws.tiered_settings:
            return None

        # 检查🔴设定是否被违反
        # 简化实现：🔴设定存在但需要 LLM 判断是否违反
        # 这里只做标记，具体违反检测由 character_consistency_node + deep_review_node 完成
        return None

    def check_question_chain_stall(self, current_chapter: int) -> Optional[dict]:
        """检查问题链停滞

        novelskills 规则：连续 2 章没有推进问题链 → 🟡
        """
        questions = self.kb.get_plot_questions(status="pending")
        if not questions:
            return None

        # 检查最近 2 章是否有回答任何问题
        recent_answered = self.kb.get_plot_questions(status="answered")
        if recent_answered:
            latest_answered_chapter = max(q.answered_in_chapter for q in recent_answered if q.answered_in_chapter)
            if current_chapter - latest_answered_chapter <= 2:
                return None

        key = f"question_chain_stall_{current_chapter}"
        if self._is_deduped(key):
            return None

        warning = {
            "type": "question_chain_stall",
            "level": "warning",
            "emoji": "🟡",
            "title": "问题链停滞",
            "message": f"连续 {current_chapter - (latest_answered_chapter if recent_answered else 0)} 章未推进问题链，还有 {len(questions)} 个待回答问题",
            "chapter_number": current_chapter,
        }
        self._mark_emitted(key)
        return warning

    def check_cross_volume_subplot_overdue(self, current_volume: int) -> Optional[dict]:
        """检查跨卷支线超期

        novelskills 规则：交汇点后2卷未交汇 → 🟡
        """
        if current_volume <= 1:
            return None

        cvs_list = self.kb.get_cross_volume_subplots(status="active")
        overdue = []
        for cvs in cvs_list:
            if cvs.expected_intersection_volume and current_volume > cvs.expected_intersection_volume + 1:
                overdue.append(f"跨卷支线#{cvs.id}")

        if not overdue:
            return None

        key = f"cross_volume_subplot_overdue_{current_volume}"
        if self._is_deduped(key):
            return None

        warning = {
            "type": "cross_volume_subplot_overdue",
            "level": "warning",
            "emoji": "🟡",
            "title": f"跨卷支线超期（{len(overdue)}个）",
            "message": f"有 {len(overdue)} 个跨卷支线超过预期交汇卷：" + "；".join(overdue[:3]),
        }
        self._mark_emitted(key)
        return warning

    def check_character_state_jump(self, current_volume: int) -> Optional[dict]:
        """检查角色状态跳变

        novelskills 规则：跨卷角色状态无铺垫跳变 → 🟡
        对比相邻卷的 character_snapshot 检测异常变化。
        """
        if current_volume <= 1:
            return None

        ccl = self.kb.get_character_change_logs(volume_number=current_volume - 1)
        if not ccl:
            return None

        # 检查是否有大量无铺垫变化
        jump_chars = []
        for log in ccl:
            changes = log.changes if isinstance(log.changes, dict) else {}
            if len(changes) >= 3:  # 单角色同时3个以上属性变化视为跳变
                jump_chars.append(f"角色#{log.character_id}")

        if not jump_chars:
            return None

        key = f"character_state_jump_{current_volume}"
        if self._is_deduped(key):
            return None

        warning = {
            "type": "character_state_jump",
            "level": "warning",
            "emoji": "🟡",
            "title": f"角色状态跳变（{len(jump_chars)}个）",
            "message": f"以下角色在上卷末尾有大量无铺垫状态变化：" + "；".join(jump_chars[:3]),
        }
        self._mark_emitted(key)
        return warning

    def check_long_term_foreshadowing_overdue(self, current_volume: int) -> Optional[dict]:
        """检查长期伏笔超期

        novelskills 规则：预期回收卷后2卷未回收 → 🟡
        """
        if current_volume <= 1:
            return None

        cvf_list = self.kb.get_cross_volume_foreshadowings(status="active")
        overdue = []
        for cvf in cvf_list:
            if cvf.expected_volume and current_volume > cvf.expected_volume + 1:
                overdue.append(f"跨卷伏笔#{cvf.id}（预期第{cvf.expected_volume}卷回收）")

        if not overdue:
            return None

        key = f"long_term_foreshadowing_overdue_{current_volume}"
        if self._is_deduped(key):
            return None

        warning = {
            "type": "long_term_foreshadowing_overdue",
            "level": "warning",
            "emoji": "🟡",
            "title": f"长期伏笔超期（{len(overdue)}个）",
            "message": f"有 {len(overdue)} 个跨卷伏笔超过预期回收卷：" + "；".join(overdue[:3]),
        }
        self._mark_emitted(key)
        return warning

    def check_all(self, current_chapter: int, current_volume: int = 1) -> list[dict]:
        """执行所有预警检查，返回预警列表

        由 post_write_summary_node 或 deep_review_node 调用。
        current_volume > 1 时额外执行跨卷预警检查。
        """
        warnings = []

        checks = [
            self.check_foreshadowing_overdue(current_chapter),
            self.check_style_drift(),
            self.check_rhythm_monotone(current_chapter),
            self.check_setting_conflict(current_chapter),
            self.check_question_chain_stall(current_chapter),
        ]

        # 跨卷预警（仅多卷项目）
        if current_volume > 1:
            checks.extend([
                self.check_cross_volume_subplot_overdue(current_volume),
                self.check_character_state_jump(current_volume),
                self.check_long_term_foreshadowing_overdue(current_volume),
            ])

        for w in checks:
            if w is not None:
                warnings.append(w)

        return warnings

    # ========== 去重 ==========

    def _is_deduped(self, key: str) -> bool:
        """检查是否在去重间隔内已发送过同类预警"""
        cache = _project_warnings.get(self.project_id, {})
        last_time = cache.get(key, 0)
        return (time.time() - last_time) < self.DEDUP_INTERVAL

    def _mark_emitted(self, key: str):
        """标记预警已发送"""
        if self.project_id not in _project_warnings:
            _project_warnings[self.project_id] = {}
        _project_warnings[self.project_id][key] = time.time()
