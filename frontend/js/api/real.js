const HEALTH_ENDPOINT = "/api/health";

/**
 * 실제 API 응답을 공통 인터페이스로 전달해 화면 모듈이 통신 방식을 알 필요 없게 한다.
 */
export async function getRealHealthStatus() {
  const response = await fetch(HEALTH_ENDPOINT, { credentials: "same-origin" });

  if (!response.ok) {
    throw new Error(`상태 확인 요청이 실패했습니다. (${response.status})`);
  }

  return response.json();
}
