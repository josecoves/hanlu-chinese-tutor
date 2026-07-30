import json
import re
from datetime import datetime, timezone
from pathlib import Path
from pypinyin import Style, lazy_pinyin
from . import config


def sentence_pinyin(text: str) -> str:
    return " ".join(lazy_pinyin(text, style=Style.TONE, neutral_tone_with_five=False))


LOW_PRIORITY_SENSE_MARKERS = (
    "surname ", "variant of ", "old variant", "used in ", "abbr. for ",
    "archaic", "foundation of a university",
)

PRIMARY_GLOSS_OVERRIDES = {
    "开学": "school begins; start of a school term",
    "院": "institution; courtyard (usually in compounds)",
}


def _sense_priority(value: str) -> tuple[int]:
    lowered = value.lower().strip()
    return (int(any(marker in lowered for marker in LOW_PRIORITY_SENSE_MARKERS)),)


def clean_gloss(senses: list[str], headword: str = "") -> str:
    if headword in PRIMARY_GLOSS_OVERRIDES:
        return PRIMARY_GLOSS_OVERRIDES[headword]
    cleaned = []
    note_markers = (
        "as opposed to", "informal", "abbr", "variant", "old", "used in",
        "taiwan pr", "also written", "see ", "lit.", "fig.", "colloquial",
        "surname", "polite", "courteous", "honorific", "bound form",
    )
    for raw in senses:
        raw = re.sub(r"\bCL:[^;/]+", "", raw, flags=re.I)
        parts = re.split(r"\s*;\s*", raw)
        for part in parts:
            parentheses = re.findall(r"\(([^)]*)\)", part)
            base = re.sub(r"\s*\([^)]*\)", "", part).strip(" ,;")
            useful = [
                p.strip() for p in parentheses
                if not any(m in p.lower() for m in note_markers)
                and not re.search(r"[\u3400-\u9fff]", p)
            ]
            value = base or "; ".join(useful)
            if value and value.lower() not in {x.lower() for x in cleaned}:
                cleaned.append(value)
    cleaned.sort(key=_sense_priority)
    useful = [
        value for value in cleaned
        if not any(marker in value.lower() for marker in LOW_PRIORITY_SENSE_MARKERS)
    ]
    selected = useful or cleaned
    return "; ".join(selected[:2]) or headword


def _definitions_by_word(path: Path) -> dict:
    records = json.loads(path.read_text())
    return {row["s"]: row for row in records}


def _band(row) -> str:
    values = sorted({
        int(label[1:]) for label in row.get("l", [])
        if label.startswith("n") and label[1:].isdigit()
    })
    return ",".join(map(str, values))


def preferred_form(row: dict, word: str) -> dict:
    forms = row.get("f") or [{}]
    def score(candidate):
        senses = candidate.get("m") or []
        pinyin = (candidate.get("i") or {}).get("y", "")
        joined = " ".join(senses).lower()
        all_low_priority = bool(senses) and all(
            any(marker in sense.lower() for marker in LOW_PRIORITY_SENSE_MARKERS)
            for sense in senses
        )
        return (
            int(all_low_priority),
            sum(marker in joined for marker in LOW_PRIORITY_SENSE_MARKERS),
            int(bool(pinyin[:1]) and pinyin[:1].isupper()),
            -len(senses),
        )
    return min(forms, key=score)


def _refresh_dictionary_metadata(conn, definitions: dict) -> None:
    for item in conn.execute("SELECT id,headword FROM item"):
        row = definitions.get(item["headword"])
        if not row:
            continue
        form = preferred_form(row, item["headword"])
        info = form.get("i", {})
        conn.execute(
            "UPDATE item SET pinyin=?,gloss=?,measure_word=? WHERE id=?",
            (
                info.get("y") or sentence_pinyin(item["headword"]),
                clean_gloss(form.get("m") or [], item["headword"]),
                "、".join(form.get("c") or []),
                item["id"],
            ),
        )


def _seed_stories(conn) -> None:
    stories = [
        ("早上的咖啡", "Morning coffee", [
            {"zh": "今天早上天气很好。", "en": "The weather is lovely this morning."},
            {"zh": "我走到家旁边的小店。", "en": "I walk to the small shop beside my home."},
            {"zh": "店里有茶，也有咖啡。", "en": "The shop has tea and coffee."},
            {"zh": "我想喝一杯热咖啡。", "en": "I want to drink a cup of hot coffee."},
            {"zh": "朋友说这里的面包也很好吃。", "en": "My friend says the bread here is also tasty."},
            {"zh": "我们坐下，一起吃早饭。", "en": "We sit down and eat breakfast together."},
            {"zh": "八点半，我们去上班。", "en": "At eight thirty, we go to work."},
            {"zh": "新的一天开始了。", "en": "A new day begins."},
        ]),
        ("坐地铁去学校", "Taking the metro to school", [
            {"zh": "我的学校离家不远。", "en": "My school is not far from home."},
            {"zh": "今天我坐地铁去学校。", "en": "Today I take the metro to school."},
            {"zh": "地铁站在路的左边。", "en": "The metro station is on the left side of the road."},
            {"zh": "车上有很多人。", "en": "There are many people on the train."},
            {"zh": "我听音乐，也看课本。", "en": "I listen to music and also read my textbook."},
            {"zh": "二十分钟以后，我到了。", "en": "Twenty minutes later, I arrive."},
            {"zh": "老师和同学都在教室里。", "en": "The teacher and classmates are all in the classroom."},
            {"zh": "九点，我们开始上课。", "en": "At nine, we begin class."},
        ]),
        ("周末的公园", "A weekend in the park", [
            {"zh": "周末我和家人去公园。", "en": "On the weekend my family and I go to the park."},
            {"zh": "公园里有很多树和花。", "en": "There are many trees and flowers in the park."},
            {"zh": "妹妹喜欢看小鸟。", "en": "My younger sister likes watching birds."},
            {"zh": "爸爸和妈妈在湖边走路。", "en": "Dad and Mom walk beside the lake."},
            {"zh": "我和弟弟一起打球。", "en": "My younger brother and I play ball together."},
            {"zh": "中午我们吃面条儿和水果。", "en": "At noon we eat noodles and fruit."},
            {"zh": "下午开始下雨了。", "en": "In the afternoon it starts to rain."},
            {"zh": "我们开心地回家。", "en": "We happily return home."},
        ]),
        ("第一次买菜", "Buying groceries for the first time", [
            {"zh": "晚上我想给朋友做饭。", "en": "In the evening I want to cook for a friend."},
            {"zh": "可是家里没有菜。", "en": "But there are no vegetables at home."},
            {"zh": "我拿着钱包去超市。", "en": "I take my wallet and go to the supermarket."},
            {"zh": "我买了鸡蛋、米和青菜。", "en": "I buy eggs, rice, and green vegetables."},
            {"zh": "这些东西一共三十元。", "en": "These things cost thirty yuan altogether."},
            {"zh": "回家以后，我开始做饭。", "en": "After returning home, I begin cooking."},
            {"zh": "朋友说中国菜很好吃。", "en": "My friend says Chinese food is delicious."},
            {"zh": "我听了非常高兴。", "en": "I am very happy to hear that."},
        ]),
        ("朋友的生日", "A friend’s birthday", [
            {"zh": "今天是我朋友小李的生日。", "en": "Today is my friend Xiao Li’s birthday."},
            {"zh": "我想送给他一个小礼物。", "en": "I want to give him a small gift."},
            {"zh": "下午我去商店买了一本书。", "en": "In the afternoon I go to the shop and buy a book."},
            {"zh": "晚上我们在他家见面。", "en": "In the evening we meet at his home."},
            {"zh": "他的妈妈做了很多好吃的菜。", "en": "His mother makes many delicious dishes."},
            {"zh": "我们一起唱生日歌。", "en": "We sing the birthday song together."},
            {"zh": "小李打开礼物，非常喜欢。", "en": "Xiao Li opens the gift and likes it very much."},
            {"zh": "大家都玩得很开心。", "en": "Everyone has a very happy time."},
        ]),
        ("在饭店点菜", "Ordering at a restaurant", [
            {"zh": "周末我和姐姐去一家中国饭店。", "en": "On the weekend my older sister and I go to a Chinese restaurant."},
            {"zh": "服务员给我们看菜单。", "en": "The server gives us the menu."},
            {"zh": "姐姐想吃鱼，我想吃鸡肉。", "en": "My sister wants fish, and I want chicken."},
            {"zh": "我们还点了米饭和青菜。", "en": "We also order rice and green vegetables."},
            {"zh": "这里的茶是免费的。", "en": "The tea here is free."},
            {"zh": "菜很快就来了。", "en": "The dishes arrive quickly."},
            {"zh": "我们吃得很饱。", "en": "We eat until we are full."},
            {"zh": "最后姐姐用手机付钱。", "en": "Finally, my sister pays with her phone."},
        ]),
        ("我的手机在哪里", "Where is my phone?", [
            {"zh": "早上我要出门，可是找不到手机。", "en": "In the morning I need to leave, but I cannot find my phone."},
            {"zh": "我先看了桌子和床。", "en": "First I look at the table and the bed."},
            {"zh": "桌子上只有一本书。", "en": "There is only a book on the table."},
            {"zh": "床上也没有手机。", "en": "The phone is not on the bed either."},
            {"zh": "我请妹妹给我打电话。", "en": "I ask my younger sister to call me."},
            {"zh": "这时，书包里有声音。", "en": "Then, there is a sound inside my schoolbag."},
            {"zh": "原来手机在书包里。", "en": "It turns out the phone is in the schoolbag."},
            {"zh": "我拿上手机，马上出门。", "en": "I take my phone and leave right away."},
        ]),
        ("去医院看医生", "Going to see a doctor", [
            {"zh": "昨天晚上我觉得不太舒服。", "en": "Last night I did not feel very well."},
            {"zh": "今天早上我的头还是很疼。", "en": "This morning my head still hurts."},
            {"zh": "妈妈带我去医院看医生。", "en": "Mom takes me to the hospital to see a doctor."},
            {"zh": "医生先问了几个问题。", "en": "The doctor first asks several questions."},
            {"zh": "然后他检查了我的身体。", "en": "Then he examines me."},
            {"zh": "医生说我应该多喝水，多休息。", "en": "The doctor says I should drink more water and rest."},
            {"zh": "回家以后，我吃了药。", "en": "After returning home, I take medicine."},
            {"zh": "下午我感觉好多了。", "en": "In the afternoon I feel much better."},
        ]),
        ("图书馆的一天", "A day at the library", [
            {"zh": "星期六上午，我去图书馆学习。", "en": "On Saturday morning, I go to the library to study."},
            {"zh": "图书馆里很安静。", "en": "It is very quiet in the library."},
            {"zh": "我先找了一本中文书。", "en": "First, I find a Chinese book."},
            {"zh": "书里的故事很有意思。", "en": "The story in the book is very interesting."},
            {"zh": "有几个生词我不认识。", "en": "There are several new words I do not recognize."},
            {"zh": "我用手机查了这些词。", "en": "I use my phone to look up these words."},
            {"zh": "中午，我和同学一起吃饭。", "en": "At noon, I eat with a classmate."},
            {"zh": "下午三点，我借书回家。", "en": "At three in the afternoon, I borrow the book and go home."},
        ]),
        ("下雨的早上", "A rainy morning", [
            {"zh": "今天早上下了很大的雨。", "en": "It rains heavily this morning."},
            {"zh": "我出门的时候忘了带伞。", "en": "I forget to take an umbrella when I leave home."},
            {"zh": "我只好跑到地铁站。", "en": "I have no choice but to run to the metro station."},
            {"zh": "我的衣服和鞋都湿了。", "en": "My clothes and shoes are both wet."},
            {"zh": "地铁里的人特别多。", "en": "There are especially many people on the metro."},
            {"zh": "我到公司的时候已经迟到了。", "en": "I am already late when I arrive at the office."},
            {"zh": "同事给了我一杯热茶。", "en": "A coworker gives me a cup of hot tea."},
            {"zh": "喝完以后，我觉得好多了。", "en": "After drinking it, I feel much better."},
        ]),
        ("周末去爬山", "Hiking on the weekend", [
            {"zh": "这个周末天气很好。", "en": "The weather is very good this weekend."},
            {"zh": "我和两个朋友一起去爬山。", "en": "I go hiking with two friends."},
            {"zh": "我们早上七点从家出发。", "en": "We leave home at seven in the morning."},
            {"zh": "山路有一点儿长。", "en": "The mountain path is a little long."},
            {"zh": "走累了，我们就坐下休息。", "en": "When we get tired, we sit down to rest."},
            {"zh": "山上有很多漂亮的花。", "en": "There are many beautiful flowers on the mountain."},
            {"zh": "中午我们在树下吃东西。", "en": "At noon, we eat under a tree."},
            {"zh": "虽然很累，但是大家都很开心。", "en": "Although we are tired, everyone is happy."},
        ]),
        ("给朋友打电话", "Calling a friend", [
            {"zh": "晚上，我想给朋友小王打电话。", "en": "In the evening, I want to call my friend Xiao Wang."},
            {"zh": "可是他第一次没有接。", "en": "But he does not answer the first time."},
            {"zh": "过了十分钟，他给我回电话。", "en": "Ten minutes later, he calls me back."},
            {"zh": "他说他刚才在洗澡。", "en": "He says he was taking a shower just now."},
            {"zh": "我们聊了今天的工作。", "en": "We talk about today’s work."},
            {"zh": "他还告诉我一个好消息。", "en": "He also tells me some good news."},
            {"zh": "下个月他要来我的城市。", "en": "Next month, he is coming to my city."},
            {"zh": "我们决定周末一起吃饭。", "en": "We decide to eat together on the weekend."},
        ]),
    ]
    for title_zh, title_en, sentences in stories:
        if conn.execute("SELECT 1 FROM story WHERE title_zh=?", (title_zh,)).fetchone():
            continue
        for sentence in sentences:
            sentence["py"] = sentence_pinyin(sentence["zh"])
            sentence["audio"] = None
        conn.execute(
            "INSERT INTO story(title_zh,title_en,sentences_json) VALUES(?,?,?)",
            (title_zh, title_en, json.dumps(sentences, ensure_ascii=False)),
        )


def _seed_context_sentences(conn) -> None:
    if not config.CONTEXT_SENTENCES_PATH.exists():
        return
    entries = json.loads(config.CONTEXT_SENTENCES_PATH.read_text())
    by_word = {}
    for entry in entries:
        by_word.setdefault(entry["word"], []).append(entry)
    for word, sentences in by_word.items():
        item = conn.execute("SELECT id FROM item WHERE headword=?", (word,)).fetchone()
        if not item:
            continue
        item_id = item["id"]
        has_context = conn.execute(
            "SELECT 1 FROM sentence s JOIN sentence_token st ON st.sentence_id=s.id "
            "WHERE st.item_id=? AND s.source<>'generated practice carrier' LIMIT 1", (item_id,)
        ).fetchone()
        if has_context:
            continue
        old_ids = [row["id"] for row in conn.execute(
            "SELECT s.id FROM sentence s JOIN sentence_token st ON st.sentence_id=s.id "
            "WHERE st.item_id=? AND s.source='generated practice carrier'", (item_id,)
        )]
        conn.execute(
            "DELETE FROM sentence_token WHERE item_id=? AND sentence_id IN ("
            "SELECT id FROM sentence WHERE source='generated practice carrier')", (item_id,)
        )
        for old_id in old_ids:
            if not conn.execute(
                "SELECT 1 FROM sentence_token WHERE sentence_id=?", (old_id,)
            ).fetchone():
                conn.execute("DELETE FROM sentence WHERE id=?", (old_id,))
        for entry in sentences:
            existing = conn.execute(
                "SELECT id FROM sentence WHERE zh=? AND en=?", (entry["zh"], entry["en"])
            ).fetchone()
            if existing:
                sentence_id = existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO sentence(zh,pinyin,en,source,validated) VALUES(?,?,?,?,1)",
                    (entry["zh"], sentence_pinyin(entry["zh"]), entry["en"], entry["source"]),
                )
                sentence_id = cursor.lastrowid
            conn.execute(
                "INSERT OR IGNORE INTO sentence_token(sentence_id,item_id,position) VALUES(?,?,?)",
                (sentence_id, item_id, entry["zh"].index(word)),
            )


def _apply_content_corrections(conn) -> None:
    corrections = (
        (
            "院",
            "我住了一个星期的院。",
            "我在医院住了一周。",
            "I was in hospital for a week.",
            "curated correction",
        ),
    )
    for word, old_zh, zh, en, source in corrections:
        conn.execute(
            "UPDATE sentence SET zh=?,pinyin=?,en=?,source=?,validated=1,"
            "audio_path=NULL WHERE zh=?",
            (zh, sentence_pinyin(zh), en, source, old_zh),
        )
        conn.execute(
            "UPDATE sentence_token SET position=? WHERE item_id=("
            "SELECT id FROM item WHERE headword=?) AND sentence_id=("
            "SELECT id FROM sentence WHERE zh=?)",
            (zh.index(word), word, zh),
        )


def bootstrap_content(conn) -> None:
    definitions = _definitions_by_word(config.HSK_PATH)
    if conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]:
        _refresh_dictionary_metadata(conn, definitions)
        _seed_context_sentences(conn)
        _apply_content_corrections(conn)
        _seed_stories(conn)
        conn.commit()
        return
    labels = json.loads(config.TOPIC_LABELS_PATH.read_text())
    for rank, (word, topics) in enumerate(labels.items(), 1):
        row = definitions.get(word, {})
        form = preferred_form(row, word)
        info = form.get("i", {})
        pinyin = info.get("y") or sentence_pinyin(word)
        gloss = clean_gloss(form.get("m") or [], word)
        band = _band(row) or ("1" if rank <= 500 else "2")
        cursor = conn.execute(
            "INSERT INTO item(kind,headword,pinyin,gloss,freq_rank,hsk_bands,measure_word) "
            "VALUES('word',?,?,?,?,?,?)",
            (word, pinyin, gloss, row.get("q"), band, ""),
        )
        item_id = cursor.lastrowid
        for topic in topics:
            if topic in config.TOPICS:
                conn.execute("INSERT INTO item_topic(item_id,topic) VALUES(?,?)", (item_id, topic))
        zh = f"今天我们学习“{word}”。"
        en = f'Today we are learning “{gloss}.”'
        cursor = conn.execute(
            "INSERT INTO sentence(zh,pinyin,en,source,validated) VALUES(?,?,?,?,?)",
            (zh, sentence_pinyin(zh), en, "generated practice carrier", 1),
        )
        conn.execute(
            "INSERT INTO sentence_token(sentence_id,item_id,position) VALUES(?,?,0)",
            (cursor.lastrowid, item_id),
        )
    _seed_context_sentences(conn)
    _apply_content_corrections(conn)
    _seed_stories(conn)
    _refresh_dictionary_metadata(conn, definitions)
    conn.commit()


def restore_progress(conn, path: Path | None = None) -> dict:
    path = path or config.PROGRESS_PATH
    if not path.exists():
        return {"memory": 0, "reviews": 0}
    data = json.loads(path.read_text())
    memory = reviews = 0
    for row in data.get("memory_state", []):
        item = conn.execute("SELECT id FROM item WHERE headword=?", (row["headword"],)).fetchone()
        if not item:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO memory_state "
            "(user_id,item_id,facet,difficulty,stability,last_review_ts,due_ts,lapses,"
            "suspended,card_json,seeded) VALUES(1,?,?,?,?,?,?,?,?,?,?)",
            (item["id"], row["facet"], row.get("difficulty"), row.get("stability"),
             row.get("last_review_ts"), row["due_ts"], row.get("lapses", 0),
             row.get("suspended", 0), row["card_json"],
             int(row.get("last_review_ts") is None)),
        )
        memory += conn.execute("SELECT changes()").fetchone()[0]
    for row in data.get("review_log", []):
        item = conn.execute("SELECT id FROM item WHERE headword=?", (row["headword"],)).fetchone()
        if not item:
            continue
        exists = conn.execute(
            "SELECT 1 FROM review_log WHERE item_id=? AND facet=? AND ts=?",
            (item["id"], row["facet"], row["ts"]),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO review_log(user_id,item_id,facet,exercise_type,grade,"
                "latency_ms,hints_used,elapsed_days,ts) VALUES(1,?,?,?,?,?,?,?,?)",
                (item["id"], row["facet"], row["exercise_type"], row["grade"],
                 row.get("latency_ms", 0), row.get("hints_used", 0),
                 row.get("elapsed_days"), row["ts"]),
            )
            reviews += 1
    for row in data.get("story_state", []):
        story = conn.execute(
            "SELECT id FROM story WHERE title_zh=?", (row["title_zh"],)
        ).fetchone()
        if story:
            conn.execute(
                "INSERT INTO story_state(user_id,story_id,status,current_index,updated_ts) "
                "VALUES(1,?,?,?,?) ON CONFLICT(user_id,story_id) DO UPDATE SET "
                "status=excluded.status,current_index=excluded.current_index,"
                "updated_ts=excluded.updated_ts",
                (
                    story["id"], row["status"], row.get("current_index", 0),
                    row["updated_ts"],
                ),
            )
    for row in data.get("story_sentence_progress", []):
        story = conn.execute(
            "SELECT id FROM story WHERE title_zh=?", (row["title_zh"],)
        ).fetchone()
        if story:
            conn.execute(
                "INSERT OR IGNORE INTO story_sentence_progress("
                "user_id,story_id,sentence_index,completed_ts) VALUES(1,?,?,?)",
                (story["id"], row["sentence_index"], row["completed_ts"]),
            )
    for row in data.get("story_word_exposure", []):
        story = conn.execute(
            "SELECT id FROM story WHERE title_zh=?", (row["title_zh"],)
        ).fetchone()
        item = conn.execute(
            "SELECT id FROM item WHERE headword=?", (row["headword"],)
        ).fetchone()
        if story and item:
            conn.execute(
                "INSERT INTO story_word_exposure(user_id,story_id,sentence_index,"
                "item_id,status,updated_ts) VALUES(1,?,?,?,?,?) ON CONFLICT("
                "user_id,story_id,sentence_index,item_id) DO UPDATE SET "
                "status=excluded.status,updated_ts=excluded.updated_ts",
                (
                    story["id"], row["sentence_index"], item["id"],
                    row["status"], row["updated_ts"],
                ),
            )
    for row in data.get("item_knowledge_override", []):
        item = conn.execute(
            "SELECT id FROM item WHERE headword=?", (row["headword"],)
        ).fetchone()
        if item and row.get("status") == "needs_practice":
            conn.execute(
                "INSERT INTO item_knowledge_override(user_id,item_id,status,updated_ts) "
                "VALUES(1,?,'needs_practice',?) ON CONFLICT(user_id,item_id) DO UPDATE "
                "SET status=excluded.status,updated_ts=excluded.updated_ts",
                (item["id"], row["updated_ts"]),
            )
    conn.execute(
        "UPDATE learner SET declared_hsk_band=? WHERE id=1",
        (int(data.get("declared_hsk_band", 0)),),
    )
    conn.commit()
    return {"memory": memory, "reviews": reviews}
