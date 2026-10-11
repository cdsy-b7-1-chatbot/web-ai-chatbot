import {
  getMockCurrentUser,
  getMockHealthStatus,
  loginMock,
  logoutMock,
  signupMock,
} from "./mock.js";
import {
  getRealCurrentUser,
  getRealHealthStatus,
  loginReal,
  logoutReal,
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
