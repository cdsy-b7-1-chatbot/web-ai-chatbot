import { initializeAuth } from "./auth.js";
import { getCurrentUser, getHealthStatus, getHealthStatusSource } from "./api/api.js";
import { ApiError } from "./api/errors.js";
import { initializeChat } from "./chat.js";
import { initializeHistory } from "./history.js";

export const AUTH_STATES = {
  CHECKING: "checking",
  AUTHENTICATED: "authenticated",
  UNAUTHENTICATED: "unauthenticated",
  ERROR: "error",
};

function getAuthCheckErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.";
}

/**
 * 서버의 현재 사용자 응답만으로 인증 상태를 정한다. 쿠키와 토큰 값은 화면 코드에서 다루지 않는다.
 */
export async function initializeApplication({
  authApi = { getCurrentUser },
  healthApi = { getHealthStatus, getHealthStatusSource },
  initializeAuthFn = initializeAuth,
  initializeChatFn = initializeChat,
  initializeHistoryFn = initializeHistory,
} = {}) {
  const authScreen = document.querySelector("#auth-screen");
  const checkingScreen = document.querySelector("#auth-checking");
  const errorScreen = document.querySelector("#auth-error");
  const errorMessage = document.querySelector("#auth-state-message");
  const chatScreen = document.querySelector("#chat-screen");
  const usernameElement = document.querySelector("#current-username");
  const retryButton = document.querySelector("#retry-auth");
  const healthStatusElement = document.querySelector("#api-status");

  if (
    !authScreen ||
    !checkingScreen ||
    !errorScreen ||
    !errorMessage ||
    !chatScreen ||
    !usernameElement ||
    !retryButton
  ) {
    return;
  }

  let authState = AUTH_STATES.CHECKING;
  let chatInitialized = false;
  let authenticationRequest = null;

  function renderAuthState(nextState, user = null, message = "") {
    authState = nextState;
    document.body.dataset.authState = nextState;
    authScreen.hidden = nextState !== AUTH_STATES.UNAUTHENTICATED;
    checkingScreen.hidden = nextState !== AUTH_STATES.CHECKING;
    errorScreen.hidden = nextState !== AUTH_STATES.ERROR;
    chatScreen.hidden = nextState !== AUTH_STATES.AUTHENTICATED;

    if (nextState === AUTH_STATES.AUTHENTICATED) {
      usernameElement.textContent = user.username;
    }

    if (nextState === AUTH_STATES.ERROR) {
      errorMessage.textContent = message;
    }
  }

  async function refreshAuthentication() {
    if (authenticationRequest) {
      return authenticationRequest;
    }

    renderAuthState(AUTH_STATES.CHECKING);
    authenticationRequest = authApi
      .getCurrentUser()
      .then((user) => {
        renderAuthState(AUTH_STATES.AUTHENTICATED, user);
        if (!chatInitialized) {
          initializeChatFn();
          initializeHistoryFn();
          chatInitialized = true;
        }
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401 && error.error === "UNAUTHORIZED") {
          renderAuthState(AUTH_STATES.UNAUTHENTICATED);
          return;
        }

        renderAuthState(AUTH_STATES.ERROR, null, getAuthCheckErrorMessage(error));
      })
      .finally(() => {
        authenticationRequest = null;
      });

    return authenticationRequest;
  }

  initializeAuthFn({ onLoginSuccess: refreshAuthentication });
  retryButton.addEventListener("click", refreshAuthentication);

  if (healthStatusElement) {
    void healthApi
      .getHealthStatus()
      .then((health) => {
        healthStatusElement.textContent = `${healthApi.getHealthStatusSource()} API 연결: ${health.status}`;
      })
      .catch((error) => {
        healthStatusElement.textContent = `API 상태를 확인하지 못했습니다: ${error.message}`;
      });
  }

  await refreshAuthentication();
  return { getAuthState: () => authState, refreshAuthentication };
}

if (typeof document !== "undefined") {
  void initializeApplication();
}
