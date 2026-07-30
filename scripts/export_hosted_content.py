"""Export public curriculum content for the hosted, read-only beta."""

import json
from pathlib import Path

from app.config import DB_PATH
from app.db import connect
from app.grammar_curriculum import RECOMMENDED_EARLY


OUTPUT = Path(__file__).resolve().parents[1] / "hosted" / "app" / "hanlu-data.json"


def main() -> None:
    conn = connect(DB_PATH)
    topics_by_item: dict[int, list[str]] = {}
    for row in conn.execute("SELECT item_id,topic FROM item_topic ORDER BY topic"):
        topics_by_item.setdefault(row["item_id"], []).append(row["topic"])

    words = [
        {
            "id": row["id"],
            "hanzi": row["headword"],
            "pinyin": row["pinyin"],
            "meaning": row["gloss"],
            "hsk": int(row["hsk_bands"] or 0),
            "topics": topics_by_item.get(row["id"], []),
        }
        for row in conn.execute(
            "SELECT id,headword,pinyin,gloss,hsk_bands FROM item "
            "WHERE kind='word' ORDER BY CAST(hsk_bands AS INTEGER),freq_rank,headword"
        )
    ]
    stories = [
        {
            "id": row["id"],
            "titleZh": row["title_zh"],
            "titleEn": row["title_en"],
            "sentences": [
                {
                    "zh": sentence["zh"],
                    "pinyin": sentence.get("py", ""),
                    "en": sentence["en"],
                }
                for sentence in json.loads(row["sentences_json"])
            ],
        }
        for row in conn.execute(
            "SELECT id,title_zh,title_en,sentences_json FROM story ORDER BY id"
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
                    "en": example["en"],
                }
                for example in json.loads(row["theory_examples_json"] or "[]")[:5]
            ],
        }
        for row in conn.execute(
            "SELECT id,level,title_zh,title_en,pattern,explanation,"
            "theory_examples_json FROM grammar_point ORDER BY level,id"
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
