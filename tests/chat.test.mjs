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
    this.attributes = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  append(child) {
    this.children.push(child);
  }

  replaceChildren(...children) {
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  focus() {
    this.focused = true;
  }
}

function createChatDocument() {
  const ids = ["chat-form", "chat-question", "chat-submit", "new-chat-button", "load-more-history", "chat-messages", "chat-message"];
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

async function click(element) {
  await Promise.all((element.listeners.get("click") ?? []).map((listener) => listener()));
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
        return { answer: "AI 답변", conversation_id: 4, truncated: false };
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

test("첫 응답의 대화방 ID를 후속 질문에 사용하고 새 대화에서는 초기화한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  const requests = [];
  let conversationId = null;
  const controller = initializeChat({
    chatApi: {
      sendChat: async (...args) => {
        requests.push(args);
        return { answer: "답변", conversation_id: 11, truncated: false };
      },
    },
    getConversationId: () => conversationId,
    onChatSuccess: (response) => { conversationId = response.conversation_id; },
    onNewConversation: () => { conversationId = null; },
  });

  chatDocument.elements["chat-question"].value = "첫 질문";
  await trigger(chatDocument.elements["chat-form"]);
  chatDocument.elements["chat-question"].value = "후속 질문";
  await trigger(chatDocument.elements["chat-form"]);
  assert.deepEqual(requests, [["첫 질문", null], ["후속 질문", 11]]);
  assert.equal(conversationId, 11);

  await click(chatDocument.elements["new-chat-button"]);
  assert.equal(conversationId, null);
  assert.equal(chatDocument.elements["chat-messages"].children.length, 0);
  assert.equal(chatDocument.elements["chat-question"].focused, true);
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
  assert.equal(chatDocument.elements["chat-messages"].attributes.get("aria-busy"), "true");
  assert.equal(chatDocument.elements["chat-message"].textContent, "AI가 답변을 작성하고 있습니다.");
  resolveRequest({ answer: "완료", conversation_id: 1, truncated: true });
  await Promise.all([firstSubmit, secondSubmit]);
  assert.equal(chatDocument.elements["chat-message"].textContent, "답변이 길이 제한으로 일부 잘렸습니다.");
  assert.equal(chatDocument.elements["chat-messages"].attributes.get("aria-busy"), "false");
});

test("새 대화·인증 해제 뒤에는 진행 중이던 응답을 표시하지 않는다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  let resolveRequest;
  const request = new Promise((resolve) => { resolveRequest = resolve; });
  const protectedErrors = [];
  const controller = initializeChat({
    chatApi: { sendChat: async () => request },
    onProtectedApiError: (error) => {
      protectedErrors.push(error);
      controller.reset();
      return true;
    },
  });

  chatDocument.elements["chat-question"].value = "지연된 질문";
  const pendingSubmit = trigger(chatDocument.elements["chat-form"]);
  await click(chatDocument.elements["new-chat-button"]);
  resolveRequest({ answer: "늦은 답변", conversation_id: 8, truncated: false });
  await pendingSubmit;
  assert.equal(chatDocument.elements["chat-messages"].children.length, 0);
  assert.equal(controller.getIsPending(), false);

  const unauthorizedDocument = createChatDocument();
  globalThis.document = unauthorizedDocument;
  let unauthorizedController;
  unauthorizedController = initializeChat({
    chatApi: { sendChat: async () => { throw new ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다."); } },
    onProtectedApiError: (error) => {
      protectedErrors.push(error);
      unauthorizedController.reset();
      return true;
    },
  });
  unauthorizedDocument.elements["chat-question"].value = "만료된 요청";
  await trigger(unauthorizedDocument.elements["chat-form"]);
  assert.equal(protectedErrors.length, 1);
  assert.equal(unauthorizedDocument.elements["chat-message"].textContent, "");
  assert.equal(unauthorizedController.getIsPending(), false);
});

test("선택한 방의 최신순 기록을 시간순으로 표시하고 실패 기록을 안내한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  let selectedConversationId = 9;
  const controller = initializeChat({
    chatApi: {
      getChatHistory: async ({ conversationId, limit, offset }) => {
        assert.equal(conversationId, 9);
        assert.equal(limit, 20);
        assert.equal(offset, 0);
        return {
          items: [
            { id: 2, question: "실패 질문", answer: null, status: "failed", error_code: "AI_TIMEOUT", created_at: "2026-10-11T00:01:00Z" },
            { id: 1, question: "처음 질문", answer: "처음 답변", status: "success", error_code: null, created_at: "2026-10-11T00:00:00Z" },
          ],
        };
      },
      sendChat: async () => ({ answer: "unused" }),
    },
    getConversationId: () => selectedConversationId,
  });
  await controller.loadConversation(9);
  assert.deepEqual(
    chatDocument.elements["chat-messages"].children.map((bubble) => [bubble.dataset.role, bubble.textContent]),
    [
      ["user", "처음 질문"],
      ["assistant", "처음 답변"],
      ["user", "실패 질문"],
      ["assistant", "답변을 생성하지 못했습니다. (AI_TIMEOUT)"],
    ],
  );
  selectedConversationId = 10;
  await controller.loadConversation(9);
  assert.equal(chatDocument.elements["chat-messages"].children.length, 0);
});

test("다른 대화방을 선택하면 이전 기록 응답을 무시한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  let selectedConversationId = 1;
  let resolveFirst;
  const firstRequest = new Promise((resolve) => { resolveFirst = resolve; });
  const controller = initializeChat({
    chatApi: {
      getChatHistory: async ({ conversationId }) => (
        conversationId === 1 ? firstRequest : { items: [{ id: 2, question: "둘째", answer: "방", status: "success", created_at: "2026-10-11T00:01:00Z" }] }
      ),
      sendChat: async () => ({ answer: "unused" }),
    },
    getConversationId: () => selectedConversationId,
  });
  const loadingFirst = controller.loadConversation(1);
  selectedConversationId = 2;
  await controller.loadConversation(2);
  resolveFirst({ items: [{ id: 1, question: "첫째", answer: "방", status: "success", created_at: "2026-10-11T00:00:00Z" }] });
  await loadingFirst;
  assert.deepEqual(
    chatDocument.elements["chat-messages"].children.map((bubble) => bubble.textContent),
    ["둘째", "방"],
  );
});

test("추가 기록은 offset으로 불러오고 중복 없이 시간순으로 표시한다", async () => {
  const chatDocument = createChatDocument();
  globalThis.document = chatDocument;
  const pageItems = Array.from({ length: 20 }, (_, index) => ({
    id: index + 1,
    question: `질문 ${index + 1}`,
    answer: String(index + 1),
    status: "success",
    created_at: `2026-10-11T00:${String(index).padStart(2, "0")}:00Z`,
  }));
  const requests = [];
  const controller = initializeChat({
    chatApi: {
      getChatHistory: async (options) => {
        requests.push(options);
        return options.offset === 0 ? { items: pageItems } : { items: [pageItems[0]] };
      },
      sendChat: async () => ({ answer: "unused" }),
    },
    getConversationId: () => 5,
  });
  await controller.loadConversation(5);
  assert.equal(chatDocument.elements["load-more-history"].hidden, false);
  await controller.loadMoreHistory();
  assert.deepEqual(requests.map(({ offset }) => offset), [0, 20]);
  assert.equal(chatDocument.elements["chat-messages"].children.length, 40);
  assert.equal(chatDocument.elements["chat-messages"].children[0].textContent, "질문 1");
});
