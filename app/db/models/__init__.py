"""테이블 모델 — 테이블마다 파일 하나. 여기서 모두 불러와야 init_db 가 테이블을 전부 만든다.

다른 영역에서는 `from app.db.models import User` 처럼 여기서 가져다 쓴다.
"""

from app.db.models.user import User

__all__ = ["User"]
