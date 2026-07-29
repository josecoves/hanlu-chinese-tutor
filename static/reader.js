(() => {
  const payload = JSON.parse(document.querySelector("#story-data").textContent);
  const data = payload.sentences;
  const storyId = payload.story_id;
  let index = Math.max(0, Math.min(data.length - 1, payload.start_index || 0));
  let mode = "reading";
  const el = id => document.getElementById(id);
  const typing = target =>
    target && (target.matches("input, textarea, select") || target.isContentEditable);

  function renderWords(sentence) {
    const host = el("reader-words");
    host.replaceChildren();
    sentence.words.forEach(word => {
      const label = document.createElement("label");
      label.className = `reader-word${word.hard ? " hard" : ""}`;
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = word.id;
      input.checked = Boolean(word.hard);
      input.addEventListener("change", () => {
        word.hard = input.checked;
        label.classList.toggle("hard", input.checked);
      });
      const hanzi = document.createElement("b");
      hanzi.textContent = word.headword;
      const detail = document.createElement("span");
      detail.textContent = `${word.pinyin} · ${word.gloss}`;
      const flag = document.createElement("em");
      flag.textContent = input.checked ? "Hard ✓" : "Mark hard";
      input.addEventListener("change", () => {
        flag.textContent = input.checked ? "Hard ✓" : "Mark hard";
      });
      label.append(input, hanzi, detail, flag);
      host.append(label);
    });
    if (!sentence.words.length) {
      const empty = document.createElement("p");
      empty.className = "reader-no-words";
      empty.textContent = "No tracked vocabulary in this sentence.";
      host.append(empty);
    }
  }

  function render() {
    const sentence = data[index];
    el("reader-zh").textContent = sentence.zh;
    el("reader-py").textContent = sentence.py;
    el("reader-en").textContent = sentence.en;
    el("position").textContent = `${index + 1} / ${data.length}`;
    el("reader-meter").style.width = `${(index + 1) / data.length * 100}%`;
    el("reader-zh").hidden = mode === "listening";
    el("reader-py").hidden = true;
    el("reader-en").hidden = true;
    el("mode").textContent = mode === "reading" ? "Reading mode" : "Listening mode";
    el("reader-save-state").textContent = sentence.completed
      ? "✓ This sentence is already in your study history. You can change its hard words and save again."
      : "";
    renderWords(sentence);
    const audio = el("reader-audio");
    audio.src = sentence.audio
      ? `/audio/${sentence.audio}`
      : `/grammar-audio?text=${encodeURIComponent(sentence.zh)}`;
    audio.hidden = false;
    if (mode === "listening") audio.play().catch(() => {});
    const next = el("next");
    next.disabled = false;
    next.textContent = index === data.length - 1 ? "Finish story ✓" : "Next →";
    el("reader-card").focus();
  }

  function move(delta) {
    index = Math.max(0, Math.min(data.length - 1, index + delta));
    render();
  }

  async function completeAndMove() {
    const next = el("next");
    if (next.disabled) return;
    next.disabled = true;
    el("reader-save-state").textContent = "Saving sentence vocabulary…";
    const hard = [...el("reader-words").querySelectorAll("input:checked")]
      .map(input => input.value).join(",");
    const body = new FormData();
    body.set("hard", hard);
    try {
      const response = await fetch(
        `/story/${storyId}/sentence/${index}/complete`,
        {method: "POST", body}
      );
      if (!response.ok) throw new Error("save failed");
      const result = await response.json();
      data[index].completed = true;
      el("sentence-study-count").textContent =
        `${result.completed} of ${result.total} sentences studied`;
      const status = document.querySelector("[data-story-status-form] select");
      if (status) status.value = result.status;
      if (index === data.length - 1) {
        el("reader-save-state").textContent =
          `✓ Story finished. ${result.studied_words} words studied; ${result.hard_words} marked hard in this sentence.`;
        next.textContent = "Finished ✓";
        return;
      }
      index += 1;
      render();
    } catch (_error) {
      el("reader-save-state").textContent =
        "Couldn’t save this sentence. Please try Next again.";
      next.disabled = false;
    }
  }

  function toggleMode() {
    mode = mode === "reading" ? "listening" : "reading";
    render();
  }

  el("prev").onclick = () => move(-1);
  el("next").onclick = completeAndMove;
  el("mode").onclick = toggleMode;
  el("characters").onclick = () => el("reader-zh").hidden = !el("reader-zh").hidden;
  el("pinyin").onclick = () => el("reader-py").hidden = !el("reader-py").hidden;
  el("translation").onclick = () => el("reader-en").hidden = !el("reader-en").hidden;
  el("audio").onclick = () => {
    const audio = el("reader-audio");
    audio.currentTime = 0;
    audio.play().catch(() => {});
  };
  document.addEventListener("keydown", event => {
    if (typing(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === "ArrowLeft") move(-1);
    else if (event.key === "ArrowRight") completeAndMove();
    else if (event.key.toLowerCase() === "a") el("audio").click();
    else if (event.key.toLowerCase() === "z") el("characters").click();
    else if (event.key.toLowerCase() === "p") el("pinyin").click();
    else if (event.key.toLowerCase() === "t") el("translation").click();
    else if (event.key.toLowerCase() === "m") toggleMode();
  });
  render();
})();
