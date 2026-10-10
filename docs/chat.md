# 채팅 구현·검증 (백엔드 B)

담당: 권현석. 작업 이슈: #9, DB 계약: #1. DB 연결·테이블·인증은 A의 기존 구현을 사용합니다. `list_chats`·`GET /api/me/chats`는 PM 담당입니다.

## 처리 흐름

1. `CurrentUser`로 인증한 후 `ChatRequest`에서 질문 앞뒤 공백을 제거합니다. 기본 1~5,000자이며 `conversation_id`는 선택적인 양의 정수입니다.
2. ID가 없거나 null이면 첫 질문 앞 100자로 제목을 정하고 방을 먼저 commit합니다. 기존 방은 로그인 사용자 소유인지 확인하고, 없거나 다른 사용자 것이면 404를 반환합니다.
3. 같은 방의 최근 성공 Q/A 5쌍을 `created_at DESC, id DESC`로 선택한 뒤 시간순으로 뒤집습니다. 한국어 기본 시스템 안내 → 이전 Q/A → 현재 질문으로 구성합니다. 실패 기록은 문맥에 넣지 않습니다.
4. `httpx.AsyncClient`로 OpenRouter를 호출합니다. `qwen/qwen3-30b-a3b-instruct-2507`, `provider.only=["streamlake"]`, `allow_fallbacks=false`, `stream=false`, 최대 1,024토큰입니다. HTTP 타임아웃과 `asyncio.timeout`으로 전체 30초를 제한하고 자동 재시도하지 않습니다.
5. 답변과 방의 활동 시각을 같은 트랜잭션에서 저장·commit한 뒤 JSON 응답을 보냅니다. DB 저장 실패 시 생성된 답변을 보내지 않습니다. 생성 제한으로 끝난 답변은 `truncated=true`입니다. 응답 시각은 UTC입니다.

동기 DB 작업은 thread pool에서 순차 실행하며 한 요청의 Session을 동시에 사용하지 않습니다. AI 대기 전에 읽기 트랜잭션을 끝내 연결을 반환합니다. 서비스는 HTTP Request·Response 객체를 사용하지 않습니다.

## 파일·repository 계약

| 파일 | 역할 |
|---|---|
| `app/chat/router.py`, `schemas.py` | `POST /api/chat`, `GET /api/conversations` HTTP 입출력·검증·응답 모델 |
| `app/chat/service.py` | 소유권 확인 → 문맥 → AI → 저장, 오류 응답 변환 |
| `app/chat/context.py`, `client.py` | 문맥 메시지 구성, OpenRouter 호출·결과 해석 |
| `app/chat/repository.py` | 대화방·대화 저장·조회, DB 이벤트 |

| 함수 | 반환·조건 |
|---|---|
| `create_conversation(db, user_id, title)` | 생성·commit 후 `Conversation` |
| `get_conversation(db, conversation_id, user_id)` | 내 방만 반환, 없으면 `None` |
| `list_conversations(db, user_id)` | 내 방을 `updated_at DESC, id DESC`로 반환 |
| `get_recent_chats(db, conversation_id, limit)` | 소유권 확인 후 호출, 성공 기록만 최신 N개 선택 후 시간순 반환 |
| `save_chat(db, *, conversation, question, answer, status, ...)` | 사용자 ID는 방에서 가져옴. 대화 INSERT·방 UPDATE·commit 후 `Chat` |

쓰기 함수는 실패 시 rollback하고 SQLAlchemy 예외를 전달합니다. DB 기본값 조회도 commit 전에 끝냅니다. 대화에는 모델·입출력 토큰 수·AI 소요 시간을 저장하고 모르는 사용량은 null로 둡니다. 합계·비용은 저장하지 않습니다. DB 스키마는 `app/db/models/` 및 이슈 #1을 확인합니다.

## 실패·로그

오류 JSON 형식은 `{"error", "message"}`이고 응답 헤더 `X-Request-ID`로 서버 로그를 찾습니다. 구체적 API 모델·예시·오류 표는 `/docs`에서 자동 생성됩니다.

| 상황 | HTTP·코드 |
|---|---|
| 인증·질문 검증·방 소유권 실패 | 401·422·404 |
| AI 키 미설정 | 503 `AI_NOT_CONFIGURED` (새 방 생성 없음) |
| AI 타임아웃 | 504 `AI_TIMEOUT` |
| AI HTTP 실패·잘못된 JSON·빈 답변 | 502 `AI_ERROR` |
| DB 조회·생성·저장 실패 | 500 `DB_ERROR` |

AI 실패는 질문·`answer=null`·`status=failed`·오류 코드를 저장합니다. 실패 기록 저장까지 실패하면 두 원인을 로그에 남기고 `DB_ERROR`를 반환합니다. 새 방은 AI보다 먼저 저장하므로 실패해도 방 목록에 남습니다.

필수 이벤트는 `request_received`, `ai_call_start`, `ai_call_success`/`ai_call_failed`, `db_save_success`/`db_save_failed`입니다. DB 읽기 실패는 `db_read_failed`입니다. 같은 요청의 이벤트에 `request_id`, `user_id`를 자동 연결합니다. AI 실패에는 외부 HTTP 상태 코드(`upstream_status`)를 남겨 인증·크레딧·제공자 오류를 구분합니다. 키·인증 토큰·질문/답변 본문·외부 오류 원문은 이벤트 로그에 넣지 않습니다.

## 설정·실행

README의 uv·PostgreSQL·인증 설정을 먼저 적용합니다. `.env.example`에 AI 설정 예시가 있고 README 환경 변수 표에 키 목록·기본값이 있습니다. 서버 `.env` 또는 배포 환경에 `OPENROUTER_API_KEY`를 설정하며, 선택 헤더는 `OPENROUTER_SITE_URL`·`OPENROUTER_SITE_NAME`이 있을 때만 전송합니다. 실제 `.env`는 Git에서 제외합니다.

키가 없어도 인증·방 목록 조회는 동작하며 채팅만 503입니다. StreamLake 외 제공자는 사용하지 않으므로 해당 제공자 장애는 오류로 처리합니다. 운영 기록을 유지하려면 재배포 후에도 같은 외부 PostgreSQL을 사용해야 합니다. DB 연결·스키마는 A, 배포 설정과 재배포 후 데이터 유지 최종 확인은 PM 담당입니다.

## 검증 방법

```text
uv run pytest
uv run ruff format --check
uv run ruff check
```

기본은 메모리 SQLite입니다. PostgreSQL은 README처럼 셸에 `TEST_DATABASE_URL`을 설정한 뒤 같은 pytest 명령을 실행합니다. 테스트는 테이블을 재생성하므로 이름에 `test`가 포함된 전용 DB를 사용합니다. AI는 가짜 client·HTTP mock으로 검증하며 실제 키를 읽지 않습니다.

자동 테스트: 사용자·방 격리, 정렬·최근 성공 5쌍, commit/rollback·시각 갱신, 인증/입력/소유권 실패 시 AI 미호출, 모델·제공자·헤더·사용량, 전체 타임아웃, HTTP·JSON·빈 응답 오류, 생성 제한, DB 실패 시 답변 미반환, AI/DB 동시 실패, 로그 추적·민감정보 미노출, OpenAPI 선언을 확인합니다.

실제 AI 확인은 **개발용 DB와 유효한 AI 설정으로 서버를 띄운 뒤** 별도 터미널에서 실행합니다. OpenRouter 호출 2회와 테스트 계정·대화 기록을 생성합니다.

```text
uv run python scripts/smoke_chat.py --base-url http://127.0.0.1:8000
```

가입 → 로그인 → 새 질문 → 같은 방에서 별명 기억 확인 → 방 목록 확인을 수행합니다. 출력에는 ID·검증 결과·요청 ID만 포함합니다. `--result <경로>`로 키·토큰 없는 JSON 증빙을 저장할 수 있습니다. 기록 내용은 `scripts/check_chat_logs.sql`로 사용자별 확인합니다.

2026-10-09 검증: SQLite 213 passed·2 skipped(PostgreSQL 전용), PostgreSQL 215 passed, Ruff 통과. 실제 서버에서 가입·로그인 → StreamLake 지정 OpenRouter 응답 → 같은 방의 후속 질문에서 별명 기억 → 대화방 목록 확인을 통과했습니다. 두 성공 기록의 사용자·방·모델·토큰·AI 소요 시간이 PostgreSQL에 저장된 것을 직접 조회했습니다. AI 실패의 502 응답·실패 기록 저장, 확인용 SQL 실행, PostgreSQL·앱 재시작 후 기록 유지도 확인했습니다. 처음 발생한 HTTP 402는 계정 크레딧 충전 후 해결되었습니다.

첫 버전은 RAG·스트리밍·대화 삭제·중복 요청 방지를 포함하지 않습니다.
