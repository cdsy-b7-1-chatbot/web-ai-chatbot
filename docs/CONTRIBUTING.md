# 협업 가이드

## 한눈에 보기

```
1. develop 에서 브랜치 만들기   git switch develop
                                git pull
                                git switch -c feature/<주제>
2. 작업하고 커밋                git commit -m "feat: 로그인 API 추가"
3. 푸시하고 PR (→ develop)      git push -u origin feature/<주제>
4. 다른 팀원 1명 이상 Approve → Merge (Create a merge commit)
5. 브랜치 삭제                  PR 화면 Delete branch → 로컬 git switch develop, git pull, git branch -d feature/<주제>
```

## 1. 브랜치

```
feature/common  ──PR──┐
feature/auth    ──PR──┼──▶ develop ───(배포할 때만, PR 1개)───▶ main ──▶ Render 배포
feature/ai-chat ──PR──┘   (기능이 하나씩 쌓임)                 (develop 전체가 한 번에)
```

| 브랜치 | 용도 | 규칙 |
|---|---|---|
| `main` | 배포·평가용. Render 가 이 브랜치를 배포 | 직접 push 금지. develop → main PR 로만 |
| `develop` | 통합용. **레포 기본 브랜치** | 직접 push 금지. 기능 PR 로만 |
| `feature/<주제>` | 기능 작업 | 예) `feature/auth`, `feature/ai-chat`, `feature/frontend` |
| `fix/<주제>` | 버그 수정 | develop 에서 만들어 develop 으로 |
| `docs/<주제>`, `chore/<주제>` | 문서, 설정·배포 | 예) `chore/deploy` |

- 기능 브랜치는 **항상 develop 에서** 만들고 **develop 으로** PR 을 올린다. main 으로 바로 올리지 않는다.
- main 은 배포할 때만 develop → main PR(릴리스 PR) 하나로 올린다. 기능마다 main 에 따로 머지하지 않는다.

## 2. 디렉터리와 코드 구조

기능 영역은 `app/<영역 이름>/` 아래에 만든다. **새 영역을 만드는 사람이 같은 PR 에서 아래 표에 한 줄 추가**한다.

| 경로 | 내용 | 담당 |
|---|---|---|
| `app/core/` | 공통 기반 — 설정, 서버 로그, 요청 미들웨어, 오류 응답, /docs | 백엔드 A |
| `tests/` | 테스트 — `tests/test_<모듈>.py` | 각 담당 |
| `docs/` | 협업·기술 문서 | 전원 |

### 영역 안의 구성

```
app/<영역>/
  router.py        HTTP 입출력만 — 요청을 받아 service 를 부르고 응답을 돌려준다
  service.py       비즈니스 로직 — 판단·계산·외부 API 호출
  schemas.py       요청·응답 모델(Pydantic) — API 가 주고받는 모양
  repository.py    저장·조회 함수
app/db/
  database.py      DB 연결 — 엔진·세션·get_db
  models/          테이블(ORM 모델) — 테이블마다 파일 하나 (user.py, chat.py …)
```

- 호출 방향은 `router → service → repository → app/db/models` 한쪽으로만. 거꾸로 부르지 않는다.
- **테이블 정의는 `app/db/models/` 에만 둔다.** 영역 안에 모델을 따로 만들지 않고, 모두 여기서 가져다 쓴다.
- **테이블 설계와 모델은 백엔드 A 가 맡는다.** 테이블을 추가·변경해야 하면 이슈를 등록하고 백엔드 A 를 담당자로 지정한다.
  A 가 ERD(#1)와 모델을 고친 뒤 각 영역이 저장·조회 함수를 맞춘다.
- 다른 영역의 저장·조회 함수가 필요하면 복사하지 말고 그 영역의 `repository.py` 를 가져다 쓴다.
- router 에서 DB 를 직접 조회하지 않는다.
- service 는 FastAPI 의 Request·Response 를 쓰지 않는다(HTTP 없이도 테스트할 수 있게).
- 테이블 모델(ORM)을 그대로 응답하지 않고 schemas 의 응답 모델로 바꿔 내보낸다(비밀번호 해시 같은 필드가 실수로 나가지 않게).
- 로직이 없는 단순한 엔드포인트는 service 를 생략해도 된다.
- 남의 영역 파일을 고쳐야 하면, PR 에서 그 영역 담당자를 리뷰어로 지정한다.
- `app/main.py` 에는 각자 라우터 등록 한 줄씩만 추가한다(여러 명이 고치는 파일이라 충돌을 줄이기 위해).

## 3. 코드 스타일

- 이름은 PEP 8 — 변수·함수·모듈 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE_CASE`.
- 포맷과 린트는 **ruff** 가 맡는다. 커밋 전에 실행한다(맥·Windows 같은 명령).
  ```
  uv run ruff format          # 포맷 자동 적용
  uv run ruff check --fix     # 린트 — 고칠 수 있는 건 자동으로 고친다
  ```
- 함수 인자와 반환값에는 타입 힌트를 단다.
- 주석·docstring 은 한국어로, "무엇을"보다 "왜"를 적는다.
- (선택) VS Code 는 Ruff 확장을 설치하고 저장할 때 포맷을 켜 두면 따로 실행하지 않아도 된다.

## 4. 커밋 메시지

```
<type>: <무엇을 바꿨는지 한국어로>

<필요하면 본문 — 무엇을, 왜>

Refs #<이슈 번호>
```

| type | 언제 |
|---|---|
| `feat` | 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 |
| `test` | 테스트 추가·수정 |
| `refactor` | 동작은 그대로 두고 코드 구조만 개선 |
| `style` | 동작에 영향 없는 포맷 변경 |
| `chore` | 설정, 의존성, 배포 등 |

- 예) `feat: 회원가입 시 아이디 중복 검사 추가`
- 금지) `update`, `fix`, `wip`, `수정` 처럼 무엇을 바꿨는지 알 수 없는 메시지
- 과제 요건: **팀원별 의미 있는 커밋 10회 이상** — 기능 단위로 나눠서 커밋한다.

## 5. 이슈와 PR

- 작업을 시작하기 전에 이슈를 만든다. 새 이슈 화면에서 **"작업" 템플릿**을 고르면 목적·할 일·완료 조건 양식이 채워진다(강제 아님 — 설계 논의처럼 자유 형식이 맞는 이슈는 빈 이슈로).
- PR 본문의 "관련 이슈"에 `Closes #<이슈 번호>` 를 적는다 → develop 에 머지되면 이슈가 **자동으로 닫힌다**.
- PR 템플릿(관련 이슈 / 변경 내용 / 확인 결과 / 체크리스트 / 리뷰 요청 사항)을 채운다. "확인 결과"는 리뷰어가 그대로 따라 할 수 있게 적는다.
- 머지 조건: **작성자가 아닌 팀원 1명 이상 Approve**.
- 머지 방식: **Create a merge commit** (개인별 커밋 이력이 남아야 과제 평가에서 확인된다. Squash 를 누르면 커밋이 하나로 합쳐져 사라진다).

## 6. PR 올리기 전 체크리스트

PR 템플릿에도 같은 체크박스가 있다.

- [ ] `uv run pytest` 가 통과한다
- [ ] `uv run ruff format`, `uv run ruff check` 를 실행했고 경고가 없다
- [ ] 새 기능·버그 수정에는 테스트를 같이 넣었다
- [ ] 새 엔드포인트는 응답 모델·예시 값·날 수 있는 오류(`error_responses`)를 선언했다 — 선언하지 않으면 /docs 에 형식이 비어 보인다
- [ ] 환경 변수를 추가했다면 `.env.example` 과 README 환경 변수 표를 같이 고쳤다
- [ ] 코드·커밋·PR 본문·스크린샷에 키·비밀번호가 없다
- [ ] DB 를 건드렸다면 Postgres(로컬 Docker 또는 개인 Render)로 서버를 띄워 직접 확인했다

## 7. 리뷰

- **Files changed** 탭에서 코드 줄을 지정해 코멘트를 달고, **Review changes** 로 Approve 또는 Request changes 를 제출한다.
- "LGTM" 한 줄만 남기지 않는다. 줄을 지정한 코멘트를 1개 이상 남긴다. 질문도 좋은 코멘트다.
  - "빈 문자열이 들어오면 어떻게 되나요?"
  - "이 함수 반환 타입도 적어 주면 좋겠습니다."
- 작성자는 코멘트를 반영한 커밋을 push 한 뒤 그 스레드에 **"반영했습니다: <커밋 해시>"** 라고 답한다.

## 8. 머지 후 정리

- 브랜치는 **PR 작성자가** 삭제한다. PR 화면의 **Delete branch** 버튼.
- 로컬 정리:
  ```
  git switch develop
  git pull
  git branch -d feature/<주제>
  git fetch --prune
  ```
- 브랜치를 지워도 PR·커밋·리뷰 기록은 남는다. 필요하면 PR 화면의 **Restore branch** 로 되살린다.

## 9. 충돌이 나면

PR 화면에 `This branch has conflicts` 가 뜨면, **나중에 머지하려는 PR 의 작성자가 자기 브랜치에서** 해결한다.

```
git switch feature/<내 브랜치>
git fetch origin
git merge origin/develop        # 충돌난 파일에 <<<<<<< ======= >>>>>>> 표시가 생긴다
# 파일을 열어 표시를 지우고 최종 내용으로 정리
git add <해결한 파일>
git commit
git push
```

- 해결하기 전에 팀 채널에 "어느 PR 과 어느 파일에서 부딪혔는지" 한 줄 알리고, 상대 변경의 의도를 모르면 물어본다.
- `git rebase`, `git push --force` 는 쓰지 않는다(이미 올라간 이력이 바뀐다).
- 해결 커밋을 push 한 뒤 리뷰어에게 재리뷰를 요청한다.

## 10. 의존성(패키지) 추가

- **`uv add <패키지>`** 로만 추가한다. 테스트·개발용은 `uv add --dev <패키지>`.
  `pip install` 은 쓰지 않는다 — `uv.lock` 에 남지 않아 다른 사람 환경과 Render 에서 깨진다.
- `pyproject.toml` 과 `uv.lock` 은 **같은 커밋**에 넣는다.
- 다른 사람의 PR 이 의존성을 바꿨다면 `git pull` 뒤 `uv sync` 를 한 번 실행한다.
- `uv.lock` 이 충돌하면 손으로 고치지 않는다. `pyproject.toml` 충돌만 정리하고 `uv lock` 으로 `uv.lock` 을 다시 만든다.

## 11. API 문서 (/docs)

- **API 명세는 /docs 다.** (로컬 http://127.0.0.1:8000/docs, 배포 `<배포 URL>/docs`) 따로 손으로 쓰지 않는다.
  맨 위에 응답 형식·오류 코드 표·요청 추적 방법이 있고, 엔드포인트별 요청·응답은 코드에서 자동으로 만들어진다.
- 새 엔드포인트를 만들 때:
  - 요청·응답을 Pydantic 모델로 선언하고 예시를 넣는다 — `model_config = ConfigDict(json_schema_extra={"examples": [...]})`
  - 날 수 있는 오류를 선언한다 — `responses=error_responses(401, 409)`
- 오류는 `raise AppError(상태 코드, ErrorCode.코드, "안내 문구")` 로 낸다. `HTTPException` 은 쓰지 않는다.
- 새 오류 코드는 `app/core/errors.py` 의 `ErrorCode` 와 `ERROR_CODE_DOCS` 에 **함께** 추가한다(빠뜨리면 테스트가 실패한다).
- 서버 로그는 `log_event(logger, "이벤트명", 필드=값)` 으로 남긴다. `print` 는 쓰지 않는다.

## 12. 민감정보

- API 키, DB 접속 주소, JWT 비밀키는 **`.env`(로컬)와 Render 환경 변수에만** 둔다.
  코드·문서·커밋·PR·이슈·팀 채팅에 붙여 넣지 않는다.
- 스크린샷에 주의한다 — Render 대시보드의 Environment 화면, `.env` 를 연 에디터, DB 접속 주소가 보이는 화면.
- 로그에 비밀번호·토큰·키를 남기지 않는다.
- `.env` 는 `.gitignore` 에 들어 있다. 그래도 `git add .` 전에 `git status` 로 올라갈 파일을 확인한다.
- **실수로 올렸다면**: 커밋을 지우는 것으로는 부족하다(이력과 다른 사람의 복사본에 남는다).
  **즉시 그 키를 폐기·재발급**하고 팀에 알린다.

## 13. 릴리스 (develop → main)

- **누가**: PM. **언제**: 배포가 필요할 때, 그리고 평가 전 마지막에.
- develop → main PR 하나를 올린다. 제목 `release: <날짜 또는 내용>`, 본문에 이번에 들어가는 PR 목록.
- 머지 전 확인:
  - [ ] develop 에서 `uv run pytest` 통과
  - [ ] 로컬에서 주요 흐름 확인: 가입 → 로그인 → 질문 → 응답 → 내 기록
  - [ ] README 갱신(환경 변수 표, API·배포 URL)
- 머지 후 확인:
  - [ ] Render 배포 완료, `<배포 URL>/api/health` 가 200
  - [ ] 외부 네트워크(휴대폰 데이터 등)에서 접속
- main 에는 릴리스 PR 말고는 머지하지 않는다. 급한 수정도 `fix/*` → develop → 릴리스 PR 순서로 올린다.

## 14. 개발 환경

README 의 "로컬 개발 환경 (맥·Windows 공통)" 을 따른다(uv).
