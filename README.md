# 웹 기반 AI 챗봇 서비스

Codyssey B7-1 팀 프로젝트입니다. FastAPI로 회원 인증, AI 질문·응답, 사용자별 대화 기록을 제공합니다.

회원가입·로그인, 인증된 사용자용 채팅·대화방 목록·내 기록 조회 API와 웹 화면을 Render에 배포했습니다.

- 서비스: https://web-ai-chatbot-33yw.onrender.com
- API 명세: https://web-ai-chatbot-33yw.onrender.com/docs
- 이용 방법: 회원가입 → 로그인 → 질문 입력 → 같은 대화방에서 후속 질문
- 배포 설정·재배포·DB 확인: [배포 가이드](docs/deployment.md)
- 실제 화면·서버 로그·검증 결과: [배포 검증 증빙](docs/verification.md)

무료 웹서비스는 한동안 요청이 없으면 쉬었다가 첫 접속 때 다시 시작하므로 응답이 늦어질 수 있습니다. 현재 무료 PostgreSQL 만료일은 **2026-11-14**입니다.

## 프로젝트 개요

- 문제 정의: 질문과 개념 설명, 글 요약을 웹에서 요청하고 이전 대화를 확인할 수 있는 서비스가 필요합니다.
- 타깃 사용자: 웹에서 질문·개념 설명·요약을 요청하고, 같은 주제의 후속 질문을 이어가려는 사용자입니다.
- 핵심 시나리오: 가입 → 로그인 → 질문 → 같은 대화방의 최근 문맥으로 AI 응답 → DB 저장 → 화면에서 응답·기록 확인입니다.

팀에서 합의한 범용 챗봇을 구현했습니다. 실제 AI 호출은 서버가 처리하며, 사용자는 자신의 대화방과 기록을 조회할 수 있습니다.

## 팀 역할

| 이름 | 역할 | 주 담당 |
| --- | --- | --- |
| 이동현 | PM | 내 기록 조회 API, 이슈·PR·일정 관리, 통합 검증, 배포 조율, 제출 문서 |
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

`app/auth/`의 인증 → `app/chat/router.py`의 HTTP 입출력 → `service.py`의 문맥·AI·저장 흐름 → `repository.py` → PostgreSQL로 연결됩니다. AI 호출은 서버의 `client.py`에서 코디세이 OpenAI 호환 API로 전송합니다.

- API 명세·요청/응답 예시: 실행한 서버의 `/docs` (로컬 http://127.0.0.1:8000/docs)
- ERD·인증·repository 설계: [이슈 #1](https://github.com/cdsy-b7-1-chatbot/web-ai-chatbot/issues/1), 테이블 정의 `app/db/models/`
- 백엔드 A DB·인증·공통 기반 설계와 검증 방법: [DB·인증 기술 문서](docs/auth.md)
- 백엔드 B 구현·검증 방법: [채팅 기술 문서](docs/chat.md)
- 내 전체·대화방별 기록 조회 및 프론트 연결: [기록 조회 API](docs/history.md)
- 사용자별 DB 확인: [확인용 SQL](scripts/check_chat_logs.sql)
- `app/history/`의 `list_chats`와 `GET /api/me/chats`, 배포 URL·최종 팀 작업 요약 취합: PM 담당

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

로컬은 `.env`, 배포(Render)는 대시보드의 Environment 에 넣습니다. 민감정보의 실제 값은 이 문서와 코드에 적지 않습니다.
환경 변수를 추가하면 이 표와 `.env.example` 을 같이 고칩니다.

| 이름 | 설명 | 기본값 |
|---|---|---|
| `LOG_LEVEL` | 서버 로그 레벨 (`DEBUG` / `INFO` / `WARNING` / `ERROR`). 화면 정적 파일(`/static/`)·배포 헬스 체크(`/api/health`) 요청 로그는 `DEBUG` 에서만 보인다(실패는 `INFO`) | `INFO` |
| `DATABASE_URL` | Postgres 주소. 로컬은 Docker Postgres(`.env.example` 값) 또는 개인 Render Postgres, 배포는 Render Postgres | 없음 — 비어 있으면 서버가 시작하지 않음 |
| `JWT_SECRET` | 로그인 토큰 서명 키(32바이트 이상). 배포에는 `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"` 로 새로 만든 값을 넣는다. 바꾸면 기존 토큰이 전부 무효가 된다 | 없음 — 비어 있거나 짧으면 서버가 시작하지 않음 |
| `JWT_EXPIRE_MINUTES` | 로그인 유지 시간(분). 지나면 401 → 다시 로그인 | `60` |
| `COOKIE_SECURE` | 로그인 쿠키를 https 로만 보내게 할지. 로컬 http 개발에서만 `false` | `true` |
| `CORS_ORIGINS` | 프론트를 다른 주소에 따로 배포할 때 그 주소. 여러 개는 쉼표로 | 없음 — 같은 주소에서만 호출 가능 |
| `TEST_DATABASE_URL` | 테스트 전용. 주면 테스트를 이 Postgres 로 돌린다. `.env` 에서는 읽지 않으니 명령 앞에 붙인다. 테스트가 테이블을 지우므로 DB 이름에 `test` 가 들어가야 한다 | 없음 — 메모리 SQLite |
| `CODYSSEY_API_KEY` | 코디세이 콘솔에서 발급한 OpenAI 호환 키. 서버에만 설정하며 미설정 시 채팅 요청에 503을 반환한다 | 없음 |
| `AI_MODEL` | 코디세이 콘솔의 사용 가능한 채팅 모델 ID | `gpt-5-mini` |
| `AI_TIMEOUT_SECONDS` | AI 호출 전체 제한 시간(초), 앱의 자동 재시도 없음 | `30` |
| `AI_MAX_OUTPUT_TOKENS` | 답변의 최대 생성 토큰 수 | `1024` |
| `CHAT_CONTEXT_PAIRS` | 같은 방에서 문맥에 포함할 최근 성공 질문·답변 쌍 수 | `5` |
| `CHAT_MAX_QUESTION_LENGTH` | 앞뒤 공백 제거 후 질문의 최대 글자 수 | `5000` |

코디세이 콘솔의 **OpenAI** 호환 방식으로 키를 발급해 `CODYSSEY_API_KEY`에 넣습니다. 서버는 `https://copa.codyssey.kr/v1/chat/completions`를 호출합니다. 배포 환경은 `AI_MODEL=gemini-3.1-flash-lite`로 설정했습니다. 코드 기본값은 위 표와 같습니다. 모델 가용 여부와 잔여 할당량은 코디세이 콘솔에서 확인합니다.

## PM 작업 요약

이동현: 이슈 #1·#11의 분담에 따라 내 전체·선택한 대화방의 기록 조회 API를 구현했습니다. 기존 인증·ORM 모델을 사용하며 사용자 범위, 대화방 소유권, 실패 이력, 최신순 정렬과 페이지 처리를 적용했습니다. 조회에는 AI 키가 필요하지 않습니다. 배포용 AI 호출을 코디세이 OpenAI 호환 API로 전환하고 관련 설정과 테스트를 맞췄습니다. Render 무료 웹서비스와 PostgreSQL을 연결해 배포하고, 외부 URL의 가입·로그인·실제 AI 응답·문맥 유지·기록 조회와 서비스 재시작 후 기록 유지를 확인했습니다. 관련 자동 테스트와 프론트 연결 명세는 [기록 조회 문서](docs/history.md)에 정리했습니다.

## 백엔드 A 작업 요약

이상우: 이슈 #1·#2에 따라 공통 기반과 DB·인증을 구현했습니다. 공통 기반은 `{error, message}` 오류 형식과 전역 예외 처리, 요청마다 `request_id`가 붙는 서버 로그, `/docs` API 명세, uv 기반 맥·Windows 개발 환경입니다(#4). DB는 users·conversations·chats 테이블 모델과 PostgreSQL 연결·세션을 만들었습니다(#6). 인증은 Argon2id 비밀번호 해시와 JWT HttpOnly 쿠키로 회원가입·로그인·로그아웃·로그인 사용자 확인(`CurrentUser`)을 구현하고, 요청 로그에 로그인 사용자의 `user_id`를 남기게 했습니다(#7). 이후 화면 정적 파일(#28)과 배포 헬스 체크(#35) 요청 로그를 DEBUG로 낮췄습니다. 팀 협업 가이드와 이슈·PR 템플릿을 작성했고(#5), B·PM·FE의 PR(#12·#15·#26)이 테이블·세션·인증 의존성을 계약대로 쓰는지 확인했습니다. 설계 결정과 검증 방법은 [DB·인증 기술 문서](docs/auth.md)에 정리했습니다.

## 백엔드 B 작업 요약

권현석: 이슈 #9에 따라 대화방·대화 repository와 인증된 채팅/방 목록 API를 구현했습니다. 최근 성공 Q/A 5쌍으로 문맥을 구성하고, 초기 AI 연동은 OpenRouter의 StreamLake 제공자로 구현했습니다. 입력 검증, 전체 타임아웃, AI·DB 오류 응답, 요청 ID로 연결되는 이벤트 로그를 추가했습니다. 관련 자동 테스트와 실제 서버 확인 스크립트, 채팅 기술 문서를 작성했습니다. 2026-10-09 실제 AI 응답·후속 질문 문맥·PostgreSQL 저장까지 검증했습니다.

## 프론트엔드 작업 요약

우광택: 가입·로그인·로그아웃, 인증 확인·오류 안내, 채팅과 대화방 목록 화면을 구현했습니다(#26). 같은 화면에서 질문과 AI 응답을 확인하고, 대화방을 선택하면 저장된 기록을 불러오도록 API를 연결했습니다. 새 대화, 모바일 대화방 패널, 로딩·실패·재시도 표시를 구현하고 프론트 API·인증·채팅·목록·화면 조정 모듈의 자동 테스트를 작성했습니다.
