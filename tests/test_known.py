from app.web import _known_headwords


def test_declared_band_counts_as_known(db):
    db.execute("UPDATE learner SET declared_hsk_band=1 WHERE id=1")
    db.commit()
    known = _known_headwords(db)
    assert {"茶", "水", "饭", "书"} <= known


def test_failed_review_does_not_count_as_known(db):
    item_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    db.execute(
        "INSERT INTO review_log(user_id,item_id,facet,exercise_type,grade,ts) "
        "VALUES(1,?,'reading-recognition','reading-recognition',1,'2026-01-01')",
        (item_id,),
    )
    db.commit()
    assert "茶" not in _known_headwords(db)
    db.execute(
        "INSERT INTO review_log(user_id,item_id,facet,exercise_type,grade,ts) "
        "VALUES(1,?,'reading-recognition','reading-recognition',3,'2026-01-02')",
        (item_id,),
    )
    db.commit()
    assert "茶" in _known_headwords(db)


def test_latest_hard_result_overrides_declared_level(db):
    db.execute("UPDATE learner SET declared_hsk_band=1 WHERE id=1")
    item_id = db.execute("SELECT id FROM item WHERE headword='茶'").fetchone()[0]
    db.execute(
        "INSERT INTO review_log(user_id,item_id,facet,exercise_type,grade,ts) "
        "VALUES(1,?,'reading-recognition','story-context',1,'2026-02-01')",
        (item_id,),
    )
    db.commit()
    assert "茶" not in _known_headwords(db)
