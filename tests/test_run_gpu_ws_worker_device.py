"""run_gpu_ws_worker.sh의 UUID->인덱스 변환 회귀 핀.

vLLM 0.19는 CUDA_VISIBLE_DEVICES를 정수로 파싱하므로 스크립트가 운영자가 지정한
장치 UUID를 nvidia-smi 인덱스로 바꿔야 한다. 그런데 validate_device(gpu_registry)는
CUDA_VISIBLE_DEVICES가 COACH_GPU_ALLOWED_DEVICES에 문자열로 그대로 있어야 통과한다.
따라서 두 변수가 같은 표현(인덱스)으로 함께 바뀌어야 워커가 기동한다. 이 테스트는
실제 스크립트를 mock nvidia-smi + 스텁 파이썬으로 끝까지 실행해 그 불변을 검증한다.
"""

import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_gpu_ws_worker.sh"
_UUID = "GPU-e800362c-2a5a-0208-8d32-28107bca6017"
_EXPECTED_INDEX = "2"


def test_branch_rewrites_both_device_vars_to_index() -> None:
    """이식 가능한 구조 핀: UUID 분기에서 두 장치 변수가 함께 인덱스로 재작성돼야 한다.

    최초 버그는 CUDA_VISIBLE_DEVICES만 인덱스로 바꾸고 COACH_GPU_ALLOWED_DEVICES는
    UUID로 남겨 validate_device 동등성 검사가 항상 실패한 것이었다. 이 테스트는 두
    재작성이 모두 존재하는지 스크립트 본문에서 직접 확인한다(OS 비의존).
    """
    text = _SCRIPT.read_text(encoding="utf-8")
    branch = text.split("== GPU-*", 1)[1]
    assert 'CUDA_VISIBLE_DEVICES="${_pinned_index}"' in branch
    assert 'COACH_GPU_ALLOWED_DEVICES="${_pinned_index}"' in branch
    assert 'export CUDA_DEVICE_ORDER="PCI_BUS_ID"' in branch


# 실제 스크립트 실행 검증은 posix + bash에서만. Windows 개발 박스는 비ASCII 경로/
# cp949 디코딩으로 subprocess 텍스트 캡처가 불안정하므로 skip(리눅스 CI에서 수행).
_run_marks = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="posix bash only",
)


def _make_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run(tmp_path: Path, *, allowed: str) -> subprocess.CompletedProcess[str]:
    # mock nvidia-smi: index 2 owns the pinned UUID.
    _make_exe(
        tmp_path / "nvidia-smi",
        "#!/usr/bin/env bash\n"
        f'echo "0, GPU-76da22e2-40da-ebc0-098a-fa92ba030976"\n'
        f'echo "{_EXPECTED_INDEX}, {_UUID}"\n',
    )
    # stub worker python: exec replaces the process, so it inherits the exported
    # env the script produced -- print the two device vars back out.
    stub_py = tmp_path / "stub_python"
    _make_exe(
        stub_py,
        "#!/usr/bin/env bash\n"
        'echo "CVD=${CUDA_VISIBLE_DEVICES}"\n'
        'echo "ALLOWED=${COACH_GPU_ALLOWED_DEVICES}"\n'
        'echo "ORDER=${CUDA_DEVICE_ORDER:-}"\n',
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "worker.token").write_text("t", encoding="utf-8")
    env = {
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "GPU_WORKER_PYTHON": str(stub_py),
        "CUDA_VISIBLE_DEVICES": _UUID,
        "COACH_GPU_ALLOWED_DEVICES": allowed,
        "COACH_GPU_WORKSPACE": str(workspace),
        "COACH_GPU_MODEL_REGISTRY": str(tmp_path / "registry.json"),
        "COACH_GPU_API_URL": "wss://example.invalid:8000/internal/gpu-link",
    }
    cmd = ["bash", str(_SCRIPT)]
    return subprocess.run(  # noqa: S603 -- bash from PATH, fixed script, isolated env.
        cmd, env=env, capture_output=True, text=True, timeout=30, check=False
    )


@_run_marks
def test_uuid_visible_and_allow_list_are_rewritten_to_same_index(tmp_path: Path) -> None:
    result = _run(tmp_path, allowed=_UUID)
    assert result.returncode == 0, result.stderr
    assert f"CVD={_EXPECTED_INDEX}" in result.stdout
    assert f"ALLOWED={_EXPECTED_INDEX}" in result.stdout
    # validate_device equality invariant: both sides must match exactly.
    cvd = next(line for line in result.stdout.splitlines() if line.startswith("CVD="))
    allowed = next(line for line in result.stdout.splitlines() if line.startswith("ALLOWED="))
    assert cvd.split("=", 1)[1] == allowed.split("=", 1)[1]
    assert "ORDER=PCI_BUS_ID" in result.stdout


@_run_marks
def test_pinned_uuid_not_in_allow_list_aborts(tmp_path: Path) -> None:
    result = _run(tmp_path, allowed="GPU-ffffffff-0000-0000-0000-000000000000")
    assert result.returncode != 0
    assert "not in COACH_GPU_ALLOWED_DEVICES" in result.stderr
