# 고정 금융 개념 응답 지연 화면

이 폴더는 한 개의 승인된 금융 개념을 고정 출처 문장으로 답하는 경로를 실제 로컬 TCP API에서
측정한다. 모델 호출·FDT 계산·고객 원장·배포 네트워크는 포함하지 않는다. 따라서 이 결과는
일반적인 서비스 응답시간이나 고객 금융 예측 정확도를 뜻하지 않는다.

```powershell
uv run --project . python -m benchmarks.coaching.direct_catalog_latency.run `
  --output artifacts/r26-direct-catalog-tcp-latency.safe.json --rounds 20 --concurrency 1 4 8
```

실행기는 승인된 27개 단일 개념 질문과, 명시적으로 두 개념을 비교하는 3개 질문을 새 세션으로만
전송한다. 각 응답은 `model=not_called`, `wording_source=template`, 질문별 기대 출처 ID 순서,
`Server-Timing`의 모델·FDT 단계 부재를 모두 검사한 뒤에만 지연시간을 집계한다. 산출물에는 원문
질문·응답·토큰·개인 자료를 기록하지 않고, 질문 ID와 기대 출처 ID의 해시 및 집계 시간만 남긴다.
`--rounds`는 최소 반복 횟수다. 동시성별 요청 수가 30개 문항보다 적으면 실행기는 각 문항을 한 번씩
포함할 만큼만 추가 파동을 보내므로, 보고서의 문항 수와 실제 검증 범위가 어긋나지 않는다.
