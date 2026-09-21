# 벤치마크

평가는 두 종류입니다. 질문의 경로를 잘 고르는지를 소비 예측 정확도라고 부르지 않습니다.

| 경로 | 입력 → 비교 대상 | 알 수 있는 것 |
| --- | --- | --- |
| [`coaching/`](coaching/) | 합성 질문·거래 상황 → 미리 정한 계약 | 코칭 감지·분류·근거 준수·오류 복구 |
| [`coaching/e2e/`](coaching/e2e/README.md) | 실제 HTTP 흐름과 추론 호출 → 계약·응답 추적 | 연결 오류, 대체 발생, 토큰 선검사 |
| [`coaching/flow/`](coaching/flow/README.md) | 결제→알림→동일 세션→추가·취소·잔액→실제 프로세스 재시작 | 현재 원장 반영·과거 코칭 보존·GET/멱등성·모델 채택 |
| [`coaching/knowledge_response/`](coaching/knowledge_response/README.md) | 공식 개념·개인 조회·자료 부족·연속 질문 → 근거 ID·원금액 | 등록된 주제의 응답 커버리지; 전체 금융 정답률은 아님 |
| [`coaching/chart_e2e.py`](coaching/chart_e2e.py) | 거래와 예산 기간 → 실제 추론·차트 JSON·HTML·저장 조회·재시도 | 차트 연결과 결과 일관성; [실행법](../docs/charts.md#재현과-검증-범위) |
| [`forecast/`](forecast/README.md) | 기준일까지 원장 → 이후 원장 소비 합계 | 관측된 SEED 시계열의 미래 소비 오차 |

`coaching/case_catalog.json`은 회귀시험용 질문 계약입니다. 숨겨진 독립 검증셋이 아닙니다. `forecast/ledger_adapter/`는 거래 원장을 평가 입력으로 읽고 실제 FDT 경계를 호출하는 어댑터입니다.

평가기 자체의 테스트 코드는 [`tests/forecast/`](../tests/forecast/), HTTP 계약 테스트는 [`tests/test_e2e.py`](../tests/test_e2e.py)에 있습니다. 이 폴더에는 평가 실행기와 실행에 필요한 고정 입력만 둡니다.

실행 결과는 새 `artifacts/` 하위 디렉터리 또는 저장소 밖으로 지정합니다. 보고서는 [`docs/validation.md`](../docs/validation.md)에 정리하며 raw 로그·모델 응답·원장·학습 가중치를 저장소에 추가하지 않습니다. 점수를 보고 수정한 뒤 같은 자료에 다시 측정한 결과는 회귀시험으로 기록합니다.
