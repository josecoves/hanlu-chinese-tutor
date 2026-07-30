(() => {
  const typing = target =>
    target && (target.matches("input, textarea, select") || target.isContentEditable);
  const toggle = id => {
    const details = document.getElementById(id);
    if (details) details.open = !details.open;
  };
  document.addEventListener("keydown", event => {
    if (typing(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.toLowerCase();
    if (/^[1-4]$/.test(key)) {
      const choice = document.querySelector(`[data-choice-index="${key}"]`);
      if (choice) {
        event.preventDefault();
        choice.click();
      }
    } else if (key === "0") {
      const unknown = document.querySelector("[data-dont-know]");
      if (unknown) {
        event.preventDefault();
        unknown.click();
      }
    } else if (key === "a") {
      const audio = document.getElementById("practice-audio");
      if (audio) {
        event.preventDefault();
        audio.currentTime = 0;
        audio.play();
      }
    } else if (key === "p") {
      toggle("pinyin-details");
    } else if (key === "w") {
      toggle("word-details");
    } else if (key === "t") {
      toggle("translation-details");
    } else if (key === "z" || key === "c") {
      toggle("context-details");
    } else if (key === "enter" || key === "arrowright") {
      const next = document.getElementById("practice-next");
      if (next) {
        event.preventDefault();
        next.click();
      }
    }
  });

  document.querySelectorAll("[data-report-form]").forEach(form => {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const button = form.querySelector("button");
      const note = form.querySelector("textarea");
      const state = form.querySelector("[data-report-state]");
      if (!note?.value.trim()) {
        if (state) state.textContent = "Please describe the problem.";
        return;
      }
      button.disabled = true;
      if (state) state.textContent = "Saving…";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: {"X-Requested-With": "hanlu"}
        });
        if (!response.ok) throw new Error("report save failed");
        note.value = "";
        if (state) state.textContent = "Report saved — continue this card.";
      } catch (_) {
        if (state) state.textContent = "Couldn’t save — try again.";
      } finally {
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-vocab-knowledge]").forEach(form => {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const button = form.querySelector("button");
      const state = form.querySelector("[aria-live]");
      button.disabled = true;
      if (state) state.textContent = "Adding…";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: {"X-Requested-With": "hanlu"}
        });
        if (!response.ok) throw new Error("knowledge save failed");
        button.textContent = "In practice queue ✓";
        if (state) state.textContent = "";
      } catch (_) {
        button.disabled = false;
        if (state) state.textContent = "Couldn’t add — try again.";
      }
    });
  });
})();
