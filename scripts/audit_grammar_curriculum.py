"""Audit the seeded grammar pools against curriculum-order guarantees."""

from __future__ import annotations

import json

from app.config import DB_PATH
from app.db import connect
from app.grammar import GRAMMAR_POINTS
from app.grammar_curriculum import future_dependencies
from app.grammar_examples import _matches


def curriculum_order() -> dict[str, tuple[int, int]]:
    numbers: dict[int, int] = {}
    order = {}
    for level, title_zh, *_rest in GRAMMAR_POINTS:
        numbers[level] = numbers.get(level, 0) + 1
        order[title_zh] = (level, numbers[level])
    return order


def main() -> None:
    conn = connect(DB_PATH)
    order = curriculum_order()
    failures = []
    lesson_count = 0
    practice_count = 0

    for row in conn.execute(
        "SELECT level,title_zh,theory_examples_json,practice_examples_json "
        "FROM grammar_point ORDER BY level,id"
    ):
        lesson_count += 1
        point = {
            **dict(row),
            "lesson_number": order[row["title_zh"]][1],
        }
        theory = json.loads(row["theory_examples_json"])
        practice = json.loads(row["practice_examples_json"])
        practice_count += len(practice)
        theory_zh = {example["zh"] for example in theory}
        practice_zh = {example["zh"] for example in practice}

        if len(theory) < 5:
            failures.append(f"{row['title_zh']}: fewer than 5 theory examples")
        if len(practice) < 10:
            failures.append(f"{row['title_zh']}: fewer than 10 practice examples")
        if theory_zh & practice_zh:
            failures.append(f"{row['title_zh']}: theory/practice duplicate")
        if sum(_matches(row["title_zh"], item["zh"]) for item in practice) < 10:
            failures.append(f"{row['title_zh']}: fewer than 10 targeted examples")

        for pool_name, examples in (("theory", theory), ("practice", practice)):
            for example in examples:
                future = future_dependencies(example["zh"], point, order)
                if future:
                    failures.append(
                        f"{row['title_zh']} {pool_name}: {example['zh']} "
                        f"requires {', '.join(future)}"
                    )

    conn.close()
    if failures:
        raise SystemExit(
            "Grammar curriculum audit failed:\n- " + "\n- ".join(failures)
        )
    print(
        f"Grammar curriculum audit passed: {lesson_count} lessons, "
        f"{practice_count} ordered practice examples."
    )


if __name__ == "__main__":
    main()
