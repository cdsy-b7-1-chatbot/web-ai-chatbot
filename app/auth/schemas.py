"""인증 API 의 요청·응답 모델. 입력 규칙: #1 3장."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models.user import USERNAME_MAX_LENGTH

USERNAME_MIN_LENGTH = 3
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64

# 아이디는 소문자로 바꿔 저장·비교한다 — "Admin" 과 "admin" 이 다른 계정이 되지 않게(사칭 방지)
_LowercaseUsername = Annotated[str, StringConstraints(to_lower=True)]


class SignupRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"username": "sangwoo", "password": "password123"}]}
    )

    # 길이를 여기서 막지 않으면 Postgres 의 varchar(20) 에서 DataError → 500 이 된다(SQLite 는 길이를 안 봄)
    username: _LowercaseUsername = Field(
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=r"^[A-Za-z0-9_]+$",
        description=f"{USERNAME_MIN_LENGTH}~{USERNAME_MAX_LENGTH}자 영문·숫자·_. 소문자로 바꿔 저장한다",
    )
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=f"{PASSWORD_MIN_LENGTH}~{PASSWORD_MAX_LENGTH}자",
    )


class LoginRequest(BaseModel):
    """형식 규칙은 검사하지 않는다 — 틀린 형식은 없는 아이디와 똑같이 401 로 응답한다."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"username": "sangwoo", "password": "password123"}]}
    )

    username: _LowercaseUsername = Field(
        max_length=USERNAME_MAX_LENGTH, description="대소문자 구분 없음"
    )
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, json_schema_extra={"examples": [{"id": 1, "username": "sangwoo"}]}
    )

    id: int
    username: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"access_token": "eyJhbGciOi...", "token_type": "bearer"}]}
    )

    access_token: str = Field(
        description="프론트를 따로 배포하면 `Authorization: Bearer <토큰>` 으로 보낸다. "
        "같은 주소에서 서빙하면 함께 내려가는 쿠키만으로 충분하다"
    )
    token_type: Literal["bearer"] = "bearer"
