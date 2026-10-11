import { ApiError } from "./api/errors.js";

/** 화면에 원문 예외를 노출하지 않고, API 오류와 연결 오류를 일관되게 안내한다. */
export function getRequestErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.";
}
