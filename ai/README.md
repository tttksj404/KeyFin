# AI 코칭

사용자의 거래·잔액으로 FDT가 금융 수치를 계산하고, AI가 코칭 여부·질문 의도를 분류한 뒤 근거에 맞는 설명을 작성하는 독립 API입니다. 서비스 코드는 [`coaching/`](coaching/)에 있습니다.

처음 보는 분은 아래 순서로 읽으면 됩니다.

| 알고 싶은 내용 | 문서 |
| --- | --- |
| 무엇을 실행하고 어떻게 호출하는가 | [서비스 시작하기](coaching/README.md) |
| AI·FDT·DB가 어떻게 연결되고 요청이 어떻게 처리되는가 | [Mermaid 구조도와 기간 계약](coaching/docs/architecture.md) |
| 거래 입력으로 기존 KeyFin 차트를 생성하려면 | [차트 API와 프런트엔드 연결](coaching/docs/charts.md) |
| 어떤 성능을 실제로 확인했는가 | [검증 결과와 한계](coaching/docs/validation.md) |
| 추론 서버와 인증은 어떻게 설정하는가 | [운영 설정](coaching/docs/operations.md) |
| 같은 실험을 다시 실행하려면 | [벤치마크 안내](coaching/benchmarks/README.md) |

```text
ai/
├── README.md                 # 이 안내
└── coaching/
    ├── src/coaching_service/ # 운영 API와 코칭 로직
    ├── vendor/fdt/           # 팀 FDT 엔진의 고정 버전
    ├── vendor/keyfin_chart/  # 팀 차트 렌더러의 고정 실행 자산
    ├── tests/                # API·금융 처리·오류 복구 회귀시험
    ├── scripts/              # 추론 서버와 HTTP 스모크 실행기
    ├── examples/             # 최소 API 요청 예시
    ├── docs/                 # 구조·운영·검증 보고서
    ├── benchmarks/           # 코칭 계약과 소비 예측 평가 실행기
    └── artifacts/            # 실행 부산물; 생성 시에만 존재하며 Git 제외
```

실험 출력은 각 실행자가 `artifacts/` 또는 저장소 밖에 보관합니다. 거래 원장, 학습 체크포인트, 프로세스 로그, 인증 설정은 커밋하지 않습니다. 과거의 시도별 폴더를 실행 의존성으로 사용하지 않습니다.

`tests/`는 코드를 검사하는 파일, `benchmarks/`는 성능 실험을 실행하는 파일, `artifacts/`는 그 실행으로 만들어진 결과물입니다. 사람이 읽을 요약 결과만 `docs/validation.md`에 남깁니다.
