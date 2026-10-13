import { getConversations } from "./api/api.js";
import { getRequestErrorMessage } from "./request-error.js";

const getHistoryErrorMessage = getRequestErrorMessage;

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
  const layout = document.querySelector("#chat-layout");
  const toggleButton = document.querySelector("#conversation-toggle");

  if (!list || !message || !retryButton) {
    return;
  }

  let conversations = [];
  let selectedConversationId = null;
  let requestGeneration = 0;

  function setConversationPanelOpen(isOpen, isUserToggle = false) {
    if (!layout || !toggleButton) {
      return;
    }

    layout.dataset.conversationsOpen = String(isOpen);
    if (isUserToggle) {
      layout.dataset.sidebarToggled = "true";
    }
    toggleButton.setAttribute("aria-expanded", String(isOpen));
    const label = isOpen ? "대화방 닫기" : "대화방 열기";
    toggleButton.setAttribute("aria-label", label);
    toggleButton.setAttribute("title", label);
  }

  function setMessage(text, state = "") {
    message.textContent = text;
    message.dataset.state = state;
  }

  function setListBusy(isBusy) {
    list.setAttribute("aria-busy", String(isBusy));
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
        setConversationPanelOpen(false);
      });
      list.append(button);
    }
  }

  async function refresh() {
    const generation = ++requestGeneration;
    setListBusy(true);
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
    } finally {
      if (generation === requestGeneration) {
        setListBusy(false);
      }
    }
  }

  function reset() {
    requestGeneration += 1;
    conversations = [];
    selectedConversationId = null;
    render();
    setListBusy(false);
    setConversationPanelOpen(false);
    retryButton.hidden = true;
    setMessage("");
  }

  retryButton.addEventListener("click", refresh);
  toggleButton?.addEventListener("click", () => {
    setConversationPanelOpen(layout?.dataset.conversationsOpen !== "true", true);
  });
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    setConversationPanelOpen(window.matchMedia("(min-width: 48.0625rem)").matches);
  }
  void refresh();
  function setSelectedConversation(conversationId) {
    selectedConversationId = conversationId;
    render();
  }

  return { getSelectedConversationId: () => selectedConversationId, refresh, reset, setSelectedConversation };
}
