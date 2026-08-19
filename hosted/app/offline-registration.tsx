"use client";

import { useEffect } from "react";

export function OfflineRegistration() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    void navigator.serviceWorker.register("/sw.js").then(async (registration) => {
      await navigator.serviceWorker.ready;
      const assetUrls = new Set<string>([window.location.origin + "/"]);
      document.querySelectorAll<HTMLScriptElement>("script[src]").forEach((element) => {
        assetUrls.add(element.src);
      });
      document.querySelectorAll<HTMLLinkElement>("link[href]").forEach((element) => {
        if (["stylesheet", "modulepreload", "preload"].includes(element.rel)) {
          assetUrls.add(element.href);
        }
      });
      document.querySelectorAll<HTMLImageElement>("img[src]").forEach((element) => {
        assetUrls.add(element.src);
      });
      registration.active?.postMessage({
        type: "CACHE_APP_SHELL",
        urls: [...assetUrls],
      });
    }).catch(() => {
      // Online use remains fully functional when offline caching is unavailable.
    });
  }, []);

  return null;
}
