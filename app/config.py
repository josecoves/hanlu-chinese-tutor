from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "tutor.db"
TOPIC_LABELS_PATH = DATA_DIR / "topic_labels.json"
PROGRESS_PATH = DATA_DIR / "progress_export.json"
HSK_PATH = ROOT / "content" / "vendor" / "complete-hsk.min.json"
CONTEXT_SENTENCES_PATH = ROOT / "content" / "context_sentences.json"

USER_ID = 1
FACETS = ("listening", "reading-recognition")
DESIRED_RETENTION = 0.90
DAILY_REVIEW_CAP = 50
DAILY_NEW_ITEMS = 10
LEECH_LAPSES = 8
BUG_RESOLVED_RETENTION_DAYS = 3

TOPICS = (
    "Greetings & social", "Numbers & time", "Family & people", "Food & drink",
    "Shopping & money", "Travel & transport", "Directions & places",
    "Home & daily life", "Work & study", "Health & body", "Weather & nature",
    "Hobbies & leisure", "Clothing & appearance", "Communication & tech",
    "Feelings & descriptions", "Core / Function",
)
