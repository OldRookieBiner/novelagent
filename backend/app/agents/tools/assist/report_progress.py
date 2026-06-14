"""报告进度的辅助工具"""

from langchain_core.tools import tool


@tool
def report_progress(message: str, percent: int = 0) -> dict:
    """Report current progress to the user. Use this when performing long operations
    like writing a chapter or generating a large outline, to keep the user informed.

    Args:
        message: Human-readable progress description (e.g., '正在写第3章正文...')
        percent: Progress percentage 0-100
    """
    return {"progress_message": message, "progress_percent": percent}
