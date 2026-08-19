# 汉路 Hanlu — hosted beta

This directory contains the Cloudflare-compatible hosted curriculum preview.
It is intentionally separate from the local FastAPI tutor so the offline app
and its private SQLite progress remain untouched.

The hosted beta includes:

- all 1,261 HSK 1–2 vocabulary entries;
- all 12 original stories with pinyin, translation, and device speech;
- all 90 grammar lessons with examples;
- HSK and topic browsing;
- a writing studio for short responses, message replies, translation, and
  target-word practice, with offline draft recovery and optional DeepSeek
  feedback; and
- responsive desktop and mobile layouts.

Story progress, grammar status, and writing history sync privately for the
signed-in learner. Visitors cannot access or overwrite the local learner
database.

The optional server-side writing reviewer uses `DEEPSEEK_API_KEY` and
`DEEPSEEK_MODEL`. It deliberately limits usage to 35 requests and a $0.02
reservation budget per UTC day. No provider key is sent to browser code.

Known hosted-beta issue: story audio currently uses device speech and can sound
less natural than the cached neural audio in the local tutor. Replace it with
hosted neural clips before treating the reader as production-ready.

Run locally with:

```bash
npm ci
npm run dev
```

Validate with:

```bash
npm test
```
