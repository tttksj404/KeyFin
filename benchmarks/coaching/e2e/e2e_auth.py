"""Read a bounded local worker credential without placing it in experiment artifacts."""

import os
import stat

from pydantic import SecretStr

from benchmarks.coaching.e2e.e2e_contracts import RunConfig


def worker_token(config: RunConfig) -> SecretStr | None:
    if config.backend == "fake":
        return None
    if config.upstream_token_file is None:
        raise ValueError("GPU backend requires an upstream token file")
    with config.upstream_token_file.open("rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Worker credential must be a regular file")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise ValueError("Worker credential must not be accessible to group or others")
        data = stream.read(8193)
    if not data or len(data) > 8192:
        raise ValueError("Worker credential file has an invalid length")
    try:
        value = data.decode("ascii").rstrip("\r\n")
    except UnicodeDecodeError:
        raise ValueError("Worker credential must contain ASCII header characters") from None
    if not value or not all(33 <= ord(character) <= 126 for character in value):
        raise ValueError("Worker credential contains invalid header characters")
    return SecretStr(value)
