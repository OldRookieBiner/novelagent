"""卷过渡数据交接节点

职责（仅数据准备，不运行修订节点——修订由图路由处理）：
1. 当前卷收尾检查：待回收伏笔清单
2. 角色状态快照 → 写入 Volume.character_snapshot
3. 当前卷最后情节块摘要 → 写入 Volume.last_block_summary
4. 跨卷追踪写入：
   - 未回收伏笔升级到 CrossVolumeForeshadowing
   - 跨卷支线升级到 CrossVolumeSubplot
   - 角色变化日志追加到 CharacterChangeLog
5. 检索索引：当前卷 rebuild + 全局 rebuild
6. 创建新卷记录（Volume + chapter_offset）
7. 更新 state: current_volume += 1, revision_context = "per_volume"

返回后，图路由到 structural_review_node（per-volume revision）。
"""

import json
import logging

from app.agents.state import NovelState, RevisionContext
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.retrieval import RetrievalService
from app.agents.prompts import VOLUME_TRANSITION_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def volume_transition_node(state: NovelState) -> NovelState:
    """卷过渡数据交接节点

    单一职责：准备卷间数据交接，设置修订上下文。
    不调用修订节点——修订由图路由到 structural_review_node。
    """
    project_id = state["project_id"]
    current_volume = state.get("current_volume", 1)
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 1. 获取当前卷记录
    volume = kb.get_volume(current_volume)
    if not volume:
        logger.error(f"Volume {current_volume} not found for project {project_id}")
        return {**state}

    # 2. 收集未回收伏笔
    unreclaimed = kb.get_foreshadowings(status="active") + kb.get_foreshadowings(status="pending_reclaim")

    # 3. 角色状态快照 — 序列化当前所有角色的关键字段
    characters = kb.get_characters()
    snapshot = []
    for c in characters:
        snapshot.append({
            "id": c.id,
            "name": c.name,
            "growth_arc": c.growth_arc,
            "core_motivation": c.core_motivation,
        })
    kb.update_volume(volume.id, {"character_snapshot": snapshot})

    # 4. 最后情节块摘要
    current_block = kb.get_current_plot_block(current_chapter - 1)
    if current_block and current_block.completion_summary:
        kb.update_volume(volume.id, {"last_block_summary": current_block.completion_summary})

    # 5. 跨卷追踪写入
    # 5a. 未回收伏笔升级到 CrossVolumeForeshadowing
    for fs in unreclaimed:
        existing_cvf = _find_cvf_by_source(kb, fs.id)
        if existing_cvf:
            # 已有跨卷伏笔记录，更新出现次数
            kb.update_cross_volume_foreshadowing(existing_cvf.id, {
                "appearance_count": existing_cvf.appearance_count + 1,
            })
        else:
            # 创建新的跨卷伏笔记录
            kb.create_cross_volume_foreshadowing({
                "source_foreshadowing_id": fs.id,
                "appearance_count": 1,
                "expected_volume": current_volume + 2,  # 预期2卷内回收
                "status": "active",
            })

    # 5b. 未解决支线升级到 CrossVolumeSubplot
    subplots = kb.get_subplots()
    active_subplots = [s for s in subplots if s.current_status != "resolved"]
    for sp in active_subplots:
        existing_cvs = _find_cvs_by_source(kb, sp.id)
        if not existing_cvs:
            kb.create_cross_volume_subplot({
                "source_subplot_id": sp.id,
                "status": "active",
                "expected_intersection_volume": current_volume + 2,
            })

    # 5c. 角色变化日志
    # 比较角色快照前后变化（简化实现：记录当前角色状态作为基线）
    prev_snapshot = volume.character_snapshot or []
    prev_map = {p["id"]: p for p in prev_snapshot if isinstance(p, dict)}
    for c in characters:
        prev = prev_map.get(c.id)
        if prev:
            changes = {}
            for field in ("growth_arc", "core_motivation"):
                old_val = prev.get(field)
                new_val = getattr(c, field, None)
                if old_val != new_val and new_val:
                    changes[field] = {"old": old_val, "new": new_val}
            if changes:
                kb.create_character_change_log({
                    "volume_number": current_volume,
                    "character_id": c.id,
                    "changes": changes,
                    "chapter_number": current_chapter - 1,
                })

    # 6. 重建检索索引（当前卷 + 全局）
    retrieval = RetrievalService(project_id)
    try:
        retrieval.rebuild_index(current_volume=current_volume)
    except Exception as e:
        logger.warning(f"卷过渡索引重建失败: {e}")

    # 7. 创建新卷记录
    new_volume_number = current_volume + 1
    new_chapter_offset = current_chapter - 1  # 已写章数即为偏移量
    kb.create_volume({
        "volume_number": new_volume_number,
        "chapter_offset": new_chapter_offset,
    })

    # 8. LLM 生成卷过渡摘要（供前端展示）
    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "volume_transition")

    unreclaimed_text = "\n".join([f"- {f.content[:60]}（状态：{f.status}）" for f in unreclaimed[:10]])
    active_subplot_text = "\n".join([f"- {s.name}（状态：{s.current_status}）" for s in active_subplots[:10]])

    if user_template:
        prompt_text = safe_format(user_template,
            current_volume=current_volume,
            new_volume=new_volume_number,
            chapter_offset=new_chapter_offset,
            unreclaimed_foreshadowings=unreclaimed_text or "无",
            active_subplots=active_subplot_text or "无",
            character_count=len(characters),
        )
    else:
        prompt_text = safe_format(VOLUME_TRANSITION_PROMPT,
            current_volume=current_volume,
            new_volume=new_volume_number,
            chapter_offset=new_chapter_offset,
            unreclaimed_foreshadowings=unreclaimed_text or "无",
            active_subplots=active_subplot_text or "无",
            character_count=len(characters),
        )

    transition_summary = ""
    try:
        async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.3):
            transition_summary += chunk
    except Exception as e:
        logger.warning(f"卷过渡摘要生成失败: {e}")
        transition_summary = f"第{current_volume}卷完成，过渡到第{new_volume_number}卷。章数偏移：{new_chapter_offset}。"

    # 9. 更新 state
    return {
        **state,
        "current_volume": new_volume_number,
        "revision_context": RevisionContext.PER_VOLUME.value,
        "post_write_summary": transition_summary,
        "confirmation_type": None,
        "waiting_for_confirmation": False,
    }


def _find_cvf_by_source(kb: KnowledgeBaseService, source_id: int):
    """查找已有的跨卷伏笔记录"""
    all_cvf = kb.get_cross_volume_foreshadowings()
    for cvf in all_cvf:
        if cvf.source_foreshadowing_id == source_id:
            return cvf
    return None


def _find_cvs_by_source(kb: KnowledgeBaseService, source_id: int):
    """查找已有的跨卷支线记录"""
    all_cvs = kb.get_cross_volume_subplots()
    for cvs in all_cvs:
        if cvs.source_subplot_id == source_id:
            return cvs
    return None
