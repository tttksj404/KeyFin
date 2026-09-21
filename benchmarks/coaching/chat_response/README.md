# 자연어 금융 채팅 응답 회귀

이 벤치마크는 실제 HTTP API에서 일반 금융 개념, 연결된 소비 이력, 자연어 예측·위험 질문이 직접 답변되는지 고정 문항으로 확인한다. 금융 개념은 모델이 선택한 근거 ID와 서버가 표시한 출처를 대조한다. 예측은 응답 receipt의 금액·기간·조건부 모형 한계가 최종 문장에 전달됐는지 검사한다. 실제 미래 예측 정확도나 사람의 답변 만족도를 평가하지 않는다.

격리된 데이터베이스와 아직 Twin이 없는 전용 자격 증명을 사용한다. 토큰은 파일이나 명령 인자에 넣지 않고 환경 변수로만 전달한다. fixture는 토큰·비밀번호·인증 헤더를 포함하지 않는 Twin bootstrap JSON이어야 한다. 기존 차트 fixture처럼 `request.data` 아래에 bootstrap이 있어도 된다. 거래와 snapshot 내부의 `user_id`는 전용 자격 증명의 소유자와 같아야 하며 실행기가 소유자를 임의 변경하지 않는다.

```powershell
$env:COACHING_CHAT_TOKEN = Read-Host -MaskInput
uv run python -m benchmarks.coaching.chat_response.run `
  --api-url $env:COACHING_CHAT_API_URL `
  --fixture <fixture.json> `
  --output artifacts/chat-response/run-001

uv run python -m benchmarks.coaching.chat_response.score `
  artifacts/chat-response/run-001/responses.json `
  artifacts/chat-response/run-001/score.json
```

실행기는 Twin 연결 전 문항을 먼저 수행하고 fixture를 연결한 뒤 나머지 문항을 각각 새 세션에서 실행한다. 모든 답변은 해당 저장 조회 API와 세션 이력으로 다시 읽어 원문 일치를 기록한다. 원문 응답과 fixture 식별 정보는 Git에서 제외된 `artifacts/` 아래에만 저장한다.

점수는 세 층으로 분리된다.

- `http`: 상태 코드, 독립 세션 이력, 저장 조회 원문 일치
- `semantic`: 근거 ID, 질문별 핵심 설명, receipt 수치·기간, 소비 집계 범위와 한계
- `model_admission`: 모델 선택/보조 문장 채택, 정형 대체, 모델을 호출하지 않은 엔진 답변

소표본 지연시간은 최솟값·중앙값·최댓값만 기록한다. 금융 개념의 `accepted`는 근거 ID 선택이 채택됐다는 뜻이며, 표시 문장은 서버의 검토된 지식 카드에서 조립된다.

예측 기간은 fixture의 `as_of`와 표준 달력으로 별도 계산해 시작일·종료일·일수를 검사한다. 월말 질문은 다음 날부터 해당 월 말일까지이므로 월말 기준일에는 미래 구간이 없다. 이 고정 답변 시험의 세 예측 문항을 비교하려면 월말 이전의 기준일과 지원하는 7봉투 소비 이력이 있는 fixture를 사용한다.
