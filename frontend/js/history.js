import { getConversations } from "./api/api.js";
import { ApiError } from "./api/errors.js";

function getHistoryErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.";
}

/**
 * 목록의 조회·선택 표시만 맡기고, 선택한 방의 기록 표시와 채팅 상태는 상위 조정 모듈에 알린다.
 */
export function initializeHistory({
  historyApi = { getConversations },
  onConversationSelect = () => {},
  onProtectedApiError = () => false,
} = {}) {
  const list = document.querySelector("#conversation-list");
  const message = document.querySelector("#conversation-message");
  const retryButton = document.querySelector("#retry-conversations");

  if (!list || !message || !retryButton) {
    return;
  }

  let conversations = [];
  let selectedConversationId = null;
  let requestGeneration = 0;

  function setMessage(text, state = "") {
    message.textContent = text;
    message.dataset.state = state;
  }

  function render() {
    list.replaceChildren();
    for (const conversation of conversations) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.conversationId = String(conversation.id);
      button.textContent = conversation.title;
      button.setAttribute("aria-current", String(conversation.id === selectedConversationId));
      button.addEventListener("click", () => {
        onConversationSelect(conversation.id);
      });
      list.append(button);
    }
  }

  async function refresh() {
    const generation = ++requestGeneration;
    setMessage("대화방을 불러오는 중입니다.");
    retryButton.hidden = true;
    try {
      const response = await historyApi.getConversations();
      if (generation !== requestGeneration) {
        return;
      }
      conversations = response.items;
      if (!conversations.some((conversation) => conversation.id === selectedConversationId)) {
        selectedConversationId = null;
      }
      render();
      setMessage(conversations.length === 0 ? "저장된 대화방이 없습니다." : "");
    } catch (error) {
      if (generation !== requestGeneration) {
        return;
      }
      if (onProtectedApiError(error)) {
        return;
      }
      conversations = [];
      selectedConversationId = null;
      render();
      setMessage(getHistoryErrorMessage(error), "error");
      retryButton.hidden = false;
    }
  }

  function reset() {
    requestGeneration += 1;
    conversations = [];
    selectedConversationId = null;
    render();
    retryButton.hidden = true;
    setMessage("");
  }

  retryButton.addEventListener("click", refresh);
  void refresh();
  function setSelectedConversation(conversationId) {
    selectedConversationId = conversationId;
    render();
  }

  return { getSelectedConversationId: () => selectedConversationId, refresh, reset, setSelectedConversation };
}
