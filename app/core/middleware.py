"""요청 미들웨어 — 요청마다 request_id 를 만들고, 요청의 시작과 끝을 로그로 남긴다.

    request_received  request_id=a1b2c3 user_id=12 method=POST path=/api/chat
    ...               (같은 요청 안의 로그에는 같은 request_id·user_id 가 자동으로 붙는다)
    request_completed request_id=a1b2c3 user_id=12 status=200 duration_ms=1312

처리되지 않은 예외도 여기서 받아 `unhandled_error` 로그 + 500 응답으로 바꾼다.
FastAPI 의 다른 오류 처리기(AppError·404·422)는 이 미들웨어 안쪽에서 먼저 처리되므로,
여기까지 올라오는 예외는 정말로 아무도 처리하지 않은 것뿐이다.
"""

import logging
import time
import uuid
from collections.abc import Callable

from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import internal_error_response
from app.core.logging import log_event, request_id_var, user_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

UserIdResolver = Callable[[HTTPConnection], int | None]


def _no_user(_: HTTPConnection) -> int | None:
    return None


class RequestContextMiddleware:
    """`resolve_user_id` 는 요청의 토큰에서 user_id 를 꺼내는 함수(비로그인이면 None).
    인증 기능이 이 모듈을 import 하지 않도록, 함수를 밖에서 넘겨받는다.
    """

    def __init__(self, app: ASGIApp, resolve_user_id: UserIdResolver = _no_user) -> None:
        self.app = app
        self.resolve_user_id = resolve_user_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 클라이언트가 보낸 X-Request-ID 는 쓰지 않는다(위조 방지). 항상 서버가 새로 만든다.
        request_id = uuid.uuid4().hex[:12]
        # 요청이 끝나도 되돌리지 않는다 — 요청마다 별도 실행 흐름이라 다른 요청에 새지 않는다.
        request_id_var.set(request_id)
        user_id_var.set(self.resolve_user_id(HTTPConnection(scope)))
        log_event(logger, "request_received", method=scope["method"], path=scope["path"])

        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            log_event(
                logger,
                "unhandled_error",
                logging.ERROR,
                exc_info=exc,
                error_type=type(exc).__name__,
            )
            if response_started:  # 응답을 보내기 시작한 뒤라면 바꿀 수 없다
                raise
            await internal_error_response()(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            log_event(logger, "request_completed", status=status, duration_ms=duration_ms)
