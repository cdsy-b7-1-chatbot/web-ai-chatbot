# 웹 기반 AI 챗봇 서비스

Codyssey B7-1 팀 프로젝트입니다. FastAPI 웹 서비스에서 회원 인증, AI 질문·응답, 사용자별 대화 기록을 구현하고 외부 URL로 배포합니다.

회원가입·로그인, 인증된 사용자용 채팅 API와 대화방 목록 API가 구현되어 있습니다. 웹 화면·내 기록 API·배포는 각 담당자의 PR에서 통합합니다.

범용 챗봇으로 사용자가 질문하고 같은 대화방에서 후속 질문을 이어갈 수 있습니다. 핵심 흐름은 가입 → 로그인 → 질문 → 최근 대화 문맥으로 AI 응답 → DB 저장 → 응답 확인입니다.

## 팀 역할

| 이름 | 역할 | 주 담당 |
| --- | --- | --- |
| 이동현 | PM | 이슈·PR·일정 관리, 통합 검증, 배포 조율, 제출 문서 |
| 이상우 | 백엔드 A | ERD·DB 연결·테이블, 회원가입·로그인·인증 |
| 권현석 | 백엔드 B | 대화방·대화 repository, 채팅·대화방 목록 API, AI 호출·문맥·오류·로그·테스트 |
| 우광택 | 프론트엔드 | 가입·로그인·채팅·기록 화면과 API 연결 |

## 협업 규칙

1. `main`은 배포·평가용, `develop`은 통합용으로 사용합니다.
2. 각 작업은 `develop`에서 기능 브랜치를 만들어 진행하고 PR로 병합합니다. 예: `feature/auth`, `feature/ai-chat`, `feature/frontend`, `chore/deploy`.
3. PR은 다른 팀원 한 명 이상이 검토합니다. 개별 커밋 이력이 남도록 **merge commit** 방식으로 병합합니다.
4. 각자 실제 작업에 대한 유의미한 커밋을 10회 이상 남기고, 역할·작업 요약을 제출 전 Git 이력과 대조합니다.
5. API 키와 실제 `.env`, 로컬 DB 파일은 커밋하지 않습니다.
6. 브랜치·커밋·PR·리뷰·릴리스의 자세한 규칙은 [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) 를 따릅니다.

## 구조·문서

`app/auth/`의 인증 → `app/chat/router.py`의 HTTP 입출력 → `service.py`의 문맥·AI·저장 흐름 → `repository.py` → PostgreSQL로 연결됩니다. AI 호출은 서버의 `client.py`에서 OpenRouter로 전송합니다.

- API 명세·요청/응답 예시: 실행한 서버의 `/docs` (로컬 http://127.0.0.1:8000/docs)
- ERD·인증·repository 설계: [이슈 #1](https://github.com/cdsy-b7-1-chatbot/web-ai-chatbot/issues/1), 테이블 정의 `app/db/models/`
- 백엔드 B 구현·검증 방법: [채팅 기술 문서](docs/chat.md)
- 사용자별 DB 확인: [확인용 SQL](scripts/check_chat_logs.sql)
- `list_chats`와 `GET /api/me/chats`, 배포 URL·최종 팀 작업 요약 취합: PM 담당

## 로컬 개발 환경 (맥·Windows 공통)

Python 버전과 패키지 버전은 [uv](https://docs.astral.sh/uv/) 로 맞춥니다(`.python-version`, `uv.lock`).

1. uv 설치
   - 맥: `brew install uv`
   - Windows: `winget install --id=astral-sh.uv -e`
2. 환경 구성: `uv sync` — Python 3.14 가 없으면 uv 가 내려받습니다.
3. 환경 변수: `.env.example` 을 `.env` 로 복사합니다(맥 `cp .env.example .env`, Windows `copy .env.example .env`).
4. 로컬 DB(Postgres): [Docker Desktop](https://www.docker.com/products/docker-desktop/) 으로 띄웁니다(Windows 는 WSL2 필요). 처음 한 번:
   ```
   docker run -d --name chatbot-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=chatbot -p 5432:5432 postgres:17
   docker exec chatbot-db createdb -U postgres chatbot_test
   ```
   두 번째 줄은 테스트용 DB 입니다(연결 오류가 나면 몇 초 뒤 다시). 다음부터는 `docker start chatbot-db` 만 하면 됩니다.
   Docker 를 쓰지 않으면 개인 Render Postgres 의 External Database URL 을 `.env` 의 `DATABASE_URL` 에 넣습니다.
5. 개발 서버: `uv run python -m app` → http://127.0.0.1:8000/api/health
6. 테스트: `uv run pytest` — DB 없이 메모리 SQLite 로 바로 돕니다. DB 코드를 바꾼 PR 은 Postgres 로도 한 번 돌립니다.
   - 맥: `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/chatbot_test uv run pytest`
   - Windows(PowerShell): `$env:TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/chatbot_test"; uv run pytest`
7. 코드 스타일: `uv run ruff format` (포맷 적용), `uv run ruff check --fix` (린트)

맥·Git Bash 에서는 `./run.sh setup`, `./run.sh run`, `./run.sh test`, `./run.sh lint` 로도 실행할 수 있습니다.

## 환경 변수

로컬은 `.env`, 배포(Render)는 대시보드의 Environment 에 넣습니다. 값은 이 문서와 코드에 적지 않습니다.
환경 변수를 추가하면 이 표와 `.env.example` 을 같이 고칩니다.

| 이름 | 설명 | 기본값 |
|---|---|---|
| `LOG_LEVEL` | 서버 로그 레벨 (`DEBUG` / `INFO` / `WARNING` / `ERROR`) | `INFO` |
| `DATABASE_URL` | Postgres 주소. 로컬은 Docker Postgres(`.env.example` 값) 또는 개인 Render Postgres, 배포는 Render Postgres | 없음 — 비어 있으면 서버가 시작하지 않음 |
| `JWT_SECRET` | 로그인 토큰 서명 키(32바이트 이상). 배포에는 `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"` 로 새로 만든 값을 넣는다. 바꾸면 기존 토큰이 전부 무효가 된다 | 없음 — 비어 있거나 짧으면 서버가 시작하지 않음 |
| `JWT_EXPIRE_MINUTES` | 로그인 유지 시간(분). 지나면 401 → 다시 로그인 | `60` |
| `COOKIE_SECURE` | 로그인 쿠키를 https 로만 보내게 할지. 로컬 http 개발에서만 `false` | `true` |
| `CORS_ORIGINS` | 프론트를 다른 주소에 따로 배포할 때 그 주소. 여러 개는 쉼표로 | 없음 — 같은 주소에서만 호출 가능 |
| `TEST_DATABASE_URL` | 테스트 전용. 주면 테스트를 이 Postgres 로 돌린다. `.env` 에서는 읽지 않으니 명령 앞에 붙인다. 테스트가 테이블을 지우므로 DB 이름에 `test` 가 들어가야 한다 | 없음 — 메모리 SQLite |
| `OPENROUTER_API_KEY` | 서버의 OpenRouter 인증 키. 미설정 시 채팅 요청에 503을 반환한다 | 없음 |
| `AI_MODEL` | OpenRouter 모델 ID. StreamLake 제공자만 사용하며 다른 제공자로 fallback하지 않는다 | `qwen/qwen3-30b-a3b-instruct-2507` |
| `AI_TIMEOUT_SECONDS` | AI 호출 전체 제한 시간(초), 앱의 자동 재시도 없음 | `30` |
| `AI_MAX_OUTPUT_TOKENS` | 답변의 최대 생성 토큰 수 | `1024` |
| `CHAT_CONTEXT_PAIRS` | 같은 방에서 문맥에 포함할 최근 성공 질문·답변 쌍 수 | `5` |
| `CHAT_MAX_QUESTION_LENGTH` | 앞뒤 공백 제거 후 질문의 최대 글자 수 | `5000` |
| `OPENROUTER_SITE_URL` | 선택 헤더 `HTTP-Referer`. 비어 있으면 생략 | 없음 |
| `OPENROUTER_SITE_NAME` | 선택 헤더 `X-OpenRouter-Title`. 비어 있으면 생략 | 없음 |

## 백엔드 B 작업 요약

권현석: 이슈 #9에 따라 대화방·대화 repository와 인증된 채팅/방 목록 API를 구현했습니다. 최근 성공 Q/A 5쌍으로 문맥을 구성하고 OpenRouter의 StreamLake 제공자만 호출합니다. 입력 검증, 전체 타임아웃, AI·DB 오류 응답, 요청 ID로 연결되는 이벤트 로그를 추가했습니다. 관련 자동 테스트와 실제 서버 확인 스크립트, 채팅 기술 문서를 작성했습니다. 2026-10-09 실제 AI 응답·후속 질문 문맥·PostgreSQL 저장까지 검증했습니다.
