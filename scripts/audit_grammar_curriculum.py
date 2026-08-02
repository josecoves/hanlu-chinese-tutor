"""Audit the seeded grammar pools against curriculum-order guarantees."""

from __future__ import annotations

import json
import argparse
import re

from app.config import DB_PATH
from app.db import connect
from app.grammar import GRAMMAR_POINTS
from app.grammar_curriculum import future_dependencies
from app.grammar_examples import GENERAL_STRUCTURE_LESSONS, _matches, vocabulary_profile


def curriculum_order() -> dict[str, tuple[int, int]]:
    numbers: dict[int, int] = {}
    order = {}
    for level, title_zh, *_rest in GRAMMAR_POINTS:
        numbers[level] = numbers.get(level, 0) + 1
        order[title_zh] = (level, numbers[level])
    return order


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()
    conn = connect(args.db)
    order = curriculum_order()
    bands = {}
    for item in conn.execute(
        "SELECT headword,hsk_bands FROM item WHERE kind='word'"
    ):
        levels = [
            int(value) for value in item["hsk_bands"].split(",")
            if value.isdigit()
        ]
        if levels:
            bands[item["headword"]] = min(levels)
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
        for example in practice:
            if not _matches(row["title_zh"], example["zh"]):
                failures.append(
                    f"{row['title_zh']} practice is not targeted: {example['zh']}"
                )
        if row["title_zh"] not in GENERAL_STRUCTURE_LESSONS:
            for example in theory:
                if not _matches(row["title_zh"], example["zh"]):
                    failures.append(
                        f"{row['title_zh']} theory is not targeted: {example['zh']}"
                    )

        for pool_name, examples in (("theory", theory), ("practice", practice)):
            for example in examples:
                hanzi_count = len(re.findall(r"[\u3400-\u9fff]", example["zh"]))
                length_limit = 16 if row["level"] == 1 else 22
                if hanzi_count > length_limit:
                    failures.append(
                        f"{row['title_zh']} {pool_name} is too long: {example['zh']}"
                    )
                vocab_level, unknown = vocabulary_profile(example["zh"], bands)
                if vocab_level > min(3, row["level"] + 1):
                    failures.append(
                        f"{row['title_zh']} {pool_name} uses HSK {vocab_level} "
                        f"vocabulary: {example['zh']}"
                    )
                unknown_limit = 3 if row["level"] <= 2 else 4
                if unknown > unknown_limit:
                    failures.append(
                        f"{row['title_zh']} {pool_name} has {unknown} unknown "
                        f"characters: {example['zh']}"
                    )
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
