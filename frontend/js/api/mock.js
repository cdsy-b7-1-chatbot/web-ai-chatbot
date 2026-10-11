import { ApiError } from "./errors.js";

let nextUserId = 1;
const usersByUsername = new Map();
let currentUserId = null;
let nextConversationId = 1;
let nextChatId = 1;
const conversationsById = new Map();
const chatsById = new Map();

function normalizeUsername(username) {
  return typeof username === "string" ? username.toLowerCase() : "";
}

function validateSignup(username, password) {
  return (
    typeof username === "string" &&
    /^[A-Za-z0-9_]{3,20}$/.test(username) &&
    typeof password === "string" &&
    password.length >= 8 &&
    password.length <= 64
  );
}

function toUserResponse(user) {
  return { id: user.id, username: user.username };
}

function getCurrentMockUser() {
  const user = [...usersByUsername.values()].find(({ id }) => id === currentUserId);
  if (!user) {
    throw new ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다.");
  }

  return user;
}

function validateChatRequest(question, conversationId) {
  if (
    typeof question !== "string" ||
    question.trim().length === 0 ||
    question.trim().length > 5000 ||
    (conversationId !== null && (!Number.isInteger(conversationId) || conversationId <= 0))
  ) {
    throw new ApiError(422, "VALIDATION_ERROR", "입력값이 올바르지 않습니다.");
  }
}

function validateHistoryRequest(conversationId, limit, offset) {
  if (
    (conversationId !== null && (!Number.isInteger(conversationId) || conversationId <= 0)) ||
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > 100 ||
    !Number.isInteger(offset) ||
    offset < 0
  ) {
    throw new ApiError(422, "VALIDATION_ERROR", "입력값이 올바르지 않습니다.");
  }
}

function toConversationResponse(conversation) {
  return {
    id: conversation.id,
    title: conversation.title,
    created_at: conversation.createdAt,
    updated_at: conversation.updatedAt,
  };
}

/**
 * 실제 상태 확인 API와 같은 응답 형태를 제공해 화면 모듈을 독립적으로 검증한다.
 */
export async function getMockHealthStatus() {
  return { status: "ok" };
}

export async function signupMock(username, password) {
  if (!validateSignup(username, password)) {
    throw new ApiError(422, "VALIDATION_ERROR", "입력값이 올바르지 않습니다.");
  }

  const normalizedUsername = normalizeUsername(username);
  if (usersByUsername.has(normalizedUsername)) {
    throw new ApiError(409, "USERNAME_TAKEN", "이미 사용 중인 아이디입니다.");
  }

  const user = { id: nextUserId, username: normalizedUsername, password };
  nextUserId += 1;
  usersByUsername.set(normalizedUsername, user);
  return toUserResponse(user);
}

export async function loginMock(username, password) {
  const user = usersByUsername.get(normalizeUsername(username));
  if (!user || user.password !== password) {
    throw new ApiError(401, "INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다.");
  }

  currentUserId = user.id;
}

export async function logoutMock() {
  currentUserId = null;
}

export async function getMockCurrentUser() {
  return toUserResponse(getCurrentMockUser());
}

/**
 * 실제 AI 호출 없이도 새 방 생성과 같은 방의 후속 질문 흐름을 검증할 수 있게 한다.
 */
export async function sendChatMock(question, conversationId = null) {
  const user = getCurrentMockUser();
  validateChatRequest(question, conversationId);

  let conversation;
  if (conversationId === null) {
    const now = new Date().toISOString();
    conversation = {
      id: nextConversationId,
      userId: user.id,
      title: question.trim().slice(0, 100),
      createdAt: now,
      updatedAt: now,
    };
    nextConversationId += 1;
    conversationsById.set(conversation.id, conversation);
  } else {
    conversation = conversationsById.get(conversationId);
    if (!conversation || conversation.userId !== user.id) {
      throw new ApiError(404, "NOT_FOUND", "대화방을 찾을 수 없습니다.");
    }
  }

  const createdAt = new Date().toISOString();
  conversation.updatedAt = createdAt;
  const response = {
    chat_id: nextChatId,
    conversation_id: conversation.id,
    answer: `Mock 답변: ${question.trim()}`,
    created_at: createdAt,
    truncated: false,
  };
  chatsById.set(response.chat_id, {
    id: response.chat_id,
    user_id: user.id,
    conversation_id: conversation.id,
    question: question.trim(),
    answer: response.answer,
    status: "success",
    error_code: null,
    created_at: response.created_at,
  });
  nextChatId += 1;
  return response;
}

export async function getMockConversations() {
  const user = getCurrentMockUser();
  const items = [...conversationsById.values()]
    .filter((conversation) => conversation.userId === user.id)
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt) || right.id - left.id)
    .map(toConversationResponse);
  return { items };
}

export async function getMockChatHistory({ conversationId = null, limit = 50, offset = 0 } = {}) {
  const user = getCurrentMockUser();
  validateHistoryRequest(conversationId, limit, offset);
  if (conversationId !== null) {
    const conversation = conversationsById.get(conversationId);
    if (!conversation || conversation.userId !== user.id) {
      throw new ApiError(404, "NOT_FOUND", "대화방을 찾을 수 없습니다.");
    }
  }

  const items = [...chatsById.values()]
    .filter((chat) => chat.user_id === user.id && (conversationId === null || chat.conversation_id === conversationId))
    .sort((left, right) => right.created_at.localeCompare(left.created_at) || right.id - left.id)
    .slice(offset, offset + limit);
  return { items };
}
