const CACHE_NAME = "hanlu-offline-v2";
const SHELL_KEY = "/__hanlu_offline_shell__";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith("hanlu-offline-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "CACHE_APP_SHELL" || !Array.isArray(event.data.urls)) return;
  event.waitUntil(cacheAppShell(event.data.urls));
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isPrivateNetworkRoute(url.pathname)) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  event.respondWith(cacheFirstAsset(request));
});

function isPrivateNetworkRoute(pathname) {
  return (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/signin-with-chatgpt") ||
    pathname.startsWith("/signout-with-chatgpt") ||
    pathname.startsWith("/callback")
  );
}

async function cacheAppShell(urls) {
  const cache = await caches.open(CACHE_NAME);
  const safeUrls = urls
    .map((value) => {
      try {
        return new URL(value, self.location.origin);
      } catch {
        return null;
      }
    })
    .filter((url) => url && url.origin === self.location.origin)
    .filter((url) => !isPrivateNetworkRoute(url.pathname));

  await Promise.all(safeUrls.map(async (url) => {
    try {
      const response = await fetch(url.href, { credentials: "same-origin" });
      if (!response.ok) return;
      const key = url.pathname === "/" ? SHELL_KEY : url.href;
      await cache.put(key, response);
    } catch {
      // A later online visit will fill anything that was temporarily unavailable.
    }
  }));
}

async function networkFirstNavigation(request) {
  try {
    const response = await fetch(request);
    if (response.ok && new URL(request.url).pathname === "/") {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(SHELL_KEY, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(SHELL_KEY);
    if (cached) return cached;
    return new Response(
      "<!doctype html><html><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Hanlu offline</title><body style='font:18px system-ui;padding:32px;line-height:1.6'><h1>Hanlu is offline</h1><p>Reconnect once to finish preparing this device for offline use.</p></body></html>",
      { headers: { "content-type": "text/html; charset=utf-8" }, status: 503 },
    );
  }
}

async function cacheFirstAsset(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
  }
  return response;
}
