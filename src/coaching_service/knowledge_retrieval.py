"""Bounded retrieval of approved concepts, separate from model selection.

Aliases describe subjects, never fixed benchmark answers. Explicit current-question
terms outrank prior context; only an anaphoric follow-up may reuse the last user topic.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from functools import lru_cache
from math import log
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from coaching_service.knowledge_catalog import KnowledgeCatalog, KnowledgeFact, load_catalog

if TYPE_CHECKING:
    from collections.abc import Sequence

    from coaching_service.llm_contract import ChatMessage

_FOLLOWUP = re.compile(
    r"(?:(?:그럼|그러면)\s*)?(?:(?:그거|그것|이것)(?:은|는)?\s*)?"
    r"(?:(?:좀|조금)\s*)?(?:더\s*)?(?:(?:자세히|자세하게|상세히)\s*)?"
    r"(?:설명해\s*(?:줘|주세요)|알려\s*(?:줘|주세요)|차이는|장단점은)[?!.]*"
)
_ANAPHORIC = re.compile(
    r"(?:(?:그럼|그러면)\s*)?(?:그것|그거|그건|그게|그걸|이것|이거|이건|이게|이걸)"
    r"(?:은|는|을|를|이|가)?(?:\s|[?!.]|$)"
)
_TOPIC_CHANGE = re.compile(r"(?:말고|대신|제외하고|빼고)")


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", unicodedata.normalize("NFKC", text).lower())


def is_followup(question: str) -> bool:
    text = question.strip()
    if _TOPIC_CHANGE.search(text):
        return False
    return _FOLLOWUP.fullmatch(text) is not None or _ANAPHORIC.match(text) is not None


def active_question(question: str) -> str:
    """Remove explicit excluded clauses without discarding earlier questions.

    Apply this to stored questions as well as the current turn. Otherwise a
    later follow-up would revive a topic the user had explicitly replaced.
    """
    clauses = re.split(r"[.!?\n]+", question)
    return " ".join(_TOPIC_CHANGE.split(clause)[-1].strip() for clause in clauses).strip()


def term_score(question: str, fact: KnowledgeFact) -> int:
    normalized = compact(question)
    # Long subject names carry more information than a short generic word.
    return sum(min(len(term), 12) for alias in fact.aliases if (term := compact(alias)) in normalized)


def _grams(text: str) -> Counter[str]:
    """Return normalized character bigrams used by the bounded body index."""
    normalized = compact(text)
    return Counter(normalized[index:index + 2] for index in range(len(normalized) - 1))


@lru_cache(maxsize=32)
def _body_index(
    facts: tuple[KnowledgeFact, ...],
) -> tuple[tuple[Counter[str], ...], Counter[str], float]:
    """Build immutable catalog statistics once per reviewed fact tuple.

    A user question changes on every request, but the approved catalog normally
    does not.  Caching only the catalog-derived document grams, frequencies, and
    mean length preserves the exact BM25-like score while removing repeated
    parsing from the interactive path.
    """
    documents = tuple(_grams(fact.title + " " + fact.text) for fact in facts)
    frequencies = Counter(term for document in documents for term in document)
    mean_length = sum(sum(document.values()) for document in documents) / max(1, len(documents))
    return documents, frequencies, mean_length


def body_scores(question: str, facts: Sequence[KnowledgeFact]) -> list[float]:
    """Recall paraphrases from approved text without enumerating test questions.

    Character bigrams tolerate Korean particles and word spacing. BM25 discounts
    common fragments and long paragraphs; at least two shared fragments are
    required. These scores propose evidence only, never certify an answer.
    """
    query = _grams(question)
    documents, frequencies, mean_length = _body_index(tuple(facts))
    scores: list[float] = []
    for document in documents:
        shared = query.keys() & document.keys()
        score = 0.0
        if len(shared) >= 2:
            length = sum(document.values())
            for term in sorted(shared):
                frequency = document[term]
                inverse = log(1 + (len(documents) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
                score += inverse * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / mean_length))
        scores.append(score)
    return scores


def explicit_subjects(question: str, facts: tuple[KnowledgeFact, ...]) -> tuple[str, ...]:
    """Guard clearly enumerated named subjects; this is not a semantic oracle.

    Only explicit all-subject requests activate the guard. Longer subject spans
    dominate nested ones (ETF fees does not additionally require an ETF definition).
    Short generic words such as interest or principal cannot demand a loan answer.
    """
    enumeration = re.search(r"각각|둘\s*다|모두", question)
    if enumeration is None:
        return ()
    # Require only the named list before the quantifier. Later explanatory
    # modifiers ("원리금 관점에서") and excluded introductory topics are not
    # additional questions. Ambiguous grammar remains the selector's job.
    subject_clause = active_question(question[:enumeration.start()])
    normalized = compact(subject_clause)
    matches: list[tuple[int, int, str]] = []
    for fact in facts:
        for alias in fact.aliases:
            term = compact(alias)
            if len(term) < 3 and term != compact(fact.title):
                continue
            for match in re.finditer(re.escape(term), normalized):
                suffix = normalized[match.end():]
                if re.match(r"의(?!뜻|의미|차이|특징|장단점)|(?:관점|기준|예시)", suffix):
                    continue
                matches.append((match.start(), match.end(), fact.id))
    subjects = tuple(dict.fromkeys(
        key for start, end, key in matches
        if not any(other_start <= start and end <= other_end and (other_start, other_end) != (start, end)
                   for other_start, other_end, _ in matches)
    ))
    return subjects if len(subjects) > 1 else ()


def retrieve_facts(
    question: str,
    history: tuple[ChatMessage, ...] = (),
    *,
    catalog: KnowledgeCatalog | None = None,
    today: date | None = None,
) -> tuple[KnowledgeFact, ...]:
    """Retrieve current records, with bounded semantic selection for small catalogs.

    Explicit subjects use eight candidates. When no alias matches but approved
    text has some overlap, a catalog of at most 32 facts can be shown in full:
    Korean paraphrases may share few character pairs with the relevant concept.
    This preserves recall without inventing a question-specific synonym list.
    The selector and actual token preflight still decide support and admission.
    """
    current = catalog or load_catalog()
    on_date = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    eligible = [fact for fact in current.facts if fact.reviewed_on <= on_date <= fact.review_due]
    # A new subject following "그거 말고" must be searched on its own even when
    # there is no stored conversation; never retain the excluded topic.
    query = active_question(question)
    if is_followup(question):
        previous = next((
            row.content for row in reversed(history) if row.role == "user" and not is_followup(row.content)
        ), "")
        if not previous:
            return ()
        # A pure request for more detail contributes no new search subject.
        previous = active_question(previous)
        query = previous if _FOLLOWUP.fullmatch(question.strip()) else previous + " " + query
    # The body index also recalls the prior concept when a substantive follow-up
    # uses generic words which match a different record's alias (e.g. interest).
    similarities = body_scores(query, eligible)
    ranked = [
        (term_score(query, fact) * 10 + similarities[index], index, fact)
        for index, fact in enumerate(eligible)
    ]
    ranked.sort(key=lambda row: (-row[0], row[1]))
    if (
        0 < len(eligible) <= 32 and any(similarities)
        and not any(term_score(query, fact) for fact in eligible)
    ):
        return tuple(fact for _, _, fact in ranked)
    return tuple(fact for score, _, fact in ranked[:8] if score > 0)
