# backend/app/agents/agent_graph.py

"""AI 搭档 Agent 图定义"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.agent_tools import AGENT_TOOLS
from app.services.llm import get_llm_service_from_config
from app.models.model_config import ModelConfig
from app.models.outline import Outline, ChapterOutline
from app.models.character import Character
from app.database import SessionLocal
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_project_context(project_id: int) -> dict:
    """构建项目上下文，注入 Agent system message"""
    db = SessionLocal()
    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        chapter_outlines = db.query(ChapterOutline).filter(ChapterOutline.project_id == project_id).order_by(ChapterOutline.chapter_number).all()

        return {
            "outline": {
                "title": outline.title if outline else None,
                "summary": outline.summary[:200] if outline and outline.summary else None,
                "confirmed": outline.confirmed if outline else False,
                "plot_points_count": len(outline.plot_points) if outline and outline.plot_points else 0,
            },
            "characters": [
                {"name": c.name, "role": c.role}
                for c in characters[:10]
            ],
            "chapter_outlines": {
                "total": len(chapter_outlines),
                "titles": [f"第{co.chapter_number}章: {co.title}" for co in chapter_outlines[:10]],
            },
        }
    finally:
        db.close()


def _get_llm_from_service(llm_service) -> ChatOpenAI:
    """将 LLMService 转换为 LangChain ChatOpenAI 兼容对象

    复用 LLMService 的 api_key/base_url/model 配置，
    保留 provider 级别的连接信息，但 tool calling 走 LangChain 协议。
    注意：这里不使用 LLMService 的 chat/chat_stream 方法，
    因为 create_react_agent 内部管理 LLM 调用。
    """
    return ChatOpenAI(
        model=llm_service.model,
        api_key=llm_service.api_key,
        base_url=llm_service.base_url,
        temperature=0.7,
    )


def create_agent_graph(model_config_id: int = None, user_id: int = None):
    """创建 Agent 图实例"""
    llm = None

    if model_config_id and user_id:
        db = SessionLocal()
        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
            if config:
                llm_service = get_llm_service_from_config(config, user_id)
                llm = _get_llm_from_service(llm_service)
        except Exception as e:
            logger.warning(f"Failed to get LLM from model config: {e}")
        finally:
            db.close()

    # 如果模型配置获取失败，尝试用户默认设置
    if llm is None and user_id:
        db = SessionLocal()
        try:
            from app.models.settings import UserSettings
            from app.services.llm import get_llm_service
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings:
                llm_service = get_llm_service(settings)
                llm = _get_llm_from_service(llm_service)
        except Exception as e:
            logger.warning(f"Failed to get LLM from user settings: {e}")
        finally:
            db.close()

    if llm is None:
        raise ValueError("无法获取 LLM 配置：请先在设置中配置 API Key")

    graph = create_react_agent(
        model=llm,
        tools=AGENT_TOOLS,
    )
    return graph
