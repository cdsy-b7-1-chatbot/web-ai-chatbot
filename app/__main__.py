"""개발 서버 진입점 — 맥·Windows 공통으로 `uv run python -m app`.

uvicorn 옵션을 여기 한 곳에 둬서 OS 마다 다른 셸 스크립트 없이 같은 명령을 쓴다.
배포(Render)는 이 파일이 아니라 uvicorn 을 직접 실행한다(코드 변경 감지·재시작이 필요 없으므로).
"""

import uvicorn


def main() -> None:
    # access_log=False: uvicorn 자체 접근 로그는 request_completed 와 겹치고 request_id 가 없다
    uvicorn.run("app.main:app", reload=True, access_log=False)


if __name__ == "__main__":  # Windows 에서 reload 가 새 프로세스를 띄울 때 다시 실행되지 않게 막는다
    main()
