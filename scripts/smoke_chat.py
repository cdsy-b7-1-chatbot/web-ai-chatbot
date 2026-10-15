"""실행 중인 서버에서 AI 문맥·기록 저장·로그아웃·재로그인을 확인한다. 계정과 대화 2개를 남긴다."""

import argparse
import json
import secrets
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


def checked(response: httpx.Response, expected: int) -> dict[str, Any]:
    if response.status_code != expected:
        # 서버 오류 원문이나 인증 응답을 출력하지 않는다.
        raise RuntimeError(f"{response.request.url.path}: HTTP {response.status_code}")
    return {} if expected == 204 else response.json()


def check_history(
    client: httpx.Client,
    headers: dict[str, str],
    user_id: int,
    conversation_id: int,
    expected: dict[int, dict[str, str]],
) -> None:
    items = checked(
        client.get("/api/me/chats", headers=headers, params={"conversation_id": conversation_id}),
        200,
    )["items"]
    if len(items) != len(expected) or {item["id"] for item in items} != set(expected):
        raise RuntimeError("저장된 대화 기록 ID 확인 실패")
    for item in items:
        if item["user_id"] != user_id or item["conversation_id"] != conversation_id:
            raise RuntimeError("대화 기록의 사용자·대화방 확인 실패")
        saved = expected[item["id"]]
        if (
            item["question"] != saved["question"]
            or item["answer"] != saved["answer"]
            or item["status"] != "success"
        ):
            raise RuntimeError("대화 기록의 질문·응답 확인 실패")
        created_at = item["created_at"]
        if not isinstance(created_at, str) or datetime.fromisoformat(created_at).tzinfo is None:
            raise RuntimeError("대화 기록의 생성 시각 확인 실패")


def smoke(base_url: str) -> dict[str, Any]:
    account = {
        "username": f"smoke_{secrets.token_hex(5)}",
        "password": secrets.token_urlsafe(24),
    }
    first_question = "테스트용 별명은 파란별입니다. 기억하고 한 문장으로 답해 주세요."
    second_question = "내가 방금 알려준 별명을 말해 주세요."
    with httpx.Client(base_url=base_url, timeout=40) as client:
        checked(client.get("/api/health"), 200)
        user = checked(client.post("/api/auth/signup", json=account), 201)
        login = checked(client.post("/api/auth/login", json=account), 200)
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        first_response = client.post(
            "/api/chat",
            headers=headers,
            json={"question": first_question},
        )
        first = checked(first_response, 200)
        second_response = client.post(
            "/api/chat",
            headers=headers,
            json={
                "question": second_question,
                "conversation_id": first["conversation_id"],
            },
        )
        second = checked(second_response, 200)
        if "파란별" not in second["answer"]:
            raise RuntimeError("후속 질문의 별명 문맥 확인 실패")
        rooms = checked(client.get("/api/conversations", headers=headers), 200)
        if not any(room["id"] == first["conversation_id"] for room in rooms["items"]):
            raise RuntimeError("대화방 목록 확인 실패")
        expected = {
            first["chat_id"]: {"question": first_question, "answer": first["answer"]},
            second["chat_id"]: {"question": second_question, "answer": second["answer"]},
        }
        check_history(client, headers, user["id"], first["conversation_id"], expected)
        checked(client.post("/api/auth/logout"), 204)
        # 로그아웃 뒤에는 보관한 Bearer 헤더도 제외하고 접근 차단을 확인한다.
        checked(client.get("/api/me/chats"), 401)
        login = checked(client.post("/api/auth/login", json=account), 200)
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        check_history(client, headers, user["id"], first["conversation_id"], expected)
        checked(client.post("/api/auth/logout"), 204)
    return {
        "user_id": user["id"],
        "conversation_id": first["conversation_id"],
        "chat_ids": [first["chat_id"], second["chat_id"]],
        "context_verified": True,
        "history_verified": True,
        "logout_verified": True,
        "relogin_history_verified": True,
        "request_ids": [
            first_response.headers["X-Request-ID"],
            second_response.headers["X-Request-ID"],
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--result", type=Path, help="키·토큰 없는 검증 결과 JSON 저장 경로")
    args = parser.parse_args()
    try:
        result = smoke(args.base_url)
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError) as error:
        # 네트워크 예외 원문에는 URL 등이 포함될 수 있어 종류만 표시한다.
        sys.stderr.write(f"검증 실패: {type(error).__name__}\n")
        if isinstance(error, RuntimeError):
            sys.stderr.write(f"{error}\n")
        return 1
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.result:
        args.result.write_text(output, encoding="utf-8")
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
