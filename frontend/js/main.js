import { initializeAuth } from "./auth.js";
import { getCurrentUser, logout } from "./api/api.js";
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
  authApi = { getCurrentUser, logout },
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
  const authMessage = document.querySelector("#auth-message");
  const logoutMessage = document.querySelector("#logout-message");
  const retryButton = document.querySelector("#retry-auth");

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
  let chatController = null;
  let historyController = null;
  let currentConversationId = null;
  let authenticationRequest = null;
  let requestGeneration = 0;

  function renderAuthState(nextState, user = null, message = "") {
    authState = nextState;
    document.body.dataset.authState = nextState;
    authScreen.hidden = nextState !== AUTH_STATES.UNAUTHENTICATED;
    checkingScreen.hidden = nextState !== AUTH_STATES.CHECKING;
    errorScreen.hidden = nextState !== AUTH_STATES.ERROR;
    chatScreen.hidden = nextState !== AUTH_STATES.AUTHENTICATED;
    if (logoutMessage) {
      logoutMessage.textContent = "";
    }
    if (authMessage) {
      authMessage.textContent = "";
      authMessage.dataset.state = "";
    }

    if (nextState === AUTH_STATES.AUTHENTICATED) {
      usernameElement.textContent = user.username;
    } else {
      usernameElement.textContent = "";
      document.body.dataset.currentConversationId = "";
      if (nextState === AUTH_STATES.UNAUTHENTICATED) {
        currentConversationId = null;
        chatController?.reset();
        historyController?.reset();
      }
    }

    if (nextState === AUTH_STATES.ERROR) {
      errorMessage.textContent = message;
    }
  }

  async function refreshAuthentication() {
    if (authenticationRequest) {
      return authenticationRequest;
    }

    const generation = requestGeneration;
    renderAuthState(AUTH_STATES.CHECKING);
    authenticationRequest = authApi
      .getCurrentUser()
      .then((user) => {
        if (generation !== requestGeneration) return;
        renderAuthState(AUTH_STATES.AUTHENTICATED, user);
        if (!chatInitialized) {
          chatController = initializeChatFn({
            getConversationId: () => currentConversationId,
            onChatSuccess: (response) => {
              currentConversationId = response.conversation_id;
              document.body.dataset.currentConversationId = String(currentConversationId);
              historyController?.setSelectedConversation(currentConversationId);
              void historyController?.refresh();
            },
            onNewConversation: () => {
              currentConversationId = null;
              document.body.dataset.currentConversationId = "";
              historyController?.setSelectedConversation(null);
            },
            onProtectedApiError: handleProtectedApiError,
          });
          historyController = initializeHistoryFn({
            onConversationSelect: (conversationId) => {
              currentConversationId = conversationId;
              document.body.dataset.currentConversationId = String(conversationId);
              historyController?.setSelectedConversation(conversationId);
              void chatController?.loadConversation(conversationId);
            },
            onProtectedApiError: handleProtectedApiError,
          });
          chatInitialized = true;
        }
      })
      .catch((error) => {
        if (generation !== requestGeneration) return;
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

  function handleProtectedApiError(error) {
    if (error instanceof ApiError && error.status === 401 && error.error === "UNAUTHORIZED") {
      requestGeneration += 1;
      renderAuthState(AUTH_STATES.UNAUTHENTICATED);
      return true;
    }
    return false;
  }

  async function logoutCurrentUser() {
    requestGeneration += 1;
    const generation = requestGeneration;
    await authApi.logout();
    if (generation === requestGeneration) {
      renderAuthState(AUTH_STATES.UNAUTHENTICATED);
    }
  }

  initializeAuthFn({ onLoginSuccess: refreshAuthentication, onLogout: logoutCurrentUser });
  retryButton.addEventListener("click", refreshAuthentication);

  await refreshAuthentication();
  return { getAuthState: () => authState, refreshAuthentication, handleProtectedApiError };
}

if (typeof document !== "undefined") {
  void initializeApplication();
}
