import random
from dataclasses import dataclass
from . import __doc__
from .. import repo


class NoCarrierSentence(Exception):
    pass


@dataclass(slots=True)
class Question:
    item_id: int
    facet: str
    headword: str
    choices: list[str]
    correct: str
    pinyin: str
    target_gloss: str
    sentence_id: int
    sentence_zh: str
    sentence_pinyin: str
    sentence_en: str
    audio_path: str | None
    reveal_zh: bool


def meaning_choices(conn, item, count=4) -> list[str]:
    rows = conn.execute(
        "SELECT gloss FROM item WHERE id<>? AND gloss<>'' ORDER BY RANDOM() LIMIT ?",
        (item.id, count * 3),
    ).fetchall()
    choices = [item.gloss]
    for row in rows:
        if row["gloss"] not in choices:
            choices.append(row["gloss"])
        if len(choices) == count:
            break
    random.shuffle(choices)
    return choices


def build_question(conn, item_id: int, facet: str) -> Question:
    item = repo.get_item(conn, item_id)
    sentence = repo.get_sentence_for_item(conn, item_id)
    if not item or not sentence:
        raise NoCarrierSentence(item_id)
    return Question(
        item_id=item.id, facet=facet, headword=item.headword,
        choices=meaning_choices(conn, item), correct=item.gloss, pinyin=item.pinyin,
        target_gloss=item.gloss, sentence_id=sentence.id, sentence_zh=sentence.zh,
        sentence_pinyin=sentence.pinyin, sentence_en=sentence.en,
        audio_path=sentence.audio_path, reveal_zh=facet == "reading-recognition",
    )
