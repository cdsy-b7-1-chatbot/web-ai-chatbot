# 대화 기록 조회 API

담당: 이동현(PM). 기존 분담과 화면 흐름은 이슈 #1·#11을 따릅니다.
기존 인증·DB 모델을 사용하며 테이블과 환경 변수는 추가하지 않습니다. AI 키 없이 저장된 기록을 조회합니다.

## 요청

`GET /api/me/chats`

| 쿼리 | 기본값 | 범위·용도 |
|---|---|---|
| `conversation_id` | 생략 | 양의 정수. 지정하면 선택한 대화방, 생략하면 내 전체 기록 |
| `limit` | `50` | `1~100`. 한 번에 가져올 개수 |
| `offset` | `0` | `0` 이상. 최신순 목록에서 건너뛸 개수 |

사용자는 인증된 세션에서 결정하며 쿼리로 다른 사용자를 지정할 수 없습니다.
기존 로그인 쿠키 또는 `Authorization: Bearer <access_token>` 헤더를 사용합니다.

```sh
curl 'http://127.0.0.1:8000/api/me/chats?conversation_id=7&limit=50&offset=0' \
  -H 'Authorization: Bearer <access_token>'
```

## 정상 응답

`200` 응답의 `items`에 실패 기록까지 포함합니다. 빈 내역은 `{"items": []}`입니다.
정렬은 이슈 #1의 계약대로 `created_at DESC, id DESC`이며 시각이 같으면 ID가 큰 기록부터 반환합니다.
시각은 ISO 8601 UTC입니다.

```json
{
  "items": [
    {
      "id": 22,
      "user_id": 3,
      "conversation_id": 7,
      "question": "방금 뭘 물어봤지?",
      "answer": null,
      "status": "failed",
      "error_code": "AI_TIMEOUT",
      "created_at": "2026-10-10T05:01:00Z"
    },
    {
      "id": 21,
      "user_id": 3,
      "conversation_id": 7,
      "question": "배포 방법을 알려줘",
      "answer": "배포는 다음 순서로 진행합니다.",
      "status": "success",
      "error_code": null,
      "created_at": "2026-10-10T05:00:00Z"
    }
  ]
}
```

## 프론트 연결

1. `GET /api/conversations`로 좌측 대화방 목록을 표시합니다.
2. 방을 선택하면 `/api/me/chats?conversation_id=<id>`를 같은 서버에 요청합니다. 기존 HttpOnly 쿠키가 인증에 사용됩니다.
3. 중앙 대화 영역은 받은 기록을 시간순으로 뒤집어 질문·답변을 표시합니다. `status=failed`는 질문과 실패 안내를 표시하며 `answer`가 null일 수 있습니다.
4. 오래된 기록이 더 필요하면 `offset`을 지금까지 받은 개수만큼 늘립니다. 반환 개수가 `limit`보다 적으면 마지막 페이지입니다.
5. `401`은 로그인 화면으로 이동하고, 다른 오류는 공통 응답의 `message`를 표시합니다. 대화방을 바꿀 때 기존 선택 방의 화면 상태를 초기화합니다.

## 오류·로그

| 상태 | 코드 | 의미 |
|---|---|---|
| `401` | `UNAUTHORIZED` | 비로그인·인증 만료 |
| `404` | `NOT_FOUND` | 없는 방 또는 다른 사용자 소유 방 |
| `422` | `VALIDATION_ERROR` | 잘못된 ID·limit·offset |
| `500` | `DB_ERROR` | 기록 또는 대화방 조회 실패 |

오류 예시: `{"error": "NOT_FOUND", "message": "대화방을 찾을 수 없습니다."}`.
기존 요청 로그에 요청 ID·사용자 ID가 붙습니다. 조회 성공은 `history_read_success`, DB 실패는
`db_read_failed operation=list_chats`로 추적하며 질문·답변 본문과 DB 오류 원문은 로그에 넣지 않습니다.

## 구현·검증

`router → service → repository → app/db/models` 구조입니다. 소유권 확인은 백엔드 B의
`get_conversation`을 재사용하고 기록 쿼리도 `Chat.user_id`로 제한합니다.
동기 DB 조회는 동기 라우트에서 실행합니다. 기존 API와 같은 UTC 응답 타입을 사용합니다.

```sh
uv run pytest tests/test_history_api.py
uv run pytest
uv run ruff check
uv run ruff format --check
```

테스트는 인증·사용자/대화방 격리·실패 이력·정렬·페이지 처리·입력 검증·DB 오류·기록 보존·OpenAPI 명세를 확인합니다.
기본 테스트 DB는 메모리 SQLite입니다. DB 조회 코드를 추가했으므로 PR 검증 시 테스트 전용 PostgreSQL에서도
실행합니다(README의 `TEST_DATABASE_URL` 설정 참조). 실제 AI 호출은 기록 조회 검증에 필요하지 않습니다.
