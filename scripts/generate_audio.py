import argparse
import asyncio
import json
import edge_tts
from app.config import AUDIO_DIR, DB_PATH
from app.db import connect
from app.tts import audio_name


async def create_one(text: str, semaphore: asyncio.Semaphore):
    name = audio_name(text)
    path = AUDIO_DIR / name
    if path.exists():
        return name
    async with semaphore:
        try:
            await edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural").save(str(path))
            return name
        except Exception:
            return None


async def generate(texts: list[str]):
    semaphore = asyncio.Semaphore(6)
    return await asyncio.gather(*(create_one(text, semaphore) for text in texts))


def unique_texts(texts):
    return list(dict.fromkeys(text.strip() for text in texts if text and text.strip()))


def main():
    parser = argparse.ArgumentParser(description="Cache Mandarin audio for offline use")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Cache every practice sentence, story sentence, grammar example, and word",
    )
    args = parser.parse_args()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect(DB_PATH)
    limit = 100000 if args.all else max(0, args.limit)
    candidate_rows = conn.execute(
        "SELECT DISTINCT s.id,s.zh,s.audio_path FROM sentence s "
        "LEFT JOIN sentence_token st ON st.sentence_id=s.id "
        "LEFT JOIN memory_state ms ON ms.item_id=st.item_id AND ms.user_id=1 "
        "ORDER BY ms.due_ts IS NULL,ms.due_ts"
    ).fetchall()
    rows = [
        row for row in candidate_rows
        if row["audio_path"] != audio_name(row["zh"])
    ][:limit]
    practice_texts = unique_texts(row["zh"] for row in rows)
    stories = conn.execute("SELECT id,sentences_json FROM story").fetchall()
    story_texts = unique_texts(
        sentence["zh"]
        for row in stories
        for sentence in json.loads(row["sentences_json"])
        if not sentence.get("audio")
    )
    grammar_texts = []
    vocabulary_texts = []
    if args.all:
        grammar_rows = conn.execute(
            "SELECT examples_json,theory_examples_json,practice_examples_json "
            "FROM grammar_point"
        ).fetchall()
        grammar_texts = unique_texts(
            example.get("zh")
            for row in grammar_rows
            for column in (
                "examples_json",
                "theory_examples_json",
                "practice_examples_json",
            )
            for example in json.loads(row[column] or "[]")
        )
        vocabulary_texts = unique_texts(
            row["headword"] for row in conn.execute("SELECT headword FROM item")
        )

    texts = unique_texts(
        [*practice_texts, *story_texts, *grammar_texts, *vocabulary_texts]
    )
    print(
        f"Preparing {len(texts)} unique clips "
        f"({len(practice_texts)} practice, {len(story_texts)} story, "
        f"{len(grammar_texts)} grammar, {len(vocabulary_texts)} vocabulary).",
        flush=True,
    )
    results = asyncio.run(generate(texts))
    audio_by_text = dict(zip(texts, results))
    made = 0
    for row in rows:
        name = audio_by_text.get(row["zh"])
        if name:
            conn.execute("UPDATE sentence SET audio_path=? WHERE id=?", (name, row["id"]))
            made += 1
    linked_stories = 0
    for row in stories:
        content = json.loads(row["sentences_json"])
        for sentence in content:
            if not sentence.get("audio"):
                sentence["audio"] = audio_by_text.get(sentence["zh"])
                linked_stories += bool(sentence["audio"])
        conn.execute("UPDATE story SET sentences_json=? WHERE id=?",
                     (json.dumps(content, ensure_ascii=False), row["id"]))
    conn.commit()
    conn.close()
    failed = sum(name is None for name in results)
    print(
        f"Linked {made} practice clips and {linked_stories} story clips. "
        f"Cache now covers the requested library; {failed} downloads failed."
    )


if __name__ == "__main__":
    main()
