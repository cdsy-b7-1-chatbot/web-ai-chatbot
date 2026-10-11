import assert from "node:assert/strict";
import test from "node:test";

class FakeElement {
  constructor() {
    this.dataset = {};
    this.disabled = false;
    this.textContent = "";
    this.value = "";
    this.children = [];
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  append(child) {
    this.children.push(child);
  }

  focus() {
    this.focused = true;
  }
}

function createChatDocument() {
  const ids = ["chat-form", "chat-question", "chat-submit", "chat-messages", "chat-message"];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  return {
    querySelector(selector) {
      return elements[selector.slice(1)] ?? null;
    },
    createElement() {
      return new FakeElement();
    },
    elements,
  };
}

async function trigger(element) {
  let prevented = false;
  await Promise.all(
    (element.listeners.get("submit") ?? []).map((listener) =>
      listener({ preventDefault: () => { prevented = true; } }),
    ),
  );
  return prevented;
}

delete globalThis.document;
const { ApiError } = await import("../frontend/js/api/errors.js");
const { getChatErrorMessage, initializeChat } = await import("../frontend/js/chat.js");

test("질문을 전송하면 사용자 질문과 AI 답변을 순서대로 표시한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  const requests = [];
  initializeChat({
    chatApi: {
      sendChat: async (...args) => {
        requests.push(args);
        return { answer: "AI 답변", truncated: false };
      },
    },
  });

  chatDocument.elements["chat-question"].value = "  질문입니다  ";
  assert.equal(await trigger(chatDocument.elements["chat-form"]), true);
  assert.deepEqual(requests, [["질문입니다", null]]);
  assert.equal(chatDocument.elements["chat-question"].value, "");
  assert.deepEqual(
    chatDocument.elements["chat-messages"].children.map((bubble) => [bubble.dataset.role, bubble.textContent]),
    [["user", "질문입니다"], ["assistant", "AI 답변"]],
  );
  assert.equal(chatDocument.elements["chat-submit"].disabled, false);
});

test("빈 질문·HTTP 오류·네트워크 오류를 안내하고 재전송을 허용한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  let calls = 0;
  initializeChat({
    chatApi: {
      sendChat: async () => {
        calls += 1;
        throw calls === 1
          ? new ApiError(502, "AI_ERROR", "AI 응답을 처리하지 못했습니다.")
          : new TypeError("Failed to fetch");
      },
    },
  });

  await trigger(chatDocument.elements["chat-form"]);
  assert.equal(calls, 0);
  assert.equal(chatDocument.elements["chat-message"].textContent, "질문을 입력해 주세요.");
  assert.equal(chatDocument.elements["chat-question"].focused, true);

  chatDocument.elements["chat-question"].value = "오류 질문";
  await trigger(chatDocument.elements["chat-form"]);
  assert.equal(chatDocument.elements["chat-message"].textContent, "AI 응답을 처리하지 못했습니다.");
  assert.equal(chatDocument.elements["chat-submit"].disabled, false);

  chatDocument.elements["chat-question"].value = "재시도 질문";
  await trigger(chatDocument.elements["chat-form"]);
  assert.equal(chatDocument.elements["chat-message"].textContent, "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.");
  assert.equal(getChatErrorMessage(new ApiError(422, "VALIDATION_ERROR", "검증 실패")), "검증 실패");
});

test("요청 중에는 중복 전송을 막고 로딩 상태를 표시한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  let calls = 0;
  let resolveRequest;
  const request = new Promise((resolve) => { resolveRequest = resolve; });
  initializeChat({
    chatApi: {
      sendChat: async () => {
        calls += 1;
        return request;
      },
    },
  });

  chatDocument.elements["chat-question"].value = "첫 질문";
  const firstSubmit = trigger(chatDocument.elements["chat-form"]);
  const secondSubmit = trigger(chatDocument.elements["chat-form"]);
  assert.equal(calls, 1);
  assert.equal(chatDocument.elements["chat-submit"].disabled, true);
  assert.equal(chatDocument.elements["chat-message"].textContent, "AI가 답변을 작성하고 있습니다.");
  resolveRequest({ answer: "완료", truncated: true });
  await Promise.all([firstSubmit, secondSubmit]);
  assert.equal(chatDocument.elements["chat-message"].textContent, "답변이 길이 제한으로 일부 잘렸습니다.");
});
