(() => {
  document.querySelectorAll("[data-review-toggle]").forEach(form => {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const input = form.querySelector("input[name=state]");
      const button = form.querySelector("button");
      const marking = input.value === "needs_practice";
      const previousText = button.textContent;
      button.disabled = true;
      button.textContent = "…";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: {"X-Requested-With": "hanlu"}
        });
        if (!response.ok) throw new Error("review toggle failed");
        input.value = marking ? "auto" : "needs_practice";
        button.classList.toggle("active", marking);
        button.textContent = marking ? "R✓" : "+R";
        button.title = marking
          ? "Marked for review · click to undo"
          : "Add to review";
        button.setAttribute(
          "aria-label",
          marking
            ? "Marked for review. Click to restore automatic knowledge status."
            : "Add this word to review"
        );
      } catch (_) {
        button.textContent = "!";
        button.title = "Couldn’t update · try again";
        setTimeout(() => {
          button.textContent = previousText;
          button.title = marking
            ? "Add to review"
            : "Marked for review · click to undo";
        }, 1500);
      } finally {
        button.disabled = false;
      }
    });
  });
})();
