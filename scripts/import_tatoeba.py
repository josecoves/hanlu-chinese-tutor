"""Import short, well-covered Mandarin/English sentence pairs from Tatoeba."""
import bz2
import json
import re
from collections import defaultdict
from pathlib import Path
import httpx
from app import config
from app.content import sentence_pinyin
from app.db import connect
from app.segment import segment

BASE = "https://downloads.tatoeba.org/exports/per_language"
FILES = {
    "cmn": f"{BASE}/cmn/cmn_sentences.tsv.bz2",
    "links": f"{BASE}/cmn/cmn-eng_links.tsv.bz2",
    "eng": f"{BASE}/eng/eng_sentences.tsv.bz2",
}

FALLBACK_SENTENCES = {
    "奶": ("妹妹每天早上喝一杯奶。", "My younger sister drinks a cup of milk every morning."),
    "妹": ("我妹今年上中学。", "My younger sister is in middle school this year."),
    "姐": ("我姐周末带我去买衣服。", "My older sister takes me clothes shopping on weekends."),
    "老年": ("奶奶到了老年，还是很健康。", "My grandmother is still very healthy in old age."),
}


def download(url: str, destination: Path) -> None:
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_bytes():
                output.write(chunk)


def rows(path: Path):
    with bz2.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            yield line.rstrip("\n").split("\t")


def traditional_map() -> dict[str, str]:
    records = json.loads(config.HSK_PATH.read_text())
    mapping = {}
    for record in records:
        simplified = record["s"]
        for form in record.get("f", []):
            traditional = form.get("t", "")
            if len(traditional) == len(simplified):
                mapping.update({a: b for a, b in zip(traditional, simplified) if a != b})
    return mapping


def main():
    cache = config.ROOT / "work" / "tatoeba"
    paths = {name: cache / Path(url).name for name, url in FILES.items()}
    for name, url in FILES.items():
        download(url, paths[name])

    links = defaultdict(list)
    english_ids = set()
    for columns in rows(paths["links"]):
        if len(columns) >= 2:
            links[columns[0]].append(columns[1])
            english_ids.add(columns[1])

    english = {}
    for columns in rows(paths["eng"]):
        if len(columns) >= 3 and columns[0] in english_ids:
            english[columns[0]] = columns[2]

    conn = connect(config.DB_PATH)
    items = {row["headword"]: dict(row) for row in conn.execute(
        "SELECT id,headword,hsk_bands FROM item WHERE kind='word'"
    )}
    lexicon = set(items)
    convert = str.maketrans(traditional_map())
    candidates = defaultdict(list)

    for columns in rows(paths["cmn"]):
        if len(columns) < 3 or columns[0] not in links:
            continue
        zh = columns[2].translate(convert).strip()
        hanzi = re.findall(r"[\u3400-\u9fff]", zh)
        if not 4 <= len(hanzi) <= 28:
            continue
        en = next((english.get(link) for link in links[columns[0]] if english.get(link)), None)
        if not en or not 3 <= len(en) <= 180:
            continue
        tokens = segment(zh, lexicon)
        known_chars = sum(len(token) for token in tokens if token in lexicon)
        coverage = known_chars / max(1, len(hanzi))
        if coverage < 0.62:
            continue
        target_words = {token for token in tokens if token in lexicon and token in zh}
        for word in target_words:
            if zh.count(word) != 1:
                continue
            score = coverage * 20 - abs(len(hanzi) - 10) * 0.15
            candidates[word].append((score, zh, en))

    imported_words = imported_sentences = 0
    for word, choices in candidates.items():
        if word not in items:
            continue
        unique = {}
        for score, zh, en in sorted(choices, reverse=True):
            unique.setdefault(zh, (score, zh, en))
        best = list(unique.values())[:3]
        if not best:
            continue
        item_id = items[word]["id"]
        old_ids = [row[0] for row in conn.execute(
            "SELECT s.id FROM sentence s JOIN sentence_token st ON st.sentence_id=s.id "
            "WHERE st.item_id=? AND s.source='generated practice carrier'", (item_id,)
        )]
        conn.execute(
            "DELETE FROM sentence_token WHERE item_id=? AND sentence_id IN ("
            "SELECT id FROM sentence WHERE source='generated practice carrier')", (item_id,)
        )
        for old_id in old_ids:
            if not conn.execute("SELECT 1 FROM sentence_token WHERE sentence_id=?", (old_id,)).fetchone():
                conn.execute("DELETE FROM sentence WHERE id=?", (old_id,))
        for _, zh, en in best:
            existing = conn.execute("SELECT id FROM sentence WHERE zh=? AND en=?", (zh, en)).fetchone()
            if existing:
                sentence_id = existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO sentence(zh,pinyin,en,source,validated) VALUES(?,?,?,?,1)",
                    (zh, sentence_pinyin(zh), en, "Tatoeba (CC BY 2.0)"),
                )
                sentence_id = cursor.lastrowid
                imported_sentences += 1
            conn.execute(
                "INSERT OR IGNORE INTO sentence_token(sentence_id,item_id,position) VALUES(?,?,?)",
                (sentence_id, item_id, zh.index(word)),
            )
        imported_words += 1
    for word, (zh, en) in FALLBACK_SENTENCES.items():
        if word not in items or word in candidates:
            continue
        item_id = items[word]["id"]
        old_ids = [row[0] for row in conn.execute(
            "SELECT s.id FROM sentence s JOIN sentence_token st ON st.sentence_id=s.id "
            "WHERE st.item_id=? AND s.source='generated practice carrier'", (item_id,)
        )]
        conn.execute(
            "DELETE FROM sentence_token WHERE item_id=? AND sentence_id IN ("
            "SELECT id FROM sentence WHERE source='generated practice carrier')", (item_id,)
        )
        for old_id in old_ids:
            conn.execute("DELETE FROM sentence WHERE id=?", (old_id,))
        cursor = conn.execute(
            "INSERT INTO sentence(zh,pinyin,en,source,validated) VALUES(?,?,?,?,1)",
            (zh, sentence_pinyin(zh), en, "authored contextual fallback"),
        )
        conn.execute(
            "INSERT INTO sentence_token(sentence_id,item_id,position) VALUES(?,?,?)",
            (cursor.lastrowid, item_id, zh.index(word)),
        )
        imported_words += 1
    conn.commit()
    print(f"Imported contextual examples for {imported_words} words "
          f"({imported_sentences} unique sentence pairs).")
    conn.close()


if __name__ == "__main__":
    main()
