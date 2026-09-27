"""Linear-time check that a compacted phrase splits completely into allowed words."""

from typing import Final

_TOPIC_MARKERS: Final = ("는", "은", "도", "만")


class WordSegments:
    """Accept text that splits into ``word (particle)? (topic marker)?`` pieces.

    A scan over reachable positions, so a failing tail costs one pass. The nested
    ``(?:word(?:particle)?)+`` regex it replaces tried every split of overlapping
    words ("썼어" as one word or 썼+어) and took seconds on a 50-character message.
    """

    def __init__(self, words: tuple[str, ...], particles: tuple[str, ...]) -> None:
        self._words: tuple[str, ...] = tuple(sorted({word for word in words if word}))
        self._particles: tuple[str, ...] = tuple(particle for particle in particles if particle)

    def covers(self, text: str) -> bool:
        """Whether the whole text splits into allowed pieces."""
        if not text:
            return False
        reachable = [False] * (len(text) + 1)
        reachable[0] = True
        for start in range(len(text)):
            if not reachable[start]:
                continue
            for word in self._words:
                if not text.startswith(word, start):
                    continue
                stem = start + len(word)
                tails = [stem] + [
                    stem + len(particle) for particle in self._particles if text.startswith(particle, stem)
                ]
                for tail in tails:
                    reachable[tail] = True
                    for marker in _TOPIC_MARKERS:
                        if text.startswith(marker, tail):
                            reachable[tail + len(marker)] = True
        return reachable[len(text)]
