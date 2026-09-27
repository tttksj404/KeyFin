/**
 * 모든 응답은 공통 봉투 `{ success, code, message, data }` 로 오고 실제 값은 `data` 안에 있다
 * (2026-09-10 백엔드 확인 — 전 도메인 공통 포맷).
 *
 * 봉투를 아는 곳은 api 층뿐이다. 도메인 함수와 model.ts 는 벗겨진 값만 본다.
 * api/mocks 의 목 데이터도 인터셉터를 거치지 않으므로 봉투 없이 둔다.
 */
type Envelope = { success: unknown; data: unknown };

function isEnvelope(body: unknown): body is Envelope {
  return typeof body === "object" && body !== null && "success" in body && "data" in body;
}

/** 봉투면 data 를 꺼내고, 봉투가 아니면 그대로 돌려준다. */
export function unwrapEnvelope(body: unknown): unknown {
  return isEnvelope(body) ? body.data : body;
}
