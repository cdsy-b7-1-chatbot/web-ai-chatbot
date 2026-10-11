import { ApiError } from "./errors.js";

const HEALTH_ENDPOINT = "/api/health";
const AUTH_ENDPOINT = "/api/auth";
const CHAT_ENDPOINT = "/api/chat";

async function requestJson(endpoint, options = {}) {
  const response = await fetch(endpoint, {
    credentials: "same-origin",
    ...options,
  });

  if (!response.ok) {
    let error = null;
    let message = `요청이 실패했습니다. (${response.status})`;

    try {
      const body = await response.json();
      error = body.error ?? null;
      message = body.message ?? message;
    } catch {
      // 오류 응답 본문이 JSON 이 아니어도 HTTP 상태는 호출자에게 전달한다.
    }

    throw new ApiError(response.status, error, message);
  }

  if (response.status === 204) {
    return undefined;
  }

  return response.json();
}

function authRequestOptions(username, password) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  };
}

/**
 * 실제 API 응답을 공통 인터페이스로 전달해 화면 모듈이 통신 방식을 알 필요 없게 한다.
 */
export async function getRealHealthStatus() {
  return requestJson(HEALTH_ENDPOINT);
}

export async function signupReal(username, password) {
  return requestJson(`${AUTH_ENDPOINT}/signup`, authRequestOptions(username, password));
}

export async function loginReal(username, password) {
  await requestJson(`${AUTH_ENDPOINT}/login`, authRequestOptions(username, password));
}

export async function logoutReal() {
  return requestJson(`${AUTH_ENDPOINT}/logout`, { method: "POST" });
}

export async function getRealCurrentUser() {
  return requestJson(`${AUTH_ENDPOINT}/me`);
}

/**
 * 채팅 백엔드의 응답 필드를 변환하지 않아 화면 코드가 Mock과 같은 계약을 사용하게 한다.
 */
export async function sendChatReal(question, conversationId = null) {
  return requestJson(CHAT_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });
}
