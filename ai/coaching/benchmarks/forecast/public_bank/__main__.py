"""Separate preparation, development selection and final evaluation commands."""

import sys
from pathlib import Path

from .prepare import prepare


def main() -> None:
    arguments = sys.argv[1:]
    if len(arguments) != 3:
        raise SystemExit("Usage: python -m benchmarks.forecast.public_bank prepare SOURCE OUTPUT")
    if arguments[0] != "prepare":
        raise SystemExit("Supported command: prepare")
    prepare(Path(arguments[1]), Path(arguments[2]))


if __name__ == "__main__":
    main()
