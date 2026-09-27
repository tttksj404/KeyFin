# 외부 호출 계층을 위한 AI API 인계 계약

현재 AI MR은 `ai/coaching`의 독립 Python API만 제공합니다. 앱 화면, Spring 또는 다른 백엔드 프록시, 원천 DB 어댑터, 푸시 전송기는 외부 팀이 소유하며 이 MR에 포함되지 않습니다. 이 문서는 외부 호출 계층이 Python API와 맞춰야 할 인증 역할, 데이터 입력, 엔드포인트와 알림 전달 계약을 정의합니다.

## 소유 범위

| AI MR이 제공하는 것 | 외부 호출 계층이 제공해야 하는 것 |
| --- | --- |
| FastAPI 엔드포인트와 요청·응답 스키마 | 로그인 사용자와 AI API 소유자 ID의 신뢰 가능한 매핑 |
| 역할별 Bearer 인증과 소유자별 SQLite 저장 | 역할별 토큰의 안전한 발급·주입·교체 |
| FDT 거래·잔액 계산, 코칭·대화·차트·예측 검증 | 권위 있는 원장·예산·개인 현황을 API 스키마로 변환하는 어댑터 |
| 코칭 알림 outbox 조회와 ack | FCM 등 실제 푸시 전송, 실패 재시도와 사용자 화면 이동 |
| 선택한 GPU 추론 서버 호출과 응답 검증 | 서비스 배포망, TLS 또는 승인된 내부망, 모니터링과 운영 복구 |

과거 앱·Spring·원천 동기화 실험은 현재 AI MR의 실행 경로가 아닙니다. 외부 팀은 아래 계약을 기준으로 각자의 저장소에서 연동을 구현하고 검증해야 합니다.

## 인증과 소유자 경계

API는 `COACHING_CLIENTS`에 등록한 Bearer 토큰으로 호출자를 식별합니다. 각 항목은 `user_id`, 32자 이상의 고유한 `token`, `role`을 가집니다. 요청 본문이 아니라 토큰에 묶인 `user_id`가 모든 저장·조회 범위를 결정합니다.

| 역할 | 허용되는 호출 | 외부 호출자 |
| --- | --- | --- |
| `backend` | 원장·개인 현황·예측 검증 입력과 차트 생성. 현재 구현상 `user`, `notification` 경로도 호출 가능 | 신뢰된 백엔드 또는 데이터 어댑터 |
| `user` | 코칭·대화·개인 조회·저장 결과 조회·본인 데이터 삭제 | 인증된 앱을 대신하는 프록시 또는 사용자별 서버 세션 |
| `notification` | 대기 알림 조회와 전달 완료 ack | 푸시 전송 worker |

최소 권한을 위해 같은 사용자의 역할별 토큰을 분리합니다. 앱에 AI API 토큰이나 GPU 추론 토큰을 직접 넣지 않습니다. 외부 프록시는 인증한 사용자를 임의의 본문 `user_id`로 바꾸지 말고, 그 사용자에게 미리 매핑한 토큰만 선택해야 합니다. 실제 전송 구간 보안과 비밀값 저장은 외부 배포 계층의 책임입니다.

## 공통 요청 규칙

- `POST`로 상태를 바꾸는 요청은 `Idempotency-Key` 헤더가 필요합니다. 동일 작업을 재시도할 때만 같은 키와 같은 본문을 사용하고, 본문이 바뀌면 새 키를 사용합니다.
- `POST /v1/forecast-validation/metrics`는 조회 계산이므로 `Idempotency-Key`를 받지 않습니다. `GET`과 `DELETE /v1/me/data`도 이 헤더를 받지 않습니다.
- 최신 요청·응답 구조는 실행 중인 `/docs`와 [`schemas.py`](../src/coaching_service/schemas.py), [`personal_contract.py`](../src/coaching_service/personal_contract.py), [`forecast_validation_contracts.py`](../src/coaching_service/forecast_validation_contracts.py)가 기준입니다.
- `POST /v1/sessions/{session_id}/messages`의 응답은 `Coaching | ChatAnswer`입니다. 호출 계층은 모든 응답에 `receipt`가 있다고 가정하지 말고 응답 형식을 판별해야 합니다.
- HTTP 성공은 GPU 답변 채택이나 예측 정확도를 뜻하지 않습니다. 설명 출처, 대체 사유, 예측 기간과 원본 receipt를 응답 그대로 보존합니다.

## 엔드포인트와 역할

`backend` 역할은 원천 데이터를 쓰고, `user` 역할은 사용자 기능을 읽고 질문하며, `notification` 역할은 전달 상태만 다룹니다. 현재 인증 규칙은 [`auth.py`](../src/coaching_service/auth.py), 라우트 등록은 [`routes.py`](../src/coaching_service/routes.py)에 있습니다.

### 상태와 FDT 입력

| 메서드·경로 | 역할 | 용도 |
| --- | --- | --- |
| `GET /healthz` | 인증 없음 | API 기동, 엔진 파일 검증, 모델 설정 유무 확인. GPU 준비나 추론 성공 확인은 아님 |
| `POST /v1/twin` | `backend` | 초기 거래·선택적 snapshot·최대 7개 봉투로 Twin 생성 |
| `GET /v1/twin` | `backend` | 토큰 소유자의 현재 Twin 원문 조회 |
| `POST /v1/events` | `backend` | `expected_revision`과 거래·취소·snapshot 이벤트 반영 |

초기 입력은 `as_of`, 1개 이상의 `transactions`, 선택적 `snapshot`, 최대 7개의 `envelopes`를 포함합니다. 이후 변경은 먼저 `GET /v1/twin`에서 현재 revision을 읽고 `POST /v1/events`의 `expected_revision`에 넣습니다. 원천 시스템은 거래 ID, 날짜·시간, 금액, 분류, 취소와 pending 의미를 FDT 계약에 맞게 변환하고 자체 원장과의 대사 책임을 유지합니다.

### 코칭·대화·개인 현황

| 메서드·경로 | 역할 | 용도 |
| --- | --- | --- |
| `POST /v1/coaching/reviews` | `user` 또는 `backend` | 현재 Twin의 지정 기간 코칭 검토 |
| `GET /v1/coaching/{coaching_id}` | `user` 또는 `backend` | 저장된 코칭 조회 |
| `POST /v1/sessions` | `user` 또는 `backend` | 빈 대화 또는 기존 코칭에서 세션 생성 |
| `GET /v1/sessions/{session_id}` | `user` 또는 `backend` | 메시지 이력과 저장된 답변 참조 조회 |
| `POST /v1/sessions/{session_id}/messages` | `user` 또는 `backend` | 연속 질문과 선택적 분석·기간 입력 |
| `POST /v1/finance/questions` | `user` 또는 `backend` | Twin 없이 일반 금융 질문 |
| `GET /v1/answers/{answer_id}` | `user` 또는 `backend` | 저장된 `ChatAnswer` 조회 |
| `POST /v1/personal/context` | `backend` | 신뢰된 보험·소득·고정비·목표 현황 저장 |
| `GET /v1/personal/context` | `user` 또는 `backend` | 저장된 개인 현황 조회 |
| `POST /v1/personal/questions` | `user` 또는 `backend` | 개인 현황에 대한 질문 |
| `DELETE /v1/me/data` | `user` 또는 `backend` | 토큰 소유자의 AI 저장 자료 삭제 |

개인 현황 입력은 외부 백엔드가 권위 있는 원천과 자료 범위를 확인한 뒤 보냅니다. 앱이 임의로 만든 금융 상태를 `backend` 입력으로 승격하지 않습니다. 삭제 완료 후 외부 시스템에 남은 원장, 인증 계정과 푸시 토큰을 어떻게 처리할지는 각 소유 팀이 별도로 정의해야 합니다.

### 차트와 예측 검증

| 메서드·경로 | 역할 | 용도 |
| --- | --- | --- |
| `POST /v1/charts/budget-forecast` | `backend` | 저장된 Twin 또는 요청 거래로 예산 예측 차트 생성 |
| `GET /v1/charts/{chart_id}` | `user` 또는 `backend` | 저장된 차트 JSON 조회 |
| `GET /v1/charts/{chart_id}/html` | `user` 또는 `backend` | 같은 차트의 HTML 조회 |
| `POST /v1/forecast-validation/monthly-budgets` | `backend` | 승인 시각과 원천 참조가 있는 월별 7봉투 편성 등록 |
| `GET /v1/forecast-validation/monthly-budgets/{plan_id}` | `user` 또는 `backend` | 등록한 편성 조회 |
| `POST /v1/forecast-validation/registrations` | `backend` | 원본 예측과 입력 digest 사전등록 |
| `GET /v1/forecast-validation/registrations/{registration_id}` | `user` 또는 `backend` | 사전등록 원문 조회 |
| `POST /v1/forecast-validation/registrations/{registration_id}/settlement` | `backend` | 만기 후 권위 있는 실제 관측으로 정산 |
| `GET /v1/forecast-validation/registrations/{registration_id}/settlement` | `user` 또는 `backend` | 정산 결과 조회 |
| `POST /v1/forecast-validation/metrics` | `user` 또는 `backend` | 소유자의 등록·정산 결과 집계 |

예측 등록과 정산은 실시간 사용자 기능과 별도의 검증 흐름입니다. 외부 백엔드는 예측 생성 시점의 원문과 원천 참조를 고정하고, 기간 만기 뒤 완전하게 수집한 실제값만 정산해야 합니다. 합성 입력이나 공개 해외 원장 결과를 실고객 정확도로 표시하지 않습니다. 세부 계약은 [예측 검증 API](forecast-validation.md)에 있습니다.

## 알림 전달 계약

AI API는 코칭 알림을 SQLite의 `outbox/`에 저장하지만 FCM이나 OS 푸시를 직접 보내지 않습니다. 외부 알림 전달기는 다음 순서를 지킵니다.

1. 해당 소유자의 `notification` 역할 토큰으로 `GET /v1/notifications`를 호출합니다.
2. 응답의 `event_id`, `coaching_id`, `text`, `created_at`을 이용해 실제 알림을 전송합니다.
3. 전송 성공을 확인한 뒤 `POST /v1/notifications/{event_id}/ack`를 고유한 `Idempotency-Key`와 함께 호출합니다.
4. 전송이 실패하면 ack하지 않습니다. 해당 항목은 다음 조회에도 남습니다.

ack가 성공하면 항목은 대기 outbox에서 제거되고 `acknowledged=true`인 기록으로 이동합니다. 사용자 역할 토큰은 알림 조회·ack에 사용할 수 없습니다. 현재 구현상 `backend` 역할도 이 경로를 호출할 수 있지만, 운영 전달기는 별도 `notification` 토큰을 사용하는 것이 인계 기준입니다. 저장 동작은 [`records.py`](../src/coaching_service/records.py)에서 확인할 수 있습니다.

## 외부 팀의 완료 기준

외부 연동이 완료됐다고 판단하려면 각 소유 팀이 다음 증거를 별도로 남겨야 합니다.

- 실제 로그인 주체와 `COACHING_CLIENTS.user_id` 매핑의 서버 측 검증
- 운영 원장·예산·개인 현황에서 Python 요청 스키마로의 변환 및 대사
- 동일 요청 재시도와 revision 충돌 처리
- `Coaching | ChatAnswer` 파싱, 세션 재조회 후 출처·예측 기간 보존
- 푸시 실수신 뒤 ack와 실패 시 미ack 재시도
- 운영망에서 Python API·GPU 추론 서버의 인증, 제한 시간, 장애 복구와 모니터링

이 증거가 없으면 독립 Python API의 시험 통과를 앱·백엔드 통합 또는 실제 푸시 완료로 확대해석하지 않습니다. Python 서비스 실행과 모델 설정은 [운영 설정](operations.md), 앱에 표시할 차트 계약은 [차트 연결 안내](charts.md)를 따릅니다.
