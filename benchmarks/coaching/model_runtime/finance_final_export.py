"""Export the frozen post-selection finance fact-selection validation partition."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from benchmarks.coaching.model_runtime.export import safe_output
from benchmarks.coaching.model_runtime.finance_selection_export import manifest as partition_manifest

if TYPE_CHECKING:
    from coaching_service.llm_prompt import FinancePromptVersion


def manifest(*, finance_prompt_version: FinancePromptVersion = "production") -> dict[str, object]:
    """Return final cases that must not inform prompt or model candidate selection."""
    return partition_manifest("final", finance_prompt_version=finance_prompt_version)


def write_manifest(
    path: Path, *, finance_prompt_version: FinancePromptVersion = "production"
) -> dict[str, object]:
    """Write a canonical ignored runtime artifact with its digest."""
    serialized = json.dumps(
        manifest(finance_prompt_version=finance_prompt_version), ensure_ascii=False, separators=(",", ":")
    )
    destination = safe_output(path)
    destination.write_text(serialized, encoding="utf-8")
    return {"path": str(destination), "sha256": hashlib.sha256(serialized.encode()).hexdigest(), "cases": 24}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--output", required=True, type=Path)
    _ = parser.add_argument(
        "--finance-prompt-version", choices=("production", "candidate_v2"), default="production"
    )
    arguments = parser.parse_args()
    print(  # noqa: T201
        json.dumps(
            write_manifest(arguments.output, finance_prompt_version=arguments.finance_prompt_version),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
