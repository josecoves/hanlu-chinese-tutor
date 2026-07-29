(() => {
  document.querySelectorAll("[data-story-status-form]").forEach(form => {
    const select = form.querySelector("select");
    const state = form.querySelector("[data-save-state]");
    select.addEventListener("change", async () => {
      const body = new FormData(form);
      select.disabled = true;
      if (state) state.textContent = "Saving…";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body,
          headers: {"X-Requested-With": "hanlu"},
        });
        if (!response.ok) throw new Error("save failed");
        const card = form.closest("[data-story-status-card]");
        if (card) card.dataset.status = select.value;
        if (state) state.textContent = "Saved";
      } catch (_error) {
        if (state) state.textContent = "Couldn’t save";
      } finally {
        select.disabled = false;
      }
    });
  });
})();
