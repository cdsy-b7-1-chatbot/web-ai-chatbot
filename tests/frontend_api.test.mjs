import assert from "node:assert/strict";
import test from "node:test";

globalThis.document = { documentElement: { dataset: { authApiMode: "mock" } } };

const api = await import("../frontend/js/api/api.js");
const { ApiError } = await import("../frontend/js/api/errors.js");

async function assertApiError(action, expected) {
  await assert.rejects(action, (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.name, "ApiError");
    assert.equal(error.status, expected.status);
    assert.equal(error.error, expected.error);
    assert.equal(error.message, expected.message);
    return true;
  });
}

test("Mock 인증 API는 가입·로그인·현재 사용자·로그아웃 흐름을 제공한다", async () => {
  const user = await api.signup("Mock_User", "password123");
  assert.deepEqual(user, { id: 1, username: "mock_user" });

  await assertApiError(() => api.getCurrentUser(), {
    status: 401,
    error: "UNAUTHORIZED",
    message: "로그인이 필요합니다.",
  });
  await api.login("MOCK_USER", "password123");
  assert.equal(await api.login("MOCK_USER", "password123"), undefined);
  assert.deepEqual(await api.getCurrentUser(), user);
  assert.equal(await api.logout(), undefined);
  await assertApiError(() => api.getCurrentUser(), {
    status: 401,
    error: "UNAUTHORIZED",
    message: "로그인이 필요합니다.",
  });
});

test("Mock 인증 API는 백엔드 오류 상태와 코드를 전달한다", async () => {
  await assertApiError(() => api.signup("ab", "short"), {
    status: 422,
    error: "VALIDATION_ERROR",
    message: "입력값이 올바르지 않습니다.",
  });
  await assertApiError(() => api.signup("mock_user", "password123"), {
    status: 409,
    error: "USERNAME_TAKEN",
    message: "이미 사용 중인 아이디입니다.",
  });
  await assertApiError(() => api.login("mock_user", "wrong-password"), {
    status: 401,
    error: "INVALID_CREDENTIALS",
    message: "아이디 또는 비밀번호가 올바르지 않습니다.",
  });
});

test("api.js는 Real 인증 API와 일관된 공개 반환값을 사용한다", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const requests = [];
  document.documentElement.dataset.authApiMode = "real";
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    if (url === "/api/auth/signup") {
      return { ok: true, status: 201, json: async () => ({ id: 1, username: "user" }) };
    }
    if (url === "/api/auth/me") {
      return { ok: true, status: 200, json: async () => ({ id: 1, username: "user" }) };
    }
    return { ok: true, status: 200, json: async () => ({ access_token: "not-exposed" }) };
  };
  assert.deepEqual(await api.signup("user", "password123"), { id: 1, username: "user" });
  assert.equal(await api.login("user", "password123"), undefined);
  assert.deepEqual(requests[0], {
    url: "/api/auth/signup",
    options: {
      credentials: "same-origin",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "user", password: "password123" }),
    },
  });
  assert.deepEqual(requests[1], {
    url: "/api/auth/login",
    options: {
      credentials: "same-origin",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "user", password: "password123" }),
    },
  });
  assert.deepEqual(await api.getCurrentUser(), { id: 1, username: "user" });
  assert.deepEqual(requests[2], {
    url: "/api/auth/me",
    options: { credentials: "same-origin" },
  });

  globalThis.fetch = async () => ({
    ok: true,
    status: 204,
    json: async () => {
      throw new Error("204 응답은 JSON 으로 읽으면 안 됩니다.");
    },
  });
  assert.equal(await api.logout(), undefined);

  globalThis.fetch = async () => ({
    ok: false,
    status: 401,
    json: async () => ({ error: "INVALID_CREDENTIALS", message: "로그인에 실패했습니다." }),
  });
  await assertApiError(() => api.login("user", "wrong"), {
    status: 401,
    error: "INVALID_CREDENTIALS",
    message: "로그인에 실패했습니다.",
  });

  const networkError = new TypeError("Failed to fetch");
  globalThis.fetch = async () => {
    throw networkError;
  };
  await assert.rejects(() => api.getCurrentUser(), (error) => error === networkError);
  document.documentElement.dataset.authApiMode = "mock";
});

test("기존 Health API는 Mock과 Real 모드에서 계속 동작한다", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
    delete document.documentElement.dataset.healthApiMode;
  });

  document.documentElement.dataset.healthApiMode = "mock";
  assert.deepEqual(await api.getHealthStatus(), { status: "ok" });
  assert.equal(api.getHealthStatusSource(), "Mock");

  document.documentElement.dataset.healthApiMode = "real";
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/health");
    assert.deepEqual(options, { credentials: "same-origin" });
    return { ok: true, status: 200, json: async () => ({ status: "ok" }) };
  };
  assert.deepEqual(await api.getHealthStatus(), { status: "ok" });
  assert.equal(api.getHealthStatusSource(), "실제");
});
