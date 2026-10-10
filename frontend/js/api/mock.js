/**
 * 실제 상태 확인 API와 같은 응답 형태를 제공해 화면 모듈을 독립적으로 검증한다.
 */
export async function getMockHealthStatus() {
  return { status: "ok" };
}
