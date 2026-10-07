#!/bin/bash
# 로컬 실행·테스트 진입점.
#
#   ./run.sh setup   가상환경(.venv) 생성 + 개발 의존성 설치
#   ./run.sh run     개발 서버 (코드 변경 시 자동 재시작, http://127.0.0.1:8000)
#   ./run.sh test    테스트 (pytest 인자를 그대로 넘길 수 있다: ./run.sh test -k health)
#
# PYTHON 환경 변수로 인터프리터를 바꿀 수 있다. 기본값은 .venv 의 python.
# setup 은 3.10 이상이 필요하다(macOS 기본 python3 는 3.9) — 예) PYTHON=python3.12 ./run.sh setup
set -e
cd "$(dirname "$0")"

case "${1:-}" in
  setup)
    "${PYTHON:-python3}" -m venv .venv
    .venv/bin/python -m pip install -q -r requirements-dev.txt
    ;;
  run)
    # uvicorn 자체 접근 로그는 끈다 — request_completed 와 내용이 겹치고 request_id 가 없어 검색이 안 된다
    exec "${PYTHON:-.venv/bin/python}" -m uvicorn app.main:app --reload --no-access-log
    ;;
  test)
    shift
    exec "${PYTHON:-.venv/bin/python}" -m pytest "$@"
    ;;
  *)
    echo "사용법: $0 {setup|run|test}" >&2
    exit 1
    ;;
esac
