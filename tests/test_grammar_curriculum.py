import json

from app.grammar import GRAMMAR_POINTS
from app.grammar_curriculum import (
    RECOMMENDED_EARLY,
    future_dependencies,
    grammar_dependencies,
)
from app.grammar_examples import CURATED_PRACTICE_SETS, _matches


def _curriculum_order():
    numbers = {}
    order = {}
    for level, title_zh, *_rest in GRAMMAR_POINTS:
        numbers[level] = numbers.get(level, 0) + 1
        order[title_zh] = (level, numbers[level])
    return order


def test_dependency_detection_finds_material_later_structures():
    assert "进行体" in grammar_dependencies("我正在和朋友打电话呢。")
    assert "是的强调句" in grammar_dependencies("我是在北京学习中文的。")
    assert "把字句" in grammar_dependencies("请把门打开。")
    assert "一边一边" in grammar_dependencies("她一边走路，一边打电话。")
    assert "除了以外" in grammar_dependencies("我除了星期天外每天都上班。")


def test_dependency_detection_avoids_common_false_positives():
    assert "补语入门" not in grammar_dependencies("我马上回来。")
    assert "补语入门" not in grammar_dependencies("商店从九点开到六点。")
    assert "是的强调句" not in grammar_dependencies("这是我的书。")
    assert "都已经了" not in grammar_dependencies("水果什么的都买好了。")


def test_future_dependency_comparison_uses_lesson_order():
    order = _curriculum_order()
    point = {
        "level": 1,
        "lesson_number": 6,
        "title_zh": "在和位置",
    }
    assert future_dependencies("我正在学习。", point, order) == ("进行体",)
    assert future_dependencies("我在学校学习。", point, order) == ()


def test_seeded_examples_are_tagged_and_respect_curriculum_order(db):
    order = _curriculum_order()
    for point in db.execute(
        "SELECT level,title_zh,theory_examples_json,practice_examples_json "
        "FROM grammar_point"
    ):
        current = order[point["title_zh"]]
        point_context = {
            **dict(point),
            "lesson_number": current[1],
        }
        for column in ("theory_examples_json", "practice_examples_json"):
            for example in json.loads(point[column]):
                assert "grammar_dependencies" in example
                assert not future_dependencies(
                    example["zh"], point_context, order
                ), (point["title_zh"], example["zh"])


def test_recommended_path_is_limited_to_foundational_lessons():
    assert "在和位置" in RECOMMENDED_EARLY
    assert "进行体" in RECOMMENDED_EARLY
    assert "的字短语作名词" in RECOMMENDED_EARLY
    assert "是的强调句" not in RECOMMENDED_EARLY
    assert "把字句" not in RECOMMENDED_EARLY
    assert len(RECOMMENDED_EARLY) < 24


def test_every_lesson_keeps_theory_and_practice_distinct(db):
    for point in db.execute(
        "SELECT title_zh,theory_examples_json,practice_examples_json "
        "FROM grammar_point"
    ):
        theory = json.loads(point["theory_examples_json"])
        practice = json.loads(point["practice_examples_json"])
        assert practice, point["title_zh"]
        assert {example["zh"] for example in theory}.isdisjoint(
            {example["zh"] for example in practice}
        ), point["title_zh"]


def test_repaired_practice_pools_are_targeted_and_attributed(db):
    for title in CURATED_PRACTICE_SETS:
        row = db.execute(
            "SELECT practice_examples_json FROM grammar_point WHERE title_zh=?",
            (title,),
        ).fetchone()
        practice = json.loads(row["practice_examples_json"])
        assert practice, title
        assert all(example.get("source") for example in practice), title
        assert all(_matches(title, example["zh"]) for example in practice), title
