import pytest
from sqlalchemy.orm import Session

from app.db.database import create_db_engine, init_db


@pytest.fixture
def engine():
    """테스트마다 새 메모리 SQLite — 테이블까지 만든 상태."""
    engine = create_db_engine("sqlite://")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def user(db):
    from app.db.models import User

    user = User(username="sangwoo", password_hash="argon2-hash")
    db.add(user)
    db.commit()
    return user
