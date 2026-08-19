import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the Hanlu hosted beta", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>汉路 Hanlu · Chinese Tutor<\/title>/i);
  assert.match(html, /Chinese that lives in context/);
  assert.match(html, /1,261/);
  assert.match(html, /18/);
  assert.match(html, /90/);
  assert.match(html, /Writing/);
  assert.match(html, /Write something real/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});

test("hosted curriculum keeps the rich vocabulary and complete story export", async () => {
  const data = JSON.parse(await readFile(
    new URL("../app/hanlu-data.json", import.meta.url),
    "utf8",
  ));
  assert.equal(data.words.length, 1261);
  assert.equal(data.stories.length, 18);
  assert.equal(data.grammar.length, 90);
  assert.ok(data.words.every((word) => Array.isArray(word.hskLevels)));
  assert.ok(data.words.every((word) => typeof word.audio === "string"));
  assert.ok(data.stories.every((story) => Number.isInteger(story.hskLevel)));
  assert.ok(data.stories.every((story) => story.sentences.every(
    (sentence) => sentence.audio && Array.isArray(sentence.words),
  )));
});

test("every hosted curriculum audio reference exists and is non-empty", async () => {
  const data = JSON.parse(await readFile(
    new URL("../app/hanlu-data.json", import.meta.url),
    "utf8",
  ));
  const names = new Set([
    ...data.words.map((word) => word.audio),
    ...data.stories.flatMap((story) => story.sentences.map((sentence) => sentence.audio)),
    ...data.grammar.flatMap((lesson) => lesson.examples.map((example) => example.audio)),
  ]);
  assert.ok(names.size > 1700);
  for (const name of names) {
    const info = await stat(new URL(`../public/audio/${name}`, import.meta.url));
    assert.ok(info.size > 0, `${name} is empty`);
  }
});

test("progress import is authenticated, private, and includes local learning dimensions", async () => {
  const route = await readFile(
    new URL("../app/api/progress/import/route.ts", import.meta.url),
    "utf8",
  );
  const schema = await readFile(
    new URL("../db/schema.ts", import.meta.url),
    "utf8",
  );
  assert.match(route, /getChatGPTUser/);
  assert.match(route, /learner_import_backup/);
  assert.match(route, /memory_state/);
  assert.match(route, /review_log/);
  assert.match(route, /grammar_state/);
  assert.match(route, /story_sentence_progress/);
  assert.match(route, /story_word_exposure/);
  assert.match(schema, /learnerImportBackup/);
});

test("offline cache excludes private progress and authentication routes", async () => {
  const serviceWorker = await readFile(
    new URL("../public/sw.js", import.meta.url),
    "utf8",
  );
  assert.match(serviceWorker, /pathname\.startsWith\("\/api\/"\)/);
  assert.match(serviceWorker, /pathname\.startsWith\("\/signin-with-chatgpt"\)/);
  assert.match(serviceWorker, /networkFirstNavigation/);
  assert.match(serviceWorker, /CACHE_APP_SHELL/);
});

test("writing review keeps DeepSeek server-side and enforces small daily limits", async () => {
  const route = await readFile(
    new URL("../app/api/writing/review/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(route, /DEEPSEEK_API_KEY/);
  assert.match(route, /DAILY_REQUEST_LIMIT = 35/);
  assert.match(route, /DAILY_BUDGET_MICRO_USD = 20_000/);
  assert.doesNotMatch(route, /NEXT_PUBLIC_DEEPSEEK|apiKey:\s*["'][^"']+/);
});

test("the interface never declares text smaller than 14px", async () => {
  const stylesheet = await readFile(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  const undersized = [...stylesheet.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g)]
    .map((match) => Number(match[1]))
    .filter((size) => size < 14);
  assert.deepEqual(undersized, []);
});
