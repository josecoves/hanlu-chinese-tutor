import json
from datetime import datetime, timezone
from .models import Item, Sentence


def item_from_row(row) -> Item:
    return Item(**{key: row[key] for key in Item.__dataclass_fields__})


def get_item(conn, item_id: int) -> Item | None:
    row = conn.execute("SELECT * FROM item WHERE id=?", (item_id,)).fetchone()
    return item_from_row(row) if row else None


def get_sentence_for_item(conn, item_id: int) -> Sentence | None:
    row = conn.execute(
        "SELECT s.* FROM sentence s JOIN sentence_token st ON st.sentence_id=s.id "
        "WHERE st.item_id=? ORDER BY s.validated DESC, RANDOM() LIMIT 1", (item_id,)
    ).fetchone()
    return Sentence(**dict(row)) if row else None


def learner_settings(conn) -> dict:
    row = conn.execute("SELECT settings_json FROM learner WHERE id=1").fetchone()
    defaults = {"daily_new_items": 10, "desired_retention": 0.9}
    if row:
        defaults.update(json.loads(row["settings_json"] or "{}"))
    return defaults


def practice_count(conn, item_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM review_log WHERE user_id=1 AND item_id=?", (item_id,)
    ).fetchone()[0]


def due_count(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM memory_state WHERE user_id=1 AND suspended=0 AND due_ts<=?",
        (datetime.now(timezone.utc).isoformat(),)
    ).fetchone()[0]
