"""全书一致性扫描工具

R10 修正：新增 chapter_range 和 max_issues 参数控制扫描范围。
不调用 LLM，纯规则扫描。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def consistency_scan(
    check_types: str = "all",
    chapter_range: str = "recent",
    max_issues: int = 20,
) -> dict:
    """全书一致性扫描。自动检测角色行为矛盾、时间线矛盾和设定引用矛盾。

    不调用 LLM，纯规则扫描。适合长篇小说定期检查。

    Args:
        check_types: 检查类型 - "character"(角色), "timeline"(时间线),
                     "setting"(设定), 或 "all"
        chapter_range: 扫描范围 - "recent"(最近20章), "all"(全书),
                       或 JSON 列表如 "[1,5,10]" 指定章节
        max_issues: 最多返回的矛盾数量（默认 20）
    """
    kb = _kb()
    issues = []

    # 解析章节范围
    chapter_nums = None
    if chapter_range not in ("recent", "all"):
        chapter_nums, warn = parse_json_param(chapter_range, [], "chapter_range")

    # 获取数据
    timeline = kb.timelines.list_timeline()
    chars = kb.characters.list_characters()
    ws = kb.world_setting.get()

    # 确定扫描范围
    recent_n = 20
    if chapter_range == "recent" and timeline:
        scan_timeline = timeline[:recent_n]
    elif chapter_nums:
        scan_timeline = [t for t in timeline if t.get("chapter_number") in chapter_nums]
    else:
        scan_timeline = timeline

    scan_chapter_numbers = list(set(t.get("chapter_number", 0) for t in scan_timeline))
    scan_chapter_numbers.sort()

    # 1. 角色行为矛盾检测
    if check_types in ("all", "character") and scan_timeline:
        emotion_by_chapter = {}
        for t in scan_timeline:
            ch = t.get("chapter_number")
            tag = t.get("emotion_tag", "")
            if ch and tag:
                emotion_by_chapter[ch] = tag

        # F1: 检测情绪凝固（3+章相同情绪）+ 跳跃检测
        sorted_chapters = sorted(emotion_by_chapter.keys())
        
        # 情绪凝固检测
        if len(sorted_chapters) >= 3:
            same_count = 1
            start_ch = sorted_chapters[0]
            for i in range(1, len(sorted_chapters)):
                if emotion_by_chapter[sorted_chapters[i]] == emotion_by_chapter[sorted_chapters[i-1]]:
                    same_count += 1
                else:
                    if same_count >= 3:
                        issues.append({
                            "type": "emotion_stagnation",
                            "chapters": list(range(start_ch, sorted_chapters[i-1] + 1)),
                            "detail": f"情绪凝固：第{start_ch}-{sorted_chapters[i-1]}章连续 {same_count} 章情绪相同「{emotion_by_chapter[start_ch]}」",
                            "confidence": "medium",
                        })
                    same_count = 1
                    start_ch = sorted_chapters[i]
            # Check last run
            if same_count >= 3:
                issues.append({
                    "type": "emotion_stagnation",
                    "chapters": list(range(start_ch, sorted_chapters[-1] + 1)),
                    "detail": f"情绪凝固：第{start_ch}-{sorted_chapters[-1]}章连续 {same_count} 章情绪相同「{emotion_by_chapter[start_ch]}」",
                    "confidence": "medium",
                })

        # 情绪跳跃检测：负→正 和 正→负
        negative_tags = {"紧张", "悲痛", "恐惧", "绝望", "愤怒"}
        positive_tags = {"欢快", "温馨", "轻松", "平静", "释然"}
        for i in range(1, len(sorted_chapters)):
            prev_tag = emotion_by_chapter[sorted_chapters[i - 1]]
            curr_tag = emotion_by_chapter[sorted_chapters[i]]
            if prev_tag in negative_tags and curr_tag in positive_tags:
                issues.append({
                    "type": "emotion_jump_negative_to_positive",
                    "chapters": [sorted_chapters[i - 1], sorted_chapters[i]],
                    "detail": f"情绪跳跃(负→正)：第{sorted_chapters[i-1]}章「{prev_tag}」→ 第{sorted_chapters[i]}章「{curr_tag}」",
                    "confidence": "medium",
                })
            elif prev_tag in positive_tags and curr_tag in negative_tags:
                issues.append({
                    "type": "emotion_jump_positive_to_negative",
                    "chapters": [sorted_chapters[i - 1], sorted_chapters[i]],
                    "detail": f"情绪跳跃(正→负)：第{sorted_chapters[i-1]}章「{prev_tag}」→ 第{sorted_chapters[i]}章「{curr_tag}」",
                    "confidence": "medium",
                })

    # 2. 时间线矛盾检测
    if check_types in ("all", "timeline") and scan_timeline:
        chapter_order = []
        for t in scan_timeline:
            ch = t.get("chapter_number")
            if ch is not None:
                chapter_order.append((ch, t.get("summary", "")))

        # 检测章节号顺序不一致
        for i in range(1, len(chapter_order)):
            if chapter_order[i][0] <= chapter_order[i - 1][0]:
                issues.append({
                    "type": "timeline_order",
                    "chapters": [chapter_order[i - 1][0], chapter_order[i][0]],
                    "detail": f"时间线章节号顺序异常：{chapter_order[i-1][0]} → {chapter_order[i][0]}",
                    "confidence": "high",
                })

    # 3. 设定引用矛盾检测
    # F3: 新增伏笔检查类型
    if check_types in ("all", "foreshadowing"):
        all_fs = kb.foreshadowings.list_foreshadowings()
        for fs in all_fs:
            planted = fs.get("planted_chapter")
            expected = fs.get("expected_resolve_chapter")
            status = fs.get("status")
            
            # 检查：提出章节 > 预期解决章节
            if planted and expected and planted > expected:
                issues.append({
                    "type": "foreshadowing_impossible_timing",
                    "chapters": [planted, expected],
                    "detail": f"伏笔「{(fs.get('content') or '')[:30]}」提出章节{planted} > 预期解决章节{expected}",
                    "confidence": "high",
                })
            
            # 检查：active 状态但超期 5+ 章
            if status == "active" and expected:
                # Find latest written chapter
                latest_ch = max((t.get("chapter_number", 0) for t in timeline), default=0)
                if latest_ch - expected >= 5:
                    issues.append({
                        "type": "foreshadowing_overdue",
                        "chapters": [planted, expected],
                        "detail": f"伏笔「{(fs.get('content') or '')[:30]}」已超期{latest_ch - expected}章未回收",
                        "confidence": "medium",
                    })
            
            # 检查：reclaimed 状态但 resolved_chapter 为空
            if status == "reclaimed" and not fs.get("resolved_chapter"):
                issues.append({
                    "type": "foreshadowing_missing_resolve_chapter",
                    "chapters": [planted],
                    "detail": f"伏笔「{(fs.get('content') or '')[:30]}」状态为reclaimed但未记录回收章节",
                    "confidence": "low",
                })

    if check_types in ("all", "setting") and ws:
        red_rules = (ws.get("tiered_settings") or {}).get("red", [])
        if red_rules and scan_chapter_numbers:
            # 检查章节是否引用了红色设定关键词
            for ch_num in scan_chapter_numbers:
                try:
                    chapter = kb.chapters.get_by_number(ch_num)
                    if chapter and chapter.get("content"):
                        ch_content = chapter["content"]
                        for rule in red_rules[:5]:
                            rule_text = rule if isinstance(rule, str) else rule.get("text", "")
                            if rule_text and len(rule_text) >= 6 and rule_text in ch_content:
                                # F2: confidence 区分 - 字符串匹配vs分词匹配
                                issues.append({
                                    "type": "setting_reference",
                                    "chapters": [ch_num],
                                    "detail": f"第{ch_num}章引用了红色设定「{rule_text[:30]}」，请检查是否遵守",
                                    "confidence": "high",
                                    "rule_preview": rule_text[:60],
                                })
                except Exception:
                    pass

    # 截断结果
    total_issues = len(issues)
    issues = issues[:max_issues]

    result = {
        "scan_chapters": len(scan_chapter_numbers),
        "chapter_range": chapter_range,
        "check_types": check_types,
        "issues_found": total_issues,
        "issues": issues,
        "message": f"扫描 {len(scan_chapter_numbers)} 章，发现 {total_issues} 个疑似矛盾" if total_issues else f"扫描 {len(scan_chapter_numbers)} 章，未发现明显矛盾",
    }
    if total_issues > max_issues:
        result["truncated"] = True
        result["note"] = f"实际发现 {total_issues} 个问题，仅返回前 {max_issues} 个"
    return result
