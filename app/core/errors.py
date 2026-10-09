"""오류 응답을 `{"error": "코드", "message": "안내 문구"}` 하나로 통일한다.

FastAPI 기본 오류 응답(`{"detail": ...}`)도 여기서 같은 형식으로 바꾼다.
직접 오류를 낼 때는 HTTPException 대신 `AppError` 를 쓴다.

    raise AppError(403, ErrorCode.FORBIDDEN, "관리자만 볼 수 있습니다.")

/docs 에 오류 응답을 표시하려면 라우트에 `responses=error_responses(401, 409)` 를 붙인다.
"""

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log_event

logger = logging.getLogger(__name__)

VALIDATION_MESSAGE = "입력값이 올바르지 않습니다."
INTERNAL_MESSAGE = "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


class ErrorCode(StrEnum):
    """오류 응답 `error` 값의 전체 목록. 새 코드는 여기와 ERROR_CODE_DOCS 에 함께 추가한다."""

    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    USERNAME_TAKEN = "USERNAME_TAKEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# /docs 의 오류 코드 표에 그대로 나간다.
ERROR_CODE_DOCS: dict[ErrorCode, str] = {
    ErrorCode.BAD_REQUEST: "400 — 요청 형식이 잘못됨",
    ErrorCode.UNAUTHORIZED: "401 — 로그인이 필요하거나 토큰이 만료됨",
    ErrorCode.FORBIDDEN: "403 — 접근 권한이 없음",
    ErrorCode.NOT_FOUND: "404 — 없는 경로 또는 리소스",
    ErrorCode.METHOD_NOT_ALLOWED: "405 — 허용되지 않은 요청 방식",
    ErrorCode.VALIDATION_ERROR: "422 — 입력값 검증 실패. 어느 필드가 틀렸는지는 서버 로그에만 남는다",
    ErrorCode.USERNAME_TAKEN: "409 — 회원가입: 이미 쓰고 있는 아이디(대소문자 구분 없음)",
    ErrorCode.INVALID_CREDENTIALS: "401 — 로그인: 아이디 또는 비밀번호가 틀림(어느 쪽인지 알려주지 않음)",
    ErrorCode.HTTP_ERROR: "그 밖의 HTTP 오류",
    ErrorCode.INTERNAL_ERROR: "500 — 처리되지 않은 서버 오류. 원인은 서버 로그에만 남는다",
}

# 프레임워크가 내는 오류(없는 경로, 허용되지 않은 메서드 등)의 코드·안내 문구
_HTTP_ERRORS: dict[int, tuple[ErrorCode, str]] = {
    400: (ErrorCode.BAD_REQUEST, "잘못된 요청입니다."),
    401: (ErrorCode.UNAUTHORIZED, "로그인이 필요합니다."),
    403: (ErrorCode.FORBIDDEN, "접근 권한이 없습니다."),
    404: (ErrorCode.NOT_FOUND, "요청한 경로를 찾을 수 없습니다."),
    405: (ErrorCode.METHOD_NOT_ALLOWED, "허용되지 않은 요청 방식입니다."),
}
_FALLBACK_HTTP_ERROR = (ErrorCode.HTTP_ERROR, "요청을 처리할 수 없습니다.")

# error_responses() 가 /docs 에 붙이는 상태 코드별 설명
_STATUS_DESCRIPTIONS: dict[int, str] = {
    400: "잘못된 요청",
    401: "로그인 필요 또는 인증 실패",
    403: "권한 없음",
    404: "찾을 수 없음",
    409: "이미 존재함",
    422: "입력값 검증 실패",
    500: "서버 오류",
    504: "외부 서비스 응답 지연",
}


class ErrorResponse(BaseModel):
    """모든 오류 응답의 형식."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"error": "VALIDATION_ERROR", "message": VALIDATION_MESSAGE}]
        }
    )

    error: ErrorCode = Field(description="오류 코드 — 프론트는 이 값으로 분기한다")
    message: str = Field(description="사용자에게 그대로 보여줘도 되는 안내 문구")


class AppError(Exception):
    """우리 코드가 직접 발생시키는 오류. 상태 코드·오류 코드·안내 문구를 그대로 응답한다.

    `headers` 는 응답 헤더에 그대로 붙는다(예: 401 의 `WWW-Authenticate: Bearer`).
    """

    def __init__(
        self,
        status_code: int,
        error: ErrorCode,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.headers = headers


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """라우트의 `responses=` 에 넘기면 /docs 에 해당 오류 응답이 ErrorResponse 형식으로 표시된다."""
    return {
        code: {"model": ErrorResponse, "description": _STATUS_DESCRIPTIONS.get(code, "오류")}
        for code in status_codes
    }


def error_response(
    status_code: int, error: ErrorCode, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message},
        headers=headers,
    )


def internal_error_response() -> JSONResponse:
    """처리되지 않은 예외에 대한 500 응답. 원인은 로그에만 남기고 응답에는 드러내지 않는다."""
    return error_response(500, ErrorCode.INTERNAL_ERROR, INTERNAL_MESSAGE)


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.error, exc.message, headers=exc.headers)


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    error, message = _HTTP_ERRORS.get(exc.status_code, _FALLBACK_HTTP_ERROR)
    return error_response(exc.status_code, error, message, headers=exc.headers)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # 응답은 고정 문구만, 상세는 로그에. 단 입력값(err["input"])은 비밀번호일 수 있어 남기지 않는다.
    details = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}:{err['type']}" for err in exc.errors()
    )
    log_event(logger, "validation_failed", errors=details)
    return error_response(422, ErrorCode.VALIDATION_ERROR, VALIDATION_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
