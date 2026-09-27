# GPU 워커 배포 재현성 (prod27_fp8)

`docs/operations.md`의 일반 배포 절차를 보완합니다. 이 문서는 `prod27_fp8` 운영 모델을
`COACH_GPU_LINK_MODE=ws`(아웃바운드 WebSocket 터널)로 기동할 때 필요한, 저장소에 없던
두 가지를 제공합니다: (1) `COACH_GPU_MODEL_REGISTRY`가 요구하는 등록 JSON, (2) 검증된
venv를 고정하는 기동 스크립트.

## 1. 모델 등록 JSON

워커는 `scripts/gpu_registry.py`의 `Registry`/`ModelEntry` pydantic 모델로 이 파일을
엄격 검증합니다(`extra="forbid"`, `revision`은 40자리 hex, `config_sha256`은 64자리
hex). 스키마와 필드 의미는 `scripts/gpu_registry.py`를 참조하세요.

템플릿: [`scripts/gpu_model_registry.example.json`](../scripts/gpu_model_registry.example.json)

```json
{
  "models": [
    {
      "tag": "prod27_fp8",
      "model_id": "Qwen/Qwen3.8-27B-FP8",
      "path": "/private/checkpoint/prod27_fp8",
      "revision": "<배치할 체크포인트의 40자리 commit>",
      "config_sha256": "<그 경로 config.json의 64자리 sha256>",
      "quantization": "fp8"
    }
  ]
}
```

`revision`/`config_sha256`은 이 템플릿에서 자리표시자(0으로 채움)이며, 배치 직전 실제
체크포인트에서 계산한 값으로 **반드시 교체**해야 합니다(운영 파일은 개인 설정이라
커밋하지 않습니다 — `docs/operations.md` 참조). vLLM 디코더 옵션
(`max_model_len=9728`, `gpu_memory_utilization=0.75`, `enable_prefix_caching=True`,
`enforce_eager=False`, `dtype=bfloat16`, `tensor_parallel_size=1`)은 JSON에 넣지 않습니다
— `scripts/gpu_registry.py`의 `vllm_decoder_options()`가 `(tag, quantization)` 조합으로
고정 정책을 반환하며, `("prod27_fp8", "fp8")`은 vLLM이 체크포인트 자체 설정에서 FP8을
자동 인식하도록 별도 loader를 지정하지 않습니다.

## 2. 기동 스크립트

[`scripts/run_gpu_ws_worker.sh`](../scripts/run_gpu_ws_worker.sh)가 재현 가능한 기동을
캡슐화합니다.

- **파이썬**: `~/r53_vllm019/bin/python` (검증된 `vllm==0.19.0` + `torch==2.10.0+cu128`,
  CUDA-12 조합이 고정된 venv). 공용 `cuda-evaluation` venv는 이 조합에 고정되어 있지
  않으므로 사용하지 않습니다.
- **`CUDA_VISIBLE_DEVICES`**: 운영 배정 장치 UUID 단일 값. 이 환경의 운영 장치는
  Device2 (`GPU-e800362c-...`) 또는 GPU0 (`GPU-76da22e2-...`) 중 실제로 배정받은 것입니다.
  `COACH_GPU_ALLOWED_DEVICES`에도 같은 값이 포함되어야 `validate_device()`를 통과합니다.
- **`COACH_GPU_LINK_MODE=ws`**, **`COACH_GPU_API_URL=wss://<ec2>:8000/internal/gpu-link`**:
  인바운드 연결이 없는 GPU 박스가 API로 아웃바운드 연결합니다(SPEC-ws-tunnel.md).
- **`COACH_GPU_MODEL=prod27_fp8`**, **`COACH_GPU_MODEL_REGISTRY=<위 JSON 경로>`**.
- **`COACH_GPU_WORKSPACE`**: `worker.token`(0600, 실행자 소유)이 있는 절대 경로.
- **`COACH_GPU_EXECUTION_BACKEND=vllm_async`** (기본값, 명시적으로 설정).

사용:

```bash
CUDA_VISIBLE_DEVICES="GPU-e800362c-..." \
COACH_GPU_ALLOWED_DEVICES="GPU-e800362c-..." \
COACH_GPU_WORKSPACE="/home/operator/gpu-workspace" \
COACH_GPU_MODEL_REGISTRY="/home/operator/gpu-workspace/gpu_model_registry.json" \
COACH_GPU_API_URL="wss://api.example.com:8000/internal/gpu-link" \
scripts/run_gpu_ws_worker.sh
```

`GPU_WORKER_MODEL_READY` 출력 후 API 쪽 `/healthz`의 `model_configured`와 워커
`/health`로 연결을 확인합니다(`docs/operations.md` "상태와 장애 확인" 절 참조).
