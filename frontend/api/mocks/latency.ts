export const MOCK_LATENCY_MS = 400;

/** 목 응답에 네트워크 지연을 흉내 낸다. 쿼리 취소(signal)도 지원해 실제 요청과 같은 경로를 탄다. */
export function withMockLatency<T>(value: T, signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => resolve(value), MOCK_LATENCY_MS);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("요청이 취소되었습니다", "AbortError"));
    });
  });
}
