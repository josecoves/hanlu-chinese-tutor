import json
from functools import lru_cache
from urllib.parse import quote

from . import config
from .content import LOW_PRIORITY_SENSE_MARKERS, preferred_form


WORD_NOTES = {
    "开学": (
        "The everyday meaning is that school or a new term begins. "
        "The older “foundation of a university” sense is not the useful meaning here."
    ),
    "院": (
        "院 is often a bound part of a longer word: 医院 means hospital, "
        "学院 means college, and 院子 means courtyard."
    ),
    "桌子": (
        "桌子 and 桌 both mean “table.” 桌 is especially common before a "
        "position word: 桌上 and 桌子上 are both natural."
    ),
}

ALTERNATIVES = {
    "桌子": ["桌"],
    "桌": ["桌子"],
    "这里": ["这儿"],
    "那里": ["那儿"],
    "哪里": ["哪儿"],
}


@lru_cache(maxsize=1)
def _entries() -> dict:
    return {row["s"]: row for row in json.loads(config.HSK_PATH.read_text())}


def _ordered_senses(senses: list[str]) -> list[str]:
    values = []
    for sense in senses:
        value = sense.strip()
        if value and value not in values:
            values.append(value)
    return sorted(values, key=lambda value: (
        int(any(marker in value.lower() for marker in LOW_PRIORITY_SENSE_MARKERS)),
        values.index(value),
    ))


def word_details(conn, item_id: int, current_sentence_id: int | None = None) -> dict:
    item = conn.execute(
        "SELECT id,headword,pinyin,gloss,hsk_bands,measure_word FROM item WHERE id=?",
        (item_id,),
    ).fetchone()
    if not item:
        return {}
    row = _entries().get(item["headword"], {})
    form = preferred_form(row, item["headword"]) if row else {}
    examples = [dict(example) for example in conn.execute(
        "SELECT DISTINCT s.zh,s.pinyin,s.en FROM sentence s "
        "JOIN sentence_token st ON st.sentence_id=s.id "
        "WHERE st.item_id=? AND s.source<>'generated practice carrier' "
        "ORDER BY CASE WHEN s.id=? THEN 0 ELSE 1 END,s.validated DESC,s.id LIMIT 4",
        (item_id, current_sentence_id or -1),
    )]
    return {
        **dict(item),
        "senses": _ordered_senses(form.get("m") or [item["gloss"]]),
        "note": WORD_NOTES.get(item["headword"], ""),
        "alternatives": ALTERNATIVES.get(item["headword"], []),
        "examples": examples,
        "dictionary_url": (
            "https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb="
            + quote(item["headword"])
        ),
    }
