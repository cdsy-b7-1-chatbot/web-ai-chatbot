"""FastAPI 앱 진입점. 실행: `uvicorn app.main:app`"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from app.auth.router import router as auth_router
from app.auth.security import ensure_jwt_secret
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.openapi import app_openapi_options, use_error_response_for_validation
from app.db.database import get_engine, init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # 설정이 빠졌으면 첫 요청 때가 아니라 지금 안내와 함께 시작을 멈춘다
    ensure_jwt_secret()
    # 없는 테이블만 만든다. DATABASE_URL 이 비어 있으면 여기서 멈춘다
    init_db(get_engine())
    yield


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok"}]})

    status: str


def create_app() -> FastAPI:
    setup_logging(get_settings().log_level)

    app = FastAPI(title="Web AI Chatbot", lifespan=lifespan, **app_openapi_options())
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    use_error_response_for_validation(app)

    @app.get("/api/health")
    def health() -> HealthResponse:
        """서버가 떠 있는지 확인(배포 헬스 체크용)."""
        return HealthResponse(status="ok")

    # 영역별 라우터 — 각자 한 줄씩 추가한다(CONTRIBUTING 2장)
    app.include_router(auth_router)

    return app


app = create_app()
