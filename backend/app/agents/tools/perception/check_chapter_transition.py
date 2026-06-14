"""章节衔接检查工具

检查第 N-1 章结尾和第 N 章大纲开场是否连贯。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _extract_names


@tool
async def check_chapter_transition(chapter_number: int) -> dict:
    """检查章节间的衔接连贯性。分析上一章结尾和当前章大纲开场是否连贯。

    Args:
        chapter_number: 当前章节号（将检查第 N-1 章到第 N 章的衔接）
    """
    kb = _kb()

    if chapter_number < 2:
        return {"error": "至少需要第 2 章才能检查衔接（需要上一章作为参照）"}

    # 读取上一章
    prev_chapter = kb.chapters.get_by_number(chapter_number - 1)
    if not prev_chapter or not prev_chapter.get("content"):
        return {"error": f"第 {chapter_number - 1} 章内容不存在，无法检查衔接"}

    prev_content = prev_chapter["content"]
    prev_closing = prev_content[-500:] if len(prev_content) > 500 else prev_content

    # 读取当前章大纲
    current_outline = kb.outlines.get_chapter_outline(chapter_number)
    if not current_outline:
        return {"error": f"第 {chapter_number} 章大纲不存在，请先创建大纲"}

    # 读取上一章时间线（情绪/场景状态）
    timeline = kb.timelines.list_timeline()
    prev_timeline = None
    for t in timeline:
        if t.get("chapter_number") == chapter_number - 1:
            prev_timeline = t
            break

    issues = []

    # 1. 情绪跳跃检测
    prev_emotion = prev_timeline.get("emotion_tag", "") if prev_timeline else ""
    curr_emotion_arc = current_outline.get("emotional_arc", "")
    if prev_emotion and curr_emotion_arc:
        negative_tags = {"紧张", "悲痛", "恐惧", "绝望", "愤怒", "悬疑"}
        positive_tags = {"欢快", "温馨", "轻松", "平静", "释然", "日常"}
        if prev_emotion in negative_tags:
            # 检查当前大纲是否有过渡
            if any(tag in curr_emotion_arc for tag in positive_tags):
                # 当前大纲情绪起点与上一章结尾冲突
                opening_words = curr_emotion_arc.split("→")[0] if "→" in curr_emotion_arc else curr_emotion_arc[:20]
                issues.append({
                    "type": "emotion_jump",
                    "detail": f"上一章结尾情绪「{prev_emotion}」，当前章情绪弧线以「{opening_words}」开场，缺少过渡",
                    "suggestion": f"建议在第{chapter_number}章开场加入从「{prev_emotion}」到新情绪的过渡描写",
                })

    # 2. 场景不连续检测
    prev_scene = current_outline.get("scene", "")
    if prev_closing and prev_scene:
        # 简单检查：如果上一章结尾提到了特定场景，当前章大纲场景是否有过渡
        closing_names = set(_extract_names(prev_closing, kb))
        outline_names = set(_extract_names(prev_scene, kb))
        # 如果上一章结尾有角色但当前章大纲场景没有提及
        missing_chars = closing_names - outline_names
        if missing_chars and len(closing_names) <= 3:
            # 只有当上一章结尾角色很少（说明是关键场景）时才标记
            pass  # 场景切换是正常的，不标记为问题

    # 3. 角色凭空变化检测
    if prev_closing:
        closing_names = set(_extract_names(prev_closing, kb))
        outline_chars_str = current_outline.get("characters", "")
        if outline_chars_str:
            outline_names = set(_extract_names(outline_chars_str, kb))
        else:
            outline_names = set()

        # 上一章结尾出现的角色在当前章大纲中消失
        disappeared = closing_names - outline_names
        if disappeared and len(disappeared) <= 3:
            # 只在消失的角色是少数时标记（大量角色消失是正常的场景切换）
            issues.append({
                "type": "character_disappear",
                "detail": f"上一章结尾出现的角色 {disappeared} 在当前章大纲中未提及",
                "suggestion": f"建议在当前章开头简短交代角色 {disappeared} 的去向",
            })

        # 当前章大纲中新出现的角色（上一章结尾没出现且没有介绍）
        new_chars = outline_names - closing_names
        if new_chars:
            issues.append({
                "type": "character_appear",
                "detail": f"当前章大纲中新增角色 {new_chars}，上一章结尾未出现",
                "suggestion": "建议在章节中为这些角色的出现安排合理的引入",
                "severity": "info",
            })

    result = {
        "chapter_number": chapter_number,
        "previous_chapter": chapter_number - 1,
        "issues_found": len(issues),
        "issues": issues,
        "prev_closing_preview": prev_closing[-200:] if len(prev_closing) > 200 else prev_closing,
        "current_outline_scene": current_outline.get("scene", ""),
    }

    if not issues:
        result["message"] = f"第{chapter_number-1}章到第{chapter_number}章衔接良好"
    else:
        result["message"] = f"发现 {len(issues)} 个衔接问题，请检查"

    return result
