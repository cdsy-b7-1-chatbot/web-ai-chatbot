"""DB 연결 — 엔진·세션·`get_db` 의존성.

앱은 Postgres 로만 실행한다(배포 Render, 로컬 Docker 또는 개인 Render). SQLite 는 테스트 기본값(메모리 DB)으로만
쓴다 — SQLite 는 문자열 길이를 검사하지 않고 시간대를 버려서, 앱을 SQLite 로 돌리면 응답이 배포와 달라진다.

    postgresql://user:pass@host/db   Render 가 주는 형식 그대로 넣으면 psycopg 3 드라이버로 바꿔 쓴다
    sqlite://                        메모리 DB (테스트 기본값, tests/conftest.py)

엔진은 처음 쓸 때 만든다 — import 만으로는 DB 에 접속하지 않아 테스트·도구 실행이 가볍다.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.logging import log_event

logger = logging.getLogger(__name__)

MISSING_URL_MESSAGE = (
    "DATABASE_URL 이 설정되지 않았습니다. "
    "로컬은 .env.example 을 .env 로 복사하고 Postgres 를 띄우세요(README 로컬 개발 환경). "
    "배포는 Render 환경 변수에 Postgres 주소를 넣으세요."
)

_IN_MEMORY_SQLITE = ("sqlite://", "sqlite:///:memory:")


class Base(DeclarativeBase):
    """모든 테이블 모델의 부모. 모델은 app/db/models/ 에 테이블마다 파일 하나로 둔다."""


def normalize_database_url(url: str) -> str:
    """Render 가 주는 `postgres://`·`postgresql://` 를 psycopg 3 드라이버 주소로 바꾼다.

    SQLAlchemy 는 `postgresql://` 을 보면 psycopg2 를 고르는데, 우리는 psycopg 3 를 설치했다.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    # SQLite 는 외래키 검사가 기본으로 꺼져 있다 — 켜지 않으면 없는 사용자 번호로도 저장된다.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(url: str) -> Engine:
    url = normalize_database_url(url)
    if not url.startswith("sqlite"):
        # Render 무료 Postgres 는 쉬는 연결을 끊는다 — 쓰기 전에 살아 있는지 확인한다
        return create_engine(url, pool_pre_ping=True)

    options: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if url in _IN_MEMORY_SQLITE:
        # 메모리 DB 는 연결마다 따로 생긴다 — 연결 하나를 같이 써야 만든 테이블이 보인다
        options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError(MISSING_URL_MESSAGE)
    return create_db_engine(url)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI 의존성 — 요청마다 세션을 열고 끝나면 닫는다(커밋하지 않은 변경은 버려진다)."""
    with _session_factory()() as session:
        yield session


# 라우트에서는 `db: SessionDep` 로 받는다 — `db=Depends(get_db)` 기본값 방식은 ruff B008 에 걸린다
SessionDep = Annotated[Session, Depends(get_db)]


def init_db(engine: Engine) -> None:
    """없는 테이블만 만든다(있는 테이블은 건드리지 않는다). 앱 시작 시 한 번 호출."""
    import app.db.models  # noqa: F401 — 모든 테이블 모델을 Base 에 등록

    Base.metadata.create_all(engine)
    # 주소에는 비밀번호가 들어 있으므로 로그에는 DB 종류만 남긴다
    log_event(logger, "db_ready", dialect=engine.dialect.name)
