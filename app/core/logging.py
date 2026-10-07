"""서버 로그 — 표준 logging 으로 stdout 에 `이벤트명 key=value ...` 를 한 줄씩 남긴다.

    2026-10-07T06:40:01Z INFO request_received request_id=a1b2c3 user_id=12 path=/api/chat

`request_id`·`user_id` 는 요청 미들웨어가 요청 문맥(ContextVar)에 넣어 두고,
`log_event` 가 꺼내 자동으로 붙인다. 호출하는 쪽은 이벤트별 필드만 넘기면 된다.
"""

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

# 요청마다 따로 있는 값. 비동기 서버에서 여러 요청이 번갈아 실행돼도 서로 섞이지 않는다.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_HANDLER_NAME = "app-stdout"

# 이 문자가 하나라도 있으면 값을 큰따옴표로 감싼다(줄바꿈 같은 제어 문자는 isprintable 로 따로 거른다).
_QUOTE_TRIGGERS = frozenset(' "=\\')


def setup_logging(level: str = "INFO") -> None:
    """앱 시작 시 호출. 루트 로거가 stdout 으로 UTC 시각을 찍게 한다.

    여러 번 불려도 우리 핸들러는 하나만 남기고, 다른 핸들러(pytest 의 로그 수집 등)는 건드리지 않는다.
    """
    formatter = logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime

    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in [h for h in root.handlers if h.get_name() == _HANDLER_NAME]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())


def format_value(value: Any) -> str:
    """로그 한 줄의 `key=value` 에서 value 부분을 만든다.

    - `None` → `-`
    - 공백·`"`·`=`·`\\` 나 줄바꿈 같은 제어 문자가 있거나 빈 문자열이면 큰따옴표로 감싸고,
      안의 `"` `\\` 줄바꿈은 `\\"` `\\\\` `\\n` 으로 바꾼다.
      → 값 안의 줄바꿈으로 가짜 로그 줄을 끼워 넣는 인젝션을 막으면서, 시도한 흔적은 한 줄 안에 남긴다.
    - 그 밖의 값은 그대로.
    """
    if value is None:
        return "-"
    text = str(value)
    if text and not any(ch in _QUOTE_TRIGGERS or not ch.isprintable() for ch in text):
        return text
    return json.dumps(text, ensure_ascii=False)


def log_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.INFO,
    *,
    exc_info: BaseException | None = None,
    **fields: Any,
) -> None:
    """`log_event(logger, "ai_call_success", latency_ms=1240)` 처럼 호출한다."""
    merged = {"request_id": request_id_var.get(), "user_id": user_id_var.get(), **fields}
    pairs = " ".join(f"{key}={format_value(value)}" for key, value in merged.items())
    logger.log(level, "%s %s", event, pairs, exc_info=exc_info)
