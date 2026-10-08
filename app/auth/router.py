"""인증 API — `/api/auth/*`. 설계: #1 3장."""

from fastapi import APIRouter

from app.auth import service
from app.auth.schemas import SignupRequest, UserResponse
from app.core.errors import error_responses
from app.db.database import SessionDep

router = APIRouter(prefix="/api/auth", tags=["인증"])


@router.post("/signup", status_code=201, responses=error_responses(409))
def signup(body: SignupRequest, db: SessionDep) -> UserResponse:
    """회원가입. 아이디는 소문자로 바꿔 저장한다. 가입만 하고 로그인은 `/login` 으로 따로 한다."""
    user = service.signup(db, body.username, body.password)
    return UserResponse.model_validate(user)
