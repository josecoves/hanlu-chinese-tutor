import json

from app import config
from app.content import clean_gloss, preferred_form


def test_common_dictionary_form_beats_surname_and_rare_reading():
    rows = {row["s"]: row for row in json.loads(config.HSK_PATH.read_text())}
    expected = {
        "三": ("sān", "three; 3"),
        "上": ("shàng", "up; upper"),
        "书": ("shū", "book; letter"),
        "家": ("jiā", "home; family"),
        "开学": ("kāi xué", "school begins; start of a school term"),
    }
    for word, (pinyin, gloss) in expected.items():
        form = preferred_form(rows[word], word)
        assert form["i"]["y"] == pinyin
        assert clean_gloss(form["m"], word) == gloss
