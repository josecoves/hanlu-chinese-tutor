import json
import app.web as web_module
from app.ai_review import AIReviewResult
from app.web import _grammar_match, _grammar_vocabulary, _known_headwords


def test_home_and_vocab(client):
    assert client.get("/").status_code == 200
    response = client.get("/vocab?q=tea")
    assert response.status_code == 200
    assert "茶" in response.text
    assert "HSK 1" in response.text
    assert "mdbg.net/chinese/dictionary" in response.text
    assert "hsk-badge hsk-1" in response.text
    assert "Practice status" in response.text


def test_vocab_defaults_to_hsk_order_and_filters_unpracticed(client, db):
    school_id = db.execute(
        "INSERT INTO item(headword,pinyin,gloss,freq_rank,hsk_bands) "
        "VALUES('开学','kāi xué','school begins',1,'2')"
    ).lastrowid
    sentence_id = db.execute(
        "INSERT INTO sentence(zh,pinyin,en,source,validated) "
        "VALUES('明天就开学了。','míngtiān jiù kāixué le','School begins tomorrow.',"
        "'test',1)"
    ).lastrowid
    db.execute("INSERT INTO sentence_token VALUES(?,?,3)", (sentence_id, school_id))
    db.commit()
    page = client.get("/vocab")
    assert page.text.index("茶 ↗") < page.text.index("开学 ↗")
    assert "hsk-badge hsk-2" in page.text

    filtered = client.get("/vocab?hsk=2&practice=unpracticed&sort=hsk")
    assert "开学 ↗" in filtered.text
    assert "茶 ↗" not in filtered.text
    assert 'value="2" selected' in filtered.text
    assert 'value="unpracticed" selected' in filtered.text
    assert (
        'href="/vocab/practice?hsk=2&amp;practice=unpracticed"'
        in filtered.text
    )

    started = client.get(
        "/vocab/practice?hsk=2&practice=unpracticed", follow_redirects=False
    )
    assert started.status_code == 303
    plan = json.loads(db.execute(
        "SELECT plan_json FROM session WHERE id=1"
    ).fetchone()[0])
    assert plan["queue"] == [[school_id, "reading-recognition"]]


def test_topics_show_hsk_progress_and_filter_practice(client, db):
    tea_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    cursor = db.execute(
        "INSERT INTO item(headword,pinyin,gloss,hsk_bands) "
        "VALUES('开学','kāi xué','school begins','2')"
    )
    school_id = cursor.lastrowid
    sentence = db.execute(
        "INSERT INTO sentence(zh,pinyin,en,source,validated) "
        "VALUES('明天就开学了。','míngtiān jiù kāixué le','School begins tomorrow.',"
        "'test',1)"
    ).lastrowid
    db.execute("INSERT INTO sentence_token VALUES(?,?,3)", (sentence, school_id))
    db.executemany(
        "INSERT INTO item_topic(item_id,topic) VALUES(?,?)",
        [(tea_id, "Work & study"), (school_id, "Work & study")],
    )
    db.execute("UPDATE learner SET declared_hsk_band=1 WHERE id=1")
    db.commit()

    page = client.get("/topics")
    assert page.status_code == 200
    assert "Work &amp; study" in page.text
    assert "1 / 1 known" in page.text
    assert "100%" in page.text
    assert "0 / 1 known" in page.text
    assert "Practice HSK 2 next" in page.text
    assert "Not available yet" in page.text
    assert "Loaded vocabulary by HSK level" in page.text
    assert "View words" in page.text
    assert "/topic/Work%20%26%20study?hsk=2" in page.text

    response = client.get(
        "/topic/Work%20%26%20study/practice?hsk=2", follow_redirects=False
    )
    assert response.status_code == 303
    plan = json.loads(db.execute(
        "SELECT plan_json FROM session WHERE id=1"
    ).fetchone()[0])
    assert plan["queue"] == [[school_id, "reading-recognition"]]


def test_story_status_and_sentence_vocabulary_update_progress(client, db):
    tea_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    story_id = db.execute(
        "INSERT INTO story(title_zh,title_en,sentences_json) VALUES(?,?,?)",
        (
            "喝茶",
            "Drinking tea",
            json.dumps([{
                "zh": "我喜欢喝茶。",
                "py": "wǒ xǐhuan hē chá",
                "en": "I like drinking tea.",
                "audio": None,
            }], ensure_ascii=False),
        ),
    ).lastrowid
    db.commit()

    library = client.get("/stories")
    assert "Twelve short HSK 1–2 readers" in library.text
    assert "Story status" not in library.text
    page = client.get(f"/story/{story_id}")
    assert "Going next marks every word studied" in page.text
    assert "\\u8336" in page.text
    assert "Flag a problem with this card" in page.text
    assert "/static/reader.js?v=2" in page.text
    reader_script = client.get("/static/reader.js").text
    assert '{capture: true}' in reader_script
    assert "event.preventDefault()" in reader_script

    saved = client.post(
        f"/story/{story_id}/status",
        data={"status": "reading"},
        headers={"X-Requested-With": "hanlu"},
    )
    assert saved.json() == {"ok": True, "status": "reading"}

    completed = client.post(
        f"/story/{story_id}/sentence/0/complete",
        data={"hard": str(tea_id)},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "finished"
    assert completed.json()["hard_words"] == 1
    exposure = db.execute(
        "SELECT status FROM story_word_exposure WHERE story_id=? AND item_id=?",
        (story_id, tea_id),
    ).fetchone()
    assert exposure["status"] == "hard"
    assert db.execute(
        "SELECT COUNT(*) FROM review_log WHERE item_id=? "
        "AND exercise_type='story-context'", (tea_id,)
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT 1 FROM memory_state WHERE item_id=? AND facet='reading-recognition'",
        (tea_id,),
    ).fetchone()

    client.post(
        f"/story/{story_id}/sentence/0/complete",
        data={"hard": str(tea_id)},
    )
    assert db.execute(
        "SELECT COUNT(*) FROM review_log WHERE item_id=? "
        "AND exercise_type='story-context'", (tea_id,)
    ).fetchone()[0] == 1

    client.post(
        f"/story/{story_id}/sentence/0/complete",
        data={"hard": ""},
    )
    assert db.execute(
        "SELECT status FROM story_word_exposure WHERE story_id=? AND item_id=?",
        (story_id, tea_id),
    ).fetchone()[0] == "studied"
    assert db.execute(
        "SELECT COUNT(*) FROM review_log WHERE item_id=? "
        "AND exercise_type='story-context'", (tea_id,)
    ).fetchone()[0] == 2
    exported = client.get("/export/progress").json()
    assert exported["schema"] == 5
    assert any(
        row["title_zh"] == "喝茶" and row["headword"] == "茶"
        for row in exported["story_word_exposure"]
    )


def test_session_is_idempotent(client, db):
    item_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    db.execute(
        "INSERT INTO session(id,user_id,plan_json) VALUES(1,1,?)",
        (json.dumps({"queue": [[item_id, "reading-recognition"]], "idx": 0,
                     "correct": 0, "wrong": 0}),),
    )
    db.commit()
    card = client.get("/session/next")
    assert card.status_code == 200
    served = json.loads(db.execute(
        "SELECT plan_json FROM session WHERE id=1"
    ).fetchone()[0])
    assert served["question"]["sentence_zh"] == "我喜欢喝茶。"
    first = client.post("/session/answer", data={"idx": 0, "response": "tea"})
    assert "Correct" in first.text
    assert "Show detailed word meaning" in first.text
    assert "Check 茶 in MDBG" in first.text
    assert "我喜欢喝茶。" in first.text
    stale = client.post("/session/answer", data={"idx": 0, "response": "tea"})
    assert "Correct" in stale.text
    assert db.execute("SELECT COUNT(*) FROM review_log").fetchone()[0] == 1


def test_word_can_be_snoozed_and_leaves_current_session(client, db):
    item_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    db.execute(
        "INSERT INTO session(id,user_id,plan_json) VALUES(1,1,?)",
        (json.dumps({"queue": [[item_id, "reading-recognition"]], "idx": 0,
                     "correct": 0, "wrong": 0}),),
    )
    db.commit()
    client.get("/session/next")
    response = client.post(
        f"/item/{item_id}/snooze", data={"days": 7}, follow_redirects=False
    )
    assert response.status_code == 303
    assert db.execute(
        "SELECT snoozed_until FROM item_preference WHERE item_id=?", (item_id,)
    ).fetchone()[0]
    plan = json.loads(db.execute(
        "SELECT plan_json FROM session WHERE id=1"
    ).fetchone()[0])
    assert plan["idx"] == 1


def test_word_can_be_marked_needs_practice_from_vocabulary(client, db):
    item_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    db.execute("UPDATE learner SET declared_hsk_band=1 WHERE id=1")
    db.commit()
    assert "茶" in _known_headwords(db)

    response = client.post(
        f"/item/{item_id}/knowledge",
        data={"state": "needs_practice", "return_to": "/vocab?hsk=1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/vocab?hsk=1"
    assert "茶" not in _known_headwords(db)
    assert db.execute(
        "SELECT status FROM item_knowledge_override WHERE item_id=?", (item_id,)
    ).fetchone()[0] == "needs_practice"
    assert db.execute(
        "SELECT COUNT(*) FROM memory_state WHERE item_id=?",
        (item_id,),
    ).fetchone()[0] == 2

    page = client.get("/vocab?hsk=1")
    assert "Memory" in page.text
    assert "Activity" in page.text
    assert "Knowledge" not in page.text
    assert "add to review" in page.text
    assert "R✓" in page.text
    assert 'data-review-toggle' in page.text
    assert "/static/vocabulary.js?v=2" in page.text
    script = client.get("/static/vocabulary.js").text
    assert 'headers: {"X-Requested-With": "hanlu"}' in script
    exported = client.get("/export/progress").json()
    assert any(
        row["headword"] == "茶" and row["status"] == "needs_practice"
        for row in exported["item_knowledge_override"]
    )

    client.post(
        f"/item/{item_id}/knowledge",
        data={"state": "auto", "return_to": "/vocab"},
    )
    assert "茶" in _known_headwords(db)

    ajax = client.post(
        f"/item/{item_id}/knowledge",
        data={"state": "needs_practice", "return_to": "/vocab"},
        headers={"X-Requested-With": "hanlu"},
    )
    assert ajax.json() == {"ok": True, "state": "needs_practice"}


def test_bug_ignores_blank_note(client, db):
    client.post("/bug", data={"ref": "#R1-1", "note": "", "return_to": "/"})
    assert db.execute("SELECT COUNT(*) FROM bug_report").fetchone()[0] == 0


def test_bug_keeps_grammar_context(client, db):
    response = client.post("/bug", data={
        "ref": "#G1-test", "note": "The translation feels wrong.",
        "context": "我是学生。 — I am a student. · Identifying with 是",
        "return_to": "/grammar",
    })
    assert response.status_code == 200
    report = db.execute("SELECT ref,note,context FROM bug_report").fetchone()
    assert report["ref"] == "#G1-test"
    assert "我是学生" in report["context"]


def test_bug_report_saves_in_place_without_losing_grammar_card(client, db):
    client.get("/grammar/practice/card?level=1&mode=production")
    before = db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0]
    response = client.post("/bug", data={
        "ref": "#G2-test",
        "note": "tree is unknown",
        "context": "公园里有很多树。 — There are many trees in the park.",
        "return_to": "/grammar",
    }, headers={"X-Requested-With": "hanlu"})
    assert response.json() == {"ok": True, "saved": True}
    after = db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0]
    assert after == before
    script = client.get("/static/practice.js").text
    assert "Report saved — continue this card." in script
    assert 'event.preventDefault()' in script


def test_bug_report_non_js_fallback_resumes_exact_grammar_reveal(client, db):
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='有字句'"
    ).fetchone()
    client.get(
        f"/grammar/practice/card?grammar_id={point['id']}&mode=production"
    )
    plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    reveal = client.post("/grammar/answer", data={"response": "完全不对"})
    assert "Keep building" in reveal.text
    assert 'value="/grammar-session/current"' in reveal.text
    assert "/static/practice.js?v=3" in reveal.text
    attempts_before = db.execute(
        "SELECT COUNT(*) FROM grammar_attempt"
    ).fetchone()[0]

    saved = client.post("/bug", data={
        "ref": plan["ref"],
        "note": "Resume this exact reveal.",
        "context": f"{plan['zh']} — {plan['en']}",
        "return_to": "/grammar-session/current",
    }, follow_redirects=False)
    assert saved.status_code == 303
    assert saved.headers["location"] == "/grammar-session/current"
    resumed = client.get(saved.headers["location"])
    assert "Keep building" in resumed.text
    assert plan["zh"] in resumed.text
    assert db.execute(
        "SELECT COUNT(*) FROM grammar_attempt"
    ).fetchone()[0] == attempts_before


def test_skip_and_flag_grammar_sentence_moves_on_without_attempt(client, db):
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='的字短语'"
    ).fetchone()
    client.get(
        f"/grammar/practice/card?grammar_id={point['id']}&mode=production"
    )
    before = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    attempts_before = db.execute(
        "SELECT COUNT(*) FROM grammar_attempt"
    ).fetchone()[0]
    skipped = client.post(
        "/grammar/session/skip-and-flag", follow_redirects=False
    )
    assert skipped.status_code == 303
    assert (
        skipped.headers["location"]
        == f"/grammar/practice/card?mode=production&grammar_id={point['id']}"
    )
    assert db.execute(
        "SELECT COUNT(*) FROM grammar_attempt"
    ).fetchone()[0] == attempts_before
    report = db.execute(
        "SELECT ref,note,context FROM bug_report ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert report["ref"] == before["ref"]
    assert "Skipped automatically" in report["note"]
    assert before["zh"] in report["context"]

    next_card = client.get(skipped.headers["location"])
    assert next_card.status_code == 200
    after = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    assert after["zh"] != before["zh"]
    assert "Skip &amp; flag this sentence" in next_card.text


def test_grammar_reference_and_comprehension_practice(client, db):
    page = client.get("/grammar")
    assert page.status_code == 200
    assert "Identifying with" in page.text
    assert "48 lessons in the curriculum" in page.text
    assert db.execute("SELECT COUNT(*) FROM grammar_point WHERE level=1").fetchone()[0] == 48
    assert db.execute("SELECT COUNT(*) FROM grammar_point WHERE level=2").fetchone()[0] == 36
    example_sets = db.execute(
        "SELECT theory_examples_json,practice_examples_json FROM grammar_point "
        "WHERE title_zh='有字句'"
    ).fetchone()
    theory = json.loads(example_sets["theory_examples_json"])
    practice = json.loads(example_sets["practice_examples_json"])
    assert len(theory) >= 5
    assert len(practice) >= 10
    assert {example["zh"] for example in theory}.isdisjoint(
        {example["zh"] for example in practice}
    )
    assert {row["zh"] for row in theory}.isdisjoint(
        {row["zh"] for row in practice}
    )
    ma_sets = db.execute(
        "SELECT theory_examples_json,practice_examples_json FROM grammar_point "
        "WHERE title_zh='吗问句'"
    ).fetchone()
    ma_theory = json.loads(ma_sets["theory_examples_json"])
    ma_practice = json.loads(ma_sets["practice_examples_json"])
    assert len(ma_theory) >= 5
    assert len(ma_practice) >= 10
    assert all(row["zh"].endswith("吗？") for row in ma_practice)
    assert not any(
        marker in row["zh"] for row in ma_practice
        for marker in ("的吗", "了吗", "在您国家的人是")
    )
    negation_sets = db.execute(
        "SELECT theory_examples_json,practice_examples_json FROM grammar_point "
        "WHERE title_zh='不和没'"
    ).fetchone()
    negation_theory = json.loads(negation_sets["theory_examples_json"])
    negation_practice = json.loads(negation_sets["practice_examples_json"])
    assert len(negation_theory) >= 5
    assert len(negation_practice) >= 10
    assert all(
        any(marker in row["zh"] for marker in ("不", "没"))
        for row in negation_practice
    )
    assert not any(
        marker in row["zh"] for row in negation_practice
        for marker in ("什么话也", "什么也", "什么都", "是不是")
    )
    card = client.get("/grammar/practice/card?level=1&mode=comprehension")
    assert card.status_code == 200
    assert 'data-choice-index="1"' in card.text
    assert "/static/practice.js" in card.text
    plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    answer = client.post("/grammar/answer", data={"response": plan["expected"]})
    assert answer.status_code == 200
    assert answer.url.path == "/grammar-session/current"
    assert "Correct" in answer.text
    assert plan["zh"] in answer.text
    assert "Flag a problem with this card" in answer.text
    assert db.execute("SELECT COUNT(*) FROM grammar_attempt").fetchone()[0] == 1


def test_grammar_lifecycle_and_practice_scope(client, db):
    empty = client.get("/grammar/practice/card?scope=active&mode=comprehension")
    assert "NO ACTIVE LESSONS YET" in empty.text
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='吗问句'"
    ).fetchone()
    saved = client.post(
        f"/grammar/{point['id']}/status",
        data={"status": "practicing"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    card = client.get("/grammar/practice/card?scope=active&mode=comprehension")
    plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    assert card.status_code == 200
    assert plan["grammar_id"] == point["id"]
    answer = client.post("/grammar/answer", data={"response": plan["expected"]})
    assert "scope=active" in answer.text
    assert "&amp;level=" not in answer.text
    client.post(f"/grammar/{point['id']}/status", data={"status": "learned"})
    assert "NO ACTIVE LESSONS YET" in client.get(
        "/grammar/practice/card?scope=active&mode=comprehension"
    ).text


def test_grammar_status_can_autosave_from_index(client, db):
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='想和要'"
    ).fetchone()
    page = client.get("/grammar")
    assert "data-auto-status" in page.text
    assert f'action="/grammar/{point["id"]}/status"' in page.text
    saved = client.post(
        f"/grammar/{point['id']}/status",
        data={"status": "practicing"},
        headers={"X-Requested-With": "hanlu"},
    )
    assert saved.status_code == 200
    assert saved.json() == {"ok": True, "status": "practicing"}
    assert db.execute(
        "SELECT status FROM grammar_state WHERE grammar_id=?", (point["id"],)
    ).fetchone()[0] == "practicing"
    script = client.get("/static/grammar.js").text
    assert script.index("new FormData(form)") < script.index("select.disabled = true")


def test_grammar_attempts_advance_untouched_lesson_status(client, db):
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='不和没'"
    ).fetchone()
    card = client.get(
        f"/grammar/practice/card?grammar_id={point['id']}&mode=comprehension"
    )
    assert card.status_code == 200
    plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    client.post("/grammar/answer", data={"response": plan["expected"]})
    state = db.execute(
        "SELECT status,source FROM grammar_state WHERE grammar_id=?",
        (point["id"],),
    ).fetchone()
    assert tuple(state) == ("practicing", "auto")

    db.executemany(
        "INSERT INTO grammar_attempt(user_id,grammar_id,direction,prompt,response,"
        "expected,correct,hints_used,ts) VALUES(1,?,'comprehension','test','test',"
        "'test',1,0,'2026-01-01T00:00:00+00:00')",
        [(point["id"],)] * 6,
    )
    db.commit()
    client.get(
        f"/grammar/practice/card?grammar_id={point['id']}&mode=comprehension"
    )
    plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    client.post("/grammar/answer", data={"response": plan["expected"]})
    state = db.execute(
        "SELECT status,source FROM grammar_state WHERE grammar_id=?",
        (point["id"],),
    ).fetchone()
    assert tuple(state) == ("learned", "auto")


def test_rich_grammar_guide_has_pinyin_audio_and_navigation(client, db):
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='的字短语作名词'"
    ).fetchone()
    page = client.get(f"/grammar/{point['id']}")
    assert page.status_code == 200
    assert "Keep the noun" in page.text
    assert "Omit a known noun" in page.text
    assert "我昨天买的书在桌上" in page.text
    assert "toggle-pinyin" in page.text
    assert "speak-chinese" in page.text
    assert "Next lesson" in page.text
    assert "Next new" in page.text
    assert "HSK 2 · Lesson" in page.text
    assert "Phrase + 的: modifying or replacing a noun" in page.text
    assert "/static/grammar.js" in page.text


def test_possessive_de_lesson_uses_reviewed_attributive_examples(client, db):
    point = db.execute(
        "SELECT id,theory_examples_json,practice_examples_json "
        "FROM grammar_point WHERE title_zh='的字短语'"
    ).fetchone()
    theory = json.loads(point["theory_examples_json"])
    practice = json.loads(point["practice_examples_json"])
    all_examples = theory + practice
    assert len(theory) >= 5
    assert len(practice) >= 10
    assert all(
        example["zh"] != "他能过考试的，是不是？"
        for example in all_examples
    )
    assert all(example["source"] == "authored and reviewed"
               for example in all_examples)
    page = client.get(f"/grammar/{point['id']}")
    assert "那是老师的杯子。" in page.text
    assert "He could pass the examination" not in page.text


def test_focused_grammar_practice_stays_on_lesson(client, db):
    point = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='有字句'"
    ).fetchone()
    client.get(
        f"/grammar/practice/card?grammar_id={point['id']}&mode=comprehension"
    )
    plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    answer = client.post("/grammar/answer", data={"response": plan["expected"]})
    assert f"grammar_id={point['id']}" in answer.text
    assert f'href="/grammar/{point["id"]}"' in answer.text
    assert "Back to lesson" in answer.text


def test_focused_grammar_practice_avoids_repeats_until_pool_is_used(client, db):
    point = db.execute(
        "SELECT id,practice_examples_json FROM grammar_point WHERE title_zh='有字句'"
    ).fetchone()
    examples = json.loads(point["practice_examples_json"])
    served = []
    for _ in range(len(examples)):
        client.get(
            f"/grammar/practice/card?grammar_id={point['id']}&mode=production"
        )
        plan = json.loads(db.execute(
            "SELECT plan_json FROM grammar_session WHERE id=1"
        ).fetchone()[0])
        served.append(plan["zh"])
    assert len(set(served)) == len(examples)

    client.get(
        f"/grammar/practice/card?grammar_id={point['id']}&mode=production"
    )
    next_plan = json.loads(db.execute(
        "SELECT plan_json FROM grammar_session WHERE id=1"
    ).fetchone()[0])
    assert next_plan["zh"] != served[-1]


def test_natural_chinese_variant_is_accepted():
    kind, note = _grammar_match(
        "桌子上有一本书", "桌上有一本书。", "production"
    )
    assert kind == "accepted_variant"
    assert "both natural" in note
    assert _grammar_match(
        "桌上没有一本书", "桌上有一本书。", "production"
    )[0] == "incorrect"
    kind, note = _grammar_match(
        "他有一个妹妹", "她有一个妹妹。", "production"
    )
    assert kind == "accepted_variant"
    assert "tested grammar is correct" in note
    assert "uses 她" in note
    kind, note = _grammar_match(
        "你国家的人吃米饭吗", "你们国家的人吃米饭吗？", "production"
    )
    assert kind == "accepted_variant"
    assert "more standard written form" in note
    kind, note = _grammar_match(
        "您喜欢喝茶吗？", "你喜欢喝茶吗？", "production"
    )
    assert kind == "accepted_variant"
    assert "different level of formality" in note
    kind, note = _grammar_match(
        "今天冷吗？", "今天很冷吗？", "production"
    )
    assert kind == "accepted_variant"
    assert "both natural" in note
    kind, note = _grammar_match(
        "你现在忙吗？", "你们现在忙吗？", "production"
    )
    assert kind == "accepted_variant"
    assert "singular or plural" in note
    kind, note = _grammar_match(
        "妈妈今天没上班", "妈妈今天没工作。", "production"
    )
    assert kind == "accepted_variant"
    assert "Both are natural" in note


def test_grammar_production_accepts_english_vocabulary_placeholder(client, db):
    tree_id = db.execute(
        "INSERT INTO item(headword,pinyin,gloss,hsk_bands) "
        "VALUES('树','shù','tree; to cultivate','1')"
    ).lastrowid
    grammar_id = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='有字句'"
    ).fetchone()[0]
    example = [{
        "zh": "公园里有很多树。",
        "en": "There are many trees in the park.",
    }]
    db.execute(
        "UPDATE grammar_point SET practice_examples_json=? WHERE id=?",
        (json.dumps(example, ensure_ascii=False), grammar_id),
    )
    db.execute("UPDATE learner SET declared_hsk_band=1 WHERE id=1")
    db.commit()

    card = client.get(
        f"/grammar/practice/card?grammar_id={grammar_id}&mode=production"
    )
    assert "Sentence vocabulary" in card.text
    assert "Expected known" in card.text
    assert "Add to practice" in card.text
    assert 'data-vocab-knowledge' in card.text

    answer = client.post(
        "/grammar/answer", data={"response": "公园里有很多tree"}
    )
    assert "Grammar correct · vocabulary supplied" in answer.text
    assert "tree" in answer.text
    assert "树" in answer.text
    attempt = db.execute(
        "SELECT correct,hints_used,match_kind FROM grammar_attempt "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert tuple(attempt) == (1, 1, "accepted_with_vocab_help")
    assert db.execute(
        "SELECT status FROM item_knowledge_override WHERE item_id=?", (tree_id,)
    ).fetchone()[0] == "needs_practice"
    assert db.execute(
        "SELECT COUNT(*) FROM memory_state WHERE item_id=?", (tree_id,)
    ).fetchone()[0] == 2


def test_grammar_vocabulary_uses_contextual_reading_for_mei(client, db):
    db.execute(
        "INSERT INTO item(headword,pinyin,gloss,hsk_bands) "
        "VALUES('没','mò','drowned; to end','1')"
    )
    db.commit()
    card = client.get("/grammar/practice/card?grammar_id=4&mode=production")
    assert card.status_code == 200
    vocabulary = _grammar_vocabulary(db, "他昨天没来。")
    mei = next(item for item in vocabulary if item["headword"] == "没")
    assert mei["pinyin"] == "méi"
    assert mei["gloss"] == "not; have not"
    hidden = _grammar_vocabulary(db, "他昨天没来。", {"不", "没"})
    assert not any(item["headword"] == "没" for item in hidden)


def test_manual_grammar_override(client, db):
    grammar_id = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='有字句'"
    ).fetchone()[0]
    cursor = db.execute(
        "INSERT INTO grammar_attempt(user_id,grammar_id,direction,prompt,response,"
        "correct,hints_used,ts,match_kind) VALUES(1,?,'production','test','test',"
        "0,0,'2026-01-01T00:00:00+00:00','incorrect')",
        (grammar_id,),
    )
    db.commit()
    response = client.post(f"/grammar/attempt/{cursor.lastrowid}/accept")
    assert response.status_code == 200
    attempt = db.execute(
        "SELECT correct,overridden,match_kind FROM grammar_attempt WHERE id=?",
        (cursor.lastrowid,),
    ).fetchone()
    assert tuple(attempt) == (1, 1, "manual_override")

    undone = client.post(
        f"/grammar/attempt/{cursor.lastrowid}/undo-accept"
    )
    assert undone.json() == {
        "ok": True, "correct": False, "manual_override": False
    }
    attempt = db.execute(
        "SELECT correct,overridden,match_kind FROM grammar_attempt WHERE id=?",
        (cursor.lastrowid,),
    ).fetchone()
    assert tuple(attempt) == (0, 0, "incorrect")

    queued = client.post(
        f"/grammar/attempt/{cursor.lastrowid}/request-review"
    )
    assert queued.json()["ok"] is True
    assert queued.json()["status"] == "pending"
    assert queued.json()["realtime"] is False
    assert db.execute(
        "SELECT status FROM grammar_review_request WHERE attempt_id=?",
        (cursor.lastrowid,),
    ).fetchone()[0] == "pending"
    progress = client.get("/progress")
    assert "Answers saved for a second opinion" in progress.text
    assert "test" in progress.text
    exported = client.get("/export/progress").json()
    assert exported["schema"] == 5
    assert any(
        row["attempt_id"] == cursor.lastrowid and row["status"] == "pending"
        for row in exported["grammar_review_request"]
    )
    assert any(
        row["id"] == cursor.lastrowid and row["response"] == "test"
        for row in exported["grammar_attempt"]
    )

    cancelled = client.post(
        f"/grammar/attempt/{cursor.lastrowid}/cancel-review"
    )
    assert cancelled.json() == {"ok": True, "status": "cancelled"}


def test_realtime_ai_review_repairs_score_and_tracks_cost(client, db, monkeypatch):
    grammar_id = db.execute(
        "SELECT id FROM grammar_point WHERE title_zh='有字句'"
    ).fetchone()[0]
    cursor = db.execute(
        "INSERT INTO grammar_attempt(user_id,grammar_id,direction,prompt,response,"
        "expected,correct,hints_used,ts,match_kind) VALUES(1,?,'production',"
        "'There is a book on the table.','桌子上有一本书','桌上有一本书。',"
        "0,0,'2026-01-01T00:00:00+00:00','incorrect')",
        (grammar_id,),
    )
    db.commit()
    result = AIReviewResult(
        verdict="acceptable",
        target_grammar_correct=True,
        confidence=0.96,
        explanation="桌子上 and 桌上 are both natural here.",
        suggested_answer="桌子上有一本书。",
        differences=("桌子上 is a slightly fuller location phrase.",),
        curriculum_issue=True,
        maintenance_note="Accept 桌子上 as an equivalent to 桌上.",
        provider="deepseek",
        model="deepseek-v4-flash",
        input_tokens=600,
        output_tokens=120,
        cache_hit_tokens=400,
        cache_miss_tokens=200,
        estimated_cost_usd=0.000062,
    )
    monkeypatch.setattr(web_module, "ai_review_configured", lambda: True)
    monkeypatch.setattr(
        web_module, "review_grammar_attempt", lambda attempt, point: result
    )

    response = client.post(
        f"/grammar/attempt/{cursor.lastrowid}/request-review"
    )
    assert response.json() == {
        "ok": True,
        "status": "resolved",
        "realtime": True,
        "decision": "acceptable",
        "correct": True,
    }
    attempt = db.execute(
        "SELECT correct,overridden,match_kind FROM grammar_attempt WHERE id=?",
        (cursor.lastrowid,),
    ).fetchone()
    assert tuple(attempt) == (1, 0, "ai_accepted")
    review = db.execute(
        "SELECT status,provider,model,decision,confidence,target_grammar_correct,"
        "curriculum_issue FROM grammar_review_request WHERE attempt_id=?",
        (cursor.lastrowid,),
    ).fetchone()
    assert tuple(review[:4]) == (
        "resolved", "deepseek", "deepseek-v4-flash", "acceptable"
    )
    assert review["confidence"] == 0.96
    assert review["target_grammar_correct"] == 1
    assert review["curriculum_issue"] == 1
    usage = db.execute(
        "SELECT status,input_tokens,output_tokens,estimated_cost_usd "
        "FROM ai_usage WHERE attempt_id=?", (cursor.lastrowid,)
    ).fetchone()
    assert tuple(usage[:3]) == ("ok", 600, 120)
    assert usage["estimated_cost_usd"] == 0.000062
    report = db.execute(
        "SELECT ref,note FROM bug_report WHERE ref=?",
        (f"#AI-G{grammar_id}-A{cursor.lastrowid}",),
    ).fetchone()
    assert report
    assert "Accept 桌子上" in report["note"]
    assert "DeepSeek is connected" in client.get("/settings").text
    progress = client.get("/progress")
    assert "桌子上 and 桌上 are both natural" in progress.text
    exported = client.get("/export/progress").json()
    assert exported["schema"] == 5
    assert exported["ai_usage"][0]["input_tokens"] == 600
    script = client.get("/static/grammar.js").text
    assert 'window.location.assign("/grammar-session/current")' in script
    assert "window.location.reload()" not in script
