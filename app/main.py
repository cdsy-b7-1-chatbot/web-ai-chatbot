"""FastAPI 앱 진입점. 실행: `uvicorn app.main:app`"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from app.auth.dependencies import user_id_from_request
from app.auth.router import router as auth_router
from app.auth.security import ensure_jwt_secret
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
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
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="Web AI Chatbot", lifespan=lifespan, **app_openapi_options())
    # 요청 로그마다 토큰 주인의 user_id 를 붙인다(비로그인은 -)
    app.add_middleware(RequestContextMiddleware, resolve_user_id=user_id_from_request)
    if settings.cors_origin_list:
        # 프론트를 다른 주소에 따로 배포했을 때만. 그때 토큰은 Authorization 헤더로 오므로 쿠키는 허용하지 않는다.
        # 나중에 추가한 미들웨어가 바깥쪽이라, 500 응답에도 CORS 헤더가 붙어 프론트가 오류를 읽을 수 있다
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=[REQUEST_ID_HEADER],  # 오류를 알릴 때 프론트가 요청 번호를 읽을 수 있게
        )
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
