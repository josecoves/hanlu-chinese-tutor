import argparse
from app import config
from app.content import bootstrap_content, restore_progress
from app.db import connect, init_schema


def main():
    parser = argparse.ArgumentParser(description="Build Chinese Tutor content")
    parser.add_argument("--refresh", action="store_true", help="rebuild content, keeping progress")
    parser.add_argument("--reset", action="store_true", help="erase all local data")
    parser.add_argument("--yes", action="store_true", help="confirm destructive reset")
    parser.add_argument("--real", action="store_true", help="use bundled complete HSK data")
    args = parser.parse_args()
    if args.reset and not args.yes:
        raise SystemExit("RESET ERASES ALL PROGRESS. Re-run with --reset --yes to confirm.")
    if args.reset and config.DB_PATH.exists():
        config.DB_PATH.unlink()
    conn = connect(config.DB_PATH)
    init_schema(conn)
    if args.refresh:
        conn.execute("DELETE FROM session")
        conn.execute("DELETE FROM sentence_token")
        conn.execute("DELETE FROM sentence")
        conn.execute("DELETE FROM item_topic")
        conn.execute("DELETE FROM story")
        conn.execute("DELETE FROM item WHERE id NOT IN (SELECT DISTINCT item_id FROM memory_state)")
        conn.commit()
    bootstrap_content(conn)
    result = restore_progress(conn)
    print(f"Ready: {conn.execute('SELECT COUNT(*) FROM item').fetchone()[0]} words; "
          f"restored {result['memory']} memory states and {result['reviews']} reviews.")
    conn.close()


if __name__ == "__main__":
    main()
