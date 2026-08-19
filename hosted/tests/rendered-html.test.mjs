import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
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
  assert.match(html, /12/);
  assert.match(html, /90/);
  assert.match(html, /Writing/);
  assert.match(html, /Write something real/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
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
