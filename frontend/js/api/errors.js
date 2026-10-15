/**
 * HTTP 오류를 네트워크 오류와 구분해 화면 모듈이 상태·서버 코드를 기준으로 처리할 수 있게 한다.
 */
export class ApiError extends Error {
  constructor(status, error, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.error = error;
  }
}
