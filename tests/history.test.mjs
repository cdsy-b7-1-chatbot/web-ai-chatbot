import assert from "node:assert/strict";
import test from "node:test";

class FakeElement {
  constructor() {
    this.dataset = {};
    this.hidden = false;
    this.textContent = "";
    this.attributes = new Map();
    this.children = [];
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  append(child) { this.children.push(child); }

  replaceChildren(...children) { this.children = children; }

  setAttribute(name, value) { this.attributes.set(name, value); }
}

function createHistoryDocument() {
  const ids = ["conversation-list", "conversation-message", "retry-conversations", "chat-layout", "conversation-toggle"];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  return {
    querySelector(selector) { return elements[selector.slice(1)] ?? null; },
    createElement() { return new FakeElement(); },
    elements,
  };
}

async function click(element) {
  await Promise.all((element.listeners.get("click") ?? []).map((listener) => listener()));
}

delete globalThis.document;
const { ApiError } = await import("../frontend/js/api/errors.js");
const { initializeHistory } = await import("../frontend/js/history.js");
const mockApi = await import("../frontend/js/api/mock.js");

test("최근 대화방을 표시하고 선택 상태와 콜백을 갱신한다", async () => {
  const historyDocument = createHistoryDocument();
  globalThis.document = historyDocument;
  const selected = [];
  let controller;
  controller = initializeHistory({
    historyApi: { getConversations: async () => ({ items: [{ id: 2, title: "둘째" }, { id: 1, title: "첫째" }] }) },
    onConversationSelect: (conversationId) => {
      selected.push(conversationId);
      controller.setSelectedConversation(conversationId);
    },
  });
  await Promise.resolve();

  const { elements } = historyDocument;
  assert.deepEqual(elements["conversation-list"].children.map((button) => button.textContent), ["둘째", "첫째"]);
  await click(elements["conversation-list"].children[1]);
  assert.equal(controller.getSelectedConversationId(), 1);
  assert.deepEqual(selected, [1]);
  assert.equal(elements["conversation-list"].children[1].attributes.get("aria-current"), "true");
});

test("모바일 대화방 버튼은 패널을 열고 대화를 선택하면 닫는다", async () => {
  const historyDocument = createHistoryDocument();
  globalThis.document = historyDocument;
  const controller = initializeHistory({
    historyApi: { getConversations: async () => ({ items: [{ id: 2, title: "둘째" }] }) },
    onConversationSelect: (conversationId) => controller.setSelectedConversation(conversationId),
  });
  await Promise.resolve();

  const { elements } = historyDocument;
  await click(elements["conversation-toggle"]);
  assert.equal(elements["chat-layout"].dataset.conversationsOpen, "true");
  assert.equal(elements["conversation-toggle"].attributes.get("aria-expanded"), "true");
  await click(elements["conversation-list"].children[0]);
  assert.equal(elements["chat-layout"].dataset.conversationsOpen, "false");
  assert.equal(elements["conversation-toggle"].attributes.get("aria-expanded"), "false");
});

test("빈 목록·오류·재시도를 화면 상태로 전달한다", async () => {
  const historyDocument = createHistoryDocument();
  globalThis.document = historyDocument;
  let attempts = 0;
  initializeHistory({
    historyApi: {
      getConversations: async () => {
        attempts += 1;
        if (attempts === 1) return { items: [] };
        if (attempts === 2) throw new ApiError(500, "DB_ERROR", "대화방을 불러오지 못했습니다.");
        return { items: [{ id: 3, title: "복구된 대화" }] };
      },
    },
  });
  await Promise.resolve();
  const { elements } = historyDocument;
  assert.equal(elements["conversation-message"].textContent, "저장된 대화방이 없습니다.");

  await click(elements["retry-conversations"]);
  assert.equal(elements["conversation-message"].textContent, "대화방을 불러오지 못했습니다.");
  assert.equal(elements["retry-conversations"].hidden, false);
  await click(elements["retry-conversations"]);
  assert.equal(elements["conversation-list"].children[0].textContent, "복구된 대화");
});

test("실제 Mock API 새 대화는 목록 새로 고침으로 표시된다", async () => {
  const username = `h_${Date.now().toString().slice(-10)}`;
  await mockApi.signupMock(username, "password123");
  await mockApi.loginMock(username, "password123");
  const historyDocument = createHistoryDocument();
  globalThis.document = historyDocument;
  const controller = initializeHistory({ historyApi: { getConversations: mockApi.getMockConversations } });
  await Promise.resolve();
  await mockApi.sendChatMock("목록에 보일 질문");
  await controller.refresh();

  assert.equal(historyDocument.elements["conversation-list"].children.length, 1);
  assert.equal(historyDocument.elements["conversation-list"].children[0].textContent, "목록에 보일 질문");
});
