from datetime import datetime, timezone
from . import config


def build_filtered(conn, *, topic: str | None = None, hsk: int = 0,
                   practice: str = "all", q: str = "", limit: int = 20) -> list[list]:
    """Build a practice queue that matches the visible vocabulary filters."""
    now = datetime.now(timezone.utc).isoformat()
    joins = " JOIN item_topic it ON it.item_id=i.id " if topic else ""
    conditions = [
        "EXISTS(SELECT 1 FROM sentence_token st WHERE st.item_id=i.id)",
        "NOT EXISTS(SELECT 1 FROM item_preference ip WHERE ip.user_id=1 "
        "AND ip.item_id=i.id AND ip.snoozed_until>?)",
    ]
    params = [now]
    if topic:
        conditions.append("it.topic=?")
        params.append(topic)
    if hsk in (1, 2, 3):
        conditions.append("(',' || i.hsk_bands || ',') LIKE ?")
        params.append(f"%,{hsk},%")
    if practice == "unpracticed":
        conditions.append(
            "NOT EXISTS(SELECT 1 FROM review_log rp WHERE rp.user_id=1 "
            "AND rp.item_id=i.id)"
        )
    elif practice == "practiced":
        conditions.append(
            "EXISTS(SELECT 1 FROM review_log rp WHERE rp.user_id=1 "
            "AND rp.item_id=i.id)"
        )
    if q.strip():
        conditions.append("(i.headword LIKE ? OR i.pinyin LIKE ? OR i.gloss LIKE ?)")
        needle = f"%{q.strip()}%"
        params.extend((needle, needle, needle))
    params.append(max(1, min(50, limit)))
    rows = conn.execute(
        "SELECT DISTINCT i.id,CASE WHEN EXISTS(SELECT 1 FROM review_log rl "
        "WHERE rl.user_id=1 AND rl.item_id=i.id) THEN 'listening' "
        "ELSE 'reading-recognition' END facet FROM item i " + joins +
        " WHERE " + " AND ".join(conditions) + " ORDER BY RANDOM() LIMIT ?",
        tuple(params),
    ).fetchall()
    return [[row["id"], row["facet"]] for row in rows]


def build(conn, *, topic: str | None = None, hsk: int = 0,
          reviews_only=False) -> list[list]:
    now = datetime.now(timezone.utc).isoformat()
    params = [now]
    topic_join = ""
    topic_where = ""
    if topic:
        topic_join = " JOIN item_topic it ON it.item_id=i.id "
        topic_where = " AND it.topic=? "
        params.append(topic)
    due = conn.execute(
        "SELECT ms.item_id,ms.facet FROM memory_state ms JOIN item i ON i.id=ms.item_id "
        + topic_join +
        "WHERE ms.user_id=1 AND ms.suspended=0 AND ms.due_ts<=? " + topic_where +
        "AND NOT EXISTS(SELECT 1 FROM item_preference ip WHERE ip.user_id=1 "
        "AND ip.item_id=i.id AND ip.snoozed_until>?) "
        "AND EXISTS(SELECT 1 FROM sentence_token st WHERE st.item_id=i.id) "
        "ORDER BY ms.due_ts LIMIT ?", (*params, now, config.DAILY_REVIEW_CAP)
    ).fetchall()
    queue = [[r["item_id"], r["facet"]] for r in due]
    if reviews_only:
        return queue
    if topic:
        level_where = (
            " AND (',' || i.hsk_bands || ',') LIKE ? " if hsk in (1, 2, 3) else ""
        )
        level_params = (f"%,{hsk},%",) if level_where else ()
        rows = conn.execute(
            "SELECT DISTINCT i.id, CASE WHEN EXISTS(SELECT 1 FROM review_log rl "
            "WHERE rl.item_id=i.id) THEN 'listening' ELSE 'reading-recognition' END facet "
            "FROM item i JOIN item_topic it ON it.item_id=i.id "
            "WHERE it.topic=? AND EXISTS(SELECT 1 FROM sentence_token st WHERE st.item_id=i.id) "
            + level_where +
            "AND NOT EXISTS(SELECT 1 FROM item_preference ip WHERE ip.user_id=1 "
            "AND ip.item_id=i.id AND ip.snoozed_until>?) "
            "ORDER BY RANDOM() LIMIT 20", (topic, *level_params, now)
        ).fetchall()
        return [[r["id"], r["facet"]] for r in rows]
    budget = int(__import__("json").loads(
        conn.execute("SELECT settings_json FROM learner WHERE id=1").fetchone()[0]
    ).get("daily_new_items", config.DAILY_NEW_ITEMS))
    seen = {x[0] for x in queue}
    new_rows = conn.execute(
        "SELECT i.id FROM item i WHERE NOT EXISTS("
        "SELECT 1 FROM memory_state ms WHERE ms.item_id=i.id AND ms.user_id=1) "
        "AND NOT EXISTS(SELECT 1 FROM item_preference ip WHERE ip.user_id=1 "
        "AND ip.item_id=i.id AND ip.snoozed_until>?) "
        "AND EXISTS(SELECT 1 FROM sentence_token st WHERE st.item_id=i.id) "
        "ORDER BY CAST(substr(i.hsk_bands,1,1) AS INTEGER), RANDOM() LIMIT ?", (now, budget)
    ).fetchall()
    queue.extend([[r["id"], "reading-recognition"] for r in new_rows if r["id"] not in seen])
    return queue
