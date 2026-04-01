# cli.py
"""NovelAgent CLI 入口"""

import argparse
import sys
from core.state import ProjectState, list_projects, project_exists
from agents.outline_agent import OutlineAgent


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

    # 进入对话循环
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
            print(f"{role}: {msg['content'][:100]}...")
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
            print(f"  - {key}: {value[:50]}...")

    outline = state.get_outline()
    if outline:
        print("\n大纲:")
        print(outline.get("raw", "")[:200] + "...")


def conversation_loop(agent: OutlineAgent, state: ProjectState):
    """对话循环"""
    print("(输入 'quit' 退出，'status' 查看状态)\n")

    while True:
        try:
            user_input = input("你: ").strip()

            if not user_input:
                continue

            if user_input == "quit":
                print("已保存进度，下次使用 continue 命令继续")
                break

            if user_input == "status":
                cmd_status(type('Args', (), {'name': state.project_name})())
                continue

            response = agent.process_user_input(user_input)
            print(f"\n[大纲Agent] {response}\n")

            # 检查是否完成
            if state.get_stage() == "completed":
                print("阶段1已完成！")
                break

        except KeyboardInterrupt:
            print("\n已保存进度，下次使用 continue 命令继续")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            print("已保存进度，请检查后继续")


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