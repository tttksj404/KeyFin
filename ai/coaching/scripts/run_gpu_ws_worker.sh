#!/usr/bin/env bash
# Reproducible startup for the prod27_fp8 GPU worker in COACH_GPU_LINK_MODE=ws
# (outbound WebSocket tunnel to the coaching API, SPEC-ws-tunnel.md).
#
# This script does not select values for you: fill in the placeholders below
# (or export them before calling this script) with the operator's own
# validated environment. See docs/operations.md and docs/gpu-deploy.md for
# what each value means and how it was validated.
set -euo pipefail

# --- required, per-operator values -----------------------------------------
# The pinned venv that has the validated vllm==0.19.0 + torch==2.10.0+cu128
# combination for this box. Do NOT use a shared/general cuda-evaluation venv;
# it is not pinned to the combination prod27_fp8 was measured against.
GPU_WORKER_PYTHON="${GPU_WORKER_PYTHON:-$HOME/r53_vllm019/bin/python}"

# Exactly one authorized device UUID. Operational device for prod27_fp8 is
# either Device2 (GPU-e800362c-...) or GPU0 (GPU-76da22e2-...) -- use the one
# actually assigned to this box; do not guess or fall back to an unassigned
# device.
: "${CUDA_VISIBLE_DEVICES:?set to the single assigned device UUID, e.g. GPU-e800362c-...}"
: "${COACH_GPU_ALLOWED_DEVICES:?set to the allow-list that contains CUDA_VISIBLE_DEVICES}"

# Absolute, operator-owned directory holding worker.token (0600) and where
# worker_metadata.json will be written.
: "${COACH_GPU_WORKSPACE:?set to an absolute directory you own, containing worker.token}"

# Absolute path to the private model registry JSON (see
# scripts/gpu_model_registry.example.json for the schema/template). This file
# is never committed with real revision/config_sha256 values.
: "${COACH_GPU_MODEL_REGISTRY:?set to the absolute path of your private registry JSON}"

# wss://<ec2-host>:8000/internal/gpu-link -- the coaching API's inbound tunnel
# endpoint this worker dials out to.
: "${COACH_GPU_API_URL:?set to wss://<ec2>:8000/internal/gpu-link}"

# vLLM 0.19 parses CUDA_VISIBLE_DEVICES as integer device indices and aborts
# when handed a "GPU-..." UUID. The operator pins the device by UUID (stable
# identity); this block resolves that UUID to its PCI-ordered nvidia-smi index
# and pins CUDA_DEVICE_ORDER so the index selects the same physical device.
# validate_device (gpu_registry.py) requires CUDA_VISIBLE_DEVICES to be a single
# value present in COACH_GPU_ALLOWED_DEVICES via string equality, so BOTH must
# use the same representation -- we translate both to the resolved index, after
# checking the pinned UUID is actually in the operator's declared allow-list.
if [[ "${CUDA_VISIBLE_DEVICES}" == GPU-* ]]; then
  _pinned_uuid="${CUDA_VISIBLE_DEVICES}"
  # Operator intent gate: the pinned UUID must be one the operator allow-listed.
  _allowed_hit=""
  IFS=',' read -ra _allowed_arr <<< "${COACH_GPU_ALLOWED_DEVICES}"
  for _a in "${_allowed_arr[@]}"; do
    if [[ "${_a// /}" == "${_pinned_uuid}" ]]; then _allowed_hit="yes"; break; fi
  done
  if [[ -z "${_allowed_hit}" ]]; then
    echo "error: pinned UUID ${_pinned_uuid} is not in COACH_GPU_ALLOWED_DEVICES" >&2
    exit 1
  fi
  _pinned_index="$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader,nounits \
    | awk -F', *' -v u="${_pinned_uuid}" '$2 == u { print $1; exit }')"
  if [[ -z "${_pinned_index}" ]]; then
    echo "error: device UUID ${_pinned_uuid} not found by nvidia-smi" >&2
    exit 1
  fi
  export CUDA_DEVICE_ORDER="PCI_BUS_ID"
  # Translate BOTH the visible device and the allow-list to the resolved index so
  # vLLM gets an int and validate_device's equality check still passes.
  CUDA_VISIBLE_DEVICES="${_pinned_index}"
  COACH_GPU_ALLOWED_DEVICES="${_pinned_index}"
  echo "  resolved device:    ${_pinned_uuid} -> index ${_pinned_index} (PCI_BUS_ID)" >&2
fi

# --- fixed for this deployment (prod27_fp8 ws worker) ----------------------
export CUDA_VISIBLE_DEVICES
export COACH_GPU_ALLOWED_DEVICES
export COACH_GPU_WORKSPACE
export COACH_GPU_MODEL_REGISTRY
export COACH_GPU_API_URL
export COACH_GPU_LINK_MODE="ws"
export COACH_GPU_MODEL="prod27_fp8"
export COACH_GPU_EXECUTION_BACKEND="${COACH_GPU_EXECUTION_BACKEND:-vllm_async}"

echo "Starting prod27_fp8 GPU ws worker" >&2
echo "  python:            ${GPU_WORKER_PYTHON}" >&2
echo "  device:             ${CUDA_VISIBLE_DEVICES}" >&2
echo "  workspace:          ${COACH_GPU_WORKSPACE}" >&2
echo "  registry:           ${COACH_GPU_MODEL_REGISTRY}" >&2
echo "  api url:            ${COACH_GPU_API_URL}" >&2
echo "  execution backend:  ${COACH_GPU_EXECUTION_BACKEND}" >&2

exec "${GPU_WORKER_PYTHON}" "$(dirname "$0")/gpu_worker.py"
