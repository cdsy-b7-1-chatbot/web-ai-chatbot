import {
  getMockCurrentUser,
  getMockChatHistory,
  getMockConversations,
  getMockHealthStatus,
  loginMock,
  logoutMock,
  sendChatMock,
  signupMock,
} from "./mock.js";
import {
  getRealCurrentUser,
  getRealChatHistory,
  getRealConversations,
  getRealHealthStatus,
  loginReal,
  logoutReal,
  sendChatReal,
  signupReal,
} from "./real.js";

const apiByFeature = {
  health: {
    mock: getMockHealthStatus,
    real: getRealHealthStatus,
  },
  auth: {
    mock: {
      signup: signupMock,
      login: loginMock,
      logout: logoutMock,
      getCurrentUser: getMockCurrentUser,
    },
    real: {
      signup: signupReal,
      login: loginReal,
      logout: logoutReal,
      getCurrentUser: getRealCurrentUser,
    },
  },
  chat: {
    mock: {
      getChatHistory: getMockChatHistory,
      getConversations: getMockConversations,
      sendChat: sendChatMock,
    },
    real: {
      getChatHistory: getRealChatHistory,
      getConversations: getRealConversations,
      sendChat: sendChatReal,
    },
  },
};

function getFeatureMode(feature) {
  const mode = document.documentElement.dataset[`${feature}ApiMode`] ?? "real";

  if (!(mode in apiByFeature[feature])) {
    throw new Error(`${feature} API 모드는 mock 또는 real이어야 합니다.`);
  }

  return mode;
}

export async function getHealthStatus() {
  const mode = getFeatureMode("health");
  return apiByFeature.health[mode]();
}

export function getHealthStatusSource() {
  return getFeatureMode("health") === "mock" ? "Mock" : "실제";
}

function getAuthApi() {
  return apiByFeature.auth[getFeatureMode("auth")];
}

export async function signup(username, password) {
  return getAuthApi().signup(username, password);
}

export async function login(username, password) {
  return getAuthApi().login(username, password);
}

export async function logout() {
  return getAuthApi().logout();
}

export async function getCurrentUser() {
  return getAuthApi().getCurrentUser();
}

/**
 * 새 대화는 conversationId에 null을 전달하고, 기존 대화는 서버가 발급한 양의 정수 ID를 전달한다.
 */
export async function sendChat(question, conversationId = null) {
  const mode = getFeatureMode("chat");
  return apiByFeature.chat[mode].sendChat(question, conversationId);
}

export async function getConversations() {
  const mode = getFeatureMode("chat");
  return apiByFeature.chat[mode].getConversations();
}

export async function getChatHistory(options = {}) {
  const mode = getFeatureMode("chat");
  return apiByFeature.chat[mode].getChatHistory(options);
}
