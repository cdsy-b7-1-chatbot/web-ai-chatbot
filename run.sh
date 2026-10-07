#!/bin/bash
# 맥·Linux·Git Bash 용 단축 명령. uv 가 필요하다(설치: brew install uv).
# Windows PowerShell 에서는 아래 주석의 uv 명령을 그대로 쓴다(README 참고).
#
#   ./run.sh setup   = uv sync               가상환경(.venv) + 의존성 — .python-version 의 Python 이 없으면 uv 가 내려받는다
#   ./run.sh run     = uv run python -m app  개발 서버 (코드 변경 시 자동 재시작, http://127.0.0.1:8000)
#   ./run.sh test    = uv run pytest         테스트 (pytest 인자를 그대로 넘길 수 있다: ./run.sh test -k health)
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
    exec uv run "${python_opt[@]}" python -m app
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
