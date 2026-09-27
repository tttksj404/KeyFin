# 실제 공개 은행 원장 기반 예측 실험

합성 질문의 경로·응답 형식 검사를 넘어, **예측 이후 실제 원장에 기록된 출금액과 예측액의 오차**를 측정한다. 체코의 과거 공개 자료이며 현재 한국 서비스 고객의 예측 정확도를 검증한 것으로 해석하면 안 된다. 세부 조건은 정답을 만들기 전에 고정한 [PROTOCOL.md](PROTOCOL.md)를 따른다.

최초 실행의 수치·채택 판단·독립 재검산은 [R12 결과 보고서](../../../docs/answer-forecast-improvement.md)에 있다. 프로토콜의 `base`는 내부 후보명이다. 이번 실행은 런타임에서 기록한 로컬 체크포인트이며 canonical 원본 정체성을 사전 고정한 비교가 아니다. `128 steps`는 fit 요청값이며 실제 optimizer 갱신 횟수의 독립 확인과 구분한다.

설치된 chronos-forecasting 2.3.1의 `predict_quantiles()`는 `mean`이라는 반환값에 실제로 일별 0.5 분위수를 담는다. 프로토콜의 “일별 평균”은 부정확한 표현이며, 이번 실행은 이 일별 P50 합계를 **점예측 후보**로 평가했다. 기간 전체의 평균·P50·확률구간이라고 해석하지 않는다. 실행 소스·예측·선택은 그대로 보존하고 다음 프로토콜에 정확한 통계량을 사전 등록한다.

프로토콜에서 말하는 익명 계좌는 정확히는 가명 해시 계좌키다. 파서는 `csv.DictReader`로 행을 읽은 뒤 명시된 열만 계산에 참조하므로, 다른 열을 메모리에 전혀 파싱하지 않는다는 의미의 열 제한은 아니다. 계산에 쓰지 않는 열을 모델 입력이나 결과에 내보내지 않는다. 이 설명은 실행 뒤의 표현 보완이며 고정 프로토콜·후보·예측을 변경하지 않는다.

## 코드와 실행 산출물

| 파일 | 역할 |
| --- | --- |
| `contracts.py` | 과거 입력·정답·예측·선택 결과를 구분하는 스키마와 날짜·계좌 분리 검사 |
| `data.py` | 원본 SHA 확인, 계산에 쓸 열 선택, 정수 단위 금액 집계 |
| `prepare.py` | 학습/개발/평가 분할 및 입력·정답 파일 분리 |
| `baselines.py` | 과거 평균·요일·달력 동일일 기준 후보 6개 |
| `worker.py` | GPU 추론, 두 조건 fine-tuning, 모델/소스/입력 해시와 실행 시간 기록 |
| `validation.py` | 예측 누락·중복·추가 사례·잘못된 금액 거부 |
| `provenance.py` | 완료·입력·실행 소스·학습 조건·가중치 변경 및 수집 파일 해시 검증 |
| `source_verification.py` | 보존된 실제 실행 소스와 검토 코드의 선언·계산 AST 직접 대조 |
| `evaluate.py` | 개발만 사용한 모델 선택과 별도 최종 평가 |
| `metrics.py` | 금액 오차, WAPE, bias, 계좌 단위 bootstrap |
| `tests/forecast/test_public_bank.py` | 경계 날짜·미래 거래 차단·변조·실제 CLI의 검증 시험 |

원자료와 실행 결과는 저장소 바깥의 개인 디렉터리에 둔다. 아래 `SOURCE`, `PREPARED`, `MODEL_OUTPUT`은 운영자가 지정할 절대 경로다. 제품 wheel에 이 실험과 원자료는 포함하지 않는다.

## 실행 순서

서비스 루트 `ai/coaching`에서 실행한다.

```console
python -m benchmarks.forecast.public_bank prepare SOURCE PREPARED
```

준비 결과:

- `protocol.lock.json`, `manifest.json`: 생성 시각, 원본·입력·정답·프로토콜 SHA.
- `model_inputs.json`: 학습 계좌의 과거 자료와 개발/평가 계좌의 기준일 이전 이력.
- `development_truth.json`, `evaluation_truth.json`: 서로 분리된 원장 정답.
- `predictions/`: 단순 기준 후보 결과.

`model_inputs.json`과 실행 코드만 GPU 환경으로 옮긴다. 정답 파일을 업로드하지 않는다. GPU worker 설정 JSON은 다음 세 경로만 받는다.

```json
{
  "inputs": "/private/prepared/model_inputs.json",
  "output": "/private/model-output",
  "chronos_checkpoint": "/private/checkpoint"
}
```

운영자가 `CUDA_VISIBLE_DEVICES`와 `COACH_GPU_ALLOWED_DEVICES`를 허용된 단일 장치로 지정한다. worker는 기존 `scripts.gpu_registry`로 승인 상태를 검사하므로 해당 모듈도 실행 환경에 제공한다. 실행 시 자동 장치 탐색·서비스 중지·제품 모델 교체는 하지 않는다.

```console
python -m benchmarks.forecast.public_bank.worker /private/run-config.json
python -m benchmarks.forecast.public_bank.evaluate select PREPARED MODEL_OUTPUT
python -m benchmarks.forecast.public_bank.evaluate evaluate PREPARED MODEL_OUTPUT
```

첫 명령의 학습·추론은 `completed.json`까지 끝나야 한다. 전체 후보의 같은 1,800개 예측이 있어야 선택할 수 있다. `select`는 평가 정답의 **값을 열지 않고** 준비 때 기록한 해시만 가져와 `selection.json`에 고정한다. `evaluate`는 선택 이후 바뀐 입력·예측·manifest·평가 정답을 거부하고 `report.json`을 만든다. 선택·보고서를 덮어쓰지 않으므로 후속 실험에는 새 출력 디렉터리를 사용한다.

GPU 결과를 수집할 때는 `runtime.json`, `completed.json`, 후보별 `inference.json`·`predictions.json`, 학습 후보별 `training.json`과 각 파일의 원격 SHA를 함께 가져온다. `file_hashes.json`은 파일명→원격 SHA 맵이다. 선택 단계가 이를 재검증해 `neural_run_manifest.json`으로 고정하며, 최종 평가는 개발 정답만으로 선택을 다시 계산해 선택 문서의 변조도 거부한다. 실행 중 코드와 검토 후 코드가 다르면 worker의 계산 함수 AST 동등성 근거가 별도로 필요하다.

실행 당시 모든 Python 소스는 `MODEL_OUTPUT/source_snapshot/benchmarks/forecast/public_bank/`에 원본 그대로 보존한다. 검증기는 runtime의 소스 해시에 직접 대조하고, worker의 계산과 입력 스키마에 쓰이는 선언을 현재 코드와 AST로 비교한다. 별도 JSON에 `ast_equal=true`라고 기록한 주장으로 검사를 대체할 수 없다. 기준 모델도 저장된 예측만 믿지 않고 과거 입력에서 다시 계산한다.

계좌키는 공개된 데이터셋 계좌 ID의 결정적 **가명키**이며 비가역적 익명화를 주장하지 않는다. 원자료와 사례별 가명키는 공개 보고서에 포함하지 않는다.

## 결과를 읽는 방법

- **MAE(CZK)**: 미래 기간의 총 출금액을 평균 얼마 틀렸는지다. 7일과 30일을 별도로 읽는다.
- **WAPE**: 전체 절대오차를 전체 실제 출금으로 나눈 값이다. 예를 들어 0.2는 오차합이 출금합의 20%라는 뜻이며, “80% 정확도”라고 부르지 않는다.
- **mean bias(CZK)**: 예측−실제 평균이다. 음수는 출금을 작게 예측한 경향이다.
- **계좌 bootstrap 95% CI**: 같은 계좌의 여러 예측을 함께 재표집해 계좌 간 변동을 반영한다. 미래 개별 계좌 금액의 확률구간이 아니다.
- **paired WAPE difference CI**: 선택 모델 WAPE−기준 모델 WAPE의 차이다. 음수일수록 선택 모델이 낫다. 구간이 0을 포함하면 이 평가에서 우위를 확정하기 어렵다.
- **individual_candidates**: 개발 선택을 끝낸 뒤 공개한 모든 단일 후보의 평가 점수다. 이 순위를 보고 시험 승자로 재선택하면 이번 평가는 더 이상 숨겨진 최종 평가가 아니다.

모든 점수는 총 계좌 출금 CZK에 대한 것이다. 계좌잔액, 일곱 소비 봉투, LLM 설명 품질, 한국 고객, 미래 실제 서비스 성과는 이 지표에 포함되지 않는다. 사전학습 포함 여부·수집 지연·지원되지 않는 거래 type 제외·국가와 시대 차이도 프로토콜의 한계로 함께 보고한다.
