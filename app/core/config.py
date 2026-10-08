"""환경 변수 설정.

값은 환경 변수에서 읽고, 로컬에서는 프로젝트 루트의 `.env` 도 읽는다.
이미 export 된 환경 변수가 `.env` 보다 우선한다(Render 에서는 대시보드에 넣은 값).
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    # 비어 있으면 서버가 시작하지 않는다(app/db/database.py). 로컬은 .env.example 의 Docker Postgres 주소.
    database_url: str | None = None

    # 토큰 서명 키. 비어 있거나 32바이트보다 짧으면 서버가 시작하지 않는다(app/auth/security.py)
    jwt_secret: str | None = None
    jwt_expire_minutes: int = Field(default=60, gt=0)
    # true 면 브라우저가 https 로만 쿠키를 보낸다. 로컬 http 개발에서만 false
    cookie_secure: bool = True
    # 프론트를 다른 주소에 따로 배포할 때만 넣는다. 여러 개는 쉼표로: https://a.onrender.com,https://b.com
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
