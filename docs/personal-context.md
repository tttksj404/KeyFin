# 개인 금융 현황 조회 계약

개인 질문의 숫자는 저장된 원본 자료를 서버가 합산한다. LLM이 잔액·대출액·소득을 생성하지 않는다. 이 기능은 현재 현황 조회이며, 금융 거래 실행이나 미래 예측 결과를 생성하지 않는다.

## 어떤 자료를 읽는가

| 질문 | 출처 | 합계의 정확한 의미 |
| --- | --- | --- |
| 내 계좌 잔액 알려줘 | 기존 FDT `snapshot.accounts` | snapshot 기준일의 보고된 계좌 잔액 합계. 음수 잔액도 유지한다. |
| 내 자산 얼마야 | 기존 FDT `accounts` + `assets` | 계좌 순잔액과 비계좌 자산가액의 합계. 부채 차감 순자산은 아니다. |
| 내 부채 얼마야 | 기존 FDT `liabilities` + 신용카드 `opening_payable_krw` | 대출 원금과 카드 미결제액. 같은 카드의 `known_bills`는 다시 더하지 않는다. |
| 예정 결제 알려줘 | 기존 FDT `known_bills` | snapshot 기준일 다음날부터의 등록된 카드 청구서. 미래 소비·전체 자동이체 합계는 아니다. |
| 내 보험료는? | 새 개인 현황 `insurance` | 등록 월 보험료 합계. 보장액은 중복 보장 때문에 합산하지 않는다. |
| 내 월 소득 얼마야 | 새 개인 현황 `income` | 등록된 월 소득 금액. 실제 입금 거래를 집계한 실현 소득은 아니다. |
| 내 고정비 알려줘 | 새 개인 현황 `fixed_costs` | 등록된 월 고정비 금액. 과거 확정 출금 합계는 아니다. |
| 내 금융 목표 보여줘 | 새 개인 현황 `goals` | 각 목표의 적립액·목표액·목표일. 목표 간 자금 중복 여부가 불명확하므로 합산하지 않는다. |

FDT가 이미 관리하는 계좌·자산·부채·카드 청구서는 새 DB에 복제하지 않는다. FDT `schedules`는 예측용 지급 가정을 담으므로 실제 소득의 정답으로 바꾸지 않는다. 보험·월 소득·월 고정비·목표의 새 현황은 조회 전용이다. 이 입력을 저장했다고 FDT 예측의 소득·고정비 가정까지 동기화되는 것은 아니다.

FDT 응답은 snapshot 기준일, `LIVE` 또는 `USER_ASSUMPTION` 출처와 원본 snapshot의 SHA-256을 근거에 담는다. snapshot과 Twin 거래 기준일이 다르면 이를 문구에도 표시한다. `LIVE`는 상류 입력의 출처 표시이며 이 API가 은행을 실시간으로 재조회했다는 뜻이 아니다.

## 입력 및 읽기 API

- `POST /v1/personal/context`: backend 역할의 토큰으로만 전체 현황 교체.
- `GET /v1/personal/context`: 인증된 자기 소유자의 최근 현황 조회.
- `POST /v1/personal/questions`: 일반 사용자 또는 backend 토큰으로 질문하고 답을 저장.
- `GET /v1/answers/{id}`: 기존 답변 조회 API로 원문 재조회.
- `DELETE /v1/me/data`: 기존 전체 삭제에 개인 현황·개인 답변·멱등 요청 기록이 포함된다.

모든 POST는 `Idempotency-Key` 헤더가 필요하다. 사용자 ID는 body로 받지 않고 설정된 토큰의 소유자만 사용한다. 서버가 UTC `received_at`을 기록한다. 입력에는 날짜만 있는 `as_of`, 출처 시스템과 레코드 ID, 실제 자료/사용자 신고/합성 자료의 구분이 필요하다. `provenance=connected_backend`는 제출자의 분류이며 독립 검증 완료 표시는 아니다.

다음은 합성 예제다. 실제 사용자 자료가 연결되었다는 증거가 아니다.

```json
{
  "expected_revision": 0,
  "as_of": "2026-09-03",
  "currency": "KRW",
  "source_system": "backend",
  "source_record_id": "synthetic-example-v1",
  "provenance": "synthetic",
  "income": {
    "coverage": "complete",
    "items": [
      {"id": "salary", "label": "급여", "monthly_amount_krw": 3100000}
    ]
  },
  "insurance": {
    "coverage": "partial",
    "items": [
      {"id": "health", "label": "건강보험", "monthly_premium_krw": 30000}
    ]
  }
}
```

이는 patch가 아닌 **전체 교체**다. 예시에서 생략한 `fixed_costs`와 `goals`는 `unknown`이 된다. 이전에 있던 값을 남겨서 최신 수집값처럼 표시하지 않는다. 연납 보험료나 연 소득을 월 금액에 그대로 넣어서는 안 된다. 상류에서 월 금액의 의미가 확정되지 않으면 해당 항목을 누락 상태로 보내야 한다.

첫 요청의 `expected_revision`은 0이며, 이후 GET/POST 응답의 `revision`을 사용한다. 동일 키와 동일 본문은 최초 응답을 그대로 반환한다. 같은 키의 다른 본문, 오래된 revision, 저장된 값보다 이전 기준일은 409다. 현재 한국 날짜보다 미래인 현황 기준일은 422다. 같은 날짜의 수정 자료는 새 revision과 새 키로 보낼 수 있다.

각 금액은 소수·문자열·불리언으로 변환되지 않는 정수 원 단위이며 범위는 0~1조 원이다. FDT 계좌 잔액만 -1조~1조 원을 허용한다. 목표액은 양수이며, 목표액을 이미 초과한 적립액은 유효하다. 같은 section 내 동일 ID를 중복 등록하거나 `unknown`에 항목을 넣으면 거부한다. FDT 조회 투영도 계좌·자산·부채·카드·청구서의 중복 ID와 누락 카드 미결제액을 거부한다.

## 자료 범위와 답변

`coverage=complete`는 backend가 그 section의 보고 범위를 모두 확인했다는 선언이다. 제삼자의 독립 검증을 뜻하지 않는다. `partial`은 보고된 일부 항목만 합산하며 전체 보유 현황으로 확정하지 않는다. `unknown` 또는 항목이 없는 `partial`은 `needs_data`이고 `total_krw`가 `null`이다. **확인된 `complete` 빈 목록만 0원**으로 답한다.

기존 FDT의 자산·부채 전체 보고 여부는 `coverage.all_assets_reported`와 `all_liabilities_reported`를 그대로 읽는다. 계좌 목록과 카드 청구서에는 모든 기관의 수집 완료를 증명하는 필드가 없어 일부 보고로 표시한다. 자산과 계좌의 실세계 중복, 카드와 대출의 실세계 중복은 상류 데이터 계약이 보장해야 한다. 서로 다른 ID로 들어온 같은 실세계 자산을 AI가 추측하여 제거하지 않는다.

질문 본문은 `{"question":"내 계좌 잔액 알려줘"}`다. 반환은 공통 `ChatAnswer`이며 `answer_type=personal_context`, `wording_source=engine`, `model=not_called`이다. 여기의 `engine`은 결정적 서버 집계 경로를 뜻하며 LLM 호출 성공을 뜻하지 않는다. 수치·기준일·행별 근거·출처·범위는 `evidence`에 포함된다. 기존 FDT 예측 답변의 `receipt`와 구분해 표시해야 한다.

한 질문에서 한 항목을 조회한다. 특정 은행·기간·항목 제외·복수 항목 비교와 같이 지원하지 않는 조건이 있으면 `needs_clarification`으로 안내한다. 조건을 버리고 전체 합계를 답하지 않는다. 자유로운 표현 전부를 처리하는 의미 검색기는 아니다. 세션 라우터가 `personal`로 분류한 뒤에도 같은 엄격한 선택기를 사용한다.

## 통합 위치와 검증 범위

`personal_routes.register_personal_context(app, core, auth)`가 API를 등록한다. `personal_service.personal_answer(repository, owner, question)`는 저장 없이 `ChatAnswer`를 반환한다. 세션은 이를 기존 대화 메시지와 `answer/{id}`와 같은 Mutation으로 저장한다. Repository의 기존 `items` 테이블, 소유자 예약, 멱등성 기록과 전체 삭제를 재사용하므로 새 테이블이나 별도 파일 DB가 없다.

테스트는 `tests/test_personal*.py`에서 실행한다. 독립된 원 단위 예제, 실제 FastAPI/SQLite 경로의 인증·격리·멱등성·revision·재시작·삭제, FDT 원본 불변을 검증한다. ASGI 테스트의 모델은 주입된 테스트 객체이며, 개인조회는 설계상 모델 호출 횟수가 0이다. 운영 backend의 실제 동기화, 금융기관별 수집 완전성, 실제 고객의 미래 예측 정확도는 이 검사로 입증하지 않는다.
