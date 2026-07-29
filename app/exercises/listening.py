from .common import build_question


def build(conn, item_id):
    return build_question(conn, item_id, "listening")
