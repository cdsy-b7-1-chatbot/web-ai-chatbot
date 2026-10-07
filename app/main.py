"""FastAPI 앱 진입점. 실행: `uvicorn app.main:app`"""

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.openapi import app_openapi_options, use_error_response_for_validation


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok"}]})

    status: str


def create_app() -> FastAPI:
    setup_logging(get_settings().log_level)

    app = FastAPI(title="Web AI Chatbot", **app_openapi_options())
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    use_error_response_for_validation(app)

    @app.get("/api/health")
    def health() -> HealthResponse:
        """서버가 떠 있는지 확인(배포 헬스 체크용)."""
        return HealthResponse(status="ok")

    return app


app = create_app()
