"""Build the next synthetic-only adapter input without reusing a final screen."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from benchmarks.coaching.model_runtime.finance_post_tuning_final import cases as r37_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r38 import cases as r38_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r39 import cases as r39_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r40 import cases as r40_cases
from benchmarks.coaching.model_runtime.finance_post_tuning_final_r41 import cases as r41_cases
from benchmarks.coaching.model_runtime.finance_sft_dataset import SftExample
from benchmarks.coaching.model_runtime.finance_sft_dataset import build_examples as build_base_examples
from coaching_service.knowledge_retrieval import compact

if TYPE_CHECKING:
    from pathlib import Path


def excluded_holdout_questions() -> frozenset[str]:
    """Return only static synthetic holdout normalizations, never customer data."""
    return frozenset(
        compact(case.question)
        for case in (*r37_cases(), *r38_cases(), *r39_cases(), *r40_cases(), *r41_cases())
    )


@cache
def build_examples() -> tuple[SftExample, ...]:
    """Build r42 training data with all post-tuning final prompts excluded."""
    # The returned tuple is immutable.  Multiple final-gate checks import it in
    # one process, so caching avoids rebuilding an identical synthetic corpus.
    return build_base_examples(extra_excluded_questions=excluded_holdout_questions())


def write_jsonl(path: Path) -> int:
    """Write an ignored synthetic-only r42 training artifact."""
    examples = build_examples()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(row.json_line() for row in examples) + "\n", encoding="utf-8")
    return len(examples)
