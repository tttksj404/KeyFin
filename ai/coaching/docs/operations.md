# 운영 설정

API와 모델 추론 프로세스는 분리합니다. API는 `uv.lock`으로 설치하고, Linux 추론 환경은 [`requirements-inference.txt`](../scripts/requirements-inference.txt)의 패키지와 CUDA가 작동하는 PyTorch를 준비합니다. 검증에 사용한 PyTorch 빌드는 `2.7.1+cu128`입니다. 드라이버·CUDA 호환성은 배치할 환경에서 확인해야 합니다.

## 추론 서버

체크포인트는 로컬에 준비합니다. 워커는 온라인에서 임의 최신 모델을 내려받지 않으며 `config.json` 해시와 등록된 모델·양자화 조합을 검사합니다. 현재 지원하는 두 조합은 다음과 같습니다.

| 워커 태그 | 모델 | 방식 | 확인한 revision |
| --- | --- | --- | --- |
| `base8` | Qwen/Qwen3-8B | BF16 | `b968826d9c46dd6066d109eabc6255188de91218` |
| `latest27_nf4` | Qwen/Qwen3.8-27B | NF4 | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |
| `prod27_fp8` | Qwen/Qwen3.8-27B-FP8 | FP8 | 배치 전 `config_sha256`을 개인 등록 파일에 실측 기입 |

개인 모델 등록 파일에는 아래 형식으로 실제 경로와 해시를 넣습니다. `revision`은 확인한 스냅샷의 40자리 commit, `config_sha256`은 그 경로의 `config.json`을 직접 계산한 64자리 해시입니다. 이 검사는 전체 가중치의 공급망 검증을 대신하지 않습니다.

```text
{"models":[{"tag":"latest27_nf4","model_id":"Qwen/Qwen3.8-27B","path":"/private/checkpoint","revision":"<40자리 commit>","config_sha256":"<64자리 sha256>","quantization":"nf4"}]}
```

실행 전에 다음 환경 변수를 설정합니다. 값은 서버별 개인 설정으로 관리합니다.

| 변수 | 값 |
| --- | --- |
| `CUDA_VISIBLE_DEVICES` | 사전에 할당받고 사용 상태를 확인한 단일 장치 식별자 |
| `COACH_GPU_ALLOWED_DEVICES` | 실행자가 사용 권한을 확인한 장치 허용 목록 |
| `COACH_GPU_WORKSPACE` | 실행자 소유의 절대 디렉터리 |
| `COACH_GPU_MODEL_REGISTRY` | 개인 모델 등록 JSON 파일의 절대 경로 |
| `COACH_GPU_MODEL` | `base8`, `latest27_nf4` 또는 `prod27_fp8` |
| `COACH_GPU_PORT` | loopback 수신 포트, 기본 `18743` |
| `COACH_GPU_BATCH_SIZE` | 기본 `0`(기존 순차 처리). `1`~`4`는 토큰 검사 분리·제한된 온라인 배치를 명시적으로 활성화 |
| `COACH_GPU_EXECUTION_BACKEND` | 기본 `vllm_async`(SPEC-latency C1). `vllm`, `transformers`로 명시 전환 가능 |

### C1 기본값 변경과 롤백

워커 실행 백엔드 기본값이 `transformers`에서 `vllm_async`로 바뀌었고, `enable_prefix_caching`을 켜서 공유 시스템 프롬프트·JSON 스키마 프리필을 재사용합니다(`scripts/gpu_registry.py`의 `vllm_decoder_options`). `max_num_seqs`도 8에서 16으로 올렸고, `max_num_batched_tokens`(8192)·`max_model_len`(9728)은 그대로 두었습니다 — 두 값은 시퀀스 1개의 프리필/디코드 토큰 예산이지 동시 시퀀스 수가 아니고, 이 서비스의 호출은 대부분 96토큰 이하라 16개 동시 요청도 그 예산 안에 들어옵니다. API 쪽 `COACHING_MODEL.max_concurrency` 기본값도 2에서 8로 올려(워커의 vllm_async 슬롯 8개와 맞춤) 실제 동시성이 엔진까지 도달하게 했습니다.

**이 변경은 코드 상 도달 가능성만 확보한 것이며, 실측 GPU A/B(E1 지연·E2 응답 JSON 동일성) 검증은 별도로 수행합니다. 이 커밋만으로 지연·정확도 개선을 주장하지 않습니다.**

문제가 생기면 아래 환경 변수로 이전 동작(코드 변경 없이)으로 되돌립니다.

| 변수 | 롤백 값 |
| --- | --- |
| `COACH_GPU_EXECUTION_BACKEND` | `transformers` |
| `COACHING_MODEL__MAX_CONCURRENCY` (또는 `COACHING_MODEL`의 `max_concurrency`) | `2` |

### FP8 27B 서빙 (`prod27_fp8`, 선택 채택)

측정 결과, L40S 1장에서 `vllm==0.19.0` + `torch==2.10.0+cu128` 조합으로 공식 `Qwen/Qwen3.8-27B-FP8`(fine-grained FP8) 체크포인트를 서빙하면 기존 `latest27_nf4`(bitsandbytes NF4) 대비 1.35배~9.1배 빠르고, 정답 선택 정확도는 히든 평가 기준 122/144로 121/144(NF4)보다 낮지 않았습니다. `scripts/gpu_registry.py`의 `vllm_decoder_options`가 `("prod27_fp8", "fp8")` 조합을 별도 분기로 처리하며, bitsandbytes 로더를 지정하지 않고 vLLM이 체크포인트 자체 설정에서 FP8(compressed-tensors) 양자화를 자동 인식하게 둡니다. `enable_prefix_caching`(True)·`max_num_seqs`(16)·greedy 결정성(`seed=715`)은 다른 태그와 동일합니다.

**서빙 환경 요건**: `vllm==0.19.0` + `torch==2.10.0+cu128`, CUDA-12 계열 드라이버(이 조합으로 실측). vLLM `0.27` 이상은 CUDA-13을 요구해 570 드라이버/CUDA-12.8 조합의 이 박스에서는 사용할 수 없습니다. 다른 드라이버·CUDA로 옮길 때는 vLLM/torch 버전 조합을 다시 확인해야 합니다.

**선택 방법**: 개인 모델 등록 파일에 `{"tag":"prod27_fp8","model_id":"Qwen/Qwen3.8-27B-FP8","quantization":"fp8", ...}` 항목을 추가하고 `COACH_GPU_MODEL=prod27_fp8`로 기동합니다. 서비스 기본 모델은 그대로 `latest27_nf4`이며, 이 태그는 선택적으로만 활성화되는 옵션입니다(자동 전환 없음). 문제가 있으면 `COACH_GPU_MODEL=latest27_nf4` 또는 `base8`로 되돌리거나 `COACH_GPU_EXECUTION_BACKEND=transformers`로 전환합니다.


작업 디렉터리에 충분히 긴 무작위 `worker.token`을 만들고 파일 권한을 `0600`으로 설정합니다. 토큰과 작업 디렉터리 소유자는 실행자와 같아야 합니다. 단일 장치 선택이 없거나 허용 목록과 다르면 시작을 거부합니다. 이 검사는 관리자의 스케줄러나 권한 통제를 대신하지 않습니다.

설정한 환경을 사용하는 Python으로 서비스 디렉터리에서 `python scripts/gpu_worker.py`를 실행합니다. `GPU_WORKER_MODEL_READY` 이후 `GET /health`로 모델·revision·한도를 확인합니다. 인증된 `POST /v1/tokenize`와 `POST /v1/chat/completions`를 제공합니다. 기본값 `0`은 기존처럼 생성 1개·대기 포함 요청 2개입니다.

배치를 켜도 GPU `generate` 호출은 한 번에 하나만 실행합니다. 같은 출력 토큰 상한의 FIFO 요청을 최대 8ms 동안 모으고, 가장 긴 입력과 출력 상한의 합에 배치 크기를 곱한 값이 16,384토큰 이하여야 합칩니다. 배치 모드의 대기 포함 요청 상한은 16개이며 포화 시 429를 반환합니다. CPU 토큰 검사는 별도 tokenizer 복사본으로 처리합니다. 입력 8,192토큰·출력 1,536토큰 상한과 프롬프트 지문 검증은 그대로입니다.

연결이 끊긴 요청은 대기열에서 취소합니다. 이미 시작한 CUDA 호출은 강제로 중단하지 않고 결과를 버리므로, 실행 중인 다른 요청을 손상시키지 않습니다. 생성 실패는 해당 배치에 503으로 반환하고 다음 배치를 처리합니다. 큰 배치가 항상 빠르지는 않으므로 실측 비교와 채택 판단을 읽고 서비스의 실제 부하로 다시 확인합니다.

## API에서 모델 연결

API 실행 환경의 `COACHING_MODEL`에 다음 JSON을 지정합니다. 주소는 같은 호스트의 loopback 또는 인증된 터널의 loopback 끝점이어야 합니다. `<worker token>`은 실제 개인 토큰을 안전하게 주입합니다.

```text
{"endpoint_url":"http://127.0.0.1:18743","token":"<worker token>","model":"latest27_nf4","token_preflight":true}
```

`COACHING_CLIENTS`는 서비스 이용 주체별 토큰 목록이고 모델 토큰과 다릅니다. `backend`·`user`·`notification` 역할과 사용자 ID를 구분합니다. 데이터베이스는 `COACHING_DATABASE`로 지정합니다. `.env`는 자동 로드하지 않으므로 환경 변수나 실행 도구의 명시적인 env 파일 기능을 사용합니다.

## 상태와 장애 확인

API `/healthz`의 `model_configured`는 설정 유무입니다. 모델 추론 성공을 보장하지 않습니다. 워커 `/health`도 프로세스·모델 적재 확인이므로 실제 요청은 [HTTP 평가](../benchmarks/coaching/e2e/README.md)로 확인합니다.

실제 모델 호출의 `wording.source`, `fallback_reason`, 토큰 측정 및 응답 시간을 함께 봅니다. 413은 입력/본문 제한, 409는 측정 후 프롬프트 변경, 429는 대기열 포화입니다. 대체 문구가 반환됐다고 수치 계산까지 실패한 것으로 해석하지 않습니다.

SQLite 파일, 토큰, 원장과 원시 응답은 `state/`, `artifacts/` 또는 저장소 밖에서 보관합니다. 재실행마다 새 실험 출력 경로를 사용하고 학습 가중치와 서버 로그를 커밋하지 않습니다. 알림 API는 전달 대기와 확인을 제공하며 실제 푸시 전송, 운영 백업, 사용자 동의 및 실제 고객 대상 평가는 서비스 연결 단계에서 검증해야 합니다.
