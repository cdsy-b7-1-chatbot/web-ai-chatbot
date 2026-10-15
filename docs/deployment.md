# Render 배포 가이드

## 현재 서비스

- 서비스: https://web-ai-chatbot-33yw.onrender.com
- API 명세: https://web-ai-chatbot-33yw.onrender.com/docs
- 상태 확인: https://web-ai-chatbot-33yw.onrender.com/api/health
- 구성: Render 무료 Python 웹서비스 1개 + 무료 PostgreSQL 17 1개, 모두 Singapore 리전
- AI: 코디세이 OpenAI 호환 API, 배포 모델 `gemini-3.1-flash-lite`
- 운영 브랜치: `main` / 초기 배포 커밋: `e4bb43e`

FastAPI가 화면과 API를 같은 주소에서 제공합니다. 브라우저는 HttpOnly 로그인 쿠키로 인증하고, AI 호출과 키 사용은 서버에서 처리합니다. 대화는 외부 PostgreSQL에 저장합니다.

## 처음 배포하기

1. Render에서 PostgreSQL을 만듭니다. PostgreSQL 17, Singapore, **Free**를 선택합니다.
2. Web Service에서 **Public Git Repository**를 선택하고 저장소 주소를 연결합니다.
   `https://github.com/cdsy-b7-1-chatbot/web-ai-chatbot`
3. Python 3, `main`, DB와 같은 Singapore 리전, **Free**를 선택합니다. Root Directory는 비워둡니다.
4. 아래 명령과 환경 변수를 설정합니다.

| 설정 | 값 |
| --- | --- |
| Build Command | `uv sync --locked --no-dev` |
| Start Command | `uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log` |
| Health Check Path | `/api/health` |
| Auto-Deploy | `Off` — 현재 공개 저장소를 직접 연결해 수동으로 배포 |

`--no-access-log`를 사용하며, 요청·처리 결과는 앱의 요청 ID 기반 로그로 확인합니다. 앱 시작 시 없는 테이블을 생성합니다.

### 서버 환경 변수

Render의 **Environment**에 설정합니다. 실제 키·서명 키·비밀번호가 포함된 DB URL은 코드나 문서에 적지 않습니다.

| 이름 | 설정 방법 또는 값 |
| --- | --- |
| `DATABASE_URL` | 같은 리전의 Render PostgreSQL **Internal Database URL** |
| `JWT_SECRET` | Render의 Generate 등으로 새로 생성한 32바이트 이상의 로그인 서명 키 |
| `CODYSSEY_API_KEY` | 코디세이 콘솔에서 발급한 OpenAI 호환 API 키 |
| `PYTHON_VERSION` | `3.14.0` |
| `COOKIE_SECURE` | `true` |
| `AI_MODEL` | `gemini-3.1-flash-lite` |
| `AI_TIMEOUT_SECONDS` | `30` |
| `AI_MAX_OUTPUT_TOKENS` | `1024` |
| `LOG_LEVEL` | `INFO` |

`CHAT_CONTEXT_PAIRS=5`, `CHAT_MAX_QUESTION_LENGTH=5000`, `JWT_EXPIRE_MINUTES=60`은 코드 기본값을 사용합니다. 화면과 API가 같은 주소이므로 `CORS_ORIGINS`는 별도로 설정하지 않습니다. `.env.example`은 이름과 예시만 제공하며 실제 `.env`는 Git에서 제외합니다.

운영 DB 주소를 `TEST_DATABASE_URL`로 사용하지 않습니다. 테스트는 별도 테스트 DB에서 실행합니다.

5. 월 요금이 **$0**인지 확인하고 Deploy web service를 실행합니다.
6. 상태가 Live로 바뀌면 `/api/health`의 `{"status":"ok"}`와 웹 화면을 확인합니다.

## 코드 변경 후 배포

1. 기능 PR을 `develop`에 병합하고, 배포할 내용을 PR로 `main`에 반영합니다.
2. Render 웹서비스에서 **Manual Deploy → Deploy latest commit**을 선택합니다.
3. Live 상태와 배포 커밋을 확인한 뒤 로그인·질문·기록 조회를 확인합니다.

같은 코드로 프로세스를 다시 시작할 때는 **Manual Deploy → Restart service**를 사용합니다. 기존 PostgreSQL 연결과 환경 변수를 유지합니다.

## 평가 시 기능·DB 기록 확인

1. 서비스에 회원가입하고 로그인합니다.
2. 질문을 보내고 같은 대화방에서 후속 질문을 보냅니다.
3. 대화방을 선택해 질문·응답을 다시 불러오고, 로그아웃 → 재로그인 후에도 목록과 기록을 확인합니다.
4. 로그인한 같은 브라우저의 새 탭에서 아래 주소를 엽니다.
   https://web-ai-chatbot-33yw.onrender.com/api/me/chats?limit=10
5. JSON의 `user_id`, `conversation_id`, `created_at`, `question`, `answer`, `status`를 확인합니다. 로그인한 사용자의 기록만 반환합니다.
6. 로그아웃한 뒤 기록 주소를 새로 열면 401이 반환되는지 확인합니다.

대화방별 조회는 `/api/me/chats?conversation_id=<대화방 ID>`를 사용합니다. 상세 요청·응답은 [기록 조회 API 문서](history.md), SQL 확인 방법은 [확인용 SQL](../scripts/check_chat_logs.sql)을 참고합니다.

Render **Logs**에서 요청 ID로 검색하면 `request_received` → `ai_call_start` → `ai_call_success` 또는 `ai_call_failed` → `db_save_success` 또는 `db_save_failed` 흐름을 추적할 수 있습니다. AI 타임아웃·실패 응답 규칙은 [채팅 기술 문서](chat.md)에 정리했습니다.

## 배포 확인 결과

2026-10-15 외부 HTTPS URL에서 확인했습니다.

- 화면·정적 JavaScript·API 명세·상태 확인: HTTP 200
- 가입·쿠키 로그인, Secure·HttpOnly·SameSite=Lax 쿠키: 정상
- 비로그인 채팅·기록 조회: 401 / 빈 질문: 422
- 실제 코디세이 호출 2회: 첫 질문 응답과 같은 대화방의 별명 기억 확인
- 브라우저에서 저장된 대화를 불러오고 후속 질문·AI 응답 표시 확인
- 사용자·대화방·시각·질문·응답이 포함된 성공 기록 2건 조회
- 요청 수신·AI 호출 시작·AI 응답 성공·DB 저장 성공 로그 확인
- Render의 서비스 재시작 이벤트 확인 후 새 로그인으로 동일 기록 2건 재조회

## 무료 서비스 운영

무료 웹서비스는 요청이 없으면 중지됐다가 다시 시작하므로 첫 응답에 시간이 걸릴 수 있습니다. 평가 전에 접속 상태를 확인합니다. 파일 시스템에 DB를 저장하지 않고 별도 PostgreSQL을 사용합니다.

현재 무료 PostgreSQL의 만료일은 **2026-11-14**입니다. 장기간 사용할 경우 만료 전에 데이터 보관과 DB 유지 방법을 결정해야 합니다. 코디세이 모델 가용 여부와 남은 할당량은 API 콘솔에서 확인합니다.
