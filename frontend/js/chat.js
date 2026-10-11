import { sendChat } from "./api/api.js";
import { ApiError } from "./api/errors.js";

export function getChatErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.";
}

/**
 * 채팅 화면의 입력·표시 상태만 관리하고, 인증 전환 같은 전역 상태는 main.js에 맡긴다.
 */
export function initializeChat({ chatApi = { sendChat }, onProtectedApiError = () => false } = {}) {
  const form = document.querySelector("#chat-form");
  const questionInput = document.querySelector("#chat-question");
  const submitButton = document.querySelector("#chat-submit");
  const messages = document.querySelector("#chat-messages");
  const message = document.querySelector("#chat-message");

  if (!form || !questionInput || !submitButton || !messages || !message) {
    return;
  }

  let requestPending = false;

  function setMessage(text, state = "") {
    message.textContent = text;
    message.dataset.state = state;
  }

  function appendBubble(role, text) {
    const bubble = document.createElement("p");
    bubble.className = "chat-bubble";
    bubble.dataset.role = role;
    bubble.textContent = text;
    messages.append(bubble);
  }

  form.addEventListener("submit", async (event) => {
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
    questionInput.disabled = true;
    submitButton.disabled = true;
    appendBubble("user", question);
    questionInput.value = "";
    setMessage("AI가 답변을 작성하고 있습니다.");
    try {
      const response = await chatApi.sendChat(question, null);
      appendBubble("assistant", response.answer);
      setMessage(response.truncated ? "답변이 길이 제한으로 일부 잘렸습니다." : "");
    } catch (error) {
      if (!onProtectedApiError(error)) {
        setMessage(getChatErrorMessage(error), "error");
      }
    } finally {
      requestPending = false;
      questionInput.disabled = false;
      submitButton.disabled = false;
    }
  });

  return { getIsPending: () => requestPending };
}
