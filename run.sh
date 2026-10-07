#!/bin/bash
# 로컬 실행·테스트 진입점. uv 가 필요하다(설치: brew install uv).
#
#   ./run.sh setup   가상환경(.venv) 생성 + 의존성 설치 — .python-version 의 Python 이 없으면 uv 가 내려받는다
#   ./run.sh run     개발 서버 (코드 변경 시 자동 재시작, http://127.0.0.1:8000)
#   ./run.sh test    테스트 (pytest 인자를 그대로 넘길 수 있다: ./run.sh test -k health)
#
# PYTHON 환경 변수로 인터프리터를 바꿀 수 있다. 예) PYTHON=3.13 ./run.sh test
set -e
cd "$(dirname "$0")"

if ! command -v uv &>/dev/null; then
  echo "uv 가 필요합니다. 설치: brew install uv  (또는 https://docs.astral.sh/uv/)" >&2
  exit 1
fi

python_opt=()
[ -n "$PYTHON" ] && python_opt=(--python "$PYTHON")

case "${1:-}" in
  setup)
    uv sync "${python_opt[@]}"
    ;;
  run)
    # uvicorn 자체 접근 로그는 끈다 — request_completed 와 내용이 겹치고 request_id 가 없어 검색이 안 된다
    exec uv run "${python_opt[@]}" uvicorn app.main:app --reload --no-access-log
    ;;
  test)
    shift
    exec uv run "${python_opt[@]}" pytest "$@"
    ;;
  *)
    echo "사용법: $0 {setup|run|test}" >&2
    exit 1
    ;;
esac
