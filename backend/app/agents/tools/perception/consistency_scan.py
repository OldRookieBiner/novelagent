"""一致性扫描工具（合并版）

合并原 consistency_scan、consistency_check、check_chapter_transition 三工具。
支持三种模式：full（全书扫描）、transition（章节衔接）、compare（两章比对）。
不调用 LLM，纯规则扫描。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param, _extract_names, _extract_times


@tool
async def consistency_scan(
    mode: str = "full",
    # full 模式参数
    check_types: str = "all",
    chapter_range: str = "recent",
    max_issues: int = 20,
    # transition 模式参数
    chapter_number: int = 0,
    # compare 模式参数
    chapter_a: int = 0,
    chapter_b: int = 0,
    aspect: str = "all",
) -> dict:
    """一致性扫描工具。支持三种模式检测一致性问题。

    - mode="full"：全书一致性扫描（默认），检测角色行为矛盾、时间线矛盾、设定引用矛盾
    - mode="transition"：章节衔接检查，分析上一章结尾与当前章大纲的连贯性
    - mode="compare"：两章比对检查，交叉分析角色行为和时间线一致性

    不调用 LLM，纯规则扫描。

    Args:
        mode: 扫描模式 - "full"(全书扫描), "transition"(章节衔接), "compare"(两章比对)
        check_types: [full] 检查类型 - "character", "timeline", "setting", "foreshadowing", 或 "all"
        chapter_range: [full] 扫描范围 - "recent"(最近20章), "all"(全书), 或 JSON 列表如 "[1,5,10]"
        max_issues: [full] 最多返回的矛盾数量（默认 20）
        chapter_number: [transition] 当前章节号（将检查第 N-1 章到第 N 章的衔接）
        chapter_a: [compare] 第一个章节号
        chapter_b: [compare] 第二个章节号
        aspect: [compare] 检查方面 - "character", "timeline", "setting", 或 "all"

    Returns:
        dict:
            - mode (str): 扫描模式 - "full" / "transition" / "compare"
            - issues_found (int): 发现的问题数量
            - issues (list): 问题列表，每个问题含 type/detail/suggestion 等字段
            - message (str): 扫描结果描述
            - truncated (bool, optional): 结果是否因数量过多截断
            - error (str, optional): 出错时的错误信息
            - 不同模式返回额外字段：full 模式含 scan_chapters, transition 模式含 prev_closing_preview 等
    """
    if mode not in ("full", "transition", "compare"):
        return {"error": f"mode 必须是 full/transition/compare 之一，收到: {mode}"}

    if mode == "transition":
        return await _scan_transition(chapter_number)
    elif mode == "compare":
        return await _scan_compare(chapter_a, chapter_b, aspect)
    else:
        return await _scan_full(check_types, chapter_range, max_issues)


async def _scan_full(check_types: str, chapter_range: str, max_issues: int) -> dict:
    """全书一致性扫描（原 consistency_scan 逻辑）"""
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
            # 检查最后一段
            if same_count >= 3:
                issues.append({
                    "type": "emotion_stagnation",
                    "chapters": list(range(start_ch, sorted_chapters[-1] + 1)),
                    "detail": f"情绪凝固：第{start_ch}-{sorted_chapters[-1]}章连续 {same_count} 章情绪相同「{emotion_by_chapter[start_ch]}」",
                    "confidence": "medium",
                })

        # 情绪跳跃检测
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

        for i in range(1, len(chapter_order)):
            if chapter_order[i][0] <= chapter_order[i - 1][0]:
                issues.append({
                    "type": "timeline_order",
                    "chapters": [chapter_order[i - 1][0], chapter_order[i][0]],
                    "detail": f"时间线章节号顺序异常：{chapter_order[i-1][0]} → {chapter_order[i][0]}",
                    "confidence": "high",
                })

    # 3. 伏笔检查
    if check_types in ("all", "foreshadowing"):
        all_fs = kb.foreshadowings.list_foreshadowings()
        for fs in all_fs:
            planted = fs.get("planted_chapter")
            expected = fs.get("expected_resolve_chapter")
            status = fs.get("status")

            if planted and expected and planted > expected:
                issues.append({
                    "type": "foreshadowing_impossible_timing",
                    "chapters": [planted, expected],
                    "detail": f"伏笔「{(fs.get('content') or '')[:30]}」提出章节{planted} > 预期解决章节{expected}",
                    "confidence": "high",
                })

            if status == "active" and expected:
                latest_ch = max((t.get("chapter_number", 0) for t in timeline), default=0)
                if latest_ch - expected >= 5:
                    issues.append({
                        "type": "foreshadowing_overdue",
                        "chapters": [planted, expected],
                        "detail": f"伏笔「{(fs.get('content') or '')[:30]}」已超期{latest_ch - expected}章未回收",
                        "confidence": "medium",
                    })

            if status == "reclaimed" and not fs.get("resolved_chapter"):
                issues.append({
                    "type": "foreshadowing_missing_resolve_chapter",
                    "chapters": [planted],
                    "detail": f"伏笔「{(fs.get('content') or '')[:30]}」状态为reclaimed但未记录回收章节",
                    "confidence": "low",
                })

    # 4. 设定引用矛盾检测
    if check_types in ("all", "setting") and ws:
        red_rules = (ws.get("tiered_settings") or {}).get("red", [])
        if red_rules and scan_chapter_numbers:
            for ch_num in scan_chapter_numbers:
                try:
                    chapter = kb.chapters.get_by_number(ch_num)
                    if chapter and chapter.get("content"):
                        ch_content = chapter["content"]
                        for rule in red_rules[:5]:
                            rule_text = rule if isinstance(rule, str) else rule.get("text", "")
                            if rule_text and len(rule_text) >= 6 and rule_text in ch_content:
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
        "mode": "full",
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


async def _scan_transition(chapter_number: int) -> dict:
    """章节衔接检查（原 check_chapter_transition 逻辑）"""
    kb = _kb()

    if chapter_number < 2:
        return {"mode": "transition", "error": "至少需要第 2 章才能检查衔接（需要上一章作为参照）"}

    # 读取上一章
    prev_chapter = kb.chapters.get_by_number(chapter_number - 1)
    if not prev_chapter or not prev_chapter.get("content"):
        return {"mode": "transition", "error": f"第 {chapter_number - 1} 章内容不存在，无法检查衔接"}

    prev_content = prev_chapter["content"]
    prev_closing = prev_content[-500:] if len(prev_content) > 500 else prev_content

    # 读取当前章大纲
    current_outline = kb.outlines.get_chapter_outline(chapter_number)
    if not current_outline:
        return {"mode": "transition", "error": f"第 {chapter_number} 章大纲不存在，请先创建大纲"}

    # 读取上一章时间线
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
            if any(tag in curr_emotion_arc for tag in positive_tags):
                opening_words = curr_emotion_arc.split("→")[0] if "→" in curr_emotion_arc else curr_emotion_arc[:20]
                issues.append({
                    "type": "emotion_jump",
                    "detail": f"上一章结尾情绪「{prev_emotion}」，当前章情绪弧线以「{opening_words}」开场，缺少过渡",
                    "suggestion": f"建议在第{chapter_number}章开场加入从「{prev_emotion}」到新情绪的过渡描写",
                })

    # 提取角色名
    closing_names = set(_extract_names(prev_closing, kb)) if prev_closing else set()
    outline_chars_str = current_outline.get("characters", "")
    outline_names = set(_extract_names(outline_chars_str, kb)) if outline_chars_str else set()

    # 2. 场景切换检测
    curr_scene = current_outline.get("scene", "")
    if prev_closing and curr_scene:
        scene_names = set(_extract_names(curr_scene, kb))
        missing_in_scene = closing_names - scene_names
        if missing_in_scene and len(closing_names) <= 3:
            issues.append({
                "type": "scene_transition",
                "detail": f"上一章结尾的角色 {missing_in_scene} 未出现在当前章场景「{curr_scene[:30]}」中",
                "suggestion": f"建议在章节开头简短交代场景切换，或说明角色 {missing_in_scene} 的去向",
                "severity": "info",
            })

    # 3. 角色凭空变化检测
    if closing_names or outline_names:
        disappeared = closing_names - outline_names
        if disappeared and len(disappeared) <= 3:
            issues.append({
                "type": "character_disappear",
                "detail": f"上一章结尾出现的角色 {disappeared} 在当前章大纲中未提及",
                "suggestion": f"建议在当前章开头简短交代角色 {disappeared} 的去向",
            })

        new_chars = outline_names - closing_names
        if new_chars:
            issues.append({
                "type": "character_appear",
                "detail": f"当前章大纲中新增角色 {new_chars}，上一章结尾未出现",
                "suggestion": "建议在章节中为这些角色的出现安排合理的引入",
                "severity": "info",
            })

    result = {
        "mode": "transition",
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


async def _scan_compare(chapter_a: int, chapter_b: int, aspect: str = "all") -> dict:
    """两章比对检查（原 consistency_check 逻辑）"""
    kb = _kb()
    result = {"mode": "compare", "chapters_compared": [chapter_a, chapter_b], "issues": []}

    # 读取两章内容
    chapter_a_obj = kb.chapters.get_by_number(chapter_a)
    chapter_b_obj = kb.chapters.get_by_number(chapter_b)
    content_a = chapter_a_obj.get("content", "") if chapter_a_obj else ""
    content_b = chapter_b_obj.get("content", "") if chapter_b_obj else ""

    if aspect in ("all", "character"):
        # 精确加载出场角色约束
        appearing_names = set()
        if content_a:
            appearing_names.update(_extract_names(content_a, kb))
        if content_b:
            appearing_names.update(_extract_names(content_b, kb))

        all_chars = kb.characters.list_characters()
        constraints = []
        for char in all_chars:
            if appearing_names and char["name"] not in appearing_names:
                continue
            constraints.append({
                "name": char["name"],
                "deep_fear": char.get("deep_fear") or "",
                "core_motivation": char.get("core_motivation") or "",
            })
        result["character_constraints"] = constraints

    if aspect in ("all", "timeline"):
        timeline = kb.timelines.list_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = timeline

    if aspect in ("all", "setting"):
        ws = kb.world_setting.get()
        if ws:
            result["world_setting_red"] = (ws.get("tiered_settings") or {}).get("red", [])

    # 章节内容交叉分析
    if aspect in ("all", "character", "timeline"):
        if content_a and content_b:
            names_a = set(_extract_names(content_a, kb))
            names_b = set(_extract_names(content_b, kb))
            common_names = names_a & names_b

            times_a = set(_extract_times(content_a))
            times_b = set(_extract_times(content_b))
            common_times = times_a & times_b

            cross_analysis = {
                "chapter_a_length": len(content_a),
                "chapter_b_length": len(content_b),
                "names_in_a": len(names_a),
                "names_in_b": len(names_b),
                "common_names": list(common_names)[:20],
                "times_in_a": len(times_a),
                "times_in_b": len(times_b),
                "common_times": list(common_times)[:10],
            }

            if common_names and aspect in ("all", "character"):
                cross_analysis["character_overlap_note"] = (
                    f"两章共同出现 {len(common_names)} 个角色名，请检查行为是否一致"
                )
            if common_times and aspect in ("all", "timeline"):
                cross_analysis["timeline_overlap_note"] = (
                    f"两章共同出现 {len(common_times)} 个时间表达，请检查时间线是否一致"
                )

            result["cross_analysis"] = cross_analysis
        else:
            result["cross_analysis"] = {
                "note": "一章或两章内容不存在，无法进行内容交叉分析"
            }

    if not result["issues"]:
        result["message"] = "未发现明显的逻辑矛盾。请提供具体的矛盾描述，我可以帮你进一步分析。"
    return result
