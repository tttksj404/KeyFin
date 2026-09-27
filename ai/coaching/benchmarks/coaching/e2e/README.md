# 코칭 HTTP 평가

서비스 API와 모델 게이트웨이를 실제 TCP로 연결해 24개 합성 시나리오를 실행합니다. 결제 감지, 중복·충돌, 사용자 격리, 코칭 조회, 대화와 의도적 모델 오류를 포함합니다. 정답 라벨은 모델 입력에 넣지 않습니다. 시나리오와 라벨은 공개 회귀 자료이므로 비공개 사람 평가라고 부르지 않습니다.

서비스 디렉터리에서 먼저 모델 없이 실행합니다.

```powershell
uv run python -m benchmarks.coaching.e2e.e2e --backend fake --output artifacts/e2e-fake
```

실제 추론 서버가 준비된 뒤 같은 디렉터리에서 아래 명령을 사용합니다. URL과 토큰 파일 경로는 개인 설정으로 바꿉니다. 두 확인 플래그는 선행 회귀시험을 마쳤고 할당된 추론 자원을 사용한다는 실행자의 확인입니다.

```text
python -m benchmarks.coaching.e2e.e2e --backend gpu --model latest27_nf4 --primary-completed --allow-gpu --upstream-url http://127.0.0.1:18743 --upstream-token-file /private/worker.token --output /private/e2e-result
```

출력의 `freeze.json`에는 소스·질문 해시, `report.json`에는 시나리오·생성·토큰 측정 결과, `verification.json`에는 파일 무결성 결과가 기록됩니다. 토큰은 출력에 넣지 않습니다. 설명 출처가 템플릿인 경우와 실제 모델 채택을 구분해 집계합니다. 의도적으로 오류를 주입한 항목을 모델의 자연 실패율에 섞지 않습니다.

명시적 `analysis.mode=forecast|risk`는 모델 분류 없이 확정한 경로이므로
`deterministic_routes`에 별도로 센다. 모델 분류·설명의 실제 호출만 채택률과
대체율의 분모에 포함하며, 명시적 경로에서도 설명 호출·수치 근거 검사는 유지한다.

서버로 실행 코드를 옮길 때는 `python -m benchmarks.coaching.e2e.e2e_bundle --output artifacts/e2e-runtime.zip`으로 실행용 묶음을 만들 수 있습니다. 라벨·이전 출력·데이터베이스는 제외되며 학습 자료로 사용하지 않습니다. 평가는 생성된 기록을 원래 질문 계약과 대조하는 별도 단계입니다.
