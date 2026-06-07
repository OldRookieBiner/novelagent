"""审查反馈路由器节点

根据 post_write_summary 和审查结果自动路由：
- 🔴 严重 → 触发 rewrite 重写当章
- 🟠 中等 → 生成 writing_constraints 注入下章
- 🟡 轻微 → 记录累积，3 次同类升级

这是必改三件套的第3件，确保审查结果闭环。
"""

import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.warning import WarningService

logger = logging.getLogger(__name__)

# 重写循环上限
MAX_REWRITE_COUNT = 2

# 轻微问题升级阈值
MINOR_ESCALATION_THRESHOLD = 3


def _classify_review_issues(post_write_summary: str, warnings: list) -> tuple[str, list]:
    """根据审查摘要和预警分类问题级别
    
    Returns:
        (severity, issue_list): 严重程度 + 具体问题列���
    """
    issues = []
    severity = "none"
    
    # 解析警告列表
    warning_types = {w.get("type", ""): w for w in warnings}
    
    # 🔴 严重问题检测
    severe_keywords = ["人设崩塌", "关键信息自相矛盾", "结构硬伤", "逻辑断裂", "OOC"]
    for keyword in severe_keywords:
        if keyword in post_write_summary or any(keyword in w.get("title", "") for w in warnings):
            severity = "severe"
            issues.append(f"严重：{keyword}")
            break
    
    # 检查伏笔回收错误（严重）
    if "伏笔回收错误" in post_write_summary or "回收逻辑错误" in post_write_summary:
        severity = "severe"
        issues.append("严重：伏笔回收逻辑错误")
    
    # 🟠 中等问题检测
    moderate_keywords = ["节奏拖沓", "场景导演未执行", "POV漂移", "风格漂移", "情绪断层"]
    if severity == "none":
        for keyword in moderate_keywords:
            if keyword in post_write_summary or any(keyword in w.get("title", "") for w in warnings):
                severity = "moderate"
                issues.append(f"中等：{keyword}")
                break
    
    # 检查超期伏笔数量
    if severity == "none":
        overdue_count = sum(1 for w in warnings if w.get("type") == "foreshadowing_overdue")
        if overdue_count >= 3:
            severity = "moderate"
            issues.append(f"中等：{overdue_count}个伏笔超期")
    
    # 🟡 轻微问题检测
    minor_keywords = ["用词可优化", "个别重复", "对话稍长", "细节可删"]
    if severity == "none":
        found_minor = []
        for keyword in minor_keywords:
            if keyword in post_write_summary:
                found_minor.append(keyword)
        if found_minor:
            severity = "minor"
            issues = [f"轻微：{k}" for k in found_minor]
    
    return severity, issues


async def feedback_router_node(state: NovelState) -> NovelState:
    """审查反馈路由器"""
    project_id = state["project_id"]
    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)
    
    # 获取本章内容
    written_chapter_num = current_chapter - 1
    chapter = None
    for ch in written_chapters:
        if ch.get("chapter_number") == written_chapter_num:
            chapter = ch
            break
    
    if not chapter:
        logger.warning(f"未找到第 {written_chapter_num} 章内容，跳过反馈路由")
        return {"writing_constraints": [], "rewrite_count": 0}
    
    # 获取 post_write_summary
    post_write_summary = state.get("post_write_summary", "")
    
    # 获取预警
    kb = KnowledgeBaseService(project_id)
    warning_service = WarningService(project_id)
    warnings = warning_service.check_all(written_chapter_num, state.get("current_volume", 1))
    
    # 分类问题
    severity, issues = _classify_review_issues(post_write_summary, warnings)
    
    logger.info(f"第 {written_chapter_num} 章审查结果：{severity}，问题：{issues}")
    
    # 获取当前重写计数
    rewrite_count = state.get("rewrite_count", 0)
    
    # 获取问题累积器
    issue_accumulator = state.get("issue_accumulator", {})
    
    result = {}
    
    if severity == "severe":
        # 🔴 严重问题：触发重写
        if rewrite_count < MAX_REWRITE_COUNT:
            # 重写当章
            rewrite_count += 1
            result["rewrite_count"] = rewrite_count
            result["rewrite_triggered"] = True
            result["rewrite_issues"] = issues
            logger.info(f"触发重写第 {written_chapter_num} 章，重写次数：{rewrite_count}")
        else:
            # 超过重写上限，强制继续并记录警告
            result["rewrite_count"] = rewrite_count
            result["rewrite_triggered"] = False
            result["rewrite_skipped"] = True
            logger.warning(f"第 {written_chapter_num} 章重写次数已达上限 {MAX_REWRITE_COUNT}，强制继续")
    
    elif severity == "moderate":
        # 🟠 中等問題：生成写作约束
        writing_constraints = [f"注意：{issue}" for issue in issues]
        result["writing_constraints"] = writing_constraints
        result["feedback_routed"] = "constraints"
        logger.info(f"生成写作约束：{writing_constraints}")
    
    elif severity == "minor":
        # 🟡 轻微问题：累积计数
        for issue in issues:
            # 提取问题类型
            issue_type = issue.split("：")[-1] if "：" in issue else issue
            current_count = issue_accumulator.get(issue_type, 0) + 1
            issue_accumulator[issue_type] = current_count
            
            # 检查是否需要升级为中等
            if current_count >= MINOR_ESCALATION_THRESHOLD:
                logger.info(f"轻微问题 '{issue_type}' 累积达��阈值 {MINOR_ESCALATION_THRESHOLD}，升级为中等")
                result["writing_constraints"] = [f"升级：{issue_type}"]
                # 累积问题降重
                issue_accumulator[issue_type] = 0
        
        result["issue_accumulator"] = issue_accumulator
        result["feedback_routed"] = "accumulated"
    
    else:
        # 无问题
        result["feedback_routed"] = "none"
        result["writing_constraints"] = []
    
    return result
