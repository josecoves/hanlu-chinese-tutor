import json
from app.config import DB_PATH, PROGRESS_PATH
from app.db import connect
from app.web import _progress_payload


def main():
    conn = connect(DB_PATH)
    PROGRESS_PATH.write_text(json.dumps(_progress_payload(conn), ensure_ascii=False, indent=2))
    conn.close()
    print(PROGRESS_PATH)


if __name__ == "__main__":
    main()
