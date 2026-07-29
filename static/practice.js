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
})();
