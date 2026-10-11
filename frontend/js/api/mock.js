import { ApiError } from "./errors.js";

let nextUserId = 1;
const usersByUsername = new Map();
let currentUserId = null;

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
  const user = [...usersByUsername.values()].find(({ id }) => id === currentUserId);
  if (!user) {
    throw new ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다.");
  }

  return toUserResponse(user);
}
