"""FastAPI 앱 진입점. 실행: `uvicorn app.main:app`"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Web AI Chatbot")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """서버가 떠 있는지 확인(배포 헬스 체크용)."""
        return {"status": "ok"}

    return app


app = create_app()
