"""灵感对话 API — 独立端点，不走 LangGraph"""

import asyncio
import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.outline import Outline
from app.models.project import Project
from app.models.user import User
from app.models.model_config import ModelConfig
from app.services.llm import get_llm_service_from_config, get_llm_service, LLMService
from app.utils.auth import get_current_user
from app.utils.error import format_sse_error
from app.utils.project import get_project_for_user
from app.agents.constants import FIELD_INFERENCE_RULES, INSPIRATION_REQUIRED_FIELDS
from app.agents.prompts import DEFAULT_PROMPTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/inspiration", tags=["inspiration"])


class ChatRequest(BaseModel):
    message: str
    llm_config_id: Optional[int] = None  # 用户选择的模型配置 ID


class ConfirmRequest(BaseModel):
    inspiration_data: dict


def _infer_fields_from_text(text: str) -> dict:
    """从自由文本推断字段"""
    inferred = {}
    for keywords, fields in FIELD_INFERENCE_RULES:
        if any(kw in text for kw in keywords):
            inferred.update(fields)
    return inferred


def _get_missing_fields(extracted: dict) -> list[str]:
    """获取仍缺失的必填字段"""
    return [f for f in INSPIRATION_REQUIRED_FIELDS if f not in extracted or not extracted[f]]


@router.post("/chat")
async def chat_inspiration(
    project_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """灵感对话 — SSE 流式响应

    独立端点，不走 LangGraph。流式输出 LLM 回复，同时从对话中
    推断/提取创作参数字段。使用独立 SessionLocal 写入 DB，
    避免请求级 Session 在长流式操作期间失效。
    """
    project = get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        outline = Outline(project_id=project_id, collected_info={}, messages=[])
        db.add(outline)
        db.commit()
        db.refresh(outline)

    messages = outline.messages or []
    collected_info = outline.collected_info or {}
    extracted = collected_info.get("_extracted", {})

    # 客户端推断 + 合并
    client_inferred = _infer_fields_from_text(request.message)
    extracted.update(client_inferred)

    # 追加用户消息
    messages.append({"role": "user", "content": request.message})

    # 构建 LLM prompt
    missing = _get_missing_fields(extracted)
    if extracted:
        prompt_template = DEFAULT_PROMPTS.get(
            "inspiration_question",
            DEFAULT_PROMPTS.get("inspiration_extraction", ""),
        )
    else:
        prompt_template = DEFAULT_PROMPTS.get("inspiration_extraction", "")

    conversation_history = "\n".join(
        f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content']}"
        for m in messages[-6:]
    )

    prompt = prompt_template.format(
        free_text=request.message,
        extracted_fields=json.dumps(extracted, ensure_ascii=False),
        missing_fields=", ".join(missing) if missing else "无",
        conversation_history=conversation_history,
        user_message=request.message,
    )

    # 获取 LLM 服务（优先使用用户选择的模型配置）
    from app.models.settings import UserSettings
    from app.utils.deps import get_user_settings_or_raise

    user_settings = get_user_settings_or_raise(current_user, db)
    llm = _get_llm_for_inspiration(
        current_user.id, user_settings, db, request.llm_config_id
    )

    # SSE 流式生成（使用独立 DB Session 避免请求级 Session 在流式操作期间失效）

    async def generate():
        sse_db = SessionLocal()
        response_text = ""
        try:
            async for chunk in llm.chat_stream(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2048,
            ):
                response_text += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

            # 解析 LLM 响应中的 extracted 字段
            try:
                code_match = re.search(
                    r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text
                )
                if code_match:
                    data = json.loads(code_match.group(1))
                    new_extracted = data.get("extracted", {})
                    extracted.update(new_extracted)
            except (json.JSONDecodeError, Exception):
                pass

            # 保存对话和提取结果（使用 SSE 专用 Session）
            messages.append({"role": "assistant", "content": response_text})
            collected_info["_extracted"] = extracted
            sse_outline = (
                sse_db.query(Outline)
                .filter(Outline.project_id == project_id)
                .first()
            )
            if sse_outline:
                sse_outline.messages = messages
                sse_outline.collected_info = collected_info
                sse_db.commit()

            yield (
                f"event: extracted\ndata: "
                f"{json.dumps({'fields': extracted, 'missing': _get_missing_fields(extracted)})}\n\n"
            )
            yield (
                f"event: done\ndata: "
                f"{json.dumps({'message': '对话轮次完成'})}\n\n"
            )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("灵感对话生成错误")
            yield format_sse_error(e)
        finally:
            sse_db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm")
def confirm_inspiration(
    project_id: int,
    request: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认灵感采集结果，写入 collected_info"""
    project = get_project_for_user(project_id, current_user.id, db)

    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="大纲不存在",
        )

    collected_info = outline.collected_info or {}
    collected_info.update(request.inspiration_data)
    collected_info.pop("_extracted", None)
    outline.collected_info = collected_info
    db.commit()

    return {"status": "ok", "collected_info": collected_info}


def _get_llm_for_inspiration(
    user_id: int,
    user_settings,
    db: Session,
    llm_config_id: Optional[int] = None,
) -> LLMService:
    """获取灵感对话的 LLM 服务

    优先使用用户指定的模型配置，否则使用默认模型配置，
    最后回退到用户设置。

    Args:
        user_id: 用户 ID
        user_settings: 用户设置实例
        db: 数据库会话
        llm_config_id: 可选的模型配置 ID

    Returns:
        LLMService 实例
    """
    if llm_config_id:
        config = (
            db.query(ModelConfig)
            .filter(ModelConfig.id == llm_config_id, ModelConfig.user_id == user_id)
            .first()
        )
        if config:
            return get_llm_service_from_config(config, user_id)

    # 使用默认模型配置
    default_config = (
        db.query(ModelConfig)
        .filter(
            ModelConfig.user_id == user_id,
            ModelConfig.is_default,
            ModelConfig.is_enabled,
        )
        .first()
    )

    if default_config:
        return get_llm_service_from_config(default_config, user_id)

    # 兼容旧版本：使用用户设置
    return get_llm_service(user_settings)
