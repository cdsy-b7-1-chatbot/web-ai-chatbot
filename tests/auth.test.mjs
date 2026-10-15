import assert from "node:assert/strict";
import test from "node:test";

class FakeElement {
  constructor() {
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.textContent = "";
    this.value = "";
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  reset() {
    this.resetCalled = true;
  }
}

function createAuthDocument() {
  const ids = [
    "login-form",
    "signup-form",
    "auth-message",
    "auth-title",
    "auth-description",
    "login-username",
    "login-password",
    "signup-username",
    "signup-password",
    "login-submit",
    "signup-submit",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  const viewButtons = [new FakeElement(), new FakeElement()];
  viewButtons[0].dataset.authView = "signup";
  viewButtons[1].dataset.authView = "login";
  elements["signup-form"].hidden = true;

  return {
    documentElement: { dataset: { authApiMode: "mock" } },
    querySelector(selector) {
      return elements[selector.slice(1)] ?? null;
    },
    querySelectorAll(selector) {
      return selector === "[data-auth-view]" ? viewButtons : [];
    },
    elements,
    viewButtons,
  };
}

async function trigger(element, type) {
  let prevented = false;
  const promises = (element.listeners.get(type) ?? []).map((listener) =>
    listener({ preventDefault: () => { prevented = true; } }),
  );
  await Promise.all(promises);
  return prevented;
}

globalThis.document = createAuthDocument();
const { ApiError } = await import("../frontend/js/api/errors.js");
const { getAuthErrorMessage, initializeAuth, validateLogin, validateSignup } = await import(
  "../frontend/js/auth.js"
);

test("회원가입과 로그인 검증은 각 폼의 규칙을 적용한다", () => {
  assert.equal(validateSignup("ab", "password123"), "아이디는 3~20자 영문, 숫자, 밑줄만 사용할 수 있습니다.");
  assert.equal(validateSignup("valid_user", "short"), "비밀번호는 8~64자를 입력해 주세요.");
  assert.equal(validateSignup("valid_user", "password123"), null);
  assert.equal(validateLogin("", "password"), "아이디와 비밀번호를 모두 입력해 주세요.");
  assert.equal(validateLogin("a!", "x"), null);
});

test("인증 화면은 로그인과 회원가입 폼을 전환한다", async () => {
  const authDocument = createAuthDocument();
  globalThis.document = authDocument;
  initializeAuth();

  assert.equal(await trigger(authDocument.viewButtons[0], "click"), false);
  assert.equal(authDocument.elements["login-form"].hidden, true);
  assert.equal(authDocument.elements["signup-form"].hidden, false);
  assert.equal(authDocument.elements["auth-title"].textContent, "회원가입");
  assert.equal(authDocument.elements["auth-description"].textContent, "새 계정을 만들어 대화를 시작해 보세요.");

  await trigger(authDocument.viewButtons[1], "click");
  assert.equal(authDocument.elements["login-form"].hidden, false);
  assert.equal(authDocument.elements["signup-form"].hidden, true);
  assert.equal(authDocument.elements["auth-description"].textContent, "대화를 시작하려면 로그인해 주세요.");
});

test("Mock API로 회원가입 후 로그인 성공을 알리고 비밀번호를 지운다", async () => {
  const authDocument = createAuthDocument();
  globalThis.document = authDocument;
  let loginSuccessCount = 0;
  initializeAuth({ onLoginSuccess: () => { loginSuccessCount += 1; } });
  const { elements } = authDocument;

  await trigger(authDocument.viewButtons[0], "click");
  elements["signup-username"].value = "form_user";
  elements["signup-password"].value = "password123";
  assert.equal(await trigger(elements["signup-form"], "submit"), true);
  assert.equal(elements["auth-message"].textContent, "회원가입이 완료되었습니다. 로그인해 주세요.");
  assert.equal(elements["auth-message"].dataset.state, "success");
  assert.equal(elements["login-username"].value, "form_user");

  elements["login-password"].value = "password123";
  assert.equal(await trigger(elements["login-form"], "submit"), true);
  assert.equal(loginSuccessCount, 1);
  assert.equal(elements["login-password"].value, "");
});

test("요청 중 중복 제출을 막고 오류 뒤 제출 버튼을 복구한다", async () => {
  const authDocument = createAuthDocument();
  globalThis.document = authDocument;
  let loginCalls = 0;
  let resolveLogin;
  const loginPromise = new Promise((resolve) => { resolveLogin = resolve; });
  initializeAuth({
    authApi: {
      signup: async () => ({ id: 1, username: "user" }),
      login: async () => {
        loginCalls += 1;
        return loginPromise;
      },
    },
  });
  const { elements } = authDocument;
  elements["login-username"].value = "a!";
  elements["login-password"].value = "x";
  const firstSubmit = trigger(elements["login-form"], "submit");
  const secondSubmit = trigger(elements["login-form"], "submit");
  assert.equal(elements["login-submit"].disabled, true);
  assert.equal(loginCalls, 1);
  resolveLogin();
  await Promise.all([firstSubmit, secondSubmit]);
  assert.equal(elements["login-submit"].disabled, false);
});

test("HTTP 오류와 네트워크 오류는 서로 다른 안내로 표시한다", async () => {
  const authDocument = createAuthDocument();
  globalThis.document = authDocument;
  initializeAuth({
    authApi: {
      signup: async () => { throw new ApiError(409, "USERNAME_TAKEN", "이미 사용 중인 아이디입니다."); },
      login: async () => { throw new TypeError("Failed to fetch"); },
    },
  });
  const { elements } = authDocument;
  await trigger(authDocument.viewButtons[0], "click");
  elements["signup-username"].value = "another_user";
  elements["signup-password"].value = "password123";
  await trigger(elements["signup-form"], "submit");
  assert.equal(elements["auth-message"].textContent, "이미 사용 중인 아이디입니다.");
  assert.equal(elements["signup-submit"].disabled, false);
  await trigger(authDocument.viewButtons[1], "click");
  elements["login-username"].value = "another_user";
  elements["login-password"].value = "password123";
  await trigger(elements["login-form"], "submit");
  assert.equal(elements["auth-message"].textContent, "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.");
  assert.equal(getAuthErrorMessage(new ApiError(401, "INVALID_CREDENTIALS", "로그인 실패")), "로그인 실패");
});
