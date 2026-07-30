# 汉路 · Chinese Tutor

A private, local-first Chinese practice app built with FastAPI, SQLite, FSRS, and
server-rendered HTML.

## Start

```bash
./run.sh
```

The first start builds the local content database and restores the supplied progress
export. Open <http://127.0.0.1:8000>.

To pre-cache every practice sentence, story sentence, grammar example, and
vocabulary pronunciation for fully offline practice:

```bash
.venv/bin/python -m scripts.generate_audio --all
```

The command is resumable: clips already on disk are reused rather than
downloaded again. Use `--limit 200` instead for a smaller practice-and-story
cache.

Contextual sentence pairs can be refreshed from Tatoeba with:

```bash
.venv/bin/python -m scripts.import_tatoeba
```

## Grammar practice

The bundled curriculum includes 48 HSK 1 lessons and 36 HSK 2 lessons aligned
to the beginner grammar framework in GF 0025–2021, plus a six-lesson HSK 3
starter set. Every lesson begins as **New**. Change it to **Practicing**
to include it in mixed grammar practice, or **Learned** to remove it from that
pool while preserving the lesson and its accuracy history. Status dropdowns
save automatically from the curriculum grid and lesson pages. Lesson pages also
offer next-in-order, next-not-started, next-practicing, and next-learned
navigation. Starting practice from a lesson page keeps every following card
focused on that lesson.

An untouched lesson becomes **Practicing** after its first attempt. An
automatically managed lesson becomes **Learned** after at least eight attempts
at 85% accuracy. Any status chosen manually remains under the learner's control,
so focused practice is never silently removed after a deliberate change.

Lesson guides separate structures, usage notes, and common pitfalls instead of
showing only a short definition. Every grammar example provides optional pinyin
and on-demand Mandarin audio; generated audio is cached locally after first use.

Practice screens support number keys `1`–`4`, `0` for “I don’t know,” `A` for
audio, `P` for pinyin, `W` for word meaning, `T` for translation, and
`Enter`/`→` for the next card when those controls are available.

After a production answer, **Explain / verify with AI** requests an optional
second opinion from DeepSeek. The review judges the lesson's target grammar
separately from incidental vocabulary, punctuation, register, and natural
alternatives. A confident accepted answer repairs its score automatically; a
grader or curriculum problem also creates a maintenance report. Uncertain
reviews never change the score. The result stays attached to the attempt in
Progress, and Settings shows aggregate calls, tokens, estimated cost, and
failures.

To enable local AI review, create `.env.local` from the safe template and add a
DeepSeek API key:

```bash
cp .env.example .env.local
code .env.local
```

Restart `./run.sh` after saving the key. `.env.local` is ignored by Git and the
key is never included in progress exports. Exercise text sent for a review does
leave the laptop and is processed by DeepSeek; all other practice remains
local. Without a key or internet connection, the same button saves the attempt
to the existing offline review queue.

Grammar questions also provide **Skip & flag this sentence**. It creates a
maintenance report, records no attempt or penalty, and immediately selects a
different sentence from the same practice scope. The detailed report form
remains available when the learner wants to explain a problem without leaving
the current card.

Theory and practice use separate saved example pools: at least five examples
appear in each lesson guide and at least ten different examples are randomized
in practice. Production grading normalizes punctuation and accepts known natural
variants such as `桌上` / `桌子上`. Rejected production answers show a character
comparison and can be manually marked correct. Focused practice provides
separate links back to its lesson or to the grammar index. The curriculum can be
searched and filtered by HSK level or learning status.

## Vocabulary and review

The app preserves the exact sentence shown on a question through its answer
reveal. “Show detailed word meaning” provides a primary learner-friendly
definition, fuller dictionary senses, usage notes and alternatives where known,
local example sentences, and a direct MDBG lookup. The short translation panel
remains a quick word-by-word gloss.

Words that are not a current priority can be paused for one week or 30 days from
either side of a review card. Paused words are excluded from new, due, and topic
queues until the selected date.

The Topics page breaks every topic into HSK 1, 2, and 3 progress. Known-word
percentages include the learner’s declared starting level plus words answered
correctly. It shows the loaded inventory (506 HSK 1 and 755 HSK 2 words), and
each available topic band links directly to its filtered word list and practice
queue. Each topic also recommends the lowest incomplete available band. Bands
without bundled vocabulary are labeled unavailable rather than shown as false
0% scores.

Vocabulary tables default to HSK-level order and use a distinct badge color for
each HSK band. Search, HSK, and practiced/not-practiced filters can be combined
on the main Vocabulary page or inside a topic. Optional sorting by Hanzi, most
practiced, or most recently practiced is also available. “Practice this
filtered set” creates a session from only the matching vocabulary, preserving
the active topic, HSK, practice-status, and search filters.

Vocabulary and topic tables include a one-click **Needs practice** control.
Flagging a word immediately removes it from known-progress totals and makes
both reading and listening memory due for review. The table combines those two
memory scores into one column and combines practice count with last activity
for a larger, more compact layout.

## Story learning

The library contains twelve original HSK 1–2 stories with New, Reading, and
Finished states, sentence-level progress, and automatic resume. Moving forward
from a sentence records its tracked vocabulary as contextual study and places
new words into spaced review. Every word is marked studied by default; toggle
only the words that still feel hard. A hard word becomes due for focused review
and is not counted as known until a later successful result.

The reader keeps its existing character, pinyin, translation, listening-mode,
and audio shortcuts. Missing story audio is generated and cached on demand.
Story status, completed sentences, and per-word study decisions are included in
the progress export.

## Test

```bash
.venv/bin/pytest
```

## Hosted beta

The `hosted/` directory contains a separate Cloudflare-compatible public
curriculum preview with the full HSK 1–2 vocabulary, story library, and grammar
curriculum. It does not upload or reuse the local learner database. Durable
account-based progress will be added as a separate hosted capability.

## Content and progress

The bundled vocabulary definitions come from the Complete HSK Vocabulary dataset
(see `content/vendor/complete-hsk-LICENSE`). Common readings and everyday senses
are selected ahead of surname, variant, and archaic entries; targeted learner
notes correct ambiguous cases such as `开学` and `院`. MDBG links provide a
convenient external cross-check. Topic labels and the personal progress
export came from the files supplied for this reconstruction. Context sentences sourced
from Tatoeba are marked `Tatoeba (CC BY 2.0)` in the local database. Runtime use is
offline. Grammar explanations and examples are original to this project; the curriculum
scope follows the published GF 0025–2021 grammar outline. Chinese Grammar Wiki
was used as a structural reference for organizing multi-case lessons, not as a
source of copied lesson text or examples.

## Publishing to GitHub

This project is released under the [MIT License](LICENSE). Personal progress,
the SQLite database, generated audio, build artifacts, virtual environments,
and local secrets are excluded by `.gitignore`.

To adapt the same local-first product for a different learner, start with the
[Spanish tutor fork prompt](SPANISH_FORK_PROMPT.md). It preserves Hanlu's
workflows while replacing Chinese-specific HSK, character, and pinyin concepts
with a Spanish CEFR and morphology model.
