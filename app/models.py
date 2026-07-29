from dataclasses import dataclass


@dataclass(slots=True)
class Item:
    id: int
    kind: str
    headword: str
    pinyin: str
    gloss: str
    freq_rank: int | None = None
    hsk_bands: str = ""
    measure_word: str = ""


@dataclass(slots=True)
class Sentence:
    id: int
    zh: str
    pinyin: str
    en: str
    audio_path: str | None = None
    source: str = ""
    validated: int = 0


@dataclass(slots=True)
class MemoryState:
    user_id: int
    item_id: int
    facet: str
    difficulty: float | None
    stability: float | None
    last_review_ts: str | None
    due_ts: str
    lapses: int
    suspended: int
    card_json: str
