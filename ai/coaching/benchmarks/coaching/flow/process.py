"""Own only API subprocesses created here; the inference worker is never restarted."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import final

import httpx2
from pydantic import TypeAdapter

from benchmarks.coaching.flow.contracts import Backend


def free_loopback_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return TypeAdapter(tuple[str, int]).validate_python(probe.getsockname())[1]


@final
class OwnedApi:
    def __init__(
        self,
        output: Path,
        backend: Backend,
        environment: dict[str, str],
        *,
        fake_factory: str = "benchmarks.coaching.flow.fake:from_environment",
    ) -> None:
        self.output: Path = output
        self.environment: dict[str, str] = environment
        self.backend: Backend = backend
        self.fake_factory: str = fake_factory
        self.port: int = free_loopback_port()
        self.process: subprocess.Popen[bytes] | None = None
        self.generation: int = 0

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> int:
        if self.process is not None:
            raise RuntimeError("owned_api_already_running")
        factory = self.fake_factory if self.backend == "fake" else "coaching_service.api:from_environment"
        self.generation += 1
        with (self.output / f"api-{self.generation}.log").open("xb") as log:
            self.process = subprocess.Popen(  # noqa: S603 - executable and arguments are fixed.
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    factory,
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self.port),
                    "--no-access-log",
                ],
                cwd=Path.cwd(),
                env=self.environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        deadline = time.monotonic() + 25
        with httpx2.Client(timeout=1, trust_env=False) as client:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError("owned_api_start_failed")
                try:
                    response = client.get(self.origin + "/healthz")
                    if response.status_code == 200:
                        return self.process.pid
                except httpx2.TransportError:
                    pass
                time.sleep(0.1)
        raise RuntimeError("owned_api_start_timeout")

    def stop(self) -> int:
        if self.process is None:
            return 0
        process = self.process
        if process.poll() is None:
            process.terminate()
        try:
            result = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            result = process.wait(timeout=5)
        self.process = None
        return result
