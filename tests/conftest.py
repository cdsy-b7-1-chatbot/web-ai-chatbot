"""테스트 공용 픽스처 — 테스트 DB 는 기본이 메모리 SQLite, `TEST_DATABASE_URL` 을 주면 그 Postgres.

    uv run pytest                                                            메모리 SQLite (설치 없이 바로)
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatbot_test uv run pytest

DB 코드를 바꾼 PR 은 Postgres 로 한 번 돌린다 — SQLite 는 문자열 길이를 검사하지 않고 시간대를 버려서
SQLite 로만 통과한 테스트는 배포에서 다르게 동작할 수 있다. `@pytest.mark.postgres` 테스트는 Postgres 에서만 돈다.

설정(`get_settings()`)은 테스트마다 `.env` 없이 기본값 + 테스트용 JWT_SECRET 으로 시작한다.
바꾸려면 `configure(cookie_secure="false")` 처럼 `configure` 픽스처를 쓴다.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401 — 지울 테이블을 알도록 모든 모델을 Base 에 등록
from app.core.config import Settings, get_settings
from app.db.database import Base, create_db_engine, init_db, normalize_database_url

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or "sqlite://"
_url = make_url(normalize_database_url(TEST_DATABASE_URL))
_backend = _url.get_backend_name()

TEST_JWT_SECRET = "test-only-jwt-secret-0123456789abcdef"
# 인증 설정 — 개발자 셸에 export 된 값도 테스트에 섞이지 않게 지운다
_AUTH_ENV = ("JWT_SECRET", "JWT_EXPIRE_MINUTES", "COOKIE_SECURE", "CORS_ORIGINS")


def pytest_configure(config):
    database = _url.database or ""
    if _backend != "sqlite" and "test" not in database:
        # 테스트는 테이블을 지웠다 다시 만든다 — 배포·개발 DB 주소를 잘못 넣어도 데이터가 날아가지 않게
        raise pytest.UsageError(
            f"TEST_DATABASE_URL 의 DB 이름에 'test' 가 들어가야 합니다(지금: {database!r}). "
            "테스트는 테이블을 지우므로 테스트 전용 DB 를 쓰세요. 예) .../chatbot_test"
        )


def pytest_report_header(config):
    # 주소에는 비밀번호가 들어 있으므로 DB 종류만 보여준다
    return f"test database: {_backend} (TEST_DATABASE_URL 로 변경)"


def pytest_collection_modifyitems(config, items):
    if _backend == "postgresql":
        return
    skip = pytest.mark.skip(reason="Postgres 전용 — TEST_DATABASE_URL 을 주면 실행")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch):
    """모든 테스트에 적용 — 개발자의 `.env`(예: COOKIE_SECURE=false)에 따라 결과가 달라지지 않게 한다."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in _AUTH_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def configure(monkeypatch):
    """`configure(cookie_secure="false", jwt_expire_minutes="5")` — 이 테스트에서만 설정값을 바꾼다."""

    def apply(**values: str) -> None:
        for name, value in values.items():
            monkeypatch.setenv(name.upper(), value)
        get_settings.cache_clear()

    return apply


@pytest.fixture
def empty_database_url():
    """테이블이 하나도 없는 테스트 DB 주소. 테스트가 끝나면 만든 테이블을 지운다.

    메모리 SQLite 는 엔진마다 새 DB 라 원래 비어 있고, Postgres 는 모든 테스트가 같은 DB 를 쓰므로 직접 비운다.
    시작할 때도 지우는 건 지난 실행이 중간에 멈춰 남긴 테이블 때문이다.
    """
    cleaner = create_db_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(cleaner)
    yield TEST_DATABASE_URL
    Base.metadata.drop_all(cleaner)
    cleaner.dispose()


@pytest.fixture
def engine(empty_database_url):
    """테스트마다 빈 DB — 테이블까지 만든 상태."""
    engine = create_db_engine(empty_database_url)
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    """API 테스트용 TestClient — 앱의 DB 를 테스트 DB 로 바꿨다.

    https 주소라 Secure 쿠키도 오간다(http 면 테스트 클라이언트가 Secure 쿠키를 보내지 않는다).
    lifespan 은 돌리지 않는다 — 테이블은 engine 픽스처가 이미 만들었다.
    """
    from app.db.database import get_db
    from app.main import create_app

    def test_db():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = test_db
    return TestClient(app, base_url="https://testserver")


USER_PASSWORD = "password123"


@pytest.fixture(scope="session")
def _user_password_hash():
    # Argon2 해싱은 한 번에 20ms 쯤 걸린다 — 테스트 실행 전체에서 한 번만 만든다
    from app.auth.security import hash_password

    return hash_password(USER_PASSWORD)


@pytest.fixture
def user_password():
    """`user` 픽스처의 비밀번호 — 로그인 테스트용."""
    return USER_PASSWORD


@pytest.fixture
def user(db, _user_password_hash):
    from app.db.models import User

    user = User(username="sangwoo", password_hash=_user_password_hash)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def conversation(db, user):
    from app.db.models import Conversation

    conversation = Conversation(user_id=user.id, title="배포 방법")
    db.add(conversation)
    db.commit()
    return conversation
