import os
"""写后自检汇总节点

汇总所有自检结果，运行预警检查，写入 state["post_write_summary"]。
Phase 4: 传递 current_volume 给预警检查和索引重建。
"""

import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.warning import WarningService
from app.agents.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


async def post_write_summary_node(state: NovelState) -> NovelState:
    """汇总写后自检结果 + 运行预警检查

    1. 读取最新追踪数据生成摘要
    2. 运行 WarningService.check_all() 检测质量信号（含跨卷预警）
    3. 预警结果写入 state（供 SSE 推送）
    """
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    current_volume = state.get("current_volume", 1)
    kb = KnowledgeBaseService(project_id)

    # current_chapter 已在 chapter_writing_node 中递增 1，
    # 所以刚写完的章节号是 current_chapter - 1
    written_chapter_num = current_chapter - 1

    # 读取最新追踪数据
    timeline = kb.get_timeline(chapter_range=(written_chapter_num, written_chapter_num))
    snapshots = kb.get_style_snapshots(last_n=1)
    overdue = kb.get_overdue_foreshadowings(written_chapter_num)

    # 生成摘要
    parts = [f"第{written_chapter_num}章写后自检："]
    if timeline:
        parts.append("  时间线：已更新")
    if snapshots:
        s = snapshots[0]
        parts.append(f"  风格：对话{s.dialogue_ratio:.0%}，句长{s.avg_sentence_length:.0f}字")
    if overdue:
        parts.append(f"  ⚠️ 超期伏笔：{len(overdue)}个")
    else:
        parts.append("  伏笔：无超期")

    # ========== 预警检查（含跨卷预警）==========
    warning_service = WarningService(project_id)
    warnings = warning_service.check_all(written_chapter_num, current_volume)

    if warnings:
        parts.append(f"\n  预警：")
        for w in warnings:
            parts.append(f"    {w['emoji']} {w['title']}：{w['message']}")

    # ========== 增量索引更新 + 定期重建 ==========
    retrieval = RetrievalService(project_id)
    
    # 1. 立即增量添加本章内容
    chapter = find_chapter_by_number(written_chapters, written_chapter_num)
    if chapter and chapter.get("content"):
        try:
            content_text = chapter["content"]
            # 分 chunk 添加
            from app.agents.services.retrieval import chunk_text
            chunks = chunk_text(content_text, min_chars=100, max_chars=500)
            
            for chunk_idx, chunk_text_item in enumerate(chunks):
                metadata = {
                    "chapter_number": written_chapter_num,
                    "volume_number": current_volume,
                    "source": f"chapter_{written_chapter_num}_chunk_{chunk_idx}",
                    "chunk_index": chunk_idx,
                }
                success = retrieval.add_document(chunk_text_item, metadata)
                if not success:
                    logger.warning(f"第 {written_chapter_num} 章 chunk {chunk_idx} 增量索引失败")
                    
            parts.append(f"  检索索引：增量更新 {len(chunks)} 个 chunk")
        except Exception as e:
            logger.warning(f"增量索引更新失败: {e}")
            parts.append(f"  检索索引：增量更新失败")
            # 标记索引需要重建
            retrieval.mark_index_stale()
    
    # 2. 每5章触发全量重建
    if written_chapter_num > 0 and written_chapter_num % 5 == 0:
        try:
            success = retrieval.rebuild_index(current_volume=current_volume)
            if success:
                parts.append(f"  检索索引：已全量重建")
                # 重建成功后清除 stale 标记
                index_path = retrieval._index_dir(project_id)
                stale_path = os.path.join(index_path, ".stale")
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            else:
                parts.append(f"  检索索引：全量重建失败")
        except Exception as e:
            logger.warning(f"检索索引全量重建失败: {e}")
            parts.append(f"  检索索引：全量重建失败")

    summary = "\n".join(parts)

    # ========== 关系演变检测 ==========
    try:
        evolution_result = await detect_and_record_evolution(
            kb=kb,
            chapter_content=chapter.get("content", "") if chapter else "",
            chapter_number=written_chapter_num,
            project_id=project_id
        )
        if evolution_result.get("changed"):
            parts.append(f"  关系演变：{evolution_result['count']}条记录已生成")
    except Exception as e:
        logger.warning(f"关系演变检测失败: {e}")

    summary = "\n".join(parts)

    return {
        "post_write_summary": summary,
    }


# ========== 关系演变检测函数 ==========

async def detect_and_record_evolution(
    kb: KnowledgeBaseService,
    chapter_content: str,
    chapter_number: int,
    project_id: int,
) -> dict:
    """检测本章是否发生人物关系变化，自动生成 EvolutionRecord"""
    
    if not chapter_content or len(chapter_content) < 100:
        return {"changed": False, "count": 0}
    
    # 1. 获取本章涉及的角色（从章节内容中提取）
    characters = kb.get_characters()
    if not characters:
        return {"changed": False, "count": 0}
    
    # 简单提取：检查章节内容中出现的角色名
    content_lower = chapter_content.lower()
    involved_names = []
    for char in characters:
        if char.name in chapter_content:
            involved_names.append(char.name)
    
    if not involved_names:
        return {"changed": False, "count": 0}
    
    # 2. 获取涉及这些角色的关系
    relations = kb.get_relations_involved_characters(involved_names)
    if not relations:
        return {"changed": False, "count": 0}
    
    # 3. 对���个关系调用 LLM 分析是否发生了关系变化
    changed_count = 0
    for relation in relations:
        changes = await analyze_relation_evolution(
            chapter_content,
            relation,
            kb
        )
        
        if changes.get("has_evolution"):
            # 4. 创建 EvolutionRecord
            record = kb.create_evolution_record(
                relation_id=relation.id,
                chapter_number=chapter_number,
                content=changes["event"],
                status_change=changes.get("status_change"),
                trust_change=changes.get("trust_change"),
            )
            
            # 5. 标记对应的 EvolutionPlan 为已触发
            kb.mark_evolution_plan_triggered(relation.id, chapter_number)
            
            # 6. 同步更新 Relation 的 trust_level
            new_trust = changes.get("new_trust_level", relation.trust_level)
            kb.update_relation_trust_level(relation.id, new_trust)
            
            changed_count += 1
    
    return {"changed": changed_count > 0, "count": changed_count}


async def analyze_relation_evolution(
    chapter_content: str,
    relation,
    kb: KnowledgeBaseService,
) -> dict:
    """调用 LLM 分析章节内容是否导致关系变化
    
    这是一个简化版本，实际生产中应该调用 LLM。
    暂时使用基于关键词的简单检测。
    """
    from app.utils.llm import get_llm_service
    
    char_a = relation.character_a.name if relation.character_a else "角色A"
    char_b = relation.character_b.name if relation.character_b else "角色B"
    
    # 构建分析 prompt
    prompt = f"""分析以下小说章节内容，判断 {char_a} 和 {char_b} 之间的关系是否发生了明显变化。

当前关系：
- 类型：{relation.relation_type}
- 信任度：{relation.trust_level}

章节内容（最后1000字）：
{chapter_content[-1000:]}

请分析：
1. 是否发生了导致信任度变化的事件？
2. 关系状态是否发生了变化？
3. 如果有变化，具体是什么事件？信任度变化了多少？

请用以下 JSON 格式返回分析结果：
{{
    "has_evolution": true/false,
    "event": "具体事件描述，如果有变化的话",
    "status_change": "关系状态变化，例如'信任→猜疑'，如果没有则为空",
    "trust_change": 信任度变化数值，例如 -20 或 +15，如果没有则为 0,
    "new_trust_level": 变化后的信任度数值
}}
"""

    try:
        # 简化版本：使用关键词检测
        trust_keywords = [
            ("信任", "背叛", -30, "信任→背叛"),
            ("原谅", "和解", 25, "敌对→和解"),
            ("爱上", "感情", 20, "陌生→感情"),
            ("吵架", "争执", -15, None),
            ("帮助", "援救", 10, None),
            ("欺骗", "谎言", -25, "信任→猜疑"),
            ("牺牲", "舍命", 30, "敌对→生死之交"),
            ("告白", "表白", 15, None),
        ]
        
        content_lower = chapter_content.lower()
        trust_change = 0
        status_change = None
        has_evolution = False
        event = ""
        
        for pos_kw, neg_kw, change, status in trust_keywords:
            if pos_kw in content_lower or neg_kw in content_lower:
                # 检查是否涉及这两个角色
                if char_a in chapter_content and char_b in chapter_content:
                    has_evolution = True
                    trust_change += change
                    event = f"{pos_kw if change > 0 else neg_kw}事件"
                    if status:
                        status_change = status
                    break
        
        if has_evolution:
            new_trust = max(0, min(100, relation.trust_level + trust_change))
            return {
                "has_evolution": True,
                "event": event,
                "status_change": status_change,
                "trust_change": trust_change,
                "new_trust_level": new_trust,
            }
    except Exception as e:
        pass
    
    return {"has_evolution": False}


# 辅助函数：查找章节
def find_chapter_by_number(chapters: list, number: int):
    for c in chapters:
        if c.get("chapter_number") == number:
            return c
    return None
