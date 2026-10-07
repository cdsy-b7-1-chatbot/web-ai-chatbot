"""환경 변수 설정.

값은 환경 변수에서 읽고, 로컬에서는 프로젝트 루트의 `.env` 도 읽는다.
이미 export 된 환경 변수가 `.env` 보다 우선한다(Render 에서는 대시보드에 넣은 값).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    # 비어 있으면 서버가 시작하지 않는다(app/db/database.py). 로컬은 .env.example 의 Docker Postgres 주소.
    database_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
