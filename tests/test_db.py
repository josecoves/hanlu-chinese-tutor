from app import repo


def test_item_and_sentence_round_trip(db):
    item = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()
    loaded = repo.get_item(db, item["id"])
    sentence = repo.get_sentence_for_item(db, item["id"])
    assert loaded.gloss == "tea"
    assert sentence.en == "I like drinking tea."
