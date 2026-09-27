"""Presentation-only voice for user-facing text (the KeyFin coach is a cat).

The stored answer stays neutral; the API applies the voice on the way out, so a
retried or re-read answer is voiced the same way and push notifications can keep
their own plain form. The transform only rewrites a sentence's final Hangul word:
numbers, amounts, dates and bracketed figures are never touched, and it is
idempotent (a sentence that already ends in 냥 is left alone).

Korean conjugation depends on whether a stem is a verb or an adjective (붙는다 vs
좋다, 구분한다 vs 필요하다), so the rules below keep small, explicit lists of the
adjectives and copula-like stems the coach actually uses; everything else is
treated as a verb. Suggestion sentences are marked ``**…**`` by the renderer. The
app draws that as bold; surfaces that cannot (push text, the plain persona) strip
the marks.
"""

from __future__ import annotations

import re
from typing import Final, Literal

Persona = Literal["cat", "plain"]

_BASE: Final = 0xAC00
_JONG_COUNT: Final = 28
_JONG_B: Final = 17  # ㅂ
_JONG_N: Final = 4  # ㄴ
_JONG_SS: Final = 20  # ㅆ

# "X하다" adjectives: 필요합니다 → 필요하다냥, not 필요한다냥.
_HADA_ADJECTIVES: Final = frozenset(
    [
        "필요", "부족", "가능", "불가능", "충분", "불충분", "중요", "동일", "확실", "불확실",
        "유사", "비슷", "적합", "부적합", "적절", "부적절", "안전", "위험", "다양", "명확",
        "불명확", "정확", "부정확", "간단", "편리", "불편", "유리", "불리", "곤란", "분명",
        "불분명", "유효", "무효", "일정", "상당", "동등", "필수", "특별", "흔", "똑같", "조용",
        "복잡", "단순",
    ]
)
# Stems whose ㅂ니다/습니다/아요 form is an adjective or existential (→ 다냥, not ㄴ다/는다냥).
_ADJECTIVE_STEMS: Final = frozenset(
    [
        "있", "없", "같", "많", "적", "좋", "괜찮", "높", "낮", "넓", "좁", "깊", "얕", "크", "작",
        "길", "짧", "빠르", "느리", "다르", "아니", "어렵", "쉽", "가볍", "무겁", "낫", "싫", "옳",
        "늦", "이르", "가깝", "멀", "비싸", "싸", "새롭", "드물", "잦",
    ]
)
# Verbs whose stem ends in 이, so 입니다 there is a verb (움직입니다 → 움직인다냥).
_I_VERBS: Final = frozenset(
    [
        "움직이", "줄이", "보이", "높이", "늘이", "붙이", "기울이", "들이", "먹이", "속이", "쌓이",
        "모이",
    ]
)


def _jong(char: str) -> int:
    code = ord(char) - _BASE
    return code % _JONG_COUNT if 0 <= code < 11172 else -1


def _with_jong(char: str, jong: int) -> str:
    code = ord(char) - _BASE
    return chr(_BASE + code - code % _JONG_COUNT + jong)


def _declarative(stem: str) -> str:
    """Stem (no ending) → 'stem + (ㄴ)다냥', choosing adjective vs verb form."""
    if not stem:
        return "다냥"
    if stem in _ADJECTIVE_STEMS or any(stem.endswith(adj) for adj in _ADJECTIVE_STEMS if len(adj) > 1):
        return stem + "다냥"
    last = stem[-1]
    jong = _jong(last)
    if jong == _JONG_SS or last == "겠":  # past or future marker: 했다냥, 겠다냥
        return stem + "다냥"
    if jong == 0:  # open syllable verb: 주 → 준다냥, 달라지 → 달라진다냥
        return stem[:-1] + _with_jong(last, _JONG_N) + "다냥"
    return stem + "는다냥"  # closed syllable verb: 붙 → 붙는다냥


def _hada(noun: str) -> str:
    """'noun + 하다' → adjective 하다냥 or verb 한다냥."""
    head = noun.rsplit(" ", 1)[-1]
    return noun + ("하다냥" if head in _HADA_ADJECTIVES or noun in _HADA_ADJECTIVES else "한다냥")


def _statement(word: str) -> str:  # noqa: C901, PLR0911, PLR0912 - one ordered ending table.
    if word.endswith(("아닙니다", "아니에요")):
        return word[:-4] + "아니다냥"
    if word.endswith("입니다"):
        stem = word[:-3] + "이"
        if any(stem.endswith(verb) for verb in _I_VERBS):
            return word[:-3] + "인다냥"
        return word[:-3] + "이다냥"
    if word.endswith(("않습니다", "않아요")):
        return word[: -4 if word.endswith("않습니다") else -3] + "않는다냥"
    if word.endswith("합니다"):
        return _hada(word[:-3])
    if word.endswith("됩니다"):
        return word[:-3] + "된다냥"
    if word.endswith("습니다"):
        return _declarative(word[:-3])
    if word.endswith("니다") and len(word) > 2 and _jong(word[-3]) == _JONG_B:
        # ㅂ니다 after an open-syllable stem: 줍니다 → 주, 다릅니다 → 다르.
        return _declarative(word[:-3] + _with_jong(word[-3], 0))
    for suffix, replacement in (
        ("이에요", "이다냥"),
        ("예요", "다냥"),
        ("드릴게요", "주겠다냥"),
        ("볼게요", "보겠다냥"),
        ("할게요", "하겠다냥"),
        ("계세요", "계신다냥"),
        ("주세요", "달라냥"),
        ("세요", "라냥"),
        ("겠어요", "겠다냥"),
        ("돼요", "된다냥"),
    ):
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith("해요"):
        return _hada(word[:-2])
    if word.endswith(("아요", "어요")) and len(word) > 2:
        stem = word[:-2]
        if _jong(stem[-1]) == _JONG_SS or stem in _ADJECTIVE_STEMS or stem[-1] in "았었했였":
            return stem + "다냥"
        if any(stem.endswith(adj) for adj in _ADJECTIVE_STEMS):
            return stem + "다냥"
    if word.endswith("요") and len(word) > 1:
        before = word[-2]
        if _jong(before) == _JONG_SS:  # contracted past: 찼어요/왔어요 → 찼다냥
            return word[:-2] + "다냥" if word.endswith(("어요", "아요")) else word[:-1] + "다냥"
        if before == "워" and len(word) > 2:
            # ㅂ-irregular adjective (어려워요 → 어렵다냥) vs 우-verb (채워요 → 채운다냥).
            b_stem = word[:-3] + _with_jong(word[-3], _JONG_B)
            if any(b_stem.endswith(adj) for adj in _ADJECTIVE_STEMS):
                return b_stem + "다냥"
            return _declarative(word[:-2] + "우")
        if before == "혀":  # passive 히+어: 읽혀요 → 읽힌다냥
            return word[:-2] + "힌다냥"
        return word[:-1] + "냥"
    if word.endswith("다"):
        return word + "냥"
    return word


def _question(word: str) -> str:
    for suffix, replacement in (
        ("어때요", "어떠냥"),
        ("예요", "냥"),
        ("까요", "까냥"),
        ("나요", "냥"),
        ("세요", "시냥"),
        ("요", "냥"),
    ):
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    return word if word.endswith("냥") else word + "냥"


# A sentence end: the final Hangul word, an optional bracketed note, terminal
# punctuation or a line end, and an optional closing bold mark.
_SENTENCE_END: Final = re.compile(
    r"(?P<word>[가-힣]+)(?P<note>\([^()\n]*\))?(?P<punct>[.?!]+|(?=\*\*|\n|$))(?P<bold>\*\*)?(?=\s|$)"
)
_BOLD: Final = re.compile(r"\*\*")


def _voice(match: re.Match[str]) -> str:
    word, note, punct, bold = match["word"], match["note"] or "", match["punct"], match["bold"] or ""
    if word.endswith("냥"):
        return match[0]
    voiced = _question(word) if punct.startswith("?") else _statement(word)
    return voiced + note + punct + bold


def cat_voice(text: str) -> str:
    """Rewrite every sentence ending into the coach's cat voice (~다냥)."""
    return _SENTENCE_END.sub(_voice, text)


def strip_bold(text: str) -> str:
    return _BOLD.sub("", text)


def present(text: str, persona: Persona, *, bold: bool = True) -> str:
    """Voice ``text`` for a user-facing surface; drop bold marks where they cannot render."""
    voiced = cat_voice(text) if persona == "cat" else text
    return voiced if bold and persona == "cat" else strip_bold(voiced)
