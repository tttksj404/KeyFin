# 봉투 구간 알림 평가 API (`POST /v1/coaching/envelope-reviews`)

백엔드가 봉투 구간 알림(잔여 50%·20%·5%·초과)을 보낼 때마다, 그 봉투의 상태를 코치 문장으로 받아 알림에 붙이는 API입니다.

## 호출

- 인증: backend 역할 토큰 + `X-Coaching-User: {사용자 ID}` (`/v1/twin`, `/v1/events`와 동일). 사용자 토큰은 403.
- `Idempotency-Key` 필수. 알림 ID 기반 키를 권장합니다. 같은 키·같은 본문 재전송은 저장된 결과를 그대로 돌려주고, 같은 키에 다른 본문은 409입니다.
- 전제: **twin push(`POST /v1/twin`)가 성공한 뒤에만 호출**합니다. 알림 직전 push에는 매번 새 `Idempotency-Key`를 쓰고(같은 키 재전송은 캐시 응답이라 장부가 갱신되지 않음), `budget_start_day`는 항상 보내 주세요(생략하면 이전 값이 유지됨). 금액은 그 push의 `envelopes`(백엔드 장부 잔액)와 `snapshot.budgets`(봉투 예산)에서, 기간은 `budget_start_day` 예산 주기에서 계산합니다. push가 실패했으면 이전 twin 기준이 되므로 호출하지 않습니다.

```json
POST /v1/coaching/envelope-reviews
{"envelope": "외식", "tier": "20", "on_date": "2026-09-23"}
```

| 필드 | 필수 | 뜻 |
| --- | --- | --- |
| `envelope` | 예 | 7봉투 이름 중 하나: `외식`, `교통비`, `의료·건강`, `취미·여가`, `쇼핑`, `편의점·마트·잡화`, `기타` (표시 라벨 `교통`·`마트·편의점`은 422) |
| `tier` | 예 | `"50"`·`"20"`·`"5"`·`"over"` — 방금 넘은 알림 구간 |
| `on_date` | 아니오 | 기준일. 생략하면 방금 push한 twin의 `as_of`(오늘). push 기준일과 같은 예산 주기 안이어야 함 |

## 응답 (200)

```json
{
  "id": "f5adb4f2088f45c5b40a284a477a831e",
  "envelope": "외식", "tier": "20",
  "text": "외식 예산이 20% 남았다냥. 예산 300,000원 중 60,000원이 남았다냥. 10월 14일까지 22일 동안 하루 2,727원 안에서 쓰면 이번 주기를 지킬 수 있다냥. 남은 기간에는 꼭 필요한 외식 지출 위주로 조절해 보라냥.",
  "budget_krw": 300000, "remaining_krw": 60000, "used_krw": 240000, "remaining_percent": 20.0,
  "as_of": "2026-09-23", "period_start": "2026-09-15", "period_end": "2026-10-14",
  "days_left": 22, "daily_allowance_krw": 2727,
  "wording_source": "template", "created_at": 1790150439.35
}
```

- `text`는 앱·푸시에 그대로 보여 줄 **평문**입니다. 굵게 표시(`**`)가 없고, 코치 말투(~다냥)가 적용됩니다(`COACHING_PERSONA=plain`이면 중립 문장).
- `remaining_krw`는 백엔드 장부 잔액 그대로, `budget_krw`는 snapshot 예산 그대로입니다. 위험 답변의 `budget_risk`(시뮬레이션·달력 월)와 달리 알림 숫자와 문장이 어긋나지 않습니다.
- `days_left`는 기준일을 포함한 예산 주기 남은 일수, `daily_allowance_krw`는 `remaining_krw // days_left`입니다(잔액이 0 이하이거나 몫이 0원이면 `null`이고 하루 문장을 생략).
- 문장은 `tier`가 아니라 **장부 숫자**를 따릅니다. 잔액 음수 → "N원 넘었다냥", 0 → "모두 썼다냥", 양수 → 남은 %·금액(1% 미만은 "1% 미만"), 예산보다 많으면 "예산보다 N원 많은 …". `tier`는 권고 문장만 고릅니다(`over`인데 잔액이 남아 있으면 5%와 같은 절제 권고).
- `used_krw`는 0 미만이 되지 않습니다. `snapshot.budgets`의 `300000.0`처럼 정수인 실수도 받습니다.
- LLM을 호출하지 않는 결정적 템플릿입니다(`wording_source="template"`). 로컬 in-process 실측 p50 36ms·p95 41ms(100회), 운영에서는 백엔드↔코칭 네트워크 왕복이 더해집니다.

## 실패

| 상태 | 코드 | 뜻 |
| --- | --- | --- |
| 403 | `backend_role_required` | backend 토큰이 아님 |
| 404 | `resource_not_found` | 이 사용자의 twin 또는 장부가 아직 없음(push 전) |
| 409 | — | 같은 `Idempotency-Key`에 다른 본문 |
| 422 | `envelope_unknown` | 7봉투가 아닌 이름 |
| 422 | `envelope_not_in_ledger` | push된 `envelopes`에 그 봉투가 없음 |
| 422 | `envelope_budget_missing` | `snapshot.budgets`에 그 봉투 예산이 없거나 0 이하 |
| 422 | `envelope_on_date_out_of_cycle` | `on_date`가 push 기준일과 다른 예산 주기 |
| 422 | (검증 오류) | `tier`·`on_date` 형식 오류 |
