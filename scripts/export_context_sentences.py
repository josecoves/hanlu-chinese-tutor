import json
from app import config
from app.db import connect


def main():
    conn = connect(config.DB_PATH)
    rows = conn.execute(
        "SELECT i.headword word,s.zh,s.en,s.source FROM sentence s "
        "JOIN sentence_token st ON st.sentence_id=s.id "
        "JOIN item i ON i.id=st.item_id "
        "WHERE s.source IN ('Tatoeba (CC BY 2.0)','authored contextual fallback') "
        "ORDER BY i.headword,s.id"
    ).fetchall()
    config.CONTEXT_SENTENCES_PATH.write_text(
        json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Exported {len(rows)} contextual links to {config.CONTEXT_SENTENCES_PATH}.")
    conn.close()


if __name__ == "__main__":
    main()
