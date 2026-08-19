"""Export the public curriculum used by the hosted Hanlu application."""

import hashlib
import json
from pathlib import Path

from app.config import DB_PATH
from app.content import sentence_pinyin
from app.db import connect
from app.grammar_curriculum import RECOMMENDED_EARLY


OUTPUT = Path(__file__).resolve().parents[1] / "hosted" / "app" / "hanlu-data.json"


def audio_name(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24] + ".mp3"


def words_in_text(text: str, lexicon: dict[str, dict]) -> list[dict]:
    """Match the longest tracked word at each position, as the local reader does."""
    ordered = sorted(lexicon, key=lambda word: (-len(word), word))
    result: list[dict] = []
    seen: set[int] = set()
    index = 0
    while index < len(text):
        match = next((word for word in ordered if text.startswith(word, index)), None)
        if not match:
            index += 1
            continue
        item = lexicon[match]
        if item["id"] not in seen:
            seen.add(item["id"])
            result.append({
                "id": item["id"],
                "hanzi": item["hanzi"],
                "pinyin": item["pinyin"],
                "meaning": item["meaning"],
                "hsk": item["hsk"],
            })
        index += len(match)
    return result


def main() -> None:
    conn = connect(DB_PATH)
    topics_by_item: dict[int, list[str]] = {}
    for row in conn.execute("SELECT item_id,topic FROM item_topic ORDER BY topic"):
        topics_by_item.setdefault(row["item_id"], []).append(row["topic"])

    words = []
    for row in conn.execute(
        "SELECT id,headword,pinyin,gloss,hsk_bands,measure_word FROM item "
        "WHERE kind='word' ORDER BY CAST(hsk_bands AS INTEGER),freq_rank,headword"
    ):
        levels = sorted(
            int(value) for value in row["hsk_bands"].split(",") if value.isdigit()
        )
        words.append({
            "id": row["id"],
            "hanzi": row["headword"],
            "pinyin": row["pinyin"],
            "meaning": row["gloss"],
            "hsk": min(levels, default=0),
            "hskLevels": levels,
            "topics": topics_by_item.get(row["id"], []),
            "measureWord": row["measure_word"],
            "audio": audio_name(row["headword"]),
        })
    lexicon = {word["hanzi"]: word for word in words}
    stories = [
        {
            "id": row["id"],
            "titleZh": row["title_zh"],
            "titleEn": row["title_en"],
            "hskLevel": row["hsk_level"],
            "sentences": [
                {
                    "zh": sentence["zh"],
                    "pinyin": sentence.get("py", ""),
                    "en": sentence["en"],
                    "audio": audio_name(sentence["zh"]),
                    "words": words_in_text(sentence["zh"], lexicon),
                }
                for sentence in json.loads(row["sentences_json"])
            ],
        }
        for row in conn.execute(
            "SELECT id,title_zh,title_en,hsk_level,sentences_json FROM story "
            "ORDER BY hsk_level,id"
        )
    ]
    grammar = [
        {
            "id": row["id"],
            "level": row["level"],
            "titleZh": row["title_zh"],
            "titleEn": row["title_en"],
            "pattern": row["pattern"],
            "explanation": row["explanation"],
            "recommendedEarly": row["title_zh"] in RECOMMENDED_EARLY,
            "examples": [
                {
                    "zh": example["zh"],
                    "pinyin": sentence_pinyin(example["zh"]),
                    "en": example["en"],
                    "audio": audio_name(example["zh"]),
                }
                for example in json.loads(row["theory_examples_json"] or "[]")[:5]
            ],
            "practiceExamples": [
                {
                    "zh": example["zh"],
                    "pinyin": sentence_pinyin(example["zh"]),
                    "en": example["en"],
                    "audio": audio_name(example["zh"]),
                    "source": example.get("source", ""),
                }
                for example in json.loads(row["practice_examples_json"] or "[]")[:10]
            ],
        }
        for row in conn.execute(
            "SELECT id,level,title_zh,title_en,pattern,explanation,"
            "theory_examples_json,practice_examples_json FROM grammar_point ORDER BY level,id"
        )
    ]
    payload = {"words": words, "stories": stories, "grammar": grammar}
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    conn.close()
    print(
        f"Exported {len(words)} words, {len(stories)} stories, "
        f"and {len(grammar)} grammar lessons to {OUTPUT}."
    )


if __name__ == "__main__":
    main()
