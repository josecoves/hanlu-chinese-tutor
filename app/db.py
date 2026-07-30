import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS item (
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'word', headword TEXT UNIQUE NOT NULL,
  pinyin TEXT NOT NULL DEFAULT '', gloss TEXT NOT NULL DEFAULT '', freq_rank INTEGER,
  hsk_bands TEXT NOT NULL DEFAULT '', measure_word TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS memory_state (
  user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, facet TEXT NOT NULL,
  difficulty REAL, stability REAL, last_review_ts TEXT, due_ts TEXT NOT NULL,
  lapses INTEGER NOT NULL DEFAULT 0, suspended INTEGER NOT NULL DEFAULT 0,
  card_json TEXT NOT NULL, seeded INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(user_id,item_id,facet), FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS review_log (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
  facet TEXT NOT NULL, exercise_type TEXT NOT NULL, grade INTEGER NOT NULL,
  latency_ms INTEGER NOT NULL DEFAULT 0, hints_used INTEGER NOT NULL DEFAULT 0,
  elapsed_days REAL, ts TEXT NOT NULL, FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS sentence (
  id INTEGER PRIMARY KEY, zh TEXT NOT NULL, pinyin TEXT NOT NULL DEFAULT '',
  en TEXT NOT NULL DEFAULT '', audio_path TEXT, source TEXT NOT NULL DEFAULT '',
  validated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sentence_token (
  sentence_id INTEGER NOT NULL, item_id INTEGER NOT NULL, position INTEGER NOT NULL,
  PRIMARY KEY(sentence_id,item_id,position),
  FOREIGN KEY(sentence_id) REFERENCES sentence(id), FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS learner (
  id INTEGER PRIMARY KEY, declared_hsk_band INTEGER NOT NULL DEFAULT 0,
  streak INTEGER NOT NULL DEFAULT 0, settings_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS session (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE, plan_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_topic (
  item_id INTEGER NOT NULL, topic TEXT NOT NULL, PRIMARY KEY(item_id,topic),
  FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE INDEX IF NOT EXISTS idx_topic ON item_topic(topic);
CREATE TABLE IF NOT EXISTS item_preference (
  user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, snoozed_until TEXT,
  PRIMARY KEY(user_id,item_id), FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS item_knowledge_override (
  user_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('needs_practice')),
  updated_ts TEXT NOT NULL,
  PRIMARY KEY(user_id,item_id), FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS bug_report (
  id INTEGER PRIMARY KEY, ref TEXT NOT NULL DEFAULT '', note TEXT NOT NULL, ts TEXT NOT NULL,
  resolved INTEGER NOT NULL DEFAULT 0, resolved_ts TEXT, context TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS story (
  id INTEGER PRIMARY KEY, title_zh TEXT NOT NULL, title_en TEXT NOT NULL,
  sentences_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS story_state (
  user_id INTEGER NOT NULL, story_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'new', current_index INTEGER NOT NULL DEFAULT 0,
  updated_ts TEXT NOT NULL,
  PRIMARY KEY(user_id,story_id), FOREIGN KEY(story_id) REFERENCES story(id)
);
CREATE TABLE IF NOT EXISTS story_sentence_progress (
  user_id INTEGER NOT NULL, story_id INTEGER NOT NULL,
  sentence_index INTEGER NOT NULL, completed_ts TEXT NOT NULL,
  PRIMARY KEY(user_id,story_id,sentence_index),
  FOREIGN KEY(story_id) REFERENCES story(id)
);
CREATE TABLE IF NOT EXISTS story_word_exposure (
  user_id INTEGER NOT NULL, story_id INTEGER NOT NULL,
  sentence_index INTEGER NOT NULL, item_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'studied', updated_ts TEXT NOT NULL,
  PRIMARY KEY(user_id,story_id,sentence_index,item_id),
  FOREIGN KEY(story_id) REFERENCES story(id), FOREIGN KEY(item_id) REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS grammar_point (
  id INTEGER PRIMARY KEY, level INTEGER NOT NULL, title_zh TEXT NOT NULL,
  title_en TEXT NOT NULL, pattern TEXT NOT NULL, explanation TEXT NOT NULL,
  examples_json TEXT NOT NULL, theory_examples_json TEXT NOT NULL DEFAULT '[]',
  practice_examples_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS grammar_attempt (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, grammar_id INTEGER NOT NULL,
  direction TEXT NOT NULL, prompt TEXT NOT NULL, response TEXT NOT NULL,
  expected TEXT NOT NULL DEFAULT '',
  correct INTEGER NOT NULL, hints_used INTEGER NOT NULL DEFAULT 0, ts TEXT NOT NULL,
  overridden INTEGER NOT NULL DEFAULT 0, match_kind TEXT NOT NULL DEFAULT 'exact',
  FOREIGN KEY(grammar_id) REFERENCES grammar_point(id)
);
CREATE TABLE IF NOT EXISTS grammar_review_request (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, attempt_id INTEGER NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','resolved','cancelled')),
  requested_ts TEXT NOT NULL, resolved_ts TEXT, decision TEXT NOT NULL DEFAULT '',
  explanation TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0,
  target_grammar_correct INTEGER NOT NULL DEFAULT 0,
  suggested_answer TEXT NOT NULL DEFAULT '', differences_json TEXT NOT NULL DEFAULT '[]',
  curriculum_issue INTEGER NOT NULL DEFAULT 0,
  maintenance_note TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(attempt_id) REFERENCES grammar_attempt(id)
);
CREATE TABLE IF NOT EXISTS ai_usage (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, attempt_id INTEGER,
  provider TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_hit_tokens INTEGER NOT NULL DEFAULT 0,
  cache_miss_tokens INTEGER NOT NULL DEFAULT 0,
  estimated_cost_usd REAL NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
  ts TEXT NOT NULL,
  FOREIGN KEY(attempt_id) REFERENCES grammar_attempt(id)
);
CREATE TABLE IF NOT EXISTS grammar_state (
  user_id INTEGER NOT NULL, grammar_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_started', updated_ts TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  PRIMARY KEY(user_id,grammar_id), FOREIGN KEY(grammar_id) REFERENCES grammar_point(id)
);
CREATE TABLE IF NOT EXISTS grammar_session (
  id INTEGER PRIMARY KEY, plan_json TEXT NOT NULL
);
"""

MIGRATIONS = {
    "item": {"measure_word": "TEXT NOT NULL DEFAULT ''"},
    "memory_state": {"seeded": "INTEGER NOT NULL DEFAULT 0"},
    "bug_report": {"resolved_ts": "TEXT", "context": "TEXT NOT NULL DEFAULT ''"},
    "grammar_point": {
        "theory_examples_json": "TEXT NOT NULL DEFAULT '[]'",
        "practice_examples_json": "TEXT NOT NULL DEFAULT '[]'",
    },
    "grammar_attempt": {
        "overridden": "INTEGER NOT NULL DEFAULT 0",
        "match_kind": "TEXT NOT NULL DEFAULT 'exact'",
        "expected": "TEXT NOT NULL DEFAULT ''",
    },
    "grammar_review_request": {
        "provider": "TEXT NOT NULL DEFAULT ''",
        "model": "TEXT NOT NULL DEFAULT ''",
        "confidence": "REAL NOT NULL DEFAULT 0",
        "target_grammar_correct": "INTEGER NOT NULL DEFAULT 0",
        "suggested_answer": "TEXT NOT NULL DEFAULT ''",
        "differences_json": "TEXT NOT NULL DEFAULT '[]'",
        "curriculum_issue": "INTEGER NOT NULL DEFAULT 0",
        "maintenance_note": "TEXT NOT NULL DEFAULT ''",
    },
    "grammar_state": {
        "source": "TEXT NOT NULL DEFAULT 'manual'",
    },
}


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for table, columns in MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    conn.execute(
        "INSERT OR IGNORE INTO learner(id,declared_hsk_band,streak,settings_json) "
        "VALUES(1,0,0,'{\"daily_new_items\":10,\"desired_retention\":0.9}')"
    )
    conn.commit()
