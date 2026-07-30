# 汉路 Hanlu — hosted beta

This directory contains the Cloudflare-compatible hosted curriculum preview.
It is intentionally separate from the local FastAPI tutor so the offline app
and its private SQLite progress remain untouched.

The hosted beta includes:

- all 1,261 HSK 1–2 vocabulary entries;
- all 12 original stories with pinyin, translation, and device speech;
- all 90 grammar lessons with examples;
- HSK and topic browsing; and
- responsive desktop and mobile layouts.

Account-based review history and synchronized progress are not enabled in this
first hosted version. Visitors cannot access or overwrite the local learner
database.

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
