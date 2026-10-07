"""오류 응답을 `{"error": "코드", "message": "안내 문구"}` 하나로 통일한다.

FastAPI 기본 오류 응답(`{"detail": ...}`)도 여기서 같은 형식으로 바꾼다.
직접 오류를 낼 때는 HTTPException 대신 `AppError` 를 쓴다.

    raise AppError(504, "AI_TIMEOUT", "응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요.")
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log_event

logger = logging.getLogger(__name__)

VALIDATION_MESSAGE = "입력값이 올바르지 않습니다."
INTERNAL_MESSAGE = "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

# 프레임워크가 내는 오류(없는 경로, 허용되지 않은 메서드 등)의 코드·안내 문구
_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "잘못된 요청입니다."),
    401: ("UNAUTHORIZED", "로그인이 필요합니다."),
    403: ("FORBIDDEN", "접근 권한이 없습니다."),
    404: ("NOT_FOUND", "요청한 경로를 찾을 수 없습니다."),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않은 요청 방식입니다."),
}
_FALLBACK_HTTP_ERROR = ("HTTP_ERROR", "요청을 처리할 수 없습니다.")


class AppError(Exception):
    """우리 코드가 직접 발생시키는 오류. 상태 코드·오류 코드·안내 문구를 그대로 응답한다."""

    def __init__(self, status_code: int, error: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message


def error_response(
    status_code: int, error: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message},
        headers=headers,
    )


def internal_error_response() -> JSONResponse:
    """처리되지 않은 예외에 대한 500 응답. 원인은 로그에만 남기고 응답에는 드러내지 않는다."""
    return error_response(500, "INTERNAL_ERROR", INTERNAL_MESSAGE)


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.error, exc.message)


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    error, message = _HTTP_ERRORS.get(exc.status_code, _FALLBACK_HTTP_ERROR)
    return error_response(exc.status_code, error, message, headers=exc.headers)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # 응답은 고정 문구만, 상세는 로그에. 단 입력값(err["input"])은 비밀번호일 수 있어 남기지 않는다.
    details = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}:{err['type']}" for err in exc.errors()
    )
    log_event(logger, "validation_failed", errors=details)
    return error_response(422, "VALIDATION_ERROR", VALIDATION_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
