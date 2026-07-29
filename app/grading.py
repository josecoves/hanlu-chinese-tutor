from .config import LEECH_LAPSES


def rating_for(correct: bool, latency_ms: int, hints_used: int = 0) -> int:
    if not correct:
        return 1
    if hints_used or latency_ms > 9000:
        return 2
    if latency_ms < 2500:
        return 4
    return 3


def is_leech(lapses: int) -> bool:
    return lapses >= LEECH_LAPSES
