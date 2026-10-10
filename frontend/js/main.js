import { initializeAuth } from "./auth.js";
import { initializeChat } from "./chat.js";
import { getHealthStatus, getHealthStatusSource } from "./api/api.js";
import { initializeHistory } from "./history.js";

async function initializeApplication() {
  initializeAuth();
  initializeChat();
  initializeHistory();

  const statusElement = document.querySelector("#api-status");
  if (!statusElement) {
    return;
  }

  try {
    const status = await getHealthStatus();
    statusElement.textContent = `${getHealthStatusSource()} API 연결: ${status.status}`;
  } catch (error) {
    statusElement.textContent = `API 상태를 확인하지 못했습니다: ${error.message}`;
  }
}

void initializeApplication();
