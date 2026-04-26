"""统一异常处理模块"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    """统一 API 错误类

    Attributes:
        code: 错误代码
        message: 错误消息
        status_code: HTTP 状态码
    """
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class APIErrorCode:
    """预定义错误代码"""
    # 认证相关
    UNAUTHORIZED = "unauthorized"
    INVALID_CREDENTIALS = "invalid_credentials"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"

    # 资源相关
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    PERMISSION_DENIED = "permission_denied"

    # 业务逻辑
    INVALID_INPUT = "invalid_input"
    WORKFLOW_ERROR = "workflow_error"
    LLM_ERROR = "llm_error"

    # 系统错误
    INTERNAL_ERROR = "internal_error"
    DATABASE_ERROR = "database_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """处理自定义 API 错误"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "detail": exc.message,  # 使用 detail 保持与 FastAPI 默认格式一致
            "message": exc.message,
            "path": str(request.url.path)
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理 HTTP 异常"""
    # 转换状态码为错误代码
    code_map = {
        400: APIErrorCode.INVALID_INPUT,
        401: APIErrorCode.UNAUTHORIZED,
        403: APIErrorCode.PERMISSION_DENIED,
        404: APIErrorCode.NOT_FOUND,
        429: APIErrorCode.RATE_LIMIT_EXCEEDED,
        500: APIErrorCode.INTERNAL_ERROR,
    }

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code_map.get(exc.status_code, APIErrorCode.INTERNAL_ERROR),
            "detail": exc.detail,  # 使用 detail 保持与 FastAPI 默认格式一致
            "message": exc.detail,
            "path": str(request.url.path)
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求验证错误"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": APIErrorCode.INVALID_INPUT,
            "message": "请求参数验证失败",
            "errors": errors,
            "path": str(request.url.path)
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的异常"""
    # 记录日志
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": APIErrorCode.INTERNAL_ERROR,
            "message": "服务器内部错误",
            "path": str(request.url.path)
        }
    )