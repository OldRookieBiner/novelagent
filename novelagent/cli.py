# cli.py
"""NovelAgent CLI 入口"""

import argparse
import sys
from core.state import ProjectState, list_projects, project_exists
from agents.outline_agent import OutlineAgent
from agents.writing_agent import WritingAgent
from agents.review_agent import ReviewAgent


def cmd_new(args):
    """创建新项目"""
    project_name = args.name

    if project_exists(project_name):
        print(f"项目 '{project_name}' 已存在，请使用 continue 命令继续")
        return

    state = ProjectState(project_name)
    print(f"已创建新项目: {project_name}")
    print("开始与大纲Agent对话，收集小说创作信息...\n")

    agent = OutlineAgent(state)
    print("[大纲Agent] 你好！请告诉我你想写什么样的小说？比如题材、主角、背景等。")

    conversation_loop(agent, state)


def cmd_continue(args):
    """继续现有项目"""
    project_name = args.name

    if not project_exists(project_name):
        print(f"项目 '{project_name}' 不存在，请使用 new 命令创建")
        return

    state = ProjectState(project_name)
    print(f"继续项目: {project_name}")
    print(f"当前阶段: {state.get_stage()}\n")

    agent = OutlineAgent(state)

    # 显示最后几条对话
    history = state.get_conversation_history()
    if history:
        print("=== 最近对话 ===")
        for msg in history[-4:]:
            role = "你" if msg["role"] == "user" else "[大纲Agent]"
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            print(f"{role}: {content}")
        print("================\n")

    conversation_loop(agent, state)


def cmd_list(args):
    """列出所有项目"""
    projects = list_projects()

    if not projects:
        print("暂无项目，使用 new 命令创建")
        return

    print("项目列表:")
    print("-" * 60)
    for p in projects:
        status = "已完成" if p["outline_confirmed"] else p["stage"]
        print(f"  {p['project_name']} - {status}")
    print("-" * 60)


def cmd_status(args):
    """查看项目状态"""
    project_name = args.name

    if not project_exists(project_name):
        print(f"项目 '{project_name}' 不存在")
        return

    state = ProjectState(project_name)

    print(f"项目: {project_name}")
    print(f"创建时间: {state.data.get('created_at')}")
    print(f"更新时间: {state.data.get('updated_at')}")
    print(f"阶段: {state.get_stage()}")
    print(f"大纲确认: {state.is_outline_confirmed()}")

    info = state.get_collected_info()
    if info:
        print("\n已收集信息:")
        for key, value in info.items():
            val_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            print(f"  - {key}: {val_str}")

    outline = state.get_outline()
    if outline:
        outline_str = outline.get("raw", "")[:200]
        print(f"\n大纲: {outline_str}...")

    # 显示卷纲信息
    volumes = state.get_volumes()
    if volumes:
        print(f"\n卷纲: 共 {len(volumes)} 卷")
        for i, v in enumerate(volumes):
            units_count = len(v.get("units", []))
            print(f"  第{i+1}卷: {units_count} 个单元")

    # 显示进度
    progress = state.get_progress_summary()
    if progress.get("total_words", 0) > 0:
        print(f"\n进度: 已写 {progress['total_words']} 字")


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
                elif result == "next_volume":
                    # 需要生成新单元纲，回到大纲Agent
                    writing_agent = None
                    review_agent = None
                    continue
                else:
                    user_input = input("你: ").strip()
                    if user_input == "quit":
                        print("已保存进度，下次使用 continue 命令继续")
                        break
                    elif user_input == "继续" or user_input == "审核":
                        continue
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
        print("[系统] 无法获取当前章节信息")
        return "error"

    chapter_title = chapter.get("title", f"第{chapter_idx + 1}章")

    # 如果章节已完成，检查是否需要进入下一章
    if chapter.get("review_passed"):
        return move_to_next_chapter(state, vol_idx, unit_idx, chapter_idx)

    # 如果章节内容已生成但未审核
    if chapter.get("content") and not chapter.get("review_passed"):
        print(f"\n[系统] 第{chapter_idx + 1}章《{chapter_title}》已有内容，正在审核...")
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
            content_preview = new_content[:500] + "..." if len(new_content) > 500 else new_content
            print(f"\n[写作Agent] 已重写第{chapter_idx + 1}章：\n\n{content_preview}\n")
            print("(输入 '继续' 进行审核，或 'quit' 退出)")
            return "rewrite"

    # 生成新章节
    print(f"\n[系统] 开始生成第{chapter_idx + 1}章《{chapter_title}》...")

    # 获取上一章结尾
    prev_ending = ""
    if chapter_idx > 0:
        prev_chapter = state.get_chapter(vol_idx, unit_idx, chapter_idx - 1)
        if prev_chapter and prev_chapter.get("content"):
            prev_ending = prev_chapter["content"][-500:]
    elif unit_idx > 0:
        # 上一单元的最后一章
        volumes = state.get_volumes()
        if vol_idx < len(volumes) and unit_idx - 1 < len(volumes[vol_idx].get("units", [])):
            prev_units = volumes[vol_idx]["units"]
            prev_unit = prev_units[unit_idx - 1]
            prev_chapters = prev_unit.get("chapters", [])
            if prev_chapters and prev_chapters[-1].get("content"):
                prev_ending = prev_chapters[-1]["content"][-500:]

    content = writing_agent.generate_chapter_content(chapter, prev_ending)
    chapter["content"] = content
    state.update_chapter(vol_idx, unit_idx, chapter_idx, chapter)

    content_preview = content[:800] + "..." if len(content) > 800 else content
    print(f"\n[写作Agent] 第{chapter_idx + 1}章《{chapter_title}》已生成：\n\n{content_preview}\n")
    print("(输入 '审核' 进行审核，或提出修改意见，或 'quit' 退出)")

    return "waiting"


def move_to_next_chapter(state: ProjectState, vol_idx: int, unit_idx: int, chapter_idx: int) -> str:
    """移动到下一章"""
    volumes = state.get_volumes()
    if vol_idx >= len(volumes):
        return "error"

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


def main():
    parser = argparse.ArgumentParser(description="NovelAgent - AI 小说创作助手")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # new 命令
    new_parser = subparsers.add_parser("new", help="创建新项目")
    new_parser.add_argument("name", help="项目名称")
    new_parser.set_defaults(func=cmd_new)

    # continue 命令
    continue_parser = subparsers.add_parser("continue", help="继续现有项目")
    continue_parser.add_argument("name", help="项目名称")
    continue_parser.set_defaults(func=cmd_continue)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有项目")
    list_parser.set_defaults(func=cmd_list)

    # status 命令
    status_parser = subparsers.add_parser("status", help="查看项目状态")
    status_parser.add_argument("name", help="项目名称")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()