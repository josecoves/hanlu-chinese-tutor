(() => {
  const statusLabel = value => value === "not_started" ? "new" : value.replace("_", " ");

  document.querySelectorAll("[data-auto-status]").forEach(form => {
    const select = form.querySelector("select[name=status]");
    const state = form.querySelector(".save-state");
    if (!select) return;
    select.addEventListener("change", async () => {
      const previous = form.dataset.currentStatus;
      const next = select.value;
      const payload = new FormData(form);
      select.disabled = true;
      if (state) state.textContent = "Saving…";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: payload,
          headers: {"X-Requested-With": "hanlu"}
        });
        if (!response.ok) throw new Error("status save failed");
        form.dataset.currentStatus = next;
        const tile = form.closest(".grammar-tile");
        if (tile) tile.dataset.status = next;
        const badge = document.querySelector("[data-status-badge]");
        if (badge) {
          badge.className = `lesson-status ${next}`;
          badge.textContent = statusLabel(next);
        }
        const name = document.querySelector("[data-status-name]");
        if (name) name.textContent = statusLabel(next);
        const oldCount = document.querySelector(`[data-status-count="${previous}"]`);
        const newCount = document.querySelector(`[data-status-count="${next}"]`);
        if (previous !== next && oldCount && newCount) {
          oldCount.textContent = Math.max(0, Number(oldCount.textContent) - 1);
          newCount.textContent = Number(newCount.textContent) + 1;
        }
        if (state) state.textContent = "Saved";
        document.dispatchEvent(new Event("grammar-filter-change"));
      } catch (_) {
        select.value = previous;
        if (state) state.textContent = "Couldn’t save — try again";
      } finally {
        select.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-mark-learned]").forEach(button => {
    button.addEventListener("click", () => {
      const select = document.getElementById(button.dataset.target);
      if (!select) return;
      select.value = "learned";
      select.dispatchEvent(new Event("change", {bubbles: true}));
      button.remove();
    });
  });

  const search = document.getElementById("grammar-search");
  const levelFilter = document.getElementById("grammar-level-filter");
  const statusFilter = document.getElementById("grammar-status-filter");
  const resultCount = document.getElementById("grammar-result-count");
  const tiles = [...document.querySelectorAll(".grammar-tile")];
  const applyFilters = () => {
    if (!tiles.length) return;
    const query = (search?.value || "").trim().toLowerCase();
    const level = levelFilter?.value || "";
    const status = statusFilter?.value || "";
    let visible = 0;
    tiles.forEach(tile => {
      const show = (!query || tile.dataset.search.includes(query))
        && (!level || tile.dataset.level === level)
        && (!status || tile.dataset.status === status);
      tile.hidden = !show;
      if (show) visible += 1;
    });
    document.querySelectorAll("[data-grammar-level]").forEach(section => {
      section.hidden = !section.querySelector(".grammar-tile:not([hidden])");
    });
    if (resultCount) resultCount.textContent = visible;
  };
  [search, levelFilter, statusFilter].forEach(control => {
    control?.addEventListener(control === search ? "input" : "change", applyFilters);
  });
  document.getElementById("grammar-filter-clear")?.addEventListener("click", () => {
    if (search) search.value = "";
    if (levelFilter) levelFilter.value = "";
    if (statusFilter) statusFilter.value = "";
    applyFilters();
  });
  document.addEventListener("grammar-filter-change", applyFilters);

  document.addEventListener("click", async event => {
    const button = event.target.closest(
      "[data-accept-attempt],[data-undo-attempt],"
      + "[data-request-ai-review],[data-cancel-ai-review]"
    );
    if (!button) return;
    event.preventDefault();
    const state = document.querySelector("[data-grading-state]");
    const action = button.hasAttribute("data-accept-attempt") ? "accept"
      : button.hasAttribute("data-undo-attempt") ? "undo"
      : button.hasAttribute("data-request-ai-review") ? "request"
      : "cancel";
    button.disabled = true;
    if (state) state.textContent = "Updating…";
    try {
      const response = await fetch(button.dataset.url, {
        method: "POST",
        headers: {"X-Requested-With": "hanlu"}
      });
      if (!response.ok) throw new Error("grading action failed");
      const verdict = document.getElementById("grammar-verdict");
      const comparison = document.getElementById("answer-comparison");
      if (action === "accept") {
        if (verdict) {
          verdict.className = "verdict correct";
          verdict.textContent = "✓ Marked correct by you";
        }
        comparison?.classList.add("accepted");
        button.removeAttribute("data-accept-attempt");
        button.setAttribute("data-undo-attempt", "");
        button.dataset.url = button.dataset.url.replace("/accept", "/undo-accept");
        button.textContent = "Undo my “correct” mark";
        if (state) state.textContent = "Saved · this is reversible";
      } else if (action === "undo") {
        if (verdict) {
          verdict.className = "verdict wrong";
          verdict.textContent = "✕ Keep building";
        }
        comparison?.classList.remove("accepted");
        button.removeAttribute("data-undo-attempt");
        button.setAttribute("data-accept-attempt", "");
        button.dataset.url = button.dataset.url.replace("/undo-accept", "/accept");
        button.textContent = "Mark correct myself";
        if (state) state.textContent = "Your override was undone";
      } else if (action === "request") {
        button.removeAttribute("data-request-ai-review");
        button.setAttribute("data-cancel-ai-review", "");
        button.dataset.url = button.dataset.url.replace(
          "/request-review", "/cancel-review"
        );
        button.textContent = "AI review queued ✓ · remove";
        if (state) state.textContent = "Saved for a later AI check";
      } else {
        button.removeAttribute("data-cancel-ai-review");
        button.setAttribute("data-request-ai-review", "");
        button.dataset.url = button.dataset.url.replace(
          "/cancel-review", "/request-review"
        );
        button.textContent = "Ask AI to check";
        if (state) state.textContent = "Removed from AI review queue";
      }
    } catch (_) {
      if (state) state.textContent = "Couldn’t update — try again";
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener("click", event => {
    const toggle = event.target.closest(".toggle-pinyin");
    if (toggle) {
      const target = document.getElementById(toggle.dataset.target);
      if (target) {
        target.hidden = !target.hidden;
        toggle.setAttribute("aria-expanded", String(!target.hidden));
      }
      return;
    }
    const speak = event.target.closest(".speak-chinese");
    if (!speak) return;
    const original = speak.textContent;
    speak.disabled = true;
    speak.textContent = "Loading audio…";
    const audio = new Audio(`/grammar-audio?text=${encodeURIComponent(speak.dataset.zh)}`);
    audio.addEventListener("playing", () => { speak.textContent = "Playing…"; });
    const reset = () => {
      speak.disabled = false;
      speak.textContent = original;
    };
    audio.addEventListener("ended", reset, {once: true});
    audio.addEventListener("error", () => {
      speak.textContent = "Audio unavailable";
      setTimeout(reset, 1600);
    }, {once: true});
    audio.play().catch(reset);
  });
})();
