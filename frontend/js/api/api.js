import { getMockHealthStatus } from "./mock.js";
import { getRealHealthStatus } from "./real.js";

const apiByFeature = {
  health: {
    mock: getMockHealthStatus,
    real: getRealHealthStatus,
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
