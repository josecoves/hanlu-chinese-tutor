from datetime import datetime, timezone
from app.grading import rating_for
from app.scheduler import new_state, review, retrievability


def test_fsrs_review_round_trip():
    now = datetime.now(timezone.utc)
    state = new_state(now)
    updated = review(state, 3, now)
    assert updated["last_review"] is not None
    assert updated["due"] > updated["last_review"]
    assert 0 <= retrievability(updated, now) <= 1


def test_latency_grading():
    assert rating_for(False, 100) == 1
    assert rating_for(True, 10000) == 2
    assert rating_for(True, 5000) == 3
    assert rating_for(True, 1000) == 4
