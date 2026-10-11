import assert from "node:assert/strict";
import test from "node:test";

class FakeElement {
  constructor() {
    this.hidden = false;
    this.textContent = "";
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
}

function createMainDocument() {
  const ids = [
    "auth-screen",
    "auth-checking",
    "auth-error",
    "auth-state-message",
    "chat-screen",
    "current-username",
    "retry-auth",
    "api-status",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  return {
    body: { dataset: {} },
    querySelector(selector) {
      return elements[selector.slice(1)] ?? null;
    },
    elements,
  };
}

async function trigger(element, type) {
  await Promise.all((element.listeners.get(type) ?? []).map((listener) => listener()));
}

delete globalThis.document;
const { ApiError } = await import("../frontend/js/api/errors.js");
const { AUTH_STATES, initializeApplication } = await import("../frontend/js/main.js");

function createDependencies(getCurrentUser) {
  let loginSuccessCallback;
  let logoutCallback;
  let chatStarts = 0;
  let chatResets = 0;
  let chatOptions;
  let historyOptions;
  const chatLoads = [];
  const historySelections = [];
  let historyRefreshes = 0;
  let historyStarts = 0;
  return {
    dependencies: {
      authApi: { getCurrentUser, logout: async () => {} },
      healthApi: {
        getHealthStatus: async () => ({ status: "ok" }),
        getHealthStatusSource: () => "Mock",
      },
      initializeAuthFn: ({ onLoginSuccess, onLogout }) => {
        loginSuccessCallback = onLoginSuccess;
        logoutCallback = onLogout;
      },
      initializeChatFn: (options) => {
        chatStarts += 1;
        chatOptions = options;
        return {
          loadConversation: (conversationId) => { chatLoads.push(conversationId); },
          reset: () => { chatResets += 1; },
        };
      },
      initializeHistoryFn: (options) => {
        historyStarts += 1;
        historyOptions = options;
        return {
          refresh: () => { historyRefreshes += 1; },
          reset: () => {},
          setSelectedConversation: (conversationId) => { historySelections.push(conversationId); },
        };
      },
    },
    getLoginSuccessCallback: () => loginSuccessCallback,
    getLogoutCallback: () => logoutCallback,
    getChatOptions: () => chatOptions,
    getHistoryOptions: () => historyOptions,
    getCoordination: () => ({ chatLoads, historyRefreshes, historySelections }),
    getStarts: () => ({ chatStarts, chatResets, historyStarts }),
  };
}

test("초기 인증 성공 시 사용자 정보를 표시하고 채팅 영역만 연다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => ({ id: 1, username: "sangwoo" }));

  const application = await initializeApplication(setup.dependencies);
  assert.equal(application.getAuthState(), AUTH_STATES.AUTHENTICATED);
  assert.equal(mainDocument.body.dataset.authState, AUTH_STATES.AUTHENTICATED);
  assert.equal(mainDocument.elements["current-username"].textContent, "sangwoo");
  assert.equal(mainDocument.elements["chat-screen"].hidden, false);
  assert.equal(mainDocument.elements["auth-screen"].hidden, true);
  assert.equal(mainDocument.elements["auth-checking"].hidden, true);
  assert.deepEqual(setup.getStarts(), { chatStarts: 1, chatResets: 0, historyStarts: 1 });
});

test("로그아웃 성공은 사용자 정보와 인증 상태를 초기화한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => ({ id: 5, username: "logout_user" }));
  const application = await initializeApplication(setup.dependencies);

  mainDocument.body.dataset.currentConversationId = "12";
  await setup.getLogoutCallback()();
  assert.equal(application.getAuthState(), AUTH_STATES.UNAUTHENTICATED);
  assert.equal(mainDocument.elements["current-username"].textContent, "");
  assert.equal(mainDocument.body.dataset.currentConversationId, "");
  assert.equal(mainDocument.elements["auth-screen"].hidden, false);
  assert.equal(mainDocument.elements["chat-screen"].hidden, true);
  assert.equal(setup.getStarts().chatResets, 1);
});

test("보호 API의 UNAUTHORIZED만 공통 인증 해제로 처리한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => ({ id: 6, username: "protected_user" }));
  const application = await initializeApplication(setup.dependencies);

  assert.equal(application.handleProtectedApiError(new ApiError(401, "INVALID_CREDENTIALS", "실패")), false);
  assert.equal(application.getAuthState(), AUTH_STATES.AUTHENTICATED);
  assert.equal(application.handleProtectedApiError(new ApiError(401, "UNAUTHORIZED", "만료")), true);
  assert.equal(application.getAuthState(), AUTH_STATES.UNAUTHENTICATED);
  assert.equal(setup.getStarts().chatResets, 1);
});

test("로그아웃 API 실패는 현재 인증 상태를 유지해 재시도할 수 있다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => ({ id: 7, username: "retry_logout" }));
  setup.dependencies.authApi.logout = async () => {
    throw new TypeError("Failed to fetch");
  };
  const application = await initializeApplication(setup.dependencies);

  await assert.rejects(() => setup.getLogoutCallback()(), TypeError);
  assert.equal(application.getAuthState(), AUTH_STATES.AUTHENTICATED);
  assert.equal(mainDocument.elements["chat-screen"].hidden, false);
});

test("로그아웃은 진행 중인 이전 인증 확인 결과를 무효화한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  let resolveCurrentUser;
  const setup = createDependencies(
    () => new Promise((resolve) => { resolveCurrentUser = resolve; }),
  );
  const applicationPromise = initializeApplication(setup.dependencies);

  await setup.getLogoutCallback()();
  resolveCurrentUser({ id: 8, username: "stale_user" });
  const application = await applicationPromise;
  assert.equal(application.getAuthState(), AUTH_STATES.UNAUTHENTICATED);
  assert.equal(mainDocument.elements["current-username"].textContent, "");
});

test("초기 401은 로그인 화면만 표시하고 채팅을 초기화하지 않는다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => {
    throw new ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다.");
  });

  const application = await initializeApplication(setup.dependencies);
  assert.equal(application.getAuthState(), AUTH_STATES.UNAUTHENTICATED);
  assert.equal(mainDocument.elements["auth-screen"].hidden, false);
  assert.equal(mainDocument.elements["chat-screen"].hidden, true);
  assert.equal(mainDocument.elements["auth-error"].hidden, true);
  assert.deepEqual(setup.getStarts(), { chatStarts: 0, chatResets: 0, historyStarts: 0 });
});

test("확인 불가 오류는 재시도로 인증 상태를 복구한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  let attempts = 0;
  const setup = createDependencies(async () => {
    attempts += 1;
    if (attempts === 1) {
      throw new TypeError("Failed to fetch");
    }
    return { id: 2, username: "retry_user" };
  });

  const application = await initializeApplication(setup.dependencies);
  assert.equal(application.getAuthState(), AUTH_STATES.ERROR);
  assert.equal(mainDocument.elements["auth-error"].hidden, false);
  assert.equal(mainDocument.elements["auth-screen"].hidden, true);
  assert.equal(mainDocument.elements["auth-state-message"].textContent, "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.");

  await trigger(mainDocument.elements["retry-auth"], "click");
  assert.equal(application.getAuthState(), AUTH_STATES.AUTHENTICATED);
  assert.equal(mainDocument.elements["current-username"].textContent, "retry_user");
  assert.equal(mainDocument.elements["chat-screen"].hidden, false);
});

test("로그인 성공 콜백은 서버 사용자 확인 뒤 한 번만 채팅을 초기화한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  let requests = 0;
  const setup = createDependencies(async () => {
    requests += 1;
    if (requests === 1) {
      throw new ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다.");
    }
    return { id: 3, username: "logged_in" };
  });

  const application = await initializeApplication(setup.dependencies);
  assert.equal(application.getAuthState(), AUTH_STATES.UNAUTHENTICATED);
  await setup.getLoginSuccessCallback()();
  assert.equal(application.getAuthState(), AUTH_STATES.AUTHENTICATED);
  assert.equal(mainDocument.elements["current-username"].textContent, "logged_in");
  assert.deepEqual(setup.getStarts(), { chatStarts: 1, chatResets: 0, historyStarts: 1 });
});

test("채팅 모듈에는 보호 API 오류를 인증 상태로 연결하는 콜백을 전달한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => ({ id: 10, username: "chat_error_user" }));
  const application = await initializeApplication(setup.dependencies);

  assert.equal(setup.getChatOptions().onProtectedApiError(new ApiError(401, "UNAUTHORIZED", "만료")), true);
  assert.equal(application.getAuthState(), AUTH_STATES.UNAUTHENTICATED);
  assert.equal(setup.getStarts().chatResets, 1);
});

test("대화방 선택·새 대화·질문 성공은 main.js가 공통 대화방 상태로 조정한다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  const setup = createDependencies(async () => ({ id: 11, username: "conversation_user" }));
  await initializeApplication(setup.dependencies);

  setup.getHistoryOptions().onConversationSelect(7);
  assert.equal(mainDocument.body.dataset.currentConversationId, "7");
  assert.deepEqual(setup.getCoordination().chatLoads, [7]);
  assert.deepEqual(setup.getCoordination().historySelections, [7]);

  setup.getChatOptions().onChatSuccess({ conversation_id: 8 });
  assert.equal(mainDocument.body.dataset.currentConversationId, "8");
  assert.deepEqual(setup.getCoordination().historySelections, [7, 8]);
  assert.equal(setup.getCoordination().historyRefreshes, 1);

  setup.getChatOptions().onNewConversation();
  assert.equal(mainDocument.body.dataset.currentConversationId, "");
  assert.deepEqual(setup.getCoordination().historySelections, [7, 8, null]);
});

test("인증 확인 중에는 인증·채팅 화면을 함께 숨긴다", async () => {
  const mainDocument = createMainDocument();
  globalThis.document = mainDocument;
  let resolveCurrentUser;
  const setup = createDependencies(
    () => new Promise((resolve) => { resolveCurrentUser = resolve; }),
  );

  const applicationPromise = initializeApplication(setup.dependencies);
  assert.equal(mainDocument.body.dataset.authState, AUTH_STATES.CHECKING);
  assert.equal(mainDocument.elements["auth-screen"].hidden, true);
  assert.equal(mainDocument.elements["chat-screen"].hidden, true);
  assert.equal(mainDocument.elements["auth-checking"].hidden, false);
  resolveCurrentUser({ id: 4, username: "checking_done" });
  await applicationPromise;
});
