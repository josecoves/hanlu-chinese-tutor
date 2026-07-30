# Copy-paste prompt: build a local Spanish tutor from Hanlu

Paste the prompt below into a new Codex task on the computer where the Spanish
tutor should live.

---

I want you to build a separate, local-first Spanish learning app by adapting
the open-source Hanlu Chinese Tutor:

https://github.com/josecoves/hanlu-chinese-tutor

First clone or fork that repository into a new project. Use Hanlu as the product,
interaction, and architecture reference, but do not merely translate its Chinese
content. Preserve its strongest workflows while redesigning the language model
for Spanish.

## Learner and product assumptions

- The learner is a native speaker of English and Chinese.
- Use English as the interface, instruction, explanation, and translation
  language. Chinese-language explanations are not required.
- The app should run locally on the learner's computer and keep progress in a
  local SQLite database.
- Keep the source code available in a separate GitHub repository so it can
  eventually become open source.
- Do not deploy a hosted version unless I explicitly request it.
- Never commit personal progress, generated audio, local databases, environment
  files, or API keys.

## Preserve these Hanlu capabilities

- Dashboard with today’s work, due reviews, and recent activity.
- Vocabulary browser with topics, filters, sorting, level badges, known/needs
  practice controls, and filtered practice sessions.
- Spaced repetition for both reading recognition and listening.
- Topic progress broken down by level.
- Story reader with sentence-by-sentence progress, audio, translation, word
  meanings, vocabulary exposure, difficult-word marking, and New/Reading/Finished
  states.
- Grammar curriculum with lesson theory, multiple examples, focused practice,
  mixed practice, New/Practicing/Learned states, accuracy, mastery suggestions,
  and automatic status progression.
- Grammar helpers that expose incidental vocabulary without revealing the
  grammar answer being tested.
- Natural-answer grading, manual correction overrides, problem reporting,
  “Skip & flag this sentence,” and optional real-time DeepSeek explanation and
  verification.
- Local progress export/import and visible AI token/cost totals.
- Keyboard shortcuts and on-demand audio wherever a target-language sentence
  appears.

## Replace the Chinese-specific learning model

- Replace HSK levels with CEFR levels. Build a complete A1 foundation and a
  useful A2 curriculum first. Mark B1 and later levels as work in progress until
  their content is genuinely complete.
- Replace hanzi, pinyin, and character readings with Spanish spelling, lemma,
  part of speech, grammatical gender, plural form, and useful conjugation
  information.
- Use natural Spanish audio with a clearly documented regional default. Start
  with neutral Spain Spanish unless I choose another variety, and keep the
  architecture ready for Latin American variants.
- Make grading accent-aware. Missing written accents should produce specific
  feedback and should not be treated as an unrelated grammar failure.
- Account for acceptable regional and register variants such as
  vosotros/ustedes where appropriate. Do not mix variants silently inside one
  lesson.
- Model Spanish-specific morphology and grammar rather than treating every
  surface form as an unrelated vocabulary item.

## Initial Spanish grammar scope

Create reviewed lesson theory and separate non-duplicating practice pools for,
at minimum:

- noun gender and number;
- definite and indefinite articles;
- subject pronouns and when Spanish omits them;
- present-tense regular verbs;
- high-frequency irregular verbs, including ser, estar, tener, ir, hacer,
  poder, querer, and venir;
- ser versus estar;
- hay versus está/están;
- adjective agreement and placement;
- negation;
- yes/no and information questions;
- possessives and demonstratives;
- gustar and similar constructions;
- direct and indirect object pronouns;
- reflexive verbs and daily routines;
- common prepositions;
- ir a + infinitive;
- present progressive;
- commands appropriate to the selected regional variety;
- preterite versus imperfect at the appropriate CEFR stage;
- por versus para;
- present perfect where appropriate to the selected variety.

Every lesson should have at least five reviewed theory examples and at least ten
different reviewed practice examples. Practice sentences must primarily test
the stated lesson and should avoid requiring grammar that has not yet been
introduced. Do not use unreviewed machine-translated or scraped examples.

## Vocabulary and stories

- Start with a properly licensed, documented A1–A2 Spanish vocabulary source.
- Organize vocabulary into practical topics such as people, home, food,
  routines, work and study, travel, health, shopping, time, weather, feelings,
  and communication.
- Store learner-friendly primary meanings plus additional senses and examples.
- Create at least twelve original graded stories with natural Spanish and
  sentence-level audio.
- Track words encountered through stories in the same knowledge system as
  vocabulary practice.
- Keep theory examples and practice examples separate and prevent immediate or
  session-level duplicates.

## AI review

Retain Hanlu’s provider-neutral AI review layer with DeepSeek as the first local
provider. Use a local `.env.local` file and a committed blank `.env.example`.
The AI should judge the grammar target separately from incidental vocabulary,
spelling, accents, punctuation, register, and equally natural wording. It must
show its verdict, confidence, explanation, meaningful differences, and a
suggested natural answer. Confident accepted answers may repair the score and
create a maintenance report when the deterministic grader needs improvement.

The tutor must remain fully usable without an API key or internet connection;
only explicitly requested AI reviews may leave the computer.

## Implementation approach

1. Inspect Hanlu’s README, architecture, database schema, tests, and current
   learner workflows before changing code.
2. Create a separate project/repository rather than overwriting the Chinese
   tutor.
3. Preserve the existing FastAPI, SQLite, server-rendered interface, local
   startup flow, and test discipline unless there is a concrete reason to
   change them.
4. Rename the product and visual copy for Spanish while retaining the polished,
   compact interaction style.
5. Remove Chinese-only content and assumptions cleanly; do not leave dead HSK,
   pinyin, or hanzi fields disguised under Spanish labels.
6. Seed only reviewed Spanish content and document every external dataset and
   license.
7. Add migrations that preserve progress as the Spanish app evolves.
8. Run the complete test suite and verify that `./run.sh` starts the local app.
9. Write a clear README covering setup, offline behavior, backups, API-key
   security, progress export, tests, and GitHub publishing.
10. Keep a backlog for later B1+ content, additional regional varieties, weekly
    AI coaching, multi-user hosting, and mobile/PWA work.

Make reasonable product decisions without pausing for minor questions. Ask me
only when a choice would materially change the language variety, curriculum,
data licensing, or privacy model. Start by proposing the new repository name,
confirming the Spanish regional variety, and showing me the adaptation plan
before implementing the content migration.

---

Suggested first project name: **Senda Spanish Tutor**.
