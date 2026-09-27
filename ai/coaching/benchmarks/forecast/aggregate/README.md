# 기간 합계 예측 실험

제품 실행 코드는 `src/coaching_service`, 이 폴더는 연구 실행 코드, 검증 코드는 `tests/forecast/test_aggregate*.py`입니다. 원자료·입력·가중치·사례별 결과는 저장소 밖의 비공개 작업 디렉터리에 보관합니다. 요약 결과와 해석은 [R15 보고서](../../../docs/aggregate-forecast-r15.md)에 있습니다.

## 비교 대상과 실행 순서

[PROTOCOL.md](PROTOCOL.md)는 자료 분리, 후보 20개, 추가학습 조건, 보정·선택·통과 기준을 실행 전에 고정합니다. 체코 과거 은행 원장의 **7일/30일 총출금**이 타깃이며 한국 소비 봉투나 계좌 잔액을 직접 예측하는 제품 API가 아닙니다.

코칭 서비스 디렉터리에서 실행합니다. `$source`, `$prepared`, `$gpu`, `$evaluation`은 각각 승인된 원자료, 새 입력 디렉터리, 수집한 GPU 결과, 새 평가 출력 경로입니다. 존재하는 출력 경로는 재사용하지 않습니다.

```powershell
uv run python -m benchmarks.forecast.aggregate.prepare $source $prepared
```

GPU 작업은 검증된 배정과 프로젝트의 GPU registry를 사용합니다. `model_inputs.json`만 전달하고 세 정답 파일은 전달하지 않습니다. 연구용 ML 환경에서 다음 명령을 실행합니다.

```text
python -m benchmarks.forecast.aggregate.worker run-config.json
```

`run-config.json`은 `inputs`, `output`, `chronos_checkpoint`, `expected_base_weights_sha256`를 갖습니다. 호스트·사용자·장치·인증정보를 설정 예제나 커밋에 적지 않습니다. GPU 환경의 `torch`, `transformers`, `chronos-forecasting`, `numpy` 버전은 `runtime.json`에 기록됩니다. 제품 의존성에 학습 패키지를 추가하지 않습니다.

결과를 수집할 때 최상위 예측 파일 3개, `runtime.json`, `completed.json`, 학습 기록 4개, 추론 기록 6개, 실행한 `source_snapshot`과 이 파일들의 상대경로 SHA256을 담은 `file_hashes.json`이 필요합니다. 공개 소스 스냅샷은 원격에서 실제 실행한 파일이어야 합니다. 메타데이터만 재작성하여 실행 성공을 만들 수 없습니다.

```powershell
uv run python -m benchmarks.forecast.aggregate.evaluate select $prepared $gpu $evaluation
uv run python -m benchmarks.forecast.aggregate.evaluate calibrate $prepared $gpu $evaluation
uv run python -m benchmarks.forecast.aggregate.evaluate evaluate $prepared $gpu $evaluation
```

첫 명령은 개발 정답만으로 선택하고 잠금을 씁니다. 두 번째는 별도 계좌의 보정 정답만 읽습니다. 마지막은 모든 해시·설정·선택·보정값을 재검증한 후 최종 평가 정답을 읽고 `report.json`을 새로 씁니다. 평가 이후 변경한 후보는 같은 자료에서 신규 독립 평가를 받았다고 주장할 수 없습니다.

## 파일별 책임

| 파일 | 역할 |
| --- | --- |
| `prepare.py`, `contracts.py` | 원자료 해시·계좌 분리·365일 입력·미래 기간 |
| `arithmetic.py` | 단순 기준 및 강건한 기간 합계 후보 |
| `worker.py`, `worker_support.py` | 실제 추가학습·추론·optimizer 관측·분위수 감사 |
| `protocol_boundary.py`, `artifacts.py`, `provenance.py` | 필수 파일·기간·학습 횟수·실행 소스·입력 해시 검증 |
| `selection.py`, `evaluate.py` | 개발 선택 → 구간 보정 → 최종 평가의 단방향 실행 |
| `scoring.py`, `report.py` | 금액 오차·구간·계좌 단위 신뢰구간·악화 구간 보고 |

```powershell
uv run pytest tests/forecast -k aggregate -o addopts="" -q
```

단위시험의 숫자 예제는 구현 검증용이며 원자료의 예측 성능 분모에 포함하지 않습니다.
