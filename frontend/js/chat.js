import { getChatHistory, sendChat } from "./api/api.js";
import { ApiError } from "./api/errors.js";

const HISTORY_PAGE_SIZE = 20;
const QUESTION_MAX_HEIGHT = 176;

export function getChatErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.";
}

/**
 * 채팅 화면의 입력·표시 상태만 관리하고, 인증 전환 같은 전역 상태는 main.js에 맡긴다.
 */
export function initializeChat({
  chatApi = { getChatHistory, sendChat },
  getConversationId = () => null,
  onChatSuccess = () => {},
  onNewConversation = () => {},
  onProtectedApiError = () => false,
} = {}) {
  const form = document.querySelector("#chat-form");
  const questionInput = document.querySelector("#chat-question");
  const submitButton = document.querySelector("#chat-submit");
  const newChatButton = document.querySelector("#new-chat-button");
  const loadMoreButton = document.querySelector("#load-more-history");
  const messages = document.querySelector("#chat-messages");
  const emptyState = document.querySelector("#chat-empty-state");
  const message = document.querySelector("#chat-message");

  if (!form || !questionInput || !submitButton || !newChatButton || !loadMoreButton || !messages || !message) {
    return;
  }

  let requestPending = false;
  let messageRequestGeneration = 0;
  let historyRequestGeneration = 0;
  let historyItems = [];
  let historyOffset = 0;
  let historyPending = false;
  let loadedConversationId = null;
  let hasMoreHistory = false;

  function setMessage(text, state = "") {
    message.textContent = text;
    message.dataset.state = state;
  }

  function setMessagesBusy(isBusy) {
    messages.setAttribute("aria-busy", String(isBusy));
  }

  function updateMessagesBusy() {
    setMessagesBusy(requestPending || historyPending);
  }

  function setHasMessages(hasMessages) {
    messages.dataset.hasMessages = String(hasMessages);
    if (emptyState) {
      emptyState.hidden = hasMessages;
    }
  }

  function resizeQuestionInput() {
    if (!questionInput.style) {
      return;
    }

    questionInput.style.height = "auto";
    const contentHeight = questionInput.scrollHeight ?? 0;
    if (contentHeight > 0) {
      questionInput.style.height = `${Math.min(contentHeight, QUESTION_MAX_HEIGHT)}px`;
    }
    questionInput.style.overflowY = contentHeight > QUESTION_MAX_HEIGHT ? "auto" : "hidden";
  }

  function appendBubble(role, text) {
    const bubble = document.createElement("p");
    bubble.className = "chat-bubble";
    bubble.dataset.role = role;
    bubble.textContent = text;
    messages.append(bubble);
    setHasMessages(true);
  }

  function reset() {
    messageRequestGeneration += 1;
    historyRequestGeneration += 1;
    requestPending = false;
    historyItems = [];
    historyOffset = 0;
    historyPending = false;
    loadedConversationId = null;
    hasMoreHistory = false;
    messages.replaceChildren();
    setHasMessages(false);
    updateMessagesBusy();
    loadMoreButton.hidden = true;
    questionInput.value = "";
    resizeQuestionInput();
    questionInput.disabled = false;
    submitButton.disabled = false;
    setMessage("");
  }

  newChatButton.addEventListener("click", () => {
    reset();
    onNewConversation();
    questionInput.focus();
  });

  function appendHistoryItem(item) {
    appendBubble("user", item.question);
    if (item.status === "success" && item.answer) {
      appendBubble("assistant", item.answer);
      return;
    }

    const reason = item.error_code ? ` (${item.error_code})` : "";
    appendBubble("assistant", `답변을 생성하지 못했습니다.${reason}`);
  }

  function renderHistory() {
    messages.replaceChildren();
    setHasMessages(false);
    for (const item of [...historyItems].sort(
      (left, right) => left.created_at.localeCompare(right.created_at) || left.id - right.id,
    )) {
      appendHistoryItem(item);
    }
  }

  function mergeHistoryItems(items) {
    const itemsById = new Map(historyItems.map((item) => [item.id, item]));
    for (const item of items) {
      itemsById.set(item.id, item);
    }
    historyItems = [...itemsById.values()];
  }

  async function loadHistoryPage(resetHistory) {
    if (historyPending || loadedConversationId === null) {
      return;
    }

    const conversationId = loadedConversationId;
    const generation = ++historyRequestGeneration;
    historyPending = true;
    updateMessagesBusy();
    if (resetHistory) {
      historyItems = [];
      historyOffset = 0;
      hasMoreHistory = false;
      messages.replaceChildren();
      setHasMessages(false);
    }
    loadMoreButton.hidden = true;
    setMessage(resetHistory ? "대화 기록을 불러오는 중입니다." : "이전 기록을 불러오는 중입니다.");
    try {
      const response = await chatApi.getChatHistory({
        conversationId,
        limit: HISTORY_PAGE_SIZE,
        offset: historyOffset,
      });
      if (generation !== historyRequestGeneration || conversationId !== getConversationId()) {
        return;
      }
      mergeHistoryItems(response.items);
      historyOffset += response.items.length;
      hasMoreHistory = response.items.length === HISTORY_PAGE_SIZE;
      renderHistory();
      loadMoreButton.hidden = !hasMoreHistory;
      setMessage(response.items.length === 0 ? "대화 기록이 없습니다." : "");
    } catch (error) {
      if (generation !== historyRequestGeneration) {
        return;
      }
      if (!onProtectedApiError(error)) {
        setMessage(getChatErrorMessage(error), "error");
      }
    } finally {
      if (generation === historyRequestGeneration) {
        historyPending = false;
        updateMessagesBusy();
        loadMoreButton.hidden = !hasMoreHistory;
      }
    }
  }

  async function loadConversation(conversationId) {
    // 같은 모듈 안의 이전 방 조회가 늦게 끝나도 새 선택을 덮어쓰지 못하게 한다.
    messageRequestGeneration += 1;
    historyRequestGeneration += 1;
    historyPending = false;
    requestPending = false;
    updateMessagesBusy();
    questionInput.disabled = false;
    submitButton.disabled = false;
    loadedConversationId = conversationId;
    await loadHistoryPage(true);
  }

  loadMoreButton.addEventListener("click", () => { void loadHistoryPage(false); });

  async function submitQuestion(event) {
    event.preventDefault();
    if (requestPending) {
      return;
    }

    const question = questionInput.value.trim();
    if (!question) {
      setMessage("질문을 입력해 주세요.", "error");
      questionInput.focus();
      return;
    }

    requestPending = true;
    const generation = messageRequestGeneration;
    updateMessagesBusy();
    questionInput.disabled = true;
    submitButton.disabled = true;
    appendBubble("user", question);
    questionInput.value = "";
    resizeQuestionInput();
    setMessage("AI가 답변을 작성하고 있습니다.");
    try {
      const response = await chatApi.sendChat(question, getConversationId());
      if (generation !== messageRequestGeneration) {
        return;
      }

      // 아직 도착하지 않은 기록 응답이 방금 표시한 질문·답변을 덮어쓰지 않게 한다.
      historyRequestGeneration += 1;
      historyPending = false;
      appendBubble("assistant", response.answer);
      setMessage(response.truncated ? "답변이 길이 제한으로 일부 잘렸습니다." : "");
      onChatSuccess(response);
    } catch (error) {
      if (generation !== messageRequestGeneration) {
        return;
      }

      if (!onProtectedApiError(error)) {
        setMessage(getChatErrorMessage(error), "error");
      }
    } finally {
      if (generation === messageRequestGeneration) {
        requestPending = false;
        updateMessagesBusy();
        questionInput.disabled = false;
        submitButton.disabled = false;
      }
    }
  }

  form.addEventListener("submit", submitQuestion);
  questionInput.addEventListener("input", resizeQuestionInput);
  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      void submitQuestion(event);
    }
  });
  resizeQuestionInput();

  return {
    getIsPending: () => requestPending,
    loadConversation,
    loadMoreHistory: () => loadHistoryPage(false),
    reset,
  };
}
