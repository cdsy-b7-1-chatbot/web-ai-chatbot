"""인증 API — `/api/auth/*`. 설계: #1 3장."""

from fastapi import APIRouter, Response

from app.auth import service
from app.auth.dependencies import CurrentUser
from app.auth.schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.auth.security import ACCESS_TOKEN_COOKIE
from app.core.config import get_settings
from app.core.errors import error_responses
from app.db.database import SessionDep

router = APIRouter(prefix="/api/auth", tags=["인증"])


def _cookie_options() -> dict:
    return {
        "httponly": True,  # 자바스크립트로 읽을 수 없다 — XSS 가 생겨도 토큰을 훔쳐 가지 못한다
        "secure": get_settings().cookie_secure,
        "samesite": "lax",  # 다른 사이트에서 보낸 POST 에는 쿠키가 붙지 않는다(CSRF 완화)
        "path": "/",
    }


@router.post("/signup", status_code=201, responses=error_responses(409))
def signup(body: SignupRequest, db: SessionDep) -> UserResponse:
    """회원가입. 아이디는 소문자로 바꿔 저장한다. 가입만 하고 로그인은 `/login` 으로 따로 한다."""
    user = service.signup(db, body.username, body.password)
    return UserResponse.model_validate(user)


@router.post("/login", responses=error_responses(401))
def login(body: LoginRequest, db: SessionDep, response: Response) -> TokenResponse:
    """로그인. 토큰을 body 의 `access_token` 과 HttpOnly 쿠키로 함께 내려준다.

    프론트를 FastAPI 가 같이 서빙하면 쿠키만으로 되고, 따로 배포하면 body 토큰을
    `Authorization: Bearer` 헤더로 보낸다. 만료(기본 60분)되면 401 → 다시 로그인.
    """
    token = service.login(db, body.username, body.password)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        max_age=get_settings().jwt_expire_minutes * 60,  # 토큰과 같이 만료
        **_cookie_options(),
    )
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=204, response_class=Response)
def logout(response: Response) -> None:
    """로그아웃 — 쿠키를 지운다. 로그인하지 않았어도 204.

    토큰 자체는 서버에서 무효로 만들 수 없어 만료 전까지 유효하다.
    body 토큰을 저장해 쓰는 프론트는 저장한 토큰도 지운다.
    """
    response.delete_cookie(ACCESS_TOKEN_COOKIE, **_cookie_options())


@router.get("/me", responses=error_responses(401))
def me(user: CurrentUser) -> UserResponse:
    """로그인한 사용자. 토큰이 없거나 만료되면 401 — 프론트는 로그인 화면으로 보낸다."""
    return UserResponse.model_validate(user)
