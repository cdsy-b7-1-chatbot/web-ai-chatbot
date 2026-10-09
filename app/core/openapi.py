"""/docs (Swagger UI) 를 API 명세로 쓸 수 있게, 문서가 실제 동작과 같은 내용을 보여주게 한다.

- 맨 위 설명: 모든 엔드포인트에 공통인 규약과 오류 코드 표
- 422 응답: FastAPI 기본값(`{"detail": [...]}`) 대신 실제로 나가는 ErrorResponse 형식
- 500 응답: 모든 엔드포인트에 ErrorResponse 로 표시(어느 엔드포인트든 날 수 있으므로)
"""

from typing import Any

from fastapi import FastAPI

from app.core.errors import ERROR_CODE_DOCS, ErrorResponse, error_responses

_CONVENTIONS = """\
모든 엔드포인트에 공통인 규약입니다. 엔드포인트별 요청·응답은 아래 목록에서 확인합니다.

### 응답 형식
- 성공·실패는 **HTTP 상태 코드**로 구분합니다.
- 정상 응답은 데이터를 그대로 돌려줍니다. 목록은 `{"items": [...]}` 로 감쌉니다.
- 필드 이름은 snake_case, 시각은 ISO 8601 UTC (`2026-10-07T05:30:00Z`) 입니다.

### 오류 응답
모든 오류는 `{"error": "코드", "message": "안내 문구"}` 형식입니다.
프론트는 `error` 로 분기하고, `message` 는 사용자에게 그대로 보여줘도 됩니다.

| 코드 | 의미 |
|---|---|
"""

_TRACING = """
### 요청 추적
모든 응답에 `X-Request-ID` 헤더가 붙습니다. 오류를 알릴 때 이 값을 함께 전달하면
서버 로그에서 해당 요청의 흐름을 찾을 수 있습니다.
"""


def api_description() -> str:
    rows = "".join(f"| `{code}` | {doc} |\n" for code, doc in ERROR_CODE_DOCS.items())
    return _CONVENTIONS + rows + _TRACING


def app_openapi_options() -> dict[str, Any]:
    """FastAPI(...) 생성자에 펼쳐 넣을 문서 관련 옵션."""
    return {"description": api_description(), "responses": error_responses(500)}


def use_error_response_for_validation(app: FastAPI) -> None:
    """문서의 422 응답을 실제 응답 형식(ErrorResponse)으로 바꾼다."""
    generate = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = generate()
        error_ref = {"$ref": f"#/components/schemas/{ErrorResponse.__name__}"}
        for operation in (op for path in schema.get("paths", {}).values() for op in path.values()):
            response = operation.get("responses", {}).get("422")
            if response and "HTTPValidationError" in str(response):
                operation["responses"]["422"] = {
                    "description": "입력값 검증 실패",
                    "content": {"application/json": {"schema": error_ref}},
                }
        for unused in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(unused, None)
        return schema

    app.openapi = openapi
