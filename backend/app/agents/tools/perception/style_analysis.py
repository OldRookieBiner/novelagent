"""风格分析工具

B3 增强：情感词汇密度 + 修辞统计 + 锚点对比。
读取章节实际内容进行分析，无内容时降级为快照统计。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _compare_with_anchor


# 情感词库
_EMOTION_WORDS = {
    "紧张": ["紧张", "焦急", "不安", "忐忑", "紧绷", "慌张", "惊恐", "恐惧", "压迫", "窒息"],
    "悲伤": ["悲伤", "哀痛", "凄凉", "落寞", "心碎", "眼泪", "哭泣", "绝望", "黯然", "哽咽"],
    "温暖": ["温暖", "温馨", "柔情", "眷恋", "感动", "微笑", "拥抱", "守护", "慰藉", "安心"],
    "愤怒": ["愤怒", "暴怒", "咆哮", "怒火", "杀意", "恨意", "咬牙", "瞪眼", "拳头", "摔"],
    "欢快": ["欢快", "喜悦", "大笑", "兴奋", "雀跃", "轻松", "惬意", "畅快", "愉悦", "灿烂"],
}

# 修辞模式（简化版，基于中文常见标志词）
_RHETORIC_PATTERNS = {
    "比喻": ["像", "如同", "仿佛", "宛如", "犹如", "好似", "一般", "似的", "般"],
    "夸张": ["极", "无比", "绝不", "千万", "无尽", "滔天", "惊天", "震天", "万里"],
    "排比": None,  # 排比需要结构分析，用句式重复检测
}


def _count_emotion_density(content: str) -> dict:
    """统计文本中各情感类别的词频密度"""
    if not content:
        return {}
    char_count = len(content)
    if char_count == 0:
        return {}
    result = {}
    for emotion, words in _EMOTION_WORDS.items():
        count = sum(content.count(w) for w in words)
        # 密度 = 每千字出现次数
        density = round(count / char_count * 1000, 2)
        result[emotion] = {
            "count": count,
            "density_per_1k": density,
        }
    return result


def _count_rhetoric(content: str) -> dict:
    """统计文本中的修辞手法频次"""
    if not content:
        return {}
    result = {}
    for category, markers in _RHETORIC_PATTERNS.items():
        if markers is None:
            # 排比检测：连续 3+ 个以相同字/词开头的短句
            # 简化方案：检测句号/逗号分隔的重复句首
            import re
            sentences = re.split(r"[，。！？；]", content)
            if len(sentences) >= 3:
                # 取前2个字作为句首指纹
                starters = [s.strip()[:2] for s in sentences if len(s.strip()) >= 2]
                # 统计连续相同句首
                parallel_count = 0
                for i in range(2, len(starters)):
                    if starters[i] == starters[i-1] == starters[i-2]:
                        parallel_count += 1
                result[category] = parallel_count
            else:
                result[category] = 0
        else:
            count = sum(content.count(m) for m in markers)
            result[category] = count
    return result


@tool
async def style_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze writing style trends and detect drift.

    Use when the user asks about style consistency, dialogue ratio,
    or whether recent chapters are drifting from the established style.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    snapshots = kb.get_style_snapshots(last_n=last_n_chapters)

    if not snapshots:
        return {"has_data": False, "message": "尚无风格统计数据，需要先写几章后才能分析"}

    avg_dialogue = sum(s.dialogue_ratio for s in snapshots if s.dialogue_ratio) / max(len(snapshots), 1)
    avg_sent_len = sum(s.avg_sentence_length for s in snapshots if s.avg_sentence_length) / max(len(snapshots), 1)
    avg_para_len = sum(s.avg_paragraph_length for s in snapshots if s.avg_paragraph_length) / max(len(snapshots), 1)

    drift = {}
    if len(snapshots) >= 3:
        recent_3 = snapshots[:3]
        recent_dialogue = sum(s.dialogue_ratio for s in recent_3) / 3
        recent_sent = sum(s.avg_sentence_length for s in recent_3) / 3

        if avg_dialogue > 0 and abs(recent_dialogue - avg_dialogue) / avg_dialogue > 0.25:
            drift["dialogue_ratio"] = {
                "overall_avg": round(avg_dialogue, 3),
                "recent_avg": round(recent_dialogue, 3),
                "direction": "偏高" if recent_dialogue > avg_dialogue else "偏低",
            }
        if avg_sent_len > 0 and abs(recent_sent - avg_sent_len) / avg_sent_len > 0.25:
            drift["sentence_length"] = {
                "overall_avg": round(avg_sent_len, 1),
                "recent_avg": round(recent_sent, 1),
                "direction": "偏长" if recent_sent > avg_sent_len else "偏短",
            }

    result = {
        "has_data": True,
        "overall_averages": {
            "dialogue_ratio": round(avg_dialogue, 3),
            "avg_sentence_length": round(avg_sent_len, 1),
            "avg_paragraph_length": round(avg_para_len, 1),
        },
        "snapshots": [
            {
                "chapter": s.chapter_number,
                "dialogue_ratio": s.dialogue_ratio,
                "avg_sentence_length": s.avg_sentence_length,
                "paragraph_count": s.paragraph_count,
            }
            for s in snapshots
        ],
        "drift_detection": drift if drift else "风格稳定，未检测到漂移",
    }

    # B3 增强：读取最近章节的实际内容进行分析
    recent_chapter_numbers = [s.chapter_number for s in snapshots[:5] if s.chapter_number]
    collected_content = ""
    chapters_analyzed = 0
    for ch_num in recent_chapter_numbers:
        chapter = kb.get_chapter_by_number(ch_num)
        if chapter and chapter.content:
            collected_content += chapter.content + "\n"
            chapters_analyzed += 1

    if collected_content:
        # B3 增强：情感词汇密度（实际计算）
        emotion_density = _count_emotion_density(collected_content)
        result["emotion_vocabulary"] = {
            "chapters_analyzed": chapters_analyzed,
            "total_chars": len(collected_content),
            "density": emotion_density,
        }

        # B3 增强：修辞统计（实际计算）
        rhetoric = _count_rhetoric(collected_content)
        result["rhetoric_stats"] = {
            "chapters_analyzed": chapters_analyzed,
            "counts": rhetoric,
        }

        # B3 增强：风格锚点对比（用实际内容）
        style = kb.get_style_constraints()
        if style and style.style_anchor:
            anchor_comparison = _compare_with_anchor(collected_content, style.style_anchor)
            result["anchor_comparison"] = {
                "anchor_preview": style.style_anchor[:100],
                "match_rate": anchor_comparison["match_rate"],
                "anchor_words": anchor_comparison["anchor_words"],
                "found_words": anchor_comparison["found_words"],
            }
    else:
        # 无章节内容时降级为快照级统计
        result["emotion_vocabulary"] = {"note": "无章节内容可用，需要先写几章"}
        result["rhetoric_stats"] = {"note": "无章节内容可用，需要先写几章"}

    if drift:
        result["warning"] = "检测到风格漂移，建议检查最近几章的写作风格"
    return result
