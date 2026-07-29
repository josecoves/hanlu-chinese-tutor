import json
from datetime import datetime, timedelta, timezone
from .scheduler import new_state


def apply_declaration(conn, band: int) -> None:
    now = datetime.now(timezone.utc)
    if band >= 0:
        rows = conn.execute("SELECT id,hsk_bands FROM item").fetchall()
        for row in rows:
            levels = [int(x) for x in row["hsk_bands"].split(",") if x.isdigit()]
            if levels and min(levels) <= band:
                for facet in ("listening", "reading-recognition"):
                    card = new_state(now)
                    card.update({"stability": 2.0, "difficulty": 5.0,
                                 "due": (now + timedelta(days=2)).isoformat()})
                    conn.execute(
                        "INSERT OR IGNORE INTO memory_state "
                        "(user_id,item_id,facet,difficulty,stability,last_review_ts,due_ts,"
                        "lapses,suspended,card_json,seeded) VALUES(1,?,?,?,?,?,?,?,?,?,1)",
                        (row["id"], facet, 5.0, 2.0, None, card["due"], 0, 0,
                         json.dumps(card)),
                    )
    conn.execute("UPDATE learner SET declared_hsk_band=? WHERE id=1", (band,))
    conn.execute(
        "DELETE FROM memory_state WHERE seeded=1 AND item_id IN ("
        "SELECT ms.item_id FROM memory_state ms JOIN item i ON i.id=ms.item_id "
        "LEFT JOIN review_log rl ON rl.item_id=ms.item_id AND rl.user_id=1 "
        "WHERE CAST(substr(i.hsk_bands,1,1) AS INTEGER)>? "
        "GROUP BY ms.item_id HAVING COUNT(rl.id)=0)", (band,)
    )
    conn.commit()
